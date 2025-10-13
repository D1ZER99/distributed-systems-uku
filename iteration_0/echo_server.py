#!/usr/bin/env python3
"""
Echo Server - Iteration 0
A simple echo server that receives messages from clients and echoes them back.
"""

import socket
import threading
import logging
import time
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('echo_server.log'),
        logging.StreamHandler()
    ]
)

class EchoServer:
    def __init__(self, host='0.0.0.0', port=8080):
        self.host = host
        self.port = port
        self.socket = None
        self.running = False
        
    def start(self):
        """Start the echo server"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind((self.host, self.port))
            self.socket.listen(5)
            self.running = True
            
            logging.info(f"Echo Server started on {self.host}:{self.port}")
            
            while self.running:
                try:
                    client_socket, address = self.socket.accept()
                    logging.info(f"New connection from {address}")
                    
                    # Handle each client in a separate thread
                    client_thread = threading.Thread(
                        target=self.handle_client,
                        args=(client_socket, address)
                    )
                    client_thread.daemon = True
                    client_thread.start()
                    
                except socket.error as e:
                    if self.running:
                        logging.error(f"Socket error: {e}")
                        
        except Exception as e:
            logging.error(f"Server error: {e}")
        finally:
            self.stop()
            
    def handle_client(self, client_socket, address):
        """Handle individual client connections"""
        try:
            while True:
                # Receive data from client
                data = client_socket.recv(1024).decode('utf-8')
                if not data:
                    break
                    
                # Log the received message
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                logging.info(f"Received from {address}: {data.strip()}")
                
                # Echo the message back with timestamp
                echo_message = f"[{timestamp}] Echo: {data}"
                client_socket.send(echo_message.encode('utf-8'))
                
        except Exception as e:
            logging.error(f"Error handling client {address}: {e}")
        finally:
            client_socket.close()
            logging.info(f"Connection closed for {address}")
            
    def stop(self):
        """Stop the echo server"""
        self.running = False
        if self.socket:
            self.socket.close()
        logging.info("Echo Server stopped")

if __name__ == "__main__":
    server = EchoServer()
    try:
        server.start()
    except KeyboardInterrupt:
        logging.info("Server interrupted by user")
        server.stop()