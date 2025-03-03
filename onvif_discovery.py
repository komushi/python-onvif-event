#!/usr/bin/env python3
"""
ONVIF Device Discovery Tool

This script implements ONVIF device discovery similar to node-onvif's startProbe() functionality.
It uses WS-Discovery protocol to find ONVIF-compliant devices on the network.

Usage:
  python onvif_discovery.py [--timeout SECONDS] [--json]

Options:
  --timeout SECONDS  Set discovery timeout (default: 15 seconds)
  --json            Output results in JSON format
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

try:
    from onvif import ONVIFCamera
    from zeep import Client
    from zeep.transports import Transport
    from requests import Session
except ImportError:
    print("Error: Required packages are not installed.")
    print("Please install them using: pip install onvif zeep")
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
            logger.error(traceback.format_exc())
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
                logger.error(traceback.format_exc())
        
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
                'discovery_method': 'Zeep Direct Connection'
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
                    'discovery_method': 'Zeep Direct Connection'
                }
            except:
                # Not an ONVIF device or authentication failed
                return None
                
    except Exception as e:
        logger.debug(f"Error checking ONVIF device at {ip}:{port}: {e}")
        return None


def scan_network_for_onvif(subnet, ports, username='admin', password='admin', wsdl_dir=None, max_workers=20):
    """Scan a network subnet for ONVIF devices using zeep and onvif libraries"""
    logger.info(f"Starting network scan for ONVIF devices on subnet {subnet}")
    
    # Parse subnet
    network = ipaddress.ip_network(subnet)
    
    # Parse ports
    port_list = [int(p.strip()) for p in ports.split(',')]
    
    # List to store found devices
    devices = []
    
    # Count for progress reporting
    total_ips = sum(1 for _ in network.hosts())
    scanned_ips = 0
    found_devices = 0
    
    logger.info(f"Scanning {total_ips} IP addresses on ports {port_list}")
    
    # First, find all IPs with open ports
    open_ports = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Create tasks for checking each IP and port combination
        futures = []
        for ip in network.hosts():
            ip_str = str(ip)
            for port in port_list:
                futures.append(executor.submit(check_port_open, ip_str, port))
                
                # Store the IP and port for reference
                open_ports.append((ip_str, port))
        
        # Process results as they complete
        for i, future in enumerate(concurrent.futures.as_completed(futures)):
            scanned_ips += 1
            
            # Print progress every 50 checks
            if scanned_ips % 50 == 0:
                progress = (scanned_ips / (total_ips * len(port_list))) * 100
                logger.info(f"Scan progress: {progress:.1f}% ({scanned_ips}/{total_ips * len(port_list)})")
    
    # Filter to only the open ports
    active_hosts = []
    for i, future in enumerate(futures):
        if future.result():
            active_hosts.append(open_ports[i])
    
    logger.info(f"Found {len(active_hosts)} open ports. Checking for ONVIF devices...")
    
    # Now check each open port for ONVIF
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Create tasks for checking each IP with open port
        futures = []
        for ip, port in active_hosts:
            futures.append(executor.submit(check_onvif_device_with_zeep, ip, port, username, password, wsdl_dir))
        
        # Process results as they complete
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result:
                devices.append(result)
                found_devices += 1
                logger.info(f"Found ONVIF device at {result['ip']}:{result['port']}")
    
    logger.info(f"Network scan completed. Found {found_devices} ONVIF devices.")
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
    parser.add_argument('--scan-network', action='store_true', help='Perform a network scan in addition to WS-Discovery')
    parser.add_argument('--subnet', default='192.168.1.0/24', help='Subnet to scan (default: 192.168.1.0/24)')
    parser.add_argument('--ports', default='80,8000,8080', help='Comma-separated list of ports to check (default: 80,8000,8080)')
    parser.add_argument('--specific-ip', help='Check a specific IP address (can be used with --ports)')
    parser.add_argument('--user', default='admin', help='Username for authentication (default: admin)')
    parser.add_argument('--password', default='admin', help='Password for authentication (default: admin)')
    parser.add_argument('--wsdl', help='Path to WSDL directory (optional)')
    args = parser.parse_args()
    
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
    
    # If requested, also scan the network
    if args.scan_network:
        if args.specific_ip:
            # Create a /32 subnet for the specific IP
            subnet = f"{args.specific_ip}/32"
            print(f"Checking specific IP: {args.specific_ip} on ports {args.ports}")
        else:
            subnet = args.subnet
            print(f"Starting network scan on subnet {subnet} with ports {args.ports}")
        
        network_devices = scan_network_for_onvif(
            subnet, 
            args.ports, 
            username=args.user, 
            password=args.password, 
            wsdl_dir=args.wsdl
        )
        
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