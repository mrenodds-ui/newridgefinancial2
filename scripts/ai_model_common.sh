#!/usr/bin/env bash
set -euo pipefail

repo_root() {
  cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd
}

require_cmd() {
  local name="$1"
  if ! command -v "$name" >/dev/null 2>&1; then
    echo "ERROR: required command not found: $name" >&2
    exit 1
  fi
}

print_local_only_notice() {
  cat <<EOF
Local-only: keep quantized weights under models/ or .local_models/ (gitignored).
Never commit .gguf, .safetensors, .bin, .pth, .pt files, or model caches.
EOF
}

print_vram_guidance() {
  local lane="$1"
  local quant="$2"
  cat <<EOF
VRAM guidance (${lane} lane, ${quant}):
  - RX 9060 XT 16GB: keep context at 4096–8192; KV cache grows quickly above 8192.
  - Frontend 24B Q4_K_M: target full GPU offload on Vulkan/Ollama when only this lane is loaded.
  - Backend 30B Q4_K_S: prefer a separate port (:11435) with num_gpu=0 (CPU/RAM) if both lanes would contend.
  - Use AI_GPU_LAYERS=auto in .env, or set an explicit layer count for partial offload experiments.
EOF
}

resolve_llama_quantize_bin() {
  if command -v llama-quantize >/dev/null 2>&1; then
    command -v llama-quantize
    return 0
  fi
  if command -v llama.cpp-quantize >/dev/null 2>&1; then
    command -v llama.cpp-quantize
    return 0
  fi
  echo "ERROR: llama-quantize (llama.cpp) is required for GGUF quantization." >&2
  echo "Install llama.cpp with Vulkan/HIP support, or use Ollama pull instead." >&2
  exit 1
}

resolve_llama_server_bin() {
  if command -v llama-server >/dev/null 2>&1; then
    command -v llama-server
    return 0
  fi
  if command -v server >/dev/null 2>&1; then
    command -v server
    return 0
  fi
  echo "ERROR: llama-server (llama.cpp) not found." >&2
  echo "Use Ollama (AI_RUNTIME=ollama) or install llama.cpp server binaries." >&2
  exit 1
}

gpu_backend_flags() {
  local backend="${AI_GPU_BACKEND:-vulkan}"
  case "${backend,,}" in
    rocm|hip)
      echo "-ngl ${AI_GPU_LAYERS:-99}"
      ;;
    vulkan|*)
      echo "-ngl ${AI_GPU_LAYERS:-99}"
      ;;
  esac
}
