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
import atexit
from datetime import datetime
from flask import Flask, request, jsonify
from typing import List, Dict
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
        print("MASTER SERVER V2 - NO DEDUPLICATION")  # Debug marker
        self.app = Flask(__name__)
        self.messages: List[Dict] = []
        self.secondaries: List[str] = []
        self.message_lock = threading.Lock()
        
        # Separate ID counter with its own lock
        self.next_id = 1
        self.counter_lock = threading.Lock()
        
        # Persistent ThreadPoolExecutor for replication
        self.executor = ThreadPoolExecutor()
        
        # Setup routes
        self.setup_routes()
        
        # Load secondary servers from environment
        self.load_secondaries()
        
        # Register shutdown handler
        atexit.register(self.shutdown)
        
    def shutdown(self):
        """Shutdown ThreadPoolExecutor gracefully"""
        if self.executor:
            logger.info("Shutting down ThreadPoolExecutor")
            self.executor.shutdown()
        
    def load_secondaries(self):
        """Load secondary server URLs from environment variables"""
        secondaries_env = os.environ.get('SECONDARIES', '')
        if secondaries_env:
            self.secondaries = [url.strip() for url in secondaries_env.split(',') if url.strip()]
            logger.info(f"Loaded {len(self.secondaries)} secondary servers: {self.secondaries}")
        else:
            logger.warning("No secondary servers configured")
            
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
            
            # Validate write concern
            max_w = len(self.secondaries) + 1  # Master + all secondaries
            if write_concern < 1 or write_concern > max_w:
                return jsonify({"error": f"Invalid write concern. Must be between 1 and {max_w}"}), 400
            
            # Generate unique ID using separate counter and lock
            with self.counter_lock:
                message_id = self.next_id
                self.next_id += 1
            
            # Compute hash for secondary compatibility (even though master doesn't use it for deduplication)
            message_hash = hashlib.sha256(message_text.encode('utf-8')).hexdigest()
            
            message_entry = {
                "id": message_id,
                "sequence": message_id,  # Include for secondary compatibility
                "message": message_text,
                "timestamp": timestamp,
                "hash": message_hash  # Include for secondary compatibility
            }
            
            logger.info(f"Received POST request with message: {message_text}, write concern: {write_concern}")
            
            # Add to master's log first
            with self.message_lock:
                self.messages.append(message_entry)
            
            # Decrement write concern for master's write
            write_concern -= 1
            logger.info(f"Message stored on master, remaining write concern: {write_concern}")

            # Need more ACKs - replicate to secondaries synchronously
            if self.secondaries:
                logger.info(f"Starting replication to {len(self.secondaries)} secondaries, need {write_concern} more ACKs")
                success = self.replicate_to_secondaries_with_concern(message_entry, write_concern)
                
                if success:
                    logger.info(f"Message {message_entry['id']} successfully replicated with required write concern")
                    return jsonify({
                        "id": message_id,
                        "message": message_text
                    }), 201
                else:
                    logger.warning(f"Message {message_entry['id']} did not meet required write concern")
                    return jsonify({
                        "id": message_id,
                        "message": message_text,
                        "warning": "Required write concern not met"
                    }), 202
            else:
                # No secondaries available but write concern > 0
                logger.warning(f"Message {message_entry['id']} did not meet required write concern (no secondaries)")
                return jsonify({
                    "id": message_id,
                    "message": message_text,
                    "warning": "Required write concern not met"
                }), 202
            
        except Exception as e:
            logger.error(f"Error handling POST request: {e}")
            return jsonify({"error": "Internal server error"}), 500
    
    def handle_get_messages(self):
        """Handle GET requests to retrieve all messages"""
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
                
            logger.info(f"Returning {len(client_messages)} messages to client")
            
            return jsonify({
                "messages": client_messages
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

        def replicate_to_secondary(secondary_url: str) -> bool:
            try:
                response = requests.post(
                    f"{secondary_url}/replicate",
                    json=message_entry,
                    timeout=30
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
            # Submit all replication tasks
            futures = []
            for secondary_url in self.secondaries:
                futures.append(self.executor.submit(replicate_to_secondary, secondary_url))

            if write_concern == 0:
                return True
            
            # Monitor completion and check write concern
            acks_received = 0
            try:
                for future in as_completed(futures, timeout=30):
                    success = future.result()
                    if success:
                        acks_received += 1
                        logger.info(f"ACK received ({acks_received}/{write_concern} needed)")
                        if acks_received >= write_concern:
                            logger.info("Write concern satisfied")
                            return True
            except Exception as e:
                logger.error(f"Error waiting for replication completion: {e}")
            
            logger.warning(f"Write concern not satisfied, got {acks_received}/{write_concern} ACKs")
            return False
                
        except Exception as e:
            logger.error(f"Error in replication: {e}")
            return False
        
    def run(self, host='0.0.0.0', port=5000):
        """Run the master server"""
        logger.info(f"Starting Master server on {host}:{port} with threading enabled")
        try:
            self.app.run(host=host, port=port, debug=False, threaded=True)
        finally:
            self.shutdown()

if __name__ == "__main__":
    master = MasterServer()
    master.run()