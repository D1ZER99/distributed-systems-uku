# Test script for Iteration 1 - Replicated Log System (PowerShell)
# This script demonstrates the blocking replication behavior

Write-Host "=== Replicated Log System Test ===" -ForegroundColor Green
Write-Host ""

# Function to check if a service is healthy
function Test-ServiceHealth {
    param($ServiceName, $Url)
    
    Write-Host "Checking $ServiceName health... " -NoNewline
    
    try {
        $response = Invoke-RestMethod -Uri "$Url/health" -Method Get -TimeoutSec 5
        Write-Host "✓ Healthy" -ForegroundColor Green
        return $true
    }
    catch {
        Write-Host "✗ Not responding" -ForegroundColor Red
        return $false
    }
}

# Function to post a message and measure time
function Post-Message {
    param($Message)
    
    Write-Host "Posting message: '$Message'"
    Write-Host "Time taken: " -NoNewline
    
    $startTime = Get-Date
    
    try {
        $body = @{ message = $Message } | ConvertTo-Json
        $response = Invoke-RestMethod -Uri "http://localhost:5000/messages" -Method Post -Body $body -ContentType "application/json" -TimeoutSec 60
        
        $endTime = Get-Date
        $duration = ($endTime - $startTime).TotalSeconds
        
        Write-Host "$([math]::Round($duration, 2)) seconds"
        Write-Host "✓ Message posted successfully" -ForegroundColor Green
    }
    catch {
        $endTime = Get-Date
        $duration = ($endTime - $startTime).TotalSeconds
        Write-Host "$([math]::Round($duration, 2)) seconds"
        Write-Host "✗ Failed to post message: $($_.Exception.Message)" -ForegroundColor Red
    }
    Write-Host ""
}

# Function to get message count from a server
function Get-MessageCount {
    param($ServerName, $Url)
    
    try {
        $response = Invoke-RestMethod -Uri "$Url/messages" -Method Get -TimeoutSec 10
        Write-Host "$ServerName`: $($response.total) messages"
    }
    catch {
        Write-Host "$ServerName`: Unable to retrieve count" -ForegroundColor Yellow
    }
}

Write-Host "1. Health Checks" -ForegroundColor Cyan
Write-Host "=================="
Test-ServiceHealth "Master" "http://localhost:5000"
Test-ServiceHealth "Secondary-1" "http://localhost:5001"
Test-ServiceHealth "Secondary-2" "http://localhost:5002"
Write-Host ""

Write-Host "2. Initial Message Counts" -ForegroundColor Cyan
Write-Host "========================="
Get-MessageCount "Master" "http://localhost:5000"
Get-MessageCount "Secondary-1" "http://localhost:5001"
Get-MessageCount "Secondary-2" "http://localhost:5002"
Write-Host ""

Write-Host "3. Testing Blocking Replication" -ForegroundColor Cyan
Write-Host "==============================="
Write-Host "Note: Each POST should take ~2+ seconds due to secondary delays" -ForegroundColor Yellow
Write-Host ""

Post-Message "First test message"
Post-Message "Second test message"
Post-Message "Third test message"

Write-Host "4. Final Message Counts" -ForegroundColor Cyan
Write-Host "======================="
Get-MessageCount "Master" "http://localhost:5000"
Get-MessageCount "Secondary-1" "http://localhost:5001"
Get-MessageCount "Secondary-2" "http://localhost:5002"
Write-Host ""

Write-Host "5. Sample Messages from Master" -ForegroundColor Cyan
Write-Host "=============================="
try {
    $response = Invoke-RestMethod -Uri "http://localhost:5000/messages" -Method Get
    $response.messages | Select-Object -First 5 | ForEach-Object {
        Write-Host "[$($_.id)] $($_.message) ($($_.timestamp))"
    }
}
catch {
    Write-Host "Unable to retrieve messages" -ForegroundColor Red
}
Write-Host ""

Write-Host "=== Test Complete ===" -ForegroundColor Green