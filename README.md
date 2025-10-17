# Replicated Log System - Progressive Implementation

This project implements a replicated log system through multiple iterations, starting with a simple echo server and progressing to a full distributed system with blocking replication.

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
4. **Failure Testing**: Can simulate secondary failures by stopping containers

### Logging and Monitoring

- **Structured Logging**: All components use consistent log formats
- **Health Endpoints**: Allow monitoring of system state
- **Performance Metrics**: Log replication timing and success rates
- **Debug Information**: Detailed logs for troubleshooting

## Future Iterations (Planned)

- **Iteration 2**: Add write-concern parameters
- **Iteration 3**: Implement retry mechanism, deduplication, ordering, heartbeats and quorum

## Contributing

When adding new iterations:

1. Create a new `iteration_N` directory
2. Follow the established project structure
3. Include comprehensive README and Docker support
4. Update this main README with the new iteration