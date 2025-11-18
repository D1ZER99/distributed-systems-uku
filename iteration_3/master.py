#!/usr/bin/env python3
"""
Master Server - Iteration 1
A master server for the replicated log system that handles POST/GET requests
and replicates messages to secondary servers with blocking replication.
"""

import logging
import time
import threading
import requests
import hashlib
import atexit
from datetime import datetime
from flask import Flask, request, jsonify
from typing import List, Dict
import os
from queue import Queue

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


class SecondaryReplicationWorker:
    """Background worker that guarantees ordered delivery with retries."""

    def __init__(
        self,
        secondary_url: str,
        request_timeout: float,
        ack_callback,
        initial_retry_delay: float,
        max_retry_delay: float,
        is_healthy_fn=None,
        wait_for_healthy_fn=None,
    ):
        self.secondary_url = secondary_url
        self.request_timeout = request_timeout
        self.ack_callback = ack_callback
        self.initial_retry_delay = max(initial_retry_delay, 0.1)
        self.max_retry_delay = max(max_retry_delay, self.initial_retry_delay)

        # Health awareness supplied by MasterServer
        self.is_healthy_fn = is_healthy_fn
        self.wait_for_healthy_fn = wait_for_healthy_fn

        self.queue: Queue = Queue()
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.session = requests.Session()
        self.thread.start()

    def enqueue_message(self, message_entry: Dict):
        """Add message to the per-secondary queue preserving order."""
        self.queue.put(message_entry)

    def stop(self):
        """Stop worker gracefully."""
        self.stop_event.set()
        self.queue.put(None)
        self.thread.join(timeout=5)

    def _run(self):
        while not self.stop_event.is_set():
            message_entry = self.queue.get()
            if message_entry is None:
                break
            try:
                self._deliver_with_retry(message_entry)
            finally:
                self.queue.task_done()

    def _deliver_with_retry(self, message_entry: Dict):
        delay = self.initial_retry_delay
        while not self.stop_event.is_set():
            # If master says this secondary is not healthy, wait until it becomes healthy again
            if self.is_healthy_fn is not None:
                try:
                    if not self.is_healthy_fn():
                        logger.info("Secondary %s not healthy; pausing retries", self.secondary_url)
                        if self.wait_for_healthy_fn is not None:
                            self.wait_for_healthy_fn(self.stop_event)
                        else:
                            # Fallback: simple sleep-based wait
                            if self.stop_event.wait(self.initial_retry_delay):
                                return
                        # After waiting, start loop again to re-check health
                        continue
                except Exception as exc:
                    logger.error("Health check for %s failed: %s", self.secondary_url, exc)

            try:
                response = self.session.post(
                    f"{self.secondary_url}/replicate",
                    json=message_entry,
                    timeout=self.request_timeout,
                )
                if response.status_code == 200:
                    logger.info(
                        "Replication to %s succeeded for message %s",
                        self.secondary_url,
                        message_entry["id"],
                    )
                    self.ack_callback(self.secondary_url, message_entry["id"])
                    return
                else:
                    logger.error(
                        "Secondary %s responded with %s for message %s",
                        self.secondary_url,
                        response.status_code,
                        message_entry["id"],
                    )
            except Exception as exc:
                logger.error(
                    "Error replicating to %s for message %s: %s",
                    self.secondary_url,
                    message_entry["id"],
                    exc,
                )

            logger.info(
                "Scheduling retry for secondary %s in %.2fs",
                self.secondary_url,
                delay,
            )
            if self.stop_event.wait(delay):
                return
            delay = min(delay * 2, self.max_retry_delay)

class MasterServer:
    def __init__(self):
        print("MASTER SERVER V2 - NO DEDUPLICATION")  # Debug marker
        self.app = Flask(__name__)
        self.messages: List[Dict] = []
        self.secondaries: List[str] = []
        self.message_lock = threading.Lock()
        self.secondary_lock = threading.Lock()
        
        # Separate ID counter with its own lock
        self.next_id = 1
        self.counter_lock = threading.Lock()
        
        # Ack tracking for tunable semi-synchronous replication
        self.message_ack_tracker: Dict[int, set] = {}
        self.ack_condition = threading.Condition()
        self.replication_managers: Dict[str, SecondaryReplicationWorker] = {}

        # Heartbeat / health tracking for secondaries
        self.secondary_health: Dict[str, Dict] = {}
        self.health_condition = threading.Condition()
        self.heartbeat_threads: Dict[str, threading.Thread] = {}
        self.heartbeat_stop_event = threading.Event()

        # Tunable retry/backoff controls
        self.initial_retry_delay = float(os.environ.get('RETRY_DELAY_INITIAL', '1.0'))
        self.max_retry_delay = float(os.environ.get('RETRY_DELAY_MAX', '10.0'))
        self.secondary_request_timeout = float(os.environ.get('SECONDARY_REQUEST_TIMEOUT', '10.0'))
        self.write_concern_timeout = float(os.environ.get('WRITE_CONCERN_TIMEOUT_SECONDS', '0'))

        # Heartbeat configuration
        self.heartbeat_interval = float(os.environ.get('HEARTBEAT_INTERVAL_SECONDS', '3.0'))
        self.heartbeat_timeout = float(os.environ.get('HEARTBEAT_TIMEOUT_SECONDS', '2.0'))
        self.heartbeat_unhealthy_threshold = int(os.environ.get('HEARTBEAT_UNHEALTHY_THRESHOLD', '3'))
        
        # Setup routes
        self.setup_routes()
        
        # Load secondary servers from environment
        self.load_secondaries()
        self.initialize_replication_managers()
        self.initialize_heartbeat_monitors()
        
        # Register shutdown handler
        atexit.register(self.shutdown)
        
    def shutdown(self):
        """Shutdown replication managers and heartbeat threads gracefully"""
        logger.info("Shutting down replication managers")
        for manager in list(self.replication_managers.values()):
            try:
                manager.stop()
            except Exception as exc:
                logger.error(f"Error shutting down manager for {manager.secondary_url}: {exc}")

        logger.info("Shutting down heartbeat monitors")
        self.heartbeat_stop_event.set()
        for url, thread in list(self.heartbeat_threads.items()):
            try:
                thread.join(timeout=2)
            except Exception as exc:
                logger.error(f"Error joining heartbeat thread for {url}: {exc}")
        
    def load_secondaries(self):
        """Load secondary server URLs from environment variables"""
        secondaries_env = os.environ.get('SECONDARIES', '')
        if secondaries_env:
            self.secondaries = [url.strip() for url in secondaries_env.split(',') if url.strip()]
            logger.info(f"Loaded {len(self.secondaries)} secondary servers: {self.secondaries}")
        else:
            logger.warning("No secondary servers configured")

    def initialize_replication_managers(self):
        """Start replication managers for all known secondaries."""
        with self.secondary_lock:
            for secondary_url in self.secondaries:
                self._ensure_replication_manager(secondary_url)

    def _ensure_replication_manager(self, secondary_url: str):
        """Create a replication manager for the given secondary if missing."""
        if secondary_url in self.replication_managers:
            return

        manager = SecondaryReplicationWorker(
            secondary_url=secondary_url,
            request_timeout=self.secondary_request_timeout,
            ack_callback=self.handle_secondary_ack,
            initial_retry_delay=self.initial_retry_delay,
            max_retry_delay=self.max_retry_delay,
            is_healthy_fn=lambda url=secondary_url: self.is_secondary_healthy(url),
            wait_for_healthy_fn=lambda stop_event, url=secondary_url: self.wait_for_secondary_healthy(url, stop_event),
        )

        with self.message_lock:
            backlog = list(self.messages)

        for message in backlog:
            manager.enqueue_message(message)

        self.replication_managers[secondary_url] = manager
        logger.info(f"Started replication manager for {secondary_url} with backlog of {len(backlog)} messages")

    def initialize_heartbeat_monitors(self):
        """Start heartbeat monitors for all known secondaries."""
        with self.secondary_lock:
            for secondary_url in self.secondaries:
                self._ensure_heartbeat_monitor(secondary_url)

    def _ensure_heartbeat_monitor(self, secondary_url: str):
        """Create a heartbeat monitor for the given secondary if missing."""
        if secondary_url in self.heartbeat_threads:
            return

        thread = threading.Thread(
            target=self._heartbeat_loop,
            args=(secondary_url,),
            daemon=True,
        )
        self.heartbeat_threads[secondary_url] = thread
        thread.start()
        logger.info(f"Started heartbeat monitor for {secondary_url}")

    def _heartbeat_loop(self, secondary_url: str):
        """Background loop that periodically checks secondary health."""
        while not self.heartbeat_stop_event.is_set():
            is_healthy = False
            try:
                resp = requests.get(
                    f"{secondary_url}/health",
                    timeout=self.heartbeat_timeout,
                )
                if resp.status_code == 200:
                    is_healthy = True
            except Exception as exc:
                logger.warning("Heartbeat to %s failed: %s", secondary_url, exc)

            now_iso = datetime.now().isoformat()
            with self.health_condition:
                info = self.secondary_health.setdefault(
                    secondary_url,
                    {"status": "Healthy", "last_heartbeat": None, "failure_count": 0},
                )
                prev_status = info["status"]

                if is_healthy:
                    info["failure_count"] = 0
                    info["last_heartbeat"] = now_iso
                    info["status"] = "Healthy"
                else:
                    info["failure_count"] += 1
                    info["last_heartbeat"] = now_iso
                    if info["failure_count"] >= self.heartbeat_unhealthy_threshold:
                        info["status"] = "Unhealthy"
                    else:
                        info["status"] = "Suspected"

                if info["status"] != prev_status:
                    logger.info(
                        "Secondary %s status changed from %s to %s",
                        secondary_url,
                        prev_status,
                        info["status"],
                    )
                    self.health_condition.notify_all()

            # Sleep until next heartbeat or stop requested
            if self.heartbeat_stop_event.wait(self.heartbeat_interval):
                break

    def is_secondary_healthy(self, secondary_url: str) -> bool:
        """Return True if secondary is considered healthy."""
        with self.health_condition:
            info = self.secondary_health.get(secondary_url)
            # If we have no info yet, optimistically assume healthy
            if not info:
                return True
            return info.get("status") == "Healthy"

    def wait_for_secondary_healthy(self, secondary_url: str, stop_event: threading.Event):
        """Block until secondary becomes healthy again or stop_event is set."""
        with self.health_condition:
            while not stop_event.is_set():
                info = self.secondary_health.get(secondary_url)
                if not info or info.get("status") == "Healthy":
                    return
                # Wait until next health change or heartbeat tick
                self.health_condition.wait(timeout=self.heartbeat_interval)
            
    def setup_routes(self):
        """Setup Flask routes"""
        
        @self.app.route('/health', methods=['GET'])
        def health():
            # Expose per-secondary heartbeat status
            with self.secondary_lock:
                secondary_urls = list(self.secondaries)

            with self.health_condition:
                secondaries_status = []
                for url in secondary_urls:
                    info = self.secondary_health.get(
                        url,
                        {"status": "Unknown", "last_heartbeat": None, "failure_count": 0},
                    )
                    secondaries_status.append({
                        "url": url,
                        "status": info.get("status", "Unknown"),
                        "last_heartbeat": info.get("last_heartbeat"),
                        "failure_count": info.get("failure_count", 0),
                    })

            return jsonify({
                "status": "healthy",
                "role": "master",
                "secondaries": secondaries_status,
            }), 200
            
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
            self.replicate_to_all_secondaries(message_entry)

            if write_concern <= 0:
                logger.info("Write concern satisfied by master only (w=1)")
                return jsonify({
                    "id": message_id,
                    "message": message_text
                }), 201

            # Track ACKs for this message
            self.initialize_ack_tracking(message_id)

            wait_timeout = self._get_wait_timeout(data)
            success = self.wait_for_write_concern(message_id, write_concern, wait_timeout)
            self.cleanup_ack_tracking(message_id)

            if success:
                logger.info(f"Message {message_entry['id']} successfully replicated with required write concern")
                return jsonify({
                    "id": message_id,
                    "message": message_text
                }), 201
            else:
                logger.warning(f"Message {message_entry['id']} did not meet required write concern before timeout")
                return jsonify({
                    "id": message_id,
                    "message": message_text,
                    "warning": "Required write concern not met before timeout"
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
            with self.secondary_lock:
                if secondary_url not in self.secondaries:
                    self.secondaries.append(secondary_url)
                    logger.info(f"Registered new secondary: {secondary_url}")
                    self._ensure_replication_manager(secondary_url)
                    self._ensure_heartbeat_monitor(secondary_url)
                else:
                    logger.info(f"Secondary {secondary_url} already registered")
                
            return jsonify({"status": "registered", "total_secondaries": len(self.secondaries)}), 200
            
        except Exception as e:
            logger.error(f"Error registering secondary: {e}")
            return jsonify({"error": "Internal server error"}), 500
    
    def replicate_to_all_secondaries(self, message_entry: Dict):
        """Fan-out message to every secondary regardless of write concern."""
        with self.secondary_lock:
            managers = list(self.replication_managers.values())

        if not managers:
            logger.info("No replication managers available; nothing to fan-out")
            return

        for manager in managers:
            manager.enqueue_message(message_entry)
        logger.info(f"Queued message {message_entry['id']} for replication to {len(managers)} secondaries")

    def initialize_ack_tracking(self, message_id: int):
        """Prepare tracking structure for a new message awaiting ACKs."""
        with self.ack_condition:
            self.message_ack_tracker[message_id] = set()

    def cleanup_ack_tracking(self, message_id: int):
        """Remove tracking once all waiters are done."""
        with self.ack_condition:
            self.message_ack_tracker.pop(message_id, None)

    def _get_wait_timeout(self, request_payload: Dict) -> float:
        """Determine wait timeout from payload or global config."""
        client_timeout_ms = request_payload.get('timeout_ms')
        if client_timeout_ms is not None:
            try:
                client_timeout = max(float(client_timeout_ms) / 1000.0, 0.0)
                return client_timeout if client_timeout > 0 else None
            except (TypeError, ValueError):
                logger.warning("Invalid timeout_ms value provided; ignoring")

        if self.write_concern_timeout > 0:
            return self.write_concern_timeout
        return None

    def wait_for_write_concern(self, message_id: int, required_acks: int, timeout: float = None) -> bool:
        """Block until required ACKs received or timeout expires."""
        if required_acks <= 0:
            return True

        deadline = time.time() + timeout if timeout else None

        with self.ack_condition:
            while True:
                acked = len(self.message_ack_tracker.get(message_id, set()))
                if acked >= required_acks:
                    return True

                if deadline is not None:
                    remaining = deadline - time.time()
                    if remaining <= 0:
                        return False
                    self.ack_condition.wait(timeout=remaining)
                else:
                    self.ack_condition.wait()

    def handle_secondary_ack(self, secondary_url: str, message_id: int):
        """Record acknowledgements coming from replication workers."""
        with self.ack_condition:
            acked_set = self.message_ack_tracker.get(message_id)
            if acked_set is None:
                return

            if secondary_url in acked_set:
                return

            acked_set.add(secondary_url)
            logger.info(
                "ACK recorded for message %s from %s (%s/%s)",
                message_id,
                secondary_url,
                len(acked_set),
                len(self.replication_managers),
            )
            self.ack_condition.notify_all()
        
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