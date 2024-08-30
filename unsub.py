from urllib.parse import urlparse

import sys
import logging
import threading

import traceback

# from onvif import ONVIFCamera
from zeep import Client, xsd
from zeep.transports import Transport
from zeep.wsse.username import UsernameToken
from requests import Session

# Setup logging to stdout
logger = logging.getLogger(__name__)
logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)

# Initialize the http server
server_thread = None
httpd = None
thread_lock = threading.Lock()
http_port = 7788


if __name__ == "__main__":
    if len(sys.argv) != 6:
        logger.error("Usage: python notify_motion.py <server_ip> <server_port> <user> <password> <local_ip>")
        sys.exit(1)

    server_ip = sys.argv[1]
    server_port = int(sys.argv[2])
    user = sys.argv[3]
    password = sys.argv[4]
    local_ip = sys.argv[5]



    # mycam = ONVIFCamera(server_ip, server_port, user, password, wsdl_dir="./wsdl")

    # proxy = mycam.create_onvif_service(name='devicemgmt')
    # logger.info(f"proxy: {proxy}")

    # req = proxy.create_type('GetServices')
    # print(req)

    # service_url, wsdl_file, binding  = mycam.get_definition('subscription')
    # logger.info(f"service_url: {service_url}, wsdl_file: {wsdl_file}, binding: {binding}")
    # service_url: http://192.168.11.93:80/onvif/event, wsdl_file: ./wsdl/events.wsdl, binding: {http://www.onvif.org/ver10/events/wsdl}SubscriptionManagerBinding

    service_url = '%s:%s/onvif/device_service' % \
                    (server_ip if (server_ip.startswith('http://') or server_ip.startswith('https://'))
                     else 'http://%s' % server_ip, server_port)
    
    wsdl_file = './wsdl/events.wsdl'

    binding = '{http://www.onvif.org/ver10/events/wsdl}SubscriptionManagerBinding'
    
    logger.info(f"service_url: {service_url}, wsdl_file: {wsdl_file}, binding: {binding}")

    # Create a session to handle authentication
    session = Session()
    session.auth = (user, password)

    wsse = UsernameToken(username=user, password=password, use_digest=True)

    # Create a Zeep client using the local WSDL file
    client = Client(wsdl_file, wsse=wsse, transport=Transport(session=session))

    subscription_manager_proxy = client.create_service(binding, service_url)

    # subscription_manager_proxy = mycam.create_onvif_service(name='Subscription')

    header_type = xsd.ComplexType(
        xsd.Sequence([
            xsd.Element('{http://www.w3.org/2005/08/addressing}To', xsd.String()),
        ])
    )

    addressing_header = header_type(To='http://192.168.11.93:80/Subscription?Idx=210235C5RD3234000995_1')

    try:
        response = subscription_manager_proxy.Unsubscribe(_soapheaders=[addressing_header])
        logger.info(f"response {response}")
    except Exception as e:
        logger.error(f"Error while unsubscribing {str(e)}")
        traceback.print_exc()
        raise