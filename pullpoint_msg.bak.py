import sys
from onvif import ONVIFCamera
import datetime
import logging
from zeep.helpers import serialize_object
from zeep import Client, xsd
from zeep.transports import Transport
from requests import Session
import time

# Setup logging to stdout
logger = logging.getLogger(__name__)
logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)

if __name__ == '__main__':
    if len(sys.argv) != 5:
        logger.error("Usage: python pullpoint_msg.py <server_ip> <server_port> <user> <password> ")
        sys.exit(1)

    server_ip = sys.argv[1]
    server_port = int(sys.argv[2])
    user = sys.argv[3]
    password = sys.argv[4]


    mycam = ONVIFCamera(server_ip, server_port, user, password) #, no_cache=True)

    pullpoint = mycam.create_pullpoint_service()
    
    while True:
        try:
            pullmess = pullpoint.PullMessages({
                "Timeout": datetime.timedelta(seconds=5), 
                "MessageLimit": 10
            })
            print(pullmess.CurrentTime)
            print(pullmess.TerminationTime)
            for msg in pullmess.NotificationMessage:
                message = serialize_object(msg)
                print(f"Motion detected: {message}")
        except Exception as e:
            print(e)
        finally:
            pass