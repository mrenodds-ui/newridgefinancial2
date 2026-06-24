#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "$0")/ai_model_common.sh"

ROOT="$(repo_root)"
PORT="${AI_PORT:-11434}"
HOST="${AI_HOST:-127.0.0.1}"
MODEL_PATH="${AI_MODEL_PATH:-${AI_FRONTEND_MODEL_PATH:-}}"
CONTEXT_SIZE="${AI_FRONTEND_CONTEXT_SIZE:-${AI_CONTEXT_SIZE:-4096}}"
RUNTIME="${AI_RUNTIME:-ollama}"
GPU_BACKEND="${AI_GPU_BACKEND:-vulkan}"

print_vram_guidance "frontend" "${AI_FRONTEND_QUANT:-Q4_K_M}"

if [[ "$RUNTIME" == "ollama" ]]; then
  require_cmd ollama
  export OLLAMA_HOST="${HOST}:${PORT}"
  if [[ -n "$MODEL_PATH" && -f "$MODEL_PATH" ]]; then
    TAG="${AI_FRONTEND_MODEL:-frontend-24b-q4}"
    MODEFILE="$(mktemp)"
    cat >"$MODEFILE" <<EOF
FROM $MODEL_PATH
PARAMETER num_ctx $CONTEXT_SIZE
EOF
    ollama create "$TAG" -f "$MODEFILE"
    rm -f "$MODEFILE"
    echo "Created Ollama model tag: $TAG on $OLLAMA_HOST"
  fi
  echo "Starting Ollama (Vulkan on Windows AMD) at http://${HOST}:${PORT}"
  echo "Pull or use: ollama pull mistral-small3.1:24b"
  exec ollama serve
fi

if [[ "$RUNTIME" == "llama_cpp" || "$RUNTIME" == "llama-cpp" ]]; then
  if [[ -z "$MODEL_PATH" || ! -f "$MODEL_PATH" ]]; then
    echo "ERROR: set AI_MODEL_PATH or AI_FRONTEND_MODEL_PATH to a quantized GGUF file." >&2
    exit 1
  fi
  SERVER_BIN="$(resolve_llama_server_bin)"
  GPU_LAYERS="${AI_GPU_LAYERS:-99}"
  if [[ "${GPU_LAYERS,,}" == "auto" || "${GPU_LAYERS,,}" == "cpu" ]]; then
    GPU_LAYERS=99
  fi
  echo "Starting llama.cpp server (${GPU_BACKEND}) at http://${HOST}:${PORT}/v1"
  exec "$SERVER_BIN" \
    -m "$MODEL_PATH" \
    --host "$HOST" \
    --port "$PORT" \
    -c "$CONTEXT_SIZE" \
    -ngl "$GPU_LAYERS"
fi

echo "ERROR: unsupported AI_RUNTIME=$RUNTIME (use ollama or llama_cpp)" >&2
exit 1
