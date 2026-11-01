#!/usr/bin/env python3
"""cloudman file manager: browse, upload, download, mkdir and delete files.

Standard library only. Protected by the same HTTP basic auth as the terminal.

Environment:
  WEB_USER, WEB_PASS   login (required)
  FILES_ROOT           folder to serve (default: the running user's home)
  FILES_PORT           port to listen on (default 7682)
"""
import base64
import hmac
import json
import os
import shutil
import tempfile
import urllib.parse
import zipfile
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(os.environ.get("FILES_ROOT") or Path.home()).resolve()
PORT = int(os.environ.get("FILES_PORT", "7682"))
USER = os.environ["WEB_USER"]
PASS = os.environ["WEB_PASS"]
EXPECTED_AUTH = "Basic " + base64.b64encode(f"{USER}:{PASS}".encode()).decode()
INDEX_HTML = (Path(__file__).parent / "index.html").read_bytes()
CHUNK = 1024 * 1024


class BadPath(Exception):
    pass


def resolve(rel: str) -> Path:
    """Map a path from the browser to a real path that stays inside ROOT."""
    rel = (rel or "").strip().lstrip("/")
    p = (ROOT / rel).resolve()
    if p != ROOT and ROOT not in p.parents:
        raise BadPath(rel)
    return p


def clean_name(name: str) -> str:
    name = (name or "").replace("\\", "/").split("/")[-1].strip()
    if name in ("", ".", ".."):
        raise BadPath(name)
    return name


class Handler(BaseHTTPRequestHandler):
    server_version = "cloudman-files"
    protocol_version = "HTTP/1.1"

    # ---------- helpers ----------
    def log_message(self, fmt, *args):
        print(f"[files] {self.address_string()} {fmt % args}", flush=True)

    def authed(self) -> bool:
        got = self.headers.get("Authorization", "")
        if hmac.compare_digest(got.encode(), EXPECTED_AUTH.encode()):
            return True
        body = b"Login required"
        self.send_response(HTTPStatus.UNAUTHORIZED)
        self.send_header("WWW-Authenticate", 'Basic realm="cloudman", charset="UTF-8"')
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        return False

    def query(self):
        return {k: v[0] for k, v in urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).items()}

    def send_json(self, obj, status=HTTPStatus.OK):
        body = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def fail(self, status, message):
        self.send_json({"error": message}, status)

    def mutation_allowed(self) -> bool:
        # A custom header can't be sent cross-site without a CORS preflight
        # (which we never approve), so this blocks CSRF on write requests.
        if self.headers.get("X-Cloudman") == "1":
            return True
        self.fail(HTTPStatus.FORBIDDEN, "Missing X-Cloudman header")
        return False

    def send_file(self, path: Path, name: str, ctype="application/octet-stream"):
        size = path.stat().st_size
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(size))
        self.send_header("Content-Disposition", "attachment; filename*=UTF-8''" + urllib.parse.quote(name))
        self.end_headers()
        with path.open("rb") as f:
            shutil.copyfileobj(f, self.wfile, CHUNK)

    # ---------- routes ----------
    def do_GET(self):
        if not self.authed():
            return
        route = urllib.parse.urlsplit(self.path).path
        q = self.query()
        try:
            if route in ("/", "/index.html"):
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(INDEX_HTML)))
                self.end_headers()
                self.wfile.write(INDEX_HTML)
            elif route == "/api/list":
                d = resolve(q.get("path", ""))
                if not d.is_dir():
                    return self.fail(HTTPStatus.NOT_FOUND, "Folder not found")
                items = []
                for e in os.scandir(d):
                    try:
                        st = e.stat()
                        items.append({"name": e.name, "dir": e.is_dir(), "size": st.st_size, "mtime": int(st.st_mtime)})
                    except OSError:
                        continue
                items.sort(key=lambda i: (not i["dir"], i["name"].lower()))
                rel = d.relative_to(ROOT).as_posix()
                self.send_json({"path": "" if rel == "." else rel, "items": items})
            elif route == "/api/download":
                p = resolve(q.get("path", ""))
                if p.is_file():
                    self.send_file(p, p.name)
                elif p.is_dir():
                    with tempfile.NamedTemporaryFile(suffix=".zip") as tmp:
                        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
                            for f in sorted(p.rglob("*")):
                                if f.is_file() and not f.is_symlink():
                                    z.write(f, f.relative_to(p.parent))
                        tmp.flush()
                        self.send_file(Path(tmp.name), (p.name or "home") + ".zip", "application/zip")
                else:
                    self.fail(HTTPStatus.NOT_FOUND, "File not found")
            else:
                self.fail(HTTPStatus.NOT_FOUND, "Not found")
        except BadPath:
            self.fail(HTTPStatus.BAD_REQUEST, "That path is outside your home folder")

    def do_PUT(self):
        if not self.authed() or not self.mutation_allowed():
            return
        if urllib.parse.urlsplit(self.path).path != "/api/upload":
            return self.fail(HTTPStatus.NOT_FOUND, "Not found")
        q = self.query()
        try:
            folder = resolve(q.get("path", ""))
            name = clean_name(q.get("name", ""))
            if not folder.is_dir():
                return self.fail(HTTPStatus.NOT_FOUND, "Folder not found")
            dest = resolve(str((folder / name).relative_to(ROOT)))
            length = int(self.headers.get("Content-Length", "0"))
            part = dest.with_name(dest.name + ".part")
            with part.open("wb") as f:
                left = length
                while left > 0:
                    buf = self.rfile.read(min(CHUNK, left))
                    if not buf:
                        break
                    f.write(buf)
                    left -= len(buf)
            if left:
                part.unlink(missing_ok=True)
                return self.fail(HTTPStatus.BAD_REQUEST, "Upload was cut off")
            part.replace(dest)
            self.send_json({"ok": True, "name": name, "size": length})
        except BadPath:
            self.fail(HTTPStatus.BAD_REQUEST, "That path is outside your home folder")
        except ValueError:
            self.fail(HTTPStatus.BAD_REQUEST, "Bad Content-Length")

    def do_POST(self):
        if not self.authed() or not self.mutation_allowed():
            return
        route = urllib.parse.urlsplit(self.path).path
        q = self.query()
        try:
            if route == "/api/mkdir":
                parent = resolve(q.get("path", ""))
                target = resolve(str((parent / clean_name(q.get("name", ""))).relative_to(ROOT)))
                target.mkdir(exist_ok=False)
                self.send_json({"ok": True})
            elif route == "/api/delete":
                p = resolve(q.get("path", ""))
                if p == ROOT:
                    return self.fail(HTTPStatus.BAD_REQUEST, "Can't delete your home folder")
                if p.is_dir() and not p.is_symlink():
                    shutil.rmtree(p)
                elif p.exists() or p.is_symlink():
                    p.unlink()
                else:
                    return self.fail(HTTPStatus.NOT_FOUND, "Not found")
                self.send_json({"ok": True})
            else:
                self.fail(HTTPStatus.NOT_FOUND, "Not found")
        except BadPath:
            self.fail(HTTPStatus.BAD_REQUEST, "That path or name isn't allowed")
        except FileExistsError:
            self.fail(HTTPStatus.CONFLICT, "A file or folder with that name already exists")


if __name__ == "__main__":
    print(f"[files] serving {ROOT} on port {PORT}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
