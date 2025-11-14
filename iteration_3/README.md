# Replicated Log System (Iteration 2)

This is a replicated log system with one Master and multiple Secondary servers, implementing **tunable write concern** for semi-synchronous replication.

## Architecture

```
Client --> Master --> Secondary-1
            |
            --> Secondary-2
```

- **Master**: Handles POST/GET requests, replicates to secondaries with configurable write concern
- **Secondaries**: Handle replication requests from master and serve GET requests with configurable delay
- **Write Concern**: Client specifies how many replicas (w=1,2,3,..,n) must acknowledge before POST completes
- **Semi-Synchronous**: Allows tunable consistency vs. performance trade-offs

## Key Features - Iteration 2

- **Tunable Write Concern (w parameter)**: Client controls how many replicas must acknowledge (*regardless of write concern value chosen messages will be replicated to all the nodes*):
  - `w=1`: Master only (fastest, lowest consistency)
  - `w=2`: Master + 1 secondary (balanced)
  - `w=3`: Master + all secondaries (highest consistency, slower)
- **Partial Success Handling**: Different HTTP status codes based on replication success
- **Flexible Consistency**: Supports both fast writes and strong consistency depending on use case
- **Backward Compatibility**: Default write concern ensures full replication like iteration 1

## Features

- **HTTP REST API** with write concern parameter
- **Tunable replication** - Client specifies required acknowledgment count
- **Parallel replication** - Master contacts all secondaries simultaneously using threading
- **Configurable delays** on secondaries to test different consistency scenarios
- **Comprehensive logging** across all components
- **Docker containerization** for easy deployment
- **Health checks** and monitoring endpoints
- **Message deduplication** and total ordering guarantees

## API Endpoints

### Master Server (Port 5000)

- `POST /messages` - Add a new message with optional write concern parameter
  - Body: `{"message": "text", "w": 2}` (w parameter optional, defaults to full replication)
  - Returns HTTP 201 if sufficient replicas acknowledge
  - Returns HTTP 202 if fewer replicas acknowledge than requested
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

## Testing Blocking Replication

### Write Concern Examples

```bash
# Fast write - only master needs to store (w=1)
curl -X POST http://localhost:5000/messages \
  -H "Content-Type: application/json" \
  -d '{"message": "Fast message", "w": 1}'

# Balanced consistency - master + 1 secondary (w=2)  
curl -X POST http://localhost:5000/messages \
  -H "Content-Type: application/json" \
  -d '{"message": "Balanced message", "w": 2}'

# Strong consistency - all replicas (w=3)
curl -X POST http://localhost:5000/messages \
  -H "Content-Type: application/json" \
  -d '{"message": "Consistent message", "w": 3}'
```

### Test Client Usage

```bash
# Basic write concern demonstration
python test_client.py write_concern

# Post with specific write concern
python test_client.py post "Hello World" -w 2

# Regular demo (backward compatibility)
python test_client.py demo

# Self-check acceptance check
python test_client.py acceptance

# Parallel processing (client with wc=1 right after client wc=3 is not waiting for client wc=3 request to end)
python test_client.py concur
```

## Performance vs. Consistency Trade-offs

The system includes configurable delays on secondary servers to demonstrate different consistency scenarios:

1. **Secondary-1**: 2.0 second delay
2. **Secondary-2**: 1.5 second delay

Write concern allows you to choose your trade-off:

- **w=1**: ~0ms delay (instant response after master write)
- **w=2**: ~1.5s delay (wait for fastest secondary)  
- **w=3**: ~10.0s delay (wait for slowest secondary)

## Consistency Scenarios

### Eventual Consistency (w=1)
- Client gets immediate response after master write
- Secondaries receive updates asynchronously
- Temporary inconsistency possible between replicas
- Best performance, eventual consistency

### Strong Consistency (w=3)
- Client waits for all replicas to acknowledge
- All replicas guaranteed to have the message
- Higher latency but immediate consistency
- Traditional blocking replication behavior

### Balanced Approach (w=2)
- Client waits for majority of replicas
- Good balance between performance and consistency
- Most practical for real-world applications

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

2. **Message Flow with Write Concern:**
   - Client sends POST to Master with write concern parameter (w)
   - Master validates message, assigns ID, and stores in local log
   - Master sends message to ALL secondaries in parallel
   - Master waits for ACKs from (w-1) secondaries (since master counts as 1)
   - Master responds to client when enough ACKs received or timeout occurs
   - Message replicated to all the nodes regardless of write concern parameter

3. **Fault Tolerance:**
   - If insufficient secondaries acknowledge, POST returns 202 (partial success)
   - Master always stores the message regardless of secondary failures
   - Write concern allows trading consistency for availability
   - Message deduplication prevents duplicate processing

4. **Performance:**
   - Parallel replication to secondaries for better performance
   - Tunable consistency allows optimization for different use cases
   - Lower write concern values provide better performance
   - Higher write concern values provide stronger consistency guarantees