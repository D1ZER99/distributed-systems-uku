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
            required_fields = ['id', 'message', 'timestamp', 'hash']
            if not all(field in data for field in required_fields):
                return jsonify({"error": "Invalid message format"}), 400
                
            # Check for duplicate messages using hash
            message_hash = data['hash']
            with self.dedup_lock:
                if message_hash in self.message_hashes:
                    logger.info(f"Duplicate message detected (hash: {message_hash[:8]}...), skipping")
                    return jsonify({
                        "status": "duplicate",
                        "message_id": data['id']
                    }), 200  # Still return success since it's already processed
                self.message_hashes.add(message_hash)
                
            message_entry = {
                "id": data['id'],
                "message": data['message'],
                "timestamp": data['timestamp'],
                "hash": data['hash'],
                "replicated_at": datetime.now().isoformat(),
                "replicated_by": self.server_id
            }
            
            # Add message to secondary's list
            with self.message_lock:
                self.messages.append(message_entry)
                logger.info(f"Replicated message {message_entry['id']}: {message_entry['message']}")
                    
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