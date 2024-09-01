import sys

from zeep import Client
from zeep.wsse.username import UsernameToken
from zeep.transports import Transport
from lxml import etree

# Load the XML Schema definition
schema_doc = etree.parse('./wsdl/envelope')
schema = etree.XMLSchema(schema_doc)

if __name__ == "__main__":

    if len(sys.argv) != 3:
        print("Usage: python get_token.py <user> <password>")
        sys.exit(1)

    user = sys.argv[1]
    password = sys.argv[2]

    wsse = UsernameToken(username=user, password=password, use_digest=True)

    # Create the SOAP envelope
    envelope = etree.Element('{http://schemas.xmlsoap.org/soap/envelope/}Envelope')

    # Create the SOAP header and body elements
    header = etree.SubElement(envelope, '{http://schemas.xmlsoap.org/soap/envelope/}Header')
    body = etree.SubElement(envelope, '{http://schemas.xmlsoap.org/soap/envelope/}Body')

    # Apply the UsernameToken to the header
    wsse.apply(envelope, header)

    # Add the Subscribe element to the body
    subscribe = etree.SubElement(body, '{http://docs.oasis-open.org/wsn/b-2}Subscribe')
    consumer_reference = etree.SubElement(subscribe, '{http://docs.oasis-open.org/wsn/b-2}ConsumerReference')
    address = etree.SubElement(consumer_reference, '{http://www.w3.org/2005/08/addressing}Address')
    address.text = 'http://192.168.11.132:7788/onvif_notifications'
    initial_termination_time = etree.SubElement(subscribe, '{http://docs.oasis-open.org/wsn/b-2}InitialTerminationTime')
    initial_termination_time.text = 'PT300S'

    # Validate the envelope against the schema
    schema.assertValid(envelope)

    # Create a zeep transport with the UsernameToken
    transport = Transport()
    transport.session.verify = False  # Disable SSL verification if needed
    transport.session.auth = wsse

    # Create a zeep client with the transport
    client = Client(wsdl='./wsdl/events.wsdl', transport=transport)

    # Set the envelope as the message for the client
    client.set_default_soapheaders([envelope])

    # Convert the envelope to a string
    envelope_str = etree.tostring(envelope, pretty_print=True).decode('utf-8')

    # Print the XML representation of the envelope
    print(envelope_str)