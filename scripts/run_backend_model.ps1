[CmdletBinding()]
param(
    [switch]$Help,

    [string]$ModelPath = $env:AI_MODEL_PATH,
    [int]$Port = $(if ($env:AI_PORT) { [int]$env:AI_PORT } else { 11435 }),
    [string]$HostName = $(if ($env:AI_HOST) { $env:AI_HOST } else { '127.0.0.1' })
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '_local_model_defaults.ps1')

if ($Help) {
    Write-Host @'
run_backend_model.ps1 - start the backend Ollama or llama.cpp lane on :11435.

Default model tag: qwen3:14b
Override with AI_BACKEND_MODEL or OLLAMA_BACKEND_MODEL.
Optional custom GGUF tag via AI_BACKEND_MODEL_PATH / AI_MODEL_PATH when creating from a local file.
'@
    exit 0
}

$runtime = if ($env:AI_RUNTIME) { $env:AI_RUNTIME } else { 'ollama' }
$contextSize = if ($env:AI_BACKEND_CONTEXT_SIZE) { $env:AI_BACKEND_CONTEXT_SIZE } elseif ($env:AI_CONTEXT_SIZE) { $env:AI_CONTEXT_SIZE } else { '4096' }
$defaultModelTag = Get-LocalBackendModelName

if (-not $ModelPath) { $ModelPath = $env:AI_BACKEND_MODEL_PATH }

Write-Host 'Local-only: keep weights under models/ or .local_models/ (gitignored). Never commit GGUF or checkpoint files.'
Write-Host 'VRAM: backend 14B Q4_K_M - keep CPU/RAM on :11435 so the frontend GPU lane stays responsive.'
Write-Host "Default backend model tag: $defaultModelTag"
Write-Host 'This script runs in the foreground. Keep this terminal open; stopping it shuts down the backend lane on this port.'
Write-Host 'Health check: curl http://127.0.0.1:11435/v1/models'

if ($runtime -eq 'ollama') {
    if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
        throw 'ollama is required but was not found on PATH.'
    }
    $env:OLLAMA_HOST = "${HostName}:$Port"
    if ($ModelPath -and (Test-Path $ModelPath)) {
        $tag = $defaultModelTag
        $modelfile = "FROM $ModelPath`nPARAMETER num_ctx $contextSize`nPARAMETER num_gpu 0"
        $temp = New-TemporaryFile
        Set-Content -Path $temp.FullName -Value $modelfile -Encoding UTF8
        ollama create $tag -f $temp.FullName
        Remove-Item $temp.FullName -Force
        Write-Host "Created Ollama model tag: $tag on $($env:OLLAMA_HOST)"
    }
    Write-Host "Starting Ollama backend lane at http://${HostName}:$Port"
    ollama serve
    exit $LASTEXITCODE
}

if ($runtime -in @('llama_cpp', 'llama-cpp')) {
    if (-not $ModelPath -or -not (Test-Path $ModelPath)) {
        throw 'Set AI_MODEL_PATH or AI_BACKEND_MODEL_PATH to a quantized GGUF file.'
    }
    $server = Get-Command llama-server -ErrorAction SilentlyContinue
    if (-not $server) { $server = Get-Command server -ErrorAction SilentlyContinue }
    if (-not $server) { throw 'llama-server not found on PATH.' }
    $gpuLayers = if ($env:AI_GPU_LAYERS -and $env:AI_GPU_LAYERS -notin @('auto', 'cpu')) { $env:AI_GPU_LAYERS } else { 0 }
    & $server.Source -m $ModelPath --host $HostName --port $Port -c $contextSize -ngl $gpuLayers
    exit $LASTEXITCODE
}

throw "Unsupported AI_RUNTIME=$runtime"
