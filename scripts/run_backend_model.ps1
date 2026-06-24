[CmdletBinding()]
param(
    [string]$ModelPath = $env:AI_MODEL_PATH,
    [int]$Port = $(if ($env:AI_PORT) { [int]$env:AI_PORT } else { 11435 }),
    [string]$HostName = $(if ($env:AI_HOST) { $env:AI_HOST } else { '127.0.0.1' })
)

$ErrorActionPreference = 'Stop'
$runtime = if ($env:AI_RUNTIME) { $env:AI_RUNTIME } else { 'ollama' }
$contextSize = if ($env:AI_BACKEND_CONTEXT_SIZE) { $env:AI_BACKEND_CONTEXT_SIZE } elseif ($env:AI_CONTEXT_SIZE) { $env:AI_CONTEXT_SIZE } else { '4096' }

if (-not $ModelPath) { $ModelPath = $env:AI_BACKEND_MODEL_PATH }

Write-Host 'Local-only: keep weights under models/ or .local_models/ (gitignored). Never commit GGUF or checkpoint files.'
Write-Host 'VRAM: backend 30B Q4_K_S - prefer CPU/RAM or partial offload on :11435 to avoid contending with the 24B frontend lane.'

if ($runtime -eq 'ollama') {
    if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
        throw 'ollama is required but was not found on PATH.'
    }
    $env:OLLAMA_HOST = "${HostName}:$Port"
    if ($ModelPath -and (Test-Path $ModelPath)) {
        $tag = if ($env:AI_BACKEND_MODEL) { $env:AI_BACKEND_MODEL } else { 'backend-30b-q4' }
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
