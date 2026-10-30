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

"$PY_CMD" -m sovereign_mesh start
