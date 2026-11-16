"""Owned loopback HTTPS + CONNECT proxy acceptance; no external or paid calls.

Requires cryptography in the test environment only. The generated TLS key lives
in a temporary directory outside the repository and is deleted after the test.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import errno
import hashlib
import http.server
import json
from pathlib import Path
import select
import socket
import ssl
import sys
import tempfile
import threading
from unittest.mock import patch
import os

import requests
import urllib3.util.connection

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT.parents[1])]
import nodes


def certificate(directory):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "api.seedance.nz")])
    now = datetime.now(timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
        .serial_number(x509.random_serial_number()).not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=1))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName("api.seedance.nz")]), critical=False)
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True).sign(key, hashes.SHA256()))
    cert_path, key_path = directory / "test-ca.pem", directory / "test-key.pem"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                         serialization.NoEncryption()))
    return cert_path, key_path


@contextmanager
def servers(cert, key, *, drop_chat=False):
    seen, tunnels = [], []

    class Origin(http.server.BaseHTTPRequestHandler):
        def log_message(self, *_): pass
        def do_POST(self):
            body = self.rfile.read(int(self.headers["Content-Length"]))
            assert self.headers.get("Authorization") == "Bearer test-placeholder"
            assert not self.headers.get("Proxy-Authorization"), "Proxy credentials leaked to origin"
            seen.append({"path": self.path, "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()})
            if self.path.endswith("/files/upload"):
                assert b"offline image" in body and b"test.png" in body
                payload = {"url": "https://assets.example/test.png"}
            else:
                assert json.loads(body)["messages"][0]["content"] == "offline prompt"
                if drop_chat:
                    self.close_connection = True
                    return
                payload = {"choices": [{"message": {"content": "offline answer"}, "finish_reason": "stop"}]}
            data = json.dumps(payload).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    origin = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Origin)
    origin.daemon_threads = True
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(str(cert), str(key))
    origin.socket = context.wrap_socket(origin.socket, server_side=True)
    origin_port = origin.server_port

    class Proxy(http.server.BaseHTTPRequestHandler):
        def log_message(self, *_): pass
        def do_CONNECT(self):
            if self.path != f"api.seedance.nz:{origin_port}":
                self.send_error(403)
                return
            tunnels.append({"method": "CONNECT", "authenticated": bool(self.headers.get("Proxy-Authorization"))})
            with socket.create_connection(("127.0.0.1", origin_port), timeout=5) as upstream:
                self.send_response(200, "Connection Established")
                self.end_headers()
                peers = [self.connection, upstream]
                while True:
                    readable, _, _ = select.select(peers, [], [], 5)
                    if not readable:
                        return
                    for current in readable:
                        data = current.recv(65536)
                        if not data:
                            return
                        (upstream if current is self.connection else self.connection).sendall(data)

    proxy = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Proxy)
    proxy.daemon_threads = True
    threads = [threading.Thread(target=s.serve_forever, daemon=True) for s in (origin, proxy)]
    for thread in threads: thread.start()
    try:
        yield origin_port, proxy.server_port, seen, tunnels
    finally:
        for server in (proxy, origin): server.shutdown(); server.server_close()
        for thread in threads: thread.join(3)


def scenario(cert, key, *, mode, drop_chat=False):
    with servers(cert, key, drop_chat=drop_chat) as (origin_port, proxy_port, seen, tunnels), socket.socket() as refused:
        refused.bind(("127.0.0.1", 0))  # Reserved but not listening: deterministic connect refusal.
        actual_connect = urllib3.util.connection.create_connection
        direct_calls = []

        def connect(address, *args, **kwargs):
            if address[0] == "api.seedance.nz":
                direct_calls.append(address[1])
                if mode in ("proxy", "drop"):
                    raise OSError(errno.ENETUNREACH, "test fixture blocks direct egress")
                address = ("127.0.0.1", origin_port)
            return actual_connect(address, *args, **kwargs)

        env = {name: "" for name in os.environ if name.lower().endswith("_proxy")}
        if mode != "direct":
            port = refused.getsockname()[1] if mode == "bad-proxy" else proxy_port
            env["HTTPS_PROXY"] = f"http://fixture-user:fixture-password@127.0.0.1:{port}"
        if mode == "bypass": env["NO_PROXY"] = "api.seedance.nz"
        base = f"https://api.seedance.nz:{origin_port}/v1"
        with patch.dict(os.environ, env), patch.object(urllib3.util.connection, "create_connection", connect), \
             patch.object(nodes.time, "sleep"), requests.Session() as session:
            session.verify = str(cert)  # Keep certificate and hostname verification enabled.
            messages = [{"role": "user", "content": "offline prompt"}]
            if drop_chat:
                try:
                    nodes._request_completion(session, "test-placeholder", messages, "balanced", chat_url=base + "/chat/completions")
                except nodes.PromptEnhancerError as error:
                    assert "may already have completed" in str(error)
                    assert "fixture-password" not in str(error)
                else:
                    raise AssertionError("Accepted-then-dropped POST must fail without resubmission")
                assert len(seen) == 1
            else:
                assert nodes._upload_media(session, "test-placeholder", b"offline image", "test.png", "image/png", base + "/files/upload") == "https://assets.example/test.png"
                assert nodes._request_completion(session, "test-placeholder", messages, "balanced", chat_url=base + "/chat/completions") == "offline answer"
                assert [row["path"] for row in seen] == ["/v1/files/upload", "/v1/chat/completions"]
        if mode in ("proxy", "drop"):
            assert tunnels and all(t["authenticated"] for t in tunnels)
            assert not direct_calls, "Explicit proxy should be used on the first attempt"
        else:
            assert not tunnels and len(direct_calls) == 2
        return {"mode": mode, "tls_verified": True, "connect_tunnels": len(tunnels), "direct_connections": len(direct_calls),
                "origin_posts": len(seen), "chat_posts": sum(v["path"].endswith("/chat/completions") for v in seen), "passed": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    out = args.output_dir.resolve()
    if out == ROOT or ROOT in out.parents: parser.error("Use a new external evidence directory")
    out.mkdir(parents=True, exist_ok=False)
    records = []
    try:
        with tempfile.TemporaryDirectory(prefix="owned-tls-", dir=out) as temporary:
            cert, key = certificate(Path(temporary))
            for mode in ("proxy", "direct", "bypass", "bad-proxy", "drop"):
                records.append(scenario(cert, key, mode=mode, drop_chat=mode == "drop"))
                print(json.dumps(records[-1]), flush=True)
    finally:
        (out / "evidence.json").write_text(json.dumps({"real_network": "owned loopback HTTPS and CONNECT only", "external_calls": 0,
            "records": records, "passed": len(records) == 5 and all(r["passed"] for r in records)}, indent=2), encoding="utf-8")


if __name__ == "__main__": main()
