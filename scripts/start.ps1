# Starts the Kanban backend services via Docker.
docker compose up -d --build
Start-Sleep -Seconds 2
$totalAttempts = 15
$attempted = 0
while ($attempted -lt $totalAttempts) {
    $attempted++
    try {
        $response = Invoke-RestMethod -Uri "http://localhost:8000/api/ping" -TimeoutSec 2 -ErrorAction Stop
        if ($response.ping -eq "pong") {
            Write-Host "Backend is up at http://localhost:8000"
            exit 0
        }
    } catch {
        Start-Sleep -Seconds 1
    }
}
Write-Host "Backend did not become healthy in time." -ForegroundColor Red
exit 1