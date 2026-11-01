#!/usr/bin/env bash
# Starts ttyd: a browser terminal guarded by HTTP basic auth.
#   WEB_USER / WEB_PASS  login for the web page (password is generated if unset)
#   PORT                 terminal port (default 7681)
#   FILES_PORT           file manager port (default 7682)
#   FILES_ENABLED        set to 0 to turn the file manager off
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

export WEB_USER WEB_PASS

# File manager (upload/download) runs as the login user, on its own port.
if [ "${FILES_ENABLED:-1}" = "1" ]; then
  FILES_ROOT="/home/${CLOUDMAN_USER}" FILES_PORT="${FILES_PORT:-7682}" \
    runuser -u "${CLOUDMAN_USER}" -- python3 /opt/cloudman/files/server.py &
fi

# enableZmodem: `sz file` in the terminal downloads to the browser, `rz` uploads.
exec ttyd \
  --port "${PORT:-7681}" \
  --writable \
  --credential "${WEB_USER}:${WEB_PASS}" \
  --terminal-type xterm-256color \
  -t enableZmodem=true \
  -t titleFixed="cloudman" \
  -t fontSize=15 \
  -t 'theme={"background":"#0d1117","foreground":"#e6edf3","cursor":"#58a6ff"}' \
  su - "${CLOUDMAN_USER}"
