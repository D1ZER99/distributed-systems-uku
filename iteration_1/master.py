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
from datetime import datetime
from flask import Flask, request, jsonify
from typing import List, Dict
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
        self.app = Flask(__name__)
        self.messages: List[Dict] = []
        self.secondaries: List[str] = []
        self.message_lock = threading.Lock()
        
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
        """Handle POST requests to append messages"""
        try:
            data = request.get_json()
            if not data or 'message' not in data:
                return jsonify({"error": "Message is required"}), 400
                
            message_text = data['message']
            timestamp = datetime.now().isoformat()
            
            message_entry = {
                "id": len(self.messages) + 1,
                "message": message_text,
                "timestamp": timestamp
            }
            
            logger.info(f"Received POST request with message: {message_text}")
            
            # First, replicate to all secondaries (blocking)
            replication_success = self.replicate_to_secondaries(message_entry)
            
            if not replication_success:
                logger.error("Failed to replicate to all secondaries")
                return jsonify({"error": "Replication failed"}), 500
                
            # Only add to master's list after successful replication
            with self.message_lock:
                self.messages.append(message_entry)
                
            logger.info(f"Message {message_entry['id']} successfully replicated and stored")
            
            return jsonify({
                "status": "success",
                "message_id": message_entry['id'],
                "replicated_to": len(self.secondaries)
            }), 201
            
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
                "messages": messages_copy,
                "total": len(messages_copy),
                "server_role": "master"
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
            
    def replicate_to_secondaries(self, message_entry: Dict) -> bool:
        """Replicate message to all secondary servers with blocking approach"""
        if not self.secondaries:
            logger.warning("No secondary servers to replicate to")
            return True  # No secondaries means replication is "successful"
            
        logger.info(f"Starting replication to {len(self.secondaries)} secondaries")
        
        # Use threading to send to all secondaries in parallel, but wait for all
        success_count = 0
        threads = []
        results = {}
        
        def replicate_to_secondary(secondary_url: str):
            try:
                response = requests.post(
                    f"{secondary_url}/replicate",
                    json=message_entry,
                    timeout=30  # 30 seconds timeout
                )
                
                if response.status_code == 200:
                    results[secondary_url] = True
                    logger.info(f"Successfully replicated to {secondary_url}")
                else:
                    results[secondary_url] = False
                    logger.error(f"Failed to replicate to {secondary_url}: {response.status_code}")
                    
            except Exception as e:
                results[secondary_url] = False
                logger.error(f"Error replicating to {secondary_url}: {e}")
                
        # Start replication threads
        for secondary_url in self.secondaries:
            thread = threading.Thread(target=replicate_to_secondary, args=(secondary_url,))
            thread.start()
            threads.append(thread)
            
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
            
        # Check results
        success_count = sum(1 for success in results.values() if success)
        
        logger.info(f"Replication completed: {success_count}/{len(self.secondaries)} successful")
        
        # Return True only if ALL secondaries acknowledged
        return success_count == len(self.secondaries)
        
    def run(self, host='0.0.0.0', port=5000):
        """Run the master server"""
        logger.info(f"Starting Master server on {host}:{port}")
        self.app.run(host=host, port=port, debug=False)

if __name__ == "__main__":
    master = MasterServer()
    master.run()