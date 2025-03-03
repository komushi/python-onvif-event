#!/usr/bin/env python3
"""
ONVIF Direct Connection Test

This script attempts to directly connect to an ONVIF camera using its IP address
to verify if it's accessible and supports ONVIF.

Usage:
  python onvif_direct_connect.py <ip_address> [--port PORT] [--user USER] [--password PASSWORD]

Options:
  --port PORT       ONVIF port (default: 80)
  --user USER       Username for authentication (default: admin)
  --password PASS   Password for authentication (default: admin)
"""

import sys
import logging
import argparse
import traceback
import os
import inspect
from urllib.parse import urlparse

try:
    from onvif import ONVIFCamera
    import onvif
except ImportError:
    print("Error: python-onvif package is not installed.")
    print("Please install it using: pip install onvif")
    sys.exit(1)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

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
        os.path.join(os.path.dirname(onvif_dir), 'schema', 'wsdl')
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            logger.info(f"Found WSDL directory at: {path}")
            return path
    
    # If we can't find it, try to get it from the ONVIFCamera class
    try:
        # Create a dummy camera to get the wsdl_dir
        dummy_cam = ONVIFCamera('0.0.0.0', 80, 'dummy', 'dummy', no_cache=True)
        if hasattr(dummy_cam, 'wsdl_dir') and dummy_cam.wsdl_dir:
            logger.info(f"Found WSDL directory from ONVIFCamera: {dummy_cam.wsdl_dir}")
            return dummy_cam.wsdl_dir
    except:
        pass
    
    logger.warning("Could not find WSDL directory. Connection may fail.")
    return None

def test_onvif_connection(ip, port=80, user='admin', password='admin', wsdl_dir=None):
    """
    Test direct connection to an ONVIF camera
    """
    logger.info(f"Attempting to connect to ONVIF camera at {ip}:{port}")
    
    # If no WSDL directory is provided, try to find it
    if wsdl_dir is None:
        wsdl_dir = get_wsdl_dir()
        
    if wsdl_dir is None:
        logger.error("WSDL directory not found. Please specify it with --wsdl parameter.")
        return False
        
    try:
        # Try to create an ONVIF camera instance
        logger.info(f"Using WSDL directory: {wsdl_dir}")
        cam = ONVIFCamera(ip, port, user, password, wsdl_dir=wsdl_dir, no_cache=True)
        
        # Get device information
        logger.info("Getting device information...")
        device_service = cam.create_devicemgmt_service()
        device_info = device_service.GetDeviceInformation()
        
        logger.info("\n=== ONVIF Camera Information ===")
        logger.info(f"Manufacturer: {getattr(device_info, 'Manufacturer', 'N/A')}")
        logger.info(f"Model: {getattr(device_info, 'Model', 'N/A')}")
        logger.info(f"Firmware Version: {getattr(device_info, 'FirmwareVersion', 'N/A')}")
        logger.info(f"Serial Number: {getattr(device_info, 'SerialNumber', 'N/A')}")
        logger.info(f"Hardware ID: {getattr(device_info, 'HardwareId', 'N/A')}")
        
        # Get device capabilities
        logger.info("\nGetting device capabilities...")
        capabilities = device_service.GetCapabilities({'Category': 'All'})
        
        # Check if device supports events
        has_events = False
        if hasattr(capabilities, 'Events'):
            has_events = True
        
        # Check if device supports PTZ
        has_ptz = False
        if hasattr(capabilities, 'PTZ'):
            has_ptz = True
        
        logger.info(f"Events Support: {'Yes' if has_events else 'No'}")
        logger.info(f"PTZ Support: {'Yes' if has_ptz else 'No'}")
        
        # Try to get service URLs
        logger.info("\nGetting service URLs...")
        services = device_service.GetServices({'IncludeCapability': True})
        
        logger.info("\n=== ONVIF Services ===")
        for service in services:
            try:
                namespace = getattr(service, 'Namespace', 'N/A')
                xaddr = getattr(service, 'XAddr', 'N/A')
                logger.info(f"Service: {namespace}")
                logger.info(f"URL: {xaddr}")
                logger.info("---")
            except Exception as e:
                logger.error(f"Error processing service: {e}")
        
        logger.info("\nConnection successful! The camera supports ONVIF.")
        return True
        
    except Exception as e:
        logger.error(f"Failed to connect to ONVIF camera: {e}")
        logger.error(traceback.format_exc())
        
        # Provide more specific error information
        if "401" in str(e):
            logger.error("Authentication failed. Please check username and password.")
        elif "Connection refused" in str(e):
            logger.error("Connection refused. Please check if the camera is reachable and the port is correct.")
        elif "timed out" in str(e):
            logger.error("Connection timed out. Please check network connectivity.")
        
        return False

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Test direct connection to an ONVIF camera')
    parser.add_argument('ip', help='IP address of the camera')
    parser.add_argument('--port', type=int, default=80, help='ONVIF port (default: 80)')
    parser.add_argument('--user', default='admin', help='Username for authentication (default: admin)')
    parser.add_argument('--password', default='admin', help='Password for authentication (default: admin)')
    parser.add_argument('--wsdl', help='Path to WSDL directory (optional)')
    
    args = parser.parse_args()
    
    # Test connection
    success = test_onvif_connection(
        args.ip, 
        port=args.port, 
        user=args.user, 
        password=args.password,
        wsdl_dir=args.wsdl
    )
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main()) 