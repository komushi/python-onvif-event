import sys
import signal

import datetime
import logging
from zeep.helpers import serialize_object
from zeep import Client, xsd
from zeep.transports import Transport
from zeep.wsse.username import UsernameToken

import xml.etree.ElementTree as ET

from requests import Session

# Setup logging to stdout
logger = logging.getLogger(__name__)
logging.basicConfig(
    format='%(asctime)s.%(msecs)03d %(levelname)s %(message)s',
    datefmt='%Y-%m-%d,%H:%M:%S',
    level=logging.INFO)


# Function to handle termination signals
def signal_handler(signum, frame):
    logger.info(f"Signal {signum} received, unsubscribing...")

    response = subscription_service.Unsubscribe(_soapheaders=[addressing_header])
    
    logger.info(f"unsub response {response}")

    logger.info(f"before exit")
    exit(0)

if __name__ == '__main__':
    if len(sys.argv) != 5:
        logger.error("Usage: python pullpoint_msg.py <server_ip> <server_port> <user> <password> ")
        sys.exit(1)

    server_ip = sys.argv[1]
    server_port = int(sys.argv[2])
    user = sys.argv[3]
    password = sys.argv[4]

    # Register signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    service_url = '%s:%s/onvif/Events' % \
                    (server_ip if (server_ip.startswith('http://') or server_ip.startswith('https://'))
                     else 'http://%s' % server_ip, server_port)
    
    wsdl_file = './wsdl/events.wsdl'

    pullpoint_subscription_binding = '{http://www.onvif.org/ver10/events/wsdl}PullPointSubscriptionBinding'
    event_binding = '{http://www.onvif.org/ver10/events/wsdl}EventBinding'
    subscription_binding = '{http://www.onvif.org/ver10/events/wsdl}SubscriptionManagerBinding'
    
    logger.info(f"service_url: {service_url}, wsdl_file: {wsdl_file}, event_binding: {event_binding}, pullpoint_subscription_binding: {pullpoint_subscription_binding}")

    # Create a session to handle authentication
    session = Session()
    session.auth = (user, password)

    wsse = UsernameToken(username=user, password=password, use_digest=True)

    # Create a Zeep client using the local WSDL file
    client = Client(wsdl_file, wsse, transport=Transport(session=session))

    event_service = client.create_service(event_binding, service_url)

    subscription = event_service.CreatePullPointSubscription()
    logger.info(f"subscription: {subscription}")

    pullpoint_service = client.create_service(pullpoint_subscription_binding, subscription.SubscriptionReference.Address._value_1)

    subscription_service = client.create_service(subscription_binding, service_url)

    addressing_header_type = xsd.ComplexType(
        xsd.Sequence([
            xsd.Element('{http://www.w3.org/2005/08/addressing}To', xsd.String())
        ])
    )

    addressing_header = addressing_header_type(To=subscription.SubscriptionReference.Address._value_1)

    while True:
        try:
            pullmess = pullpoint_service.PullMessages(Timeout='PT1M', MessageLimit=10)
            for msg in pullmess.NotificationMessage:
                message = serialize_object(msg)
                message_element = message['Message']['_value_1']

                utc_time = None
                is_motion = None
                for simple_item in message_element.findall(".//ns0:SimpleItem", namespaces={'ns0': 'http://www.onvif.org/ver10/schema'}):
                    if simple_item.attrib.get('Name') == "IsMotion":
                        is_motion = simple_item.attrib.get('Value')
                        utc_time = message_element.attrib.get('UtcTime')
                        break

                if utc_time is not None and is_motion is not None:
                    logger.info(f"Motion detected: utc_time: {utc_time} is_motion: {is_motion}")

        except Exception as e:
            logger.info(e)
            exit(0)
            