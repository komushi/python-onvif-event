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
    events_service = mycam.create_events_service()
    print(events_service.GetEventProperties())

    # Define the topic we're interested in
    topic_of_interest = "RuleEngine/CellMotionDetector/Motion"

    # Create the message filter
    # message_filter = mycam.create_type('Filter')
    # topic_expression = mycam.create_type('TopicExpression')
    # topic_expression._value_1 = topic_of_interest
    # topic_expression.Dialect = 'http://www.onvif.org/ver10/tev/topicExpression/ConcreteSet'
    # message_filter.TopicExpression = topic_expression

    notification_service = mycam.create_onvif_service(name='Notification')

    service_url, wsdl_file, binding  = mycam.get_definition('notification')

    logger.info(f"service_url: {service_url}, wsdl_file: {wsdl_file}, binding: {binding}")

    # Create a session to handle authentication
    session = Session()
    session.auth = (user, password)

    # Create a Zeep client using the local WSDL file
    client = Client(wsdl_file, transport=Transport(session=session))

    # Get the FilterType
    filter_type = client.get_type('{http://docs.oasis-open.org/wsn/b-2}FilterType')
    logger.info(f"filter_type: {filter_type}")

    # Get the TopicExpressionType
    topic_expression_type = client.get_type('{http://docs.oasis-open.org/wsn/b-2}TopicExpressionType')
    logger.info(f"topic_expression_type: {topic_expression_type}")

    # Create the topic_expression
    # topic_expression = topic_expression_type('tns1:RuleEngine/CellMotionDetector/Motion', Dialect='http://www.onvif.org/ver10/tev/topicExpression/ConcreteSet')
    topic_expression = topic_expression_type(
        _value_1='tns1:RuleEngine/CellMotionDetector/Motion',
        Dialect='http://www.onvif.org/ver10/tev/topicExpression/ConcreteSet'
    )
    logger.info(f"topic_expression: {topic_expression}")

    # Create the topic_filter
    message_filter = filter_type({
        'TopicExpression': topic_expression,
    })
    logger.info(f"message_filter: {message_filter}")

    pullpoint = mycam.create_pullpoint_service()
    
    while True:
        try:
            pullmess = pullpoint.PullMessages({
                "Timeout": datetime.timedelta(seconds=5), 
                "MessageLimit": 10,
                # 'Filter': message_filter
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