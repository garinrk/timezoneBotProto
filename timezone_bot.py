"""
TimeZoneBot — Telegram bot for tracking team member timezones.

Shows each registered member's current local time on demand. Designed for
distributed teams who want a quick way to check "what time is it for everyone?"

Commands:
  /timeiswhat        — Show current time for all registered users
  /whosawake         — Show who is likely awake (7am–11pm local)
  /settz <tz>        — Register your own timezone (e.g. America/Chicago)
  /settz @user <tz>  — Admin: set timezone for another user
  /removeuser @user  — Admin: remove a user from the list
  /tzlist            — Show common timezone examples
  /help              — Show command help

Configuration:
  BOT_TOKEN   — Required. Set as an environment variable (see README).
  ADMIN_IDS   — Optional. Set of Telegram user IDs with admin privileges.
                If empty, all users can use admin commands.
  DATA_FILE   — Path to the JSON file used for persistence (default: timezone_data.json).

Setup:
  1. pip install -r requirements.txt
  2. Create a bot via @BotFather and copy your token
  3. export BOT_TOKEN="your_token_here"
  4. python timezone_bot.py
"""

import os
import json
import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo, available_timezones

from telegram import Update, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

# ── Config ────────────────────────────────────────────────────────────────────

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
DATA_FILE = Path("timezone_data.json")
ADMIN_IDS: set[int] = set()  # Fill with your Telegram user ID(s) for admin commands
                               # You can find yours by messaging @userinfobot

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ── Persistence (simple JSON) ────────────────────────────────────────────────

def load_data() -> dict:
    """Load user timezone data from the JSON file. Returns empty dict if file doesn't exist."""
    if DATA_FILE.exists():
        return json.loads(DATA_FILE.read_text())
    return {}


def save_data(data: dict):
    """Persist user timezone data to the JSON file."""
    DATA_FILE.write_text(json.dumps(data, indent=2))


def get_chat_users(data: dict, chat_id: str) -> dict:
    """Return the user dict for a given chat, creating it if absent.

    Data structure: { chat_id: { user_key: { username, display, tz } } }
    """
    return data.setdefault(chat_id, {})


# ── Helpers ───────────────────────────────────────────────────────────────────

def is_valid_tz(tz: str) -> bool:
    """Return True if tz is a valid IANA timezone identifier."""
    return tz in available_timezones()


def format_time_line(display_name: str, tz_str: str) -> str:
    """Format a single user's time as an HTML line with an awake/asleep indicator.

    Uses a simple heuristic: 7am–11pm local = awake (green), otherwise asleep (moon).
    """
    now = datetime.now(ZoneInfo(tz_str))
    time_str = now.strftime("%I:%M %p · %a %b %d")
    hour = now.hour
    indicator = "🟢" if 7 <= hour < 23 else "🌙"
    return f"{indicator} <b>{display_name}</b> — {time_str}\n    <i>{tz_str}</i>"


def is_admin(user_id: int) -> bool:
    """Return True if user_id has admin privileges.

    If ADMIN_IDS is empty, all users are treated as admins.
    """
    return len(ADMIN_IDS) == 0 or user_id in ADMIN_IDS


# ── Command Handlers ─────────────────────────────────────────────────────────

async def cmd_timeiswhat(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Handle /timeiswhat — show current local time for every registered user in this chat."""
    data = load_data()
    chat_id = str(update.effective_chat.id)
    users = get_chat_users(data, chat_id)

    if not users:
        await update.message.reply_text(
            "No users registered yet.\nUse /settz <timezone> to add yourself."
        )
        return

    lines = []
    for uid, info in sorted(users.items(), key=lambda x: x[1].get("tz", "")):
        lines.append(format_time_line(info["display"], info["tz"]))

    header = f"🕐 <b>Team Times</b> ({len(lines)} members)\n"
    await update.message.reply_html(header + "\n".join(lines))


async def cmd_whosawake(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Handle /whosawake — split registered users into awake (7am–11pm) and asleep groups."""
    data = load_data()
    chat_id = str(update.effective_chat.id)
    users = get_chat_users(data, chat_id)

    if not users:
        await update.message.reply_text(
            "No users registered yet.\nUse /settz <timezone> to add yourself."
        )
        return

    awake = []
    asleep = []
    for uid, info in sorted(users.items(), key=lambda x: x[1].get("tz", "")):
        now = datetime.now(ZoneInfo(info["tz"]))
        hour = now.hour
        time_str = now.strftime("%I:%M %p")
        if 7 <= hour < 23:
            awake.append(f"🟢 <b>{info['display']}</b> — {time_str}")
        else:
            asleep.append(f"🌙 <b>{info['display']}</b> — {time_str}")

    lines = []
    if awake:
        lines.append(f"<b>Awake ({len(awake)})</b>")
        lines.extend(awake)
    if asleep:
        if awake:
            lines.append("")
        lines.append(f"<b>Sleeping ({len(asleep)})</b>")
        lines.extend(asleep)

    await update.message.reply_html("\n".join(lines))


async def cmd_settz(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Handle /settz — register a timezone for the calling user or (admin only) another user.

    Usage:
      /settz America/Chicago          — self-register
      /settz @username Europe/London  — admin sets for another user
    """
    args = ctx.args or []

    # Determine target user and timezone
    if len(args) == 2 and args[0].startswith("@"):
        # Admin setting for another user: /settz @username America/New_York
        if not is_admin(update.effective_user.id):
            await update.message.reply_text("Only admins can set timezone for other users.")
            return
        target_username = args[0].lstrip("@").lower()
        tz_str = args[1]
        # We store by username since we don't have the target's user_id easily
        target_key = f"@{target_username}"
        display = f"@{target_username}"
    elif len(args) == 1:
        # Self-register: /settz America/Chicago
        tz_str = args[0]
        target_key = str(update.effective_user.id)
        display = (
            update.effective_user.full_name
            or update.effective_user.username
            or str(update.effective_user.id)
        )
    else:
        await update.message.reply_text(
            "Usage:\n"
            "  /settz America/Chicago\n"
            "  /settz @username Europe/London"
        )
        return

    if not is_valid_tz(tz_str):
        await update.message.reply_text(
            f"❌ Unknown timezone: <code>{tz_str}</code>\n"
            "Use /tzlist for examples, or check:\n"
            "https://en.wikipedia.org/wiki/List_of_tz_database_time_zones",
            parse_mode="HTML",
        )
        return

    data = load_data()
    chat_id = str(update.effective_chat.id)
    users = get_chat_users(data, chat_id)
    users[target_key] = {
        "username": display,
        "display": display,
        "tz": tz_str,
    }
    save_data(data)

    now = datetime.now(ZoneInfo(tz_str))
    await update.message.reply_html(
        f"✅ Set <b>{display}</b> → <code>{tz_str}</code>\n"
        f"Current time there: {now.strftime('%I:%M %p')}"
    )


async def cmd_removeuser(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Handle /removeuser @username — admin-only command to remove a user from this chat's list."""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Only admins can remove users.")
        return

    args = ctx.args or []
    if len(args) != 1:
        await update.message.reply_text("Usage: /removeuser @username")
        return

    target = args[0].lstrip("@").lower()
    data = load_data()
    chat_id = str(update.effective_chat.id)
    users = get_chat_users(data, chat_id)

    # Try both key formats (user_id and @username)
    removed = False
    for key in [f"@{target}", target]:
        if key in users:
            del users[key]
            removed = True
            break

    # Also search by display name / username field
    if not removed:
        for key, info in list(users.items()):
            if info.get("username", "").lower().lstrip("@") == target:
                del users[key]
                removed = True
                break

    if removed:
        save_data(data)
        await update.message.reply_text(f"✅ Removed @{target}")
    else:
        await update.message.reply_text(f"❌ User @{target} not found in this chat.")


async def cmd_tzlist(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Handle /tzlist — display a curated list of common IANA timezone identifiers."""
    examples = (
        "🌍 <b>Common Timezones</b>\n\n"
        "<b>Americas</b>\n"
        "  <code>America/New_York</code>      — US Eastern\n"
        "  <code>America/Chicago</code>       — US Central\n"
        "  <code>America/Denver</code>        — US Mountain\n"
        "  <code>America/Los_Angeles</code>   — US Pacific\n"
        "  <code>America/Toronto</code>       — Canada Eastern\n"
        "  <code>America/Sao_Paulo</code>     — Brazil\n\n"
        "<b>Europe</b>\n"
        "  <code>Europe/London</code>         — UK\n"
        "  <code>Europe/Paris</code>          — Central Europe\n"
        "  <code>Europe/Berlin</code>         — Germany\n"
        "  <code>Europe/Moscow</code>         — Russia\n\n"
        "<b>Asia / Pacific</b>\n"
        "  <code>Asia/Tokyo</code>            — Japan\n"
        "  <code>Asia/Shanghai</code>         — China\n"
        "  <code>Asia/Kolkata</code>          — India\n"
        "  <code>Asia/Dubai</code>            — UAE\n"
        "  <code>Australia/Sydney</code>      — Australia East\n\n"
        "Full list: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones"
    )
    await update.message.reply_html(examples)


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Handle /help and /start — display a summary of all available commands."""
    text = (
        "🤖 <b>Timezone Bot</b>\n\n"
        "/timeiswhat — See everyone's current time\n"
        "/whosawake — See who's likely awake\n"
        "/settz <code>America/Chicago</code> — Set your timezone\n"
        "/settz <code>@user Europe/London</code> — Set for someone else (admin)\n"
        "/removeuser <code>@user</code> — Remove a user (admin)\n"
        "/tzlist — Common timezone examples\n"
        "/help — This message"
    )
    await update.message.reply_html(text)


async def post_init(app: Application):
    """Register bot commands with Telegram so they appear in the command menu."""
    await app.bot.set_my_commands([
        BotCommand("timeiswhat", "Show team times"),
        BotCommand("whosawake", "Show who's awake right now"),
        BotCommand("settz", "Set your timezone"),
        BotCommand("removeuser", "Remove a user (admin)"),
        BotCommand("tzlist", "Common timezone examples"),
        BotCommand("help", "Show help"),
    ])


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    """Entry point — validate config, register handlers, and start polling."""
    if not BOT_TOKEN:
        print("Error: BOT_TOKEN environment variable is not set.")
        print("Get a token from @BotFather on Telegram, then run:")
        print("  export BOT_TOKEN=\"your_token_here\"")
        return

    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("timeiswhat", cmd_timeiswhat))
    app.add_handler(CommandHandler("whosawake", cmd_whosawake))
    app.add_handler(CommandHandler("settz", cmd_settz))
    app.add_handler(CommandHandler("removeuser", cmd_removeuser))
    app.add_handler(CommandHandler("tzlist", cmd_tzlist))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("start", cmd_help))

    logger.info("Bot starting...")
    app.run_polling()


if __name__ == "__main__":
    main()
