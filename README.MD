# Python ONVIF Event Tools

A collection of Python scripts for working with ONVIF-compliant IP cameras, including device discovery, event notifications, and device management.

## Installation

### Using pip with requirements.txt
```bash
pip install -r requirements.txt
```

### Manual installation
```bash
sudo python3 -m pip install urllib3==1.26.16 --break-system-packages
sudo python3 -m pip install onvif_zeep --break-system-packages
```

### Upgrade existing installation
```bash
python3 -m pip install --upgrade onvif_zeep
```

## Script Descriptions

### Device Discovery

#### `onvif_discovery.py`
Discovers ONVIF-compliant devices on your network using WS-Discovery protocol.
- Supports both multicast discovery and network scanning
- Can scan specific subnets and verify ONVIF compliance
- Outputs device addresses and capabilities

Usage:
```bash
python onvif_discovery.py --timeout 10
```

#### `onvif_discovery_enhanced.py`
Enhanced version of the discovery tool with additional features for more thorough device detection.

### Event Notifications

#### `notify_motion.py`
Subscribes to motion detection events from ONVIF cameras and sets up an HTTP server to receive real-time notifications.
- Creates event subscriptions for motion detection
- Runs a local HTTP server to receive push notifications
- Automatically handles subscription cleanup on exit

Usage:
```bash
python notify_motion.py <server_ip> <server_port> <user> <password> <local_ip> <local_port>
python3 notify_motion.py 192.168.135.40 2020 user password 192.168.135.123 7788
```

#### `pullpoint_msg.py`
Alternative method for receiving ONVIF events using pull-point subscription mechanism.
- Uses pull-based event retrieval instead of push notifications
- Suitable for environments where incoming HTTP connections are not possible

### Device Management

#### `device_mgmt.py`
Queries and displays device information and capabilities.
- Gets device model, manufacturer, and firmware version
- Lists supported ONVIF services
- Displays device capabilities and profiles

#### `onvif_direct_connect.py`
Establishes direct connections to ONVIF devices for testing and debugging.
- Tests ONVIF connectivity
- Verifies authentication
- Useful for troubleshooting connection issues

#### `dejitter_example.py`
Command-line tool for managing motion detection dejitter (anti-dithering/去抖动) settings on Dahua cameras.
- Get current dejitter value via Dahua's proprietary API
- Set new dejitter value to control motion alarm stability
- Helps prevent rapid on/off cycling of motion alarms
- Useful for automating dejitter restoration after camera reboots

Usage:
```bash
# Get current dejitter value
python3 dejitter_example.py 192.168.11.62 admin password --get

# Set dejitter to 5 seconds
python3 dejitter_example.py 192.168.11.62 admin password --set 5

# Both get and set (shows before/after values)
python3 dejitter_example.py 192.168.11.62 admin password --get --set 10
```

Note: This tool uses Dahua's proprietary HTTP API (`/cgi-bin/configManager.cgi`) as the standard ONVIF interface doesn't support modifying these settings on Dahua cameras.

### Subscription Management

#### `unsub.py`
Unsubscribes from existing event subscriptions.
- Cleanly terminates event subscriptions
- Prevents resource leaks on camera devices

Usage:
```bash
python unsub.py <server_ip> <server_port> <user> <password> <local_ip>
python unsub.py 192.168.11.81 80 komushi pa55word 192.168.11.82
```

#### `renew.py`
Renews existing event subscriptions before they expire.
- Extends subscription duration
- Maintains continuous event monitoring

#### `sub_post.py`
Creates event subscriptions using direct HTTP POST requests.
- Low-level subscription creation
- Useful for debugging and custom subscription setups

### Authentication and Security

#### `get_token.py`
Generates WS-Security tokens for ONVIF authentication.
- Creates properly formatted security tokens
- Handles password digest generation
- Includes nonce and timestamp creation

#### `get_token.raw.py`
Raw implementation of token generation for understanding the authentication process.

## Additional Resources

### Testing with GStreamer
Test RTSP streams from ONVIF cameras:
```bash
gst-launch-1.0 -v rtspsrc location=rtsp://<rtsp-server-url> ! fakesink
```

### Manual SOAP Request Example
Send raw SOAP requests to ONVIF devices:
```bash
curl -vX POST "http://192.168.11.42/onvif/device_service" -d @sub.xml \
--header "Content-Type: application/soap+xml" \
--header 'SOAPAction: "http://docs.oasis-open.org/wsn/bw-2/NotificationProducer/SubscribeRequest"' \
--header 'charset: utf-8' \
--header 'action: "http://docs.oasis-open.org/wsn/bw-2/NotificationProducer/SubscribeRequest"'
```

### Example SOAP Subscription Request (sub.xml)
```xml
<?xml version='1.0' encoding='utf-8'?>
<soap-env:Envelope xmlns:soap-env="http://www.w3.org/2003/05/soap-envelope">
	<soap-env:Header>
		<wsse:Security xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd">
			<wsse:UsernameToken>
				<wsse:Username>komushi</wsse:Username>
				<wsse:Password Type="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-username-token-profile-1.0#PasswordDigest">iZ9N2RgDktKL1VBcLDtmdHAf/rg=</wsse:Password>
				<wsse:Nonce EncodingType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-soap-message-security-1.0#Base64Binary">LWMhMZfcgY5uj5BuKsxYIQ==</wsse:Nonce>
				<wsu:Created xmlns:wsu="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd">2024-08-30T23:59:29+00:00</wsu:Created>
			</wsse:UsernameToken>
		</wsse:Security>
	</soap-env:Header>
	<soap-env:Body>
		<ns0:Subscribe xmlns:ns0="http://docs.oasis-open.org/wsn/b-2">
			<ns0:ConsumerReference>
				<ns1:Address xmlns:ns1="http://www.w3.org/2005/08/addressing">http://192.168.11.132:7788/onvif_notifications</ns1:Address>
			</ns0:ConsumerReference>
			<ns0:InitialTerminationTime>PT300S</ns0:InitialTerminationTime>
		</ns0:Subscribe>
	</soap-env:Body>
</soap-env:Envelope>
```

## WSDL Files

The `wsdl/` directory contains local copies of ONVIF WSDL files for offline operation, including:
- Device management
- Media services
- PTZ control
- Event handling
- Analytics
- And more...