#!/usr/bin/env python3
"""
Secondary Server - Iteration 3
A secondary server with enhanced total order enforcement,
sync mechanism, and retry testing features.
"""

import logging
import json
import time
import threading
import hashlib
import random
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
        
        # Total order enforcement - pending messages waiting for sequence
        self.pending_messages: Dict[int, Dict] = {}  # {sequence: message}
        self.next_expected_sequence = 1
        self.order_lock = threading.Lock()
        
        # Test error generation
        self.error_rate = float(os.environ.get('ERROR_RATE', '0.1'))  # 10% chance of random errors
        
        # Setup routes
        self.setup_routes()
        
    def setup_routes(self):
        """Setup Flask routes"""
        
        @self.app.route('/health', methods=['GET'])
        def health():
            with self.message_lock:
                last_sequence = self.messages[-1]['sequence'] if self.messages else 0
            return jsonify({
                "status": "healthy", 
                "role": "secondary",
                "server_id": self.server_id,
                "message_count": len(self.messages),
                "last_sequence": last_sequence,
                "next_expected": self.next_expected_sequence
            }), 200
            
        @self.app.route('/messages', methods=['GET'])
        def get_messages():
            return self.handle_get_messages()
            
        @self.app.route('/replicate', methods=['POST'])
        def replicate_message():
            return self.handle_replication()
            
        @self.app.route('/sync', methods=['POST'])
        def sync_with_master():
            return self.handle_sync_request()
            
    def handle_get_messages(self):
        """Handle GET requests to retrieve all replicated messages"""
        try:
            with self.message_lock:
                messages_copy = self.messages.copy()
                
            # Return only essential fields to client (id and message)
            client_messages = []
            for msg in messages_copy:
                client_messages.append({
                    "id": msg["id"],
                    "message": msg["message"]
                })
                
            logger.info(f"Returning {len(client_messages)} replicated messages to client")
            
            return jsonify({
                "messages": client_messages
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
            
    def handle_sync_request(self):
        """Handle sync requests from master for missed message replication"""
        try:
            data = request.get_json()
            last_sequence = data.get('last_sequence', 0) if data else 0
            
            with self.message_lock:
                current_last = self.messages[-1]['sequence'] if self.messages else 0
                
            return jsonify({
                "status": "sync_info",
                "server_id": self.server_id,
                "last_sequence": current_last,
                "ready_for_sync": True
            }), 200
            
        except Exception as e:
            logger.error(f"Error handling sync request: {e}")
            return jsonify({"error": "Sync failed"}), 500
            
    def process_pending_messages(self):
        """Process pending messages that can now be added in sequence"""
        with self.order_lock:
            while self.next_expected_sequence in self.pending_messages:
                message_entry = self.pending_messages.pop(self.next_expected_sequence)
                
                # Add to main messages list
                with self.message_lock:
                    self.messages.append(message_entry)
                    
                logger.info(f"Processed pending message {message_entry['id']} with sequence {self.next_expected_sequence}")
                self.next_expected_sequence += 1
                
            # Log current state
            if self.pending_messages:
                pending_sequences = sorted(self.pending_messages.keys())
                logger.info(f"Still waiting for sequence {self.next_expected_sequence}, have pending: {pending_sequences}")
            
    def insert_in_total_order(self, message_entry: Dict):
        """Insert message enforcing strict total order - messages must arrive in sequence"""
        sequence = message_entry['sequence']
        
        with self.order_lock:
            if sequence == self.next_expected_sequence:
                # This is the next expected message, add it immediately
                with self.message_lock:
                    self.messages.append(message_entry)
                
                logger.info(f"Added message {message_entry['id']} with sequence {sequence} in order")
                self.next_expected_sequence += 1
                
                # Process any pending messages that can now be added
                self.process_pending_messages()
                
            elif sequence > self.next_expected_sequence:
                # Future message, store in pending
                self.pending_messages[sequence] = message_entry
                logger.info(f"Message {message_entry['id']} with sequence {sequence} is out of order (expecting {self.next_expected_sequence}), storing as pending")
                
            else:
                # Past message, this shouldn't happen with proper deduplication
                logger.warning(f"Message {message_entry['id']} with sequence {sequence} is from the past (expecting {self.next_expected_sequence}), ignoring")    
            
    def handle_replication(self):
        """Handle replication requests from master with enhanced error testing"""
        try:
            # Generate random errors for testing retry mechanism (after message is processed)
            will_error_after = random.random() < self.error_rate
            
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
                
            # Check for duplicate messages
            message_hash = data['hash']
            if self.is_duplicate_message(message_hash):
                logger.info(f"Duplicate message detected, skipping replication")
                return jsonify({
                    "status": "duplicate",
                    "message_id": data['id']
                }), 200
                
            # Create message entry
            message_entry = {
                "id": data['id'],
                "sequence": data['sequence'],
                "message": data['message'], 
                "timestamp": data['timestamp'],
                "hash": data['hash'],
                "replicated_at": datetime.now().isoformat(),
                "replicated_by": self.server_id
            }
            
            # Insert message with total order enforcement
            self.insert_in_total_order(message_entry)
            
            logger.info(f"Processed message {message_entry['id']} (seq: {message_entry['sequence']}): {message_entry['message']}")
            
            # Generate error AFTER processing message (to test deduplication)
            if will_error_after:
                logger.info(f"Generating test error after processing message {message_entry['id']}")
                return jsonify({"error": "Simulated internal server error"}), 500
                
            # Send successful ACK back to master
            return jsonify({
                "status": "replicated",
                "message_id": message_entry['id'],
                "server_id": self.server_id,
                "sequence": message_entry['sequence'],
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
            
        self.app.run(host=host, port=port, debug=False, threaded=True)

if __name__ == "__main__":
    secondary = SecondaryServer()
    
    # Get port from environment or use default
    port = int(os.environ.get('SECONDARY_PORT', '5001'))
    secondary.run(port=port)