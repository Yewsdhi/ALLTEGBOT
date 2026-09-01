"""
ALLTEGBOT - robust member tracker / tagall helper.

Telegram Bot API limitation:
A bot cannot enumerate every historical member of a group on demand.
This module therefore tracks users whenever Telegram exposes them through
messages, joins, promotions/demotions, and other update events.
"""

import asyncio
import os
import sqlite3
from contextlib import closing
from html import escape

DB_PATH = os.getenv("DB_PATH", "alltegbot.sqlite3")
TAG_BATCH = max(1, int(os.getenv("TAG_BATCH", "5")))
TAG_DELAY = max(0.5, float(os.getenv("TAG_DELAY", "1.2")))

def init_db():
    with closing(sqlite3.connect(DB_PATH)) as con:
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("""
            CREATE TABLE IF NOT EXISTS members (
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                first_name TEXT,
                username TEXT,
                active INTEGER DEFAULT 1,
                PRIMARY KEY(chat_id, user_id)
            )
        """)
        con.commit()

def remember_user(chat_id, user):
    if not user or getattr(user, "is_bot", False):
        return
    init_db()
    with closing(sqlite3.connect(DB_PATH)) as con:
        con.execute("""
            INSERT INTO members(chat_id,user_id,first_name,username,active)
            VALUES(?,?,?,?,1)
            ON CONFLICT(chat_id,user_id) DO UPDATE SET
              first_name=excluded.first_name,
              username=excluded.username,
              active=1
        """, (
            chat_id, user.id,
            getattr(user, "first_name", None) or "",
            getattr(user, "username", None) or ""
        ))
        con.commit()

def remember_users_from_message(message):
    if not message:
        return
    remember_user(message.chat.id, message.from_user)
    for u in getattr(message, "new_chat_members", None) or []:
        remember_user(message.chat.id, u)

def deactivate_user(chat_id, user_id):
    init_db()
    with closing(sqlite3.connect(DB_PATH)) as con:
        con.execute(
            "UPDATE members SET active=0 WHERE chat_id=? AND user_id=?",
            (chat_id, user_id)
        )
        con.commit()

def get_members(chat_id):
    init_db()
    with closing(sqlite3.connect(DB_PATH)) as con:
        rows = con.execute("""
            SELECT user_id, first_name, username
            FROM members
            WHERE chat_id=? AND active=1
            ORDER BY rowid
        """, (chat_id,)).fetchall()
    return rows

def mention(user_id, first_name):
    name = (first_name or "Member").strip()[:64]
    return f'<a href="tg://user?id={int(user_id)}">{escape(name)}</a>'

async def send_tagall(bot, chat_id, text=""):
    rows = get_members(chat_id)
    if not rows:
        return 0

    # Keep each message below Telegram's message-size limits.
    chunks = []
    current = []
    for uid, first, _username in rows:
        current.append(mention(uid, first))
        if len(current) >= TAG_BATCH:
            chunks.append(" ".join(current))
            current = []
    if current:
        chunks.append(" ".join(current))

    sent = 0
    prefix = (text or "").strip()
    for i, chunk in enumerate(chunks):
        body = f"{prefix}\n\n{chunk}" if prefix else chunk
        try:
            await bot.send_message(chat_id, body, parse_mode="HTML")
            sent += 1
            if i + 1 < len(chunks):
                await asyncio.sleep(TAG_DELAY)
        except Exception:
            # Continue with remaining chunks if one batch fails.
            continue
    return sent

init_db()
