#!/usr/bin/env python3
"""
Master Server - Iteration 1
A master server for the replicated log system that handles POST/GET requests
and replicates messages to secondary servers with blocking replication.
"""

import logging
import json
import time
import threading
import requests
import hashlib
from datetime import datetime
from flask import Flask, request, jsonify
from typing import List, Dict, Set
from concurrent.futures import ThreadPoolExecutor, as_completed
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('master.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger('Master')

class MasterServer:
    def __init__(self):
        print("DEDUPLICATION FEATURE ENABLED - MASTER V2")  # Debug marker
        self.app = Flask(__name__)
        self.messages: List[Dict] = []
        self.secondaries: List[str] = []
        self.message_lock = threading.Lock()
        
        # Separate ID counter with its own lock
        self.next_id = 1
        self.counter_lock = threading.Lock()
        
        # Message deduplication
        self.message_hashes: Set[str] = set()
        self.dedup_lock = threading.Lock()
        
        # Setup routes
        self.setup_routes()
        
        # Load secondary servers from environment
        self.load_secondaries()
        
    def load_secondaries(self):
        """Load secondary server URLs from environment variables"""
        secondaries_env = os.environ.get('SECONDARIES', '')
        if secondaries_env:
            self.secondaries = [url.strip() for url in secondaries_env.split(',') if url.strip()]
            logger.info(f"Loaded {len(self.secondaries)} secondary servers: {self.secondaries}")
        else:
            logger.warning("No secondary servers configured")
            
    def compute_message_hash(self, message_text: str) -> str:
        """Compute a hash for message deduplication based only on content"""
        # Create hash based only on message content for proper deduplication
        return hashlib.sha256(message_text.encode('utf-8')).hexdigest()
        
    def is_duplicate_message(self, message_hash: str) -> bool:
        """Check if message is a duplicate"""
        with self.dedup_lock:
            logger.info(f"Checking hash {message_hash[:8]}... against {len(self.message_hashes)} existing hashes")
            if message_hash in self.message_hashes:
                return True
            self.message_hashes.add(message_hash)
            logger.info(f"Added new hash {message_hash[:8]}..., total hashes: {len(self.message_hashes)}")
            return False
            
    def setup_routes(self):
        """Setup Flask routes"""
        
        @self.app.route('/health', methods=['GET'])
        def health():
            return jsonify({"status": "healthy", "role": "master"}), 200
            
        @self.app.route('/messages', methods=['POST'])
        def post_message():
            return self.handle_post_message()
            
        @self.app.route('/messages', methods=['GET'])
        def get_messages():
            return self.handle_get_messages()
            
        @self.app.route('/secondaries', methods=['POST'])
        def register_secondary():
            return self.handle_register_secondary()
            
    def handle_post_message(self):
        """Handle POST requests to append messages with write concern"""
        try:
            data = request.get_json()
            if not data or 'message' not in data:
                return jsonify({"error": "Message is required"}), 400
                
            message_text = data['message']
            # Parse write concern parameter (default to total replicas + 1 for master)
            write_concern = data.get('w', len(self.secondaries) + 1)
            timestamp = datetime.now().isoformat()
            
            # Check for message deduplication
            message_hash = self.compute_message_hash(message_text)
            logger.info(f"Computed hash for message '{message_text}': {message_hash[:8]}...")
            if self.is_duplicate_message(message_hash):
                logger.info(f"Duplicate message detected: {message_text}")
                return jsonify({"error": "Duplicate message"}), 409  # Conflict status
            
            # Validate write concern
            max_w = len(self.secondaries) + 1  # Master + all secondaries
            if write_concern < 1 or write_concern > max_w:
                return jsonify({"error": f"Invalid write concern. Must be between 1 and {max_w}"}), 400
            
            # Generate unique ID using separate counter and lock
            with self.counter_lock:
                message_id = self.next_id
                self.next_id += 1
            
            message_entry = {
                "id": message_id,
                "sequence": message_id,  # Use ID as sequence number for ordering
                "message": message_text,
                "timestamp": timestamp,
                "hash": message_hash
            }
            
            logger.info(f"Received POST request with message: {message_text}, write concern: {write_concern}")
            
            # Add to master's log first
            with self.message_lock:
                self.messages.append(message_entry)
            
            # Decrement write concern for master's write
            write_concern -= 1
            
            # Check if write concern already satisfied after master write
            if write_concern == 0:
                logger.info(f"Message {message_entry['id']} satisfied write concern with master write only")
                return jsonify({
                    "id": message_id,
                    "message": message_text
                }), 201
            
            # Replicate to secondaries based on remaining write concern
            success = self.replicate_to_secondaries_with_concern(message_entry, write_concern)
            
            # Return based on replication success
            if success:
                logger.info(f"Message {message_entry['id']} successfully replicated with required write concern")
                return jsonify({
                    "id": message_id,
                    "message": message_text
                }), 201
            else:
                # Not enough ACKs - still added to master but return different status
                logger.warning(f"Message {message_entry['id']} did not meet required write concern")
                return jsonify({
                    "id": message_id,
                    "message": message_text,
                    "warning": "Required write concern not met"
                }), 202  # Accepted but not fully replicated
            
        except Exception as e:
            logger.error(f"Error handling POST request: {e}")
            return jsonify({"error": "Internal server error"}), 500
            
    def handle_get_messages(self):
        """Handle GET requests to retrieve all messages"""
        try:
            with self.message_lock:
                messages_copy = self.messages.copy()
                
            logger.info(f"Returning {len(messages_copy)} messages")
            
            return jsonify({
                "messages": messages_copy
            }), 200
            
        except Exception as e:
            logger.error(f"Error handling GET request: {e}")
            return jsonify({"error": "Internal server error"}), 500
            
    def handle_register_secondary(self):
        """Handle secondary server registration"""
        try:
            data = request.get_json()
            if not data or 'url' not in data:
                return jsonify({"error": "URL is required"}), 400
                
            secondary_url = data['url']
            if secondary_url not in self.secondaries:
                self.secondaries.append(secondary_url)
                logger.info(f"Registered new secondary: {secondary_url}")
                
            return jsonify({"status": "registered", "total_secondaries": len(self.secondaries)}), 200
            
        except Exception as e:
            logger.error(f"Error registering secondary: {e}")
            return jsonify({"error": "Internal server error"}), 500
            
        
    def replicate_to_secondaries_with_concern(self, message_entry: Dict, write_concern: int) -> bool:
        """Replicate message to secondaries and return once enough ACKs received"""
        if not self.secondaries:
            logger.warning("No secondary servers to replicate to")
            return write_concern == 0  # Return True if no more ACKs needed
            
        logger.info(f"Starting replication to {len(self.secondaries)} secondaries, need {write_concern} more ACKs")
        
        def replicate_to_secondary(secondary_url: str) -> bool:
            try:
                response = requests.post(
                    f"{secondary_url}/replicate",
                    json=message_entry,
                    timeout=30  # 30 seconds timeout
                )
                
                if response.status_code == 200:
                    logger.info(f"Successfully replicated to {secondary_url}")
                    return True
                else:
                    logger.error(f"Failed to replicate to {secondary_url}: {response.status_code}")
                    return False
                    
            except Exception as e:
                logger.error(f"Error replicating to {secondary_url}: {e}")
                return False
        
        try:
            with ThreadPoolExecutor(max_workers=len(self.secondaries)) as executor:
                # Submit all replication tasks
                futures = []
                for secondary_url in self.secondaries:
                    futures.append(executor.submit(replicate_to_secondary, secondary_url))
                
                # If write concern already satisfied, return immediately
                if write_concern == 0:
                    logger.info("Write concern already satisfied before secondary replication")
                    return True
                
                # Monitor completion and check write concern
                try:
                    for future in as_completed(futures, timeout=30):
                        success = future.result()
                        if success:
                            write_concern -= 1
                            logger.info(f"ACK received, remaining write concern: {write_concern}")
                            if write_concern == 0:
                                logger.info("Write concern satisfied")
                                return True
                except Exception as e:
                    logger.error(f"Error waiting for replication completion: {e}")
                
                logger.warning(f"Write concern not satisfied, still need {write_concern} more ACKs")
                return False
                
        except Exception as e:
            logger.error(f"Error in ThreadPoolExecutor: {e}")
            return False
        
    def run(self, host='0.0.0.0', port=5000):
        """Run the master server"""
        logger.info(f"Starting Master server on {host}:{port} with threading enabled")
        self.app.run(host=host, port=port, debug=False, threaded=True) # Enable threading for concurrent requests

if __name__ == "__main__":
    master = MasterServer()
    master.run()