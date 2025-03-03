#!/usr/bin/env python3
"""
ONVIF Device Discovery Tool

This script implements ONVIF device discovery similar to node-onvif's startProbe() functionality.
It uses WS-Discovery protocol and direct network scanning to find ONVIF-compliant devices.

Usage:
  python onvif_discovery.py [--timeout SECONDS] [--json] [--no-scan] [--subnet SUBNET] [--ports PORTS]

Options:
  --timeout SECONDS  Set discovery timeout (default: 15 seconds)
  --json            Output results in JSON format
  --no-scan         Disable network scanning (use only WS-Discovery)
  --subnet SUBNET   Subnet to scan (default: auto-detect)
  --ports PORTS     Comma-separated list of ports to check (default: 80,8000,8080,554)
  --user USER       Username for authentication (default: admin)
  --password PASS   Password for authentication (default: admin)
  --wsdl DIR        Path to WSDL directory (default: auto-detect)
"""

import sys
import logging
import threading
import time
import socket
import uuid
import re
import json
import argparse
from urllib.parse import urlparse
import traceback
import ipaddress
import concurrent.futures
import os
import inspect
import netifaces

try:
    from onvif import ONVIFCamera
    import onvif
    from zeep import Client
    from zeep.transports import Transport
    from requests import Session
except ImportError:
    print("Error: Required packages are not installed.")
    print("Please install them using: pip install onvif zeep netifaces")
    sys.exit(1)

# Setup logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Suppress excessive logging from requests
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("zeep").setLevel(logging.WARNING)

def get_wsdl_dir():
    """
    Find the WSDL directory from the onvif package
    """
    # Get the directory of the onvif package
    onvif_dir = os.path.dirname(inspect.getfile(onvif))
    
    # Check for wsdl directory in common locations
    possible_paths = [
        os.path.join(onvif_dir, 'wsdl'),
        os.path.join(onvif_dir, 'schema', 'wsdl'),
        os.path.join(os.path.dirname(onvif_dir), 'wsdl'),
        os.path.join(os.path.dirname(onvif_dir), 'schema', 'wsdl'),
        './wsdl'  # Local wsdl directory
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            logger.debug(f"Found WSDL directory at: {path}")
            return path
    
    # If we can't find it, try to get it from the ONVIFCamera class
    try:
        # Create a dummy camera to get the wsdl_dir
        dummy_cam = ONVIFCamera('0.0.0.0', 80, 'dummy', 'dummy', no_cache=True)
        if hasattr(dummy_cam, 'wsdl_dir') and dummy_cam.wsdl_dir:
            logger.debug(f"Found WSDL directory from ONVIFCamera: {dummy_cam.wsdl_dir}")
            return dummy_cam.wsdl_dir
    except:
        pass
    
    logger.warning("Could not find WSDL directory. Connection may fail.")
    return None

def get_local_subnets():
    """Get local subnets from network interfaces"""
    subnets = []
    try:
        # Get all network interfaces
        interfaces = netifaces.interfaces()
        for interface in interfaces:
            # Skip loopback interface
            if interface.startswith('lo'):
                continue
                
            # Get addresses for this interface
            addresses = netifaces.ifaddresses(interface)
            
            # Check for IPv4 addresses
            if netifaces.AF_INET in addresses:
                for address in addresses[netifaces.AF_INET]:
                    if 'addr' in address and 'netmask' in address:
                        ip = address['addr']
                        netmask = address['netmask']
                        
                        # Skip loopback addresses
                        if ip.startswith('127.'):
                            continue
                            
                        # Calculate network address and CIDR
                        try:
                            # Convert netmask to CIDR notation
                            netmask_bits = sum([bin(int(x)).count('1') for x in netmask.split('.')])
                            subnet = f"{ip}/{netmask_bits}"
                            
                            # Create a proper network address
                            network = ipaddress.IPv4Network(f"{ip}/{netmask}", strict=False)
                            subnet = str(network)
                            
                            subnets.append(subnet)
                        except Exception as e:
                            logger.debug(f"Error calculating subnet for {ip}/{netmask}: {e}")
    except Exception as e:
        logger.warning(f"Error getting local subnets: {e}")
    
    # If no subnets found, use a default
    if not subnets:
        subnets = ['192.168.1.0/24']
    
    return subnets

class OnvifDiscovery:
    """
    Class to handle ONVIF device discovery similar to node-onvif's startProbe()
    """
    def __init__(self):
        self.devices = []
        self.is_running = False
        self.discovery_thread = None
        self.stop_event = threading.Event()
        
    def _create_probe_message(self):
        """Create a WS-Discovery probe message"""
        message_id = uuid.uuid4().urn
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope" xmlns:a="http://schemas.xmlsoap.org/ws/2004/08/addressing">
  <s:Header>
    <a:Action s:mustUnderstand="1">http://schemas.xmlsoap.org/ws/2005/04/discovery/Probe</a:Action>
    <a:MessageID>{message_id}</a:MessageID>
    <a:ReplyTo>
      <a:Address>http://schemas.xmlsoap.org/ws/2004/08/addressing/role/anonymous</a:Address>
    </a:ReplyTo>
    <a:To s:mustUnderstand="1">urn:schemas-xmlsoap-org:ws:2005:04:discovery</a:To>
  </s:Header>
  <s:Body>
    <Probe xmlns="http://schemas.xmlsoap.org/ws/2005/04/discovery">
      <d:Types xmlns:d="http://schemas.xmlsoap.org/ws/2005/04/discovery" xmlns:dp0="http://www.onvif.org/ver10/network/wsdl">dp0:NetworkVideoTransmitter</d:Types>
    </Probe>
  </s:Body>
</s:Envelope>"""

    def _parse_probe_response(self, response):
        """Parse the WS-Discovery probe response to extract device information"""
        try:
            # Extract XAddrs (device service URLs)
            xaddrs_match = re.search(r'<d:XAddrs>(.*?)</d:XAddrs>', response, re.DOTALL)
            if not xaddrs_match:
                return None
                
            xaddrs = xaddrs_match.group(1).strip()
            urls = xaddrs.split()
            
            if not urls:
                return None
                
            # Use the first URL
            url = urls[0]
            parsed_url = urlparse(url)
            
            # Extract IP and port
            ip = parsed_url.hostname
            port = parsed_url.port or 80
            
            # Extract device types
            types_match = re.search(r'<d:Types>(.*?)</d:Types>', response, re.DOTALL)
            types = types_match.group(1).strip() if types_match else ""
            
            # Extract scopes
            scopes_match = re.search(r'<d:Scopes>(.*?)</d:Scopes>', response, re.DOTALL)
            scopes = scopes_match.group(1).strip() if scopes_match else ""
            
            # Extract device information from scopes
            name = "Unknown"
            hardware = "Unknown"
            location = "Unknown"
            
            if scopes:
                # Try to extract name
                name_match = re.search(r'onvif://www\.onvif\.org/name/([^\s]+)', scopes)
                if name_match:
                    name = name_match.group(1).replace('_', ' ')
                
                # Try to extract hardware
                hardware_match = re.search(r'onvif://www\.onvif\.org/hardware/([^\s]+)', scopes)
                if hardware_match:
                    hardware = hardware_match.group(1).replace('_', ' ')
                
                # Try to extract location
                location_match = re.search(r'onvif://www\.onvif\.org/location/([^\s]+)', scopes)
                if location_match:
                    location = location_match.group(1).replace('_', ' ')
            
            # Create device info object
            device_info = {
                'xaddrs': xaddrs,
                'url': url,
                'ip': ip,
                'port': port,
                'name': name,
                'hardware': hardware,
                'location': location,
                'types': types,
                'scopes': scopes,
                'discovery_method': 'WS-Discovery'
            }
            
            return device_info
            
        except Exception as e:
            logger.error(f"Error parsing probe response: {e}")
            logger.debug(traceback.format_exc())
            return None

    def _discovery_thread_func(self, timeout=15):
        """Thread function to handle the discovery process"""
        # Create a UDP socket for multicast
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 4)
        sock.settimeout(5)  # 5 seconds timeout
        
        # Bind to all interfaces
        sock.bind(('', 0))
        
        # Create the probe message
        probe_msg = self._create_probe_message()
        
        # WS-Discovery multicast address and port
        multicast_addr = "239.255.255.250"
        multicast_port = 3702
        
        # Send the probe message
        sock.sendto(probe_msg.encode(), (multicast_addr, multicast_port))
        
        # Receive responses until stopped
        start_time = time.time()
        while not self.stop_event.is_set() and (time.time() - start_time) < timeout:
            try:
                sock.settimeout(1)  # 1 second timeout for each receive attempt
                data, addr = sock.recvfrom(8192)
                response = data.decode('utf-8')
                
                # Parse the response
                device_info = self._parse_probe_response(response)
                if device_info:
                    # Check if this device is already in our list (by IP)
                    is_new = True
                    for device in self.devices:
                        if device['ip'] == device_info['ip']:
                            is_new = False
                            break
                    
                    if is_new:
                        self.devices.append(device_info)
                        logger.info(f"Discovered ONVIF device: {device_info['name']} at {device_info['ip']}:{device_info['port']}")
                
            except socket.timeout:
                # This is expected, just continue
                pass
            except Exception as e:
                logger.error(f"Error in discovery thread: {e}")
                logger.debug(traceback.format_exc())
        
        # Close the socket
        sock.close()
        self.is_running = False
        logger.info(f"WS-Discovery completed. Found {len(self.devices)} devices.")

    def start_probe(self, timeout=15):
        """Start the ONVIF device discovery process"""
        if self.is_running:
            logger.warning("Discovery is already running")
            return False
        
        # Clear previous results
        self.devices = []
        self.stop_event.clear()
        self.is_running = True
        
        # Start the discovery thread
        self.discovery_thread = threading.Thread(target=self._discovery_thread_func, args=(timeout,))
        self.discovery_thread.daemon = True
        self.discovery_thread.start()
        
        logger.info("ONVIF device discovery started")
        return True

    def stop_probe(self):
        """Stop the ONVIF device discovery process"""
        if not self.is_running:
            logger.warning("Discovery is not running")
            return False
        
        # Signal the thread to stop
        self.stop_event.set()
        
        # Wait for the thread to finish
        if self.discovery_thread and self.discovery_thread.is_alive():
            self.discovery_thread.join(timeout=2)
        
        self.is_running = False
        logger.info("ONVIF device discovery stopped")
        return True
    
    def get_devices(self):
        """Get the list of discovered devices"""
        return self.devices


def check_port_open(ip, port, timeout=1):
    """Check if a port is open on the given IP address"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((ip, port))
        sock.close()
        return result == 0
    except:
        return False


def check_onvif_device_with_zeep(ip, port, username='admin', password='admin', wsdl_dir=None):
    """
    Check if an IP:port combination is an ONVIF device using zeep and onvif libraries
    """
    try:
        # If no WSDL directory is provided, try to find it
        if wsdl_dir is None:
            wsdl_dir = get_wsdl_dir()
            
        if wsdl_dir is None:
            logger.warning(f"WSDL directory not found for {ip}:{port}")
            return None
            
        # Try to create an ONVIF camera instance
        cam = ONVIFCamera(ip, port, username, password, wsdl_dir=wsdl_dir, no_cache=True)
        
        # Get device information
        device_service = cam.create_devicemgmt_service()
        
        try:
            # Try to get device information
            device_info = device_service.GetDeviceInformation()
            
            # Create device info object
            return {
                'ip': ip,
                'port': port,
                'url': f"http://{ip}:{port}/onvif/device_service",
                'name': f"{getattr(device_info, 'Manufacturer', 'Unknown')} {getattr(device_info, 'Model', '')}".strip(),
                'hardware': getattr(device_info, 'Model', 'Unknown'),
                'location': 'Unknown',
                'firmware': getattr(device_info, 'FirmwareVersion', 'Unknown'),
                'serial': getattr(device_info, 'SerialNumber', 'Unknown'),
                'discovery_method': 'Network Scan'
            }
        except Exception as e:
            # If GetDeviceInformation fails, try a simpler request
            try:
                # Try to get system date and time
                device_service.GetSystemDateAndTime()
                
                # If we get here, it's an ONVIF device but we couldn't get detailed info
                return {
                    'ip': ip,
                    'port': port,
                    'url': f"http://{ip}:{port}/onvif/device_service",
                    'name': 'Unknown ONVIF Device',
                    'hardware': 'Unknown',
                    'location': 'Unknown',
                    'discovery_method': 'Network Scan'
                }
            except:
                # Not an ONVIF device or authentication failed
                return None
                
    except Exception as e:
        logger.debug(f"Error checking ONVIF device at {ip}:{port}: {e}")
        return None


def scan_network_for_onvif(subnet, ports, username='admin', password='admin', wsdl_dir=None, max_workers=20, specific_ip=None):
    """Scan a network subnet for ONVIF devices using zeep and onvif libraries"""
    logger.info(f"Starting network scan for ONVIF devices on subnet {subnet}")
    
    # If specific IP is provided, only scan that IP
    if specific_ip:
        ips_to_scan = [specific_ip]
        logger.info(f"Scanning specific IP: {specific_ip}")
    else:
        # Parse subnet
        network = ipaddress.ip_network(subnet)
        ips_to_scan = [str(ip) for ip in network.hosts()]
        logger.info(f"Scanning {len(ips_to_scan)} IP addresses")
    
    # Parse ports
    port_list = [int(p.strip()) for p in ports.split(',')]
    logger.info(f"Checking ports: {port_list}")
    
    # List to store found devices
    devices = []
    
    # First, find all IPs with open ports
    open_ports = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Create tasks for checking each IP and port combination
        futures = []
        for ip in ips_to_scan:
            for port in port_list:
                future = executor.submit(check_port_open, ip, port)
                futures.append((future, ip, port))
        
        # Process results as they complete
        for i, (future, ip, port) in enumerate(futures):
            if i % 50 == 0 and len(ips_to_scan) > 10:
                progress = (i / len(futures)) * 100
                logger.info(f"Port scan progress: {progress:.1f}% ({i}/{len(futures)})")
                
            if future.result():
                open_ports.append((ip, port))
                logger.debug(f"Found open port: {ip}:{port}")
    
    logger.info(f"Found {len(open_ports)} open ports. Checking for ONVIF devices...")
    
    # Now check each open port for ONVIF
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Create tasks for checking each IP with open port
        futures = []
        for ip, port in open_ports:
            # Try with default credentials first
            futures.append((executor.submit(check_onvif_device_with_zeep, ip, port, username, password, wsdl_dir), ip, port))
            
            # Also try with common alternative credentials if not the same as provided
            if username != 'admin' or password != 'admin':
                futures.append((executor.submit(check_onvif_device_with_zeep, ip, port, 'admin', 'admin', wsdl_dir), ip, port))
            
            # Try with empty password
            if password != '':
                futures.append((executor.submit(check_onvif_device_with_zeep, ip, port, username, '', wsdl_dir), ip, port))
        
        # Process results as they complete
        for future, ip, port in futures:
            result = future.result()
            if result:
                # Check if this device is already in our list (by IP)
                is_new = True
                for device in devices:
                    if device['ip'] == result['ip']:
                        is_new = False
                        break
                
                if is_new:
                    devices.append(result)
                    logger.info(f"Found ONVIF device at {result['ip']}:{result['port']}")
    
    logger.info(f"Network scan completed. Found {len(devices)} ONVIF devices.")
    return devices


def print_devices(devices, json_output=False):
    """Print discovered devices in human-readable or JSON format"""
    if json_output:
        print(json.dumps(devices, indent=2))
    else:
        if devices:
            print("\n=== Discovered ONVIF Devices ===")
            for i, device in enumerate(devices):
                print(f"Device {i+1}:")
                print(f"  Name: {device['name']}")
                print(f"  IP: {device['ip']}")
                print(f"  Port: {device['port']}")
                print(f"  Hardware: {device.get('hardware', 'Unknown')}")
                print(f"  Location: {device.get('location', 'Unknown')}")
                print(f"  URL: {device['url']}")
                if 'firmware' in device:
                    print(f"  Firmware: {device['firmware']}")
                if 'serial' in device:
                    print(f"  Serial: {device['serial']}")
                print(f"  Discovery Method: {device.get('discovery_method', 'Unknown')}")
                print("---")
            print(f"Total devices found: {len(devices)}")
        else:
            print("No ONVIF devices found on the network")


def main():
    """Main function to run the discovery process"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='ONVIF Device Discovery Tool')
    parser.add_argument('--timeout', type=int, default=15, help='Discovery timeout in seconds (default: 15)')
    parser.add_argument('--json', action='store_true', help='Output results in JSON format')
    parser.add_argument('--no-scan', action='store_true', help='Disable network scanning (use only WS-Discovery)')
    parser.add_argument('--subnet', help='Subnet to scan (default: auto-detect)')
    parser.add_argument('--ports', default='80,8000,8080,554', help='Comma-separated list of ports to check (default: 80,8000,8080,554)')
    parser.add_argument('--specific-ip', help='Check a specific IP address (can be used with --ports)')
    parser.add_argument('--user', default='admin', help='Username for authentication (default: admin)')
    parser.add_argument('--password', default='admin', help='Password for authentication (default: admin)')
    parser.add_argument('--wsdl', help='Path to WSDL directory (optional)')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    args = parser.parse_args()
    
    # Set debug logging if requested
    if args.debug:
        logger.setLevel(logging.DEBUG)
    
    all_devices = []
    
    # Run WS-Discovery
    print(f"Starting ONVIF WS-Discovery (timeout: {args.timeout} seconds)...")
    discovery = OnvifDiscovery()
    discovery.start_probe(timeout=args.timeout)
    
    # Wait for discovery to complete
    try:
        while discovery.is_running:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nDiscovery interrupted by user")
        discovery.stop_probe()
    
    # Get discovered devices
    ws_devices = discovery.get_devices()
    all_devices.extend(ws_devices)
    
    # If network scanning is not disabled, scan the network
    if not args.no_scan:
        # Get WSDL directory
        wsdl_dir = args.wsdl or get_wsdl_dir()
        
        if args.specific_ip:
            # Scan specific IP
            print(f"Checking specific IP: {args.specific_ip} on ports {args.ports}")
            network_devices = scan_network_for_onvif(
                "0.0.0.0/0",  # Dummy subnet, not used
                args.ports, 
                username=args.user, 
                password=args.password, 
                wsdl_dir=wsdl_dir,
                specific_ip=args.specific_ip
            )
        else:
            # Determine subnet to scan
            if args.subnet:
                subnets = [args.subnet]
            else:
                subnets = get_local_subnets()
                print(f"Auto-detected subnets: {', '.join(subnets)}")
            
            # Scan each subnet
            network_devices = []
            for subnet in subnets:
                print(f"Scanning subnet {subnet} with ports {args.ports}")
                devices = scan_network_for_onvif(
                    subnet, 
                    args.ports, 
                    username=args.user, 
                    password=args.password, 
                    wsdl_dir=wsdl_dir
                )
                network_devices.extend(devices)
        
        # Add only devices that weren't found by WS-Discovery
        for device in network_devices:
            # Check if this device is already in our list (by IP)
            is_new = True
            for existing_device in all_devices:
                if existing_device['ip'] == device['ip']:
                    is_new = False
                    break
            
            if is_new:
                all_devices.append(device)
    
    # Display all discovered devices
    print_devices(all_devices, json_output=args.json)
    
    return 0


if __name__ == "__main__":
    sys.exit(main()) 