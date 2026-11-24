param(
    [switch]$Setup
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$logDirectory = Join-Path $repoRoot "logs"
New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null

$services = @(
    @{ Name = "auth"; Port = 8081; Check = "/" },
    @{ Name = "catalog"; Port = 8082; Check = "/products" },
    @{ Name = "inventory"; Port = 8083; Check = "/" },
    @{ Name = "orders"; Port = 8084; Check = "/health" },
    @{ Name = "payments"; Port = 8085; Check = "/health" },
    @{ Name = "shipping"; Port = 8086; Check = "/health" }
)
# Lab 4: the Analytics service is started only once its folder exists (Amal creates it).
if (Test-Path (Join-Path $repoRoot "services\analytics\main.py")) {
    $services += @{ Name = "analytics"; Port = 8087; Check = "/health" }
}

if ($Setup) {
    & (Join-Path $PSScriptRoot "setup-services.ps1")
}

$started = @()
foreach ($service in $services) {
    $servicePath = Join-Path $repoRoot "services\$($service.Name)"
    $python = Join-Path $servicePath ".venv\Scripts\python.exe"
    if (-not (Test-Path $python)) {
        throw "Environment for $($service.Name) is missing. Run .\scripts\setup-services.ps1 first, or use -Setup."
    }

    $alreadyListening = $false
    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $connect = $client.BeginConnect("127.0.0.1", $service.Port, $null, $null)
        $alreadyListening = $connect.AsyncWaitHandle.WaitOne(250) -and $client.Connected
    } finally {
        $client.Dispose()
    }

    if ($alreadyListening) {
        Write-Host "$($service.Name) already has a listener on port $($service.Port); leaving it untouched."
        continue
    }

    $arguments = @(
        "-m", "uvicorn", "main:app",
        "--host", "127.0.0.1",
        "--port", "$($service.Port)"
    )
    $stdoutLog = Join-Path $logDirectory "$($service.Name).out.log"
    $stderrLog = Join-Path $logDirectory "$($service.Name).err.log"
    $process = Start-Process `
        -FilePath $python `
        -ArgumentList $arguments `
        -WorkingDirectory $servicePath `
        -RedirectStandardOutput $stdoutLog `
        -RedirectStandardError $stderrLog `
        -WindowStyle Hidden `
        -PassThru
    $started += $service.Name
    Write-Host "Started $($service.Name) (PID $($process.Id)) on http://127.0.0.1:$($service.Port)"
}

Write-Host "Waiting for APIs to respond..."
foreach ($service in $services) {
    $url = "http://127.0.0.1:$($service.Port)$($service.Check)"
    $ready = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        try {
            Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 2 | Out-Null
            $ready = $true
            break
        } catch {
            Start-Sleep -Seconds 1
        }
    }

    if (-not $ready) {
        throw "$($service.Name) did not respond at $url. Check $stderrLog for its startup error."
    }
    Write-Host "OK  $($service.Name): $url"
}

Write-Host "All service APIs are responding. Open the frontend at http://localhost:5173."
