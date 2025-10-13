#!/bin/bash

# Test script for Iteration 1 - Replicated Log System
# This script demonstrates the blocking replication behavior

echo "=== Replicated Log System Test ==="
echo ""

# Function to check if a service is healthy
check_health() {
    local service_name=$1
    local url=$2
    echo -n "Checking $service_name health... "
    
    if curl -s "$url/health" > /dev/null 2>&1; then
        echo "✓ Healthy"
        return 0
    else
        echo "✗ Not responding"
        return 1
    fi
}

# Function to post a message and measure time
post_message() {
    local message=$1
    echo "Posting message: '$message'"
    echo -n "Time taken: "
    
    start_time=$(date +%s.%N)
    response=$(curl -s -X POST "http://localhost:5000/messages" \
        -H "Content-Type: application/json" \
        -d "{\"message\": \"$message\"}" \
        -w "%{http_code}")
    end_time=$(date +%s.%N)
    
    duration=$(echo "$end_time - $start_time" | bc)
    echo "${duration} seconds"
    
    if [[ "$response" == *"201"* ]]; then
        echo "✓ Message posted successfully"
    else
        echo "✗ Failed to post message"
    fi
    echo ""
}

# Function to get message count from a server
get_message_count() {
    local server_name=$1
    local url=$2
    
    count=$(curl -s "$url/messages" | jq -r '.total' 2>/dev/null)
    if [[ "$count" =~ ^[0-9]+$ ]]; then
        echo "$server_name: $count messages"
    else
        echo "$server_name: Unable to retrieve count"
    fi
}

echo "1. Health Checks"
echo "=================="
check_health "Master" "http://localhost:5000"
check_health "Secondary-1" "http://localhost:5001"
check_health "Secondary-2" "http://localhost:5002"
echo ""

echo "2. Initial Message Counts"
echo "========================="
get_message_count "Master" "http://localhost:5000"
get_message_count "Secondary-1" "http://localhost:5001"
get_message_count "Secondary-2" "http://localhost:5002"
echo ""

echo "3. Testing Blocking Replication"
echo "==============================="
echo "Note: Each POST should take ~2+ seconds due to secondary delays"
echo ""

post_message "First test message"
post_message "Second test message"
post_message "Third test message"

echo "4. Final Message Counts"
echo "======================="
get_message_count "Master" "http://localhost:5000"
get_message_count "Secondary-1" "http://localhost:5001"
get_message_count "Secondary-2" "http://localhost:5002"
echo ""

echo "5. Sample Messages from Master"
echo "=============================="
curl -s "http://localhost:5000/messages" | jq -r '.messages[] | "[\(.id)] \(.message) (\(.timestamp))"' | head -5
echo ""

echo "=== Test Complete ==="