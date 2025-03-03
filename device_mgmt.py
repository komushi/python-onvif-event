import sys
import signal
import json
import logging
import threading

import traceback

import http.server
import socketserver

from onvif import ONVIFCamera
from zeep import Client, xsd
from zeep.transports import Transport
from requests import Session

# Setup logging to stdout
logger = logging.getLogger(__name__)
logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)


def print_capabilities(capabilities, indent=0):
    logger.info(capabilities)

    # for key, value in capabilities.items():
    #     if isinstance(value, dict):
    #         logger.info(f'{" " * indent}{key}:')
    #         print_capabilities(value, indent + 2)
    #     else:
    #         logger.info(f'{" " * indent}{key}: {value}')


def get_onvif_version(device_service):
    """
    Get and display the ONVIF version information from the device
    """
    try:
        # Get device information which includes ONVIF version
        device_info = device_service.GetDeviceInformation()
        logger.info("Device Information:")
        logger.info(f"Manufacturer: {getattr(device_info, 'Manufacturer', 'N/A')}")
        logger.info(f"Model: {getattr(device_info, 'Model', 'N/A')}")
        logger.info(f"FirmwareVersion: {getattr(device_info, 'FirmwareVersion', 'N/A')}")
        logger.info(f"SerialNumber: {getattr(device_info, 'SerialNumber', 'N/A')}")
        logger.info(f"HardwareId: {getattr(device_info, 'HardwareId', 'N/A')}")
        
        # Get supported services and their versions
        services = device_service.GetServices({'IncludeCapability': True})
        logger.info("\nONVIF Services and Versions:")
        for service in services:
            try:
                namespace = getattr(service, 'Namespace', 'N/A')
                version = getattr(service, 'Version', None)
                if version:
                    version_str = f"{getattr(version, 'Major', 'N/A')}.{getattr(version, 'Minor', 'N/A')}"
                else:
                    version_str = "N/A"
                logger.info(f"Service: {namespace}, Version: {version_str}")
            except Exception as e:
                logger.error(f"Error processing service: {e}")
            
        return device_info, services
    except Exception as e:
        logger.error(f"Error getting ONVIF version: {e}")
        logger.error(traceback.format_exc())
        return None, None


def get_device_capabilities(device_service):
    """
    Get and display device capabilities including ONVIF version
    """
    try:
        # Get device capabilities
        capabilities = device_service.GetCapabilities({'Category': 'All'})
        
        # Extract ONVIF version from capabilities
        logger.info("\nDevice Capabilities:")
        
        # Check if Device capabilities exist
        device_caps = getattr(capabilities, 'Device', None)
        if device_caps:
            # Get ONVIF version
            system = getattr(device_caps, 'System', None)
            if system:
                # Try different ways to get supported versions
                supported_versions = getattr(system, 'SupportedVersions', None)
                if supported_versions:
                    logger.info("Supported ONVIF Versions:")
                    # Handle both list and single value cases
                    if isinstance(supported_versions, list):
                        for version in supported_versions:
                            logger.info(f"  - {version}")
                    else:
                        logger.info(f"  - {supported_versions}")
                else:
                    # Try alternative attribute names
                    version = getattr(system, 'Version', None) or getattr(system, 'OnvifVersion', None)
                    if version:
                        logger.info(f"ONVIF Version: {version}")
                    else:
                        logger.info("No specific ONVIF versions found in capabilities")
            
            # Log other important capabilities
            logger.info("\nOther Device Capabilities:")
            for attr_name in dir(device_caps):
                if not attr_name.startswith('_') and attr_name not in ['System']:
                    try:
                        value = getattr(device_caps, attr_name)
                        if value is not None:
                            logger.info(f"  {attr_name}: {value}")
                    except Exception:
                        pass
        else:
            # Try to extract information directly from capabilities
            logger.info("Device capabilities not found in standard format")
            logger.info("Trying to extract information directly from capabilities object:")
            
            # Print all non-private attributes of capabilities
            for attr_name in dir(capabilities):
                if not attr_name.startswith('_'):
                    try:
                        value = getattr(capabilities, attr_name)
                        if value is not None and attr_name not in ['Events', 'Media', 'PTZ', 'Imaging', 'Extension']:
                            logger.info(f"  {attr_name}: {value}")
                    except Exception:
                        pass
        
        return capabilities
    except Exception as e:
        logger.error(f"Error getting device capabilities: {e}")
        logger.error(traceback.format_exc())
        return None


def get_onvif_protocol_version(device_service):
    """
    Get the ONVIF protocol version directly from the device service
    """
    try:
        # Get ONVIF protocol version
        protocol_version = device_service.GetServiceCapabilities()
        
        logger.info("ONVIF Protocol Information:")
        
        # Try to extract version information
        for attr_name in dir(protocol_version):
            if not attr_name.startswith('_') and 'Version' in attr_name:
                try:
                    value = getattr(protocol_version, attr_name)
                    if value is not None:
                        logger.info(f"  {attr_name}: {value}")
                except Exception:
                    pass
        
        # Log all other service capabilities
        logger.info("\nOther Service Capabilities:")
        for attr_name in dir(protocol_version):
            if not attr_name.startswith('_') and 'Version' not in attr_name:
                try:
                    value = getattr(protocol_version, attr_name)
                    if value is not None:
                        logger.info(f"  {attr_name}: {value}")
                except Exception:
                    pass
                    
        return protocol_version
    except Exception as e:
        logger.error(f"Error getting ONVIF protocol version: {e}")
        logger.error(traceback.format_exc())
        return None


def summarize_onvif_version(device_info, services, capabilities, protocol_version):
    """
    Summarize all ONVIF version information collected from different sources
    """
    logger.info("\n=== ONVIF Version Summary ===")
    
    # Check if we have firmware version from device info
    if device_info:
        firmware = getattr(device_info, 'FirmwareVersion', 'N/A')
        logger.info(f"Device Firmware Version: {firmware}")
    
    # Extract version information from services
    if services:
        logger.info("\nSupported ONVIF Service Namespaces:")
        for service in services:
            try:
                namespace = getattr(service, 'Namespace', 'N/A')
                if 'onvif' in namespace.lower():
                    logger.info(f"  - {namespace}")
            except Exception:
                pass
    
    # Final determination of ONVIF version
    logger.info("\nONVIF Version Determination:")
    
    # Check for explicit version in capabilities
    onvif_version = "Could not determine ONVIF version"
    
    # Try to determine from capabilities
    if capabilities:
        device_caps = getattr(capabilities, 'Device', None)
        if device_caps:
            system = getattr(device_caps, 'System', None)
            if system:
                supported_versions = getattr(system, 'SupportedVersions', None)
                if supported_versions:
                    if isinstance(supported_versions, list) and supported_versions:
                        onvif_version = f"ONVIF {supported_versions[0]}"
                    else:
                        onvif_version = f"ONVIF {supported_versions}"
    
    # If we couldn't determine from capabilities, try from services
    if onvif_version == "Could not determine ONVIF version" and services:
        # Look for the highest version in service namespaces
        highest_version = 0
        for service in services:
            try:
                namespace = getattr(service, 'Namespace', '')
                if 'onvif' in namespace.lower() and 'ver' in namespace.lower():
                    # Try to extract version number (e.g., from "http://www.onvif.org/ver20/...")
                    version_str = namespace.split('ver')[1].split('/')[0]
                    if version_str.isdigit():
                        version = int(version_str)
                        highest_version = max(highest_version, version)
            except Exception:
                pass
        
        if highest_version > 0:
            major = highest_version // 10
            minor = highest_version % 10
            onvif_version = f"ONVIF {major}.{minor} (derived from service namespaces)"
    
    logger.info(f"Determined ONVIF Version: {onvif_version}")
    logger.info("===================================\n")


if __name__ == "__main__":

    if len(sys.argv) != 5:
        logger.error("Usage: python device_mgmt.py <server_ip> <server_port> <user> <password>")
        sys.exit(1)

    server_ip = sys.argv[1]
    server_port = int(sys.argv[2])
    user = sys.argv[3]
    password = sys.argv[4]

    mycam = ONVIFCamera(server_ip, server_port, user, password, wsdl_dir="./wsdl")

    device_service = mycam.create_devicemgmt_service()

    service_url, wsdl_file, binding  = mycam.get_definition('devicemgmt')

    logger.info(f"service_url: {service_url}, wsdl_file: {wsdl_file}, binding: {binding}")

    # Get and display ONVIF version information
    logger.info("\n=== ONVIF Version Information ===")
    device_info, services = get_onvif_version(device_service)
    logger.info("===================================\n")

    # Get and display device capabilities including ONVIF version
    logger.info("\n=== ONVIF Device Capabilities ===")
    capabilities = get_device_capabilities(device_service)
    logger.info("===================================\n")

    # Get and display ONVIF protocol version
    logger.info("\n=== ONVIF Protocol Version ===")
    protocol_version = get_onvif_protocol_version(device_service)
    logger.info("===================================\n")
    
    # Summarize all ONVIF version information
    summarize_onvif_version(device_info, services, capabilities, protocol_version)

    events_service = mycam.create_events_service()
    
    capabilities = events_service.GetServiceCapabilities()
    
    print_capabilities(capabilities)

    # event_properties = events_service.GetEventProperties()

    # logger.info(event_properties)

    # res = events_service.CreatePullPointSubscription()
    # logger.info(res)

    # # Create a session to handle authentication
    # session = Session()
    # session.auth = (user, password)

    # # Create a Zeep client using the local WSDL file
    # client = Client(wsdl_file, transport=Transport(session=session))

    # # Get the FilterType element
    # reboot = client.get_element('{http://www.onvif.org/ver10/device/wsdl}SystemReboot')
    # logger.info(f"reboot: {reboot}")

    # try:
    #     reboot_response = device_service.SystemReboot()
    #     print(f"Reboot Response: {reboot_response}")
    # except Exception as e:
    #     print(f"An error occurred during SystemReboot: {e}")
