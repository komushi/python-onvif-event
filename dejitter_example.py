#!/usr/bin/env python3
"""
Simple example to get and set Dejitter (去抖动) on Dahua cameras
"""
import requests
from requests.auth import HTTPDigestAuth
import re
import sys
import argparse

def get_dejitter(ip, username, password):
    """Get current Dejitter value"""
    url = f"http://{ip}/cgi-bin/configManager.cgi"
    params = {
        'action': 'getConfig',
        'name': 'MotionDetect'
    }
    
    # Use HTTP Digest Authentication
    auth = HTTPDigestAuth(username, password)
    
    try:
        response = requests.get(url, params=params, auth=auth, timeout=10)
        
        if response.status_code == 200:
            # Extract Dejitter value using regex
            match = re.search(r'Dejitter=(\d+)', response.text)
            if match:
                dejitter_value = int(match.group(1))
                print(f"Current Dejitter (去抖动): {dejitter_value} seconds")
                return dejitter_value
            else:
                print("Dejitter parameter not found")
                return None
        else:
            print(f"Failed to get config: {response.status_code}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"Error connecting to camera: {e}")
        return None

def set_dejitter(ip, username, password, new_value):
    """Set new Dejitter value"""
    url = f"http://{ip}/cgi-bin/configManager.cgi"
    params = {
        'action': 'setConfig',
        'MotionDetect[0].EventHandler.Dejitter': str(new_value)
    }
    
    # Use HTTP Digest Authentication
    auth = HTTPDigestAuth(username, password)
    
    try:
        response = requests.get(url, params=params, auth=auth, timeout=10)
        
        if response.status_code == 200:
            print(f"Successfully set Dejitter to {new_value} seconds")
            return True
        else:
            print(f"Failed to set Dejitter: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"Error connecting to camera: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(
        description='Get or set Dejitter (去抖动) on Dahua cameras',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Get current dejitter value
  python3 dejitter_example.py 192.168.11.62 admin password --get

  # Set dejitter to 5 seconds
  python3 dejitter_example.py 192.168.11.62 admin password --set 5

  # Both get and set (get current, set new, verify)
  python3 dejitter_example.py 192.168.11.62 admin password --get --set 10
        '''
    )
    
    # Required arguments
    parser.add_argument('ip', help='Camera IP address')
    parser.add_argument('username', help='Camera username')
    parser.add_argument('password', help='Camera password')
    
    # Optional arguments
    parser.add_argument('--get', action='store_true', 
                       help='Get current dejitter value')
    parser.add_argument('--set', type=int, metavar='SECONDS',
                       help='Set dejitter value in seconds')
    parser.add_argument('--port', type=int, default=80,
                       help='Camera HTTP port (default: 80)')
    
    args = parser.parse_args()
    
    # Validate that at least one action is specified
    if not args.get and args.set is None:
        parser.error('At least one of --get or --set must be specified')
    
    print(f"=== Dahua Camera Dejitter Tool ===")
    print(f"Camera: {args.ip}:{args.port}")
    print(f"User: {args.username}\n")
    
    # Perform requested actions
    if args.get:
        print("Getting current Dejitter value:")
        get_dejitter(args.ip, args.username, args.password)
        if args.set is not None:
            print()  # Add blank line between operations
    
    if args.set is not None:
        print(f"Setting Dejitter to {args.set} seconds:")
        if set_dejitter(args.ip, args.username, args.password, args.set):
            # Verify the change
            print("\nVerifying the change:")
            get_dejitter(args.ip, args.username, args.password)

if __name__ == "__main__":
    main()