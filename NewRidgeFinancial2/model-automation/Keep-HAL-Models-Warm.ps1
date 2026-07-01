[CmdletBinding()]
param(
    [string]$OllamaHost = "http://127.0.0.1:11434",
    [string[]]$Models,
    [int]$KeepAlive = -1,
    [switch]$AllConfigured,
    [switch]$IncludeReasoningLanes,
    [string]$OllamaExe = "C:\Users\mreno\AppData\Local\Programs\Ollama\ollama.exe",
    [switch]$Watch,
    [int]$WatchSeconds = 120
)

$ErrorActionPreference = "Stop"

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptRoot
$modelsConfigPath = Join-Path $projectRoot "site\data\hal-models.json"

function Get-ConfiguredModels {
    param(
        [switch]$All,
        [switch]$IncludeReasoning
    )

    if (-not (Test-Path $modelsConfigPath)) {
        return @("hal-chat:8b")
    }

    $config = Get-Content $modelsConfigPath -Raw | ConvertFrom-Json

    if ($All) {
        # Every configured model. NOTE: these cannot all co-reside on a 16 GB
        # GPU; Ollama will load on demand and evict under memory pressure.
        $available = @($config.readinessDisplay.availableModels)
        if ($available.Count -gt 0) {
            return ($available | Select-Object -Unique)
        }
    }

    # Always-resident default: GPU-pinned chat only unless fastModel is enabled.
    $lane = @()
    if ($config.config.localModel.model -and $config.config.localModel.enabled -ne $false) {
        $lane += $config.config.localModel.model
    }
    if ($config.config.fastModel.enabled -eq $true -and $config.config.fastModel.model) {
        $lane += $config.config.fastModel.model
    }

    if ($IncludeReasoning) {
        # Larger lanes. They will not all co-reside on 16 GB VRAM; pinning them
        # keeps whichever is loaded resident, but expect on-demand swapping.
        $lane += $config.config.reasoningModel.model
        $lane += $config.config.escalationModel.model
    }

    return ($lane | Where-Object { $_ } | Select-Object -Unique)
}

function Test-OllamaUp {
    try {
        Invoke-RestMethod -Uri "$OllamaHost/api/version" -TimeoutSec 5 | Out-Null
        return $true
    } catch {
        return $false
    }
}

function Ensure-OllamaRunning {
    if (Test-OllamaUp) {
        return
    }

    Write-Host "Ollama API not reachable at $OllamaHost. Attempting to start the server..."

    if (Test-Path $OllamaExe) {
        Start-Process -FilePath $OllamaExe -ArgumentList "serve" -WindowStyle Hidden | Out-Null
    } else {
        Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Hidden | Out-Null
    }

    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep -Seconds 1
        if (Test-OllamaUp) {
            Write-Host "Ollama server is up."
            return
        }
    }

    throw "Ollama server did not become reachable at $OllamaHost."
}

function Set-ModelResident {
    param([Parameter(Mandatory = $true)][string]$Model)

    # An empty-prompt generate request loads the model and, with keep_alive = -1,
    # tells Ollama to keep it resident indefinitely (no time-based eviction).
    $body = @{
        model      = $Model
        keep_alive = $KeepAlive
    } | ConvertTo-Json -Compress

    try {
        Invoke-RestMethod -Uri "$OllamaHost/api/generate" -Method Post -Body $body -ContentType "application/json" -TimeoutSec 600 | Out-Null
        Write-Host "Pinned resident (keep_alive=$KeepAlive): $Model"
        return $true
    } catch {
        Write-Warning "Could not pin model '$Model': $($_.Exception.Message)"
        return $false
    }
}

function Invoke-WarmCycle {
    Ensure-OllamaRunning

    $targets = $Models
    if (-not $targets -or $targets.Count -eq 0) {
        $targets = Get-ConfiguredModels -All:$AllConfigured -IncludeReasoning:$IncludeReasoningLanes
    }

    Write-Host ("Keeping {0} model(s) resident: {1}" -f $targets.Count, ($targets -join ", "))

    $ok = 0
    foreach ($model in $targets) {
        if (Set-ModelResident -Model $model) {
            $ok += 1
        }
    }

    Write-Host ("Warm cycle complete. {0}/{1} model(s) resident at {2}." -f $ok, $targets.Count, (Get-Date))

    try {
        $loaded = (Invoke-RestMethod -Uri "$OllamaHost/api/ps" -TimeoutSec 5).models
        if ($loaded) {
            Write-Host "Currently loaded:"
            foreach ($m in $loaded) {
                $expiry = if ($m.expires_at) { $m.expires_at } else { "no expiry" }
                Write-Host ("  - {0} (expires: {1})" -f $m.name, $expiry)
            }
        }
    } catch {
        # /api/ps is informational only.
    }
}

Invoke-WarmCycle

if (-not $Watch) {
    return
}

Write-Host "Watch mode: re-warming every $WatchSeconds second(s). Press Ctrl+C to stop."
while ($true) {
    Start-Sleep -Seconds $WatchSeconds
    try {
        Invoke-WarmCycle
    } catch {
        Write-Warning "Warm cycle failed: $($_.Exception.Message)"
    }
}
