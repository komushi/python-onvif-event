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


if __name__ == "__main__":

    if len(sys.argv) != 5:
        logger.error("Usage: python reboot_cam.py <server_ip> <server_port> <user> <password>")
        sys.exit(1)

    server_ip = sys.argv[1]
    server_port = int(sys.argv[2])
    user = sys.argv[3]
    password = sys.argv[4]

    mycam = ONVIFCamera(server_ip, server_port, user, password)

    device_service = mycam.create_devicemgmt_service()

    service_url, wsdl_file, binding  = mycam.get_definition('devicemgmt')

    logger.info(f"service_url: {service_url}, wsdl_file: {wsdl_file}, binding: {binding}")

    capabilities = device_service.GetCapabilities({'Category': 'All'})

    print_capabilities(capabilities)

    capabilities = device_service.GetServiceCapabilities()

    print_capabilities(capabilities)

    events_service = mycam.create_events_service()
    
    capabilities = events_service.GetServiceCapabilities()
    
    print_capabilities(capabilities)

    event_properties = events_service.GetEventProperties()

    logger.info(event_properties)

    res = events_service.CreatePullPointSubscription()
    logger.info(res)

    # Create a session to handle authentication
    session = Session()
    session.auth = (user, password)

    # Create a Zeep client using the local WSDL file
    client = Client(wsdl_file, transport=Transport(session=session))

    # Get the FilterType element
    reboot = client.get_element('{http://www.onvif.org/ver10/device/wsdl}SystemReboot')
    logger.info(f"reboot: {reboot}")

    try:
        reboot_response = device_service.SystemReboot()
        print(f"Reboot Response: {reboot_response}")
    except Exception as e:
        print(f"An error occurred during SystemReboot: {e}")
