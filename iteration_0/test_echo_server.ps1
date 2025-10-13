# PowerShell script to test the echo server
# Save as test_echo_server.ps1

param(
    [string]$ServerHost = "localhost",
    [int]$ServerPort = 8080,
    [string]$Message = "Hello from PowerShell!"
)

Write-Host "Testing Echo Server at $ServerHost`:$ServerPort" -ForegroundColor Green
Write-Host "Message: $Message" -ForegroundColor Yellow

try {
    # Create TCP client
    $tcpClient = New-Object System.Net.Sockets.TcpClient
    $tcpClient.Connect($ServerHost, $ServerPort)
    
    # Get network stream
    $stream = $tcpClient.GetStream()
    
    # Send message
    $messageBytes = [System.Text.Encoding]::UTF8.GetBytes($Message)
    $stream.Write($messageBytes, 0, $messageBytes.Length)
    
    Write-Host "Message sent successfully!" -ForegroundColor Green
    
    # Read response
    $buffer = New-Object byte[] 1024
    $bytesRead = $stream.Read($buffer, 0, 1024)
    $response = [System.Text.Encoding]::UTF8.GetString($buffer, 0, $bytesRead)
    
    Write-Host "Server Response: $response" -ForegroundColor Cyan
    
    # Clean up
    $stream.Close()
    $tcpClient.Close()
    
    Write-Host "✓ Echo server is working correctly!" -ForegroundColor Green
}
catch {
    Write-Host "✗ Failed to connect to echo server: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Make sure the server is running on $ServerHost`:$ServerPort" -ForegroundColor Yellow
}