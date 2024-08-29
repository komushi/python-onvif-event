from urllib.parse import urlparse

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
import xml.etree.ElementTree as ET

# Setup logging to stdout
logger = logging.getLogger(__name__)
logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)

# Initialize the http server
server_thread = None
httpd = None
thread_lock = threading.Lock()
http_port = 7788

subscription_references = []  # List to store SubscriptionReference.Address

# Function to handle termination signals
def signal_handler(signum, frame):
    logger.info(f"Signal {signum} received, shutting down http server.")

    # for address in subscription_references:
    #     try:
    #         unsubscribe(address)
    #         logger.info(f"Unsubscribed from {address}")
    #     except Exception as e:
    #         logger.error(f"Failed to unsubscribe from {address}: {str(e)}")

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
                    

                    logger.info(f"Notification received: {post_data.decode('utf-8')}")
                    
                    
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

def unsubscribe(address):
    # Create unsubscribe request using the stored SubscriptionReference.Address
    try:

        subscription_reference_type = client.get_element('{http://www.w3.org/2005/08/addressing}EndpointReference')
        subscription_reference = subscription_reference_type(
            Address='http://192.168.11.210:2020/event-0_2020',
            ReferenceParameters=None,
            Metadata=None
        )
        unsubscription_options = {
            'SubscriptionReference': subscription_reference,
        }

        print(f"unsubscription_options: {unsubscription_options}")

        subscription_service = mycam.create_onvif_service(name='Subscription')

        subscription_service.Unsubscribe(unsubscription_options)
        print(f"Unsubscribed from")
    except Exception as e:
        logger.error(f"Error while unsubscribing from {address}: {str(e)}")
        traceback.print_exc()
        raise

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

    mycam = ONVIFCamera(server_ip, server_port, user, password, wsdl_dir="./wsdl")
    
    notification_service = mycam.create_onvif_service(name='Notification')

    service_url, wsdl_file, binding  = mycam.get_definition('notification')
    logger.info(f"service_url: {service_url}, wsdl_file: {wsdl_file}, binding: {binding}")

    # Create a session to handle authentication
    session = Session()
    session.auth = (user, password)

    # Create a Zeep client using the local WSDL file
    client = Client(wsdl_file, transport=Transport(session=session))

    # Get the EndpointReferenceType
    address_type = client.get_element('{http://www.w3.org/2005/08/addressing}EndpointReference')
    print(f"address_type {address_type}")

    # Create the consumer reference
    consumer_reference = address_type(Address=f"http://{local_ip}:7788/onvif_notifications")
    print(f"consumer_reference {consumer_reference}")

    subscription_options = {
        'ConsumerReference': consumer_reference,
        'InitialTerminationTime': 'PT100S'
    }

    subscription = notification_service.Subscribe(subscription_options)

    try:
        
        logger.info(f"Subscription successful: {subscription}")

        subscription_references.append(subscription['SubscriptionReference']['Address']['_value_1'])

        start_server_thread()
        
        # Keep the main thread running
        while True:
            pass
    except Exception as e:
        print("Error occurred:", str(e))
        if hasattr(e, 'detail'):
            print("SOAP Fault Detail:", e.detail)
        traceback.print_exc()


