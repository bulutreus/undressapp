"""
FastAPI: Mini App statik dosyalar + elmas bakiyesi (Telegram initData) + ComfyUI üretim.
Çalıştırma: uvicorn main:app --host 0.0.0.0 --port 8080
Mini App URL'si HTTPS olmalı (Telegram); botta env: MINIAPP_URL bu adrese işaret etmeli.
"""
from __future__ import annotations

import json
import logging
import os
from urllib.parse import unquote
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# .env, bot yuklenmeden once (MINIAPP_URL vb. import sirasinda okunur)
load_dotenv(Path(__file__).resolve().parent / ".env", override=True)

import aiohttp
import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

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
    detect_comfyui_url,
)
from telegram_init_data import validate_and_parse_init_data

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Gereceli yollar: uvicorn farkli cwd ile baslasa bile dosyalar/outputs ayni proje altinda olsun.
PROJECT_DIR = Path(__file__).resolve().parent


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


async def _send_output_to_bot_user(bot_token: str, user_id: int, file_path: Path) -> bool:
    """Best-effort: send generated output to the same user in bot chat."""
    if not bot_token or not file_path.is_file():
        return False
    api = f"https://api.telegram.org/bot{bot_token}/sendDocument"
    try:
        content = file_path.read_bytes()
        form = aiohttp.FormData()
        form.add_field("chat_id", str(user_id))
        form.add_field("caption", "Your output is ready.")
        form.add_field(
            "document",
            content,
            filename=file_path.name,
            content_type="application/octet-stream",
        )
        timeout = aiohttp.ClientTimeout(total=20)
        async with aiohttp.ClientSession(timeout=timeout) as sess:
            async with sess.post(api, data=form) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    logger.warning("Bot output send failed (%s): %s", resp.status, body[:300])
                    return False
        return True
    except Exception as exc:
        logger.warning("Bot output send error: %s", exc)
        return False


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
        token = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
        if not token:
            raise ValueError(
                "TELEGRAM_BOT_TOKEN yok. .env icinde tam satir: TELEGRAM_BOT_TOKEN=... (sadece sayi:harf yazi degil; "
                f"ornek: {Path(__file__).resolve().parent / '.env'})"
            )

        workflow_path = _path_from_env("CloLessAi.json", "COMFY_WORKFLOW_PATH")
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
    init_data: str = Field(..., min_length=1)


class SubscriptionInvoiceBody(BaseModel):
    init_data: str = Field(default="", max_length=8192)
    plan: str = Field(..., min_length=1, max_length=16)
    billing: str = Field(..., min_length=1, max_length=16)


class GalleryDeleteBody(BaseModel):
    init_data: str = Field(..., min_length=1)
    rel: str = Field(..., min_length=1, max_length=4000)



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
        raise HTTPException(status_code=400, detail="Gecersiz yol.")
    target = (out_root / part).resolve()
    try:
        target.relative_to(out_root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Gecersiz yol.") from exc
    try:
        target.relative_to(user_root)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="Bu dosyaya erisim yok.") from exc
    if not target.is_file():
        raise HTTPException(status_code=404, detail="Dosya yok veya zaten silindi.")
    try:
        target.unlink()
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Dosya silinemedi.") from exc


def create_app() -> FastAPI:
    app = FastAPI(title="CloLess Mini App API", version="1.0.0")
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
        pro_files_dir = PROJECT_DIR / "pro_files"
        if pro_files_dir.is_dir():
            app.mount(
                "/pro_files",
                StaticFiles(directory=str(pro_files_dir)),
                name="pro_files",
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

    @app.get("/health")
    async def health() -> JSONResponse:
        settings: WebSettings = app.state.settings
        return JSONResponse({"ok": True, "comfyui_url": settings.comfyui_url})

    @app.get("/pro")
    async def pro_page() -> FileResponse:
        return FileResponse(
            PROJECT_DIR / "pro.html",
            media_type="text/html",
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/creator")
    async def creator_page() -> FileResponse:
        return FileResponse(
            PROJECT_DIR / "creator.html",
            media_type="text/html",
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/api/miniapp/config")
    async def miniapp_config() -> JSONResponse:
        bot_username = (os.getenv("BOT_USERNAME") or "").strip().lstrip("@")
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

    @app.post("/api/miniapp/balance")
    async def miniapp_balance(body: BalanceBody) -> JSONResponse:
        settings: WebSettings = app.state.settings
        parsed = validate_and_parse_init_data(body.init_data, settings.bot_token)
        if not parsed:
            raise HTTPException(status_code=401, detail="initData gecersiz veya suresi doldu.")
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

    @app.post("/api/miniapp/subscription-invoice")
    async def miniapp_subscription_invoice(body: SubscriptionInvoiceBody) -> JSONResponse:
        settings: WebSettings = app.state.settings
        parsed = validate_and_parse_init_data(body.init_data, settings.bot_token) if body.init_data.strip() else None
        if body.init_data.strip() and not parsed:
            raise HTTPException(status_code=401, detail="Telegram oturumu doğrulanamadı.")

        plan = body.plan.strip().lower()
        billing = body.billing.strip().lower()
        plan_id = f"{plan}_{billing}"
        plan_package = PLAN_STARS_PACKAGES.get(plan_id)
        if not plan_package:
            raise HTTPException(status_code=400, detail="Bu plan Telegram Stars ile satın alınamıyor.")

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
            raise HTTPException(status_code=502, detail="Telegram ödeme bağlantısı oluşturulamadı.") from exc
        if not isinstance(result, dict) or not result.get("ok") or not result.get("result"):
            logger.warning("Telegram invoice link rejected: %s", str(result)[:400])
            raise HTTPException(status_code=502, detail="Telegram ödeme bağlantısı oluşturulamadı.")
        return JSONResponse({"ok": True, "invoice_url": result["result"], "stars": stars})

    @app.post("/api/miniapp/profile")
    async def miniapp_profile(body: BalanceBody) -> JSONResponse:
        settings: WebSettings = app.state.settings
        parsed = validate_and_parse_init_data(body.init_data, settings.bot_token)
        if not parsed:
            raise HTTPException(status_code=401, detail="initData gecersiz veya suresi doldu.")
        uid = int(parsed["user_id"])
        display_name, photo_url = _profile_from_init_user(parsed.get("user_json") or parsed.get("user"))
        if not photo_url:
            photo_url = await _telegram_profile_photo_url(settings.bot_token, uid)
        username = ""
        raw = (parsed.get("user_json") or parsed.get("user") or "").strip()
        if raw:
            try:
                u = json.loads(raw)
                if isinstance(u, dict):
                    username = (u.get("username") or "").strip()
            except (json.JSONDecodeError, TypeError):
                pass
        diamonds = _diamonds_balance_for_api(uid)
        return JSONResponse(
            {
                "ok": True,
                "user_id": uid,
                "display_name": display_name,
                "username": username,
                "photo_url": photo_url or "",
                "diamonds": diamonds,
            }
        )

    @app.post("/api/miniapp/gallery")
    async def miniapp_gallery(body: BalanceBody) -> JSONResponse:
        settings: WebSettings = app.state.settings
        parsed = validate_and_parse_init_data(body.init_data, settings.bot_token)
        if not parsed:
            raise HTTPException(status_code=401, detail="initData gecersiz veya suresi doldu.")
        files = _gallery_files_for_user(settings.output_dir, parsed)
        return JSONResponse({"ok": True, "files": files})

    @app.api_route("/api/miniapp/gallery/delete", methods=["POST", "DELETE"])
    async def miniapp_gallery_delete(body: GalleryDeleteBody) -> JSONResponse:
        settings: WebSettings = app.state.settings
        parsed = validate_and_parse_init_data(body.init_data, settings.bot_token)
        if not parsed:
            raise HTTPException(status_code=401, detail="initData gecersiz veya suresi doldu.")
        _delete_gallery_file_for_user(
            output_dir=settings.output_dir, parsed=parsed, rel_raw=body.rel
        )
        return JSONResponse({"ok": True})

    @app.post("/api/generate")
    async def generate(
        image: UploadFile = File(...),
        init_data: str = Form(...),
        prompt: str | None = Form(default=None),
        media_type: str = Form(default="image"),
        media_category: str = Form(default="undress"),
        card_key: str = Form(default=""),
        client_price: str | None = Form(default=None),
    ) -> JSONResponse:
        settings: WebSettings = app.state.settings
        client: CloLessClient = app.state.client

        parsed = validate_and_parse_init_data((init_data or "").strip(), settings.bot_token)
        if not parsed:
            raise HTTPException(status_code=401, detail="initData gecersiz veya suresi doldu.")

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
                detail=f"Yetersiz elmas. Gerekli: {price:.0f} 💎",
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
                raise HTTPException(status_code=400, detail="Gorsel bos olamaz.")
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
        sent_to_bot = False
        if results:
            sent_to_bot = await _send_output_to_bot_user(settings.bot_token, uid, results[0])
        return JSONResponse(
            {
                "ok": True,
                "files": files,
                "diamonds_after": new_bal,
                "photo_cost": price,
                "sent_to_bot": sent_to_bot,
            }
        )

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
