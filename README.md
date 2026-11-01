# cloudman

A Linux shell in your web browser. One Docker container runs
[ttyd](https://github.com/tsl0922/ttyd), which serves a real `bash` terminal
over HTTP/WebSocket behind a username/password login.

![screenshot](docs/screenshot.png)

## What's inside

- Ubuntu base (`mcr.microsoft.com/devcontainers/base:ubuntu`) with git, curl, zsh
- ttyd, tmux, htop, vim, nano, ssh client, rsync, ping
- Login user `cloudman` with passwordless `sudo`
- Home directory on a Docker volume, so files survive restarts

## Run it

With Docker Compose:

```bash
WEB_PASS=choose-a-strong-password docker compose up -d --build
```

Or with plain Docker:

```bash
docker build -t cloudman .
docker run -d --name cloudman -p 7681:7681 -e WEB_USER=admin -e WEB_PASS=choose-a-strong-password cloudman
```

Open <http://localhost:7681> and log in as `admin` with your password.
If you leave `WEB_PASS` out (plain `docker run` only), a random password is
generated and printed in `docker logs cloudman`.

## Settings

| Variable   | Default    | Meaning                     |
|------------|------------|-----------------------------|
| `WEB_USER` | `admin`    | Login name for the web page |
| `WEB_PASS` | (random)   | Login password              |
| `PORT`     | `7681`     | Port inside the container   |

## Security notes

Anyone who logs in gets a root-capable shell. Basic auth over plain HTTP sends
the password unencrypted, so for anything outside your own machine or LAN put it
behind HTTPS (a reverse proxy such as Caddy or Traefik, or a Cloudflare/Tailscale
tunnel). Don't expose port 7681 straight to the internet.

## Building behind a TLS-intercepting proxy

The Dockerfile accepts an optional CA certificate as a BuildKit secret (it is
not stored in the image):

```bash
docker build --network host --build-arg https_proxy=$HTTPS_PROXY \
  --secret id=proxy_ca,src=/path/to/ca.crt -t cloudman .
```
