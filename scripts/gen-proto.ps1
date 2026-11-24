# Generates the gRPC Python code from proto/inventory.proto
# into the two services that use it (Inventory = server, Orders = client).
# Run after setup-services.ps1, and again every time the .proto changes.

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$protoDir = Join-Path $repoRoot "proto"
$protoFile = Join-Path $protoDir "inventory.proto"

foreach ($service in @("inventory", "orders")) {
    $servicePath = Join-Path $repoRoot "services\$service"
    $python = Join-Path $servicePath ".venv\Scripts\python.exe"
    if (-not (Test-Path $python)) {
        throw "Environment for $service is missing. Run .\scripts\setup-services.ps1 first."
    }

    & $python -m grpc_tools.protoc `
        "-I$protoDir" `
        "--python_out=$servicePath" `
        "--grpc_python_out=$servicePath" `
        $protoFile
    if ($LASTEXITCODE -ne 0) {
        throw "protoc failed for $service. Is grpcio-tools installed in its .venv?"
    }
    Write-Host "Generated inventory_pb2.py and inventory_pb2_grpc.py in services\$service"
}
