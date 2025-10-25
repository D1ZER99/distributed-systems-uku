#!/usr/bin/env python3
"""
Concurrent Request Test - Tests that w=1 doesn't wait for w=3
"""

import requests
import threading
import time
from datetime import datetime

def send_message(message, w, client_name):
    """Send a message and measure time"""
    start_time = time.time()
    print(f"{datetime.now().strftime('%H:%M:%S.%f')[:-3]} - {client_name}: Sending '{message}' (w={w})")
    
    try:
        response = requests.post(
            "http://localhost:5000/messages",
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

def test_concurrent_requests():
    """Test that w=1 requests don't wait for w=3 requests"""
    print("🧪 Testing Concurrent Request Handling")
    print("=" * 50)
    print("Expected behavior:")
    print("  - Client 1 (w=3): Should take ~10 seconds (secondary delay)")
    print("  - Client 2 (w=1): Should complete in <1 second (no waiting)")
    print()
    
    # Start both requests almost simultaneously
    def client1():
        return send_message("Slow message (w=3)", 3, "Client 1")
    
    def client2():
        time.sleep(2)  # Wait 2 seconds, then send fast request
        return send_message("Fast message (w=1)", 1, "Client 2")
    
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
    else:
        print("❌ Concurrent processing: NOT WORKING")
        print("   Client 2 waited for Client 1 (sequential processing)")

if __name__ == "__main__":
    test_concurrent_requests()