[CmdletBinding()]
param(
    [int]$WaitSeconds = 180,
    [switch]$NoDockerStart,
    [string]$LogDir = (Join-Path $env:TEMP "agentmemory")
)

$ErrorActionPreference = "Stop"

$HealthUrl = "http://localhost:3111/agentmemory/health"
$ViewerUrl = "http://localhost:3113"

function Test-AgentMemoryUrl {
    param([string]$Url)

    try {
        return Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 5
    } catch {
        return $null
    }
}

function Wait-ForDocker {
    param([int]$Seconds)

    $deadline = (Get-Date).AddSeconds($Seconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-DockerReady) {
            return $true
        }
        Start-Sleep -Seconds 5
    }

    return $false
}

function Test-DockerReady {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        return $false
    }

    docker info *> $null
    return $LASTEXITCODE -eq 0
}

$health = Test-AgentMemoryUrl -Url $HealthUrl
if ($health) {
    Write-Host "agentmemory is already healthy at $HealthUrl"
    Write-Host $health.Content
    exit 0
}

if (-not $NoDockerStart) {
    if (-not (Test-DockerReady)) {
        try {
            Start-Service com.docker.service -ErrorAction Stop
        } catch {
            Write-Warning "Could not start Docker service: $($_.Exception.Message)"
        }

        $dockerDesktop = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
        if (Test-Path $dockerDesktop) {
            Start-Process -FilePath $dockerDesktop -WindowStyle Hidden | Out-Null
        }

        if (-not (Wait-ForDocker -Seconds ([Math]::Min($WaitSeconds, 120)))) {
            Write-Warning "Docker is not ready. Continuing in case native iii-engine is available."
        }
    }
}

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$stdout = Join-Path $LogDir "agentmemory.out.log"
$stderr = Join-Path $LogDir "agentmemory.err.log"

$process = Start-Process -FilePath "npx.cmd" `
    -ArgumentList @("-y", "@agentmemory/agentmemory") `
    -WindowStyle Hidden `
    -PassThru `
    -RedirectStandardOutput $stdout `
    -RedirectStandardError $stderr

Write-Host "Started agentmemory process $($process.Id)"
Write-Host "Logs: $stdout"
Write-Host "Errors: $stderr"

$deadline = (Get-Date).AddSeconds($WaitSeconds)
while ((Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 5
    $health = Test-AgentMemoryUrl -Url $HealthUrl
    if ($health) {
        Write-Host "agentmemory health: $($health.StatusCode)"
        Write-Host $health.Content

        $viewer = Test-AgentMemoryUrl -Url $ViewerUrl
        if ($viewer) {
            Write-Host "agentmemory viewer: $ViewerUrl"
        } else {
            Write-Warning "agentmemory API is healthy, but the viewer did not respond at $ViewerUrl"
        }

        exit 0
    }
}

Write-Error "agentmemory did not become healthy within $WaitSeconds seconds. Check $stdout and $stderr."
