# Echo Client-Server Application (Iteration 0)

This is a simple Echo Client-Server application implemented in Python.

## Features

- **Echo Server**: Listens for client connections and echoes back received messages with timestamps
- **Echo Client**: Connects to the server and can send messages in interactive or single-message mode
- **Logging**: Comprehensive logging for both client and server
- **Docker Support**: Both client and server can run in Docker containers
- **Multi-client Support**: Server can handle multiple concurrent clients

## Files

- `echo_server.py` - Echo server implementation
- `echo_client.py` - Echo client implementation
- `Dockerfile.server` - Docker configuration for the server
- `Dockerfile.client` - Docker configuration for the client
- `docker-compose.yml` - Docker Compose configuration for easy deployment

## Usage

### Local Development

1. **Start the server:**
   ```bash
   python echo_server.py
   ```

2. **Run the client (interactive mode):**
   ```bash
   python echo_client.py
   ```

3. **Run the client (single message):**
   ```bash
   python echo_client.py localhost 8080 "Hello World"
   ```

### Docker Deployment

1. **Build and run with Docker Compose:**
   ```bash
   docker-compose up --build
   ```

2. **To interact with the client:**
   ```bash
   docker exec -it echo-client python echo_client.py echo-server 8080
   ```

3. **Test with curl (server only):**
   ```bash
   # This won't work as expected since the server expects socket connections
   # but you can telnet to test
   telnet localhost 8080
   ```

## Architecture

```
Client(s) <---> Echo Server
    |              |
    |              |
[Socket Conn] [Multi-threaded]
```

The server uses threading to handle multiple concurrent client connections, making it scalable for multiple clients.