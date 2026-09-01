# ALLTEGBOT

A Python Telegram group bot with tagging, couples, games, welcome messages and moderation.

## Features

- `/tagall` and `/tagadmins`
- `/cancel` and `/tagdelay`
- Couple / ship commands
- Dice, coin, truth, dare and 8-ball
- Custom welcome messages
- Link lock
- Anti-spam message deletion
- SQLite persistence
- Inline help menu
- Heroku worker configuration

## Heroku

Set at least:

- `BOT_TOKEN` — required
- `BOT_USERNAME` — bot username without `@`
- `OWNER_CHAT_ID` — optional numeric owner ID
- `OWNER_URL`, `SUPPORT_URL`, `UPDATE_URL` — optional Telegram links

The bot must be an administrator in a group for commands that need admin privileges, and it needs **Delete Messages** permission for `/lock links` and `/antispam`.

### Local

```bash
python -m pip install -r requirements.txt
export BOT_TOKEN="YOUR_TOKEN"
python bot.py
```

## Important Telegram limitation

A normal Telegram bot cannot request the complete member list of a group. `/tagall` therefore tags members the bot has seen/remembered. `/tagadmins` uses Telegram's current administrator list.
