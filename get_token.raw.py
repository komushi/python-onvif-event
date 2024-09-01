import sys

from zeep.wsse.username import UsernameToken
from zeep.wsse import utils
from lxml import etree

if __name__ == "__main__":

    if len(sys.argv) != 3:
        print("Usage: python get_token.py <user> <password>")
        sys.exit(1)

    user = sys.argv[1]
    password = sys.argv[2]

    wsse = UsernameToken(username=user, password=password, use_digest=True)

    # Create the SOAP envelope
    envelope = etree.Element('{http://www.w3.org/2003/05/soap-envelope}Envelope', nsmap={
        'soap-env': 'http://www.w3.org/2003/05/soap-envelope',
        'wsse': 'http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd',
        'wsu': 'http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd'
    })

    # Create the SOAP header and body elements
    header = etree.SubElement(envelope, '{http://www.w3.org/2003/05/soap-envelope}Header')
    body = etree.SubElement(envelope, '{http://www.w3.org/2003/05/soap-envelope}Body')

    # Apply the UsernameToken to the header
    wsse.apply(envelope, header)

    # Add the Subscribe element to the body
    subscribe = etree.SubElement(body, '{http://docs.oasis-open.org/wsn/b-2}Subscribe')
    consumer_reference = etree.SubElement(subscribe, '{http://docs.oasis-open.org/wsn/b-2}ConsumerReference')
    address = etree.SubElement(consumer_reference, '{http://www.w3.org/2005/08/addressing}Address')
    address.text = 'http://192.168.11.132:7788/onvif_notifications'
    initial_termination_time = etree.SubElement(subscribe, '{http://docs.oasis-open.org/wsn/b-2}InitialTerminationTime')
    initial_termination_time.text = 'PT300S'

    # Convert the envelope to a string
    envelope_str = etree.tostring(envelope, pretty_print=True).decode('utf-8')

    # Print the XML representation of the envelope
    print(envelope_str)

