# Shared local model defaults aligned with app/ai_local_config.py

function Get-LocalFrontendModelName {
    if ($env:AI_FRONTEND_MODEL -and $env:AI_FRONTEND_MODEL.Trim()) {
        return $env:AI_FRONTEND_MODEL.Trim()
    }
    if ($env:OLLAMA_FRONTEND_MODEL -and $env:OLLAMA_FRONTEND_MODEL.Trim()) {
        return $env:OLLAMA_FRONTEND_MODEL.Trim()
    }
    return 'queen3:14b'
}

function Get-LocalBackendModelName {
    if ($env:AI_BACKEND_MODEL -and $env:AI_BACKEND_MODEL.Trim()) {
        return $env:AI_BACKEND_MODEL.Trim()
    }
    if ($env:OLLAMA_BACKEND_MODEL -and $env:OLLAMA_BACKEND_MODEL.Trim()) {
        return $env:OLLAMA_BACKEND_MODEL.Trim()
    }
    return 'queen3:14b'
}
