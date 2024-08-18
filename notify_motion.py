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

# Initialize the http server
server_thread = None
httpd = None
thread_lock = threading.Lock()
http_port = 7777


# Function to handle termination signals
def signal_handler(signum, frame):
    logger.info(f"Signal {signum} received, shutting down http server.")

    stop_http_server()

    logger.info(f"before exit")
    exit(0)
    logger.info(f"after exit")

    # global server_thread    
    # if server_thread is not None:
    #     stop_http_server()
    #     server_thread.join()  # Wait for the server thread to finish
    #     server_thread = None
    # logger.info(f'Available threads after http server shutdown: {", ".join(thread.name for thread in threading.enumerate())}')

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
                    # Process the POST data
                    content_length = int(self.headers['Content-Length'])
                    post_data = self.rfile.read(content_length)
                    # event = json.loads(post_data)
                    event = post_data.decode('utf-8')


                    logger.info(f"/onvif_notifications: {event}")


                    self.send_response(200)
                    self.send_header('Content-type', 'text/html')
                    self.end_headers()
                    self.wfile.write("Notification Received".encode('utf-8'))
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

    # for key, value in capabilities.items():
    #     if isinstance(value, dict):
    #         logger.info(f'{" " * indent}{key}:')
    #         print_capabilities(value, indent + 2)
    #     else:
    #         logger.info(f'{" " * indent}{key}: {value}')


if __name__ == "__main__":
    if len(sys.argv) != 5:
        logger.error("Usage: python notify_motion.py <server_ip> <server_port> <user> <password>")
        sys.exit(1)

    server_ip = sys.argv[1]
    server_port = int(sys.argv[2])
    user = sys.argv[3]
    password = sys.argv[4]

    # Register signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    start_server_thread()

    mycam = ONVIFCamera(server_ip, server_port, user, password)
    
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
    logger.info(f"address_type: {address_type}")

    # Create the consumer reference
    consumer_reference = address_type(Address='http://192.168.11.125:7777/onvif_notifications')
    logger.info(f"consumer_reference: {consumer_reference}")

    # # Get the FilterType
    # filter_type = client.get_type('{http://docs.oasis-open.org/wsn/b-2}FilterType')
    # logger.info(f"filter_type: {filter_type}")

    # # Get the TopicExpressionType
    # topic_expression_type = client.get_type('{http://docs.oasis-open.org/wsn/b-2}TopicExpressionType')
    # logger.info(f"topic_expression_type: {topic_expression_type}")

    # # Create the topic_expression
    # topic_expression = topic_expression_type('tns1:RuleEngine/CellMotionDetector/Motion', Dialect='http://www.onvif.org/ver10/tev/topicExpression/ConcreteSet')
    # logger.info(f"topic_expression: {topic_expression}")

    # # Create the topic_filter
    # topic_filter = filter_type({
    #         'TopicExpression': topic_expression,
    # })
    # logger.info(f"topic_filter: {topic_filter}")
    

    subscription_options = {
        'ConsumerReference': consumer_reference,
        # 'Filter': topic_filter,
        'InitialTerminationTime': 'PT1H'
    }

    # subscription_options = {
    #     'ConsumerReference': {
    #         'Address': {
    #             '_value_1': 'http://192.168.11.126:7777/onvif_notifications',
    #             '_attr_1': None
    #         },
    #     },
    #     'Filter': topic_filter,
    #     'InitialTerminationTime': 'PT1H'
    # }

    try:
        subscription = notification_service.Subscribe(subscription_options)
        print("Subscription successful:", subscription)
        
        # Keep the main thread running
        while True:
            pass
    except Exception as e:
        print("Error occurred:", str(e))
        if hasattr(e, 'detail'):
            print("SOAP Fault Detail:", e.detail)
        traceback.print_exc()


