#!/bin/zsh
set -euo pipefail
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
cd $HOME/Code/relocation
export UV_CACHE_DIR=.uv-cache
exec $HOME/.local/bin/uv run uvicorn relocation.api.app:app --host 127.0.0.1 --port 8000
