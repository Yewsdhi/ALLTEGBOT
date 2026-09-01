# ALLTEGBOT - New Full TagAll Build

## Features
- Robust SQLite member tracking
- Tracks users from normal messages and new-member updates
- `/tagall <message>` support through `tagall_system.py`
- Safe batched mentions and delay
- SQLite WAL mode
- Existing project files preserved

## Important Telegram limitation
The Telegram Bot API does not provide a method for a normal bot to enumerate
every historical member of a group. Therefore no bot-only implementation can
guarantee discovering/tagging 100% of members that have never interacted with
the bot.

For the largest possible member coverage, keep the bot in the group from the
start, give it appropriate admin permissions, and let it observe join/message
updates.

## Environment
Optional:
- `DB_PATH` - SQLite path (default `alltegbot.sqlite3`)
- `TAG_BATCH` - mentions per message (default 5)
- `TAG_DELAY` - seconds between messages (default 1.2)

Never put your bot token into source code. Use environment variables.
