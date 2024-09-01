```
sudo python3 -m pip install urllib3==1.26.16 --break-system-packages
sudo python3 -m pip install onvif_zeep --break-system-packages
```

```
python3 -m pip install --upgrade onvif_zeep
```

```
python notify_motion.py <server_ip> <server_port> <user> <password> <local_ip>
python3 notify_motion.py 192.168.135.40 2020 user password 192.168.135.123

python unsub.py <server_ip> <server_port> <user> <password> <local_ip>
python unsub.py 192.168.11.81 80 komushi pa55word 192.168.11.82
```

```
gst-launch-1.0 -v rtspsrc location=rtsp://<rtsp-server-url> ! fakesink
```

```
curl -vX POST "http://192.168.11.42/onvif/device_service" -d @sub.xml \
--header "Content-Type: application/soap+xml" \
--header 'SOAPAction: "http://docs.oasis-open.org/wsn/bw-2/NotificationProducer/SubscribeRequest"' \
--header 'charset: utf-8' \
--header 'action: "http://docs.oasis-open.org/wsn/bw-2/NotificationProducer/SubscribeRequest"'
```

```sub.xml
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