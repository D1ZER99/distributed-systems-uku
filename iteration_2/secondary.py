#!/usr/bin/env python3
"""
Secondary Server - Iteration 1
A secondary server for the replicated log system that receives replicated messages
from the master and serves GET requests with intentional delay for testing.
"""

import logging
import json
import time
import threading
import hashlib
from datetime import datetime
from flask import Flask, request, jsonify
from typing import List, Dict, Set
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('secondary.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger('Secondary')

class SecondaryServer:
    def __init__(self, server_id: str = None):
        self.app = Flask(__name__)
        self.messages: List[Dict] = []
        self.message_lock = threading.Lock()
        self.server_id = server_id or os.environ.get('SERVER_ID', 'secondary-1')
        
        # Configurable delay for testing blocking replication
        self.replication_delay = float(os.environ.get('REPLICATION_DELAY', '2.0'))
        
        # Message deduplication
        self.message_hashes: Set[str] = set()
        self.dedup_lock = threading.Lock()
        
        # Setup routes
        self.setup_routes()
        
    def setup_routes(self):
        """Setup Flask routes"""
        
        @self.app.route('/health', methods=['GET'])
        def health():
            return jsonify({
                "status": "healthy", 
                "role": "secondary",
                "server_id": self.server_id,
                "message_count": len(self.messages)
            }), 200
            
        @self.app.route('/messages', methods=['GET'])
        def get_messages():
            return self.handle_get_messages()
            
        @self.app.route('/replicate', methods=['POST'])
        def replicate_message():
            return self.handle_replication()
            
    def handle_get_messages(self):
        """Handle GET requests to retrieve all replicated messages"""
        try:
            with self.message_lock:
                messages_copy = self.messages.copy()
                
            logger.info(f"Returning {len(messages_copy)} replicated messages")
            
            return jsonify({
                "messages": messages_copy
            }), 200
            
        except Exception as e:
            logger.error(f"Error handling GET request: {e}")
            return jsonify({"error": "Internal server error"}), 500
        
    def is_duplicate_message(self, message_hash: str) -> bool:
        """Check if message is a duplicate using hash"""
        with self.dedup_lock:
            logger.info(f"Secondary checking hash {message_hash[:8]}... against {len(self.message_hashes)} existing hashes")
            if message_hash in self.message_hashes:
                logger.info(f"Duplicate detected: hash {message_hash[:8]}...")
                return True
            self.message_hashes.add(message_hash)
            logger.info(f"New message: added hash {message_hash[:8]}..., total: {len(self.message_hashes)}")
            return False
            
    def insert_in_sequence_order(self, message_entry: Dict):
        """Insert message maintaining sequence order"""
        sequence = message_entry['sequence']
        
        # Find correct position to insert based on sequence number
        insert_pos = 0
        for i, existing_msg in enumerate(self.messages):
            if existing_msg['sequence'] > sequence:
                break
            insert_pos = i + 1
        
        # Insert at correct position
        self.messages.insert(insert_pos, message_entry)
        logger.info(f"Inserted message {message_entry['id']} at position {insert_pos} based on sequence {sequence}")
        
        # Log current message order for debugging
        sequences = [msg['sequence'] for msg in self.messages]
        logger.debug(f"Current message sequence order: {sequences}")    
            
    def handle_replication(self):
        """Handle replication requests from master"""
        try:
            # Introduce delay to test blocking replication
            if self.replication_delay > 0:
                logger.info(f"Introducing {self.replication_delay}s delay for replication testing")
                time.sleep(self.replication_delay)
                
            data = request.get_json()
            if not data:
                return jsonify({"error": "No data provided"}), 400
                
            # Validate message structure
            required_fields = ['id', 'sequence', 'message', 'timestamp', 'hash']
            if not all(field in data for field in required_fields):
                return jsonify({"error": "Invalid message format"}), 400
                
            # Check for duplicate messages using the new method
            message_hash = data['hash']
            if self.is_duplicate_message(message_hash):
                logger.info(f"Duplicate message detected, skipping replication")
                return jsonify({
                    "status": "duplicate",
                    "message_id": data['id']
                }), 200
                
            # Rest of the method stays the same...
            message_entry = {
                "id": data['id'],
                "sequence": data['sequence'],  # Preserve sequence number
                "message": data['message'], 
                "timestamp": data['timestamp'],
                "hash": data['hash'],
                "replicated_at": datetime.now().isoformat(),
                "replicated_by": self.server_id
            }
            
            # Insert message in sequence order instead of simple append
            with self.message_lock:
                self.insert_in_sequence_order(message_entry)
                logger.info(f"Replicated message {message_entry['id']} (seq: {message_entry['sequence']}): {message_entry['message']}")
                    
            # Send ACK back to master
            return jsonify({
                "status": "replicated",
                "message_id": message_entry['id'],
                "server_id": self.server_id,
                "total_messages": len(self.messages)
            }), 200
            
        except Exception as e:
            logger.error(f"Error handling replication: {e}")
            return jsonify({"error": "Replication failed"}), 500
                
    def register_with_master(self, master_url: str):
        """Register this secondary server with the master"""
        try:
            import requests
            
            secondary_url = f"http://{os.environ.get('SECONDARY_HOST', 'localhost')}:{os.environ.get('SECONDARY_PORT', '5001')}"
            
            response = requests.post(
                f"{master_url}/secondaries",
                json={"url": secondary_url},
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info(f"Successfully registered with master at {master_url}")
            else:
                logger.error(f"Failed to register with master: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Error registering with master: {e}")
            
    def run(self, host='0.0.0.0', port=5001):
        """Run the secondary server"""
        logger.info(f"Starting Secondary server '{self.server_id}' on {host}:{port}")
        logger.info(f"Replication delay set to {self.replication_delay}s")
        
        # Try to register with master if configured
        master_url = os.environ.get('MASTER_URL')
        if master_url:
            # Register in a separate thread to avoid blocking startup
            threading.Thread(
                target=self.register_with_master, 
                args=(master_url,), 
                daemon=True
            ).start()
            
        self.app.run(host=host, port=port, debug=False)

if __name__ == "__main__":
    secondary = SecondaryServer()
    
    # Get port from environment or use default
    port = int(os.environ.get('SECONDARY_PORT', '5001'))
    secondary.run(port=port)