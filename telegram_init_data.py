"""Telegram Mini App: initData bütünlük doğrulaması (bot token + WebAppData)."""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from base64 import urlsafe_b64decode, urlsafe_b64encode
from typing import Any
from urllib.parse import parse_qsl


def create_login_session(user: dict[str, Any], bot_token: str, *, max_age_sec: int = 30 * 86400) -> str:
    """Create a signed, time-limited server session for a verified Telegram user."""
    if not bot_token or not user.get("id"):
        raise ValueError("Verified Telegram user and bot token are required.")
    claims = {
        "user_id": int(user["id"]),
        "user": {
            key: user[key]
            for key in ("id", "first_name", "last_name", "username", "photo_url", "email", "provider")
            if user.get(key)
        },
        "iat": int(time.time()),
        "exp": int(time.time()) + int(max_age_sec),
    }
    payload = urlsafe_b64encode(json.dumps(claims, separators=(",", ":")).encode("utf-8")).rstrip(b"=")
    key = hashlib.sha256(bot_token.encode("utf-8")).digest()
    signature = hmac.new(key, payload, hashlib.sha256).digest()
    return (payload + b"." + urlsafe_b64encode(signature).rstrip(b"=")).decode("ascii")


def validate_login_session(session: str, bot_token: str) -> dict[str, Any] | None:
    """Validate a signed app session and return the same shape as initData parsing."""
    if not session or not bot_token:
        return None
    try:
        payload, signature = session.encode("ascii").split(b".", 1)
        key = hashlib.sha256(bot_token.encode("utf-8")).digest()
        expected = hmac.new(key, payload, hashlib.sha256).digest()
        supplied = urlsafe_b64decode(signature + b"=" * (-len(signature) % 4))
        if not hmac.compare_digest(expected, supplied):
            return None
        claims = json.loads(urlsafe_b64decode(payload + b"=" * (-len(payload) % 4)))
        now = int(time.time())
        issued_at = int(claims.get("iat", 0))
        expires_at = int(claims.get("exp", 0))
        user_id = int(claims.get("user_id", 0))
        if user_id <= 0 or issued_at > now + 30 or expires_at <= now:
            return None
        if expires_at - issued_at > 30 * 86400:
            return None
        user = claims.get("user") or {"id": user_id}
        if not isinstance(user, dict) or int(user.get("id", 0)) != user_id:
            return None
        return {"user_id": user_id, "user_json": json.dumps(user, ensure_ascii=False)}
    except (ValueError, TypeError, KeyError, UnicodeError, json.JSONDecodeError):
        return None


def _parse_telegram_user_id(pairs: dict[str, str]) -> int | None:
    raw = (pairs.get("user") or "").strip()
    if not raw:
        return None
    try:
        u = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None
    if isinstance(u, dict) and u.get("id") is not None:
        return int(u["id"])
    return None


def validate_and_parse_init_data(
    init_data: str,
    bot_token: str,
    *,
    max_age_sec: int = 86400,
) -> dict[str, Any] | None:
    """
    Dönen dict: tüm alanlar + 'user_id' (int) ve gerekirse 'user_json'.
    Hatalı imza veya süresi geçmiş auth_date -> None.
    """
    if not (init_data and init_data.strip() and bot_token):
        return None
    try:
        pairs = dict(parse_qsl(init_data, keep_blank_values=True, strict_parsing=True))
    except ValueError:
        return None
    check_hash = pairs.pop("hash", None)
    if not check_hash:
        return None
    dcs = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    # Mini App initData uses WebAppData as the HMAC key; Login Widget
    # authorization uses SHA256(bot_token) directly as the HMAC key.
    webapp_secret = hmac.new(
        b"WebAppData",
        bot_token.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    login_secret = hashlib.sha256(bot_token.encode("utf-8")).digest()
    message = dcs.encode("utf-8")
    webapp_expected = hmac.new(webapp_secret, message, hashlib.sha256).hexdigest()
    login_expected = hmac.new(login_secret, message, hashlib.sha256).hexdigest()
    is_webapp = hmac.compare_digest(webapp_expected, check_hash)
    is_login_widget = hmac.compare_digest(login_expected, check_hash)
    if not (is_webapp or is_login_widget):
        return None
    if max_age_sec > 0:
        try:
            ad = int(pairs.get("auth_date", "0") or 0)
        except ValueError:
            return None
        now = int(time.time())
        if not ad or ad > now + 30 or (now - ad) > max_age_sec:
            return None
    uid = _parse_telegram_user_id(pairs) if is_webapp else None
    if is_login_widget:
        try:
            uid = int(pairs.get("id", ""))
        except (TypeError, ValueError):
            uid = None
    if uid is None:
        return None
    out: dict[str, Any] = {**pairs, "user_id": uid}
    if pairs.get("user"):
        out["user_json"] = pairs["user"]
    elif is_login_widget:
        out["user_json"] = json.dumps(
            {
                "id": uid,
                "first_name": pairs.get("first_name", ""),
                "last_name": pairs.get("last_name", ""),
                "username": pairs.get("username", ""),
                "photo_url": pairs.get("photo_url", ""),
            },
            ensure_ascii=False,
        )
    return out
