#!/usr/bin/env python3
"""
Manual test of professor's acceptance test scenario
"""
import requests
import time
import json

def get_messages(url, name):
    try:
        r = requests.get(url + '/messages')
        if r.status_code == 200:
            msgs = r.json()['messages']
            print(f'{name}: {[m["message"] for m in msgs]}')
            return msgs
        else:
            print(f'{name}: Error {r.status_code}')
            return []
    except Exception as e:
        print(f'{name}: Error - {e}')
        return []

def send_message(msg, w):
    try:
        start = time.time()
        r = requests.post('http://localhost:5000/messages', json={'message': msg, 'w': w})
        duration = time.time() - start
        print(f'Sent {msg} (w={w}) in {duration:.2f}s: {r.status_code}')
        return r.status_code == 201
    except Exception as e:
        print(f'Error sending {msg}: {e}')
        return False

print('=== Professor Acceptance Test - Manual ===')
print('Waiting for servers...')
time.sleep(3)

print('\n1. Send Msg1 (w=1) - should be immediate')
send_message('Msg1', 1)

print('\n2. Send Msg2 (w=2) - should wait ~2s for secondary-1')  
send_message('Msg2', 2)

print('\n3. Check state after fast messages (Msg1, Msg2):')
get_messages('http://localhost:5000', 'Master')
get_messages('http://localhost:5001', 'Secondary-1')  
get_messages('http://localhost:5002', 'Secondary-2')

print('\n4. Send Msg3 (w=3) - will wait ~10s for secondary-2')
send_message('Msg3', 3)

print('\n5. Send Msg4 (w=1) - should be immediate')
send_message('Msg4', 1)

print('\n6. Final state:')
get_messages('http://localhost:5000', 'Master')
get_messages('http://localhost:5001', 'Secondary-1')
get_messages('http://localhost:5002', 'Secondary-2')