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
            
            # Replicate to secondaries based on write concern
            acks_needed = write_concern - 1  # Subtract 1 for master's own write
            acks_received = self.replicate_to_secondaries_with_concern(message_entry, acks_needed)
            
            # Check if we received enough acknowledgments
            if acks_received >= acks_needed:
                logger.info(f"Message {message_entry['id']} successfully replicated with {acks_received} ACKs")
                return jsonify({
                    "id": message_id,
                    "message": message_text
                }), 201
            else:
                # Not enough ACKs - still added to master but return different status
                logger.warning(f"Message {message_entry['id']} only received {acks_received} of {acks_needed} required ACKs")
                return jsonify({
                    "id": message_id,
                    "message": message_text,
                    "warning": f"Only {acks_received} of {acks_needed} replicas acknowledged"
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
            
    # def replicate_to_secondaries(self, message_entry: Dict) -> bool:
    #     """Replicate message to all secondary servers with blocking approach"""
    #     if not self.secondaries:
    #         logger.warning("No secondary servers to replicate to")
    #         return True  # No secondaries means replication is "successful"
            
    #     logger.info(f"Starting replication to {len(self.secondaries)} secondaries")
        
    #     # Use threading to send to all secondaries in parallel, but wait for all
    #     success_count = 0
    #     threads = []
    #     results = {}
        
    #     def replicate_to_secondary(secondary_url: str):
    #         try:
    #             response = requests.post(
    #                 f"{secondary_url}/replicate",
    #                 json=message_entry,
    #                 timeout=30  # 30 seconds timeout
    #             )
                
    #             if response.status_code == 200:
    #                 results[secondary_url] = True
    #                 logger.info(f"Successfully replicated to {secondary_url}")
    #             else:
    #                 results[secondary_url] = False
    #                 logger.error(f"Failed to replicate to {secondary_url}: {response.status_code}")
                    
    #         except Exception as e:
    #             results[secondary_url] = False
    #             logger.error(f"Error replicating to {secondary_url}: {e}")
                
    #     # Start replication threads
    #     for secondary_url in self.secondaries:
    #         thread = threading.Thread(target=replicate_to_secondary, args=(secondary_url,))
    #         thread.start()
    #         threads.append(thread)
            
    #     # Wait for all threads to complete
    #     for thread in threads:
    #         thread.join()
            
    #     # Check results
    #     success_count = sum(1 for success in results.values() if success)
        
    #     logger.info(f"Replication completed: {success_count}/{len(self.secondaries)} successful")
        
    #     # Return True only if ALL secondaries acknowledged
    #     return success_count == len(self.secondaries)
        
    def replicate_to_secondaries_with_concern(self, message_entry: Dict, acks_needed: int) -> int:
        """Replicate message to secondaries and return once enough ACKs received"""
        if not self.secondaries:
            logger.warning("No secondary servers to replicate to")
            return 0  # No secondaries available
            
        logger.info(f"Starting replication to {len(self.secondaries)} secondaries, need {acks_needed} ACKs")
        
        # If no ACKs needed (w=1), we can return immediately after starting replication
        if acks_needed <= 0:
            logger.info(f"No ACKs needed (w=1), starting background replication and returning immediately")
            
            # Start replication in background threads but don't wait
            def replicate_to_secondary_background(secondary_url: str):
                try:
                    logger.info(f"Background replication starting to {secondary_url}")
                    response = requests.post(
                        f"{secondary_url}/replicate",
                        json=message_entry,
                        timeout=30  # 30 seconds timeout
                    )
                    
                    if response.status_code == 200:
                        logger.info(f"Background replication successful to {secondary_url}")
                    else:
                        logger.error(f"Background replication failed to {secondary_url}: {response.status_code}")
                        
                except Exception as e:
                    logger.error(f"Background replication error to {secondary_url}: {e}")
                    
            # Start background replication threads
            for secondary_url in self.secondaries:
                thread = threading.Thread(target=replicate_to_secondary_background, args=(secondary_url,))
                thread.daemon = True  # Don't block shutdown
                thread.start()
                logger.info(f"Started background replication thread for {secondary_url}")
                
            logger.info(f"Returning immediately for w=1 without waiting")
            return 0  # Return immediately for w=1
        
        # For w>1, we need to wait for ACKs
        threads = []
        results = {}
        results_lock = threading.Lock()
        
        def replicate_to_secondary(secondary_url: str):
            try:
                response = requests.post(
                    f"{secondary_url}/replicate",
                    json=message_entry,
                    timeout=30  # 30 seconds timeout
                )
                
                with results_lock:
                    if response.status_code == 200:
                        results[secondary_url] = True
                        logger.info(f"Successfully replicated to {secondary_url}")
                    else:
                        results[secondary_url] = False
                        logger.error(f"Failed to replicate to {secondary_url}: {response.status_code}")
                        
            except Exception as e:
                with results_lock:
                    results[secondary_url] = False
                    logger.error(f"Error replicating to {secondary_url}: {e}")
                
        # Start replication threads
        for secondary_url in self.secondaries:
            thread = threading.Thread(target=replicate_to_secondary, args=(secondary_url,))
            thread.start()
            threads.append(thread)
            
        # Wait until we have enough ACKs or all threads complete
        import time
        start_time = time.time()
        max_wait_time = 30  # Maximum wait time in seconds
        
        while time.time() - start_time < max_wait_time:
            with results_lock:
                acks_received = sum(1 for success in results.values() if success)
                
            # If we have enough ACKs, we can return early
            if acks_received >= acks_needed:
                logger.info(f"Write concern satisfied: {acks_received}/{acks_needed} ACKs received")
                return acks_received
                
            # Check if all threads are done
            all_done = all(not thread.is_alive() for thread in threads)
            if all_done:
                break
                
            time.sleep(0.1)  # Small delay before checking again
            
        # Final count after timeout or all threads complete
        with results_lock:
            acks_received = sum(1 for success in results.values() if success)
            
        logger.info(f"Replication completed: {acks_received}/{len(self.secondaries)} acknowledged")
        
        return acks_received
        
    def run(self, host='0.0.0.0', port=5000):
        """Run the master server"""
        logger.info(f"Starting Master server on {host}:{port} with threading enabled")
        self.app.run(host=host, port=port, debug=False, threaded=True) # Enable threading for concurrent requests

if __name__ == "__main__":
    master = MasterServer()
    master.run()