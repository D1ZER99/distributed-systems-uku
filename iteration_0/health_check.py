# Simple health check for echo server
# This script tries to connect and send a test message

import socket
import time
import sys

def test_echo_server(host='localhost', port=8080, timeout=5):
    """Test if the echo server is responding"""
    
    print(f"Testing Echo Server at {host}:{port}")
    print("-" * 40)
    
    try:
        # Create socket and connect
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        
        print(f"Attempting to connect...")
        sock.connect((host, port))
        print("✓ Connected successfully!")
        
        # Send test message
        test_message = "Health Check Test Message"
        print(f"Sending: {test_message}")
        
        sock.send(test_message.encode('utf-8'))
        
        # Receive response
        response = sock.recv(1024).decode('utf-8')
        print(f"Received: {response.strip()}")
        
        # Verify echo functionality
        if test_message in response:
            print("✓ Echo functionality working correctly!")
            result = True
        else:
            print("✗ Echo functionality not working properly")
            result = False
            
        sock.close()
        return result
        
    except socket.timeout:
        print(f"✗ Connection timed out after {timeout} seconds")
        return False
    except ConnectionRefusedError:
        print("✗ Connection refused - server may not be running")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def multiple_client_test(host='localhost', port=8080):
    """Test multiple concurrent connections"""
    print("\nTesting multiple concurrent connections...")
    print("-" * 40)
    
    import threading
    
    results = []
    
    def client_test(client_id):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((host, port))
            
            message = f"Client {client_id} test message"
            sock.send(message.encode('utf-8'))
            
            response = sock.recv(1024).decode('utf-8')
            sock.close()
            
            if message in response:
                print(f"✓ Client {client_id}: Success")
                results.append(True)
            else:
                print(f"✗ Client {client_id}: Failed")
                results.append(False)
                
        except Exception as e:
            print(f"✗ Client {client_id}: Error - {e}")
            results.append(False)
    
    # Start multiple clients
    threads = []
    for i in range(3):
        thread = threading.Thread(target=client_test, args=(i+1,))
        threads.append(thread)
        thread.start()
    
    # Wait for all to complete
    for thread in threads:
        thread.join()
    
    success_count = sum(results)
    print(f"\nConcurrent test results: {success_count}/3 clients successful")

if __name__ == "__main__":
    # Parse command line arguments
    host = sys.argv[1] if len(sys.argv) > 1 else 'localhost'
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8080
    
    print("Echo Server Health Check")
    print("=" * 40)
    
    # Basic connectivity test
    if test_echo_server(host, port):
        # If basic test passes, try concurrent connections
        multiple_client_test(host, port)
    else:
        print("\nBasic connectivity failed. Server may not be running.")
        print("Try starting the server with:")
        print("  docker-compose up --build")
        print("  OR")
        print("  python echo_server.py")