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

gst-launch-1.0 -v rtspsrc location=rtsp://<rtsp-server-url> ! fakesink