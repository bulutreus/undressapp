import asyncio
from contextlib import suppress
import html
import json
import logging
import os
import copy
import random
import time
import uuid
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from pathlib import Path
from tempfile import gettempdir
from typing import Any
from urllib.parse import quote, urlparse

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env", override=True)

import aiohttp
from telegram import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputFile,
    KeyboardButton,
    LabeledPrice,
    MenuButtonDefault,
    MenuButtonWebApp,
    ReplyKeyboardMarkup,
    Update,
    User,
    WebAppInfo,
)
from telegram.constants import ChatMemberStatus
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    PreCheckoutQueryHandler,
    filters,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)  # Telegram API URL logs can contain bot credentials
logger = logging.getLogger(__name__)
_ad_broadcast_fallback_task: asyncio.Task[Any] | None = None


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
    ul = u.lower()
    if not (ul.startswith("http://") or ul.startswith("https://")):
        u = "https://" + u.lstrip("/")
    if u.lower().startswith("http://"):
        u = "https://" + u[7:]
    p = urlparse(u)
    h = (p.hostname or "").lower()
    if h in ("127.0.0.1", "localhost", "::1") or (h.startswith("127.") and h.count(".") == 3):
        logger.warning(
            "MINIAPP_URL: '%s' Telegram/BotFather icin gecersiz (yerel adres). Uzak https kullan: "
            "ornek: cloudflared tunnel ciktisindaki https://....trycloudflare.com -> .env MINIAPP_URL=...",
            u,
        )
        return ""
    return u.rstrip("/")


TERMS_URL = "https://telegra.ph/Terms-of-Use-11-26-2"
# HTTPS Mini App; BotFather / Menu Button sadece public https (tunel URL).
MINIAPP_URL = _normalize_miniapp_url(os.getenv("MINIAPP_URL") or os.getenv("MINI_APP_URL") or "")
if MINIAPP_URL:
    logger.info("MINIAPP_URL OK: %s", MINIAPP_URL)
# Zorunlu kanal: kanal ID'si (-100...) — kanala botu admin ekleyin; üyelik getChatMember ile doğrulanır.
MANDATORY_CHANNEL_INVITE_URL = os.getenv(
    "MANDATORY_CHANNEL_INVITE_URL",
    "https://t.me/+NrJM_MrRr-xhZjFk",
).strip()
MANDATORY_CHANNEL_ID = os.getenv("MANDATORY_CHANNEL_ID", "").strip()
MANDATORY_CHANNEL_USERNAME = os.getenv("MANDATORY_CHANNEL_USERNAME", "").strip()
DATA_DIR = Path(os.getenv("BOT_DATA_DIR", "data")).expanduser()
USERS_DB_PATH = DATA_DIR / "users.json"
_ADMIN_USER_IDS_RAW = ",".join(
    [
        os.getenv("ADMIN_USER_IDS", "").strip(),
        os.getenv("ADMIN_USER_ID", "").strip(),
    ]
).strip(",")
_ADMIN_USERNAMES_RAW = ",".join(
    [
        os.getenv("ADMIN_USERNAMES", "").strip(),
        os.getenv("ADMIN_USERNAME", "").strip(),
        "hottokn",
    ]
).strip(",")

DAILY_REWARD_DIAMONDS = float(os.getenv("DAILY_REWARD_DIAMONDS", "0.4"))
DAILY_COOLDOWN_SECONDS = int(os.getenv("DAILY_COOLDOWN_SECONDS", str(24 * 60 * 60)))
DAILY_CHANNEL_URL = (os.getenv("DAILY_CHANNEL_URL", "").strip() or None)
# Telegram GIF: yerel dosya (bot klasörü veya assets/) ya da DAILY_SUCCESS_GIF_FILE_ID.
DAILY_SUCCESS_GIF_FILE_ID = (os.getenv("DAILY_SUCCESS_GIF_FILE_ID", "").strip() or None)
REFERRAL_REWARD_DIAMONDS = float(os.getenv("REFERRAL_REWARD_DIAMONDS", "0.4"))
REFERRAL_MAX_PER_USER = int(os.getenv("REFERRAL_MAX_PER_USER", "1000000"))
# Her fotoğraf işlemi maliyeti; ilk kullanıcıya verilen deneme elması
PHOTO_COST_DIAMONDS = float(os.getenv("PHOTO_COST_DIAMONDS", "1"))
SEX_COST_DIAMONDS = float(os.getenv("SEX_COST_DIAMONDS", "2"))
CHEST_ADJUST_COST_DIAMONDS = float(os.getenv("CHEST_ADJUST_COST_DIAMONDS", "0.5"))
CHEST_ADJUST_MIN = -5
CHEST_ADJUST_MAX = 5
STARTER_TRIAL_DIAMONDS = float(os.getenv("STARTER_TRIAL_DIAMONDS", "1"))
AD_BROADCAST_INTERVAL_SECONDS = 0  # Reklam yayinlari kapali
AD_BROADCAST_FIRST_DELAY_SECONDS = int(os.getenv("AD_BROADCAST_FIRST_DELAY_SECONDS", "60"))

# Gizli promosyon (menü/help'te yok; yalnızca kodu bilen kullanır)
SECRET_PROMO_CODE = "HOTTOK10FREE"
SECRET_PROMO_DIAMONDS = 10.0
ONE_TIME_PROMO_CODE = "HOTTOK"
ONE_TIME_PROMO_DIAMONDS = 3.0
SUPPORTED_LANGUAGES: dict[str, str] = {
    "tr": "Türkçe",
    "en": "English",
    "ar": "العربية",
}

MENU_LABELS: dict[str, dict[str, str]] = {
    "vip": {"tr": "💰 VIP Satın Al 💎", "en": "💰 Buy VIP 💎", "ar": "💰 شراء VIP 💎"},
    "my": {"tr": "👀 Benim 💎'ımı kontrol et", "en": "👀 Check my 💎", "ar": "👀 تحقق من رصيدي 💎"},
    "invite": {"tr": "🚀 Arkadaşlarını davet et, 💎 kazan", "en": "🚀 Invite friends, earn 💎", "ar": "🚀 ادعُ أصدقاءك واربح 💎"},
    "daily": {"tr": "🎁 Günlük hediye al 💎", "en": "🎁 Claim daily gift 💎", "ar": "🎁 احصل على الهدية اليومية 💎"},
    "photo": {"tr": "⚡️ Fotoğrafımı işle!", "en": "⚡️ Process my photo!", "ar": "⚡️ عالج صورتي!"},
    "prompt": {"tr": "📝 Prompt ile işle", "en": "📝 Process with prompt", "ar": "📝 معالجة عبر الوصف"},
    "chest": {"tr": "👙 Göğüs ölçüsü", "en": "👙 Chest size", "ar": "👙 حجم الصدر"},
    "help": {"tr": "❓ Nasıl kullanılır?", "en": "❓ How to use?", "ar": "❓ كيفية الاستخدام؟"},
}

# VIP paketleri — Telegram Stars (XTR). En az: 10 VIP 💎 = 249 ⭐
# id -> (vip_elmas_miktari, stars_fiyati, kisa_baslik)
VIP_PACKAGES: dict[str, tuple[float, int, str]] = {
    "p10": (10.0, 249, "10 VIP 💎"),
    "p50": (50.0, 1099, "50 VIP 💎"),
    "p100": (100.0, 2099, "100 VIP 💎"),
    "p1000": (1000.0, 19999, "1000 VIP 💎"),
    "p5000": (5000.0, 99999, "5000 VIP 💎"),
    "p10000": (10000.0, 199999, "10000 VIP 💎"),
}

# Telegram Mini App subscription invoices paid with Telegram Stars (XTR).
# Annual Pro is intentionally excluded; that plan is available through Crypto only.
PLAN_STARS_PACKAGES: dict[str, tuple[str, str, int, int]] = {
    "pro_monthly": ("pro", "monthly", 2500, 30),
    "creator_monthly": ("creator", "monthly", 6500, 30),
    "creator_yearly": ("creator", "yearly", 28000, 365),
}

VIDEO_PRICE_TIERS: tuple[int, int, int] = (20, 20, 20)
AD_CARD_OFFERS: tuple[dict[str, Any], ...] = (
    {"id": "v01", "name": "Undress", "diamonds": 299.0, "video": "undress.mp4"},
    {"id": "v02", "name": "Riding", "diamonds": 299.0, "video": "riding.mp4"},
    {"id": "v03", "name": "Handjob", "diamonds": 299.0, "video": "handjob.mp4"},
    {"id": "v04", "name": "Doggy", "diamonds": 399.0, "video": "doggy.mp4"},
    {"id": "v05", "name": "Missionary", "diamonds": 399.0, "video": "missionary.mp4"},
    {"id": "v06", "name": "Deepthroat", "diamonds": 399.0, "video": "deepthroat.mp4"},
    {"id": "v07", "name": "Double Penetration", "diamonds": 499.0, "video": "double-penetration.mp4"},
    {"id": "v08", "name": "Bukkake", "diamonds": 499.0, "video": "bukkake.mp4"},
    {"id": "v09", "name": "Squirt", "diamonds": 499.0, "video": "squirt.mp4"},
)

_USERS_META_KEY = "_meta"
_PROCESSED_STAR_PAYMENTS_CAP = 4000
_PROMPT_TRANSLATION_CACHE_MAX = 512
_prompt_translation_cache: dict[str, str] = {}
_translate_http_session: aiohttp.ClientSession | None = None


def _now_ts() -> int:
    return int(time.time())


def _mandatory_channel_target() -> str:
    if MANDATORY_CHANNEL_ID:
        return MANDATORY_CHANNEL_ID
    uname = MANDATORY_CHANNEL_USERNAME.lstrip("@").strip()
    return f"@{uname}" if uname else ""


def _extract_public_username_from_invite_url(url: str) -> str | None:
    raw = (url or "").strip()
    if not raw:
        return None
    marker = "t.me/"
    idx = raw.find(marker)
    if idx < 0:
        return None
    tail = raw[idx + len(marker):].strip().strip("/")
    if not tail or tail.startswith("+"):
        # Private invite links like t.me/+xxxx cannot be used in get_chat_member.
        return None
    username = tail.split("/", 1)[0].split("?", 1)[0].lstrip("@").strip()
    if not username:
        return None
    return f"@{username}"


def _mandatory_channel_targets() -> list[str]:
    """Membership check candidates, ordered by reliability."""
    targets: list[str] = []
    if MANDATORY_CHANNEL_ID:
        targets.append(MANDATORY_CHANNEL_ID)
    uname = MANDATORY_CHANNEL_USERNAME.lstrip("@").strip()
    if uname:
        targets.append(f"@{uname}")
    invite_username = _extract_public_username_from_invite_url(MANDATORY_CHANNEL_INVITE_URL)
    if invite_username:
        targets.append(invite_username)
    # de-duplicate while preserving order
    dedup: list[str] = []
    seen: set[str] = set()
    for t in targets:
        if t not in seen:
            seen.add(t)
            dedup.append(t)
    return dedup


def _is_mandatory_channel_enabled() -> bool:
    return bool(MANDATORY_CHANNEL_INVITE_URL or _mandatory_channel_target())


def _parse_admin_user_ids(raw_value: str) -> set[int]:
    out: set[int] = set()
    for part in raw_value.split(","):
        piece = (part or "").strip()
        if not piece:
            continue
        try:
            out.add(int(piece))
        except ValueError:
            logger.warning("Gecersiz admin user id atlandi: %r", piece)
    return out


ADMIN_USER_IDS = _parse_admin_user_ids(_ADMIN_USER_IDS_RAW)


def _parse_admin_usernames(raw_value: str) -> set[str]:
    out: set[str] = set()
    for part in raw_value.split(","):
        piece = (part or "").strip().lstrip("@").lower()
        if piece:
            out.add(piece)
    return out


ADMIN_USERNAMES = _parse_admin_usernames(_ADMIN_USERNAMES_RAW)


def _is_admin_user(user_id: int | None, username: str | None = None) -> bool:
    if user_id is not None and int(user_id) in ADMIN_USER_IDS:
        return True
    normalized = (username or "").strip().lstrip("@").lower()
    return bool(normalized) and normalized in ADMIN_USERNAMES


def daily_gift_message_html(lang: str = "tr", extra_success_line: str | None = None) -> str:
    amt = DAILY_REWARD_DIAMONDS
    if lang == "en":
        if DAILY_CHANNEL_URL:
            channel_part = (
                f'You can claim {amt:g} 💎 for free every 24 hours. '
                f'<a href="{html.escape(DAILY_CHANNEL_URL)}">Join our channel</a> '
                "and tap to claim! ✨"
            )
        else:
            channel_part = (
                f"You can claim {amt:g} 💎 for free every 24 hours. "
                "Join our channel and tap to claim! ✨"
            )
        body = (
            "🎁 <b>Daily Gift</b>\n\n"
            f"{channel_part}\n\n"
            "📌 It does not stack automatically, so don't forget to claim on time."
        )
    else:
        if DAILY_CHANNEL_URL:
            channel_part = (
                f'Her 24 saatte bir {amt:g} 💎 ücretsiz olarak talep edebilirsiniz. '
                f'<a href="{html.escape(DAILY_CHANNEL_URL)}">Kanalımıza katılın</a> '
                "ve talep etmek için tıklayın! ✨"
            )
        else:
            channel_part = (
                f"Her 24 saatte bir {amt:g} 💎 ücretsiz olarak talep edebilirsiniz. "
                "Kanalımıza katılın ve talep etmek için tıklayın! ✨"
            )
        body = (
            "🎁 <b>Günlük Hediye</b>\n\n"
            f"{channel_part}\n\n"
            "📌 Otomatik olarak birikmeyecek, zamanında talep etmeyi unutmayın."
        )
    if extra_success_line:
        body = body + "\n\n" + extra_success_line
    return body


def build_daily_gift_markup(remaining_seconds: int, lang: str = "tr") -> InlineKeyboardMarkup:
    """remaining_seconds > 0: bekleme; <= 0: talep edilebilir."""
    if remaining_seconds > 0:
        h = remaining_seconds // 3600
        m = (remaining_seconds % 3600) // 60
        s = remaining_seconds % 60
        wait_text = (
            f"⌛ Wait {h:02d}:{m:02d}:{s:02d}"
            if lang == "en"
            else f"⌛ {h:02d}:{m:02d}:{s:02d} süresince bekleyin"
        )
        row1 = [
            InlineKeyboardButton(
                text=wait_text,
                callback_data="daily:status",
            )
        ]
    else:
        claim_text = "🎁 Claim gift" if lang == "en" else "🎁 Hediyeyi talep et"
        row1 = [InlineKeyboardButton(text=claim_text, callback_data="daily:claim")]
    row2 = [
        InlineKeyboardButton(
            text=_menu_label(lang, "invite"),
            callback_data="menu:invite",
        )
    ]
    return InlineKeyboardMarkup([row1, row2])


def build_daily_success_markup(lang: str = "tr") -> InlineKeyboardMarkup:
    """Tebrik ekranı — davet + günlük hediye ekranına dönüş."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    text=_menu_label(lang, "invite"),
                    callback_data="menu:invite",
                )
            ],
            [InlineKeyboardButton(text="↩️ Back" if lang == "en" else "↩️ Geri", callback_data="daily:back")],
        ]
    )


def daily_success_message_plain(reward: float, total: float, lang: str = "tr") -> str:
    if lang == "en":
        return (
            f"🎉 Congrats, you earned {reward:.1f} 💎!\n\n"
            f"You now have {total:.1f} 💎."
        )
    return (
        f"🎉 Tebrikler, {reward:.1f} 💎 kazandınız!\n\n"
        f"Şimdi {total:.1f} 💎'nız var."
    )


def _daily_success_gif_local_path() -> Path | None:
    """GIF/Video: önce DAILY_SUCCESS_GIF_PATH, sonra proje kökü, son olarak assets/."""
    env = os.getenv("DAILY_SUCCESS_GIF_PATH", "").strip()
    if env:
        p = Path(env).expanduser()
        if p.is_file():
            return p
    names = ("daily_success.gif", "daily_success.mp4", "daily_success.webm")
    root = Path(__file__).resolve().parent
    for name in names:
        cand = root / name
        if cand.is_file():
            return cand
    for name in names:
        cand = root / "assets" / name
        if cand.is_file():
            return cand
    return None


def _daily_remaining_seconds(user: dict[str, Any]) -> int:
    now = _now_ts()
    last = int(user.get("daily_last_ts", 0) or 0)
    return (last + DAILY_COOLDOWN_SECONDS) - now


def _ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _load_users_db() -> dict[str, Any]:
    _ensure_data_dir()
    if not USERS_DB_PATH.exists():
        return {}
    try:
        return json.loads(USERS_DB_PATH.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def _save_users_db(db: dict[str, Any]) -> None:
    _ensure_data_dir()
    USERS_DB_PATH.write_text(json.dumps(db, ensure_ascii=False, indent=2), encoding="utf-8")


def _get_user(db: dict[str, Any], user_id: int) -> dict[str, Any]:
    key = str(user_id)
    key_existed_before = key in db
    user = db.get(key)
    if not isinstance(user, dict):
        user = {}
        db[key] = user
    user.setdefault("diamonds", 0.0)
    user.setdefault("vip_diamonds", 0.0)
    user.setdefault("trial_diamonds", 0.0)
    user.setdefault("daily_last_ts", 0)
    user.setdefault("referred_by", None)  # int user_id | None
    user.setdefault("referrals_count", 0)
    user.setdefault("referrals_earned", 0.0)
    user.setdefault("referrals_users", [])  # list[int]
    user.setdefault("promo_hotok10free", False)
    user.setdefault("promo_hottok_used", False)
    user.setdefault("language", "tr")
    user.setdefault("prompt_mode_enabled", False)
    user.setdefault("custom_prompt_text", "")
    user.setdefault("awaiting_prompt_input", False)
    user.setdefault("is_adult_verified", False)
    if "terms_accepted" not in user:
        # Yeni profil: henüz kabul yok. Eski JSON'da alan yoksa: daha önce kullanıyordu, kabul edilmiş say.
        user["terms_accepted"] = False if not key_existed_before else True
    if "starter_trial_given" not in user:
        # Eski kayıtlar: başlangıç bonusu sayılır (tekrar 1 💎 verilmez).
        user["starter_trial_given"] = bool(key_existed_before)
    return user


def _user_language(db: dict[str, Any], user_id: int | None) -> str:
    if user_id is None:
        return "tr"
    user = _get_user(db, int(user_id))
    lang = str(user.get("language", "tr") or "tr").lower()
    return lang if lang in SUPPORTED_LANGUAGES else "tr"


def _lang_from_update(update: Update | None) -> str:
    if not update:
        return "tr"
    user = getattr(update, "effective_user", None)
    user_id = getattr(user, "id", None)
    db = _load_users_db()
    return _user_language(db, int(user_id) if user_id is not None else None)


def _menu_label(lang: str, key: str) -> str:
    labels = MENU_LABELS.get(key, {})
    return labels.get(lang) or labels.get("tr") or key


def _effective_prompt_for_user(user: dict[str, Any]) -> str | None:
    if user.get("prompt_mode_enabled"):
        custom = str(user.get("custom_prompt_text", "") or "").strip()
        if custom:
            return custom
    # Normal akışta workflow içindeki sabit prompt kullanılmalı.
    return None


async def _translate_prompt_to_english(prompt: str | None) -> str | None:
    text = (prompt or "").strip()
    if not text:
        return None
    cached = _prompt_translation_cache.get(text)
    if cached:
        return cached
    # Fast and keyless Google endpoint; fallback to original prompt on any failure.
    url = "https://translate.googleapis.com/translate_a/single"
    params = {
        "client": "gtx",
        "sl": "auto",
        "tl": "en",
        "dt": "t",
        "q": text,
    }
    timeout = aiohttp.ClientTimeout(total=5)
    try:
        global _translate_http_session
        if _translate_http_session is None or _translate_http_session.closed:
            _translate_http_session = aiohttp.ClientSession(timeout=timeout)
        async with _translate_http_session.get(url, params=params) as resp:
            if resp.status != 200:
                return text
            data = await resp.json(content_type=None)
            parts = data[0] if isinstance(data, list) and data else []
            translated = "".join(
                str(item[0]) for item in parts if isinstance(item, list) and item and item[0]
            ).strip()
            result = translated or text
            _prompt_translation_cache[text] = result
            if len(_prompt_translation_cache) > _PROMPT_TRANSLATION_CACHE_MAX:
                _prompt_translation_cache.pop(next(iter(_prompt_translation_cache)))
            return result
    except Exception:
        return text


def _grant_starter_trial_if_needed(user: dict[str, Any]) -> bool:
    """İlk kez kullananlara STARTER_TRIAL_DIAMONDS verir. True = az önce verildi."""
    if user.get("starter_trial_given"):
        return False
    user["starter_trial_given"] = True
    user["trial_diamonds"] = float(user.get("trial_diamonds", 0.0) or 0.0) + STARTER_TRIAL_DIAMONDS
    user["diamonds"] = float(user.get("diamonds", 0.0) or 0.0) + STARTER_TRIAL_DIAMONDS
    return True


def _diamonds_total_from_buckets(user: dict[str, Any]) -> float:
    """Toplam = deneme (trial) + VIP; tek tutarlı kaynak."""
    return float(user.get("trial_diamonds", 0.0) or 0.0) + float(user.get("vip_diamonds", 0.0) or 0.0)


def _deduct_diamonds(user: dict[str, Any], cost: float) -> None:
    """Önce deneme, sonra VIP; ardından diamonds alanını (trial+vip) ile aynı tutar."""
    trial = float(user.get("trial_diamonds", 0.0) or 0.0)
    vip = float(user.get("vip_diamonds", 0.0) or 0.0)
    remain = cost
    take_t = min(trial, remain)
    user["trial_diamonds"] = max(0.0, trial - take_t)
    remain -= take_t
    if remain > 0:
        user["vip_diamonds"] = max(0.0, vip - remain)
    user["diamonds"] = _diamonds_total_from_buckets(user)


def _deduct_one_photo_diamond(user: dict[str, Any]) -> None:
    """Toplamdan PHOTO_COST düşer; önce deneme, kalanı VIP elmasından."""
    _deduct_diamonds(user, PHOTO_COST_DIAMONDS)


def _users_meta(db: dict[str, Any]) -> dict[str, Any]:
    raw = db.get(_USERS_META_KEY)
    if not isinstance(raw, dict):
        raw = {}
        db[_USERS_META_KEY] = raw
    raw.setdefault("star_charge_ids", [])
    return raw


def _parse_vip_invoice_payload(payload: str | None) -> tuple[str, int] | None:
    if not payload:
        return None
    parts = payload.split("|")
    if len(parts) != 3 or parts[0] != "vip":
        return None
    pkg_id, uid_s = parts[1], parts[2]
    if pkg_id not in VIP_PACKAGES or not uid_s.isdigit():
        return None
    return pkg_id, int(uid_s)


def _parse_card_invoice_payload(payload: str | None) -> tuple[str, int] | None:
    if not payload:
        return None
    parts = payload.split("|")
    if len(parts) != 3 or parts[0] != "card":
        return None
    offer_id, uid_s = parts[1], parts[2]
    if (offer_id != "minvideo" and _card_offer_by_id(offer_id) is None) or not uid_s.isdigit():
        return None
    return offer_id, int(uid_s)


def _parse_plan_invoice_payload(payload: str | None) -> tuple[str, int | None] | None:
    if not payload:
        return None
    parts = payload.split("|")
    if len(parts) not in (2, 3) or parts[0] != "plan":
        return None
    plan_id = parts[1]
    uid_s = parts[2] if len(parts) == 3 else ""
    if plan_id not in PLAN_STARS_PACKAGES or (uid_s and not uid_s.isdigit()):
        return None
    return plan_id, int(uid_s) if uid_s else None


def build_vip_shop_markup() -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for pkg_id, (vip_amt, stars, title) in VIP_PACKAGES.items():
        label = f"{title} · {int(stars)} ⭐"
        rows.append([InlineKeyboardButton(text=label, callback_data=f"shop:vip:{pkg_id}")])
    return InlineKeyboardMarkup(rows)


def build_video_promo_markup(lang: str = "tr", *, offer_id: str = "", stars: int = 0) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if MINIAPP_URL:
        rows.append([
            InlineKeyboardButton(
                text=("🎬 Open Mini App" if lang == "en" else "🎬 Mini App'i Aç"),
                web_app=WebAppInfo(url=MINIAPP_URL),
            )
        ])
    if offer_id and stars > 0:
        rows.append([
            InlineKeyboardButton(
                text=(f"⭐ Pay {stars} Stars" if lang == "en" else f"⭐ {stars} Stars ile Öde"),
                callback_data="shop:card:minvideo",
            )
        ])
    return InlineKeyboardMarkup(rows)


def _stars_for_card_price(diamonds: float) -> int:
    # Cap Stars price at 100 for card payments.
    return min(100, max(1, int(round(float(diamonds) * 20))))


def _min_video_card_price() -> float:
    return float(min(VIDEO_PRICE_TIERS))


def _miniapp_generate_price(
    media_type: str,
    media_category: str,
    *,
    card_key: str = "",
) -> float:
    """Mini app: kart rozetindeki fiyat kadar elmas düşülür."""
    _ = card_key
    kind = (media_type or "image").strip().lower()
    group = (media_category or "undress").strip().lower()
    if kind == "video":
        return float(_min_video_card_price())
    if group == "sex":
        return float(SEX_COST_DIAMONDS)
    return float(PHOTO_COST_DIAMONDS)


def _miniapp_price_table() -> dict[str, float]:
    return {
        "undress": float(PHOTO_COST_DIAMONDS),
        "sex": float(SEX_COST_DIAMONDS),
        "video": float(_min_video_card_price()),
    }


def _card_offer_by_id(offer_id: str) -> dict[str, Any] | None:
    for offer in AD_CARD_OFFERS:
        if str(offer.get("id")) == str(offer_id):
            return offer
    return None


def _pick_next_ad_offer(last_offer_id: str | None) -> dict[str, Any] | None:
    if not AD_CARD_OFFERS:
        return None
    pool = [o for o in AD_CARD_OFFERS if str(o.get("id", "")) != str(last_offer_id or "")]
    if not pool:
        pool = list(AD_CARD_OFFERS)
    return random.choice(pool)


def _miniapp_video_url(file_name: str | None) -> str | None:
    if not MINIAPP_URL or not file_name:
        return None
    return f"{MINIAPP_URL}/undress/video/{file_name}"


async def maybe_send_periodic_ad(update: Update, context: ContextTypes.DEFAULT_TYPE, *, reason: str = "") -> None:
    # Interaction-based ad flow disabled; ads are sent by hourly broadcast job.
    return


def _video_ad_text(lang: str, offer: dict[str, Any]) -> str:
    diamonds = _min_video_card_price()
    return (
        "🔥 Video card offer\n\n"
        f"💎 Minimum price: {diamonds:.0f}\n"
        "Pay below with Telegram Stars."
        if lang == "en"
        else "🔥 Video kart teklifi\n\n"
        "ŞİMDİ İSTEDİĞİN KİŞİNİN BİR FOTOĞRAFINI MİNİ APP E GÖNDER VE BU ŞEKİLDE BİR VİDEOSUNU OLUŞTUR!\n"
        f"💎 Minimum fiyat: {diamonds:.0f}\n"
        "Aşağıdan Telegram Stars ile öde."
    )


async def send_video_ad_to_chat(
    bot: Any,
    *,
    chat_id: int,
    lang: str,
    last_offer_id: str | None = None,
) -> str | None:
    offer = _pick_next_ad_offer(last_offer_id)
    if not offer:
        return None
    offer_id = str(offer.get("id", ""))
    diamonds = _min_video_card_price()
    stars = _stars_for_card_price(diamonds)
    text = _video_ad_text(lang, offer)
    next_video_url = _miniapp_video_url(str(offer.get("video", "")))
    if next_video_url:
        try:
            await bot.send_video(
                chat_id=chat_id,
                video=next_video_url,
                caption=text,
                reply_markup=build_video_promo_markup(lang, offer_id="minvideo", stars=stars),
            )
            return offer_id
        except Exception as exc:
            logger.warning("Video reklam gönderimi başarısız (chat_id=%s), metin fallback: %s", chat_id, exc)
    try:
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=build_video_promo_markup(lang, offer_id="minvideo", stars=stars),
            disable_web_page_preview=True,
        )
    except Exception as exc:
        logger.warning("Butonlu reklam gönderimi başarısız (chat_id=%s), sade metin fallback: %s", chat_id, exc)
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            disable_web_page_preview=True,
        )
    return offer_id


async def _broadcast_hourly_ads(bot: Any) -> None:
    if AD_BROADCAST_INTERVAL_SECONDS <= 0:
        return
    db = _load_users_db()
    changed = False
    for key, value in db.items():
        if key == _USERS_META_KEY or not isinstance(value, dict):
            continue
        if not str(key).isdigit():
            continue
        chat_id = int(key)
        user = _get_user(db, chat_id)
        lang = str(user.get("language", "tr") or "tr").lower()
        if lang not in SUPPORTED_LANGUAGES:
            lang = "tr"
        last_offer_id = str(user.get("ad_last_offer_id", "") or "")
        try:
            next_offer_id = await send_video_ad_to_chat(
                bot,
                chat_id=chat_id,
                lang=lang,
                last_offer_id=last_offer_id,
            )
            if next_offer_id:
                user["ad_last_offer_id"] = next_offer_id
                changed = True
        except Exception as exc:
            logger.warning("Saatlik reklam gönderilemedi (chat_id=%s): %s", chat_id, exc)
        await asyncio.sleep(0.05)
    if changed:
        _save_users_db(db)


async def hourly_ad_broadcast_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    await _broadcast_hourly_ads(context.bot)


async def _hourly_ad_broadcast_fallback_loop(app: Application) -> None:
    """JobQueue yoksa reklam yayınını arka planda sürdür."""
    interval_seconds = max(1, AD_BROADCAST_INTERVAL_SECONDS)
    first_delay_seconds = max(1, min(interval_seconds, AD_BROADCAST_FIRST_DELAY_SECONDS))
    await asyncio.sleep(first_delay_seconds)
    while True:
        await _broadcast_hourly_ads(app.bot)
        await asyncio.sleep(interval_seconds)


def build_invite_markup(invite_link: str, lang: str = "tr") -> InlineKeyboardMarkup:
    """Telegram paylaşım bağlantısı (davet linki paylaşımda gider)."""
    share_text = (
        "Edit your photos magically with this bot! 💎 Try it too:"
        if lang == "en"
        else "Bu botla fotoğraflarını sihirli şekilde düzenle! 💎 Sen de dene:"
    )
    share_url = (
        "https://t.me/share/url?"
        f"url={quote(invite_link, safe='')}&text={quote(share_text, safe='')}"
    )
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(text="📤 Share with friends" if lang == "en" else "📤 Arkadaşlarınla paylaş", url=share_url)]]
    )


def _parse_referrer_id_from_start_args(args: list[str] | None) -> int | None:
    if not args:
        return None
    token = (args[0] or "").strip()
    if not token.startswith("ref_"):
        return None
    raw = token.removeprefix("ref_").strip()
    if not raw.isdigit():
        return None
    return int(raw)


def _apply_referral_if_possible(*, db: dict[str, Any], new_user_id: int, referrer_id: int) -> tuple[bool, str]:
    if new_user_id == referrer_id:
        return False, "self_referral"

    new_user = _get_user(db, new_user_id)
    ref_user = _get_user(db, referrer_id)

    if new_user.get("referred_by") is not None:
        return False, "already_referred"

    if int(ref_user.get("referrals_count", 0) or 0) >= REFERRAL_MAX_PER_USER:
        return False, "referrer_limit"

    referred_users_raw = ref_user.get("referrals_users") or []
    try:
        referred_users = [int(x) for x in referred_users_raw]
    except Exception:
        referred_users = []

    if new_user_id in referred_users:
        return False, "duplicate"

    new_user["referred_by"] = referrer_id
    ref_user["referrals_count"] = int(ref_user.get("referrals_count", 0) or 0) + 1
    ref_user["referrals_earned"] = float(ref_user.get("referrals_earned", 0.0)) + REFERRAL_REWARD_DIAMONDS
    ref_user["diamonds"] = float(ref_user.get("diamonds", 0.0)) + REFERRAL_REWARD_DIAMONDS
    ref_user["trial_diamonds"] = float(ref_user.get("trial_diamonds", 0.0)) + REFERRAL_REWARD_DIAMONDS
    ref_user["referrals_users"] = referred_users + [new_user_id]
    return True, "ok"


async def _try_referral_reward_on_start(
    context: ContextTypes.DEFAULT_TYPE,
    *,
    new_user_id: int,
    referrer_id: int,
) -> None:
    """Davet linkiyle ( ?start=ref_... ) Başlat / /start yapıldığında davet edene elmas yükler."""
    db = _load_users_db()
    applied, reason = _apply_referral_if_possible(
        db=db,
        new_user_id=new_user_id,
        referrer_id=referrer_id,
    )
    if applied:
        _save_users_db(db)
        try:
            await context.bot.send_message(
                chat_id=int(referrer_id),
                text=f"🎉 Davet ödülü: +{REFERRAL_REWARD_DIAMONDS:g} 💎 kazandın!",
            )
        except Exception as exc:
            logger.warning("Referrer bilgilendirilemedi: %s", exc)
    else:
        logger.info("Referral uygulanmadı (start): %s", reason)


async def detect_comfyui_url(
    preferred_url: str,
    request_headers: dict[str, str] | None = None,
) -> str:
    candidates = []
    for url in (preferred_url, "http://127.0.0.1:8002", "http://127.0.0.1:8000", "http://127.0.0.1:8188"):
        clean = (url or "").rstrip("/")
        if clean and clean not in candidates:
            candidates.append(clean)

    timeout = aiohttp.ClientTimeout(total=3)
    for base_url in candidates:
        try:
            async with aiohttp.ClientSession(
                base_url=base_url,
                headers=request_headers,
                timeout=timeout,
            ) as probe:
                async with probe.get("/system_stats") as response:
                    if response.status < 400:
                        logger.info("ComfyUI endpoint bulundu: %s", base_url)
                        return base_url
        except Exception:
            logger.warning("ComfyUI endpoint erişilemedi: %s", base_url)

    logger.warning(
        "ComfyUI endpoint otomatik bulunamadi. Varsayilan adres kullanilacak: %s",
        preferred_url.rstrip("/") or "http://127.0.0.1:8002",
    )
    return preferred_url.rstrip("/") or "http://127.0.0.1:8002"


# ComfyUI API formatinda class_type -> positive prompt'un yazildigi inputs anahtari
_TEXT_NODE_CLASS_TO_FIELD: dict[str, str] = {
    "Text": "text",
    "CLIPTextEncode": "text",
    "CLIPTextEncodeSDXL": "text",
    "CLIPTextEncodeSDRefiner": "text",
    "CLIPTextEncodeFlux": "text",
    "TextEncodeQwenImageEditPlus": "prompt",
}


@dataclass(frozen=True)
class Settings:
    telegram_token: str
    comfyui_url: str
    workflow_path: Path
    output_dir: Path
    image_node_id: str | None
    image_field: str
    text_node_id: str | None
    text_field: str
    output_node_id: str | None
    poll_interval_seconds: float

    @classmethod
    def from_env(cls) -> "Settings":
        telegram_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        if not telegram_token:
            raise ValueError("TELEGRAM_BOT_TOKEN tanımlı değil.")

        workflow_path = Path(
            os.getenv("COMFY_WORKFLOW_PATH", "CloLessAi.json")
        ).expanduser()
        if not workflow_path.is_absolute():
            workflow_path = Path.cwd() / workflow_path

        output_dir = Path(os.getenv("COMFY_OUTPUT_DIR", "outputs")).expanduser()
        if not output_dir.is_absolute():
            output_dir = Path.cwd() / output_dir

        out_node = (os.getenv("COMFY_OUTPUT_NODE_ID", "64") or "").strip()
        return cls(
            telegram_token=telegram_token,
            comfyui_url=os.getenv("COMFYUI_URL", "http://127.0.0.1:8002").rstrip("/"),
            workflow_path=workflow_path,
            output_dir=output_dir,
            image_node_id=os.getenv("COMFY_IMAGE_NODE_ID") or None,
            image_field=os.getenv("COMFY_IMAGE_FIELD", "image"),
            text_node_id=os.getenv("COMFY_TEXT_NODE_ID", "") or None,
            text_field=os.getenv("COMFY_TEXT_FIELD", "text"),
            output_node_id=out_node or None,
            poll_interval_seconds=float(os.getenv("COMFY_POLL_INTERVAL_SECONDS", "0.5")),
        )


class CloLessClient:
    def __init__(self, settings: Settings, session: aiohttp.ClientSession) -> None:
        self.settings = settings
        self.session = session
        self.client_id = str(uuid.uuid4())
        self._ws_task = None
        self._ws = None
        self._futures: dict[str, asyncio.Future] = {}
        self._workflow_cache: dict[str, Any] | None = None
        self._workflow_file_mtime_ns: int | None = None
        self._workflow_prompt_cache: dict[str, Any] | None = None

    async def ensure_ws(self):
        if self._ws and not self._ws.closed:
            return

        ws_url = f"{self.settings.comfyui_url.replace('http', 'ws')}/ws?clientId={self.client_id}"
        try:
            self._ws = await self.session.ws_connect(ws_url)
            if self._ws_task and not self._ws_task.done():
                self._ws_task.cancel()
            self._ws_task = asyncio.create_task(self._listen_ws())
            logger.info("WebSocket bağlantısı kuruldu (clientId=%s)", self.client_id)
        except Exception as e:
            logger.error("WebSocket bağlantı hatası: %s", e)

    async def _listen_ws(self):
        try:
            async for msg in self._ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    if data.get("type") == "executing":
                        exec_data = data.get("data", {})
                        prompt_id = exec_data.get("prompt_id")
                        if exec_data.get("node") is None and prompt_id in self._futures:
                            self._futures[prompt_id].set_result(True)
                elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                    break
        except Exception as e:
            logger.error("WebSocket dinleme hatası: %s", e)
        finally:
            self._ws = None
            for fut in self._futures.values():
                if not fut.done(): fut.set_result(False)

    def load_workflow(self) -> dict[str, Any]:
        if not self.settings.workflow_path.exists():
            raise FileNotFoundError(
                f"Workflow dosyası bulunamadı: {self.settings.workflow_path}"
            )
        stat = self.settings.workflow_path.stat()
        current_mtime_ns = int(stat.st_mtime_ns)
        if (
            self._workflow_prompt_cache is not None
            and self._workflow_file_mtime_ns == current_mtime_ns
        ):
            return copy.deepcopy(self._workflow_prompt_cache)

        workflow_data = json.loads(self.settings.workflow_path.read_text(encoding="utf-8"))
        prompt = workflow_data.get("prompt") if isinstance(workflow_data, dict) else None

        if isinstance(prompt, dict):
            self._workflow_prompt_cache = prompt
            self._workflow_file_mtime_ns = current_mtime_ns
            return copy.deepcopy(prompt)
        if self.is_prompt_workflow(workflow_data):
            self._workflow_prompt_cache = workflow_data
            self._workflow_file_mtime_ns = current_mtime_ns
            return copy.deepcopy(workflow_data)
        if self.is_ui_workflow(workflow_data):
            # UI→API dönüşümü güncellenince eski önbellek yanlış graf üretebilir.
            self._workflow_cache = None
            converted = self.convert_ui_workflow_to_prompt(workflow_data)
            self._workflow_prompt_cache = converted
            self._workflow_file_mtime_ns = current_mtime_ns
            return copy.deepcopy(converted)
        raise ValueError("Workflow JSON formatı desteklenmiyor.")

    @staticmethod
    def is_prompt_workflow(workflow_data: Any) -> bool:
        if not isinstance(workflow_data, dict):
            return False
        numeric_keys = [key for key in workflow_data.keys() if str(key).isdigit()]
        if not numeric_keys:
            return False
        return all(
            isinstance(workflow_data[key], dict) and "class_type" in workflow_data[key]
            for key in numeric_keys
        )

    @staticmethod
    def is_ui_workflow(workflow_data: Any) -> bool:
        return (
            isinstance(workflow_data, dict)
            and isinstance(workflow_data.get("nodes"), list)
            and isinstance(workflow_data.get("links"), list)
        )

    def convert_ui_workflow_to_prompt(self, workflow_data: dict[str, Any]) -> dict[str, Any]:
        if self._workflow_cache is not None:
            return copy.deepcopy(self._workflow_cache)

        links_by_id: dict[int, list[Any]] = {}
        for link in workflow_data.get("links", []):
            if isinstance(link, list) and len(link) >= 6:
                links_by_id[int(link[0])] = link

        prompt: dict[str, Any] = {}
        for node in workflow_data.get("nodes", []):
            node_id = str(node["id"])
            inputs: dict[str, Any] = {}

            for input_item in node.get("inputs", []):
                link_id = input_item.get("link")
                if link_id is None:
                    continue
                link = links_by_id.get(int(link_id))
                if not link:
                    continue
                origin_node_id = str(link[1])
                origin_output_slot = int(link[2])
                inputs[input_item["name"]] = [origin_node_id, origin_output_slot]

            # Widget değerleri, ComfyUI'da kabloyla bağlı girişleri ASLA ezmesin (ör. prompt <- Text düğümü).
            for key, val in self.extract_widget_values(node).items():
                if key not in inputs:
                    inputs[key] = val

            prompt[node_id] = {
                "inputs": inputs,
                "class_type": node["type"],
                "_meta": {
                    "title": node.get("title") or node.get("_meta", {}).get("title") or node["type"]
                },
            }

        self._workflow_cache = prompt
        return copy.deepcopy(prompt)

    def extract_widget_values(self, node: dict[str, Any]) -> dict[str, Any]:
        values = list(node.get("widgets_values") or [])
        node_type = node.get("type")

        if node_type == "CheckpointLoaderSimple":
            return self.zip_widget_values(("ckpt_name",), values)
        if node_type == "KSampler":
            mapping = self.zip_widget_values(
                (
                    "seed",
                    "control_after_generate",
                    "steps",
                    "cfg",
                    "sampler_name",
                    "scheduler",
                    "denoise",
                ),
                values,
            )
            mapping.pop("control_after_generate", None)
            return mapping
        if node_type == "TextEncodeQwenImageEditPlus":
            return self.zip_widget_values(("prompt",), values)
        if node_type == "LoadImage":
            return self.zip_widget_values(("image", "upload"), values)
        if node_type == "EmptyLatentImage":
            return self.zip_widget_values(("width", "height", "batch_size"), values)
        if node_type == "ImageScaleToTotalPixels":
            return self.zip_widget_values(("upscale_method", "megapixels", "resolution_steps"), values)
        if node_type == "LayerUtility: ImageScaleByAspectRatio V2":
            return self.zip_widget_values(
                (
                    "aspect_ratio",
                    "proportional_width",
                    "proportional_height",
                    "fit",
                    "method",
                    "round_to_multiple",
                    "scale_to_side",
                    "scale_to_length",
                    "background_color",
                ),
                values,
            )
        if node_type == "Int":
            mapping = self.zip_widget_values(("Number",), values)
            if "Number" in mapping:
                try:
                    mapping["Number"] = int(mapping["Number"])
                except (TypeError, ValueError):
                    pass
            return mapping
        if node_type == "Text":
            return self.zip_widget_values(("text",), values)
        if node_type == "SaveImage":
            return self.zip_widget_values(("filename_prefix",), values)
        if node_type == "CompressImages":
            return self.zip_widget_values(("filename_prefix",), values)
        if node_type == "VAELoader":
            return self.zip_widget_values(("vae_name",), values)
        return {}

    @staticmethod
    def zip_widget_values(keys: tuple[str, ...], values: list[Any]) -> dict[str, Any]:
        return {key: values[index] for index, key in enumerate(keys) if index < len(values)}

    def resolve_image_node_id(self, workflow: dict[str, Any]) -> str:
        if self.settings.image_node_id:
            if self.settings.image_node_id in workflow:
                return self.settings.image_node_id

        for node_id, node_data in workflow.items():
            if not isinstance(node_data, dict):
                continue
            if node_data.get("class_type") == "LoadImage":
                return node_id

        for node_id, node_data in workflow.items():
            if not isinstance(node_data, dict):
                continue
            inputs = node_data.get("inputs", {})
            if isinstance(inputs, dict) and self.settings.image_field in inputs:
                return node_id
        raise ValueError(f"'{self.settings.image_field}' alanını içeren bir node bulunamadı.")

    def _text_input_field_for_node(self, node: dict[str, Any]) -> str:
        ct = node.get("class_type")
        if isinstance(ct, str) and ct in _TEXT_NODE_CLASS_TO_FIELD:
            return _TEXT_NODE_CLASS_TO_FIELD[ct]
        return self.settings.text_field

    @staticmethod
    def _text_node_feeding_string_input(
        workflow: dict[str, Any], encoder_id: str, input_key: str
    ) -> tuple[str, str] | None:
        """
        Qwen/CLIP düğümünde prompt/text hâlâ bir Text düğümüne bağlıysa, metin oraya yazılmalı
        (sadece encoder'a string basmak bazı Comfy sürümlerinde gölgede kalan link yüzünden yetersiz).
        """
        enc = workflow.get(str(encoder_id))
        if not isinstance(enc, dict):
            return None
        ins = enc.get("inputs") or {}
        ref = ins.get(input_key)
        if not isinstance(ref, list) or len(ref) != 2:
            return None
        src = workflow.get(str(ref[0]))
        if not isinstance(src, dict):
            return None
        if str(src.get("class_type") or "") != "Text":
            return None
        return (str(ref[0]), "text")

    def _injection_from_encoder_text_links(self, workflow: dict[str, Any]) -> tuple[str, str] | None:
        for nid, node in workflow.items():
            if not isinstance(node, dict):
                continue
            cls_name = str(node.get("class_type") or "")
            if cls_name == "TextEncodeQwenImageEditPlus":
                p = self._text_node_feeding_string_input(workflow, str(nid), "prompt")
                if p:
                    logger.info(
                        "Prompt Text kaynağı (Qwen link): node=%s -> Text node=%s",
                        nid,
                        p[0],
                    )
                    return p
            if cls_name in (
                "CLIPTextEncode",
                "CLIPTextEncodeSDXL",
                "CLIPTextEncodeSDRefiner",
                "CLIPTextEncodeFlux",
            ):
                p = self._text_node_feeding_string_input(workflow, str(nid), "text")
                if p:
                    logger.info(
                        "Prompt Text kaynağı (CLIP link): node=%s -> Text node=%s",
                        nid,
                        p[0],
                    )
                    return p
        return None

    def _resolve_prompt_injection_target(self, workflow: dict[str, Any]) -> tuple[str, str] | None:
        """(node_id, inputs key) — Qwen 'prompt', CLIP/Text 'text' vb."""
        tid = (self.settings.text_node_id or "").strip()

        def try_node(nid: str) -> tuple[str, str] | None:
            node = workflow.get(nid)
            if not isinstance(node, dict):
                return None
            return (str(nid), self._text_input_field_for_node(node))

        if tid and tid in workflow:
            p = try_node(tid)
            if p:
                return p

        linked = self._injection_from_encoder_text_links(workflow)
        if linked:
            return linked

        preferred = (
            "Text",
            "TextEncodeQwenImageEditPlus",
            "CLIPTextEncode",
            "CLIPTextEncodeSDXL",
            "CLIPTextEncodeSDRefiner",
            "CLIPTextEncodeFlux",
        )
        seen: set[str] = set()
        for cls_name in preferred:
            for nid, node in workflow.items():
                if not isinstance(node, dict):
                    continue
                if str(node.get("class_type")) != cls_name:
                    continue
                s = str(nid)
                if s in seen:
                    continue
                p = try_node(s)
                if p:
                    seen.add(s)
                    logger.info(
                        "Prompt düğümü otomatik seçildi: node=%s class=%s field=%s",
                        p[0],
                        cls_name,
                        p[1],
                    )
                    return p
        return None

    def inject_inputs(
        self,
        workflow: dict[str, Any],
        uploaded_image_name: str,
        caption: str | None,
    ) -> dict[str, Any]:
        image_node_id = self.resolve_image_node_id(workflow)
        workflow[image_node_id].setdefault("inputs", {})[self.settings.image_field] = uploaded_image_name

        if caption is not None:
            target = self._resolve_prompt_injection_target(workflow)
            if target:
                node_id, field = target
                workflow[node_id].setdefault("inputs", {})[field] = caption
                logger.info(
                    "Workflow metin set: node=%s field=%s len=%s",
                    node_id,
                    field,
                    len(caption),
                )
            else:
                logger.warning(
                    "Prompt yazilamadi: workflowda metin düğümü bulunamadi (COMFY_TEXT_NODE_ID=%s).",
                    self.settings.text_node_id,
                )

        return workflow

    async def upload_image(self, image_name: str, image_bytes: bytes) -> dict[str, Any]:
        logger.info("Medya CloLess'a yükleniyor: %s", image_name)
        form = aiohttp.FormData()
        form.add_field("image", image_bytes, filename=image_name)
        form.add_field("type", "input")
        form.add_field("overwrite", "true")
        async with self.session.post("/upload/image", data=form) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def queue_prompt(self, workflow: dict[str, Any]) -> str:
        payload = {"client_id": self.client_id, "prompt": workflow}
        async with self.session.post("/prompt", json=payload) as resp:
            resp.raise_for_status()
            data = await resp.json()
            return data["prompt_id"]

    async def wait_for_outputs(self, prompt_id: str) -> list[dict[str, Any]]:
        logger.info("İşlem bekleniyor... prompt_id=%s", prompt_id)
        history = await self.get_history_outputs(prompt_id, ignore_error=True)
        if history: return history

        await self.ensure_ws()
        loop = asyncio.get_running_loop()
        self._futures[prompt_id] = loop.create_future()

        try:
            done_ws = False
            try:
                done_ws = await asyncio.wait_for(self._futures[prompt_id], timeout=300)
            except asyncio.TimeoutError:
                logger.warning("WebSocket timeout (300s), polling'e devam ediliyor.")

            if not done_ws:
                return await self.wait_for_outputs_polling(prompt_id)
            return await self.get_history_outputs(prompt_id)
        finally:
            self._futures.pop(prompt_id, None)

    async def wait_for_outputs_polling(self, prompt_id: str) -> list[dict[str, Any]]:
        while True:
            history = await self.get_history_outputs(prompt_id, ignore_error=True)
            if history: return history
            await asyncio.sleep(self.settings.poll_interval_seconds)

    async def get_history_outputs(self, prompt_id: str, ignore_error: bool = False) -> list[dict[str, Any]]:
        try:
            async with self.session.get(f"/history/{prompt_id}") as resp:
                if resp.status != 200: return []
                history = await resp.json()

            prompt_history = history.get(prompt_id, {})
            outputs = prompt_history.get("outputs", {})
            status = prompt_history.get("status", {})

            images = self.extract_images(outputs)
            if not images and status.get("status_str") == "error":
                if ignore_error: return []
                raise RuntimeError(f"CloLess hatası: {status}")
            return images
        except Exception:
            if ignore_error: return []
            raise

    def _extract_images_from_node_output(self, node_output: dict[str, Any]) -> list[dict[str, Any]]:
        files: list[dict[str, Any]] = []
        seen: set[tuple[Any, ...]] = set()
        candidates = (
            node_output.get("images", [])
            + node_output.get("files", [])
            + node_output.get("gifs", [])
        )
        ui = node_output.get("ui", {})
        if isinstance(ui, dict):
            candidates += ui.get("images", []) + ui.get("files", []) + ui.get("gifs", [])

        for f in candidates:
            filename = f.get("filename")
            if filename:
                key = (filename, f.get("subfolder", ""), f.get("type", "output"))
                if key not in seen:
                    seen.add(key)
                    files.append(f)
        return files

    def extract_images(self, outputs: dict[str, Any]) -> list[dict[str, Any]]:
        """Nihai düğüm (COMFY_OUTPUT_NODE_ID, varsayılan SaveImage 64) — ara zoom/ölçek çıktıları gönderilmez."""
        pref = self.settings.output_node_id
        if pref:
            raw = outputs.get(pref) or outputs.get(str(pref))
            if raw is None:
                return []
            if isinstance(raw, dict):
                return self._extract_images_from_node_output(raw)
            return []
        files: list[dict[str, Any]] = []
        seen: set[tuple[Any, ...]] = set()
        for node_output in outputs.values():
            if not isinstance(node_output, dict):
                continue
            for f in self._extract_images_from_node_output(node_output):
                fn = f.get("filename")
                if not fn:
                    continue
                key = (fn, f.get("subfolder", ""), f.get("type", "output"))
                if key not in seen:
                    seen.add(key)
                    files.append(f)
        return files

    async def download_image(self, meta: dict[str, Any]) -> bytes:
        params = {"filename": meta["filename"], "subfolder": meta.get("subfolder", ""), "type": meta.get("type", "output")}
        for endpoint in ("/view", "/api/view"):
            try:
                async with self.session.get(endpoint, params=params) as resp:
                    if resp.status == 200:
                        return await resp.read()
            except: continue
        raise RuntimeError(f"Dosya indirilemedi: {meta['filename']}")

    def save_output_file(
        self,
        prompt_id: str,
        filename: str,
        file_bytes: bytes,
        *,
        user_folder: str | None = None,
    ) -> Path:
        name = Path(filename).name
        if user_folder:
            path = self.settings.output_dir / user_folder / "sonrasi" / f"{prompt_id}_{name}"
        else:
            path = self.settings.output_dir / prompt_id / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(file_bytes)
        return path

    async def process_single_output(
        self, prompt_id: str, meta: dict[str, Any], *, user_folder: str | None = None
    ) -> Path:
        content = await self.download_image(meta)
        return self.save_output_file(prompt_id, meta["filename"], content, user_folder=user_folder)

    async def run_workflow(
        self,
        image_name: str,
        image_bytes: bytes,
        caption: str | None,
        *,
        user_folder: str | None = None,
    ) -> list[Path]:
        if user_folder:
            try:
                oncesi_dir = self.settings.output_dir / user_folder / "oncesi"
                oncesi_dir.mkdir(parents=True, exist_ok=True)
                safe_name = Path(image_name).name
                before_path = oncesi_dir / f"{_now_ts()}_{safe_name}"
                before_path.write_bytes(image_bytes)
            except OSError as exc:
                logger.warning("Öncesi fotoğraf outputs'a yazılamadı: %s", exc)

        upload_result = await self.upload_image(image_name, image_bytes)
        uploaded_name = upload_result.get("name", image_name)
        workflow = self.load_workflow()
        prompt = self.inject_inputs(workflow, uploaded_name, caption)
        prompt_id = await self.queue_prompt(prompt)

        metas = await self.wait_for_outputs(prompt_id)
        tasks = [
            self.process_single_output(prompt_id, m, user_folder=user_folder) for m in metas
        ]
        return await asyncio.gather(*tasks)


async def send_result(message, context, user_id, file_path, caption, reply_markup=None):
    bot = context.bot
    ext = file_path.suffix.lower()
    is_photo = ext in {".jpg", ".jpeg", ".png", ".webp"}
    is_video = ext in {".mp4", ".webm", ".mov", ".m4v"}

    try:
        with file_path.open("rb") as f:
            if is_photo:
                try:
                    return await bot.send_photo(
                        chat_id=user_id,
                        photo=f,
                        caption=caption,
                        has_spoiler=True,
                        reply_markup=reply_markup,
                    )
                except Exception as e:
                    logger.warning("Fotoğraf gönderilemedi, doküman olarak deneniyor: %s", e)
            elif is_video:
                try:
                    return await bot.send_video(
                        chat_id=user_id,
                        video=f,
                        caption=caption,
                        has_spoiler=True,
                        reply_markup=reply_markup,
                    )
                except Exception as e:
                    logger.warning("Video gönderilemedi, doküman olarak deneniyor: %s", e)

            f.seek(0)
            try:
                return await bot.send_document(
                    chat_id=user_id,
                    document=f,
                    caption=caption,
                    reply_markup=reply_markup,
                )
            except Exception as e:
                logger.error("Doküman gönderilemedi: %s", e)
                f.seek(0)
                if is_photo:
                    return await message.reply_photo(
                        photo=f,
                        caption=caption,
                        has_spoiler=True,
                        reply_markup=reply_markup,
                    )
                elif is_video:
                    return await message.reply_video(
                        video=f,
                        caption=caption,
                        has_spoiler=True,
                        reply_markup=reply_markup,
                    )
                else:
                    return await message.reply_document(document=f, caption=caption, reply_markup=reply_markup)
    except Exception as e:
        logger.error("Gönderim hatası: %s", e)
    return None


async def _process_media_job(
    *,
    msg,
    status_msg,
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    filename: str,
    file_bytes: bytes,
    prompt: str | None,
    tg_user: User | None = None,
    chest_level: int | None = None,
) -> None:
    client = context.application.bot_data["cloless_client"]
    storage_folder = _telegram_storage_folder_name(tg_user)
    db = _load_users_db()
    lang = _user_language(db, user_id)
    workflow_prompt = await _translate_prompt_to_english(prompt)
    try:
        results = await client.run_workflow(
            filename, file_bytes, workflow_prompt, user_folder=storage_folder
        )

        if not results:
            raise RuntimeError("Çıktı alınamadı.")

        await status_msg.edit_text("✅ Completed, sending..." if lang == "en" else "✅ Tamamlandı, gönderiliyor...")
        sent_messages = await asyncio.gather(
            *[
                send_result(
                    msg,
                    context,
                    user_id,
                    r,
                    ("Processing complete." if lang == "en" else "İşlem tamamlandı.") if i == 0 else None,
                    reply_markup=(
                        build_chest_adjust_markup(lang, chest_level)
                        if i == 0 and chest_level is not None
                        else None
                    ),
                )
                for i, r in enumerate(results)
            ]
        )
        if chest_level is not None:
            try:
                db_after = _load_users_db()
                user_after = _get_user(db_after, int(user_id))
                source_map = (
                    user_after.get("chest_adjust_sources")
                    if isinstance(user_after.get("chest_adjust_sources"), dict)
                    else {}
                )
                for i, sent in enumerate(sent_messages):
                    if i != 0 or sent is None:
                        continue
                    msg_id = getattr(sent, "message_id", None)
                    if msg_id is None:
                        continue
                    source_map[str(msg_id)] = {
                        "result_path": str(results[i]),
                        "filename": results[i].name or filename,
                        "base_prompt": prompt or "",
                        "level": chest_level,
                    }
                user_after["chest_adjust_sources"] = source_map
                _save_users_db(db_after)
            except Exception as exc:
                logger.warning("Chest adjust kaynak eşlemesi kaydedilemedi: %s", exc)
        await status_msg.delete()
    except Exception as e:
        logger.error("Hata! User ID: %s, Error: %s", user_id, e, exc_info=True)
        if isinstance(e, aiohttp.ClientConnectorError):
            settings = context.application.bot_data.get("settings")
            comfyui_url = settings.comfyui_url if isinstance(settings, Settings) else "COMFYUI_URL"
            await status_msg.edit_text(
                (
                    "❌ Could not connect to ComfyUI. Check if ComfyUI is running and the URL is correct "
                    f"(active: {comfyui_url})."
                )
                if lang == "en"
                else "❌ ComfyUI'ye baglanilamadi. ComfyUI acik mi ve URL dogru mu kontrol edin "
                f"(aktif: {comfyui_url})."
            )
        else:
            await status_msg.edit_text("❌ An error occurred. Please try again." if lang == "en" else "❌ Bir hata oluştu. Lütfen tekrar deneyin.")


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    if not msg:
        return
    lang = _lang_from_update(update)
    text = "Please use the website for the service. Payments are available only through this Telegram bot." if lang == "en" else "Hizmet i?in l?tfen web sitemizi kullan?n. ?deme yaln?zca bu Telegram botundan yap?l?r."
    await msg.reply_text(text, reply_markup=build_main_inline_markup(lang), disable_web_page_preview=True)

async def secret_promo_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Gizli promosyon — komut listesinde / yardımda yok."""
    msg = update.effective_message
    tg = update.effective_user
    if not msg or not tg:
        return
    if not await _ensure_channel_access(update, context):
        return
    lang = _lang_from_update(update)
    db = _load_users_db()
    u = _get_user(db, int(tg.id))
    entered_code = (msg.text or "").strip().upper()
    if entered_code == ONE_TIME_PROMO_CODE:
        if u.get("promo_hottok_used"):
            await msg.reply_text(
                "You already used this promo code." if lang == "en" else "Bu promosyon kodunu zaten kullandınız."
            )
            return
        u["promo_hottok_used"] = True
        u["trial_diamonds"] = float(u.get("trial_diamonds", 0.0)) + ONE_TIME_PROMO_DIAMONDS
        u["diamonds"] = float(u.get("diamonds", 0.0)) + ONE_TIME_PROMO_DIAMONDS
        _save_users_db(db)
        await msg.reply_text(
            f"✅ Code accepted! +{ONE_TIME_PROMO_DIAMONDS:.0f} 💎 added to your account."
            if lang == "en"
            else f"✅ Kod kabul edildi! +{ONE_TIME_PROMO_DIAMONDS:.0f} 💎 hesabınıza eklendi."
        )
        return

    u["trial_diamonds"] = float(u.get("trial_diamonds", 0.0)) + SECRET_PROMO_DIAMONDS
    u["diamonds"] = float(u.get("diamonds", 0.0)) + SECRET_PROMO_DIAMONDS
    u["promo_hotok10free_used_count"] = int(u.get("promo_hotok10free_used_count", 0) or 0) + 1
    _save_users_db(db)
    await msg.reply_text(
        f"✅ Code accepted! +{SECRET_PROMO_DIAMONDS:.0f} 💎 added to your account."
        if lang == "en"
        else f"✅ Kod kabul edildi! +{SECRET_PROMO_DIAMONDS:.0f} 💎 hesabınıza eklendi."
    )


async def handle_menu_click(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.effective_message.text
    lang = _lang_from_update(update)
    if not await _ensure_channel_access(update, context):
        return
    user = update.effective_user
    if user:
        db = _load_users_db()
        u = _get_user(db, int(user.id))
        if u.get("awaiting_prompt_input"):
            value = (text or "").strip()
            if not value:
                await update.effective_message.reply_text(
                    "Prompt cannot be empty. Please send your prompt text."
                    if lang == "en"
                    else "Prompt boş olamaz. Lütfen prompt metnini gönderin."
                )
                return
            u["custom_prompt_text"] = value
            u["prompt_mode_enabled"] = True
            u["awaiting_prompt_input"] = False
            _save_users_db(db)
            await update.effective_message.reply_text(
                "✅ Prompt saved. Now send a photo."
                if lang == "en"
                else "✅ Prompt kaydedildi. Şimdi fotoğraf gönder."
            )
            return
    if text in {
        "📸 Fotoğraf Oluştur",
        "⚡ Fotoğrafını işle!",
        "⚡ Fotoğrafımı işle!",
        "⚡️ Fotoğrafımı işle!",
        "⚡️ Process my photo!",
    }:
        await update.effective_message.reply_text(
            "📷 Please send a photo." if lang == "en" else "📷 Lütfen bir fotoğraf gönderin."
        )
    elif text in {_menu_label(lang, "vip"), _menu_label("tr", "vip"), _menu_label("en", "vip")}:
        await buy_command(update, context)
    elif text in {_menu_label(lang, "my"), _menu_label("tr", "my"), _menu_label("en", "my")}:
        await my_command(update, context)
    elif text in {"🚀 Arkadaşlarını Davet Et, 💎 kazan", _menu_label("tr", "invite"), _menu_label("en", "invite")}:
        await invite_command(update, context)
    elif text in {_menu_label("tr", "daily"), _menu_label("en", "daily")}:
        await daily_command(update, context)
    elif text in {"📏 Beden ölçüsü", _menu_label("tr", "chest"), _menu_label("en", "chest")}:
        await size_command(update, context)
    elif text in {_menu_label("tr", "prompt"), _menu_label("en", "prompt")}:
        await prompt_mode_command(update, context)
    elif text == "🎬 Video Oluştur":
        offer_price = _min_video_card_price()
        offer_stars = _stars_for_card_price(offer_price)
        await update.effective_message.reply_text(
            (
                "🎬 Create videos from Mini App.\n"
                f"Minimum video card price: {offer_price:.0f} 💎\n"
                "Tap a button below."
            )
            if lang == "en"
            else (
                "🎬 Videoları Mini App üzerinden oluşturabilirsin.\n"
                f"Minimum video kart fiyatı: {offer_price:.0f} 💎\n"
                "Aşağıdaki butonlardan devam et."
            ),
            reply_markup=build_video_promo_markup(lang, offer_id="minvideo", stars=offer_stars),
            disable_web_page_preview=True,
        )
    elif text in {"❓ Yardım", _menu_label("tr", "help"), _menu_label("en", "help")}:
        await help_command(update, context)
    else:
        await update.effective_message.reply_text(
            "I couldn't understand that command. Please use menu buttons or type /help."
            if lang == "en"
            else "Bu komutu anlayamadim. Lutfen menu butonlarini kullanin veya /help yazin."
        )
    await maybe_send_periodic_ad(update, context, reason="menu_click")


def build_accept_terms_markup(lang: str = "tr") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(
            text=("✅ I accept" if lang == "en" else ("✅ أوافق" if lang == "ar" else "✅ Kabul ediyorum")),
            callback_data="accept_terms",
        )]]
    )


def _age_intro_text(lang: str = "tr") -> str:
    if lang == "en":
        return (
            "🔞 This bot is for users aged 18 and above.\n\n"
            "By continuing, you confirm that you are at least 18 years old."
        )
    if lang == "ar":
        return (
            "🔞 هذا البوت مخصص للمستخدمين بعمر 18 سنة فما فوق.\n\n"
            "بالمتابعة، أنت تؤكد أن عمرك 18 سنة أو أكثر."
        )
    return (
        "🔞 Bu bot yalnızca 18 yaş ve üzeri kullanıcılar içindir.\n\n"
        "Devam ederek en az 18 yaşında olduğunu onaylamış olursun."
    )


def build_age_verify_markup(lang: str = "tr") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(
                text=("✅ I am 18+" if lang == "en" else ("✅ عمري 18+" if lang == "ar" else "✅ 18 yaşından büyüğüm")),
                callback_data="age:ok",
            )],
            [InlineKeyboardButton(
                text=("❌ I am under 18" if lang == "en" else ("❌ عمري أقل من 18" if lang == "ar" else "❌ 18 yaş altıyım")),
                callback_data="age:no",
            )],
        ]
    )


def _welcome_balance_text(user: dict[str, Any], lang: str = "tr") -> str:
    vip = float(user.get("vip_diamonds", 0.0) or 0.0)
    trial = float(user.get("trial_diamonds", 0.0) or 0.0)
    total = _diamonds_total_from_buckets(user)
    if lang == "en":
        heading = "Your ?? balance:\n\n"
        columns = "  VIP      Trial      Total\n-----   ---------   -------\n"
    else:
        heading = "Elmas bakiyen ??:\n\n"
        columns = "  VIP      Deneme      Toplam\n-----   ---------   -------\n"
    table = columns + f"{vip:>5.0f}   {trial:>9.1f}   {total:>7.1f}"
    footer = "Use the button below to buy more diamonds with Telegram Stars." if lang == "en" else "Daha fazla elmas almak i?in a?a??daki Telegram Stars ile sat?n al d??mesine bas."
    return heading + f"<pre>{html.escape(table)}</pre>\n\n" + footer


def _photo_tips_intro_text(lang: str = "tr") -> str:
    return "Open the website to use the service. Payments are made only through this Telegram bot." if lang == "en" else "Hizmeti kullanmak i?in web sitesini a??n. ?demeler yaln?zca bu Telegram botundan yap?l?r."

def build_photo_tips_markup(lang: str = "tr") -> InlineKeyboardMarkup:
    rows = []
    if MINIAPP_URL:
        rows.append([InlineKeyboardButton(text="Open website" if lang == "en" else "Web sitesini a?", web_app=WebAppInfo(url=MINIAPP_URL))])
    rows.append([InlineKeyboardButton(text="Buy with Telegram Stars" if lang == "en" else "Telegram Stars ile ?deme", callback_data="menu:vip")])
    return InlineKeyboardMarkup(rows)

def build_main_inline_markup(lang: str = "tr") -> InlineKeyboardMarkup:
    rows = []
    if MINIAPP_URL:
        rows.append([InlineKeyboardButton(text="Open website" if lang == "en" else "Web sitesini a?", web_app=WebAppInfo(url=MINIAPP_URL))])
    rows.append([InlineKeyboardButton(text="Buy with Telegram Stars" if lang == "en" else "Telegram Stars ile ?deme", callback_data="menu:vip")])
    return InlineKeyboardMarkup(rows)

def _terms_intro_text(lang: str = "tr") -> str:
    if lang == "en":
        return (
            "To continue using this bot, you must first read and accept the Terms of Use.\n"
            "By tapping the ✅ \"I accept\" button below, you confirm that you have read\n"
            "and accepted the terms.\n"
            f"{TERMS_URL}"
        )
    if lang == "ar":
        return (
            "للاستمرار في استخدام هذا البوت، يجب عليك أولاً قراءة شروط الاستخدام وقبولها.\n"
            "بالضغط على زر ✅ \"أوافق\" أدناه، فإنك تؤكد أنك قرأت الشروط\n"
            "ووافقت عليها.\n"
            f"{TERMS_URL}"
        )
    return (
        "Bu botu kullanmaya devam etmek için önce Kullanım\n"
        "Koşullarını okuyup kabul etmeniz gerekmektedir. Aşağıdaki ✅\n"
        "\"Kabul Ediyorum\" butonuna tıklayarak, şartları okuduğunuzu ve\n"
        "kabul ettiğinizi onaylamış olursunuz.\n"
        f"{TERMS_URL}"
    )


def build_mandatory_channel_markup(lang: str = "tr") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(
                ("📢 Join channel" if lang == "en" else ("📢 انضم إلى القناة" if lang == "ar" else "📢 Kanala katıl")),
                url=MANDATORY_CHANNEL_INVITE_URL,
            )],
            [InlineKeyboardButton(
                ("✅ I joined, verify" if lang == "en" else ("✅ انضممت، تحقق" if lang == "ar" else "✅ Katıldım, doğrula")),
                callback_data="verify_channel_join",
            )],
        ]
    )


def build_language_markup(selected_lang: str) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for code, label in SUPPORTED_LANGUAGES.items():
        prefix = "✅ " if code == selected_lang else ""
        rows.append(
            [InlineKeyboardButton(text=f"{prefix}{label}", callback_data=f"lang:set:{code}")]
        )
    return InlineKeyboardMarkup(rows)


def build_chest_adjust_markup(lang: str, level: int) -> InlineKeyboardMarkup:
    title = (
        f"👙 Chest size: {level:+d}"
        if lang == "en"
        else f"👙 Göğüs ölçüsü: {level:+d}"
    )
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("➖1", callback_data="chest:adj:-1"),
                InlineKeyboardButton("➖2", callback_data="chest:adj:-2"),
                InlineKeyboardButton("➖3", callback_data="chest:adj:-3"),
                InlineKeyboardButton("➖4", callback_data="chest:adj:-4"),
                InlineKeyboardButton("➖5", callback_data="chest:adj:-5"),
            ],
            [InlineKeyboardButton(title, callback_data="chest:noop")],
            [
                InlineKeyboardButton("➕1", callback_data="chest:adj:1"),
                InlineKeyboardButton("➕2", callback_data="chest:adj:2"),
                InlineKeyboardButton("➕3", callback_data="chest:adj:3"),
                InlineKeyboardButton("➕4", callback_data="chest:adj:4"),
                InlineKeyboardButton("➕5", callback_data="chest:adj:5"),
            ],
        ]
    )


def _compose_prompt_with_chest(base_prompt: str | None, chest_level: int) -> str | None:
    base = (base_prompt or "").strip()
    if chest_level == 0:
        return base if base else None
    if chest_level > 0:
        chest_line = (
            f"Increase breast size by {chest_level} step(s) while keeping everything else unchanged and natural."
        )
    else:
        chest_line = (
            f"Decrease breast size by {abs(chest_level)} step(s) while keeping everything else unchanged and natural."
        )
    if base:
        return f"{base}\n\n{chest_line}"
    return chest_line


async def _user_in_mandatory_channel(bot, user_id: int) -> bool:
    """Kanal zorunluluğu: bot kanalda yönetici olmalı."""
    channel_targets = _mandatory_channel_targets()
    if not channel_targets:
        logger.warning(
            "Kanal dogrulama hedefi ayarli degil (MANDATORY_CHANNEL_ID/USERNAME). "
            "Davet linki var ama dogrulama yapilamiyor."
        )
        return False
    for channel_target in channel_targets:
        try:
            m = await bot.get_chat_member(chat_id=channel_target, user_id=user_id)
        except TelegramError as exc:
            logger.warning("Kanal üyeliği kontrol edilemedi (%s): %s", channel_target, exc)
            continue
        st = m.status
        if st in (
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER,
            ChatMemberStatus.RESTRICTED,
        ):
            return True
    return False


async def _user_has_mandatory_channel_access(bot, user: User) -> bool:
    """Zorunlu kanal: admin, veya 'Katıldım, doğrula' ile onay (kayıtlı), veya gerçek üyelik."""
    if not _is_mandatory_channel_enabled():
        return True
    if _is_admin_user(user.id, user.username):
        return True
    db = _load_users_db()
    u = _get_user(db, int(user.id))
    if u.get("channel_join_ack"):
        return True
    return await _user_in_mandatory_channel(bot, int(user.id))


async def _ensure_channel_access(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Katildiysa / butonla onayladiysa kullanir, degilse kullanamaz (admin muaf)."""
    if not _is_mandatory_channel_enabled():
        return True
    user = update.effective_user
    if user is None:
        return False
    if await _user_has_mandatory_channel_access(context.bot, user):
        return True

    lang = _lang_from_update(update)
    msg = update.effective_message
    if msg:
        await msg.reply_text(
            (
                "🔒 To use this bot, you must first <b>join our channel</b>.\n\n"
                "1) Tap <b>Join channel</b> below.\n"
                "2) Then tap <b>I joined, verify</b>."
            )
            if lang == "en"
            else "🔒 Bu botu kullanmak için önce <b>kanalımıza katılmanız</b> gerekiyor.\n\n"
            "1) Aşağıdan <b>Kanala katıl</b> ile kanala girin.\n"
            "2) Sonra <b>Katıldım, doğrula</b> butonuna basın.",
            parse_mode="HTML",
            reply_markup=build_mandatory_channel_markup(lang),
            disable_web_page_preview=True,
        )
    return False


def _display_name(user: User | None) -> str:
    if user is None:
        return "Arkadaş"
    fn = (user.first_name or "").strip()
    ln = (user.last_name or "").strip()
    if fn and ln:
        return f"{fn} {ln}"
    if fn:
        return fn
    if ln:
        return ln
    if user.username:
        return f"@{user.username}"
    return "Arkadaş"


def _greeting_user_tag(user: User | None) -> str:
    """Selamlama: mümkünse @kullanıcıadı, yoksa görünen ad."""
    if user is None:
        return "Arkadaş"
    un = (user.username or "").strip()
    if un:
        return f"@{un}"
    return _display_name(user)


def _telegram_storage_folder_name(user: User | None) -> str:
    """outputs/<ad>/oncesi|sonrasi — Telegram @kullanıcıadı; yoksa user_<id>."""
    if user is None:
        return "unknown"
    un = (user.username or "").strip()
    if un:
        safe = "".join(c for c in un if c.isalnum() or c == "_")
        if safe:
            return safe[:80]
    return f"user_{user.id}"


async def send_main_menu(message: Any, settings: Settings, *, chat_user: User | None = None) -> None:
    db = _load_users_db()
    tg_user = chat_user if chat_user is not None else getattr(message, "from_user", None)
    user_id = getattr(tg_user, "id", None)
    lang = _user_language(db, int(user_id)) if user_id is not None else "tr"
    text = ("Open our website to use the service. Payments are handled only in this Telegram bot." if lang == "en" else "Hizmeti kullanmak i?in web sitemizi a??n. ?demeler yaln?zca bu Telegram botundan al?n?r.")
    await message.reply_text(text, reply_markup=build_main_inline_markup(lang), disable_web_page_preview=True)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = list(getattr(context, "args", None) or [])
    if args and (args[0] or "").strip().lower() == "buy":
        await buy_command(update, context)
        return

    referrer_id = _parse_referrer_id_from_start_args(args)
    user = update.effective_user
    if user and referrer_id:
        await _try_referral_reward_on_start(
            context,
            new_user_id=int(user.id),
            referrer_id=int(referrer_id),
        )

    lang = _lang_from_update(update)
    if user and _is_mandatory_channel_enabled() and not _is_admin_user(user.id, user.username):
        if not await _user_has_mandatory_channel_access(context.bot, user):
            await update.effective_message.reply_text(
                (
                    "🔒 To use this bot, you must first <b>join our channel</b>.\n\n"
                    "1) Tap <b>Join channel</b> below.\n"
                    "2) Then tap <b>I joined, verify</b>."
                )
                if lang == "en"
                else "🔒 Bu botu kullanmak için önce <b>kanalımıza katılmanız</b> gerekiyor.\n\n"
                "1) Aşağıdan <b>Kanala katıl</b> ile kanala girin.\n"
                "2) Sonra <b>Katıldım, doğrula</b> butonuna basın.",
                parse_mode="HTML",
                reply_markup=build_mandatory_channel_markup(lang),
                disable_web_page_preview=True,
            )
            return

    db = _load_users_db()
    u = _get_user(db, int(user.id)) if user else None
    if u and _grant_starter_trial_if_needed(u):
        _save_users_db(db)
    # Açılış (/start): zorunlu kanal dışında yaş/şart ekranı yok; doğrudan foto ipuçları.
    if user and u:
        await update.effective_message.reply_text(
            _welcome_balance_text(u, lang),
            parse_mode="HTML",
            reply_markup=build_photo_tips_markup(lang),
            disable_web_page_preview=True,
        )


async def verify_channel_join_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.from_user:
        return
    lang = _lang_from_update(update)
    if not _is_mandatory_channel_enabled():
        await query.answer()
        return

    uid = query.from_user.id
    db = _load_users_db()
    u = _get_user(db, int(uid))
    u["channel_join_ack"] = True
    _save_users_db(db)

    await query.answer("✅ Channel verified!" if lang == "en" else "✅ Kanal doğrulandı!")
    await query.edit_message_text(
        _photo_tips_intro_text(lang),
        reply_markup=build_photo_tips_markup(lang),
        disable_web_page_preview=True,
    )


async def age_verify_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    lang = _lang_from_update(update)
    data = query.data or ""
    await query.answer()
    user_id = query.from_user.id if query.from_user else None
    if user_id is None:
        return
    db = _load_users_db()
    u = _get_user(db, int(user_id))
    if data == "age:ok":
        u["is_adult_verified"] = True
        _save_users_db(db)
        await query.edit_message_text(
            _terms_intro_text(lang),
            reply_markup=build_accept_terms_markup(lang),
            disable_web_page_preview=False,
        )
        return
    await query.edit_message_text(
        "⛔ This bot is restricted to users aged 18+."
        if lang == "en"
        else ("⛔ هذا البوت مخصص فقط للمستخدمين بعمر 18+." if lang == "ar" else "⛔ Bu bot yalnızca 18 yaş ve üzeri kullanıcılar içindir.")
    )


async def accept_terms_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id if query.from_user else None
    lang = _lang_from_update(update)
    if user_id is not None:
        db = _load_users_db()
        u = _get_user(db, int(user_id))
        u["terms_accepted"] = True
        _save_users_db(db)
    await query.edit_message_text(
        _photo_tips_intro_text(lang),
        reply_markup=build_photo_tips_markup(lang),
        disable_web_page_preview=True,
    )


async def photo_tips_ok_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()
    settings = context.application.bot_data["settings"]
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except TelegramError:
        pass
    await send_main_menu(
        query.message,
        settings,
        chat_user=query.from_user if query.from_user else None,
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    if not msg:
        return
    lang = _lang_from_update(update)
    text = "Use /buy to pay with Telegram Stars. Open the website to use the service." if lang == "en" else "Telegram Stars ile ?deme i?in /buy komutunu kullan?n. Hizmeti kullanmak i?in web sitesini a??n."
    await msg.reply_text(text, reply_markup=build_main_inline_markup(lang), disable_web_page_preview=True)

async def ad_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    return

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = _lang_from_update(update)
    user_id = update.effective_user.id if update.effective_user else None
    username = update.effective_user.username if update.effective_user else None
    if not _is_admin_user(user_id, username):
        await update.effective_message.reply_text(
            "This command is for admin only." if lang == "en" else "Bu komut sadece admin içindir."
        )
        return

    db = _load_users_db()
    users = [
        value
        for key, value in db.items()
        if key != _USERS_META_KEY and isinstance(value, dict)
    ]
    total_users = len(users)
    users_with_balance = sum(1 for u in users if _diamonds_total_from_buckets(u) > 0.0)
    vip_users = sum(1 for u in users if float(u.get("vip_diamonds", 0.0) or 0.0) > 0.0)
    terms_accepted = sum(1 for u in users if bool(u.get("terms_accepted")))
    prompt_mode_on = sum(1 for u in users if bool(u.get("prompt_mode_enabled")))

    tr_users = sum(1 for u in users if str(u.get("language", "tr")) == "tr")
    en_users = sum(1 for u in users if str(u.get("language", "tr")) == "en")
    other_lang_users = max(total_users - tr_users - en_users, 0)

    text = (
        "📊 <b>Bot Stats</b>\n\n"
        f"• Total users: <b>{total_users}</b>\n"
        f"• Users with balance: <b>{users_with_balance}</b>\n"
        f"• VIP users: <b>{vip_users}</b>\n"
        f"• Terms accepted: <b>{terms_accepted}</b>\n"
        f"• Prompt mode active: <b>{prompt_mode_on}</b>\n\n"
        "🌍 <b>Languages</b>\n"
        f"• TR: <b>{tr_users}</b>\n"
        f"• EN: <b>{en_users}</b>\n"
        f"• Other: <b>{other_lang_users}</b>"
        if lang == "en"
        else "📊 <b>Bot İstatistikleri</b>\n\n"
        f"• Toplam kullanıcı: <b>{total_users}</b>\n"
        f"• Bakiyesi olan kullanıcı: <b>{users_with_balance}</b>\n"
        f"• VIP kullanıcı: <b>{vip_users}</b>\n"
        f"• Şartları kabul eden: <b>{terms_accepted}</b>\n"
        f"• Prompt modu aktif: <b>{prompt_mode_on}</b>\n\n"
        "🌍 <b>Diller</b>\n"
        f"• TR: <b>{tr_users}</b>\n"
        f"• EN: <b>{en_users}</b>\n"
        f"• Diğer: <b>{other_lang_users}</b>"
    )
    await update.effective_message.reply_text(text, parse_mode="HTML")


async def buy_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _ensure_channel_access(update, context):
        return
    lang = _lang_from_update(update)
    text = (
        "💰 <b>Buy VIP</b> 💎\n\n"
        "Select a package below. Payment is made with <b>Telegram Stars</b> (⭐).\n\n"
        "Purchased VIP diamonds are added to your balance (1 💎 ≈ 1 operation)."
        if lang == "en"
        else "💰 <b>VIP Satın Al</b> 💎\n\n"
        "Aşağıdan bir paket seçin. Ödeme <b>Telegram Stars</b> (⭐) ile yapılır.\n\n"
        "Satın alınan VIP elması bakiyenize eklenir (1 💎 ≈ 1 işlem)."
    )
    await update.effective_message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=build_vip_shop_markup(),
    )


async def shop_vip_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.message:
        return
    if not await _ensure_channel_access(update, context):
        return
    lang = _lang_from_update(update)
    data = query.data or ""
    parts = data.split(":")
    if len(parts) != 3 or parts[0] != "shop" or parts[1] != "vip":
        return
    pkg_id = parts[2]
    pkg = VIP_PACKAGES.get(pkg_id)
    if not pkg:
        await query.answer("Package not found." if lang == "en" else "Paket bulunamadı.", show_alert=True)
        return
    user_id = query.from_user.id if query.from_user else None
    if user_id is None:
        await query.answer("Session error." if lang == "en" else "Oturum hatası.", show_alert=True)
        return
    vip_amt, stars, title = pkg
    payload = f"vip|{pkg_id}|{user_id}"
    if len(payload.encode("utf-8")) > 128:
        logger.error("Fatura payload çok uzun: %s", payload)
        await query.answer("Invoice could not be created." if lang == "en" else "Fatura oluşturulamadı.", show_alert=True)
        return
    await query.answer()
    try:
        await context.bot.send_invoice(
            chat_id=query.message.chat_id,
            title=title,
            description=f"{vip_amt:g} VIP elması — Telegram Stars ile ödeme.",
            payload=payload,
            provider_token=None,
            currency="XTR",
            prices=[LabeledPrice(f"{int(vip_amt)} VIP 💎", int(stars))],
            start_parameter=f"vip_{pkg_id}"[:32],
        )
    except TelegramError as exc:
        logger.warning("send_invoice başarısız: %s", exc)
        await query.message.reply_text(
            "❌ Invoice could not be sent. Please update Telegram or try again later."
            if lang == "en"
            else "❌ Fatura gönderilemedi. Telegram uygulamanızı güncelleyin veya daha sonra tekrar deneyin."
        )


async def shop_card_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.message:
        return
    if not await _ensure_channel_access(update, context):
        return
    lang = _lang_from_update(update)
    data = query.data or ""
    parts = data.split(":")
    if len(parts) != 3 or parts[0] != "shop" or parts[1] != "card":
        return
    offer_id = parts[2]
    if offer_id != "minvideo":
        await query.answer("Offer not found." if lang == "en" else "Teklif bulunamadı.", show_alert=True)
        return
    user_id = query.from_user.id if query.from_user else None
    if user_id is None:
        await query.answer("Session error." if lang == "en" else "Oturum hatası.", show_alert=True)
        return
    diamonds = _min_video_card_price()
    stars = _stars_for_card_price(diamonds)
    title = f"Video Card • {diamonds:.0f} 💎"
    payload = f"card|{offer_id}|{user_id}"
    if len(payload.encode("utf-8")) > 128:
        logger.error("Kart fatura payload çok uzun: %s", payload)
        await query.answer("Invoice could not be created." if lang == "en" else "Fatura oluşturulamadı.", show_alert=True)
        return
    await query.answer()
    try:
        await context.bot.send_invoice(
            chat_id=query.message.chat_id,
            title=title,
            description=(
                f"This payment adds {diamonds:.0f} VIP 💎 (minimum needed for a video card)."
                if lang == "en"
                else f"Bu ödeme {diamonds:.0f} VIP 💎 ekler (video kartı için minimum tutar)."
            ),
            payload=payload,
            provider_token=None,
            currency="XTR",
            prices=[LabeledPrice(f"{diamonds:.0f} VIP 💎", int(stars))],
            start_parameter=f"card_{offer_id}"[:32],
        )
    except TelegramError as exc:
        logger.warning("shop_card send_invoice başarısız: %s", exc)
        await query.message.reply_text(
            "❌ Invoice could not be sent. Please update Telegram or try again later."
            if lang == "en"
            else "❌ Fatura gönderilemedi. Telegram uygulamanızı güncelleyin veya daha sonra tekrar deneyin."
        )


async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.pre_checkout_query
    if not q:
        return
    lang = _lang_from_update(update)
    parsed_vip = _parse_vip_invoice_payload(q.invoice_payload)
    parsed_card = _parse_card_invoice_payload(q.invoice_payload)
    parsed_plan = _parse_plan_invoice_payload(q.invoice_payload)
    if not parsed_vip and not parsed_card and not parsed_plan:
        await q.answer(ok=False, error_message="Invalid payment." if lang == "en" else "Geçersiz ödeme.")
        return
    uid = parsed_vip[1] if parsed_vip else (parsed_card[1] if parsed_card else parsed_plan[1])
    if not q.from_user or (uid is not None and q.from_user.id != uid):
        await q.answer(ok=False, error_message="This payment does not belong to this account." if lang == "en" else "Bu ödeme bu hesaba ait değil.")
        return
    if (q.currency or "").upper() != "XTR":
        await q.answer(ok=False, error_message="Invalid currency." if lang == "en" else "Para birimi geçersiz.")
        return
    if parsed_vip:
        pkg_id = parsed_vip[0]
        pkg = VIP_PACKAGES.get(pkg_id)
        if not pkg:
            await q.answer(ok=False, error_message="Package not found." if lang == "en" else "Paket bulunamadı.")
            return
        _vip_amt, stars, _title = pkg
    elif parsed_card:
        offer_id = parsed_card[0]
        if offer_id != "minvideo":
            await q.answer(ok=False, error_message="Offer not found." if lang == "en" else "Teklif bulunamadı.")
            return
        stars = _stars_for_card_price(_min_video_card_price())
    else:
        plan_id = parsed_plan[0]
        stars = PLAN_STARS_PACKAGES[plan_id][2]
    if int(q.total_amount) != int(stars):
        await q.answer(ok=False, error_message="Amount mismatch." if lang == "en" else "Tutar uyuşmuyor.")
        return
    await q.answer(ok=True)


async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    if not msg or not msg.successful_payment:
        return
    sp = msg.successful_payment
    tg_user = update.effective_user
    if not tg_user:
        return
    lang = _lang_from_update(update)
    parsed_vip = _parse_vip_invoice_payload(sp.invoice_payload)
    parsed_card = _parse_card_invoice_payload(sp.invoice_payload)
    parsed_plan = _parse_plan_invoice_payload(sp.invoice_payload)
    if not parsed_vip and not parsed_card and not parsed_plan:
        logger.warning("successful_payment: payload veya kullanıcı uyuşmuyor")
        return
    uid = parsed_vip[1] if parsed_vip else (parsed_card[1] if parsed_card else parsed_plan[1])
    if uid is not None and uid != tg_user.id:
        logger.warning("successful_payment: payload veya kullanıcı uyuşmuyor")
        return
    if parsed_plan:
        uid = tg_user.id
    if parsed_vip:
        pkg_id = parsed_vip[0]
        pkg = VIP_PACKAGES.get(pkg_id)
        if not pkg:
            logger.warning("successful_payment: bilinmeyen paket %s", pkg_id)
            return
        vip_amt, stars, _title = pkg
    elif parsed_card:
        offer_id = parsed_card[0]
        if offer_id != "minvideo":
            logger.warning("successful_payment: bilinmeyen kart teklifi %s", offer_id)
            return
        vip_amt = _min_video_card_price()
        stars = _stars_for_card_price(vip_amt)
    else:
        plan_id = parsed_plan[0]
        _plan, _billing, stars, _days = PLAN_STARS_PACKAGES[plan_id]
    if (sp.currency or "").upper() != "XTR" or int(sp.total_amount) != int(stars):
        logger.warning("successful_payment: tutar veya para birimi uyuşmuyor")
        return
    charge_id = sp.telegram_payment_charge_id
    if not charge_id:
        logger.warning("successful_payment: telegram_payment_charge_id yok")
        return

    db = _load_users_db()
    meta = _users_meta(db)
    seen: list = meta["star_charge_ids"]
    if charge_id in seen:
        logger.info("Yinelenen Stars ödemesi yok sayıldı: %s", charge_id)
        return
    seen.append(charge_id)
    if len(seen) > _PROCESSED_STAR_PAYMENTS_CAP:
        meta["star_charge_ids"] = seen[-_PROCESSED_STAR_PAYMENTS_CAP:]

    user = _get_user(db, tg_user.id)
    if parsed_plan:
        plan_id = parsed_plan[0]
        plan, billing, _stars, days = PLAN_STARS_PACKAGES[plan_id]
        now = datetime.now(timezone.utc)
        previous_expiry = user.get("subscription_expires_at")
        if user.get("subscription_plan") == plan and previous_expiry:
            try:
                parsed_expiry = datetime.fromisoformat(str(previous_expiry))
                if parsed_expiry.tzinfo is None:
                    parsed_expiry = parsed_expiry.replace(tzinfo=timezone.utc)
                if parsed_expiry > now:
                    now = parsed_expiry
            except (TypeError, ValueError):
                pass
        user["subscription_plan"] = plan
        user["subscription_billing"] = billing
        user["subscription_expires_at"] = (now + timedelta(days=days)).isoformat()
        user["subscription_stars_charge_id"] = charge_id
    else:
        user["vip_diamonds"] = float(user.get("vip_diamonds", 0.0)) + vip_amt
        user["diamonds"] = float(user.get("diamonds", 0.0)) + vip_amt
    _save_users_db(db)

    if parsed_plan:
        plan_id = parsed_plan[0]
        plan, billing, stars, _days = PLAN_STARS_PACKAGES[plan_id]
        await msg.reply_text(
            f"✅ {plan.title()} {billing} plan activated ({stars} ⭐)."
            if lang == "en"
            else f"✅ {plan.title()} {('yıllık' if billing == 'yearly' else 'aylık')} planınız etkinleştirildi ({stars} ⭐)."
        )
        return

    await msg.reply_text(
        (
            f"✅ Payment received! <b>+{vip_amt:g} VIP 💎</b> has been added to your account.\n\n"
            "To see your balance: /my"
        )
        if lang == "en"
        else f"✅ Ödeme alındı! <b>+{vip_amt:g} VIP 💎</b> hesabınıza eklendi.\n\n"
        "Bakiyeyi görmek için: /my",
        parse_mode="HTML",
    )


async def my_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _ensure_channel_access(update, context):
        return
    user_id = update.effective_user.id if update.effective_user else None
    db = _load_users_db()
    if user_id is None:
        vip = deneme = toplam = 0.0
    else:
        user = _get_user(db, int(user_id))
        vip = float(user.get("vip_diamonds", 0.0))
        deneme = float(user.get("trial_diamonds", 0.0))
        toplam = _diamonds_total_from_buckets(user)

    table = (
        ("  VIP      Trial      Total\n" if _lang_from_update(update) == "en" else "  VIP      Deneme      Toplam\n")
        + "-----   ---------   -------\n"
        f"{vip:>5.0f}   {deneme:>9.1f}   {toplam:>7.1f}"
    )
    lang = _lang_from_update(update)
    await update.effective_message.reply_text(
        ("Your 💎:\n\n" if lang == "en" else "Senin 💎:\n\n")
        +
        f"<pre>{html.escape(table)}</pre>",
        parse_mode="HTML",
        reply_markup=build_main_inline_markup(lang),
    )


async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    if not await _ensure_channel_access(update, context):
        return
    await query.answer()
    data = query.data or ""
    if not data.startswith("menu:"):
        return
    action = data.split(":", 1)[1]
    if action == "vip":
        await buy_command(update, context)
    elif action == "invite":
        await invite_command(update, context)
    elif action == "daily":
        await daily_command(update, context)
    elif action == "photo":
        await query.message.reply_text("📷 Please send a photo." if _lang_from_update(update) == "en" else "📷 Lütfen bir fotoğraf gönderin.")
    elif action == "prompt":
        await prompt_mode_command(update, context)
    elif action == "chest":
        await size_command(update, context)


async def invite_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _ensure_channel_access(update, context):
        return
    bot_username = getattr(getattr(context, "bot", None), "username", None)
    user_id = update.effective_user.id if update.effective_user else None
    if bot_username and user_id:
        lang = _lang_from_update(update)
        link = f"https://t.me/{bot_username}?start=ref_{user_id}"
        db = _load_users_db()
        user = _get_user(db, int(user_id))
        count = int(user.get("referrals_count", 0) or 0)
        earned = float(user.get("referrals_earned", 0.0) or 0.0)
        await update.effective_message.reply_text(
            (
                "🚀 Invite friends, earn 💎\n\n"
                f"- For each new user: **+{REFERRAL_REWARD_DIAMONDS:g} 💎**\n"
                f"- Your invites: **{count}**\n"
                f"- You earned: **{earned:.1f} 💎**\n\n"
                "Use the button below to share."
            )
            if lang == "en"
            else "🚀 Arkadaşlarını davet et, 💎 kazan\n\n"
            f"- Her yeni kullanıcı için: **+{REFERRAL_REWARD_DIAMONDS:g} 💎**\n"
            f"- Davetlerin: **{count}**\n"
            f"- Kazandığın: **{earned:.1f} 💎**\n\n"
            "Arkadaşlarınla paylaşmak için aşağıdaki butonu kullan.",
            parse_mode="Markdown",
            disable_web_page_preview=True,
            reply_markup=build_invite_markup(link, lang),
        )
    else:
        await update.effective_message.reply_text(
            "🚀 Arkadaşlarını davet et, 💎 kazan\n\n"
            "Davet linki üretilemedi. Lütfen tekrar deneyin."
        )


async def daily_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = _lang_from_update(update)
    user_id = update.effective_user.id if update.effective_user else None
    if user_id is None:
        await update.effective_message.reply_text("🎁 Daily Gift\n\nAn error occurred." if lang == "en" else "🎁 Günlük Hediye\n\nBir hata oluştu.")
        return
    eff = update.effective_user
    if eff and (
        _is_mandatory_channel_enabled()
        and not _is_admin_user(user_id, eff.username)
        and not await _user_has_mandatory_channel_access(context.bot, eff)
    ):
        await update.effective_message.reply_text(
            (
                "🔒 To claim the daily gift, you must first <b>join our channel</b>.\n\n"
                "1) Tap <b>Join channel</b> below.\n"
                "2) Then tap <b>I joined, verify</b>."
            )
            if lang == "en"
            else "🔒 Günlük hediyeyi alabilmek için önce <b>kanalımıza katılmanız</b> gerekiyor.\n\n"
            "1) Aşağıdan <b>Kanala katıl</b> ile kanala girin.\n"
            "2) Sonra <b>Katıldım, doğrula</b> butonuna basın.",
            parse_mode="HTML",
            reply_markup=build_mandatory_channel_markup(lang),
            disable_web_page_preview=True,
        )
        return

    db = _load_users_db()
    user = _get_user(db, int(user_id))
    remaining = _daily_remaining_seconds(user)
    await update.effective_message.reply_text(
        daily_gift_message_html(lang),
        parse_mode="HTML",
        reply_markup=build_daily_gift_markup(remaining, lang),
        disable_web_page_preview=True,
    )


async def daily_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    data = query.data or ""
    lang = _lang_from_update(update)
    if data == "daily:status":
        await query.answer("Please wait ⏳" if lang == "en" else "Henüz bekleyin ⏳", show_alert=False)
        return

    if data == "daily:back":
        await query.answer()
        user_id = query.from_user.id if query.from_user else None
        if user_id is None:
            return
        db = _load_users_db()
        user = _get_user(db, int(user_id))
        remaining = _daily_remaining_seconds(user)
        await query.message.reply_text(
            daily_gift_message_html(lang),
            parse_mode="HTML",
            reply_markup=build_daily_gift_markup(remaining, lang),
            disable_web_page_preview=True,
        )
        return

    if data != "daily:claim":
        return

    user_id = query.from_user.id if query.from_user else None
    if user_id is None:
        if lang == "en":
            await query.answer("An error occurred.", show_alert=True)
        else:
            await query.answer("Bir hata oluştu.", show_alert=True)
        return
    if query.from_user and (
        _is_mandatory_channel_enabled()
        and not _is_admin_user(user_id, query.from_user.username)
        and not await _user_has_mandatory_channel_access(context.bot, query.from_user)
    ):
        await query.answer(
            "Please join the channel first."
            if lang == "en"
            else "Lütfen önce kanala katılın.",
            show_alert=True,
        )
        await query.message.reply_text(
            (
                "🔒 To claim the daily gift, you must first <b>join our channel</b>.\n\n"
                "1) Tap <b>Join channel</b> below.\n"
                "2) Then tap <b>I joined, verify</b>."
            )
            if lang == "en"
            else "🔒 Günlük hediyeyi alabilmek için önce <b>kanalımıza katılmanız</b> gerekiyor.\n\n"
            "1) Aşağıdan <b>Kanala katıl</b> ile kanala girin.\n"
            "2) Sonra <b>Katıldım, doğrula</b> butonuna basın.",
            parse_mode="HTML",
            reply_markup=build_mandatory_channel_markup(lang),
            disable_web_page_preview=True,
        )
        return

    db = _load_users_db()
    user = _get_user(db, int(user_id))
    remaining = _daily_remaining_seconds(user)
    if remaining > 0:
        if lang == "en":
            await query.answer("Not ready yet.", show_alert=True)
        else:
            await query.answer("Süre henüz dolmadı.", show_alert=True)
        return

    await query.answer()
    user["daily_last_ts"] = _now_ts()
    user["trial_diamonds"] = float(user.get("trial_diamonds", 0.0)) + DAILY_REWARD_DIAMONDS
    user["diamonds"] = float(user.get("diamonds", 0.0)) + DAILY_REWARD_DIAMONDS
    _save_users_db(db)

    total_balance = _diamonds_total_from_buckets(user)
    chat_id = query.message.chat_id

    try:
        await query.message.delete()
    except Exception as exc:
        logger.debug("Günlük mesaj silinemedi (normal olabilir): %s", exc)

    gif_path = _daily_success_gif_local_path()
    if gif_path:
        try:
            with open(gif_path, "rb") as gif_f:
                await context.bot.send_animation(
                    chat_id=chat_id,
                    animation=InputFile(gif_f, filename=gif_path.name),
                )
        except Exception as exc:
            logger.warning("Günlük başarı GIF dosyası gönderilemedi: %s", exc)
    elif DAILY_SUCCESS_GIF_FILE_ID:
        try:
            await context.bot.send_animation(
                chat_id=chat_id,
                animation=DAILY_SUCCESS_GIF_FILE_ID,
            )
        except Exception as exc:
            logger.warning("Günlük başarı GIF'i gönderilemedi (file_id kontrol edin): %s", exc)

    await context.bot.send_message(
        chat_id=chat_id,
        text=daily_success_message_plain(DAILY_REWARD_DIAMONDS, total_balance, lang),
        reply_markup=build_daily_success_markup(lang),
    )


async def lang_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _ensure_channel_access(update, context):
        return
    db = _load_users_db()
    user_id = update.effective_user.id if update.effective_user else None
    selected = _user_language(db, user_id)
    selected_label = SUPPORTED_LANGUAGES.get(selected, "Türkçe")
    await update.effective_message.reply_text(
        "🌍 Dil seçimi / Language selection\n\n"
        f"{'Current language' if selected == 'en' else 'Mevcut dil'}: {selected_label}\n"
        f"{'Select a language:' if selected == 'en' else 'Bir dil seçin:'}",
        reply_markup=build_language_markup(selected),
    )


async def set_language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    data = query.data or ""
    parts = data.split(":")
    if len(parts) != 3:
        return
    lang = parts[2].lower()
    if lang not in SUPPORTED_LANGUAGES:
        await query.answer("Invalid language selection.", show_alert=True)
        return
    user_id = query.from_user.id if query.from_user else None
    if user_id is None:
        await query.answer("User not found.", show_alert=True)
        return
    db = _load_users_db()
    user = _get_user(db, int(user_id))
    user["language"] = lang
    _save_users_db(db)
    label = SUPPORTED_LANGUAGES[lang]
    await query.answer(f"Language updated: {label}" if lang == "en" else f"Dil güncellendi: {label}")
    await query.edit_message_text(
        "🌍 Dil seçimi / Language selection\n\n"
        f"{'Current language' if lang == 'en' else 'Mevcut dil'}: {label}\n"
        f"{'Select a language:' if lang == 'en' else 'Bir dil seçin:'}",
        reply_markup=build_language_markup(lang),
    )


async def chest_noop_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    lang = _lang_from_update(update)
    await query.answer(
        "Use -1 / +1 buttons. Each change costs 0.5 💎."
        if lang == "en"
        else "-1 / +1 butonlarını kullanın. Her ayar 0.5 💎 maliyetlidir.",
        show_alert=False,
    )


async def chest_adjust_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.from_user or not query.message:
        return
    if not await _ensure_channel_access(update, context):
        return
    lang = _lang_from_update(update)
    data = query.data or ""
    parts = data.split(":")
    if len(parts) != 3:
        return
    try:
        delta = int(parts[2])
    except ValueError:
        await query.answer("Invalid value." if lang == "en" else "Geçersiz değer.", show_alert=True)
        return
    if delta not in (-5, -4, -3, -2, -1, 1, 2, 3, 4, 5):
        await query.answer("Invalid value." if lang == "en" else "Geçersiz değer.", show_alert=True)
        return

    user_id = int(query.from_user.id)
    db = _load_users_db()
    user = _get_user(db, user_id)
    source_map = user.get("chest_adjust_sources") if isinstance(user.get("chest_adjust_sources"), dict) else {}
    source_key = str(query.message.message_id)
    source_state = source_map.get(source_key) if isinstance(source_map.get(source_key), dict) else {}
    result_path = str(source_state.get("result_path") or "")
    filename = str(source_state.get("filename") or "")
    base_prompt = str(source_state.get("base_prompt") or "")
    current_level = int(source_state.get("level", 0) or 0)
    if not result_path or not filename:
        await query.answer(
            "Please process a photo first."
            if lang == "en"
            else "Lütfen önce bir fotoğraf işleyin.",
            show_alert=True,
        )
        return

    target_level = max(CHEST_ADJUST_MIN, min(CHEST_ADJUST_MAX, current_level + delta))
    if target_level == current_level:
        await query.answer(
            "Limit reached (-5 to +5)." if lang == "en" else "Sınırdasınız (-5 ile +5).",
            show_alert=True,
        )
        return

    bal = _diamonds_total_from_buckets(user)
    if bal + 1e-9 < CHEST_ADJUST_COST_DIAMONDS:
        await query.answer(
            "Not enough 💎. Each adjustment costs 0.5 💎."
            if lang == "en"
            else "Yeterli 💎 yok. Her ayar 0.5 💎 maliyetlidir.",
            show_alert=True,
        )
        return

    _deduct_diamonds(user, CHEST_ADJUST_COST_DIAMONDS)
    source_map[source_key] = {
        "result_path": result_path,
        "filename": filename,
        "base_prompt": base_prompt,
        "level": target_level,
    }
    user["chest_adjust_sources"] = source_map
    _save_users_db(db)

    await query.answer(
        (
            f"Adjustment applied ({target_level:+d}). -{CHEST_ADJUST_COST_DIAMONDS:g} 💎"
        )
        if lang == "en"
        else f"Ayar uygulandı ({target_level:+d}). -{CHEST_ADJUST_COST_DIAMONDS:g} 💎"
    )
    try:
        await query.edit_message_reply_markup(
            reply_markup=build_chest_adjust_markup(lang, target_level)
        )
    except TelegramError:
        pass

    status_msg = await query.message.reply_text(
        "⏳ Reprocessing with chest adjustment..."
        if lang == "en"
        else "⏳ Göğüs ölçüsü ayarıyla tekrar işleniyor..."
    )
    source_filename = filename
    try:
        source_path = Path(result_path)
        if not source_path.exists() or not source_path.is_file():
            raise FileNotFoundError(result_path)
        file_bytes = source_path.read_bytes()
        source_filename = source_path.name or source_filename
    except Exception as exc:
        logger.error("Chest adjust kaynak sonuç dosyası okunamadı: %s", exc, exc_info=True)
        await status_msg.edit_text(
            "❌ Could not read selected result image. Please use buttons under a recent result."
            if lang == "en"
            else "❌ Seçilen sonuç görseli okunamadı. Lütfen son bir sonucun altındaki butonları kullanın."
        )
        return

    adjusted_prompt = _compose_prompt_with_chest(base_prompt, target_level)
    asyncio.create_task(
        _process_media_job(
            msg=query.message,
            status_msg=status_msg,
            context=context,
            user_id=user_id,
            filename=source_filename,
            file_bytes=bytes(file_bytes),
            prompt=adjusted_prompt,
            tg_user=query.from_user,
            chest_level=target_level,
        )
    )


async def prompt_mode_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _ensure_channel_access(update, context):
        return
    lang = _lang_from_update(update)
    user = update.effective_user
    msg = update.effective_message
    if not user or not msg:
        return
    db = _load_users_db()
    u = _get_user(db, int(user.id))
    enabled = bool(u.get("prompt_mode_enabled"))
    if enabled:
        u["awaiting_prompt_input"] = False
        u["prompt_mode_enabled"] = False
        u["custom_prompt_text"] = ""
        _save_users_db(db)
        await msg.reply_text(
            "✅ Prompt mode has been turned off. Send a photo normally."
            if lang == "en"
            else "✅ Prompt modu kapatıldı. Fotoğrafı normal şekilde gönderebilirsin."
        )
        return

    u["awaiting_prompt_input"] = False
    u["prompt_mode_enabled"] = True
    _save_users_db(db)
    await msg.reply_text(
        "📝 Prompt mode is active.\nSend a photo first and write your prompt in the photo caption."
        if lang == "en"
        else "📝 Prompt modu aktif.\nÖnce fotoğraf gönder ve promptunu fotoğraf açıklamasına yaz."
    )


async def size_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _ensure_channel_access(update, context):
        return
    lang = _lang_from_update(update)
    await update.effective_message.reply_text(
        (
            "👙 Chest size adjustment is active.\n\n"
            "After your photo is processed, use the -/+ buttons under the result.\n"
            "Each adjustment costs 0.5 💎 and supports levels between -5 and +5."
        )
        if lang == "en"
        else "👙 Göğüs ölçüsü ayarı aktif.\n\n"
        "Fotoğrafın işlendikten sonra sonucun altındaki -/+ butonlarını kullan.\n"
        "Her ayar 0.5 💎 maliyetlidir ve -5 ile +5 aralığını destekler."
    )


async def post_init(app: Application) -> None:
    settings = app.bot_data["settings"]
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
    app.bot_data["settings"] = Settings(
        telegram_token=settings.telegram_token,
        comfyui_url=resolved_url,
        workflow_path=settings.workflow_path,
        output_dir=settings.output_dir,
        image_node_id=settings.image_node_id,
        image_field=settings.image_field,
        text_node_id=settings.text_node_id,
        text_field=settings.text_field,
        output_node_id=settings.output_node_id,
        poll_interval_seconds=settings.poll_interval_seconds,
    )
    session = aiohttp.ClientSession(
        base_url=resolved_url,
        headers=comfyui_headers,
        connector=aiohttp.TCPConnector(limit=100, keepalive_timeout=30)
    )
    app.bot_data["cloless_client"] = CloLessClient(app.bot_data["settings"], session)
    app.bot_data["http_session"] = session
    logger.info("Bot ComfyUI adresi: %s", resolved_url)
    if _is_mandatory_channel_enabled() and not _mandatory_channel_target():
        logger.warning(
            "Kanal daveti aktif ama dogrulama hedefi yok. "
            "MANDATORY_CHANNEL_ID (-100...) veya MANDATORY_CHANNEL_USERNAME ayarlayin."
        )
    try:
        await app.bot.set_my_commands(
            [
                BotCommand("start", "🚀 Başlat"),
                BotCommand("buy", "💰 Buy VIP / VIP Satın Al"),
                BotCommand("my", "👀 Check account / Hesabım"),
                BotCommand("invite", "🚀 Invite friends / Davet"),
                BotCommand("daily", "🎁 Daily gift / Günlük hediye"),
                BotCommand("lang", "🌍 Language / Dil"),
                BotCommand("size", "👙 Chest size / Beden ölçüsü"),
                BotCommand("help", "❓ Help / Yardım"),
            ]
        )
        logger.info("Bot komut menüsü ayarlandı.")
    except Exception as exc:
        logger.warning("Bot komut menüsü ayarlanamadı: %s", exc)
    try:
        if MINIAPP_URL:
            await app.bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(
                    text="HOTTOK",
                    web_app=WebAppInfo(url=MINIAPP_URL),
                )
            )
            logger.info("Sohbet menu butonu: Mini App (%s)", MINIAPP_URL)
        else:
            await app.bot.set_chat_menu_button(menu_button=MenuButtonDefault())
            logger.info("Sohbet menu butonu: varsayilan (MINIAPP_URL bos).")
    except Exception as exc:
        logger.warning("Sohbet menu butonu ayarlanamadi: %s", exc)
    try:
        if app.job_queue and AD_BROADCAST_INTERVAL_SECONDS > 0:
            first_delay_seconds = max(1, min(AD_BROADCAST_INTERVAL_SECONDS, AD_BROADCAST_FIRST_DELAY_SECONDS))
            app.job_queue.run_repeating(
                hourly_ad_broadcast_job,
                interval=AD_BROADCAST_INTERVAL_SECONDS,
                first=first_delay_seconds,
                name="hourly_ad_broadcast",
            )
            logger.info(
                "Saatlik reklam zamanlayıcısı aktif: interval=%s sn, first=%s sn",
                AD_BROADCAST_INTERVAL_SECONDS,
                first_delay_seconds,
            )
        elif AD_BROADCAST_INTERVAL_SECONDS > 0:
            global _ad_broadcast_fallback_task
            if _ad_broadcast_fallback_task is None or _ad_broadcast_fallback_task.done():
                _ad_broadcast_fallback_task = asyncio.create_task(_hourly_ad_broadcast_fallback_loop(app))
                logger.info(
                    "Saatlik reklam fallback döngüsü aktif: interval=%s sn, first=%s sn",
                    AD_BROADCAST_INTERVAL_SECONDS,
                    max(1, min(AD_BROADCAST_INTERVAL_SECONDS, AD_BROADCAST_FIRST_DELAY_SECONDS)),
                )
    except Exception as exc:
        logger.warning("Saatlik reklam zamanlayıcısı başlatılamadı: %s", exc)


async def post_stop(app: Application) -> None:
    global _ad_broadcast_fallback_task
    if _ad_broadcast_fallback_task and not _ad_broadcast_fallback_task.done():
        _ad_broadcast_fallback_task.cancel()
        with suppress(asyncio.CancelledError):
            await _ad_broadcast_fallback_task
    _ad_broadcast_fallback_task = None
    session = app.bot_data.get("http_session")
    if session:
        await session.close()
    global _translate_http_session
    if _translate_http_session and not _translate_http_session.closed:
        await _translate_http_session.close()


def main() -> None:
    settings = Settings.from_env()
    app = Application.builder().token(settings.telegram_token).post_init(post_init).post_stop(post_stop).build()
    app.bot_data["settings"] = settings
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CallbackQueryHandler(verify_channel_join_callback, pattern="^verify_channel_join$"))
    app.add_handler(CallbackQueryHandler(age_verify_callback, pattern=r"^age:(ok|no)$"))
    app.add_handler(CallbackQueryHandler(accept_terms_callback, pattern="^accept_terms$"))
    app.add_handler(CallbackQueryHandler(photo_tips_ok_callback, pattern="^photo_tips_ok$"))
    app.add_handler(CallbackQueryHandler(daily_callback, pattern="^daily:"))
    app.add_handler(CallbackQueryHandler(chest_adjust_callback, pattern=r"^chest:adj:(-?[1-5])$"))
    app.add_handler(CallbackQueryHandler(chest_noop_callback, pattern=r"^chest:noop$"))
    app.add_handler(CallbackQueryHandler(shop_vip_callback, pattern=r"^shop:vip:"))
    app.add_handler(CallbackQueryHandler(shop_card_callback, pattern=r"^shop:card:"))
    app.add_handler(CallbackQueryHandler(set_language_callback, pattern=r"^lang:set:"))
    app.add_handler(CallbackQueryHandler(main_menu_callback, pattern="^menu:(vip|invite|daily|photo|prompt|chest)$"))
    app.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    app.add_handler(CommandHandler("buy", buy_command))
    app.add_handler(CommandHandler("ad", ad_command))
    app.add_handler(CommandHandler("my", my_command))
    app.add_handler(CommandHandler("invite", invite_command))
    app.add_handler(CommandHandler("daily", daily_command))
    app.add_handler(CommandHandler("lang", lang_command))
    app.add_handler(CommandHandler("size", size_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))
    app.add_handler(
        MessageHandler(
            filters.TEXT
            & ~filters.COMMAND
            & filters.Regex(f"^({SECRET_PROMO_CODE}|{ONE_TIME_PROMO_CODE})$"),
            secret_promo_callback,
        )
    )
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu_click))
    app.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO | filters.Document.IMAGE | filters.Document.VIDEO, handle_photo))
    app.run_polling()


if __name__ == "__main__":
    main()
