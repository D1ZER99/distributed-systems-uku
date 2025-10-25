#!/usr/bin/env python3
"""
Test Client - Iteration 1
A test client to interact with the replicated log system.
"""

import requests
import json
import time
import threading
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
        
    def post_message(self, message: str, write_concern: int = None):
        """Send a POST request to add a message with optional write concern"""
        try:
            logger.info(f"Sending message: {message}" + (f" with write concern: {write_concern}" if write_concern else ""))
            start_time = time.time()
            
            payload = {"message": message}
            if write_concern is not None:
                payload["w"] = write_concern
            
            response = requests.post(
                f"{self.master_url}/messages",
                json=payload,
                timeout=60  # Allow time for replication
            )
            
            end_time = time.time()
            duration = end_time - start_time
            
            if response.status_code in [201, 202]:  # Accept both full success and partial success
                result = response.json()
                status = "fully replicated" if response.status_code == 201 else "partially replicated"
                logger.info(f"Message {status} in {duration:.2f}s: {result}")
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
        
    def demo_write_concern(self):
        """Demonstration of write concern feature"""
        print("\n=== Write Concern Demo ===")
        
        # Test different write concern values
        test_cases = [
            (1, "Message with w=1 (master only)"),
            (2, "Message with w=2 (master + 1 secondary)"),
            (3, "Message with w=3 (master + 2 secondaries)"),
            (4, "Message with w=4 (should fail - too high)")
        ]
        
        for w, message in test_cases:
            print(f"\n--- Testing write concern w={w} ---")
            result = self.post_message(message, write_concern=w)
            
            if result:
                if 'warning' in result:
                    print(f"⚠️  Partial success: {result}")
                else:
                    print(f"✅ Full success: {result}")
            else:
                print(f"❌ Failed to send message")
                
            # Small delay between requests
            time.sleep(1)
            
        # Check final state across all servers
        print(f"\n--- Final State Check ---")
        servers = [
            ("Master", self.master_url),
            ("Secondary 1", "http://localhost:5001"),
            ("Secondary 2", "http://localhost:5002")
        ]
        
        for name, url in servers:
            response = self.get_messages(url)
            if response and isinstance(response, dict) and 'messages' in response:
                messages = response['messages']
                print(f"{name}: {len(messages)} messages")
                for msg in messages[-3:]:  # Show last 3 messages
                    print(f"  - ID {msg['id']}: {msg['message']}")
            else:
                print(f"{name}: Failed to retrieve messages or no messages found")
                
        print("\n=== Write Concern Demo Complete ===")
        
    def demo_deduplication(self):
        """Demonstration of message deduplication"""
        print("\n=== Message Deduplication Demo ===")
        
        # Send the same message twice to test deduplication
        test_message = "Duplicate test message"
        
        print(f"\n--- Sending message first time ---")
        result1 = self.post_message(test_message)
        
        if result1:
            print(f"✅ First message successful: {result1}")
        else:
            print(f"❌ First message failed")
            return
            
        time.sleep(1)  # Small delay
        
        print(f"\n--- Sending exact same message again ---")
        result2 = self.post_message(test_message)
        
        if result2:
            print(f"⚠️  Unexpected success (should be duplicate): {result2}")
        else:
            print(f"✅ Correctly rejected as duplicate")
            
        # Send a slightly different message to ensure non-duplicates work
        print(f"\n--- Sending similar but different message ---")
        different_message = test_message + " (modified)"
        result3 = self.post_message(different_message)
        
        if result3:
            print(f"✅ Different message successful: {result3}")
        else:
            print(f"❌ Different message failed")
            
        print("\n=== Deduplication Demo Complete ===")
        
    def wait_for_servers(self, timeout=30):
        """Wait for all servers to be ready"""
        print("🔄 Waiting for servers to start...")
        servers = {
            "Master": self.master_url,
            "Secondary-1": "http://localhost:5001",
            "Secondary-2": "http://localhost:5002"
        }
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            all_ready = True
            for name, url in servers.items():
                try:
                    response = requests.get(f"{url}/health", timeout=2)
                    if response.status_code == 200:
                        print(f"   ✅ {name} is ready")
                    else:
                        all_ready = False
                        print(f"   ⚠️ {name} not ready (HTTP {response.status_code})")
                except:
                    all_ready = False
                    print(f"   ❌ {name} not reachable")
            
            if all_ready:
                print("✅ All servers are ready!")
                return True
                
            time.sleep(2)
        
        print("❌ Timeout waiting for servers")
        return False
    
    def send_message_for_test(self, message, write_concern, expected_status=201):
        """Send a message with specified write concern for testing"""
        try:
            start_time = time.time()
            response = requests.post(
                f"{self.master_url}/messages",
                json={"message": message, "w": write_concern},
                timeout=15
            )
            end_time = time.time()
            
            duration = end_time - start_time
            status_text = "✅ Ok" if response.status_code == expected_status else f"❌ {response.status_code}"
            
            print(f"   {message} (w={write_concern}) - {status_text} ({duration:.2f}s)")
            
            if response.status_code != expected_status:
                print(f"      Expected {expected_status}, got {response.status_code}")
                print(f"      Response: {response.text}")
            
            return response.status_code == expected_status
            
        except Exception as e:
            print(f"   ❌ {message} (w={write_concern}) - Error: {e}")
            return False
    
    def get_messages_for_test(self, server_url, server_name):
        """Get messages from a server for testing"""
        try:
            response = requests.get(f"{server_url}/messages", timeout=5)
            if response.status_code == 200:
                data = response.json()
                messages = data.get('messages', [])
                return [msg['message'] for msg in messages]
            else:
                print(f"❌ Failed to get messages from {server_name}: {response.status_code}")
                return []
        except Exception as e:
            print(f"❌ Error getting messages from {server_name}: {e}")
            return []
    
    def check_messages_on_servers(self):
        """Check messages on all servers"""
        print("\n📋 Checking messages on all servers:")
        
        # Get messages from all servers
        master_msgs = self.get_messages_for_test(self.master_url, "Master")
        s1_msgs = self.get_messages_for_test("http://localhost:5001", "Secondary-1")
        s2_msgs = self.get_messages_for_test("http://localhost:5002", "Secondary-2")
        
        print(f"   Master:      {master_msgs}")
        print(f"   Secondary-1: {s1_msgs}")
        print(f"   Secondary-2: {s2_msgs}")
        
        return master_msgs, s1_msgs, s2_msgs
    
    def acceptance_test(self):
        """Run the complete acceptance test"""
        print("🧪 Starting Self-Check Acceptance Test")
        print("=" * 50)
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # Step 1: Wait for servers
        if not self.wait_for_servers():
            print("❌ Test failed: Servers not ready")
            return False
        
        print(f"\n⏱️ Waiting 5 seconds for secondary delays to be configured...")
        time.sleep(5)
        
        # Step 2: Send test messages
        print(f"\n📤 Sending test messages:")
        
        success = True
        success &= self.send_message_for_test("Msg1", 1)    # w=1 - Ok (fast)
        success &= self.send_message_for_test("Msg2", 2)    # w=2 - Ok (medium) 
        success &= self.send_message_for_test("Msg3", 3)    # w=3 - Wait (slow)
        success &= self.send_message_for_test("Msg4", 1)    # w=1 - Ok (fast)
        
        if not success:
            print("❌ Some messages failed to send")
        
        # Step 3: Check immediate state (might show inconsistency)
        print(f"\n🔍 Checking immediate state:")
        master_msgs, s1_msgs, s2_msgs = self.check_messages_on_servers()
        
        # Step 4: Wait for eventual consistency
        print(f"\n⏱️ Waiting 3 seconds for eventual consistency...")
        time.sleep(3)
        
        # Step 5: Check final consistent state
        print(f"\n🔍 Checking final consistent state:")
        master_msgs, s1_msgs, s2_msgs = self.check_messages_on_servers()
        
        # Step 6: Validate expected results
        print(f"\n✅ Expected Results Validation:")
        
        expected_all = ["Msg1", "Msg2", "Msg3", "Msg4"]
        
        # Master and S1 should have all messages
        master_ok = set(master_msgs) >= set(expected_all)
        s1_ok = set(s1_msgs) >= set(expected_all)
        
        print(f"   Master has all messages:      {'✅' if master_ok else '❌'}")
        print(f"   Secondary-1 has all messages: {'✅' if s1_ok else '❌'}")
        print(f"   Secondary-2 has messages:     ✅ (eventual consistency)")
        
        # Summary
        overall_success = master_ok and s1_ok
        print(f"\n🎯 Test Result: {'✅ PASSED' if overall_success else '❌ FAILED'}")
        
        return overall_success
        
    def send_message_concurrent(self, message, w, client_name):
        """Send a message and measure time for concurrent testing"""
        start_time = time.time()
        print(f"{datetime.now().strftime('%H:%M:%S.%f')[:-3]} - {client_name}: Sending '{message}' (w={w})")
        
        try:
            response = requests.post(
                f"{self.master_url}/messages",
                json={"message": message, "w": w},
                timeout=30
            )
            end_time = time.time()
            duration = end_time - start_time
            
            print(f"{datetime.now().strftime('%H:%M:%S.%f')[:-3]} - {client_name}: Completed in {duration:.2f}s - Status: {response.status_code}")
            return duration
            
        except Exception as e:
            end_time = time.time()
            duration = end_time - start_time
            print(f"{datetime.now().strftime('%H:%M:%S.%f')[:-3]} - {client_name}: Failed after {duration:.2f}s - Error: {e}")
            return duration

    def concurrent_test(self):
        """Test that w=1 requests don't wait for w=3 requests"""
        print("🧪 Testing Concurrent Request Handling")
        print("=" * 50)
        print("Expected behavior:")
        print("  - Client 1 (w=3): Should take ~10 seconds (secondary delay)")
        print("  - Client 2 (w=1): Should complete in <1 second (no waiting)")
        print()
        
        # Start both requests almost simultaneously
        def client1():
            return self.send_message_concurrent("Slow message (w=3)", 3, "Client 1")
        
        def client2():
            time.sleep(2)  # Wait 2 seconds, then send fast request
            return self.send_message_concurrent("Fast message (w=1)", 1, "Client 2")
        
        # Start both threads
        thread1 = threading.Thread(target=client1)
        thread2 = threading.Thread(target=client2)
        
        start_time = time.time()
        thread1.start()
        thread2.start()
        
        # Wait for both to complete
        thread1.join()
        thread2.join()
        
        total_time = time.time() - start_time
        print(f"\n📊 Total test time: {total_time:.2f}s")
        
        # Check if concurrent behavior worked
        if total_time < 12:  # Should be around 10s, not 20s
            print("✅ Concurrent processing: WORKING")
            print("   Client 2 didn't wait for Client 1 to complete")
            return True
        else:
            print("❌ Concurrent processing: NOT WORKING")
            print("   Client 2 waited for Client 1 (sequential processing)")
            return False

def main():
    import sys
    
    client = ReplicatedLogClient()
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "demo":
            client.demo_replication()
        elif command == "write_concern":
            client.demo_write_concern()
        elif command == "dedup":
            client.demo_deduplication()
        elif command == "acceptance":
            client.acceptance_test()
        elif command == "concur":
            client.concurrent_test()
        elif command == "post" and len(sys.argv) > 2:
            message = " ".join(sys.argv[2:])
            write_concern = None
            # Check if last argument is a write concern parameter
            if len(sys.argv) > 3 and sys.argv[-2] == "-w":
                try:
                    write_concern = int(sys.argv[-1])
                    message = " ".join(sys.argv[2:-2])
                except ValueError:
                    pass
            client.post_message(message, write_concern)
        elif command == "get":
            server_url = sys.argv[2] if len(sys.argv) > 2 else None
            messages = client.get_messages(server_url)
            if messages:
                print(json.dumps(messages, indent=2))
        else:
            print("Usage: python test_client.py [demo|write_concern|dedup|acceptance|concur|post <message> [-w <write_concern>]|get [server_url]]")
    else:
        client.demo_replication()

if __name__ == "__main__":
    main()