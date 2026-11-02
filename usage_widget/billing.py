"""Read the SuperGrok weekly pool without persisting credentials.

The Grok CLI owns the session in ``~/.grok/auth.json``. This module asks that
CLI for billing first, so the common path never reads the token. The HTTP
fallback reads the access token in memory, sends it only to
``cli-chat-proxy.grok.com``, and refuses any redirect off that host. Nothing
returned to the widget includes a token, email, or account id.
"""

from __future__ import annotations

import json
import os
import select
import shutil
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BILLING_HOST = "cli-chat-proxy.grok.com"
BILLING_URL = "https://cli-chat-proxy.grok.com/v1/billing?format=credits"
TOKEN_AUTH = "xai-grok-cli"
PROVIDER = "grok"

PUBLIC_KEYS = (
    "schemaVersion",
    "provider",
    "ok",
    "auth",
    "percentUsed",
    "resetsAt",
    "window",
    "plan",
    "fetchedAt",
    "message",
)


class AuthRequired(Exception):
    """The CLI session is missing or rejected."""


class Unavailable(Exception):
    """Billing could not be read, for a reason other than auth."""


class SameOriginRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not same_billing_host(newurl):
            raise urllib.error.HTTPError(newurl, code, "cross-origin redirect refused", headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def same_billing_host(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    return parsed.scheme == "https" and parsed.hostname == BILLING_HOST


def grok_home() -> Path:
    return Path(os.environ.get("GROK_HOME") or (Path.home() / ".grok")).expanduser()


def grok_binary() -> str | None:
    override = os.environ.get("GROK_BIN", "").strip()
    if override and os.access(override, os.X_OK):
        return override
    bundled = grok_home() / "bin" / "grok"
    if os.access(bundled, os.X_OK):
        return str(bundled)
    return shutil.which("grok")


def state_path() -> Path:
    root = os.environ.get("XDG_STATE_HOME", "").strip()
    base = Path(root).expanduser() if root else Path.home() / ".local" / "state"
    return base / "usage-widget" / "status.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def public_record(
    *,
    ok: bool,
    auth: str,
    percent_used: float | None = None,
    resets_at: str = "",
    window: str = "",
    plan: str = "",
    message: str = "",
    fetched_at: str = "",
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "schemaVersion": 1,
        "provider": PROVIDER,
        "ok": ok,
        "auth": auth,
        "percentUsed": percent_used,
        "resetsAt": resets_at,
        "window": window,
        "plan": plan,
        "fetchedAt": fetched_at or _now(),
        "message": message,
    }
    extra = set(record) - set(PUBLIC_KEYS)
    if extra:
        raise RuntimeError(f"public record has unexpected keys: {sorted(extra)}")
    return record


def signed_out(message: str = "Run grok login") -> dict[str, Any]:
    return public_record(ok=False, auth="signed-out", message=message)


def missing_cli() -> dict[str, Any]:
    return public_record(ok=False, auth="missing", message="Grok CLI not found")


def unavailable() -> dict[str, Any]:
    return public_record(ok=False, auth="error", message="Usage unavailable")


def _safe_plan(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    text = " ".join(value.split())
    if not text or len(text) > 40 or any(ord(ch) < 32 for ch in text):
        return ""
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 ._-+")
    if any(ch not in allowed for ch in text):
        return ""
    return text


def _window(period_type: str) -> str:
    text = period_type.upper()
    if "MONTH" in text:
        return "monthly"
    if "WEEK" in text:
        return "weekly"
    return "period"


def parse_billing(payload: dict[str, Any]) -> dict[str, Any]:
    """Pull the shared weekly pool out of a billing payload.

    ``creditUsagePercent`` is the amount already used, on a 0-100 scale.
    Product rows are a split of that pool, not the number the bar shows.
    """
    if not isinstance(payload, dict):
        raise Unavailable("billing payload was not an object")
    config = payload.get("config") if isinstance(payload.get("config"), dict) else payload
    if not isinstance(config, dict):
        raise Unavailable("billing payload had no config")
    try:
        percent = float(config.get("creditUsagePercent"))
    except (TypeError, ValueError):
        raise Unavailable("billing payload had no usage percent") from None
    if percent != percent or percent < 0 or percent > 100:
        raise Unavailable("billing payload had an unusable usage percent")
    period = config.get("currentPeriod") if isinstance(config.get("currentPeriod"), dict) else {}
    resets_at = str((period or {}).get("end") or config.get("billingPeriodEnd") or "").strip()
    if resets_at == "":
        raise Unavailable("billing payload had no reset time")
    window = _window(str((period or {}).get("type") or ""))
    plan = _safe_plan(payload.get("subscription_tier") or config.get("subscription_tier"))
    return public_record(
        ok=True,
        auth="ok",
        percent_used=percent,
        resets_at=resets_at,
        window=window,
        plan=plan,
        message="",
    )


def _rpc(proc: subprocess.Popen[str], request_id: int, method: str, params: dict[str, Any] | None, timeout: float) -> dict[str, Any]:
    if proc.stdin is None or proc.stdout is None:
        raise Unavailable("Grok stdio is closed")
    proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}}) + "\n")
    proc.stdin.flush()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        ready, _, _ = select.select([proc.stdout], [], [], 0.25)
        if not ready:
            continue
        line = proc.stdout.readline()
        if not line:
            break
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(message, dict) and message.get("id") == request_id:
            return message
    raise Unavailable("Grok billing timed out")


def _auth_error(message: dict[str, Any]) -> bool:
    error = message.get("error")
    if not isinstance(error, dict):
        return False
    if error.get("code") in (401, 403):
        return True
    text = str(error.get("message") or "").lower()
    markers = ("unauthorized", "unauthenticated", "authentication", "login", "expired", "sign-in", "sign in")
    return any(marker in text for marker in markers)


def collect_acp(binary: str, timeout: float = 20) -> dict[str, Any]:
    try:
        proc = subprocess.Popen(
            [binary, "agent", "--no-leader", "stdio"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except OSError as exc:
        raise Unavailable("could not start Grok") from exc
    try:
        _rpc(
            proc,
            1,
            "initialize",
            {"protocolVersion": "0.1.0", "clientInfo": {"name": "usage-widget", "version": "0"}, "capabilities": {}},
            timeout,
        )
        if proc.stdin is None:
            raise Unavailable("Grok stdio is closed")
        proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "initialized", "params": {}}) + "\n")
        proc.stdin.flush()
        message = _rpc(proc, 2, "_x.ai/billing", {}, timeout)
    finally:
        if proc.stdin:
            try:
                proc.stdin.close()
            except Exception:
                pass
        proc.terminate()
        try:
            proc.wait(timeout=1)
        except subprocess.TimeoutExpired:
            proc.kill()
    if _auth_error(message):
        raise AuthRequired("sign-in rejected")
    error = message.get("error")
    if error:
        code = error.get("code") if isinstance(error, dict) else None
        if code == -32601:
            raise Unavailable("billing method missing")
        raise Unavailable("Grok billing failed")
    result = message.get("result")
    if not isinstance(result, dict):
        raise Unavailable("billing result missing")
    return parse_billing(result)


def _read_login(home: Path) -> dict[str, Any] | None:
    path = home / "auth.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    best: dict[str, Any] | None = None
    for entry in data.values():
        if not isinstance(entry, dict):
            continue
        mode = str(entry.get("auth_mode") or "")
        if mode not in ("oidc", "oauth", ""):
            continue
        key = str(entry.get("key") or "").strip()
        if key == "" or key.startswith("sk-") or key.startswith("xai-"):
            continue
        if best is None or str(entry.get("expires_at") or "") > str(best.get("expires_at") or ""):
            best = entry
    return best


def collect_http(home: Path, timeout: float = 10) -> dict[str, Any]:
    login = _read_login(home)
    if login is None:
        raise AuthRequired("no CLI session")
    token = str(login.get("key") or "").strip()
    if token == "":
        raise AuthRequired("no CLI session")
    headers = {
        "Authorization": "Bearer " + token,
        "X-XAI-Token-Auth": TOKEN_AUTH,
        "Accept": "application/json",
    }
    user_id = str(login.get("user_id") or "").strip()
    if user_id:
        headers["x-userid"] = user_id
    request = urllib.request.Request(BILLING_URL, headers=headers, method="GET")
    opener = urllib.request.build_opener(SameOriginRedirectHandler)
    try:
        with opener.open(request, timeout=timeout) as response:
            final = getattr(response, "geturl", lambda: BILLING_URL)()
            if not same_billing_host(final):
                raise Unavailable("redirected off the billing host")
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise AuthRequired("sign-in rejected") from None
        raise Unavailable("billing request failed") from None
    except (OSError, json.JSONDecodeError, TimeoutError) as exc:
        raise Unavailable("billing request failed") from exc
    if not isinstance(payload, dict):
        raise Unavailable("billing payload was not an object")
    return parse_billing(payload)


def collect(timeout: float = 20) -> dict[str, Any]:
    binary = grok_binary()
    if not binary:
        return missing_cli()
    try:
        return collect_acp(binary, timeout=timeout)
    except AuthRequired:
        return signed_out()
    except Unavailable:
        pass
    except Exception:
        pass
    try:
        return collect_http(grok_home(), timeout=min(10, timeout))
    except AuthRequired:
        return signed_out()
    except Exception:
        return unavailable()


def write_status(record: dict[str, Any], path: Path | None = None) -> Path:
    target = path or state_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(target.parent, 0o700)
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(record, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(temporary, 0o600)
    os.replace(temporary, target)
    os.chmod(target, 0o600)
    return target
