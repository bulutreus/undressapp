"""
FastAPI: Mini App statik dosyalar + elmas bakiyesi (Telegram initData) + ComfyUI üretim.
Çalıştırma: uvicorn main:app --host 0.0.0.0 --port 8080
Mini App URL'si HTTPS olmalı (Telegram); botta env: MINIAPP_URL bu adrese işaret etmeli.
"""
from __future__ import annotations

import json
import html
import logging
import os
import asyncio
import re
import secrets
import base64
import gzip
import hashlib
from datetime import datetime, timezone
from urllib.parse import quote, unquote, urlencode, urlsplit
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# .env, bot yuklenmeden once (MINIAPP_URL vb. import sirasinda okunur)
load_dotenv(Path(__file__).resolve().parent / ".env", override=True)

import aiohttp
import jwt
import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from jwt import PyJWKClient, PyJWKClientError

from bot import (
    CloLessClient,
    PLAN_STARS_PACKAGES,
    PHOTO_COST_DIAMONDS,
    VIP_PACKAGES,
    _deduct_diamonds,
    _diamonds_total_from_buckets,
    _get_user,
    _grant_starter_trial_if_needed,
    _load_users_db,
    _miniapp_generate_price,
    _miniapp_price_table,
    _save_users_db,
    _users_meta,
    detect_comfyui_url,
)
from telegram_init_data import create_login_session, validate_and_parse_init_data, validate_login_session

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)
_GOOGLE_OIDC_JWKS = PyJWKClient(
    "https://www.googleapis.com/oauth2/v3/certs",
    cache_jwk_set=True,
    timeout=5,
)

# Gereceli yollar: uvicorn farkli cwd ile baslasa bile dosyalar/outputs ayni proje altinda olsun.
PROJECT_DIR = Path(__file__).resolve().parent


def _load_embedded_app_page_manifest(index_path: Path) -> dict[str, str]:
    marker = b'<script id="miniapp-page-manifest" type="application/json">'
    document = index_path.read_bytes()
    start = document.find(marker)
    if start < 0:
        raise ValueError(f"Mini App page manifest is missing from {index_path}")
    start += len(marker)
    end = document.find(b"</script>", start)
    if end < 0:
        raise ValueError(f"Mini App page manifest is incomplete in {index_path}")

    manifest = json.loads(document[start:end].decode("utf-8"))
    if not isinstance(manifest, dict) or not manifest:
        raise ValueError(f"Mini App page manifest is empty in {index_path}")

    page_data_dir = index_path.parent / "page-data"
    pages: dict[str, str] = {}
    for name, version in manifest.items():
        if not isinstance(name, str) or Path(name).name != name or not name.endswith(".html"):
            raise ValueError(f"Invalid page name in Mini App manifest: {name!r}")
        if not isinstance(version, str) or not re.fullmatch(r"[a-f0-9]{64}", version):
            raise ValueError(f"Invalid page version in Mini App manifest: {name}")
        if not (page_data_dir / f"{version}.html.gz").is_file():
            raise ValueError(f"Compressed Mini App page data is missing: {name}")
        pages[name] = version
    return pages


def _read_compressed_app_page(page_path: Path) -> bytes:
    return gzip.decompress(page_path.read_bytes())


def _legacy_asset_cache_control(file_path: Path) -> str:
    fingerprinted_name = re.search(
        r"(?:^|[._-])(?=[a-z0-9_-]{8,}(?:[._-]|$))(?=[a-z0-9_-]*\d)[a-z0-9_-]+(?=[._-]|$)",
        file_path.name,
        re.IGNORECASE,
    )
    if fingerprinted_name:
        return "public, max-age=31536000, immutable"
    return "public, max-age=3600, stale-while-revalidate=86400"


def _normalize_telegram_bot_token(token: str) -> str:
    token = (token or "").strip()
    parts = token.split(":")
    if len(parts) >= 3 and parts[0].isdigit() and parts[0] == parts[1]:
        return parts[0] + ":" + ":".join(parts[2:])
    return token


def _path_from_env(relative_default: str, env_key: str) -> Path:
    """COMFY_*/gibi env; mutlak degilse PROJECT_DIR ile birlestir (cwd degil)."""
    raw = (os.getenv(env_key) or "").strip()
    p = Path(raw or relative_default).expanduser()
    if not p.is_absolute():
        p = PROJECT_DIR / p
    return p


def _resolve_card_prompts_path() -> Path:
    raw = (os.getenv("CARD_PROMPTS_FILE") or "").strip()
    p = Path(raw) if raw else (PROJECT_DIR / "data" / "card_prompts.txt")
    p = p.expanduser()
    if not p.is_absolute():
        p = PROJECT_DIR / p
    return p


@dataclass(frozen=True)
class WebSettings:
    bot_token: str
    comfyui_url: str
    workflow_path: Path
    output_dir: Path
    image_node_id: str | None
    image_field: str
    text_node_id: str | None
    text_field: str
    output_node_id: str | None
    poll_interval_seconds: float
    miniapp_dir: Path

    @classmethod
    def from_env(cls) -> "WebSettings":
        token = _normalize_telegram_bot_token(os.getenv("TELEGRAM_BOT_TOKEN") or "")
        if not token:
            raise ValueError(
                "TELEGRAM_BOT_TOKEN yok. .env icinde tam satir: TELEGRAM_BOT_TOKEN=... (sadece sayi:harf yazi degil; "
                f"ornek: {Path(__file__).resolve().parent / '.env'})"
            )

        workflow_path = _path_from_env("workflows/default-workflow.json", "COMFY_WORKFLOW_PATH")
        output_dir = _path_from_env("outputs", "COMFY_OUTPUT_DIR")

        mini = PROJECT_DIR / "miniapp"
        if not mini.is_dir():
            raise ValueError(f"miniapp dizini bulunamadi: {mini}")

        out_node = (os.getenv("COMFY_OUTPUT_NODE_ID", "64") or "").strip()
        return cls(
            bot_token=token,
            comfyui_url=os.getenv("COMFYUI_URL", "http://127.0.0.1:8002").rstrip("/"),
            workflow_path=workflow_path,
            output_dir=output_dir,
            image_node_id=os.getenv("COMFY_IMAGE_NODE_ID") or None,
            image_field=os.getenv("COMFY_IMAGE_FIELD", "image"),
            # Bos: Text->encoder linkini takip eder (CloLessAi: Text(42) -> Qwen(3))
            text_node_id=os.getenv("COMFY_TEXT_NODE_ID", "") or None,
            text_field=os.getenv("COMFY_TEXT_FIELD", "text"),
            output_node_id=out_node or None,
            poll_interval_seconds=float(os.getenv("COMFY_POLL_INTERVAL_SECONDS", "0.5")),
            miniapp_dir=mini,
        )


def _user_folder_name(parsed: dict) -> str:
    uid = int(parsed.get("user_id", 0))
    raw = (parsed.get("user") or parsed.get("user_json") or "").strip()
    if raw:
        try:
            u = json.loads(raw)
            if isinstance(u, dict):
                un = (u.get("username") or "").strip()
                if un:
                    s = "".join(c for c in un if c.isalnum() or c == "_")
                    if s:
                        return s[:80]
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
    return f"user_{uid}"


def _diamonds_balance_for_api(user_id: int) -> float:
    db = _load_users_db()
    u = _get_user(db, int(user_id))
    if _grant_starter_trial_if_needed(u):
        _save_users_db(db)
    t = _diamonds_total_from_buckets(u)
    d0 = float(u.get("diamonds", 0.0) or 0.0)
    if abs(t - d0) > 1e-6:
        u["diamonds"] = t
        _save_users_db(db)
    return t


def _refund_deducted_components(
    user: dict,
    price: float,
    taken_trial: float,
    taken_vip: float,
) -> None:
    """generate iptal/bos/500: _deduct_diamonds ayni dağılımla geri yükler (deneme + VIP sütunları /my ile uyumlu)."""
    user["diamonds"] = float(user.get("diamonds", 0.0) or 0.0) + float(price)
    user["trial_diamonds"] = float(user.get("trial_diamonds", 0.0) or 0.0) + float(taken_trial)
    user["vip_diamonds"] = float(user.get("vip_diamonds", 0.0) or 0.0) + float(taken_vip)


class BalanceBody(BaseModel):
    init_data: str = Field(default="", max_length=8192)


class TelegramLoginBody(BaseModel):
    init_data: str = Field(..., min_length=1, max_length=8192)


class TelegramOidcBody(BaseModel):
    id_token: str = Field(..., min_length=1, max_length=16384)


class GoogleLoginBody(BaseModel):
    id_token: str = Field(..., min_length=1, max_length=16384)


class SubscriptionInvoiceBody(BaseModel):
    init_data: str = Field(default="", max_length=8192)
    plan: str = Field(..., min_length=1, max_length=16)
    billing: str = Field(..., min_length=1, max_length=16)


class VipInvoiceBody(BaseModel):
    init_data: str = Field(default="", max_length=8192)
    package_id: str = Field(..., min_length=1, max_length=16)


class GalleryDeleteBody(BaseModel):
    init_data: str = Field(default="", max_length=8192)
    rel: str = Field(..., min_length=1, max_length=4000)


def _authenticate_app_request(init_data: str, request: Request, bot_token: str) -> dict | None:
    miniapp_token = _normalize_telegram_bot_token(os.getenv("MINIAPP_BOT_TOKEN") or bot_token)
    parsed = validate_and_parse_init_data((init_data or "").strip(), miniapp_token)
    if parsed:
        return parsed
    return validate_login_session(request.cookies.get("undress_session", ""), bot_token)


def _auth_provider(parsed: dict) -> str:
    raw = parsed.get("user_json") or parsed.get("user") or ""
    try:
        user = json.loads(raw) if isinstance(raw, str) else raw
    except (json.JSONDecodeError, TypeError):
        return "telegram"
    return str(user.get("provider") or "telegram") if isinstance(user, dict) else "telegram"


def _miniapp_bot_token(settings: WebSettings) -> str:
    return _normalize_telegram_bot_token(os.getenv("MINIAPP_BOT_TOKEN") or settings.bot_token)


def _google_client_id() -> str:
    client_id = (os.getenv("GOOGLE_CLIENT_ID") or "").strip()
    if not client_id:
        raise HTTPException(status_code=503, detail="Google sign-in is not configured on the server.")
    return client_id


def _secure_request_cookie(request: Request) -> bool:
    forwarded_proto = request.headers.get("x-forwarded-proto", "").split(",", 1)[0].strip().lower()
    return request.url.scheme == "https" or forwarded_proto == "https"


def _verify_google_id_token(id_token: str, client_id: str, expected_nonce: str) -> dict:
    signing_key = _GOOGLE_OIDC_JWKS.get_signing_key_from_jwt(id_token)
    claims = jwt.decode(
        id_token,
        signing_key.key,
        algorithms=["RS256"],
        audience=client_id,
        issuer=["https://accounts.google.com", "accounts.google.com"],
        leeway=60,
        options={"require": ["exp", "iat", "iss", "aud", "sub", "nonce"]},
    )
    supplied_nonce = str(claims.get("nonce", ""))
    if not secrets.compare_digest(supplied_nonce, expected_nonce):
        raise jwt.InvalidTokenError("Google login nonce does not match.")
    if claims.get("email_verified") is not True:
        raise jwt.InvalidTokenError("Google email address is not verified.")
    return claims


def _get_or_create_google_user(claims: dict) -> tuple[int, dict]:
    subject = str(claims.get("sub") or "").strip()
    email = str(claims.get("email") or "").strip().lower()
    if not subject or not email:
        raise HTTPException(status_code=401, detail="Google did not provide a verified email address.")

    db = _load_users_db()
    meta = _users_meta(db)
    google_accounts = meta.setdefault("google_accounts", {})
    if not isinstance(google_accounts, dict):
        google_accounts = {}
        meta["google_accounts"] = google_accounts

    user_id = 0
    try:
        mapped_id = int(google_accounts.get(subject, 0))
        existing = db.get(str(mapped_id))
        if mapped_id > 0 and isinstance(existing, dict) and existing.get("google_sub") == subject:
            user_id = mapped_id
    except (TypeError, ValueError):
        pass

    if not user_id:
        while True:
            user_id = secrets.randbelow(8_000_000_000_000_000) + 1_000_000_000_000_000
            if str(user_id) not in db:
                break

    full_name = str(claims.get("name") or "").strip()
    email_name = email.partition("@")[0]
    profile = {
        "id": user_id,
        "first_name": str(claims.get("given_name") or full_name or email_name or "Google user"),
        "last_name": str(claims.get("family_name") or ""),
        "photo_url": str(claims.get("picture") or ""),
        "email": email,
        "provider": "google",
    }

    user = _get_user(db, user_id)
    user.update(
        {
            "auth_provider": "google",
            "google_sub": subject,
            "email": email,
            "first_name": profile["first_name"],
            "last_name": profile["last_name"],
            "photo_url": profile["photo_url"],
        }
    )
    google_accounts[subject] = user_id
    _save_users_db(db)
    return user_id, profile


async def _telegram_profile_photo_url(bot_token: str, user_id: int) -> str | None:
    """Bot API ile kullanici profil fotosu URL'si."""
    api_base = f"https://api.telegram.org/bot{bot_token}"
    timeout = aiohttp.ClientTimeout(total=15)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as sess:
            async with sess.get(
                f"{api_base}/getUserProfilePhotos",
                params={"user_id": int(user_id), "limit": 1},
            ) as resp:
                data = await resp.json(content_type=None)
                if resp.status != 200 or not data.get("ok"):
                    return None
                photos = (data.get("result") or {}).get("photos") or []
                if not photos or not photos[0]:
                    return None
                file_id = photos[0][-1].get("file_id")
                if not file_id:
                    return None
            async with sess.get(f"{api_base}/getFile", params={"file_id": file_id}) as resp:
                data = await resp.json(content_type=None)
                if resp.status != 200 or not data.get("ok"):
                    return None
                file_path = (data.get("result") or {}).get("file_path")
                if not file_path:
                    return None
                return f"https://api.telegram.org/file/bot{bot_token}/{file_path}"
    except Exception as exc:
        logger.debug("Profil fotosu alinamadi user_id=%s: %s", user_id, exc)
        return None


def _profile_from_init_user(user_json_raw: str | None) -> tuple[str, str | None]:
    display_name = "User"
    photo_url: str | None = None
    raw = (user_json_raw or "").strip()
    if not raw:
        return display_name, photo_url
    try:
        u = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return display_name, photo_url
    if not isinstance(u, dict):
        return display_name, photo_url
    first = (u.get("first_name") or "").strip()
    last = (u.get("last_name") or "").strip()
    username = (u.get("username") or "").strip()
    if first or last:
        display_name = " ".join(x for x in (first, last) if x)
    elif username:
        display_name = f"@{username}"
    photo_raw = (u.get("photo_url") or "").strip()
    if photo_raw:
        photo_url = photo_raw
    return display_name, photo_url



def _load_card_prompts_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError:
        return out
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        key = k.strip().lower()
        val = v.strip()
        if key and val:
            out[key] = val
    return out


def _resolve_prompt_for_generate(
    mapping: dict[str, str],
    card_key: str,
    media_category: str,
    media_type: str,
    form_prompt: str | None,
) -> str | None:
    """Kart promptu + form/Telegram promptunu birlestirip tek prompt dondurur."""
    fp = (form_prompt or "").strip()
    ck = (card_key or "").strip().lower()
    candidates: list[str] = []
    if ck:
        candidates.append(ck)
        if "." in ck:
            candidates.append(Path(ck).stem.lower())
    mg = (media_category or "undress").strip().lower()
    candidates.append(mg)
    if (media_type or "").strip().lower() == "video":
        candidates.append("video")
    card_prompt: str | None = None
    for c in candidates:
        if c and c in mapping:
            card_prompt = mapping[c]
            break
    if card_prompt and fp:
        # Kartin temel stili korunur; Telegram/form promptu detay olarak eklenir.
        return f"{card_prompt}\n\n{fp}"
    if fp:
        return fp
    return card_prompt


def _gallery_image_paths_user_folder(user_root: Path) -> list[Path]:
    """Ciktilar 'sonrasi/'; oncesi (yukleme) listelenmez; alt klasorler dahil (rglob)."""
    exts = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
    seen: set[Path] = set()
    paths: list[Path] = []
    sonrasi = user_root / "sonrasi"
    if sonrasi.is_dir():
        for p in sonrasi.rglob("*"):
            if p.is_file() and p.suffix.lower() in exts:
                rp = p.resolve()
                if rp not in seen:
                    seen.add(rp)
                    paths.append(p)
    for p in user_root.iterdir():
        if p.is_file() and p.suffix.lower() in exts:
            rp = p.resolve()
            if rp not in seen:
                seen.add(rp)
                paths.append(p)
    return paths


def _gallery_files_for_user(output_dir: Path, parsed: dict) -> list[dict[str, str]]:
    user_root = output_dir / _user_folder_name(parsed)
    if not user_root.is_dir():
        return []
    items: list[tuple[float, Path]] = []
    for p in _gallery_image_paths_user_folder(user_root):
        try:
            items.append((p.stat().st_mtime, p))
        except OSError:
            continue
    items.sort(key=lambda x: x[0], reverse=True)
    out: list[dict[str, str]] = []
    out_root = output_dir.resolve()
    for _, p in items:
        try:
            rel = p.resolve().relative_to(out_root)
        except ValueError:
            logger.warning("Galeri: yol diske gore cozumlenemedi: %s", p)
            continue
        out.append(
            {
                "url": "/outputs/" + rel.as_posix(),
                "name": p.name,
                "rel": rel.as_posix(),
            }
        )
    return out


def _delete_gallery_file_for_user(*, output_dir: Path, parsed: dict, rel_raw: str) -> None:
    """Yalnizca kullanici ciktilari altindaki gercek dosyayi siler; path traversal engellenir."""
    out_root = output_dir.resolve()
    user_root = (out_root / _user_folder_name(parsed)).resolve()
    part = (rel_raw or "").replace("\\", "/").strip()
    if not part or part.startswith("/") or ".." in part.split("/"):
        raise HTTPException(status_code=400, detail="Invalid path.")
    target = (out_root / part).resolve()
    try:
        target.relative_to(out_root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid path.") from exc
    try:
        target.relative_to(user_root)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="Access to this file is denied.") from exc
    if not target.is_file():
        raise HTTPException(status_code=404, detail="File not found or already deleted.")
    try:
        target.unlink()
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Could not delete file.") from exc


def create_app() -> FastAPI:
    app = FastAPI(title="CloLess Mini App API", version="1.0.0")
    telegram_sign_in_paths = {
        "/api/auth/telegram",
        "/api/auth/telegram/oidc-config",
        "/api/auth/telegram/oidc/start",
        "/api/auth/telegram/oidc/callback",
        "/api/auth/telegram/oidc",
    }

    async def refresh_embedded_app_page_manifest() -> None:
        index_path = app.state.settings.miniapp_dir / "index.html"
        try:
            modified_ns = index_path.stat().st_mtime_ns
        except OSError:
            logger.exception("Could not stat the Mini App index file")
            return
        if modified_ns == app.state.embedded_app_page_manifest_mtime_ns:
            return

        async with app.state.embedded_app_page_manifest_lock:
            try:
                modified_ns = index_path.stat().st_mtime_ns
            except OSError:
                logger.exception("Could not stat the Mini App index file")
                return
            if modified_ns == app.state.embedded_app_page_manifest_mtime_ns:
                return
            try:
                manifest = await asyncio.to_thread(_load_embedded_app_page_manifest, index_path)
            except Exception:
                logger.exception("Could not reload the Mini App page manifest")
                return
            app.state.embedded_app_page_manifest = manifest
            app.state.embedded_app_page_manifest_mtime_ns = modified_ns

    @app.middleware("http")
    async def disable_telegram_web_sign_in(request: Request, call_next):
        if request.url.path in telegram_sign_in_paths:
            return JSONResponse(
                {"detail": "Telegram web sign-in is disabled. Continue with Google instead."},
                status_code=410,
            )
        return await call_next(request)
    app.add_middleware(GZipMiddleware, minimum_size=1024, compresslevel=5)
    _cors = (os.getenv("CORS_ALLOW_ORIGINS") or "*").strip()
    if _cors == "*":
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    else:
        origins = [o.strip() for o in _cors.split(",") if o.strip()]
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @app.on_event("startup")
    async def on_startup() -> None:
        settings = WebSettings.from_env()
        access_client_id = os.getenv("COMFYUI_ACCESS_CLIENT_ID", "").strip()
        access_client_secret = os.getenv("COMFYUI_ACCESS_CLIENT_SECRET", "").strip()
        if bool(access_client_id) != bool(access_client_secret):
            raise ValueError(
                "Cloudflare Access icin COMFYUI_ACCESS_CLIENT_ID ve "
                "COMFYUI_ACCESS_CLIENT_SECRET birlikte ayarlanmalidir."
            )
        comfyui_headers = (
            {
                "CF-Access-Client-Id": access_client_id,
                "CF-Access-Client-Secret": access_client_secret,
            }
            if access_client_id and access_client_secret
            else None
        )
        resolved_url = await detect_comfyui_url(
            settings.comfyui_url,
            request_headers=comfyui_headers,
        )
        settings = WebSettings(
            bot_token=settings.bot_token,
            comfyui_url=resolved_url,
            workflow_path=settings.workflow_path,
            output_dir=settings.output_dir,
            image_node_id=settings.image_node_id,
            image_field=settings.image_field,
            text_node_id=settings.text_node_id,
            text_field=settings.text_field,
            output_node_id=settings.output_node_id,
            poll_interval_seconds=settings.poll_interval_seconds,
            miniapp_dir=settings.miniapp_dir,
        )
        settings.output_dir.mkdir(parents=True, exist_ok=True)
        app.state.settings = settings
        manifest_path = settings.miniapp_dir / "index.html"
        app.state.embedded_app_page_manifest = await asyncio.to_thread(
            _load_embedded_app_page_manifest,
            manifest_path,
        )
        app.state.embedded_app_page_manifest_mtime_ns = manifest_path.stat().st_mtime_ns
        app.state.embedded_app_page_manifest_lock = asyncio.Lock()
        app.state.embedded_app_page_data_dir = settings.miniapp_dir / "page-data"
        app.state.session = aiohttp.ClientSession(
            base_url=settings.comfyui_url,
            headers=comfyui_headers,
            connector=aiohttp.TCPConnector(limit=100, keepalive_timeout=30),
        )
        app.state.client = CloLessClient(settings, app.state.session)
        out = settings.output_dir
        app.mount(
            "/outputs",
            StaticFiles(directory=str(out)),
            name="outputs",
        )
        assets_dir = PROJECT_DIR / "assets"
        if assets_dir.is_dir():
            app.mount(
                "/assets",
                StaticFiles(directory=str(assets_dir)),
                name="assets",
            )
        miniapp_fonts_dir = assets_dir / "miniapp" / "fonts"
        if miniapp_fonts_dir.is_dir():
            app.mount(
                "/fonts",
                StaticFiles(directory=str(miniapp_fonts_dir)),
                name="miniapp_fonts",
            )
        pro_files_dir = PROJECT_DIR / "assets" / "legacy-endpoints" / "pro_files"
        if pro_files_dir.is_dir():
            app.mount(
                "/pro_files",
                StaticFiles(directory=str(pro_files_dir)),
                name="pro_files",
            )
        login_assets_dir = PROJECT_DIR / "assets" / "legacy-endpoints" / "login_files"
        if login_assets_dir.is_dir():
            app.mount(
                "/login_files",
                StaticFiles(directory=str(login_assets_dir)),
                name="login_files",
            )
        static_dir = settings.miniapp_dir
        if static_dir.is_dir():
            app.mount(
                "/",
                StaticFiles(directory=str(static_dir), html=True),
                name="miniapp",
            )
        prompts_path = _resolve_card_prompts_path()
        app.state.card_prompts = _load_card_prompts_file(prompts_path)
        logger.info(
            "Card prompts: %d keys from %s",
            len(app.state.card_prompts or {}),
            prompts_path,
        )
        logger.info("Mini App: %s | ComfyUI: %s", static_dir, settings.comfyui_url)

    @app.on_event("shutdown")
    async def on_shutdown() -> None:
        session = getattr(app.state, "session", None)
        if session is not None:
            await session.close()

    @app.get("/favicon.svg", include_in_schema=False)
    async def favicon_svg() -> FileResponse:
        return FileResponse(PROJECT_DIR / "assets" / "branding" / "favicon.svg")

    @app.get("/favicon.webp", include_in_schema=False)
    async def favicon_webp() -> FileResponse:
        return FileResponse(PROJECT_DIR / "assets" / "branding" / "favicon.webp")

    @app.get("/health")
    async def health() -> JSONResponse:
        settings: WebSettings = app.state.settings
        return JSONResponse({"ok": True, "comfyui_url": settings.comfyui_url})

    @app.get("/__miniapp/pages/{page_name}/{version}", include_in_schema=False)
    async def embedded_miniapp_page(page_name: str, version: str) -> FileResponse:
        await refresh_embedded_app_page_manifest()
        if Path(page_name).name != page_name or not page_name.endswith(".html"):
            raise HTTPException(status_code=404, detail="Page not found.")
        expected_version = app.state.embedded_app_page_manifest.get(page_name)
        if expected_version is None or not secrets.compare_digest(expected_version, version):
            raise HTTPException(status_code=404, detail="Page not found.")

        page_path = app.state.embedded_app_page_data_dir / f"{expected_version}.html.gz"
        if not page_path.is_file():
            raise HTTPException(status_code=404, detail="Page not found.")
        return FileResponse(
            page_path,
            media_type="text/html",
            headers={
                "Cache-Control": "public, max-age=31536000, immutable",
                "Content-Encoding": "gzip",
                "ETag": f'"{expected_version}"',
                "Vary": "Accept-Encoding",
            },
        )

    @app.get("/login")
    @app.get("/login.html")
    async def login_page() -> HTMLResponse:
        await refresh_embedded_app_page_manifest()
        page_version = app.state.embedded_app_page_manifest.get("login.html")
        if page_version is None:
            raise HTTPException(status_code=500, detail="Google login page is unavailable.")

        page_path = app.state.embedded_app_page_data_dir / f"{page_version}.html.gz"
        try:
            page = await asyncio.to_thread(_read_compressed_app_page, page_path)
        except (OSError, EOFError, gzip.BadGzipFile) as exc:
            logger.exception("Failed to read the Google login page")
            raise HTTPException(status_code=500, detail="Google login page is unavailable.") from exc

        contents = page.decode("utf-8-sig")
        head_match = re.search(r"<head\b[^>]*>", contents, re.IGNORECASE)
        if head_match is None:
            raise HTTPException(status_code=500, detail="Google login page has no head element.")
        if not re.search(r"<base\b", contents[head_match.end():], re.IGNORECASE):
            contents = contents[:head_match.end()] + '<base href="/"> ' + contents[head_match.end():]

        return HTMLResponse(contents, headers={"Cache-Control": "no-cache"})

    @app.get("/pro")
    async def pro_page() -> FileResponse:
        return FileResponse(
            app.state.settings.miniapp_dir / "index.html",
            media_type="text/html",
            headers={"Cache-Control": "no-cache"},
        )

    @app.get("/creator")
    async def creator_page() -> FileResponse:
        return FileResponse(
            app.state.settings.miniapp_dir / "index.html",
            media_type="text/html",
            headers={"Cache-Control": "no-cache"},
        )

    @app.get("/api/miniapp/config")
    async def miniapp_config() -> JSONResponse:
        # The configured username is the payment bot. Only discover a username from
        # the active token when no explicit payment bot has been configured.
        bot_username = (os.getenv("BOT_USERNAME") or "").strip().lstrip("@")
        bot_token = (app.state.settings.bot_token or "").strip()
        if bot_token and not bot_username:
            try:
                timeout = aiohttp.ClientTimeout(total=5)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(f"https://api.telegram.org/bot{bot_token}/getMe") as response:
                        result = await response.json(content_type=None)
                if result.get("ok") and isinstance(result.get("result"), dict):
                    bot_username = str(result["result"].get("username") or "").strip().lstrip("@")
            except Exception:
                logger.warning("Could not resolve Telegram bot username from configured token")
        buy_url = f"https://t.me/{bot_username}?start=buy" if bot_username else ""
        bot_url = f"https://t.me/{bot_username}?start=welcome" if bot_username else ""
        prices = _miniapp_price_table()
        return JSONResponse(
            {
                "ok": True,
                "bot_username": bot_username,
                "bot_url": bot_url,
                "buy_url": buy_url,
                "prices": prices,
                "photo_cost": prices["undress"],
            }
        )

    @app.get("/api/auth/google/config")
    async def google_login_config(request: Request) -> JSONResponse:
        client_id = _google_client_id()
        nonce = secrets.token_urlsafe(32)
        response = JSONResponse({"ok": True, "client_id": client_id, "nonce": nonce})
        response.headers["Cache-Control"] = "no-store"
        response.set_cookie(
            key="google_oidc_nonce",
            value=nonce,
            max_age=600,
            httponly=True,
            secure=_secure_request_cookie(request),
            samesite="lax",
            path="/",
        )
        return response

    @app.post("/api/auth/google")
    async def google_login(body: GoogleLoginBody, request: Request) -> JSONResponse:
        settings: WebSettings = app.state.settings
        expected_nonce = request.cookies.get("google_oidc_nonce", "")
        if not expected_nonce:
            raise HTTPException(status_code=401, detail="Google sign-in expired. Please try again.")

        try:
            claims = await asyncio.to_thread(
                _verify_google_id_token,
                body.id_token,
                _google_client_id(),
                expected_nonce,
            )
        except PyJWKClientError as exc:
            logger.warning("Google OIDC signing keys unavailable: %s", str(exc)[:200])
            raise HTTPException(status_code=502, detail="Google sign-in verification is temporarily unavailable.") from exc
        except jwt.PyJWTError as exc:
            logger.info("Google OIDC token rejected (%s): %s", type(exc).__name__, str(exc)[:200])
            raise HTTPException(status_code=401, detail="Google sign-in could not be verified. Please try again.") from exc

        user_id, user_data = _get_or_create_google_user(claims)
        login_response = JSONResponse({"ok": True, "user_id": user_id})
        login_response.headers["Cache-Control"] = "no-store"
        login_response.set_cookie(
            key="undress_session",
            value=create_login_session(user_data, settings.bot_token),
            max_age=30 * 86400,
            httponly=True,
            secure=_secure_request_cookie(request),
            samesite="lax",
            path="/",
        )
        login_response.delete_cookie(
            key="google_oidc_nonce",
            path="/",
            httponly=True,
            secure=_secure_request_cookie(request),
            samesite="lax",
        )
        return login_response

    @app.post("/api/auth/telegram")
    async def telegram_login(body: TelegramLoginBody) -> JSONResponse:
        settings: WebSettings = app.state.settings
        parsed = validate_and_parse_init_data(body.init_data, _miniapp_bot_token(settings))
        if not parsed:
            raise HTTPException(status_code=401, detail="Telegram sign-in could not be verified or has expired.")
        user_data = {
            "id": int(parsed["user_id"]),
            "first_name": parsed.get("first_name", ""),
            "last_name": parsed.get("last_name", ""),
            "username": parsed.get("username", ""),
            "photo_url": parsed.get("photo_url", ""),
        }
        login_response = JSONResponse({"ok": True, "user_id": user_data["id"]})
        login_response.set_cookie(
            key="undress_session",
            value=create_login_session(user_data, settings.bot_token),
            max_age=30 * 86400,
            httponly=True,
            secure=True,
            samesite="lax",
            path="/",
        )
        return login_response

    @app.get("/api/auth/telegram/oidc-config")
    async def telegram_oidc_config() -> JSONResponse:
        if (os.getenv("TELEGRAM_LOGIN_CLIENT_SECRET") or "").strip():
            client_id, _, _ = _telegram_oidc_config()
            mode = "oidc"
        else:
            client_id = _telegram_oidc_client_id()
            mode = "library"
        nonce = secrets.token_urlsafe(32)
        response = JSONResponse(
            {
                "ok": True,
                "mode": mode,
                "client_id": client_id,
                "nonce": nonce,
            }
        )
        response.set_cookie(
            key="telegram_oidc_nonce",
            value=nonce,
            max_age=600,
            httponly=True,
            secure=True,
            samesite="lax",
            path="/",
        )
        return response

    @app.get("/api/auth/telegram/oidc/start")
    async def telegram_oidc_start(next: str = "/Image.html") -> RedirectResponse:
        client_id, _, redirect_uri = _telegram_oidc_config()
        state = secrets.token_urlsafe(32)
        verifier = secrets.token_urlsafe(64)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).rstrip(b"=").decode("ascii")
        nonce = secrets.token_urlsafe(32)
        query = urlencode(
            {
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "scope": "openid profile",
                "state": state,
                "nonce": nonce,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            }
        )
        response = RedirectResponse(f"https://oauth.telegram.org/auth?{query}", status_code=302)
        cookie_options = {
            "max_age": 600,
            "httponly": True,
            "secure": True,
            "samesite": "lax",
            "path": "/",
        }
        response.set_cookie("telegram_oidc_state", state, **cookie_options)
        response.set_cookie("telegram_oidc_verifier", verifier, **cookie_options)
        response.set_cookie("telegram_oidc_nonce", nonce, **cookie_options)
        response.set_cookie("telegram_oidc_next", _safe_login_return_path(next), **cookie_options)
        return response

    @app.get("/api/auth/telegram/oidc/callback")
    async def telegram_oidc_callback(request: Request, code: str = "", state: str = "", error: str = "") -> RedirectResponse:
        return_path = _safe_login_return_path(request.cookies.get("telegram_oidc_next"))

        def failed(reason: str = "telegram_signin_failed") -> RedirectResponse:
            query = urlencode({"auth_error": reason, "next": return_path})
            response = RedirectResponse(f"/login.html?{query}", status_code=303)
            _telegram_oidc_clear_cookies(response)
            return response

        if error:
            return failed("telegram_signin_cancelled" if error == "access_denied" else "telegram_signin_failed")

        expected_state = request.cookies.get("telegram_oidc_state", "")
        verifier = request.cookies.get("telegram_oidc_verifier", "")
        expected_nonce = request.cookies.get("telegram_oidc_nonce", "")
        if not code or not state or not expected_state or not secrets.compare_digest(state, expected_state):
            return failed()
        if not verifier or not expected_nonce:
            return failed("telegram_signin_expired")

        try:
            client_id, client_secret, redirect_uri = _telegram_oidc_config()
            timeout = aiohttp.ClientTimeout(total=20)
            async with aiohttp.ClientSession(
                timeout=timeout,
                auth=aiohttp.BasicAuth(client_id, client_secret),
            ) as session:
                async with session.post(
                    "https://oauth.telegram.org/token",
                    data={
                        "grant_type": "authorization_code",
                        "code": code,
                        "redirect_uri": redirect_uri,
                        "client_id": client_id,
                        "code_verifier": verifier,
                    },
                ) as token_response:
                    token_data = await token_response.json(content_type=None)
                    if token_response.status != 200 or not isinstance(token_data, dict):
                        logger.warning("Telegram OIDC code exchange failed with HTTP %s", token_response.status)
                        return failed()
            id_token = str(token_data.get("id_token") or "")
            if not id_token:
                logger.warning("Telegram OIDC token response did not contain an ID token")
                return failed()
            claims = await asyncio.to_thread(
                _verify_telegram_oidc_token,
                id_token,
                client_id,
                expected_nonce,
            )
        except PyJWKClientError as exc:
            logger.warning("Telegram OIDC signing keys unavailable: %s", str(exc)[:200])
            return failed("telegram_signin_unavailable")
        except jwt.PyJWTError as exc:
            logger.info("Telegram OIDC token rejected: %s", str(exc)[:200])
            return failed()
        except HTTPException as exc:
            logger.warning("Telegram OIDC callback configuration error: %s", exc.detail)
            return failed("telegram_signin_unavailable")
        except Exception as exc:
            logger.warning("Telegram OIDC callback failed: %s", str(exc)[:200])
            return failed("telegram_signin_unavailable")

        try:
            user_id = int(claims.get("id") or claims.get("sub") or 0)
        except (TypeError, ValueError):
            user_id = 0
        if user_id <= 0:
            return failed()
        full_name = str(claims.get("name") or "").strip()
        user_data = {
            "id": user_id,
            "first_name": str(claims.get("given_name") or full_name or claims.get("preferred_username") or "Telegram user"),
            "last_name": str(claims.get("family_name") or ""),
            "username": str(claims.get("preferred_username") or ""),
            "photo_url": str(claims.get("picture") or ""),
        }
        response = RedirectResponse(return_path, status_code=303)
        response.set_cookie(
            key="undress_session",
            value=create_login_session(user_data, app.state.settings.bot_token),
            max_age=30 * 86400,
            httponly=True,
            secure=True,
            samesite="lax",
            path="/",
        )
        _telegram_oidc_clear_cookies(response)
        return response

    @app.post("/api/auth/telegram/oidc")
    async def telegram_oidc_login(body: TelegramOidcBody, request: Request) -> JSONResponse:
        settings: WebSettings = app.state.settings
        client_id = (os.getenv("TELEGRAM_LOGIN_CLIENT_ID") or "").strip()
        expected_nonce = request.cookies.get("telegram_oidc_nonce", "")
        if not client_id or not expected_nonce:
            raise HTTPException(status_code=401, detail="Telegram sign-in expired. Please try again.")

        try:
            claims = await asyncio.to_thread(
                _verify_telegram_oidc_token,
                body.id_token,
                client_id,
                expected_nonce,
            )
        except PyJWKClientError as exc:
            logger.warning("Telegram OIDC signing keys unavailable: %s", str(exc)[:200])
            raise HTTPException(status_code=502, detail="Telegram sign-in verification is temporarily unavailable.") from exc
        except jwt.PyJWTError as exc:
            logger.warning("Telegram OIDC token rejected (%s): %s", type(exc).__name__, str(exc)[:200])
            if isinstance(exc, jwt.InvalidAudienceError):
                detail = "Telegram sign-in failed: the token audience does not match this bot."
            elif isinstance(exc, jwt.InvalidIssuerError):
                detail = "Telegram sign-in failed: the token was not issued by Telegram."
            elif isinstance(exc, jwt.ExpiredSignatureError):
                detail = "Telegram sign-in expired. Please try again."
            elif isinstance(exc, jwt.InvalidSignatureError):
                detail = "Telegram sign-in failed: Telegram's token signature could not be verified."
            else:
                detail = "Telegram sign-in failed: the token is invalid or its nonce does not match."
            raise HTTPException(status_code=401, detail=detail) from exc
        except Exception as exc:
            logger.warning("Telegram OIDC verification unavailable: %s", str(exc)[:200])
            raise HTTPException(status_code=502, detail="Telegram sign-in verification is temporarily unavailable.") from exc

        try:
            user_id = int(claims.get("id") or claims.get("sub") or 0)
        except (TypeError, ValueError):
            user_id = 0
        if user_id <= 0:
            raise HTTPException(status_code=401, detail="Telegram account ID is missing.")

        full_name = str(claims.get("name") or "").strip()
        first_name = str(claims.get("given_name") or full_name or claims.get("preferred_username") or "Telegram user")
        user_data = {
            "id": user_id,
            "first_name": first_name,
            "last_name": str(claims.get("family_name") or ""),
            "username": str(claims.get("preferred_username") or ""),
            "photo_url": str(claims.get("picture") or ""),
        }
        login_response = JSONResponse({"ok": True, "user_id": user_id})
        login_response.set_cookie(
            key="undress_session",
            value=create_login_session(user_data, settings.bot_token),
            max_age=30 * 86400,
            httponly=True,
            secure=True,
            samesite="lax",
            path="/",
        )
        login_response.delete_cookie(
            key="telegram_oidc_nonce",
            path="/",
            httponly=True,
            secure=True,
            samesite="lax",
        )
        return login_response

    @app.get("/api/auth/session")
    async def auth_session(request: Request) -> JSONResponse:
        settings: WebSettings = app.state.settings
        parsed = validate_login_session(request.cookies.get("undress_session", ""), settings.bot_token)
        if not parsed:
            raise HTTPException(status_code=401, detail="Session not found or expired.")
        try:
            user = json.loads(parsed.get("user_json", "{}"))
        except (json.JSONDecodeError, TypeError):
            user = {}
        return JSONResponse(
            {
                "ok": True,
                "user_id": int(parsed["user_id"]),
                "first_name": str(user.get("first_name", "")),
                "last_name": str(user.get("last_name", "")),
                "username": str(user.get("username", "")),
                "photo_url": str(user.get("photo_url", "")),
                "email": str(user.get("email", "")),
                "provider": str(user.get("provider", "telegram")),
            }
        )

    @app.post("/api/auth/logout")
    async def telegram_logout() -> JSONResponse:
        logout_response = JSONResponse({"ok": True})
        logout_response.delete_cookie("undress_session", path="/", httponly=True, secure=True, samesite="lax")
        return logout_response

    @app.post("/api/miniapp/balance")
    async def miniapp_balance(body: BalanceBody, request: Request) -> JSONResponse:
        settings: WebSettings = app.state.settings
        parsed = _authenticate_app_request(body.init_data, request, settings.bot_token)
        if not parsed:
            raise HTTPException(status_code=401, detail="Telegram session data is invalid or expired.")
        uid = int(parsed["user_id"])
        total = _diamonds_balance_for_api(uid)
        return JSONResponse(
            {
                "ok": True,
                "diamonds": total,
                "photo_cost": float(PHOTO_COST_DIAMONDS),
                "user_id": uid,
            }
        )

    @app.post("/api/miniapp/game-credit-promo")
    async def miniapp_game_credit_promo(body: BalanceBody, request: Request) -> JSONResponse:
        settings: WebSettings = app.state.settings
        parsed = _authenticate_app_request(body.init_data, request, settings.bot_token)
        if not parsed:
            raise HTTPException(status_code=401, detail="Sign in with Telegram to claim this reward.")

        uid = int(parsed["user_id"])
        db = _load_users_db()
        user = _get_user(db, uid)
        starter_trial_added = _grant_starter_trial_if_needed(user)
        already_claimed = bool(user.get("game_t_100_promo_claimed"))
        if already_claimed:
            if starter_trial_added:
                _save_users_db(db)
            return JSONResponse(
                {
                    "ok": True,
                    "awarded": False,
                    "credits_awarded": 0,
                    "diamonds": _diamonds_total_from_buckets(user),
                }
            )

        user["vip_diamonds"] = float(user.get("vip_diamonds", 0.0) or 0.0) + 100
        user["game_t_100_promo_claimed"] = True
        user["diamonds"] = _diamonds_total_from_buckets(user)
        _save_users_db(db)
        return JSONResponse(
            {
                "ok": True,
                "awarded": True,
                "credits_awarded": 100,
                "diamonds": user["diamonds"],
            }
        )

    @app.post("/api/miniapp/vip-invoice")
    async def miniapp_vip_invoice(body: VipInvoiceBody, request: Request) -> JSONResponse:
        settings: WebSettings = app.state.settings
        parsed = _authenticate_app_request(body.init_data, request, settings.bot_token)
        if not parsed:
            raise HTTPException(status_code=401, detail="Telegram session could not be verified.")
        if _auth_provider(parsed) == "google":
            raise HTTPException(status_code=403, detail="Telegram Stars purchases require a Telegram account.")

        package = VIP_PACKAGES.get(body.package_id.strip().lower())
        if not package:
            raise HTTPException(status_code=400, detail="Credit package not found.")

        vip_amount, stars, _label = package
        package_id = body.package_id.strip().lower()
        user_id = int(parsed["user_id"])
        title = f"{int(vip_amount)} VIP Credits"
        payload = f"vip|{package_id}|{user_id}"
        request_body = {
            "title": title,
            "description": f"{int(vip_amount)} VIP credits package",
            "payload": payload,
            "provider_token": "",
            "currency": "XTR",
            "prices": [{"label": title, "amount": int(stars)}],
        }
        api_url = f"https://api.telegram.org/bot{settings.bot_token}/createInvoiceLink"
        try:
            async with app.state.session.post(api_url, json=request_body) as response:
                result = await response.json(content_type=None)
        except aiohttp.ClientError as exc:
            logger.warning("Telegram VIP invoice link request failed: %s", exc)
            raise HTTPException(status_code=502, detail="Telegram invoice link could not be created.") from exc
        if not isinstance(result, dict) or not result.get("ok") or not result.get("result"):
            logger.warning("Telegram VIP invoice link rejected: %s", str(result)[:400])
            raise HTTPException(status_code=502, detail="Telegram invoice link could not be created.")
        return JSONResponse({"ok": True, "invoice_url": result["result"], "stars": int(stars)})

    @app.post("/api/miniapp/subscription-invoice")
    async def miniapp_subscription_invoice(body: SubscriptionInvoiceBody, request: Request) -> JSONResponse:
        settings: WebSettings = app.state.settings
        parsed = _authenticate_app_request(body.init_data, request, settings.bot_token)
        if body.init_data.strip() and not parsed:
            raise HTTPException(status_code=401, detail="Telegram session could not be verified.")
        if parsed and _auth_provider(parsed) == "google":
            raise HTTPException(status_code=403, detail="Telegram Stars subscriptions require a Telegram account.")

        plan = body.plan.strip().lower()
        billing = body.billing.strip().lower()
        plan_id = f"{plan}_{billing}"
        plan_package = PLAN_STARS_PACKAGES.get(plan_id)
        if not plan_package:
            raise HTTPException(status_code=400, detail="This plan cannot be purchased with Telegram Stars.")

        _plan, _billing, stars, _days = plan_package
        months = 12 if billing == "yearly" else 1
        title = f"{plan.title()} Plan"
        description = f"{plan.title()} Plan, {months} mo."
        user_id = int(parsed["user_id"]) if parsed else None
        payload = f"plan|{plan_id}|{user_id}" if user_id else f"plan|{plan_id}"
        api_url = f"https://api.telegram.org/bot{settings.bot_token}/createInvoiceLink"
        request_body = {
            "title": title,
            "description": description,
            "payload": payload,
            "provider_token": "",
            "currency": "XTR",
            "prices": [{"label": title, "amount": stars}],
        }
        try:
            async with app.state.session.post(api_url, json=request_body) as response:
                result = await response.json(content_type=None)
        except aiohttp.ClientError as exc:
            logger.warning("Telegram invoice link request failed: %s", exc)
            raise HTTPException(status_code=502, detail="Telegram payment link could not be created.") from exc
        if not isinstance(result, dict) or not result.get("ok") or not result.get("result"):
            logger.warning("Telegram invoice link rejected: %s", str(result)[:400])
            raise HTTPException(status_code=502, detail="Telegram payment link could not be created.")
        return JSONResponse({"ok": True, "invoice_url": result["result"], "stars": stars})

    @app.post("/api/miniapp/profile")
    async def miniapp_profile(body: BalanceBody, request: Request) -> JSONResponse:
        settings: WebSettings = app.state.settings
        parsed = _authenticate_app_request(body.init_data, request, settings.bot_token)
        if not parsed:
            raise HTTPException(status_code=401, detail="Telegram session data is invalid or expired.")
        uid = int(parsed["user_id"])
        display_name, photo_url = _profile_from_init_user(parsed.get("user_json") or parsed.get("user"))
        if not photo_url and _auth_provider(parsed) == "telegram":
            photo_url = await _telegram_profile_photo_url(settings.bot_token, uid)
        username = ""
        email = ""
        raw = (parsed.get("user_json") or parsed.get("user") or "").strip()
        profile_user = {}
        if raw:
            try:
                u = json.loads(raw)
                if isinstance(u, dict):
                    profile_user = u
                    username = (u.get("username") or "").strip()
                    email = (u.get("email") or "").strip()
            except (json.JSONDecodeError, TypeError):
                pass
        diamonds = _diamonds_balance_for_api(uid)
        db = _load_users_db()
        account = _get_user(db, uid)
        expires_at = str(account.get("subscription_expires_at") or "")
        subscription_plan = str(account.get("subscription_plan") or "")
        subscription_active = False
        if expires_at:
            try:
                expiry = datetime.fromisoformat(expires_at)
                if expiry.tzinfo is None:
                    expiry = expiry.replace(tzinfo=timezone.utc)
                subscription_active = expiry > datetime.now(timezone.utc)
            except ValueError:
                logger.warning("Invalid subscription expiry stored for user %s", uid)
        return JSONResponse(
            {
                "ok": True,
                "user_id": uid,
                "display_name": display_name,
                "username": username,
                "email": email,
                "provider": str(profile_user.get("provider") or "telegram"),
                "photo_url": photo_url or "",
                "diamonds": diamonds,
                "membership": {
                    "plan": subscription_plan,
                    "expires_at": expires_at,
                    "active": subscription_active,
                },
            }
        )

    @app.post("/api/miniapp/gallery")
    async def miniapp_gallery(body: BalanceBody, request: Request) -> JSONResponse:
        settings: WebSettings = app.state.settings
        parsed = _authenticate_app_request(body.init_data, request, settings.bot_token)
        if not parsed:
            raise HTTPException(status_code=401, detail="Telegram session data is invalid or expired.")
        files = _gallery_files_for_user(settings.output_dir, parsed)
        return JSONResponse({"ok": True, "files": files})

    @app.api_route("/api/miniapp/gallery/delete", methods=["POST", "DELETE"])
    async def miniapp_gallery_delete(body: GalleryDeleteBody, request: Request) -> JSONResponse:
        settings: WebSettings = app.state.settings
        parsed = _authenticate_app_request(body.init_data, request, settings.bot_token)
        if not parsed:
            raise HTTPException(status_code=401, detail="Telegram session data is invalid or expired.")
        _delete_gallery_file_for_user(
            output_dir=settings.output_dir, parsed=parsed, rel_raw=body.rel
        )
        return JSONResponse({"ok": True})

    @app.post("/api/generate")
    async def generate(
        request: Request,
        image: UploadFile = File(...),
        init_data: str = Form(default=""),
        prompt: str | None = Form(default=None),
        media_type: str = Form(default="image"),
        media_category: str = Form(default="undress"),
        card_key: str = Form(default=""),
        client_price: str | None = Form(default=None),
    ) -> JSONResponse:
        settings: WebSettings = app.state.settings
        client: CloLessClient = app.state.client

        parsed = _authenticate_app_request((init_data or "").strip(), request, settings.bot_token)
        if not parsed:
            raise HTTPException(status_code=401, detail="Telegram session data is invalid or expired.")

        prompts_path = _resolve_card_prompts_path()
        card_prompts = _load_card_prompts_file(prompts_path)
        app.state.card_prompts = card_prompts

        uid = int(parsed["user_id"])
        media_kind = (media_type or "image").strip().lower()
        media_group = (media_category or "undress").strip().lower()
        card_key_norm = unquote((card_key or "").strip())
        price = _miniapp_generate_price(media_kind, media_group, card_key=card_key_norm)
        if client_price is not None:
            try:
                client_val = float(str(client_price).strip())
                if abs(client_val - price) > 1e-6:
                    logger.warning(
                        "generate price mismatch: client=%s server=%s user=%s card=%r",
                        client_val,
                        price,
                        uid,
                        (card_key_norm or "")[:80],
                    )
            except ValueError:
                pass
        db = _load_users_db()
        u = _get_user(db, uid)
        _grant_starter_trial_if_needed(u)
        bal = _diamonds_total_from_buckets(u)
        if bal + 1e-9 < price:
            _save_users_db(db)
            raise HTTPException(
                status_code=402,
                detail=f"Not enough credits. Required: {price:.0f} credits.",
            )

        trial0 = float(u.get("trial_diamonds", 0.0) or 0.0)
        vip0 = float(u.get("vip_diamonds", 0.0) or 0.0)
        _deduct_diamonds(u, price)
        taken_trial = trial0 - float(u.get("trial_diamonds", 0.0) or 0.0)
        taken_vip = vip0 - float(u.get("vip_diamonds", 0.0) or 0.0)
        _save_users_db(db)
        new_bal = _diamonds_total_from_buckets(u)
        user_folder = _user_folder_name(parsed)
        try:
            image_bytes = await image.read()
            if not image_bytes:
                db2 = _load_users_db()
                u2 = _get_user(db2, uid)
                _refund_deducted_components(u2, price, taken_trial, taken_vip)
                _save_users_db(db2)
                raise HTTPException(status_code=400, detail="Image cannot be empty.")
            name = (image.filename or "image.jpg").rsplit("/")[-1]
            final_prompt = _resolve_prompt_for_generate(
                card_prompts,
                card_key_norm,
                media_group,
                media_kind,
                prompt,
            )
            logger.info(
                "generate: user_folder=%s card_key=%r prompt_len=%s file=%s",
                user_folder,
                (card_key_norm or "")[:120],
                len(final_prompt or ""),
                prompts_path,
            )
            if final_prompt is None and not card_prompts:
                logger.warning(
                    "card_prompts bos: %s dosyasini kontrol et (proje data/ veya CARD_PROMPTS_FILE).",
                    prompts_path,
                )
            elif final_prompt is None and card_prompts:
                logger.warning(
                    "Kart promptu eslesmedi: card_key=%r media_category=%r media_type=%r (data/card_prompts.txt). "
                    "Workflow'daki sabit metin kullanilacak.",
                    (card_key_norm or "")[:160],
                    media_group,
                    media_kind,
                )
            results = await client.run_workflow(name, image_bytes, final_prompt, user_folder=user_folder)
        except HTTPException:
            raise
        except Exception as exc:
            db3 = _load_users_db()
            u3 = _get_user(db3, uid)
            _refund_deducted_components(u3, price, taken_trial, taken_vip)
            _save_users_db(db3)
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        out_root = settings.output_dir.resolve()
        files: list[dict[str, str]] = []
        for p in results:
            rel_url = "/outputs/" + p.resolve().relative_to(out_root).as_posix()
            files.append({"url": rel_url, "name": p.name})
        return JSONResponse(
            {
                "ok": True,
                "files": files,
                "diamonds_after": new_bal,
                "photo_cost": price,
            }
        )

    async def spa_shell_page() -> FileResponse:
        return FileResponse(
            app.state.settings.miniapp_dir / "index.html",
            media_type="text/html",
            headers={"Cache-Control": "no-cache"},
        )

    spa_pages = (
        "aml-policy.html",
        "blog.html",
        "complaint.html",
        "content-removal.html",
        "index.html",
        "miniapp.html",
        "Image.html",
        "sex.html",
        "duo.html",
        "Explore.html",
        "FaceSwap.html",
        "Games.html",
        "presets.html",
        "video.html",
        "videocustom.html",
        "videotalking.html",
        "texttoımage.html",
        "continue.html",
        "crypto.html",
        "usdt.html",
        "pro.html",
        "creator.html",
        "rewards.html",
        "task.html",
        "quitfitswap.html",
        "Oluşturduklarım – AI Oluşturma Geçmişin _ Undress AI.html",
        "new model training.html",
        "online-safety.html",
        "partners.html",
        "policy.html",
        "privacy.html",
        "terms.html",
        "tida-policy.html",
        "Undress AI - ÜCRETSİZ Deepnude Oluşturun _ AI Undress App.html",
        "Undress App - Create Deepnude Images for FREE _ AI Undress App.html",
        "Undress Fotoğraf ve Video Düzenleyici — Yükleyin ve AI Undressing Oluşturun.html",
        "usc-2257-exemption.html",
        "login.html",
        "account.html",
        "root-pro.html",
        "root-creator.html",
    )
    spa_routes = {
        "/",
        "/login",
        "/edit",
        "/tr/edit",
        "/explore",
        "/games",
        "/account",
        "/plans/pro",
        "/plans/pro/",
        "/plans/pro/index.html",
        "/plans/creator",
        "/plans/creator/",
        "/plans/creator/index.html",
    }
    for page_name in spa_pages:
        spa_routes.add(f"/{page_name}")
        lowercase_path = f"/{page_name}".lower()
        spa_routes.add(lowercase_path)
    for route_index, route_path in enumerate(sorted(spa_routes)):
        app.add_api_route(
            route_path,
            spa_shell_page,
            methods=["GET", "HEAD"],
            name=f"spa_shell_{route_index}",
            include_in_schema=False,
        )

    @app.api_route("/_legacy/{legacy_path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    async def legacy_app_file(legacy_path: str) -> Response:
        legacy_path = legacy_path.lstrip("/")
        static_roots = (
            app.state.settings.miniapp_dir.resolve(),
            (PROJECT_DIR / "assets" / "miniapp").resolve(),
        )
        file_path: Path | None = None
        fallback_path: Path | None = None
        for static_root in static_roots:
            candidate = (static_root / legacy_path).resolve()
            try:
                candidate.relative_to(static_root)
            except ValueError:
                continue
            if fallback_path is None:
                fallback_path = candidate
            if candidate.is_file():
                file_path = candidate
                break
        if file_path is None:
            file_path = fallback_path
        if file_path is None:
            raise HTTPException(status_code=404, detail="File not found.")

        if file_path.suffix.lower() != ".html":
            if not file_path.is_file():
                raise HTTPException(status_code=404, detail="File not found.")
            return FileResponse(
                file_path,
                headers={"Cache-Control": _legacy_asset_cache_control(file_path)},
            )

        await refresh_embedded_app_page_manifest()
        page_name = file_path.name
        page_version = app.state.embedded_app_page_manifest.get(page_name)
        if page_version is not None:
            page_data_path = app.state.embedded_app_page_data_dir / f"{page_version}.html.gz"
            try:
                embedded_page = await asyncio.to_thread(_read_compressed_app_page, page_data_path)
            except (OSError, EOFError, gzip.BadGzipFile) as exc:
                logger.exception("Failed to read embedded Mini App page: %s", page_name)
                raise HTTPException(status_code=500, detail="Page is temporarily unavailable.") from exc
        else:
            if not file_path.is_file():
                raise HTTPException(status_code=404, detail="File not found.")
            embedded_page = await asyncio.to_thread(file_path.read_bytes)
        contents = embedded_page.decode("utf-8-sig")
        bridge = """<script>
(function () {
  if (window.parent === window) return;
  if (!window.Telegram && window.parent.Telegram) window.Telegram = window.parent.Telegram;
  var router = window.parent.__miniappRouter;
  if (!router) return;
  document.addEventListener("click", function (event) {
    var link = event.target && event.target.closest ? event.target.closest("a[href]") : null;
    if (!link || link.hasAttribute("download") ||
        (link.target && link.target.toLowerCase() !== "_self")) return;
    var target;
    try { target = new URL(link.href, window.location.href); } catch (error) { return; }
    if (target.protocol !== "http:" && target.protocol !== "https:" &&
        target.protocol !== "mailto:" && target.protocol !== "tel:") return;
    if (target.origin === window.location.origin &&
        target.href.split("#")[0] === window.location.href.split("#")[0]) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    router.navigate(target.href);
  }, true);
})();
</script>"""
        head_start = contents.lower().find("<head")
        head_end = contents.find(">", head_start) if head_start >= 0 else -1
        if head_end >= 0:
            base_href = "/" if page_name.lower() == "login.html" else f"/_legacy/{quote(page_name)}"
            prefix = ""
            if "<base" not in contents[: head_end + 1].lower():
                prefix = f'<base href="{html.escape(base_href, quote=True)}"> '
            contents = contents[: head_end + 1] + prefix + bridge + contents[head_end + 1 :]

        return HTMLResponse(contents, headers={"Cache-Control": "no-cache"})

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
