import sys
import signal

import datetime
import logging
from zeep.helpers import serialize_object
from zeep import Client, xsd
from zeep.transports import Transport
from requests import Session

from zeep.wsse.username import UsernameToken

# Setup logging to stdout
logger = logging.getLogger(__name__)
logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)

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
            pullmess = pullpoint_service.PullMessages(Timeout=datetime.timedelta(seconds=5),MessageLimit=10)
            print(pullmess.CurrentTime)
            print(pullmess.TerminationTime)
            for msg in pullmess.NotificationMessage:
                message = serialize_object(msg)
                print(f"Motion detected: {message}")
        except Exception as e:
            print(e)
        finally:
            pass