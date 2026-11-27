$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$services = @("auth", "catalog", "inventory", "orders", "payments", "shipping")
# Lab 4: the Analytics service is set up only once its folder exists (Amal creates it).
if (Test-Path (Join-Path $repoRoot "services\analytics\requirements.txt")) {
    $services += "analytics"
}
# Lab 5: the API Gateway (single entry point on 8080).
$services += "api-gateway"
$requiredModules = @{
    auth = @("fastapi", "uvicorn", "pydantic", "bcrypt")
    catalog = @("fastapi", "uvicorn", "pydantic")
    inventory = @("fastapi", "uvicorn", "pydantic", "pytest", "httpx", "grpc", "grpc_tools")
    orders = @("fastapi", "uvicorn", "httpx", "pydantic", "grpc", "grpc_tools", "confluent_kafka")
    payments = @("fastapi", "uvicorn", "httpx", "pydantic", "pika", "confluent_kafka")
    shipping = @("fastapi", "uvicorn", "httpx", "pydantic", "pika", "confluent_kafka")
    analytics = @("fastapi", "uvicorn", "pydantic", "confluent_kafka")
    "api-gateway" = @("fastapi", "uvicorn", "httpx", "user_agents")
}

& py -3.12 --version
if ($LASTEXITCODE -ne 0) {
    throw "Python 3.12 is required. Install it, then rerun this script."
}

foreach ($service in $services) {
    $servicePath = Join-Path $repoRoot "services\$service"
    $requirements = Join-Path $servicePath "requirements.txt"
    $python = Join-Path $servicePath ".venv\Scripts\python.exe"

    if (-not (Test-Path $python)) {
        Write-Host "Creating Python environment for $service..."
        & py -3.12 -m venv --system-site-packages (Join-Path $servicePath ".venv")
        if ($LASTEXITCODE -ne 0) {
            throw "Could not create the virtual environment for $service."
        }
    }

    $venvConfig = Join-Path $servicePath ".venv\pyvenv.cfg"
    $configText = Get-Content -Path $venvConfig -Raw
    if ($configText -match "(?m)^include-system-site-packages\s*=") {
        $configText = [regex]::Replace(
            $configText,
            "(?m)^include-system-site-packages\s*=.*$",
            "include-system-site-packages = true"
        )
    } else {
        $configText += "`ninclude-system-site-packages = true`n"
    }
    Set-Content -Path $venvConfig -Value $configText -NoNewline

    $moduleArgs = $requiredModules[$service]
    $missingModules = & $python -c "import importlib.util,sys; missing=[name for name in sys.argv[1:] if importlib.util.find_spec(name) is None]; print(','.join(missing))" @moduleArgs
    if ($missingModules) {
        Write-Host "Installing missing dependencies for ${service}: $missingModules"
        & $python -m pip install --disable-pip-version-check --timeout 120 --retries 5 -r $requirements
        if ($LASTEXITCODE -ne 0) {
            throw "Dependency installation failed for $service. Check internet access and retry."
        }

        $missingModules = & $python -c "import importlib.util,sys; missing=[name for name in sys.argv[1:] if importlib.util.find_spec(name) is None]; print(','.join(missing))" @moduleArgs
        if ($missingModules) {
            throw "Required modules are still missing for ${service}: $missingModules"
        }
    } else {
        Write-Host "Using already available dependencies for $service."
    }
}

Write-Host "All service environments are ready: $($services -join ', ')."
