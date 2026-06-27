[CmdletBinding()]
param(
    [switch]$Help,

    [string]$ModelPath = $env:AI_MODEL_PATH,
    [int]$Port = $(if ($env:AI_PORT) { [int]$env:AI_PORT } else { 11434 }),
    [string]$HostName = $(if ($env:AI_HOST) { $env:AI_HOST } else { '127.0.0.1' })
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '_local_model_defaults.ps1')

if ($Help) {
    Write-Host @'
run_frontend_model.ps1 - start the frontend Ollama or llama.cpp lane on :11434.

Default model tag: qwen3:14b
Override with AI_FRONTEND_MODEL or OLLAMA_FRONTEND_MODEL.
Optional custom GGUF tag via AI_FRONTEND_MODEL_PATH / AI_MODEL_PATH when creating from a local file.
'@
    exit 0
}

$runtime = if ($env:AI_RUNTIME) { $env:AI_RUNTIME } else { 'ollama' }
$contextSize = if ($env:AI_FRONTEND_CONTEXT_SIZE) { $env:AI_FRONTEND_CONTEXT_SIZE } elseif ($env:AI_CONTEXT_SIZE) { $env:AI_CONTEXT_SIZE } else { '4096' }
$defaultModelTag = Get-LocalFrontendModelName

if (-not $ModelPath) { $ModelPath = $env:AI_FRONTEND_MODEL_PATH }

Write-Host 'Local-only: keep weights under models/ or .local_models/ (gitignored). Never commit GGUF or checkpoint files.'
Write-Host 'VRAM: frontend 14B Q4_K_M - keep context at 3072 on 16GB AMD; use Vulkan Ollama on Windows.'
Write-Host "Default frontend model tag: $defaultModelTag"
Write-Host 'This script runs in the foreground. Keep this terminal open; stopping it shuts down the frontend lane on this port.'
Write-Host 'Health check: curl http://127.0.0.1:11434/v1/models'

if ($runtime -eq 'ollama') {
    if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
        throw 'ollama is required but was not found on PATH.'
    }
    $env:OLLAMA_HOST = "${HostName}:$Port"
    if ($ModelPath -and (Test-Path $ModelPath)) {
        $tag = $defaultModelTag
        $modelfile = "FROM $ModelPath`nPARAMETER num_ctx $contextSize"
        $temp = New-TemporaryFile
        Set-Content -Path $temp.FullName -Value $modelfile -Encoding UTF8
        ollama create $tag -f $temp.FullName
        Remove-Item $temp.FullName -Force
        Write-Host "Created Ollama model tag: $tag on $($env:OLLAMA_HOST)"
    }
    Write-Host "Starting Ollama frontend lane at http://${HostName}:$Port"
    ollama serve
    exit $LASTEXITCODE
}

if ($runtime -in @('llama_cpp', 'llama-cpp')) {
    if (-not $ModelPath -or -not (Test-Path $ModelPath)) {
        throw 'Set AI_MODEL_PATH or AI_FRONTEND_MODEL_PATH to a quantized GGUF file.'
    }
    $server = Get-Command llama-server -ErrorAction SilentlyContinue
    if (-not $server) { $server = Get-Command server -ErrorAction SilentlyContinue }
    if (-not $server) { throw 'llama-server not found on PATH.' }
    $gpuLayers = if ($env:AI_GPU_LAYERS -and $env:AI_GPU_LAYERS -ne 'auto' -and $env:AI_GPU_LAYERS -ne 'cpu') { $env:AI_GPU_LAYERS } else { 99 }
    & $server.Source -m $ModelPath --host $HostName --port $Port -c $contextSize -ngl $gpuLayers
    exit $LASTEXITCODE
}

throw "Unsupported AI_RUNTIME=$runtime"
