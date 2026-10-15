"""Kanal görevleri: paylaşılan depolama, doğrulama, elmas ödülü (ana bot + görev botu)."""
from __future__ import annotations

import asyncio
import html
import json
import logging
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputFile, Update
from telegram.constants import ChatMemberStatus
from telegram.error import TelegramError
from telegram.ext import ContextTypes
from telegram.ext._application import ApplicationHandlerStop

from bot import (
    DATA_DIR,
    SUPPORTED_LANGUAGES,
    _USERS_META_KEY,
    _diamonds_total_from_buckets,
    _get_user,
    _has_configured_admin_user_ids,
    _is_admin_user,
    _load_users_db,
    _save_users_db,
    register_runtime_admin,
)

logger = logging.getLogger(__name__)

PROJECT_DIR = Path(__file__).resolve().parent
_cached_task_bot_username: str = ""

TASK_CHANNELS_PATH = DATA_DIR / "task_channels.json"
TASK_CHANNEL_REWARD = float(os.getenv("TASK_CHANNEL_REWARD", "0.5"))
MAIN_BOT_USERNAME = (
    (os.getenv("MAIN_BOT_USERNAME") or os.getenv("BOT_USERNAME") or "").strip().lstrip("@")
)
TASK_BOT_USERNAME = (os.getenv("TASK_BOT_USERNAME") or "").strip().lstrip("@")
MAIN_BOT_TOKEN = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
TASK_BOT_TOKEN = (os.getenv("TASK_BOT_TOKEN") or "").strip()

MANDATORY_CHANNEL_INVITE_URL = (
    os.getenv("MANDATORY_CHANNEL_INVITE_URL", "https://t.me/+NrJM_MrRr-xhZjFk") or ""
).strip()
MANDATORY_CHANNEL_ID = (os.getenv("MANDATORY_CHANNEL_ID") or "").strip()
MANDATORY_CHANNEL_USERNAME = (os.getenv("MANDATORY_CHANNEL_USERNAME") or "").strip()

TASK_AUTO_APPROVE_JOIN = (os.getenv("TASK_AUTO_APPROVE_JOIN", "1") or "1").strip().lower() not in (
    "0",
    "false",
    "no",
    "off",
)

_TME_INVITE_RE = re.compile(r"t\.me/(\+[^/?#\s]+)", re.I)
_TME_RE = re.compile(r"t\.me/([^/?#\s]+)", re.I)

PENDING_ADD_CHANNEL_KEY = "pending_add_channel"
PENDING_REMOVE_CHANNEL_KEY = "pending_remove_channel"


def _looks_like_channel_input(text: str) -> bool:
    t = normalize_channel_input(text)
    if not t:
        return False
    lower = t.lower()
    if t.startswith("@") or t.startswith("-100") or lower.startswith("http"):
        return True
    if "t.me/" in lower:
        return True
    if t.startswith("+"):
        return True
    return False


def normalize_channel_input(raw: str) -> str:
    t = (raw or "").strip()
    if not t:
        return t
    lower = t.lower()
    if lower.startswith("t.me/"):
        return f"https://{t}" if not lower.startswith("http") else t
    if re.fullmatch(r"\+[A-Za-z0-9_-]+", t):
        return t
    if (
        not t.startswith("@")
        and not t.startswith("-")
        and not lower.startswith("http")
        and re.fullmatch(r"[A-Za-z0-9_]{3,32}", t)
    ):
        return f"@{t.lstrip('@')}"
    return t


def _is_private_invite_arg(raw: str) -> bool:
    t = normalize_channel_input(raw)
    if "+" not in t:
        return False
    lower = t.lower()
    return lower.startswith("http") or "t.me/" in lower or t.startswith("+")


def _private_invite_url(raw: str) -> str:
    t = normalize_channel_input(raw)
    if t.startswith("http"):
        return t
    if "t.me/" in t.lower():
        return t if t.startswith("http") else f"https://{t.lstrip('/')}"
    return t


TASK_JOIN_REQUESTS_PATH = DATA_DIR / "task_join_requests.json"


def _ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_task_channels_db() -> dict[str, Any]:
    _ensure_data_dir()
    if not TASK_CHANNELS_PATH.exists():
        return {"channels": []}
    try:
        raw = json.loads(TASK_CHANNELS_PATH.read_text(encoding="utf-8")) or {}
    except Exception:
        raw = {}
    if not isinstance(raw, dict):
        raw = {}
    channels = raw.get("channels")
    if not isinstance(channels, list):
        channels = []
    return {"channels": channels}


def save_task_channels_db(db: dict[str, Any]) -> None:
    _ensure_data_dir()
    TASK_CHANNELS_PATH.write_text(json.dumps(db, ensure_ascii=False, indent=2), encoding="utf-8")


def _extract_tme_username(text: str) -> str | None:
    m = _TME_RE.search(text or "")
    if not m:
        return None
    slug = (m.group(1) or "").strip().strip("/")
    if not slug or slug.startswith("+"):
        return None
    return f"@{slug}"


def _invite_url_from_target(username: str | None, fallback: str = "") -> str:
    if username:
        return f"https://t.me/{username.lstrip('@')}"
    return fallback


def ensure_default_task_channels() -> int:
    """Zorunlu kanalı görev listesine ekler (liste boşsa). Dönen: eklenen kanal sayısı."""
    if not (MANDATORY_CHANNEL_INVITE_URL or MANDATORY_CHANNEL_ID or MANDATORY_CHANNEL_USERNAME):
        return 0

    db = load_task_channels_db()
    channels: list[dict[str, Any]] = list(db.get("channels") or [])
    if channels:
        return 0

    username = MANDATORY_CHANNEL_USERNAME.strip()
    if username and not username.startswith("@"):
        username = f"@{username}"

    title = "Resmi Kanal"
    if username:
        title = f"Kanal {username}"

    entry: dict[str, Any] = {
        "key": "ch_default",
        "chat_id": MANDATORY_CHANNEL_ID,
        "username": username,
        "title": title,
        "invite_url": MANDATORY_CHANNEL_INVITE_URL
        or _invite_url_from_target(username.lstrip("@") if username else None),
        "active": True,
        "added_at": int(time.time()),
        "source": "mandatory_channel_env",
    }
    channels.append(entry)
    db["channels"] = channels
    save_task_channels_db(db)
    logger.info("Varsayilan kanal gorevi eklendi: %s", entry.get("invite_url") or entry.get("chat_id"))
    return 1


def user_lang(user_id: int) -> str:
    db = _load_users_db()
    u = _get_user(db, int(user_id))
    lang = (u.get("language") or "tr").strip().lower()
    return lang if lang in ("tr", "en", "ar") else "tr"


def user_task_rewards(user: dict[str, Any]) -> list[str]:
    raw = user.get("task_channel_rewards")
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for item in raw:
        piece = str(item or "").strip()
        if piece and piece not in out:
            out.append(piece)
    return out


def channel_reward_keys(channel: dict[str, Any]) -> list[str]:
    keys: list[str] = []
    chat_id = str(channel.get("chat_id") or "").strip()
    username = str(channel.get("username") or "").strip()
    key = str(channel.get("key") or "").strip()
    if chat_id:
        keys.append(chat_id)
    if username:
        un = username if username.startswith("@") else f"@{username.lstrip('@')}"
        if un not in keys:
            keys.append(un)
    if key and key not in keys:
        keys.append(key)
    return keys


def user_claimed_channel(user: dict[str, Any], channel: dict[str, Any]) -> bool:
    claimed = set(user_task_rewards(user))
    return any(k in claimed for k in channel_reward_keys(channel))


def mark_channel_reward(user: dict[str, Any], channel: dict[str, Any]) -> None:
    rewards = user_task_rewards(user)
    for key in channel_reward_keys(channel):
        if key not in rewards:
            rewards.append(key)
    user["task_channel_rewards"] = rewards


def _invite_link_key(url: str) -> str:
    raw = (url or "").strip()
    if not raw:
        return ""
    m = _TME_INVITE_RE.search(raw)
    if m:
        return m.group(1).lower()
    m2 = _TME_RE.search(raw)
    if m2:
        slug = (m2.group(1) or "").strip().lower()
        if slug and not slug.startswith("+"):
            return slug
    return raw.lower().rstrip("/")


def find_channel_for_join(chat_id: int | str, invite_url: str | None = None) -> dict[str, Any] | None:
    """Gizli/açık kanal: chat_id veya davet linki ile görev kanalını bul."""
    db = load_task_channels_db()
    channels = active_channels(db)
    cid = str(chat_id)

    found = find_channel(channels, cid)
    if found:
        if not str(found.get("chat_id") or "").strip():
            found["chat_id"] = cid
            save_task_channels_db(db)
        return found

    invite_key = _invite_link_key(invite_url or "")
    if invite_key:
        for ch in channels:
            stored = _invite_link_key(str(ch.get("invite_url") or ""))
            if stored and stored == invite_key:
                if not str(ch.get("chat_id") or "").strip():
                    ch["chat_id"] = cid
                    save_task_channels_db(db)
                return ch
    return None


def try_grant_channel_reward(user_id: int, channel: dict[str, Any]) -> tuple[bool, float]:
    """Ödül verilirse (True, yeni_toplam). Zaten alındıysa (False, mevcut_toplam)."""
    users_db = _load_users_db()
    u = _get_user(users_db, int(user_id))
    if user_claimed_channel(u, channel):
        return False, _diamonds_total_from_buckets(u)
    mark_channel_reward(u, channel)
    u["trial_diamonds"] = float(u.get("trial_diamonds", 0.0) or 0.0) + float(TASK_CHANNEL_REWARD)
    total = _diamonds_total_from_buckets(u)
    u["diamonds"] = total
    _save_users_db(users_db)
    return True, total


def user_task_join_requests(user: dict[str, Any]) -> list[str]:
    raw = user.get("task_join_requests")
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for item in raw:
        piece = str(item or "").strip()
        if piece and piece not in out:
            out.append(piece)
    return out


def _load_join_requests_cache() -> dict[str, Any]:
    _ensure_data_dir()
    if not TASK_JOIN_REQUESTS_PATH.is_file():
        return {"users": {}}
    try:
        raw = json.loads(TASK_JOIN_REQUESTS_PATH.read_text(encoding="utf-8")) or {}
    except Exception:
        raw = {}
    if not isinstance(raw, dict):
        raw = {}
    users = raw.get("users")
    if not isinstance(users, dict):
        users = {}
    return {"users": users}


def _save_join_requests_cache(cache: dict[str, Any]) -> None:
    _ensure_data_dir()
    TASK_JOIN_REQUESTS_PATH.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def record_task_join_request(user_id: int, channel: dict[str, Any]) -> None:
    key = str(channel.get("key") or "").strip()
    if not key:
        return
    users_db = _load_users_db()
    u = _get_user(users_db, int(user_id))
    keys = user_task_join_requests(u)
    if key not in keys:
        keys.append(key)
        u["task_join_requests"] = keys
        _save_users_db(users_db)

    cache = _load_join_requests_cache()
    users = cache.setdefault("users", {})
    uid = str(int(user_id))
    entry = users.setdefault(uid, {})
    if isinstance(entry, dict):
        entry[key] = int(time.time())
    _save_join_requests_cache(cache)


def user_has_cached_join_request(user_id: int, channel: dict[str, Any]) -> bool:
    key = str(channel.get("key") or "").strip()
    if not key:
        return False
    cache = _load_join_requests_cache()
    users = cache.get("users") or {}
    entry = users.get(str(int(user_id))) or {}
    return isinstance(entry, dict) and key in entry


def _bot_tokens(bot=None) -> list[str]:
    out: list[str] = []
    for piece in (
        getattr(bot, "token", None),
        TASK_BOT_TOKEN,
        MAIN_BOT_TOKEN,
    ):
        token = (piece or "").strip()
        if token and token not in out:
            out.append(token)
    return out


def _is_private_invite_channel(channel: dict[str, Any]) -> bool:
    return "+" in str(channel.get("invite_url") or "")


def _request_invite_key(req: dict[str, Any]) -> str:
    invite_obj = req.get("invite_link") or {}
    if isinstance(invite_obj, dict):
        raw = str(invite_obj.get("invite_link") or "")
        if raw:
            return _invite_link_key(raw)
    return ""


def _request_user_id(req: dict[str, Any]) -> int:
    from_user = req.get("from") or req.get("from_user") or {}
    try:
        return int(from_user.get("id") or 0)
    except (TypeError, ValueError):
        return 0


async def _fetch_join_requests(token: str, chat_id: str, user_id: int | None = None) -> list[dict[str, Any]]:
    payload: dict[str, Any] = {"chat_id": chat_id}
    if user_id is not None:
        payload["user_id"] = int(user_id)
    try:
        data = await _telegram_api_post(token, "getChatJoinRequests", payload)
    except Exception as exc:
        logger.debug("getChatJoinRequests failed chat=%s: %s", chat_id, exc)
        return []
    if not data.get("ok"):
        return []
    result = data.get("result") or {}
    requests = result.get("requests") or []
    return [r for r in requests if isinstance(r, dict)]


async def _find_pending_join_for_channel(
    bot,
    user_id: int,
    channel: dict[str, Any],
) -> bool:
    target_key = str(channel.get("key") or "").strip()
    target_invite = _invite_link_key(str(channel.get("invite_url") or ""))
    seen_chats: set[str] = set()

    db = load_task_channels_db()
    for ch in active_channels(db):
        cid = str(ch.get("chat_id") or "").strip()
        if not cid or cid in seen_chats:
            continue
        seen_chats.add(cid)

        for token in _bot_tokens(bot):
            requests = await _fetch_join_requests(token, cid, user_id)
            if not requests:
                requests = await _fetch_join_requests(token, cid)

            for req in requests:
                if _request_user_id(req) != int(user_id):
                    continue
                req_invite = _request_invite_key(req)
                ch_invite = _invite_link_key(str(ch.get("invite_url") or ""))
                same_channel = str(ch.get("key") or "") == target_key
                if not same_channel and target_invite:
                    if req_invite:
                        same_channel = req_invite == target_invite
                    elif ch_invite == target_invite:
                        same_channel = True
                if not same_channel:
                    continue
                if not str(channel.get("chat_id") or "").strip():
                    channel["chat_id"] = cid
                    _persist_channel_update(channel)
                record_task_join_request(user_id, channel)
                return True
    return False


def user_has_task_join_request(user: dict[str, Any], channel: dict[str, Any]) -> bool:
    key = str(channel.get("key") or "").strip()
    return bool(key) and key in user_task_join_requests(user)


def channel_reward_success_message(lang: str, total: float) -> str:
    reward = TASK_CHANNEL_REWARD
    if lang == "en":
        return (
            f"🎉 You earned {reward:g} 💎!\n\n"
            f"Total balance: {total:.1f} 💎"
            + main_bot_hint(lang)
        )
    return (
        f"🎉 {reward:g} elmas kazandınız!\n\n"
        f"Toplam bakiye: {total:.1f} 💎"
        + main_bot_hint(lang)
    )


async def _telegram_api_post(token: str, method: str, payload: dict[str, Any]) -> dict[str, Any]:
    import aiohttp

    url = f"https://api.telegram.org/bot{token}/{method}"
    timeout = aiohttp.ClientTimeout(total=12)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(url, json=payload) as resp:
            return await resp.json(content_type=None)


async def _send_bot_message(token: str, user_id: int, text: str) -> None:
    if not token:
        return
    try:
        data = await _telegram_api_post(
            token,
            "sendMessage",
            {"chat_id": int(user_id), "text": text, "parse_mode": "HTML"},
        )
        if not data.get("ok"):
            logger.warning("sendMessage failed uid=%s: %s", user_id, data)
    except Exception as exc:
        logger.warning("sendMessage error uid=%s: %s", user_id, exc)


async def send_via_main_bot(user_id: int, text: str) -> None:
    if not MAIN_BOT_TOKEN or MAIN_BOT_TOKEN == TASK_BOT_TOKEN:
        return
    await _send_bot_message(MAIN_BOT_TOKEN, user_id, text)


async def deliver_channel_reward_notification(
    user_id: int,
    total: float,
    *,
    via_bot=None,
    reply_to_message=None,
) -> str:
    lang = user_lang(user_id)
    text = channel_reward_success_message(lang, total)
    if via_bot and reply_to_message is not None:
        try:
            await reply_to_message.reply_text(text, parse_mode="HTML")
        except TelegramError as exc:
            logger.warning("Gorev botu odul mesaji gonderilemedi: %s", exc)
    elif via_bot:
        try:
            await via_bot.send_message(int(user_id), text, parse_mode="HTML")
        except TelegramError as exc:
            logger.warning("Gorev botu odul mesaji gonderilemedi: %s", exc)
    await send_via_main_bot(user_id, text)
    return text


async def _notify_reward(bot, user_id: int, channel: dict[str, Any], total: float, *, first_time: bool) -> None:
    if not first_time:
        return
    await deliver_channel_reward_notification(user_id, total, via_bot=bot)


async def chat_join_request_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Gizli kanal: kullanıcı İstek gönder'e basınca otomatik doğrula + elmas ver."""
    req = update.chat_join_request
    if not req or not req.from_user:
        return

    user_id = int(req.from_user.id)
    chat_id = req.chat.id
    invite_raw = ""
    if req.invite_link and getattr(req.invite_link, "invite_link", None):
        invite_raw = str(req.invite_link.invite_link or "")

    channel = find_channel_for_join(chat_id, invite_raw)
    if not channel:
        logger.debug("Join request ignored (not a task channel): chat_id=%s", chat_id)
        return

    record_task_join_request(user_id, channel)
    granted, total = try_grant_channel_reward(user_id, channel)
    if granted:
        await deliver_channel_reward_notification(user_id, total, via_bot=context.bot)

    if TASK_AUTO_APPROVE_JOIN:
        try:
            await req.approve()
        except TelegramError as exc:
            logger.warning(
                "Katilma istegi onaylanamadi chat=%s uid=%s: %s",
                chat_id,
                user_id,
                exc,
            )

    logger.info(
        "Join request task chat=%s uid=%s granted=%s total=%.1f",
        chat_id,
        user_id,
        granted,
        total,
    )


def find_channel(channels: list[dict[str, Any]], token: str) -> dict[str, Any] | None:
    needle = (token or "").strip().lower()
    if not needle:
        return None
    for ch in channels:
        if not isinstance(ch, dict):
            continue
        if str(ch.get("key") or "").lower() == needle:
            return ch
        if str(ch.get("chat_id") or "").lower() == needle:
            return ch
        un = str(ch.get("username") or "").lstrip("@").lower()
        if un and (needle == un or needle == f"@{un}"):
            return ch
    return None


def active_channels(db: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for ch in db.get("channels") or []:
        if isinstance(ch, dict) and ch.get("active", True):
            out.append(ch)
    return out


def main_bot_tasks_promo_caption(lang: str) -> str:
    if lang == "en":
        return (
            "💎 Take just a few minutes, complete tasks and collect your diamonds! 🚀\n"
            "📢 Join Telegram channels, earn rewards instantly. "
            "More tasks, more diamonds! ✨"
        )
    return (
        "💎 Sadece birkaç dakikanı ayır, görevleri tamamla ve elmaslarını topla! 🚀\n"
        "📢 Telegram kanallarına katıl, ödülleri anında kazan. "
        "Ne kadar çok görev, o kadar çok elmas! ✨"
    )


def tasks_intro(lang: str) -> str:
    if lang == "en":
        return (
            "🎯 To start earning diamonds, just join the Telegram channels below!\n\n"
            "✅ After joining all channels, return to the bot and claim your reward instantly.\n"
            "💎 The more tasks you complete, the more diamonds you earn!"
        )
    return (
        "🎯 Elmas kazanmaya başlamak için aşağıdaki Telegram kanallarına katılman yeterli!\n\n"
        "✅ Tüm kanallara katıldıktan sonra bota geri dön ve ödülünü anında al.\n"
        "💎 Ne kadar çok görev tamamlarsan, o kadar çok elmas kazanırsın!"
    )


def main_bot_hint(lang: str) -> str:
    if not MAIN_BOT_USERNAME:
        return ""
    if lang == "en":
        return f"\n\n💎 Use /my to check your balance."
    return f"\n\n💎 Bakiyeni görmek için /my yaz."


_CHANNEL_BUTTON_COLORS = ("🔴", "🟠", "🟡", "🟢", "🔵", "🟣", "🩵", "🩷")


def _channel_color_emoji(index: int) -> str:
    return _CHANNEL_BUTTON_COLORS[(max(1, index) - 1) % len(_CHANNEL_BUTTON_COLORS)]


def _reward_diamond_label(reward: float | None = None) -> str:
    r = float(reward if reward is not None else TASK_CHANNEL_REWARD)
    if r == int(r):
        return f"{int(r)} 💎"
    return f"{r:g} 💎"


def channel_list_label(
    channels: list[dict[str, Any]],
    lang: str,
    *,
    channel: dict[str, Any] | None = None,
    index: int | None = None,
) -> str:
    n = index
    if n is None and channel is not None:
        key = str(channel.get("key") or "")
        for i, ch in enumerate(channels, 1):
            if str(ch.get("key") or "") == key:
                n = i
                break
    if n is None:
        n = 1
    return f"#{n} · {_reward_diamond_label()}"


def channel_button_label(index: int, lang: str, *, claimed: bool = False) -> str:
    color = _channel_color_emoji(index)
    core = channel_list_label([], lang, index=index)
    if claimed:
        return f"✅ {core}"
    return f"{color} {core}"


def _persist_channel_update(channel: dict[str, Any]) -> None:
    key = str(channel.get("key") or "").strip()
    if not key:
        return
    db = load_task_channels_db()
    channels: list[dict[str, Any]] = list(db.get("channels") or [])
    for ch in channels:
        if str(ch.get("key") or "") == key:
            ch.update(
                {
                    "chat_id": channel.get("chat_id", ch.get("chat_id", "")),
                    "username": channel.get("username", ch.get("username", "")),
                    "title": channel.get("title", ch.get("title", "")),
                    "invite_url": channel.get("invite_url", ch.get("invite_url", "")),
                }
            )
            break
    db["channels"] = channels
    save_task_channels_db(db)


async def ensure_channel_resolved(bot, channel: dict[str, Any]) -> dict[str, Any]:
    if str(channel.get("chat_id") or "").strip():
        return channel
    invite = str(channel.get("invite_url") or "").strip()
    username = str(channel.get("username") or "").strip()
    target = username or invite
    if not target or ("+" in invite and not username):
        return channel
    try:
        chat_id, title, uname = await resolve_channel_target(bot, target)
    except ValueError:
        return channel
    channel["chat_id"] = chat_id
    if uname:
        channel["username"] = f"@{uname.lstrip('@')}"
    if title:
        channel["title"] = title
    _persist_channel_update(channel)
    return channel


def build_tasks_markup(channels: list[dict[str, Any]], user: dict[str, Any], lang: str) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    verify_label = "✨ Verify" if lang == "en" else "✨ Doğrula"
    for i, ch in enumerate(channels, 1):
        key = str(ch.get("key") or "")
        label = channel_button_label(i, lang, claimed=user_claimed_channel(user, ch))
        invite = str(ch.get("invite_url") or "").strip()
        claimed = user_claimed_channel(user, ch)
        row: list[InlineKeyboardButton] = []
        if claimed:
            row.append(
                InlineKeyboardButton(
                    label,
                    callback_data=f"task:done:{key}",
                )
            )
        else:
            if invite:
                row.append(
                    InlineKeyboardButton(
                        f"{label}  ›",
                        url=invite,
                    )
                )
            row.append(
                InlineKeyboardButton(
                    verify_label,
                    callback_data=f"task:verify:{key}",
                )
            )
        rows.append(row)
    rows.append(
        [
            InlineKeyboardButton(
                "🔄 Refresh" if lang == "en" else "🔄 Yenile",
                callback_data="task:refresh",
            )
        ]
    )
    return InlineKeyboardMarkup(rows)


def gorev_image_path() -> Path | None:
    """Proje kökündeki görev.png / gorev.png."""
    for base in (PROJECT_DIR, PROJECT_DIR / "assets"):
        if not base.is_dir():
            continue
        for name in ("görev.png", "gorev.png", "Görev.png", "GOREV.png"):
            candidate = base / name
            if candidate.is_file():
                return candidate
        for p in base.glob("*.png"):
            stem = p.stem.lower().replace("ö", "o").replace("ü", "u")
            if stem in ("gorev", "görev"):
                return p
    return None


async def resolve_task_bot_username() -> str:
    global _cached_task_bot_username
    if TASK_BOT_USERNAME:
        return TASK_BOT_USERNAME
    if _cached_task_bot_username:
        return _cached_task_bot_username
    token = (os.getenv("TASK_BOT_TOKEN") or "").strip()
    if not token:
        return ""
    try:
        import aiohttp

        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(f"https://api.telegram.org/bot{token}/getMe") as resp:
                data = await resp.json(content_type=None)
                if data.get("ok"):
                    un = (data.get("result") or {}).get("username") or ""
                    _cached_task_bot_username = str(un).strip().lstrip("@")
                    return _cached_task_bot_username
    except Exception as exc:
        logger.warning("Gorev botu username alinamadi: %s", exc)
    return ""


def build_main_bot_tasks_promo_markup(task_bot_username: str) -> InlineKeyboardMarkup | None:
    un = (task_bot_username or "").strip().lstrip("@")
    if not un:
        return None
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("🎯 Görev Botuna Git", url=f"https://t.me/{un}?start=tasks")]]
    )


def build_task_bot_notice_markup(task_bot_username: str) -> InlineKeyboardMarkup | None:
    un = (task_bot_username or "").strip().lstrip("@")
    if not un:
        return None
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("🎯 Görevlere Git", url=f"https://t.me/{un}?start=tasks")]]
    )


async def send_tasks_promo_to_chat(bot, chat_id: int, lang: str) -> bool:
    """Ana bot: görev görseli + metin + görev botu butonu (broadcast için)."""
    caption = main_bot_tasks_promo_caption(lang)
    task_un = await resolve_task_bot_username()
    markup = build_main_bot_tasks_promo_markup(task_un)
    if not markup:
        return False
    img_path = gorev_image_path()
    try:
        if img_path:
            with img_path.open("rb") as photo_file:
                await bot.send_photo(
                    chat_id=chat_id,
                    photo=InputFile(photo_file, filename=img_path.name),
                    caption=caption,
                    reply_markup=markup,
                )
        else:
            await bot.send_message(chat_id, caption, reply_markup=markup)
        return True
    except TelegramError as exc:
        logger.warning("Gorev promosu gonderilemedi chat=%s: %s", chat_id, exc)
        try:
            await bot.send_message(chat_id, caption, reply_markup=markup)
            return True
        except TelegramError:
            return False


async def broadcast_tasks_promo(bot) -> None:
    """Tüm kullanıcılara periyodik görev promosu gönder."""
    task_un = await resolve_task_bot_username()
    if not task_un and not TASK_BOT_TOKEN:
        return
    db = _load_users_db()
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
        try:
            await send_tasks_promo_to_chat(bot, chat_id, lang)
        except Exception as exc:
            logger.warning("Gorev promosu yayini basarisiz chat=%s: %s", chat_id, exc)
        await asyncio.sleep(0.05)


def new_channel_notice_message(lang: str, channel_index: int) -> str:
    reward = TASK_CHANNEL_REWARD
    if lang == "en":
        return (
            f"📢 <b>New task channel!</b>\n\n"
            f"Channel #{channel_index} is live — complete it and earn <b>{reward:g} 💎</b>.\n"
            "Tap the button below to view tasks."
        )
    return (
        f"📢 <b>Yeni görev kanalı eklendi!</b>\n\n"
        f"Kanal #{channel_index} hazır — görevi tamamla, <b>{reward:g} 💎</b> kazan.\n"
        "Görevleri görmek için aşağıdaki butona bas."
    )


async def send_new_channel_notice_to_chat(bot, chat_id: int, lang: str, channel_index: int) -> bool:
    caption = new_channel_notice_message(lang, channel_index)
    task_un = await resolve_task_bot_username()
    markup = build_task_bot_notice_markup(task_un)
    if not markup:
        try:
            await bot.send_message(chat_id, caption, parse_mode="HTML")
            return True
        except TelegramError:
            return False
    img_path = gorev_image_path()
    try:
        if img_path:
            with img_path.open("rb") as photo_file:
                await bot.send_photo(
                    chat_id=chat_id,
                    photo=InputFile(photo_file, filename=img_path.name),
                    caption=caption,
                    reply_markup=markup,
                    parse_mode="HTML",
                )
        else:
            await bot.send_message(chat_id, caption, reply_markup=markup, parse_mode="HTML")
        return True
    except TelegramError as exc:
        logger.warning("Yeni kanal bildirimi gonderilemedi chat=%s: %s", chat_id, exc)
        try:
            await bot.send_message(chat_id, caption, reply_markup=markup, parse_mode="HTML")
            return True
        except TelegramError:
            return False


async def notify_all_users_new_channel(channel: dict[str, Any]) -> None:
    """Yeni kanal eklendiğinde tüm kullanıcılara görev botu üzerinden bildirim gönder."""
    token = TASK_BOT_TOKEN
    if not token:
        logger.warning("Yeni kanal bildirimi: TASK_BOT_TOKEN yok")
        return

    db_channels = load_task_channels_db()
    channels = active_channels(db_channels)
    channel_index = 1
    key = str(channel.get("key") or "")
    for i, ch in enumerate(channels, 1):
        if str(ch.get("key") or "") == key:
            channel_index = i
            break

    from telegram import Bot

    db = _load_users_db()
    sent = 0
    async with Bot(token=token) as bot:
        for user_key, value in db.items():
            if user_key == _USERS_META_KEY or not isinstance(value, dict):
                continue
            if not str(user_key).isdigit():
                continue
            chat_id = int(user_key)
            user = _get_user(db, chat_id)
            lang = str(user.get("language", "tr") or "tr").lower()
            if lang not in SUPPORTED_LANGUAGES:
                lang = "tr"
            try:
                if await send_new_channel_notice_to_chat(bot, chat_id, lang, channel_index):
                    sent += 1
            except Exception as exc:
                logger.warning("Yeni kanal bildirimi basarisiz chat=%s: %s", chat_id, exc)
            await asyncio.sleep(0.05)
    logger.info("Yeni kanal bildirimi: %s kullaniciya gonderildi (kanal #%s)", sent, channel_index)


def schedule_new_channel_notification(channel: dict[str, Any]) -> None:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(notify_all_users_new_channel(channel))
        return
    loop.create_task(notify_all_users_new_channel(channel))


async def send_main_bot_tasks_promo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ana bot: gorsel + kisa mesaj + gorev botuna tek buton (kanal listesi yok)."""
    query = update.callback_query
    if query:
        await query.answer()

    chat_id = None
    reply = None
    if query and query.message:
        chat_id = query.message.chat_id
    elif update.effective_message:
        reply = update.effective_message
        chat_id = reply.chat_id

    if chat_id is None:
        return

    lang = user_lang(update.effective_user.id) if update.effective_user else "tr"
    task_un = await resolve_task_bot_username()
    if not build_main_bot_tasks_promo_markup(task_un):
        fallback = "Görev botu ayarlı değil. .env içine TASK_BOT_USERNAME=@... ekleyin."
        if reply:
            await reply.reply_text(fallback)
        else:
            await context.bot.send_message(chat_id, fallback)
        return

    if reply:
        caption = main_bot_tasks_promo_caption(lang)
        markup = build_main_bot_tasks_promo_markup(task_un)
        img_path = gorev_image_path()
        try:
            if img_path:
                with img_path.open("rb") as photo_file:
                    await reply.reply_photo(
                        photo=InputFile(photo_file, filename=img_path.name),
                        caption=caption,
                        reply_markup=markup,
                    )
            else:
                await reply.reply_text(caption, reply_markup=markup)
        except TelegramError as exc:
            logger.warning("Gorev promosu gonderilemedi: %s", exc)
            await reply.reply_text(caption, reply_markup=markup)
    else:
        await send_tasks_promo_to_chat(context.bot, chat_id, lang)


async def send_tasks(update: Update, *, edit: bool = False) -> None:
    ensure_default_task_channels()
    user = update.effective_user
    if not user:
        return
    lang = user_lang(user.id)
    db_channels = load_task_channels_db()
    channels = active_channels(db_channels)
    users_db = _load_users_db()
    u = _get_user(users_db, int(user.id))

    if not channels:
        text = (
            "No channel tasks yet. Check back later."
            if lang == "en"
            else "Henüz kanal görevi yok. Daha sonra tekrar bak."
        )
        markup = None
    else:
        text = tasks_intro(lang)
        markup = build_tasks_markup(channels, u, lang)

    target = update.callback_query.message if edit and update.callback_query else update.effective_message
    if not target:
        return
    if edit:
        await target.edit_text(text, reply_markup=markup, disable_web_page_preview=True)
    else:
        await target.reply_text(text, reply_markup=markup, disable_web_page_preview=True)


async def resolve_channel_target(bot, raw: str) -> tuple[str, str, str | None]:
    piece = (raw or "").strip()
    if not piece:
        raise ValueError("Kanal bilgisi bos.")

    candidates: list[str] = []
    if piece.startswith("@"):
        candidates.append(piece)
    elif re.fullmatch(r"-?\d+", piece):
        candidates.append(piece)
    else:
        un = _extract_tme_username(piece)
        if un:
            candidates.append(un)
        elif piece.startswith("http"):
            raise ValueError("Ozel davet linki (+) icin kanal ID (-100...) kullanin.")
        else:
            candidates.append(f"@{piece.lstrip('@')}")

    last_exc: Exception | None = None
    for target in candidates:
        try:
            chat = await bot.get_chat(chat_id=target)
        except TelegramError as exc:
            last_exc = exc
            continue
        chat_id = str(chat.id)
        title = (chat.title or chat.username or chat_id).strip()
        username = (chat.username or "").strip() or None
        return chat_id, title, username

    if last_exc:
        raise ValueError(f"Kanal bulunamadi: {last_exc}")
    raise ValueError("Kanal cozulemedi.")


def _admin_command_args(context: ContextTypes.DEFAULT_TYPE) -> list[str]:
    """Eski sürümdeki HOTTOKKANALADD vb. kod argümanını yoksay."""
    args = list(context.args or [])
    legacy_codes = {"hottokkanaladd", "hottokkanaldel"}
    for key in ("TASK_ADMIN_ADD_CODE", "TASK_ADMIN_REMOVE_CODE", "TASK_ADMIN_LIST_CODE"):
        val = (os.getenv(key) or "").strip().lower()
        if val:
            legacy_codes.add(val)
    if args and args[0].strip().lower() in legacy_codes:
        return args[1:]
    return args


async def _ensure_admin(update: Update, *, bootstrap: bool = False) -> bool:
    user = update.effective_user
    msg = update.effective_message
    if not user or not msg:
        return False
    if _is_admin_user(user.id, user.username):
        return True
    if bootstrap and not _has_configured_admin_user_ids():
        register_runtime_admin(int(user.id))
        return True
    lang = user_lang(user.id)
    text = "⛔ Admin only." if lang == "en" else "⛔ Bu komut sadece admin içindir."
    await msg.reply_text(text)
    return False


async def admin_help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user:
        return
    lang = user_lang(user.id)
    if not _is_admin_user(user.id, user.username):
        await _ensure_admin(update)
        return
    from bot import _admin_ids_debug_text

    if lang == "en":
        body = (
            "<b>Admin commands</b>\n\n"
            "<code>/addchannel @channel</code>\n"
            "<code>/addchannel https://t.me/+invite Title</code>\n"
            "<code>/removechannel</code> — numaralı listeden sil\n"
            "<code>/removechannel 2</code>\n"
            "<code>/listchannels</code>\n\n"
            f"{html.escape(_admin_ids_debug_text())}"
        )
    else:
        body = (
            "<b>Admin komutları</b>\n\n"
            "<code>/addchannel @kanal</code>\n"
            "<code>/addchannel https://t.me/+davet Baslik</code>\n"
            "<code>/removechannel</code> — numaralı listeden sil\n"
            "<code>/removechannel 2</code>\n"
            "<code>/listchannels</code>\n\n"
            f"{html.escape(_admin_ids_debug_text())}"
        )
    await update.effective_message.reply_text(body, parse_mode="HTML")


async def add_channel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _ensure_admin(update, bootstrap=True):
        return
    args = _admin_command_args(context)
    if not args:
        context.user_data.pop(PENDING_REMOVE_CHANNEL_KEY, None)
        context.user_data[PENDING_ADD_CHANNEL_KEY] = True
        await update.effective_message.reply_text(
            "📢 Kanal linkini gönder:\n\n"
            "• <code>@kanal</code>\n"
            "• <code>https://t.me/kanal</code>\n"
            "• <code>https://t.me/+davet</code> (gizli kanal)",
            parse_mode="HTML",
        )
        return
    await execute_add_channel(update, context, [normalize_channel_input(a) for a in args])


async def pending_add_channel_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await admin_pending_message(update, context)


async def pending_remove_channel_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await admin_pending_message(update, context)


async def admin_pending_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    msg = update.effective_message
    if not user or not msg or not msg.text:
        return
    if not _is_admin_user(user.id, user.username):
        context.user_data.pop(PENDING_ADD_CHANNEL_KEY, None)
        context.user_data.pop(PENDING_REMOVE_CHANNEL_KEY, None)
        return

    text = msg.text.strip()
    if text.startswith("/"):
        context.user_data.pop(PENDING_ADD_CHANNEL_KEY, None)
        context.user_data.pop(PENDING_REMOVE_CHANNEL_KEY, None)
        return

    if context.user_data.get(PENDING_ADD_CHANNEL_KEY):
        if not _looks_like_channel_input(text):
            await msg.reply_text(
                "❌ Geçersiz format.\n\n"
                "Örnek:\n"
                "• <code>@kanal</code>\n"
                "• <code>https://t.me/kanal</code>\n"
                "• <code>https://t.me/+davet</code>",
                parse_mode="HTML",
            )
            return
        context.user_data.pop(PENDING_ADD_CHANNEL_KEY, None)
        context.user_data.pop(PENDING_REMOVE_CHANNEL_KEY, None)
        normalized = normalize_channel_input(text)
        await execute_add_channel(update, context, [normalized])
        raise ApplicationHandlerStop

    if context.user_data.get(PENDING_REMOVE_CHANNEL_KEY):
        if not text.isdigit():
            await msg.reply_text(
                "❌ Silmek için listedeki numarayı yaz (<code>1</code>, <code>2</code> …).",
                parse_mode="HTML",
            )
            return
        context.user_data.pop(PENDING_REMOVE_CHANNEL_KEY, None)
        await execute_remove_channel_at_index(update, int(text))
        raise ApplicationHandlerStop


async def execute_add_channel(
    update: Update, context: ContextTypes.DEFAULT_TYPE, args: list[str]
) -> None:
    msg = update.effective_message
    if not msg or not args:
        return

    target_raw = normalize_channel_input(args[0].strip())
    invite_url = ""
    title_override = ""
    for extra in args[1:]:
        piece = normalize_channel_input(extra.strip())
        if piece.startswith("http") and not invite_url:
            invite_url = piece
        elif not title_override:
            title_override = extra.strip()

    # Gizli davet linki (+): chat_id olmadan eklenebilir; join request ile dolar.
    if _is_private_invite_arg(target_raw):
        invite_url = _private_invite_url(target_raw)
        title = title_override or "Gizli Kanal"
        db = load_task_channels_db()
        channels: list[dict[str, Any]] = list(db.get("channels") or [])
        invite_key = _invite_link_key(invite_url)
        for ch in channels:
            if _invite_link_key(str(ch.get("invite_url") or "")) == invite_key:
                ch["invite_url"] = invite_url
                ch["title"] = title
                ch["active"] = True
                save_task_channels_db(db)
                await msg.reply_text(
                    f"✅ Kanal güncellendi: <b>{html.escape(title)}</b>",
                    parse_mode="HTML",
                )
                return
        entry = {
            "key": f"ch_{uuid.uuid4().hex[:10]}",
            "chat_id": "",
            "username": "",
            "title": title,
            "invite_url": invite_url,
            "active": True,
            "added_at": int(time.time()),
        }
        channels.append(entry)
        db["channels"] = channels
        save_task_channels_db(db)
        await msg.reply_text(
            f"✅ Gizli kanal eklendi: <b>{html.escape(title)}</b>\n"
            f"Key: <code>{html.escape(entry['key'])}</code>\n\n"
            "⚠️ Botu kanala yönetici yapın (katılma isteklerini görmek için).\n"
            "📣 Tüm kullanıcılara bildirim gönderiliyor…",
            parse_mode="HTML",
        )
        schedule_new_channel_notification(entry)
        return

    try:
        chat_id, title, username = await resolve_channel_target(context.bot, target_raw)
    except ValueError as exc:
        await msg.reply_text(f"❌ {exc}")
        return

    if not invite_url:
        invite_url = _invite_url_from_target(f"@{username}" if username else None)
    if title_override:
        title = title_override
    if target_raw.startswith("http") and "+" in target_raw and not invite_url:
        invite_url = target_raw.strip()

    db = load_task_channels_db()
    channels: list[dict[str, Any]] = list(db.get("channels") or [])
    existing = find_channel(channels, chat_id) or (
        find_channel(channels, f"@{username}") if username else None
    )
    if existing:
        existing["chat_id"] = chat_id
        existing["title"] = title
        existing["username"] = f"@{username}" if username else existing.get("username", "")
        if invite_url:
            existing["invite_url"] = invite_url
        existing["active"] = True
        save_task_channels_db(db)
        await msg.reply_text(
            f"✅ Kanal güncellendi: <b>{html.escape(title)}</b>\n"
            f"ID: <code>{html.escape(chat_id)}</code>",
            parse_mode="HTML",
        )
        return

    entry = {
        "key": f"ch_{uuid.uuid4().hex[:10]}",
        "chat_id": chat_id,
        "username": f"@{username}" if username else "",
        "title": title,
        "invite_url": invite_url,
        "active": True,
        "added_at": int(time.time()),
    }
    channels.append(entry)
    db["channels"] = channels
    save_task_channels_db(db)
    await msg.reply_text(
        f"✅ Kanal eklendi: <b>{html.escape(title)}</b>\n"
        f"Key: <code>{html.escape(entry['key'])}</code>\n"
        f"Chat: <code>{html.escape(chat_id)}</code>\n\n"
        "⚠️ Botu kanala <b>yönetici</b> yapın (üyelik kontrolü için).\n"
        "📣 Tüm kullanıcılara bildirim gönderiliyor…",
        parse_mode="HTML",
    )
    schedule_new_channel_notification(entry)


def format_remove_channel_pick_list(channels: list[dict[str, Any]]) -> str:
    lines = ["<b>🗑 Silinecek kanalı seç</b>\n"]
    for i, ch in enumerate(channels, 1):
        label = channel_list_label(channels, "tr", index=i)
        color = _channel_color_emoji(i)
        title = html.escape(str(ch.get("title") or "Kanal"))
        lines.append(f"{i}. {color} <b>{html.escape(label)}</b> — {title}")
    lines.append(
        "\nSilmek istediğin numarayı yaz (<code>1</code>, <code>2</code> …)\n"
        "veya <code>/removechannel 3</code>"
    )
    return "\n".join(lines)


async def execute_remove_channel_at_index(update: Update, index: int) -> bool:
    msg = update.effective_message
    if not msg:
        return False
    db = load_task_channels_db()
    channels = active_channels(db)
    if index < 1 or index > len(channels):
        await msg.reply_text(
            f"❌ Geçersiz numara. 1–{len(channels)} arası bir sayı yaz."
            if channels
            else "❌ Liste boş."
        )
        return False
    target = channels[index - 1]
    found_key = str(target.get("key") or "")
    title = str(target.get("title") or "Kanal")
    all_channels: list[dict[str, Any]] = list(db.get("channels") or [])
    db["channels"] = [c for c in all_channels if str(c.get("key") or "") != found_key]
    save_task_channels_db(db)
    await msg.reply_text(
        f"🗑 Kanal silindi: <b>{html.escape(title)}</b> (#{index})",
        parse_mode="HTML",
    )
    return True


async def execute_remove_channel_by_token(update: Update, token: str) -> bool:
    msg = update.effective_message
    if not msg:
        return False
    db = load_task_channels_db()
    channels: list[dict[str, Any]] = list(db.get("channels") or [])
    found = find_channel(channels, token)
    if not found and not token.startswith("@") and not token.startswith("-") and not token.startswith("ch_"):
        found = find_channel(channels, f"@{token.lstrip('@')}")
    if not found:
        await msg.reply_text("❌ Kanal listede yok.")
        return False
    title = str(found.get("title") or "Channel")
    found_key = str(found.get("key") or "")
    db["channels"] = [c for c in channels if str(c.get("key") or "") != found_key]
    save_task_channels_db(db)
    await msg.reply_text(
        f"🗑 Kanal silindi: <b>{html.escape(title)}</b>",
        parse_mode="HTML",
    )
    return True


async def remove_channel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _ensure_admin(update):
        return
    args = _admin_command_args(context)
    db = load_task_channels_db()
    channels = active_channels(db)

    if not args:
        if not channels:
            await update.effective_message.reply_text("Liste boş.")
            return
        context.user_data.pop(PENDING_ADD_CHANNEL_KEY, None)
        context.user_data[PENDING_REMOVE_CHANNEL_KEY] = True
        await update.effective_message.reply_text(
            format_remove_channel_pick_list(channels),
            parse_mode="HTML",
        )
        return

    token = unquote(args[0]).strip()
    context.user_data.pop(PENDING_REMOVE_CHANNEL_KEY, None)
    if token.isdigit():
        await execute_remove_channel_at_index(update, int(token))
        return
    await execute_remove_channel_by_token(update, token)


async def list_channels_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _ensure_admin(update):
        return

    db = load_task_channels_db()
    channels = active_channels(db)
    if not channels:
        await update.effective_message.reply_text("Liste boş.")
        return

    lines = ["<b>Kanal görevleri</b>\n"]
    for i, ch in enumerate(channels, 1):
        label = channel_list_label(channels, "tr", index=i)
        color = _channel_color_emoji(i)
        lines.append(
            f"{i}. {color} <b>{html.escape(label)}</b>\n"
            f"   key: <code>{html.escape(str(ch.get('key') or ''))}</code>\n"
            f"   chat: <code>{html.escape(str(ch.get('chat_id') or ''))}</code>"
        )
    await update.effective_message.reply_text("\n".join(lines), parse_mode="HTML")


async def user_is_channel_member(bot, channel: dict[str, Any], user_id: int) -> tuple[bool, str]:
    targets: list[str] = []
    chat_id = str(channel.get("chat_id") or "").strip()
    username = str(channel.get("username") or "").strip()
    if chat_id:
        targets.append(chat_id)
    if username:
        targets.append(username if username.startswith("@") else f"@{username.lstrip('@')}")

    if not targets:
        invite = str(channel.get("invite_url") or "")
        if "+" in invite:
            return False, "private_pending"
        return False, "Kanal yapılandırması hatalı."

    last_err = ""
    for target in targets:
        try:
            member = await bot.get_chat_member(chat_id=target, user_id=user_id)
        except TelegramError as exc:
            last_err = str(exc)
            logger.warning("task verify getChatMember failed %s uid=%s: %s", target, user_id, exc)
            continue
        status = member.status
        if status in (
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER,
            ChatMemberStatus.RESTRICTED,
        ):
            return True, ""
    if last_err:
        return False, "Bot kanalda yönetici değil veya kanal bulunamadı."
    return False, "not_member"


async def _api_has_pending_join_request(bot, channel: dict[str, Any], user_id: int) -> bool:
    chat_id = str(channel.get("chat_id") or "").strip()
    if chat_id:
        for token in _bot_tokens(bot):
            requests = await _fetch_join_requests(token, chat_id, user_id)
            for req in requests:
                if _request_user_id(req) == int(user_id):
                    return True
    return await _find_pending_join_for_channel(bot, user_id, channel)


async def user_can_claim_channel(
    bot,
    channel: dict[str, Any],
    user_id: int,
    user: dict[str, Any],
) -> tuple[bool, str]:
    ok, reason = await user_is_channel_member(bot, channel, user_id)
    if ok:
        return True, ""

    if await _api_has_pending_join_request(bot, channel, user_id):
        return True, ""

    return False, reason


async def task_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.from_user or not query.data:
        return

    user = query.from_user
    lang = user_lang(user.id)
    data = query.data

    if data == "task:refresh":
        await query.answer()
        await send_tasks(update, edit=True)
        return

    if not data.startswith("task:"):
        await query.answer()
        return

    parts = data.split(":", 2)
    if len(parts) != 3:
        await query.answer()
        return
    action, channel_key = parts[1], parts[2]

    if action == "done":
        msg = "Already claimed." if lang == "en" else "Bu kanal için ödül zaten alındı."
        await query.answer(msg, show_alert=True)
        return

    db_ch = load_task_channels_db()
    channel = find_channel(active_channels(db_ch), channel_key)
    if not channel:
        msg = "Channel not found." if lang == "en" else "Kanal bulunamadı."
        await query.answer(msg, show_alert=True)
        return

    users_db = _load_users_db()
    u = _get_user(users_db, int(user.id))

    if action == "info":
        channels = active_channels(db_ch)
        title = html.escape(channel_list_label(channels, lang, channel=channel))
        claimed = user_claimed_channel(u, channel)
        status = "✅ Ödül alındı" if claimed else ("⏳ Not claimed yet" if lang == "en" else "⏳ Henüz alınmadı")
        await query.answer()
        await query.message.reply_text(f"<b>{title}</b>\n{status}", parse_mode="HTML")
        return

    if action != "verify":
        await query.answer()
        return

    if user_claimed_channel(u, channel):
        msg = "Already claimed." if lang == "en" else "Bu kanal ödülünü zaten aldın."
        await query.answer(msg, show_alert=True)
        await send_tasks(update, edit=True)
        return

    channel = await ensure_channel_resolved(context.bot, channel)
    can_claim, reason = await user_can_claim_channel(context.bot, channel, int(user.id), u)
    if not can_claim:
        if reason in ("not_member", "private_pending"):
            msg = (
                "Join the channel or send a join request first, then tap Verify again."
                if lang == "en"
                else "Önce kanala katıl veya istek gönder, sonra Doğrula'ya tekrar bas."
            )
        else:
            msg = reason if lang == "tr" else "Could not verify. Is the bot admin in the channel?"
        await query.answer(msg, show_alert=True)
        return

    granted, total = try_grant_channel_reward(int(user.id), channel)
    if not granted:
        msg = "Already claimed." if lang == "en" else "Bu kanal ödülünü zaten aldın."
        await query.answer(msg, show_alert=True)
        await send_tasks(update, edit=True)
        return

    await query.answer("OK" if lang == "en" else "Tamam")
    await deliver_channel_reward_notification(
        int(user.id),
        total,
        via_bot=context.bot,
        reply_to_message=query.message,
    )
    await send_tasks(update, edit=True)


async def tasks_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await send_tasks(update, edit=False)
