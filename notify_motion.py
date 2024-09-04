from urllib.parse import urlparse

import sys
import signal
import json
import logging
import threading

import traceback

import http.server
import socketserver

import datetime

# from onvif import ONVIFCamera
from zeep import Client, xsd
from zeep.transports import Transport
from requests import Session
import xml.etree.ElementTree as ET

from zeep.wsse.username import UsernameToken

# Setup logging to stdout
logger = logging.getLogger(__name__)
logging.basicConfig(stream=sys.stdout, level=logging.INFO)

# Initialize the http server
server_thread = None
httpd = None
thread_lock = threading.Lock()
http_port = 7788

subscription_references = []  # List to store SubscriptionReference.Address

# Function to handle termination signals
def signal_handler(signum, frame):
    logger.info(f"Signal {signum} received, shutting down http server.")

    response = subscription_service.Unsubscribe(_soapheaders=[addressing_header])
    
    logger.info(f"unsub response {response}")

    stop_http_server()

    logger.info(f"before exit")
    exit(0)

# http server
def start_server_thread():
    global server_thread
    with thread_lock:
        if server_thread is None or not server_thread.is_alive():
            stop_http_server()
            server_thread = threading.Thread(target=start_http_server, name="Thread-HttpServer" ,daemon=True)
            server_thread.start()
            logger.info("Server thread started")
        else:
            logger.info("Server thread is already running")

def stop_http_server():
    global httpd
    if httpd:
        logger.info("Shutting down HTTP server")
        httpd.shutdown()
        logger.info("HTTP server shut down1")
        httpd.server_close()
        logger.info("HTTP server shut down2")
        httpd = None
        logger.info("HTTP server shut down3")


def start_http_server():

    global httpd

    class ReusableTCPServer(socketserver.TCPServer):
        allow_reuse_address = True

    class NewHandler(http.server.SimpleHTTPRequestHandler):
        
        def do_POST(self):
            try:
                # if self.client_address[0] != '127.0.0.1':
                #     self.send_error(403, "Forbidden: Only localhost allowed")
                #     return
                
                if self.path == '/onvif_notifications':
                    content_length = int(self.headers['Content-Length'])
                    post_data = self.rfile.read(content_length)
                    
                    # Parse the XML content
                    root = ET.fromstring(post_data)
                    
                    # Extract the topic
                    topic_element = root.find(".//{http://docs.oasis-open.org/wsn/b-2}Topic")
                    if topic_element is not None:
                        topic = topic_element.text
                        if topic == "tns1:RuleEngine/CellMotionDetector/Motion":

                            # Extract SubscriptionReference Address and get the host/IP
                            address_element = root.find(".//{http://www.w3.org/2005/08/addressing}Address")
                            address = address_element.text if address_element is not None else None
                            
                            if address and address in subscription_references:
                                # Extract IsMotion as a boolean
                                is_motion_element = root.find(".//{http://www.onvif.org/ver10/schema}SimpleItem[@Name='IsMotion']")
                                is_motion_value = is_motion_element.get('Value').lower() == 'true' if is_motion_element is not None else None
                                
                                # Extract UtcTime
                                utc_time_element = root.find(".//{http://www.onvif.org/ver10/schema}Message")
                                utc_time = utc_time_element.get('UtcTime') if utc_time_element is not None else None
                                
                                # Log the extracted values
                                logger.info(f"Motion detected: IsMotion={is_motion_value}, Address={address}, UtcTime={utc_time}")
                            else:
                                logger.info(f"Received notification from unsubscribed address: {address}")
                    

                    # logger.info(f"Notification received: {post_data.decode('utf-8')}")
                    
                    
                    self.send_response(200)
                    self.end_headers()
            except BrokenPipeError:
                logger.error("Client disconnected before the response could be sent.")
            except Exception as e:
                logger.error(f"Error handling POST request: {e}")
                traceback.print_exc()

                self.send_response(500)
                self.end_headers()
                self.wfile.write(b'Internal Server Error')

        def address_string(self):  # Limit access to local network requests
            host, _ = self.client_address[:2]
            return host

    try:
        # Define the server address and port
        server_address = ('', http_port)

        httpd = ReusableTCPServer(server_address, NewHandler)
        
        httpd.serve_forever()

        logger.info(f"HTTP server started")
    except Exception as e:
        logger.error(f"Error starting HTTP server: {e}")

def print_capabilities(capabilities, indent=0):
    logger.info(capabilities)

if __name__ == "__main__":
    if len(sys.argv) != 6:
        logger.error("Usage: python notify_motion.py <server_ip> <server_port> <user> <password> <local_ip>")
        sys.exit(1)

    server_ip = sys.argv[1]
    server_port = int(sys.argv[2])
    user = sys.argv[3]
    password = sys.argv[4]
    local_ip = sys.argv[5]

    # Register signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    # mycam = ONVIFCamera(server_ip, server_port, user, password, wsdl_dir="./wsdl")
    
    # notification_service1 = mycam.create_onvif_service(name='Notification')

    # service_url, wsdl_file, binding  = mycam.get_definition('notification')
    # logger.info(f"service_url: {service_url}, wsdl_file: {wsdl_file}, binding: {binding}")

    service_url = '%s:%s/onvif/Events' % \
                    (server_ip if (server_ip.startswith('http://') or server_ip.startswith('https://'))
                     else 'http://%s' % server_ip, server_port)
    
    wsdl_file = './wsdl/events.wsdl'

    notification_binding = '{http://www.onvif.org/ver10/events/wsdl}NotificationProducerBinding'
    subscription_binding = '{http://www.onvif.org/ver10/events/wsdl}SubscriptionManagerBinding'
    
    logger.info(f"service_url: {service_url}, wsdl_file: {wsdl_file}, subscription_binding: {subscription_binding}, notification_binding: {notification_binding}")

    # Create a session to handle authentication
    session = Session()
    session.auth = (user, password)

    wsse = UsernameToken(username=user, password=password, use_digest=True)
    logger.info(f"onvif.subscribe wsse {wsse}")

    # Create a Zeep client using the local WSDL file
    client = Client(wsdl_file, wsse=wsse, transport=Transport(session=session))
    logger.info(f"onvif.subscribe client {client}")

    notification_service = client.create_service(notification_binding, service_url)
    logger.info(f"onvif.subscribe notification_service {notification_service}")

    subscription_service = client.create_service(subscription_binding, service_url)
    logger.info(f"onvif.subscribe subscription_service {subscription_service}")

    # Get the EndpointReferenceType
    address_type = client.get_element('{http://www.w3.org/2005/08/addressing}EndpointReference')
    logger.info(f"onvif.subscribe address_type {address_type}")

    # Create the consumer reference
    consumer_reference = address_type(Address=f"http://{local_ip}:7788/onvif_notifications")
    logger.info(f"onvif.subscribe consumer_reference {consumer_reference}")

    subscription = notification_service.Subscribe(ConsumerReference=consumer_reference, InitialTerminationTime='PT1H')
    logger.info(f"onvif.subscribe subscription {subscription}")

    addressing_header_type = xsd.ComplexType(
        xsd.Sequence([
            xsd.Element('{http://www.w3.org/2005/08/addressing}To', xsd.String())
        ])
    )

    addressing_header = addressing_header_type(To=subscription.SubscriptionReference.Address._value_1)
    logger.info(f"onvif.subscribe addressing_header {addressing_header}")

    subscription_references.append(subscription.SubscriptionReference.Address._value_1)

    try:
        
        logger.info(f"Subscription successful: {subscription}")

        start_server_thread()
        
        # Keep the main thread running
        while True:
            pass
    except Exception as e:
        print("Error occurred:", str(e))
        if hasattr(e, 'detail'):
            print("SOAP Fault Detail:", e.detail)
        traceback.print_exc()


