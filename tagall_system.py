"""
ALLTEGBOT TagAll system.

Usage from python-telegram-bot:
    from tagall_system import remember_users_from_message, send_tagall

Important:
Telegram Bot API cannot enumerate every historical group member.
This module tags every member ID that the bot has legitimately observed/stored.
It never refuses just because the stored count is small.
"""

import asyncio
import html
import os
import sqlite3

DB_PATH = os.getenv("DB_PATH", "alltegbot.sqlite3")
TAG_BATCH = max(1, int(os.getenv("TAG_BATCH", "5")))
TAG_DELAY = max(0.5, float(os.getenv("TAG_DELAY", "1.2")))

def init_db():
    con = sqlite3.connect(DB_PATH)
    try:
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("""
            CREATE TABLE IF NOT EXISTS members (
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                first_name TEXT NOT NULL DEFAULT '',
                username TEXT NOT NULL DEFAULT '',
                active INTEGER NOT NULL DEFAULT 1,
                PRIMARY KEY(chat_id, user_id)
            )
        """)
        con.commit()
    finally:
        con.close()

def remember_user(chat_id, user):
    if not user or getattr(user, "is_bot", False):
        return
    init_db()
    con = sqlite3.connect(DB_PATH)
    try:
        con.execute("""
            INSERT INTO members(chat_id,user_id,first_name,username,active)
            VALUES(?,?,?,?,1)
            ON CONFLICT(chat_id,user_id) DO UPDATE SET
              first_name=excluded.first_name,
              username=excluded.username,
              active=1
        """, (
            int(chat_id),
            int(user.id),
            getattr(user, "first_name", "") or "",
            getattr(user, "username", "") or "",
        ))
        con.commit()
    finally:
        con.close()

def remember_users_from_message(message):
    if not message:
        return
    remember_user(message.chat.id, message.from_user)
    for user in (getattr(message, "new_chat_members", None) or []):
        remember_user(message.chat.id, user)

def deactivate_user(chat_id, user_id):
    init_db()
    con = sqlite3.connect(DB_PATH)
    try:
        con.execute(
            "UPDATE members SET active=0 WHERE chat_id=? AND user_id=?",
            (int(chat_id), int(user_id))
        )
        con.commit()
    finally:
        con.close()

def get_members(chat_id):
    init_db()
    con = sqlite3.connect(DB_PATH)
    try:
        return con.execute("""
            SELECT user_id, first_name, username
            FROM members
            WHERE chat_id=? AND active=1
            ORDER BY rowid ASC
        """, (int(chat_id),)).fetchall()
    finally:
        con.close()

def make_mention(user_id, first_name):
    name = (first_name or "Member").strip()[:64]
    return f'<a href="tg://user?id={int(user_id)}">{html.escape(name)}</a>'

async def send_tagall(bot, chat_id, text=""):
    """
    Sends the supplied message together with every stored member mention.
    No minimum-member check and no artificial 2/3/80 member cutoff.
    """
    rows = get_members(chat_id)
    if not rows:
        # This is only the unavoidable case where the bot has no user IDs.
        await bot.send_message(
            chat_id,
            "⚠️ No member IDs are available yet. Telegram does not let a bot "
            "download the complete historical member list.",
        )
        return 0

    prefix = (text or "").strip()
    sent_batches = 0
    batch = []

    async def flush(items):
        nonlocal sent_batches
        if not items:
            return
        mentions = " ".join(items)
        body = f"{prefix}\n\n{mentions}" if prefix else mentions
        # Telegram message text limit is handled by small batches.
        await bot.send_message(chat_id, body, parse_mode="HTML")
        sent_batches += 1

    for uid, first_name, _username in rows:
        batch.append(make_mention(uid, first_name))
        if len(batch) >= TAG_BATCH:
            try:
                await flush(batch)
            except Exception:
                # Keep processing remaining members if a batch fails.
                pass
            batch = []
            await asyncio.sleep(TAG_DELAY)

    if batch:
        try:
            await flush(batch)
        except Exception:
            pass

    return sent_batches

init_db()
