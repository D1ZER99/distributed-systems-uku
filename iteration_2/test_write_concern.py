#!/usr/bin/env python3
"""
Test script to demonstrate write concern functionality
"""

import requests
import json
import time

def test_write_concern():
    """Test different write concern values"""
    
    master_url = "http://localhost:5000"
    
    print("Testing Write Concern Implementation")
    print("=" * 50)
    
    # Test case 1: w=1 (master only)
    print("\n1. Testing w=1 (master only)")
    try:
        response = requests.post(
            f"{master_url}/messages",
            json={"message": "Test message with w=1", "w": 1},
            timeout=5
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
    
    # Test case 2: w=2 (master + 1 secondary)
    print("\n2. Testing w=2 (master + 1 secondary)")
    try:
        response = requests.post(
            f"{master_url}/messages",
            json={"message": "Test message with w=2", "w": 2},
            timeout=5
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
    
    # Test case 3: w=3 (master + 2 secondaries)
    print("\n3. Testing w=3 (master + 2 secondaries)")
    try:
        response = requests.post(
            f"{master_url}/messages",
            json={"message": "Test message with w=3", "w": 3},
            timeout=5
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
    
    # Test case 4: Default write concern
    print("\n4. Testing default write concern (all replicas)")
    try:
        response = requests.post(
            f"{master_url}/messages",
            json={"message": "Test message with default w"},
            timeout=5
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
    
    # Test case 5: Invalid write concern
    print("\n5. Testing invalid write concern (w=10)")
    try:
        response = requests.post(
            f"{master_url}/messages",
            json={"message": "Test message with w=10", "w": 10},
            timeout=5
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
    
    # Test case 6: Duplicate messages (should be accepted now)
    print("\n6. Testing duplicate messages")
    duplicate_message = "Duplicate message test"
    
    for i in range(3):
        print(f"\n   Attempt {i+1}:")
        try:
            response = requests.post(
                f"{master_url}/messages",
                json={"message": duplicate_message, "w": 1},
                timeout=5
            )
            print(f"   Status: {response.status_code}")
            print(f"   Response: {response.json()}")
        except requests.exceptions.RequestException as e:
            print(f"   Error: {e}")
    
    # Get all messages
    print("\n7. Retrieving all messages")
    try:
        response = requests.get(f"{master_url}/messages", timeout=5)
        print(f"Status: {response.status_code}")
        messages = response.json().get('messages', [])
        print(f"Total messages: {len(messages)}")
        for msg in messages:
            print(f"  ID: {msg['id']}, Message: {msg['message']}")
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")

def test_curl_commands():
    """Print curl commands for manual testing"""
    print("\n" + "=" * 50)
    print("CURL COMMANDS FOR MANUAL TESTING")
    print("=" * 50)
    
    print("\n1. Send message with w=1:")
    print('curl -X POST http://localhost:5000/messages \\')
    print('  -H "Content-Type: application/json" \\')
    print('  -d \'{"message": "Test with w=1", "w": 1}\'')
    
    print("\n2. Send message with w=2:")
    print('curl -X POST http://localhost:5000/messages \\')
    print('  -H "Content-Type: application/json" \\')
    print('  -d \'{"message": "Test with w=2", "w": 2}\'')
    
    print("\n3. Send message with w=3:")
    print('curl -X POST http://localhost:5000/messages \\')
    print('  -H "Content-Type: application/json" \\')
    print('  -d \'{"message": "Test with w=3", "w": 3}\'')
    
    print("\n4. Send message with default write concern:")
    print('curl -X POST http://localhost:5000/messages \\')
    print('  -H "Content-Type: application/json" \\')
    print('  -d \'{"message": "Test with default w"}\'')
    
    print("\n5. Get all messages:")
    print('curl -X GET http://localhost:5000/messages')
    
    print("\n6. Check health:")
    print('curl -X GET http://localhost:5000/health')

if __name__ == "__main__":
    print("Write Concern Test Script")
    print("Make sure the master server is running on localhost:5000")
    print("and secondary servers are configured via SECONDARIES environment variable")
    
    choice = input("\nChoose option:\n1. Run automated tests\n2. Show curl commands\n3. Both\nChoice (1/2/3): ")
    
    if choice in ["1", "3"]:
        print("\n" + "="*50)
        print("RUNNING AUTOMATED TESTS")
        test_write_concern()
    
    if choice in ["2", "3"]:
        test_curl_commands()
    
    print("\nDone!")