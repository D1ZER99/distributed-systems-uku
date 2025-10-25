#!/usr/bin/env python3
"""
Test Client - Iteration 1
A test client to interact with the replicated log system.
"""

import requests
import json
import time
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger('TestClient')

class ReplicatedLogClient:
    def __init__(self, master_url='http://localhost:5000'):
        self.master_url = master_url
        
    def post_message(self, message: str):
        """Send a POST request to add a message"""
        try:
            logger.info(f"Sending message: {message}")
            start_time = time.time()
            
            response = requests.post(
                f"{self.master_url}/messages",
                json={"message": message},
                timeout=60  # Allow time for replication
            )
            
            end_time = time.time()
            duration = end_time - start_time
            
            if response.status_code == 201:
                result = response.json()
                logger.info(f"Message posted successfully in {duration:.2f}s: {result}")
                return result
            else:
                logger.error(f"Failed to post message: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error posting message: {e}")
            return None
            
    def get_messages(self, server_url=None):
        """Get all messages from a server"""
        try:
            url = server_url or self.master_url
            logger.info(f"Getting messages from {url}")
            
            response = requests.get(f"{url}/messages", timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                messages = result.get('messages', [])
                logger.info(f"Retrieved {len(messages)} messages from server")
                return result
            else:
                logger.error(f"Failed to get messages: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting messages: {e}")
            return None
            
    def health_check(self, server_url):
        """Check server health"""
        try:
            response = requests.get(f"{server_url}/health", timeout=5)
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            logger.error(f"Health check failed for {server_url}: {e}")
            return None
            
    def demo_replication(self):
        """Demonstrate the replication system"""
        print("=== Replicated Log System Demo ===\n")
        
        # Health checks
        print("1. Health Checks:")
        servers = [
            ("Master", "http://localhost:5000"),
            ("Secondary-1", "http://localhost:5001"),
            ("Secondary-2", "http://localhost:5002")
        ]
        
        for name, url in servers:
            health = self.health_check(url)
            if health:
                print(f"   {name}: ✓ {health.get('status', 'unknown')} - {health.get('server_id', 'no-id')}")
            else:
                print(f"   {name}: ✗ Not responding")
        
        print("\n2. Initial State:")
        for name, url in servers:
            messages = self.get_messages(url)
            if messages:
                message_count = len(messages.get('messages', []))
                print(f"   {name}: {message_count} messages")
        
        print("\n3. Adding Messages (watch for replication delay):")
        test_messages = [
            "Hello, replicated world!",
            "This is message number 2",
            "Testing blocking replication",
            "Final test message"
        ]
        
        for i, msg in enumerate(test_messages, 1):
            print(f"\n   Posting message {i}/{len(test_messages)}: '{msg}'")
            result = self.post_message(msg)
            if result:
                print(f"   ✓ Posted successfully (replicated to {result.get('replicated_to', 0)} secondaries)")
            else:
                print(f"   ✗ Failed to post")
                
        print("\n4. Final State:")
        for name, url in servers:
            messages = self.get_messages(url)
            if messages:
                message_list = messages.get('messages', [])
                print(f"\n   {name}:")
                print(f"   Total messages: {len(message_list)}")
                for msg in message_list[-3:]:  # Show last 3 messages
                    print(f"     - [{msg['id']}] {msg['message']}")
                    
        print("\n=== Demo Complete ===")

def main():
    import sys
    
    client = ReplicatedLogClient()
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "demo":
            client.demo_replication()
        elif command == "post" and len(sys.argv) > 2:
            message = " ".join(sys.argv[2:])
            client.post_message(message)
        elif command == "get":
            server_url = sys.argv[2] if len(sys.argv) > 2 else None
            messages = client.get_messages(server_url)
            if messages:
                print(json.dumps(messages, indent=2))
        else:
            print("Usage: python test_client.py [demo|post <message>|get [server_url]]")
    else:
        client.demo_replication()

if __name__ == "__main__":
    main()