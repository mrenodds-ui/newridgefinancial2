#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "$0")/ai_model_common.sh"

SOURCE_PATH="${1:-}"
QUANT_TYPE="${2:-Q4_K_S}"
ROOT="$(repo_root)"
OUT_DIR="${MODEL_OUTPUT_DIR:-$ROOT/.local_models/backend}"
FALLBACK_QUANTS=("Q3_K_M" "Q3_K_S")

if [[ -z "$SOURCE_PATH" ]]; then
  echo "Usage: $0 /path/to/source-30b-model [Q4_K_S]" >&2
  exit 1
fi
if [[ ! -e "$SOURCE_PATH" ]]; then
  echo "ERROR: source model path does not exist: $SOURCE_PATH" >&2
  exit 1
fi

QUANT_BIN="$(resolve_llama_quantize_bin)"
mkdir -p "$OUT_DIR"

BASENAME="$(basename "$SOURCE_PATH")"
STEM="${BASENAME%.*}"
F16_GGUF="$OUT_DIR/${STEM}.f16.gguf"
OUT_GGUF="$OUT_DIR/backend-30b.${QUANT_TYPE}.gguf"

if [[ "$SOURCE_PATH" != *.gguf ]]; then
  if ! command -v python >/dev/null 2>&1; then
    echo "ERROR: python is required to convert HuggingFace checkpoints to GGUF." >&2
    exit 1
  fi
  if [[ ! -f "$ROOT/scripts/convert_hf_to_gguf.py" ]]; then
    echo "ERROR: missing scripts/convert_hf_to_gguf.py — copy from upstream llama.cpp or pass an existing .gguf file." >&2
    exit 1
  fi
  echo "Converting HuggingFace checkpoint to F16 GGUF..."
  python "$ROOT/scripts/convert_hf_to_gguf.py" "$SOURCE_PATH" --outfile "$F16_GGUF" --outtype f16
  SOURCE_GGUF="$F16_GGUF"
else
  SOURCE_GGUF="$SOURCE_PATH"
fi

print_vram_guidance "backend" "$QUANT_TYPE"
echo "Quantizing to $OUT_GGUF ..."
if ! "$QUANT_BIN" "$SOURCE_GGUF" "$OUT_GGUF" "$QUANT_TYPE"; then
  for fallback in "${FALLBACK_QUANTS[@]}"; do
    if [[ "$fallback" == "$QUANT_TYPE" ]]; then
      continue
    fi
    echo "WARN: $QUANT_TYPE failed; trying fallback $fallback ..."
    OUT_GGUF="$OUT_DIR/backend-30b.${fallback}.gguf"
    "$QUANT_BIN" "$SOURCE_GGUF" "$OUT_GGUF" "$fallback"
    QUANT_TYPE="$fallback"
    break
  done
fi

echo "Done. Set in .env:"
echo "  AI_BACKEND_MODEL_PATH=$OUT_GGUF"
echo "  AI_BACKEND_QUANT=$QUANT_TYPE"
echo "  AI_RUNTIME=llama_cpp"
