#!/usr/bin/env bash
# Starts ttyd: a browser terminal guarded by HTTP basic auth.
#   WEB_USER / WEB_PASS  login for the web page (password is generated if unset)
#   PORT                 listening port (default 7681)
set -euo pipefail

WEB_USER="${WEB_USER:-admin}"
if [ -z "${WEB_PASS:-}" ]; then
  WEB_PASS="$(head -c 18 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 16)"
  echo "======================================================"
  echo " cloudman: no WEB_PASS set, generated one for you:"
  echo "   user: ${WEB_USER}"
  echo "   pass: ${WEB_PASS}"
  echo "======================================================"
fi

exec ttyd \
  --port "${PORT:-7681}" \
  --writable \
  --credential "${WEB_USER}:${WEB_PASS}" \
  --terminal-type xterm-256color \
  -t titleFixed="cloudman" \
  -t fontSize=15 \
  -t 'theme={"background":"#0d1117","foreground":"#e6edf3","cursor":"#58a6ff"}' \
  su - "${CLOUDMAN_USER}"
