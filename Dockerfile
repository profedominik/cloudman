# cloudman — a Linux shell you open in your web browser.
# ttyd serves a real terminal (bash) over HTTP/WebSocket, protected by a login,
# and a small file manager (port 7682) handles uploads and downloads.
FROM mcr.microsoft.com/devcontainers/base:ubuntu

ARG USERNAME=cloudman

# Optional build-time proxy CA (only needed in locked-down build environments).
# Passed as a BuildKit secret so it never ends up in the image.
RUN --mount=type=secret,id=proxy_ca,required=false,mode=0444 \
    set -eux; \
    APT_OPTS=""; \
    if [ -s /run/secrets/proxy_ca ]; then APT_OPTS="-o Acquire::https::CAInfo=/run/secrets/proxy_ca"; fi; \
    sed -i 's|http://|https://|g' /etc/apt/sources.list.d/*.sources /etc/apt/sources.list 2>/dev/null || true; \
    apt-get $APT_OPTS update; \
    DEBIAN_FRONTEND=noninteractive apt-get $APT_OPTS install -y --no-install-recommends \
        ttyd tini python3 lrzsz htop nano vim tmux iputils-ping net-tools openssh-client rsync unzip; \
    rm -rf /var/lib/apt/lists/*

# Unprivileged login user with passwordless sudo.
RUN useradd -m -s /bin/bash "$USERNAME" \
 && echo "$USERNAME ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/$USERNAME \
 && chmod 0440 /etc/sudoers.d/$USERNAME

COPY files/ /opt/cloudman/files/
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

ENV CLOUDMAN_USER=$USERNAME \
    PORT=7681 \
    FILES_PORT=7682
EXPOSE 7681 7682
WORKDIR /home/$USERNAME

ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/entrypoint.sh"]
