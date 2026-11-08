#!/usr/bin/env bash
cd "$(dirname "$0")" || exit 1
echo "========================================================================"
echo "   SUP AGENTIC MESH (POWERED BY NEXUS) - 1-COMMAND MASTER LAUNCHER"
echo "   [Web Studio + Owner Telegram Bot + IDE + P2P Market + Supercomputer]"
echo "========================================================================"

if command -v python3 &> /dev/null; then
    PY_CMD="python3"
elif command -v python &> /dev/null; then
    PY_CMD="python"
else
    echo "[!] Python 3 is not installed."
    exit 1
fi

echo "[+] Using Python: $PY_CMD"

# Level 1 (Default): Detect & Report GPU/VRAM Only (Never auto-installs or auto-starts training without opt-in)
if command -v nvidia-smi &> /dev/null && nvidia-smi &> /dev/null; then
    GPU_INFO=$(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null | head -n 1)
    echo "[+] GPU Detected: ${GPU_INFO:-NVIDIA CUDA GPU} [Level 1: Detect & Report Only - Pass --gpu-candidate to opt-in]"
    if [ "${1:-}" = "--install-gpu" ]; then
        echo "[!] GPU QLoRA Training Stack (torch, transformers, peft, trl, bitsandbytes) requires ~2.5 GB download."
        read -r -p "Install GPU QLoRA stack from requirements-gpu.txt? (y/n): " CONFIRM_GPU
        if [ "$CONFIRM_GPU" = "y" ] || [ "$CONFIRM_GPU" = "Y" ]; then
            "$PY_CMD" -m pip install -r requirements-gpu.txt
        fi
    elif [ "${1:-}" = "--gpu-candidate" ]; then
        echo "[+] Opt-In Level 2 Enabled: Background Candidate Training (Staged Only - Human Approval Required)"
        export NEXUS_GPU_TRAINING_LEVEL=2
    fi
else
    echo "[*] Standard CPU Mode Detected (1-Click Lightweight Launch - No GPU Required)."
fi

"$PY_CMD" -m sovereign_mesh start
