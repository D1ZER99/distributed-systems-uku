#!/usr/bin/env python3
"""
Master Server - Iteration 3
A master server for the replicated log system with retry mechanism,
missed message replication, and tunable semi-synchronous replication.
"""

import logging
import json
import time
import threading
import requests
import hashlib
import atexit
import random
from datetime import datetime
from flask import Flask, request, jsonify
from typing import List, Dict, Set, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed, Future
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
        print("MASTER SERVER V3 - WITH RETRY MECHANISM")  # Debug marker
        self.app = Flask(__name__)
        self.messages: List[Dict] = []
        self.secondaries: List[str] = []
        self.message_lock = threading.Lock()
        
        # Separate ID counter with its own lock
        self.next_id = 1
        self.counter_lock = threading.Lock()
        
        # Persistent ThreadPoolExecutor for replication
        self.executor = ThreadPoolExecutor()
        
        # Secondary state tracking for missed message replication
        self.secondary_states: Dict[str, Dict] = {}  # {url: {"last_sequence": int, "available": bool}}
        self.state_lock = threading.Lock()
        
        # Retry configuration
        self.max_retry_attempts = int(os.environ.get('MAX_RETRY_ATTEMPTS', '-1'))  # -1 = unlimited
        self.initial_retry_delay = float(os.environ.get('INITIAL_RETRY_DELAY', '1.0'))
        self.max_retry_delay = float(os.environ.get('MAX_RETRY_DELAY', '60.0'))
        self.replication_timeout = float(os.environ.get('REPLICATION_TIMEOUT', '30.0'))
        
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
            # Initialize secondary states
            with self.state_lock:
                for secondary_url in self.secondaries:
                    self.secondary_states[secondary_url] = {
                        "last_sequence": 0,
                        "available": True,
                        "last_seen": datetime.now().isoformat()
                    }
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
            
        @self.app.route('/sync/<path:secondary_url>', methods=['POST'])
        def sync_secondary(secondary_url):
            return self.handle_secondary_sync(secondary_url)
            
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
                
            # Initialize or update secondary state
            with self.state_lock:
                if secondary_url not in self.secondary_states:
                    self.secondary_states[secondary_url] = {
                        "last_sequence": 0,
                        "available": True,
                        "last_seen": datetime.now().isoformat()
                    }
                else:
                    self.secondary_states[secondary_url]["available"] = True
                    self.secondary_states[secondary_url]["last_seen"] = datetime.now().isoformat()
                    
            logger.info(f"Registered secondary: {secondary_url}")
                
            # Trigger catch-up replication for rejoining secondary
            self.trigger_catch_up_replication(secondary_url)
                
            return jsonify({"status": "registered", "total_secondaries": len(self.secondaries)}), 200
            
        except Exception as e:
            logger.error(f"Error registering secondary: {e}")
            return jsonify({"error": "Internal server error"}), 500
            
        
    def handle_secondary_sync(self, secondary_url: str):
        """Handle secondary synchronization requests"""
        try:
            # Decode URL if needed
            secondary_url = secondary_url.replace('%3A', ':').replace('%2F', '/')
            
            data = request.get_json()
            last_sequence = data.get('last_sequence', 0) if data else 0
            
            # Find missed messages
            missed_messages = []
            with self.message_lock:
                for msg in self.messages:
                    if msg['sequence'] > last_sequence:
                        missed_messages.append(msg)
                        
            logger.info(f"Sending {len(missed_messages)} missed messages to {secondary_url}")
            
            return jsonify({
                "status": "sync_ready",
                "missed_messages": missed_messages,
                "total_messages": len(self.messages)
            }), 200
            
        except Exception as e:
            logger.error(f"Error handling secondary sync: {e}")
            return jsonify({"error": "Internal server error"}), 500

    def trigger_catch_up_replication(self, secondary_url: str):
        """Trigger catch-up replication for a rejoining secondary in background"""
        def do_catch_up():
            try:
                # Get secondary's last sequence number
                with self.state_lock:
                    last_sequence = self.secondary_states.get(secondary_url, {}).get('last_sequence', 0)
                
                # Find missed messages
                missed_messages = []
                with self.message_lock:
                    for msg in self.messages:
                        if msg['sequence'] > last_sequence:
                            missed_messages.append(msg)
                
                if not missed_messages:
                    logger.info(f"No missed messages for {secondary_url}")
                    return
                    
                logger.info(f"Replicating {len(missed_messages)} missed messages to {secondary_url}")
                
                # Replicate missed messages one by one with retry
                for msg in missed_messages:
                    success = self.replicate_single_message_with_retry(secondary_url, msg, max_attempts=5)
                    if success:
                        with self.state_lock:
                            if secondary_url in self.secondary_states:
                                self.secondary_states[secondary_url]['last_sequence'] = msg['sequence']
                    else:
                        logger.error(f"Failed to replicate missed message {msg['id']} to {secondary_url}")
                        break
                        
            except Exception as e:
                logger.error(f"Error in catch-up replication for {secondary_url}: {e}")
        
        # Run in background
        threading.Thread(target=do_catch_up, daemon=True).start()

    def calculate_retry_delay(self, attempt: int) -> float:
        """Calculate exponential backoff delay with jitter"""
        if attempt <= 0:
            return 0
        
        # Exponential backoff: base_delay * (2 ^ (attempt - 1))
        delay = self.initial_retry_delay * (2 ** (attempt - 1))
        
        # Cap at max delay
        delay = min(delay, self.max_retry_delay)
        
        # Add jitter (±20%)
        jitter = delay * 0.2 * (random.random() - 0.5)
        delay += jitter
        
        return max(0, delay)

    def replicate_single_message_with_retry(self, secondary_url: str, message_entry: Dict, 
                                           max_attempts: Optional[int] = None) -> bool:
        """Replicate a single message to a secondary with retry mechanism"""
        if max_attempts is None:
            max_attempts = self.max_retry_attempts
            
        attempt = 0
        
        while max_attempts < 0 or attempt < max_attempts:
            attempt += 1
            
            try:
                response = requests.post(
                    f"{secondary_url}/replicate",
                    json=message_entry,
                    timeout=self.replication_timeout
                )
                
                if response.status_code == 200:
                    # Update secondary state
                    with self.state_lock:
                        if secondary_url in self.secondary_states:
                            self.secondary_states[secondary_url]['available'] = True
                            self.secondary_states[secondary_url]['last_sequence'] = message_entry['sequence']
                            self.secondary_states[secondary_url]['last_seen'] = datetime.now().isoformat()
                    
                    logger.info(f"Successfully replicated message {message_entry['id']} to {secondary_url} on attempt {attempt}")
                    return True
                else:
                    logger.warning(f"Failed to replicate to {secondary_url} on attempt {attempt}: HTTP {response.status_code}")
                    
            except Exception as e:
                logger.warning(f"Error replicating to {secondary_url} on attempt {attempt}: {e}")
                
                # Mark as unavailable on connection errors
                with self.state_lock:
                    if secondary_url in self.secondary_states:
                        self.secondary_states[secondary_url]['available'] = False
            
            # Calculate and wait for retry delay (except on last attempt)
            if max_attempts < 0 or attempt < max_attempts:
                delay = self.calculate_retry_delay(attempt)
                if delay > 0:
                    logger.info(f"Retrying {secondary_url} in {delay:.2f}s (attempt {attempt})")
                    time.sleep(delay)
        
        logger.error(f"Failed to replicate message {message_entry['id']} to {secondary_url} after {attempt} attempts")
        return False

    def replicate_to_secondaries_with_concern(self, message_entry: Dict, write_concern: int) -> bool:
        """Enhanced replication with retry mechanism and blocking until write concern is met"""
        if write_concern == 0:
            return True
        
        if not self.secondaries:
            logger.warning("No secondaries available for replication")
            return False
        
        logger.info(f"Starting replication with write concern {write_concern}, available secondaries: {len(self.secondaries)}")
        
        # Track replication futures and their status
        futures_to_secondary: Dict[Future, str] = {}
        successful_replications = 0
        
        # Start replication to all secondaries with retry
        for secondary_url in self.secondaries:
            future = self.executor.submit(
                self.replicate_single_message_with_retry, 
                secondary_url, 
                message_entry,
                max_attempts=self.max_retry_attempts if self.max_retry_attempts > 0 else 10  # Limit for initial replication
            )
            futures_to_secondary[future] = secondary_url
        
        # Wait for write concern to be satisfied
        try:
            # Use a longer timeout for retry mechanism
            timeout = self.replication_timeout * 3  # Allow more time for retries
            
            for future in as_completed(futures_to_secondary, timeout=timeout):
                secondary_url = futures_to_secondary[future]
                try:
                    success = future.result()
                    if success:
                        successful_replications += 1
                        logger.info(f"ACK received from {secondary_url} ({successful_replications}/{write_concern} needed)")
                        
                        if successful_replications >= write_concern:
                            logger.info("Write concern satisfied")
                            return True
                except Exception as e:
                    logger.error(f"Future error for {secondary_url}: {e}")
                    
        except Exception as e:
            logger.error(f"Error waiting for replication completion: {e}")
        
        # If write concern not met, continue retrying in background for remaining secondaries
        if successful_replications < write_concern:
            remaining_futures = [f for f in futures_to_secondary.keys() if not f.done()]
            if remaining_futures:
                logger.info(f"Continuing retries for {len(remaining_futures)} secondaries in background")
                
                def background_retry():
                    for future in remaining_futures:
                        secondary_url = futures_to_secondary[future]
                        try:
                            # Continue retrying with unlimited attempts
                            self.replicate_single_message_with_retry(
                                secondary_url, 
                                message_entry, 
                                max_attempts=-1  # Unlimited retries in background
                            )
                        except Exception as e:
                            logger.error(f"Background retry error for {secondary_url}: {e}")
                
                threading.Thread(target=background_retry, daemon=True).start()
        
        logger.warning(f"Write concern not satisfied immediately, got {successful_replications}/{write_concern} ACKs")
        return successful_replications >= write_concern
        
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