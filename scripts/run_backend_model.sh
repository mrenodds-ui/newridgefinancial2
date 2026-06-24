#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "$0")/ai_model_common.sh"

ROOT="$(repo_root)"
PORT="${AI_PORT:-11435}"
HOST="${AI_HOST:-127.0.0.1}"
MODEL_PATH="${AI_MODEL_PATH:-${AI_BACKEND_MODEL_PATH:-}}"
CONTEXT_SIZE="${AI_BACKEND_CONTEXT_SIZE:-${AI_CONTEXT_SIZE:-4096}}"
RUNTIME="${AI_RUNTIME:-ollama}"
GPU_BACKEND="${AI_GPU_BACKEND:-vulkan}"

print_local_only_notice
print_vram_guidance "backend" "${AI_BACKEND_QUANT:-Q4_K_S}"

if [[ "$RUNTIME" == "ollama" ]]; then
  require_cmd ollama
  export OLLAMA_HOST="${HOST}:${PORT}"
  if [[ -n "$MODEL_PATH" && -f "$MODEL_PATH" ]]; then
    TAG="${AI_BACKEND_MODEL:-backend-30b-q4}"
    MODEFILE="$(mktemp)"
    cat >"$MODEFILE" <<EOF
FROM $MODEL_PATH
PARAMETER num_ctx $CONTEXT_SIZE
PARAMETER num_gpu 0
EOF
    ollama create "$TAG" -f "$MODEFILE"
    rm -f "$MODEFILE"
    echo "Created Ollama model tag: $TAG on $OLLAMA_HOST"
  fi
  echo "Starting Ollama backend lane at http://${HOST}:${PORT}"
  echo "Pull or use: ollama pull qwen3:30b"
  exec ollama serve
fi

if [[ "$RUNTIME" == "llama_cpp" || "$RUNTIME" == "llama-cpp" ]]; then
  if [[ -z "$MODEL_PATH" || ! -f "$MODEL_PATH" ]]; then
    echo "ERROR: set AI_MODEL_PATH or AI_BACKEND_MODEL_PATH to a quantized GGUF file." >&2
    exit 1
  fi
  SERVER_BIN="$(resolve_llama_server_bin)"
  GPU_LAYERS="${AI_GPU_LAYERS:-0}"
  if [[ "${GPU_LAYERS,,}" == "auto" ]]; then
    GPU_LAYERS=0
  fi
  echo "Starting llama.cpp server (${GPU_BACKEND}) at http://${HOST}:${PORT}/v1 (GPU layers=${GPU_LAYERS})"
  exec "$SERVER_BIN" \
    -m "$MODEL_PATH" \
    --host "$HOST" \
    --port "$PORT" \
    -c "$CONTEXT_SIZE" \
    -ngl "$GPU_LAYERS"
fi

echo "ERROR: unsupported AI_RUNTIME=$RUNTIME (use ollama or llama_cpp)" >&2
exit 1
