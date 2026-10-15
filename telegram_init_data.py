"""Telegram Mini App: initData bütünlük doğrulaması (bot token + WebAppData)."""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any
from urllib.parse import parse_qsl


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
    # secret_key = HMAC-SHA-256( key=WebAppData, msg=bot_token )
    secret = hmac.new(
        b"WebAppData",
        bot_token.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    expected = hmac.new(secret, dcs.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, check_hash):
        return None
    if max_age_sec > 0:
        try:
            ad = int(pairs.get("auth_date", "0") or 0)
        except ValueError:
            return None
        if ad and (int(time.time()) - ad) > max_age_sec:
            return None
    uid = _parse_telegram_user_id(pairs)
    if uid is None:
        return None
    out: dict[str, Any] = {**pairs, "user_id": uid}
    if pairs.get("user"):
        out["user_json"] = pairs["user"]
    return out
