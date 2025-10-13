#!/usr/bin/env python3
"""
Echo Client - Iteration 0
A simple echo client that connects to the echo server and sends messages.
"""

import socket
import threading
import logging
import time
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('echo_client.log'),
        logging.StreamHandler()
    ]
)

class EchoClient:
    def __init__(self, host='localhost', port=8080):
        self.host = host
        self.port = port
        self.socket = None
        self.connected = False
        
    def connect(self):
        """Connect to the echo server"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            self.connected = True
            logging.info(f"Connected to echo server at {self.host}:{self.port}")
            return True
        except Exception as e:
            logging.error(f"Failed to connect to server: {e}")
            return False
            
    def send_message(self, message):
        """Send a message to the server and receive echo"""
        if not self.connected:
            logging.error("Not connected to server")
            return None
            
        try:
            # Send message
            self.socket.send(message.encode('utf-8'))
            logging.info(f"Sent: {message}")
            
            # Receive echo
            response = self.socket.recv(1024).decode('utf-8')
            logging.info(f"Received: {response.strip()}")
            return response
            
        except Exception as e:
            logging.error(f"Error sending message: {e}")
            return None
            
    def disconnect(self):
        """Disconnect from the server"""
        if self.socket:
            self.socket.close()
            self.connected = False
            logging.info("Disconnected from server")
            
    def interactive_mode(self):
        """Run client in interactive mode"""
        print("Echo Client - Interactive Mode")
        print("Type 'quit' to exit")
        print("-" * 30)
        
        while True:
            try:
                message = input("Enter message: ")
                if message.lower() == 'quit':
                    break
                    
                response = self.send_message(message)
                if response:
                    print(f"Server response: {response.strip()}")
                else:
                    print("Failed to get response from server")
                    
            except KeyboardInterrupt:
                break
            except EOFError:
                break
                
        self.disconnect()

def main():
    # Parse command line arguments
    host = sys.argv[1] if len(sys.argv) > 1 else 'localhost'
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8080
    
    client = EchoClient(host, port)
    
    if client.connect():
        if len(sys.argv) > 3:
            # Send single message mode
            message = ' '.join(sys.argv[3:])
            response = client.send_message(message)
            if response:
                print(response.strip())
            client.disconnect()
        else:
            # Interactive mode
            client.interactive_mode()
    else:
        logging.error("Could not connect to server")
        sys.exit(1)

if __name__ == "__main__":
    main()