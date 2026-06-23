[CmdletBinding()]
param(
    [string]$ConfigPath = (Join-Path $PSScriptRoot 'litellm_ollama_router.yaml'),
    [string]$OllamaBaseUrl = ''
)

$resolvedConfigPath = (Resolve-Path $ConfigPath).Path
if ([string]::IsNullOrWhiteSpace($OllamaBaseUrl)) {
    if ([string]::IsNullOrWhiteSpace($env:OLLAMA_BASE_URL)) {
        $env:OLLAMA_BASE_URL = 'http://127.0.0.1:11434'
    }
} else {
    $env:OLLAMA_BASE_URL = $OllamaBaseUrl
}

Write-Host "Starting LiteLLM proxy with config: $resolvedConfigPath"
Write-Host "Using Ollama base URL: $($env:OLLAMA_BASE_URL)"
Write-Host "OpenAI-compatible endpoint will be available on http://127.0.0.1:4000 by default."

uv tool run --from "litellm[proxy]" litellm --config $resolvedConfigPath