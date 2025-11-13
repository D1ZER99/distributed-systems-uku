#!/usr/bin/env python3
"""
Test Script for Iteration 3 - Retry Mechanism Demonstration
"""

import requests
import time
import threading
from datetime import datetime

def test_retry_mechanism():
    """Test the retry mechanism with secondary failures"""
    print("🧪 Testing Retry Mechanism (Iteration 3)")
    print("=" * 50)
    
    # Test 1: Basic message with retries
    print("\n📝 Test 1: Sending message with retry mechanism")
    try:
        response = requests.post(
            "http://localhost:5000/messages",
            json={"message": "Test message with retries", "w": 2},
            timeout=60
        )
        print(f"✅ Status: {response.status_code}")
        print(f"📄 Response: {response.json()}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test 2: Check total order
    print("\n🔢 Test 2: Verifying total order in secondary")
    try:
        response = requests.get("http://localhost:5001/messages")
        messages = response.json().get("messages", [])
        print(f"📊 Secondary has {len(messages)} messages")
        if messages:
            ids = [msg["id"] for msg in messages]
            print(f"🔢 Message IDs in order: {ids}")
    except Exception as e:
        print(f"❌ Error getting secondary messages: {e}")
    
    # Test 3: Health check with sequence info
    print("\n💓 Test 3: Secondary health with sequence tracking")
    try:
        response = requests.get("http://localhost:5001/health")
        health = response.json()
        print(f"🏥 Secondary health: {health}")
    except Exception as e:
        print(f"❌ Error getting health: {e}")

def test_concurrent_with_retry():
    """Test concurrent operations don't block each other during retries"""
    print("\n🚀 Testing Concurrent Operations with Retry")
    print("=" * 50)
    
    def send_message(msg, w, delay=0):
        if delay:
            time.sleep(delay)
        start_time = time.time()
        try:
            response = requests.post(
                "http://localhost:5000/messages",
                json={"message": msg, "w": w},
                timeout=60
            )
            duration = time.time() - start_time
            print(f"✅ '{msg}' (w={w}): {duration:.1f}s - {response.status_code}")
            return duration
        except Exception as e:
            duration = time.time() - start_time
            print(f"❌ '{msg}' failed after {duration:.1f}s: {e}")
            return duration
    
    # Send concurrent requests
    threads = []
    threads.append(threading.Thread(target=send_message, args=("Fast message (w=1)", 1, 0)))
    threads.append(threading.Thread(target=send_message, args=("Slow message (w=3)", 3, 1)))
    threads.append(threading.Thread(target=send_message, args=("Another fast (w=1)", 1, 2)))
    
    print("🏁 Starting concurrent requests...")
    for thread in threads:
        thread.start()
    
    for thread in threads:
        thread.join()

if __name__ == "__main__":
    print("🔄 Replicated Log System - Iteration 3 Test")
    print("📋 Expected setup: Master on :5000, Secondary on :5001")
    print("⚠️  Make sure to set ERROR_RATE=0.1 and REPLICATION_DELAY=2.0 on secondary")
    print()
    
    # Wait for user confirmation
    input("Press Enter when servers are running...")
    
    test_retry_mechanism()
    time.sleep(2)
    test_concurrent_with_retry()
    
    print("\n✨ Test complete! Check logs for retry attempts and total order enforcement.")