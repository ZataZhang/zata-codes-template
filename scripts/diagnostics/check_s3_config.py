"""Diagnostic script: verify S3 configuration end-to-end.

Run via:

    uv run python scripts/diagnostics/check_s3_config.py

Reads `S3_*` from environment variables, `.env`, and `.env.local`, then performs:

  1. SDK client init + bucket reachability check (no bucket creation)
  2. Upload a small temporary object under `_diagnostics/`
  3. Verify object existence
  4. Generate a presigned GET URL
  5. Download and assert byte equality
  6. Optionally check presigned URL browser reachability (CORS headers)
  7. Remove the temporary object

The script exits with code 0 on success and 1 on any blocking verification
failure. Presigned URL browser reachability is reported but does not fail the
diagnostic because backend-proxy previews may intentionally avoid browser CORS.
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

from botocore.exceptions import ClientError
from dotenv import load_dotenv

_PROJECT_ROOT_PATH = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT_PATH) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT_PATH))

from scripts.backup_service.config import BackupConfig  # noqa: E402
from scripts.backup_service.s3_client import S3Client  # noqa: E402

_DIAGNOSTIC_KEY_NAMESPACE = "_diagnostics"
_DIAGNOSTIC_PAYLOAD = b"template s3 diagnostic payload"


def _load_environment_files() -> None:
    """Load local dotenv files using the same root as justfile commands."""
    load_dotenv(_PROJECT_ROOT_PATH / ".env", override=False)
    load_dotenv(_PROJECT_ROOT_PATH / ".env.local", override=True)


def _prefix_object_key(storage_prefix: str, object_key: str) -> str:
    normalized_prefix = storage_prefix.strip("/")
    normalized_object_key = object_key.lstrip("/")
    if not normalized_prefix:
        return normalized_object_key
    return f"{normalized_prefix}/{normalized_object_key}"


def _print_step(step_label: str) -> None:
    print(f"  -> {step_label} ... ", end="", flush=True)


def _print_ok(detail: str = "") -> None:
    if detail:
        print(f"OK ({detail})")
    else:
        print("OK")


def _print_failure(failure_exc: Exception) -> None:
    print("FAIL")
    print(f"     {type(failure_exc).__name__}: {failure_exc}")


def _validate_s3_config(backup_config: BackupConfig) -> list[str]:
    missing_field_names: list[str] = []
    if not backup_config.s3_endpoint:
        missing_field_names.append("S3_ENDPOINT")
    if not backup_config.s3_access_key:
        missing_field_names.append("S3_ACCESS_KEY")
    if not backup_config.s3_secret_key:
        missing_field_names.append("S3_SECRET_KEY")
    if not backup_config.s3_bucket:
        missing_field_names.append("S3_BUCKET")
    return missing_field_names


def _try_cleanup(sdk_client, bucket_name: str, prefixed_object_key: str) -> None:
    """Best-effort cleanup after a mid-diagnostic failure; silent on failure."""
    try:
        sdk_client.delete_object(Bucket=bucket_name, Key=prefixed_object_key)
    except Exception:
        pass


def _redact_presigned_url(presigned_url: str) -> str:
    """Strip the query string so the SigV4 credential/signature are not logged."""
    base_url, _, _ = presigned_url.partition("?")
    return f"{base_url}?<redacted-signature>"


def _check_presigned_browser_reachability(presigned_url: str) -> tuple[bool, str]:
    """Check whether a presigned URL is browser-reachable via CORS.

    The presigned URL is signed for GET, so the probe must also use GET; a HEAD
    probe would change the canonical request and fail SigV4 signature validation
    on strict servers. A sample ``Origin`` header is sent because S3-compatible
    services only emit ``Access-Control-Allow-Origin`` in response to an actual
    CORS request, so a probe without ``Origin`` could never observe the header.

    Returns:
        Tuple of (is_reachable, classification) where classification is one of
        'yes', 'cors-missing', 'dns', 'connection', or 'http-<status>'.
    """
    import urllib.error
    import urllib.request

    request = urllib.request.Request(presigned_url, method="GET")
    request.add_header("Origin", "https://diagnostic.local")
    request.add_header("Range", "bytes=0-0")
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            cors_header = response.headers.get("Access-Control-Allow-Origin")
            if cors_header:
                return True, "yes"
            return False, "cors-missing"
    except urllib.error.HTTPError as http_exc:
        return False, f"http-{http_exc.code}"
    except urllib.error.URLError as url_exc:
        underlying_name = type(url_exc.reason).__name__
        if underlying_name in {"gaierror", "NameResolutionError"}:
            return False, "dns"
        return False, "connection"
    except Exception:
        return False, "connection"


def run_s3_config_diagnostic() -> int:
    _load_environment_files()
    backup_config = BackupConfig.from_env()

    print("S3 configuration diagnostic")
    print(f"  endpoint        : {backup_config.s3_endpoint}")
    print(f"  bucket          : {backup_config.s3_bucket}")
    print(f"  prefix          : {backup_config.s3_prefix!r}")
    print(f"  addressing_style: {backup_config.s3_addressing_style}")
    print()

    missing_field_names = _validate_s3_config(backup_config)
    if missing_field_names:
        print("S3 configuration is incomplete.")
        for missing_field_name in missing_field_names:
            print(f"  missing: {missing_field_name}")
        return 1

    _print_step("Initialize SDK client")
    try:
        storage_client = S3Client(
            endpoint=backup_config.s3_endpoint,
            access_key=backup_config.s3_access_key,
            secret_key=backup_config.s3_secret_key,
            bucket=backup_config.s3_bucket,
            addressing_style=backup_config.s3_addressing_style,
        )
        sdk_client = storage_client.client
        _print_ok(backup_config.s3_endpoint)
    except Exception as init_exc:
        _print_failure(init_exc)
        return 1

    _print_step(f"Check bucket '{backup_config.s3_bucket}' is reachable")
    try:
        sdk_client.head_bucket(Bucket=backup_config.s3_bucket)
        _print_ok()
    except ClientError as bucket_exc:
        _print_failure(bucket_exc)
        error_code = bucket_exc.response.get("Error", {}).get("Code", "")
        if error_code in {"404", "NoSuchBucket"}:
            print(
                f"     Bucket '{backup_config.s3_bucket}' does not exist on this endpoint."
            )
            print("     Create it first or fix S3_BUCKET in .env.")
        elif error_code in {"403", "Forbidden", "AccessDenied"}:
            print("     Credentials are valid but lack s3:HeadBucket permission,")
            print("     OR the bucket lives in a different region/account.")
        return 1
    except Exception as bucket_exc:
        _print_failure(bucket_exc)
        return 1

    diagnostic_object_key = f"{_DIAGNOSTIC_KEY_NAMESPACE}/{uuid.uuid4()}.txt"
    prefixed_object_key = _prefix_object_key(
        backup_config.s3_prefix,
        diagnostic_object_key,
    )

    _print_step(f"Upload test object at '{prefixed_object_key}'")
    try:
        sdk_client.put_object(
            Bucket=backup_config.s3_bucket,
            Key=prefixed_object_key,
            Body=_DIAGNOSTIC_PAYLOAD,
            ContentType="text/plain",
        )
        _print_ok()
    except Exception as put_exc:
        _print_failure(put_exc)
        return 1

    _print_step("Verify object existence via head_object")
    try:
        sdk_client.head_object(Bucket=backup_config.s3_bucket, Key=prefixed_object_key)
        _print_ok()
    except Exception as head_exc:
        _print_failure(head_exc)
        _try_cleanup(sdk_client, backup_config.s3_bucket, prefixed_object_key)
        return 1

    _print_step("Generate presigned GET URL (5 min)")
    try:
        presigned_url = sdk_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": backup_config.s3_bucket, "Key": prefixed_object_key},
            ExpiresIn=300,
        )
        _print_ok(_redact_presigned_url(presigned_url))
    except Exception as presign_exc:
        _print_failure(presign_exc)
        _try_cleanup(sdk_client, backup_config.s3_bucket, prefixed_object_key)
        return 1

    _print_step("Download object and verify byte equality")
    try:
        response = sdk_client.get_object(
            Bucket=backup_config.s3_bucket,
            Key=prefixed_object_key,
        )
        downloaded_payload = response["Body"].read()
        if downloaded_payload != _DIAGNOSTIC_PAYLOAD:
            print("FAIL")
            print(
                f"     Byte mismatch: uploaded {len(_DIAGNOSTIC_PAYLOAD)} bytes, "
                f"got {len(downloaded_payload)} bytes."
            )
            _try_cleanup(sdk_client, backup_config.s3_bucket, prefixed_object_key)
            return 1
        _print_ok()
    except Exception as get_exc:
        _print_failure(get_exc)
        _try_cleanup(sdk_client, backup_config.s3_bucket, prefixed_object_key)
        return 1

    _print_step("Check presigned URL browser reachability (CORS)")
    try:
        is_reachable, classification = _check_presigned_browser_reachability(
            presigned_url,
        )
        _print_ok(f"presigned_url_browser_reachable: {classification}")
        if not is_reachable:
            print(
                "     Tip: If cors-missing, configure CORS on the bucket for your "
                "frontend origin, or serve previews through the backend proxy."
            )
    except Exception as reach_exc:
        _print_failure(reach_exc)

    _print_step("Remove test object")
    try:
        sdk_client.delete_object(
            Bucket=backup_config.s3_bucket, Key=prefixed_object_key
        )
        _print_ok()
    except Exception as remove_exc:
        _print_failure(remove_exc)
        print(f"     Leftover diagnostic object: {prefixed_object_key}")
        return 1

    print()
    print("S3 configuration looks healthy.")
    return 0


if __name__ == "__main__":
    sys.exit(run_s3_config_diagnostic())
