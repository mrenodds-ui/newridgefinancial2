[CmdletBinding()]
param(
    [string]$ConfigPath = (Join-Path $PSScriptRoot 'litellm_ollama_router.yaml'),
    [string]$OllamaFrontendBaseUrl = '',
    [string]$OllamaBackendBaseUrl = ''
)

$resolvedConfigPath = (Resolve-Path $ConfigPath).Path

if ([string]::IsNullOrWhiteSpace($OllamaFrontendBaseUrl)) {
    if ([string]::IsNullOrWhiteSpace($env:OLLAMA_FRONTEND_BASE_URL)) {
        if ([string]::IsNullOrWhiteSpace($env:AI_FRONTEND_BASE_URL)) {
            if ([string]::IsNullOrWhiteSpace($env:OLLAMA_BASE_URL)) {
                $env:OLLAMA_FRONTEND_BASE_URL = 'http://127.0.0.1:11434'
            } else {
                $env:OLLAMA_FRONTEND_BASE_URL = $env:OLLAMA_BASE_URL
            }
        } else {
            $env:OLLAMA_FRONTEND_BASE_URL = $env:AI_FRONTEND_BASE_URL
        }
    }
} else {
    $env:OLLAMA_FRONTEND_BASE_URL = $OllamaFrontendBaseUrl
}

if ([string]::IsNullOrWhiteSpace($env:OLLAMA_BASE_URL)) {
    $env:OLLAMA_BASE_URL = $env:OLLAMA_FRONTEND_BASE_URL
}

if ([string]::IsNullOrWhiteSpace($OllamaBackendBaseUrl)) {
    if ([string]::IsNullOrWhiteSpace($env:OLLAMA_BACKEND_BASE_URL)) {
        if ([string]::IsNullOrWhiteSpace($env:AI_BACKEND_BASE_URL)) {
            $env:OLLAMA_BACKEND_BASE_URL = 'http://127.0.0.1:11435'
        } else {
            $env:OLLAMA_BACKEND_BASE_URL = $env:AI_BACKEND_BASE_URL
        }
    }
} else {
    $env:OLLAMA_BACKEND_BASE_URL = $OllamaBackendBaseUrl
}

Write-Host "Starting LiteLLM proxy with config: $resolvedConfigPath"
Write-Host "Using frontend Ollama base URL: $($env:OLLAMA_FRONTEND_BASE_URL)"
Write-Host "Using backend Ollama base URL: $($env:OLLAMA_BACKEND_BASE_URL)"
Write-Host "OpenAI-compatible endpoint will be available on http://127.0.0.1:4000 by default."

if ([string]::IsNullOrWhiteSpace($env:LITELLM_MASTER_KEY)) {
    Write-Warning @"
LITELLM_MASTER_KEY is not set. This is acceptable for localhost-only development.
Set LITELLM_MASTER_KEY before exposing the proxy to other hosts or shared networks.
Do not run an unauthenticated LiteLLM proxy outside 127.0.0.1.
"@
}

uv tool run --from "litellm[proxy]" litellm --config $resolvedConfigPath
