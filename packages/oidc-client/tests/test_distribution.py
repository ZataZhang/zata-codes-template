"""在仓库外构建并安装 wheel，验证公开 API 与真实 RS256 issuer。"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import textwrap
import zipfile
from pathlib import Path

import pytest

_CONSUMER_SCRIPT = r"""
from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

from joserfc import jwt
from joserfc.jwk import RSAKey

import zata_oidc
from zata_oidc import HttpOidcClient, OidcAuthenticationError, OidcClientSettings

server_state = {}
issuer_key = RSAKey.generate_key()
private_jwk = issuer_key.as_dict(private=True)
private_jwk["kid"] = "wheel-consumer-key"
issuer_key = RSAKey.import_key(private_jwk)
public_jwk = issuer_key.as_dict(private=False)
public_jwk["kid"] = "wheel-consumer-key"
forged_key = RSAKey.generate_key()
forged_jwk = forged_key.as_dict(private=True)
forged_jwk["kid"] = "wheel-consumer-key"
forged_key = RSAKey.import_key(forged_jwk)


class IssuerHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        issuer = server_state["issuer"]
        if self.path == "/issuer/.well-known/openid-configuration":
            response = {
                "issuer": issuer,
                "authorization_endpoint": issuer + "/authorize",
                "token_endpoint": issuer + "/token",
                "jwks_uri": issuer + "/jwks",
            }
        elif self.path == "/issuer/jwks":
            response = {"keys": [public_jwk]}
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(response).encode("utf-8"))

    def do_POST(self):
        content_length = int(self.headers["Content-Length"])
        form = parse_qs(self.rfile.read(content_length).decode("utf-8"))
        server_state["form"] = {key: values[0] for key, values in form.items()}
        now = int(time.time())
        claims = {
            "iss": server_state["issuer"],
            "sub": "wheel-consumer-subject",
            "aud": "wheel-client",
            "iat": now,
            "exp": now + 300,
            "nonce": "wheel-consumer-nonce",
            "email": "wheel@example.test",
            "email_verified": True,
            "name": "Wheel Consumer",
        }
        signing_key = forged_key if server_state["form"].get("code") == "forged" else issuer_key
        id_token = jwt.encode({"alg": "RS256", "kid": "wheel-consumer-key"}, claims, signing_key)
        body = json.dumps({"id_token": id_token}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format, *_args):
        return


http_server = ThreadingHTTPServer(("127.0.0.1", 0), IssuerHandler)
server_state["issuer"] = f"http://127.0.0.1:{http_server.server_port}/issuer"
server_thread = threading.Thread(target=http_server.serve_forever, daemon=True)
server_thread.start()
client = HttpOidcClient(
    OidcClientSettings(
        issuer=server_state["issuer"],
        client_id="wheel-client",
        client_secret="wheel-test-secret",
        callback_uri="http://127.0.0.1/callback",
    )
)
try:
    authorization_url = client.build_authorization_url(
        state="wheel-state",
        nonce="wheel-consumer-nonce",
        code_verifier="w" * 43,
    )
    assert "code_challenge_method=S256" in authorization_url
    identity = client.exchange_and_verify_authorization_code(
        code="signed",
        code_verifier="w" * 43,
        nonce="wheel-consumer-nonce",
    )
    assert identity.subject == "wheel-consumer-subject"
    assert identity.email_verified is True
    assert server_state["form"]["client_secret"] == "wheel-test-secret"
    assert server_state["form"]["code_verifier"] == "w" * 43
    try:
        client.exchange_and_verify_authorization_code(
            code="forged",
            code_verifier="w" * 43,
            nonce="wheel-consumer-nonce",
        )
    except OidcAuthenticationError as error:
        assert error.reason.value == "token_validation"
    else:
        raise AssertionError("untrusted RS256 signature was accepted")
finally:
    client.close()
    http_server.shutdown()
    http_server.server_close()
    server_thread.join(timeout=5)

print(zata_oidc.__file__)
"""


def test_wheel_installs_outside_checkout_and_verifies_signed_issuer(tmp_path: Path) -> None:
    """非 editable wheel 消费环境能验证可信签名并拒绝伪造签名。"""

    uv_path = shutil.which("uv")
    if uv_path is None:
        pytest.skip("uv CLI is required for the isolated wheel distribution test")

    package_root = Path(__file__).resolve().parents[1]
    build_directory = tmp_path / "dist"
    consumer_directory = tmp_path / "consumer"
    environment_directory = tmp_path / "consumer-venv"
    build_directory.mkdir()
    consumer_directory.mkdir()

    build_result = subprocess.run(
        [
            uv_path,
            "build",
            "--project",
            str(package_root),
            "--out-dir",
            str(build_directory),
        ],
        cwd=consumer_directory,
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
    )
    assert build_result.returncode == 0, build_result.stdout + build_result.stderr

    wheel_paths = list(build_directory.glob("zata_oidc-*.whl"))
    source_archives = list(build_directory.glob("zata_oidc-*.tar.gz"))
    assert len(wheel_paths) == 1
    assert len(source_archives) == 1
    with zipfile.ZipFile(wheel_paths[0]) as wheel_archive:
        wheel_files = wheel_archive.namelist()
    assert any(file_path.startswith("zata_oidc/") for file_path in wheel_files)
    assert not any(file_path.startswith("backend/") for file_path in wheel_files)

    virtualenv_result = subprocess.run(
        [uv_path, "venv", "--python", sys.executable, str(environment_directory)],
        cwd=consumer_directory,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert virtualenv_result.returncode == 0, virtualenv_result.stdout + virtualenv_result.stderr

    python_path = environment_directory / (
        "Scripts/python.exe" if os.name == "nt" else "bin/python"
    )
    install_result = subprocess.run(
        [uv_path, "pip", "install", "--python", str(python_path), str(wheel_paths[0])],
        cwd=consumer_directory,
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
    )
    assert install_result.returncode == 0, install_result.stdout + install_result.stderr

    consumer_script_path = consumer_directory / "consumer_check.py"
    consumer_script_path.write_text(textwrap.dedent(_CONSUMER_SCRIPT), encoding="utf-8")
    consumer_environment = os.environ.copy()
    consumer_environment.pop("PYTHONPATH", None)
    consumer_environment.pop("PYTHONHOME", None)
    consumer_environment["PYTHONNOUSERSITE"] = "1"
    consumer_result = subprocess.run(
        [str(python_path), str(consumer_script_path)],
        cwd=consumer_directory,
        env=consumer_environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert consumer_result.returncode == 0, consumer_result.stdout + consumer_result.stderr
    assert str(environment_directory) in consumer_result.stdout
    assert str(package_root) not in consumer_result.stdout
