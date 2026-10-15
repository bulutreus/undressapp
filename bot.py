from importlib.machinery import SourcelessFileLoader
from pathlib import Path
import sys

_cache_dir = Path(__file__).resolve().parent / "__pycache__"
_cache_name = f"bot.cpython-{sys.version_info.major}{sys.version_info.minor}.pyc"
_cache_path = _cache_dir / _cache_name
if not _cache_path.is_file():
    raise RuntimeError(f"Required compiled bot module is missing: {_cache_path}")
_loader = SourcelessFileLoader("bot", str(_cache_path))
_run_as_script = __name__ == "__main__"
if _run_as_script:
    __name__ = "bot"
exec(_loader.get_code("bot"), globals())
if _run_as_script:
    __name__ = "__main__"

AD_BROADCAST_INTERVAL_SECONDS = 0
TASKS_PROMO_BROADCAST_INTERVAL_SECONDS = 0


def build_main_inline_markup(lang=DEFAULT_LANGUAGE):
    rows = []
    site_url = get_miniapp_url()
    if site_url:
        label = "Open Website" if lang == "en" else "Web sitesini ac"
        rows.append([InlineKeyboardButton(text=label, web_app=WebAppInfo(url=site_url))])
    buy_label = "Buy with Telegram Stars" if lang == "en" else "Telegram Stars ile satin al"
    rows.append([InlineKeyboardButton(text=buy_label, callback_data="menu:vip")])
    return InlineKeyboardMarkup(rows)


async def send_main_menu(message, settings, *, chat_user=None):
    lang = _user_language(_load_users_db(), int(chat_user.id)) if chat_user else DEFAULT_LANGUAGE
    text = (
        "Use our website for the service. Payments are handled only in this Telegram bot."
        if lang == "en"
        else "Hizmeti web sitemizden kullanin. Odemeler yalnizca Telegram botundan alinir."
    )
    await message.reply_text(text, reply_markup=build_main_inline_markup(lang))


def _photo_tips_intro_text(lang=DEFAULT_LANGUAGE):
    return (
        "Use our website for the service. Payments are handled only in this Telegram bot."
        if lang == "en"
        else "Hizmeti web sitemizden kullanin. Odemeler yalnizca Telegram botundan alinir."
    )


def build_photo_tips_markup(lang=DEFAULT_LANGUAGE):
    return build_main_inline_markup(lang)


async def ad_command(update, context):
    return


async def handle_photo(update, context):
    message = update.effective_message
    if not message:
        return
    lang = _lang_from_update(update)
    await message.reply_text(
        _photo_tips_intro_text(lang),
        reply_markup=build_main_inline_markup(lang),
        disable_web_page_preview=True,
    )


_legacy_post_init = post_init


async def post_init(app):
    await _legacy_post_init(app)
    await app.bot.set_my_commands(
        [
            BotCommand("start", "Open website / Siteyi ac"),
            BotCommand("buy", "Buy with Telegram Stars / Satin al"),
            BotCommand("my", "Check balance / Bakiyem"),
            BotCommand("lang", "Language / Dil"),
        ]
    )
    site_url = get_miniapp_url()
    if site_url:
        await app.bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(text="Website", web_app=WebAppInfo(url=site_url))
        )
    else:
        await app.bot.set_chat_menu_button(menu_button=MenuButtonDefault())


async def _website_only_command(update, context):
    message = update.effective_message
    if not message:
        return
    lang = _lang_from_update(update)
    await message.reply_text(
        _photo_tips_intro_text(lang),
        reply_markup=build_main_inline_markup(lang),
        disable_web_page_preview=True,
    )


invite_command = _website_only_command
daily_command = _website_only_command
size_command = _website_only_command
help_command = _website_only_command
prompt_mode_command = _website_only_command

try:
    import task_channels as _task_channels

    _task_channels.send_main_bot_tasks_promo = _website_only_command
except ImportError:
    pass


if __name__ == "__main__":
    main()
