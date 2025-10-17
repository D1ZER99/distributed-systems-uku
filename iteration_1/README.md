# Replicated Log System (Iteration 1)

This is a replicated log system with one Master and multiple Secondary servers, implementing blocking replication with acknowledgments.

## Architecture

```
Client --> Master --> Secondary-1
            |
            --> Secondary-2
```

- **Master**: Handles POST/GET requests, replicates to secondaries with blocking approach
- **Secondaries**: Handle replication requests from master and serve GET requests with configurable delay
- **Blocking Replication**: Master waits for ACKs from ALL secondaries before completing POST request

## Features

- **HTTP REST API** for all interactions
- **Blocking replication** - POST completes only after all secondaries acknowledge
- **Parallel replication** - Master contacts all secondaries simultaneously using threading
- **Configurable delays** on secondaries to test blocking behavior
- **Comprehensive logging** across all components
- **Docker containerization** for easy deployment
- **Health checks** and monitoring endpoints
- **Multiple secondary support** with different configurations

## API Endpoints

### Master Server (Port 5000)

- `POST /messages` - Add a new message (replicates to all secondaries)
- `GET /messages` - Get all messages from master
- `GET /health` - Health check
- `POST /secondaries` - Register a secondary server

### Secondary Servers (Ports 5001, 5002)

- `GET /messages` - Get all replicated messages
- `POST /replicate` - Internal endpoint for master to replicate messages
- `GET /health` - Health check with server info

## Files

- `master.py` - Master server implementation (Flask + requests + threading)
- `secondary.py` - Secondary server implementation  
- `test_client.py` - Test client for demonstration
- `requirements.txt` - Python dependencies (Flask, requests)
- `Dockerfile.master` - Docker configuration for master
- `Dockerfile.secondary` - Docker configuration for secondaries
- `docker-compose.yml` - Complete system deployment

## Usage

### Docker Deployment (Recommended)

1. **Start the entire system:**
   ```bash
   docker-compose up --build
   ```

2. **Test the system:**
   ```bash
   # Run comprehensive demo
   python test_client.py demo
   
   # Post a single message
   python test_client.py post "Hello World"
   
   # Get messages from master
   python test_client.py get
   
   # Get messages from secondary
   python test_client.py get http://localhost:5001
   ```

3. **Manual testing with curl:**
   ```bash
   # Health checks
   curl http://localhost:5000/health
   curl http://localhost:5001/health
   curl http://localhost:5002/health
   
   # Post a message (notice the delay due to replication)
   curl -X POST http://localhost:5000/messages \
        -H "Content-Type: application/json" \
        -d '{"message": "Test message"}'
   
   # Get messages from master
   curl http://localhost:5000/messages
   
   # Get messages from secondaries
   curl http://localhost:5001/messages
   curl http://localhost:5002/messages
   ```

### Local Development

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Start servers manually:**
   ```bash
   # Terminal 1 - Master
   python master.py
   
   # Terminal 2 - Secondary 1
   SERVER_ID=secondary-1 SECONDARY_PORT=5001 REPLICATION_DELAY=2.0 python secondary.py
   
   # Terminal 3 - Secondary 2  
   SERVER_ID=secondary-2 SECONDARY_PORT=5002 REPLICATION_DELAY=1.5 python secondary.py
   ```

3. **Configure master to know about secondaries:**
   ```bash
   export SECONDARIES="http://localhost:5001,http://localhost:5002"
   python master.py
   ```

## Configuration

### Environment Variables

**Master:**
- `SECONDARIES` - Comma-separated list of secondary URLs

**Secondary:**
- `SERVER_ID` - Unique identifier for the secondary
- `SECONDARY_PORT` - Port to run on (default: 5001)
- `SECONDARY_HOST` - Hostname for registration (default: localhost)
- `REPLICATION_DELAY` - Artificial delay in seconds (default: 2.0)
- `MASTER_URL` - Master URL for registration

## Implementation Details

### � **Synchronous Architecture with Parallel Replication**

The implementation uses **synchronous programming** with **threading for parallel replication**:

```python
# Threading-based parallel replication
def replicate_to_secondaries(self, message_entry):
    threads = []
    for secondary_url in self.secondaries:
        thread = threading.Thread(target=replicate_to_secondary, args=(secondary_url,))
        thread.start()  # Start all threads simultaneously
        threads.append(thread)
    
    # Wait for all threads to complete
    for thread in threads:
        thread.join()  # Block until all replication completes
```

### ⚡ **Performance Characteristics**

| Approach | Time Complexity | Blocking Behavior | Complexity |
|----------|-----------------|-------------------|------------|
| **Sequential Replication** | O(sum of delays) | Blocks per secondary | Simple |
| **Parallel Replication (Current)** | O(max delay) | Blocks until all complete | Moderate |
| **Async Implementation** | O(max delay) | Non-blocking event loop | Complex |

### 🎯 **Why Synchronous Programming?**

**Benefits for learning:**
- ✅ **Easier to understand** - Linear execution flow
- ✅ **Simpler debugging** - Stack traces are clear
- ✅ **Fewer edge cases** - No async/await gotchas
- ✅ **Standard libraries** - Works with regular requests, Flask
- ✅ **Good performance** - Threading provides parallelism where needed

**Threading provides the benefits we need:**
- ✅ **Parallel replication** - All secondaries contacted simultaneously
- ✅ **Optimal timing** - Total delay = max(secondary delays)
- ✅ **Strong consistency** - Waits for all ACKs before success

## Testing Blocking Replication

The system includes configurable delays on secondary servers to demonstrate blocking replication:

1. **Secondary-1**: 2.0 second delay
2. **Secondary-2**: 1.5 second delay

When you POST a message, the master will wait for both secondaries to acknowledge before responding. You'll notice the delay in the POST response time.

## Logs

Each component generates detailed logs:

- `master.log` - Master server logs
- `secondary.log` - Secondary server logs (one per secondary)
- Console output with timestamps and log levels

## Monitoring

- Health check endpoints show server status and message counts
- Logs provide detailed replication timing and success/failure information
- Test client provides comprehensive system demonstration

## Architecture Details

1. **Message Flow:**
   - Client sends POST to Master
   - Master validates message and assigns ID
   - Master sends message to ALL secondaries in parallel
   - Master waits for ACK from ALL secondaries
   - Only after all ACKs, Master stores message and responds to client

2. **Fault Tolerance:**
   - If ANY secondary fails to acknowledge, the entire POST fails
   - This ensures strong consistency across all replicas
   - Perfect link assumption means no message loss or corruption

3. **Performance:**
   - Parallel replication to secondaries for better performance
   - Blocking approach ensures consistency over availability
   - Configurable delays allow testing of different scenarios