# TimeZoneBot

A Telegram bot for distributed teams to track each other's timezones. Ask "what time is it for everyone?" and get an instant answer with local times and an awake/asleep indicator.

## Prerequisites

- Python 3.11+
- A Telegram bot token from [@BotFather](https://t.me/BotFather)

## Installation

```bash
git clone https://github.com/your-username/TimeZoneBot.git
cd TimeZoneBot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Configuration

### BOT_TOKEN (required)

Set your bot token as an environment variable:

```bash
export BOT_TOKEN="your_token_here"
```

Or create a `.env` file (it's in `.gitignore` so it won't be committed):

```
BOT_TOKEN=your_token_here
```

Then load it before running: `source .env && python timezone_bot.py`

### ADMIN_IDS (optional)

Edit `timezone_bot.py` and add your Telegram user ID(s) to the `ADMIN_IDS` set:

```python
ADMIN_IDS: set[int] = {123456789}
```

You can find your user ID by messaging [@userinfobot](https://t.me/userinfobot) on Telegram. If `ADMIN_IDS` is left empty, all users can use admin commands.

## Running the Bot

```bash
source venv/bin/activate
export BOT_TOKEN="your_token_here"
python timezone_bot.py
```

Add the bot to a Telegram group and use `/help` to get started.

## Command Reference

| Command | Description |
|---|---|
| `/timeiswhat` | Show the current local time for every registered user |
| `/whosawake` | Show who is likely awake (7am–11pm local) vs. asleep |
| `/settz America/Chicago` | Register your own timezone |
| `/settz @username Europe/London` | Set a timezone for another user (admin only) |
| `/removeuser @username` | Remove a user from the list (admin only) |
| `/tzlist` | Display common IANA timezone identifiers with examples |
| `/help` | Show this command summary |

## Configuration Options

| Variable | Where | Description |
|---|---|---|
| `BOT_TOKEN` | Environment variable | Your Telegram bot token from @BotFather |
| `ADMIN_IDS` | `timezone_bot.py` line ~38 | Set of integer Telegram user IDs with admin access |
| `DATA_FILE` | `timezone_bot.py` line ~37 | Path to the JSON persistence file (default: `timezone_data.json`) |

## Data Format

User data is stored in `timezone_data.json` (excluded from version control). The structure is:

```json
{
  "-1001234567890": {
    "123456789": {
      "username": "Alice",
      "display": "Alice",
      "tz": "America/New_York"
    },
    "@bob": {
      "username": "@bob",
      "display": "@bob",
      "tz": "Europe/London"
    }
  }
}
```

Top-level keys are chat IDs. Within each chat, keys are either Telegram user IDs (for self-registered users) or `@username` strings (for admin-registered users).

## Dependencies

- **[python-telegram-bot](https://python-telegram-bot.org/) 20.x+** — async Telegram Bot API wrapper
- **zoneinfo** — IANA timezone support (Python 3.9+ standard library)

## License

MIT
