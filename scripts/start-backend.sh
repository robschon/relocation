#!/bin/zsh
set -euo pipefail
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
cd $HOME/Code/relocation
export UV_CACHE_DIR=.uv-cache

existing_pids=(${${(@f)"$(lsof -tiTCP:8000 -sTCP:LISTEN 2>/dev/null || true)"}:#})
if (( ${#existing_pids[@]} > 0 )); then
  echo "Stopping existing backend on port 8000: ${existing_pids[*]}"
  kill "${existing_pids[@]}"

  for _ in {1..20}; do
    if ! lsof -tiTCP:8000 -sTCP:LISTEN >/dev/null 2>&1; then
      break
    fi
    sleep 0.2
  done
fi

exec $HOME/.local/bin/uv run uvicorn relocation.api.app:app --host 127.0.0.1 --port 8000
