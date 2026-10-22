#!/bin/zsh
set -euo pipefail
export PATH="/opt/homebrew/bin:$HOME/.local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
cd "${0:A:h}/../frontend"
exec /opt/homebrew/bin/npm run dev -- --host 0.0.0.0 --port 5173
