"""Cloudflare tunel URL'sini .env + Telegram Mini App menu butonuna yazar."""
from __future__ import annotations

import json
import logging
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
ENV_PATH = ROOT / ".env"
LIVE_URL_PATH = ROOT / "data" / "current_miniapp_url.txt"
MENU_BUTTON_TEXT = "HOTTOK"
TRYCLOUDFLARE_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com", re.I)

logger = logging.getLogger(__name__)

_cached: tuple[str, float] = ("", 0.0)


def _normalize_miniapp_url(raw: str) -> str:
    """Telegram Web App: sadece public https; localhost / 127.0.0.1 / http reddedilir."""
    u = (raw or "").strip()
    for q in ('"', "'"):
        if len(u) >= 2 and u[0] == q and u[-1] == q:
            u = u[1:-1].strip()
    u = u.replace("\r", "").replace("\n", "")
    u = (u or "").split()[0] if u else ""
    if not u:
        return ""
    if not (u.lower().startswith("http://") or u.lower().startswith("https://")):
        u = "https://" + u.lstrip("/")
    if u.lower().startswith("http://"):
        u = "https://" + u[7:]
    p = urlparse(u)
    h = (p.hostname or "").lower()
    if h in ("127.0.0.1", "localhost", "::1") or (h.startswith("127.") and h.count(".") == 3):
        return ""
    return u.rstrip("/")


def extract_trycloudflare_url(text: str) -> str:
    m = TRYCLOUDFLARE_RE.search(text or "")
    return _normalize_miniapp_url(m.group(0) if m else "")


def _read_live_file() -> str:
    try:
        if LIVE_URL_PATH.is_file():
            return _normalize_miniapp_url(LIVE_URL_PATH.read_text(encoding="utf-8"))
    except OSError:
        return ""
    return ""


def get_miniapp_url() -> str:
    """Return only the configured permanent HTTPS site address."""
    global _cached
    now = time.monotonic()
    if now - _cached[1] < 1.0:
        return _cached[0]
    load_dotenv(ENV_PATH, override=False)
    url = _normalize_miniapp_url(os.getenv("MINIAPP_URL") or os.getenv("MINI_APP_URL") or "")
    _cached = (url, now)
    return url


def invalidate_miniapp_url_cache() -> None:
    global _cached
    _cached = ("", 0.0)


def _upsert_env_key(path: Path, key: str, value: str) -> None:
    if path.is_file():
        lines = path.read_text(encoding="utf-8").splitlines()
    else:
        lines = []
    found = False
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            out.append(line)
            continue
        eq = stripped.find("=")
        name = stripped[:eq].strip() if eq > 0 else ""
        if name == key:
            out.append(f"{key}={value}")
            found = True
        else:
            out.append(line)
    if not found:
        if out and out[-1].strip():
            out.append("")
        out.append(f"{key}={value}")
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def _write_live_url(url: str) -> None:
    LIVE_URL_PATH.parent.mkdir(parents=True, exist_ok=True)
    LIVE_URL_PATH.write_text(url + "\n", encoding="utf-8")


def _load_bot_token() -> str:
    load_dotenv(ENV_PATH, override=True)
    return (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()


def set_telegram_menu_button(url: str, token: str | None = None) -> None:
    token = (token or _load_bot_token()).strip()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN yok")
    payload = json.dumps(
        {
            "menu_button": {
                "type": "web_app",
                "text": MENU_BUTTON_TEXT,
                "web_app": {"url": url},
            }
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/setChatMenuButton",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Telegram HTTP {exc.code}: {detail}") from exc
    if not body.get("ok"):
        raise RuntimeError(f"Telegram setChatMenuButton: {body}")


def apply_miniapp_url(raw_url: str, *, push_telegram: bool = True) -> str:
    """Yeni public https URL'yi kaydet ve Telegram menu butonuna bas."""
    url = _normalize_miniapp_url(raw_url)
    if not url:
        raise ValueError(f"Gecersiz Mini App URL: {raw_url!r}")
    _write_live_url(url)
    try:
        _upsert_env_key(ENV_PATH, "MINIAPP_URL", url)
    except OSError as exc:
        logger.warning(".env guncellenemedi: %s", exc)
    os.environ["MINIAPP_URL"] = url
    invalidate_miniapp_url_cache()
    if push_telegram:
        set_telegram_menu_button(url)
    return url
