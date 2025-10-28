# Replicated Log System - Progressive Implementation

This project implements a replicated log system through multiple iterations,2. **HTTP over Sockets**: HTTP provides better interoperability and easier testing
3. **Blocking vs. Semi-Synchronous Replication**: 
   - Iteration 1: Full blocking replication ensures strong consistency
   - Iteration 2: Tunable write concern allows consistency vs. performance trade-offs
4. **Message Deduplication**: SHA256 hashing prevents duplicate message processing
5. **Total Ordering**: Sequence numbers guarantee consistent message ordering across replicas
6. **Background Replication**: w=1 enables immediate responses with asynchronous replication
7. **Docker Containerization**: Enables easy deployment and scaling across iterationsting with a simple echo server and progressing to a full distributed system with blocking replication.

## Project Structure

```
docker_project/
├── iteration_0/          # Simple Echo Client-Server
│   ├── echo_server.py    # Echo server implementation
│   ├── echo_client.py    # Echo client implementation
│   ├── Dockerfile.server # Docker config for server
│   ├── Dockerfile.client # Docker config for client
│   ├── docker-compose.yml
│   └── README.md
│
├── iteration_1/          # Replicated Log System
│   ├── master.py         # Master server (handles POST/GET)
│   ├── secondary.py      # Secondary server (replication target)
│   ├── test_client.py    # Test client for demonstration
│   ├── requirements.txt  # Python dependencies
│   ├── Dockerfile.master # Docker config for master
│   ├── Dockerfile.secondary # Docker config for secondaries
│   ├── docker-compose.yml
│   └── README.md
│
├── iteration_2/          # Advanced Replicated Log with Write Concern
│   ├── master.py         # Master with tunable write concern
│   ├── secondary.py      # Secondary with ordering & deduplication
│   ├── test_client.py    # Comprehensive test suite
│   ├── requirements.txt  # Python dependencies
│   ├── Dockerfile.master # Docker config for master
│   ├── Dockerfile.secondary # Docker config for secondaries
│   ├── docker-compose.yml
│   └── README.md
│
└── README.md            # This file
```

## Iterations Overview

### Iteration 0: Echo Client-Server Application

A foundational implementation demonstrating:
- **Socket-based communication** between client and server
- **Multi-threaded server** handling concurrent clients
- **Basic logging** and error handling
- **Docker containerization** for both components

**Key Features:**
- Server echoes received messages with timestamps
- Client supports both interactive and single-message modes
- Comprehensive logging for debugging
- Docker Compose for easy deployment

### Iteration 1: Replicated Log System

A distributed system implementing:
- **Master-Secondary architecture** with blocking replication
- **HTTP REST API** for client interactions
- **Synchronous replication** with acknowledgments
- **Configurable delays** for testing blocking behavior

**Key Features:**
- Master handles POST (append) and GET (retrieve) operations
- Secondaries replicate messages and serve GET requests
- Blocking replication ensures all secondaries acknowledge before POST completes
- Artificial delays demonstrate the blocking nature
- Perfect link assumption (no failures or message loss)

### Iteration 2: Advanced Replicated Log with Write Concern

A sophisticated distributed system implementing:
- **Tunable write concern** for semi-synchronous replication
- **Message deduplication** using SHA256 hashing
- **Total ordering** with sequence numbers
- **Concurrent request processing** with background replication
- **Comprehensive testing suite** with acceptance tests

**Key Features:**
- **Write Concern (w=1,2,3,..,n)**: Client controls consistency vs. performance trade-offs
  - `w=1`: Master only (fastest, background replication to secondaries)
  - `w=2`: Master + 1 secondary (balanced approach)
  - `w=3`: Master + all secondaries (strongest consistency)
- **Message Deduplication**: SHA256-based duplicate prevention
- **Total Ordering**: Sequence numbers ensure consistent message order across replicas
- **Background Replication**: w=1 requests return immediately while replicating asynchronously
- **Concurrent Processing**: Multiple requests processed simultaneously without blocking
- **Acceptance Testing**: Professor-specified test scenarios with artificial delays
- **Stress Testing**: Concurrent request handling and ordering verification

## Quick Start

### Running Iteration 0 (Echo System)

```bash
cd iteration_0
docker-compose up --build

# In another terminal, interact with the client
docker exec -it echo-client python echo_client.py echo-server 8080
```

### Running Iteration 1 (Replicated Log)

```bash
cd iteration_1
docker-compose up --build

# In another terminal, run the demo
python test_client.py demo

# Or test manually
curl -X POST http://localhost:5000/messages \
     -H "Content-Type: application/json" \
     -d '{"message": "Hello replicated world!"}'

curl http://localhost:5000/messages
curl http://localhost:5001/messages
curl http://localhost:5002/messages
```

## System Requirements

- **Docker** and Docker Compose
- **Python 3.9+** (for local development)
- **Network access** between containers

## Development Notes

### Design Decisions

1. **HTTP over Sockets**: Iteration 1 uses HTTP for better interoperability and easier testing
2. **Blocking Replication**: Ensures strong consistency at the cost of availability
3. **Storage via Docker Volumes**: Simplifies implementation while demonstrating core concepts
4. **Configurable Delays**: Allow testing of different replication scenarios
5. **Docker Containerization**: Enables easy deployment and scaling

### Testing Strategy

1. **Unit Testing**: Each component can be tested independently
2. **Integration Testing**: Docker Compose provides full system testing
3. **Performance Testing**: Configurable delays allow testing of various scenarios
4. **Consistency Testing**: Write concern parameters enable testing different consistency levels
5. **Concurrent Testing**: Multiple simultaneous requests test threading and ordering
6. **Acceptance Testing**: Professor-specified scenarios validate distributed systems behavior
7. **Stress Testing**: High-volume concurrent requests test system robustness

### Logging and Monitoring

- **Structured Logging**: All components use consistent log formats
- **Health Endpoints**: Allow monitoring of system state
- **Performance Metrics**: Log replication timing and success rates
- **Debug Information**: Detailed logs for troubleshooting

## Future Iterations (Planned)

- **Iteration 3**: Advanced fault tolerance with leader election
- **Iteration 4**: Implement Byzantine fault tolerance
- **Iteration 5**: Add persistent storage and recovery mechanisms

## Performance Characteristics

### Iteration Comparison

| Feature | Iteration 0 | Iteration 1 | Iteration 2 |
|---------|-------------|-------------|-------------|
| **Consistency** | N/A | Strong | Tunable (w=1,2,3) |
| **Performance** | High | Lower (blocking) | Configurable |
| **Fault Tolerance** | None | Basic | Enhanced |
| **Ordering** | N/A | Arrival order | Total ordering |
| **Deduplication** | N/A | None | SHA256-based |
| **Concurrency** | Basic | Sequential | Full concurrent |
| **Testing** | Manual | Basic | Comprehensive |

### Write Concern Performance (Iteration 2)

- **w=1**: ~10ms response time (immediate + background replication)
- **w=2**: ~2s response time (wait for Secondary-1)
- **w=3**: ~10s response time (wait for Secondary-2)

*Times based on configured artificial delays for demonstration purposes.*

## Key Achievements (Iteration 2)

### Distributed Systems Concepts Implemented

- ✅ **Tunable Consistency**: Write concern parameters (w=1,2,3) allow trading consistency for performance
- ✅ **Message Deduplication**: SHA256-based duplicate detection prevents message replay
- ✅ **Total Ordering**: Sequence numbers ensure consistent message ordering across all replicas
- ✅ **Concurrent Processing**: Background replication and threading enable simultaneous request handling
- ✅ **Semi-Synchronous Replication**: Combines benefits of synchronous and asynchronous approaches
- ✅ **Fault Tolerance**: Graceful handling of secondary failures with partial success responses
- ✅ **Professor's Acceptance Tests**: Meets all specified academic requirements for distributed systems

### Technical Excellence

- **Thread-Safe Operations**: Proper locking and concurrent data structure usage
- **Comprehensive Logging**: Detailed tracing for debugging and monitoring
- **Error Handling**: Robust error recovery and graceful degradation
- **Testing Coverage**: Unit tests, integration tests, stress tests, and acceptance tests
- **Docker Integration**: Production-ready containerization with health checks
- **API Design**: RESTful endpoints with proper HTTP status codes and error responses

## Contributing

When adding new iterations:

1. Create a new `iteration_N` directory
2. Follow the established project structure
3. Include comprehensive README and Docker support
4. Update this main README with the new iteration