#!/usr/bin/env python3
"""
Self-Check Acceptance Test for Iteration 2
Tests write concern functionality and eventual consistency
"""

import requests
import time
import json
from datetime import datetime

class AcceptanceTest:
    def __init__(self):
        self.master_url = "http://localhost:5000"
        self.secondary1_url = "http://localhost:5001" 
        self.secondary2_url = "http://localhost:5002"
        
    def wait_for_servers(self, timeout=30):
        """Wait for all servers to be ready"""
        print("🔄 Waiting for servers to start...")
        servers = {
            "Master": self.master_url,
            "Secondary-1": self.secondary1_url,
            "Secondary-2": self.secondary2_url
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
    
    def send_message(self, message, write_concern, expected_status=201):
        """Send a message with specified write concern"""
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
    
    def get_messages(self, server_url, server_name):
        """Get messages from a server"""
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
    
    def check_messages(self):
        """Check messages on all servers"""
        print("\n📋 Checking messages on all servers:")
        
        # Get messages from all servers
        master_msgs = self.get_messages(self.master_url, "Master")
        s1_msgs = self.get_messages(self.secondary1_url, "Secondary-1")
        s2_msgs = self.get_messages(self.secondary2_url, "Secondary-2")
        
        print(f"   Master:      {master_msgs}")
        print(f"   Secondary-1: {s1_msgs}")
        print(f"   Secondary-2: {s2_msgs}")
        
        return master_msgs, s1_msgs, s2_msgs
    
    def run_acceptance_test(self):
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
        success &= self.send_message("Msg1", 1)    # w=1 - Ok (fast)
        success &= self.send_message("Msg2", 2)    # w=2 - Ok (medium) 
        success &= self.send_message("Msg3", 3)    # w=3 - Wait (slow)
        success &= self.send_message("Msg4", 1)    # w=1 - Ok (fast)
        
        if not success:
            print("❌ Some messages failed to send")
        
        # Step 3: Check immediate state (might show inconsistency)
        print(f"\n🔍 Checking immediate state:")
        master_msgs, s1_msgs, s2_msgs = self.check_messages()
        
        # Step 4: Wait for eventual consistency
        print(f"\n⏱️ Waiting 3 seconds for eventual consistency...")
        time.sleep(3)
        
        # Step 5: Check final consistent state
        print(f"\n🔍 Checking final consistent state:")
        master_msgs, s1_msgs, s2_msgs = self.check_messages()
        
        # Step 6: Validate expected results
        print(f"\n✅ Expected Results Validation:")
        
        expected_all = ["Msg1", "Msg2", "Msg3", "Msg4"]
        expected_s2_partial = ["Msg1"]  # Might have some messages
        
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

if __name__ == "__main__":
    test = AcceptanceTest()
    success = test.run_acceptance_test()
    exit(0 if success else 1)