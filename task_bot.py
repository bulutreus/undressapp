"""
Telegram görev botu (ayrı token). Ana bot ile aynı task_channels.py modülünü kullanır.
Çalıştırma: python task_bot.py  veya start-all.bat
"""
from __future__ import annotations

import html
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, ChatJoinRequestHandler, CommandHandler, MessageHandler, filters
from telegram.ext._application import ApplicationHandlerStop

from task_channels import (
    TASK_CHANNEL_REWARD,
    add_channel_command,
    admin_help_command,
    admin_pending_message,
    chat_join_request_handler,
    ensure_default_task_channels,
    list_channels_command,
    remove_channel_command,
    send_tasks,
    task_callback,
    tasks_command,
)

load_dotenv(Path(__file__).resolve().parent / ".env", override=True)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

TASK_BOT_TOKEN = (os.getenv("TASK_BOT_TOKEN") or "").strip()


async def start_command(update: Update, context) -> None:
    await send_tasks(update, edit=False)


async def help_command(update: Update, context) -> None:
    from bot import _is_admin_user

    user = update.effective_user
    if user and _is_admin_user(user.id, user.username):
        text = (
            "<b>Admin</b>\n"
            "<code>/addchannel @kanal https://t.me/kanal</code>\n"
            "<code>/removechannel</code> — numaralı listeden sil\n"
            "<code>/listchannels</code>"
        )
    else:
        text = "Kanal görevleri için /tasks yaz — 💎 kazan."
    await update.effective_message.reply_text(text, parse_mode="HTML")


def build_application() -> Application:
    if not TASK_BOT_TOKEN:
        raise ValueError("TASK_BOT_TOKEN yok. .env dosyasına TASK_BOT_TOKEN=... ekleyin.")

    ensure_default_task_channels()
    app = Application.builder().token(TASK_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("tasks", tasks_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("admin", admin_help_command))
    app.add_handler(CommandHandler("addchannel", add_channel_command))
    app.add_handler(CommandHandler("addchannels", add_channel_command))
    app.add_handler(CommandHandler("removechannel", remove_channel_command))
    app.add_handler(CommandHandler("listchannels", list_channels_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, admin_pending_message, block=False))
    app.add_handler(CallbackQueryHandler(task_callback, pattern=r"^task:"))
    app.add_handler(ChatJoinRequestHandler(chat_join_request_handler))
    return app


def main() -> None:
    application = build_application()
    logger.info("Görev botu başlıyor. Ödül=%s 💎", TASK_CHANNEL_REWARD)
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
