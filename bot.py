import os
import random
import sqlite3
import logging
import time
import asyncio
from html import escape

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode, ChatMemberStatus
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    ChatMemberHandler,
    filters,
)

# =========================================================
# CONFIG
# =========================================================

TOKEN = os.getenv("BOT_TOKEN")
BOT_USERNAME = os.getenv("BOT_USERNAME", "mentionmayabot")

SUPPORT_URL = os.getenv(
    "SUPPORT_URL",
    "https://t.me/annu_support"
)

UPDATE_URL = os.getenv(
    "UPDATE_URL",
    "https://t.me/annu_support"
)

# Put your direct image URL in Heroku Config Vars:
# START_IMAGE=https://your-domain.com/start.jpg
START_IMAGE = os.getenv("START_IMAGE", "https://n.uguu.se/UZTaivEa.jpg")

if not TOKEN:
    raise RuntimeError("BOT_TOKEN is missing")


# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

log = logging.getLogger("badnam")


# =========================================================
# DATABASE
# =========================================================

DB = os.getenv("DB_PATH", "maya.db")

conn = sqlite3.connect(
    DB,
    check_same_thread=False
)

conn.execute("PRAGMA journal_mode=WAL")

cur = conn.cursor()

cur.executescript("""
CREATE TABLE IF NOT EXISTS users(
    chat_id INTEGER,
    user_id INTEGER,
    name TEXT,
    username TEXT,
    last_seen INTEGER,
    PRIMARY KEY(chat_id,user_id)
);

CREATE TABLE IF NOT EXISTS couples(
    chat_id INTEGER,
    user_id INTEGER,
    partner_id INTEGER,
    PRIMARY KEY(chat_id,user_id)
);

CREATE TABLE IF NOT EXISTS settings(
    chat_id INTEGER PRIMARY KEY,
    welcome TEXT,
    welcome_enabled INTEGER DEFAULT 1,
    antispam INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS tags(
    chat_id INTEGER PRIMARY KEY,
    active INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS locks(
    chat_id INTEGER,
    feature TEXT,
    PRIMARY KEY(chat_id,feature)
);
""")

conn.commit()


# =========================================================
# DATABASE HELPER
# =========================================================

def db(sql, args=(), fetch=False):

    c = conn.cursor()

    c.execute(sql, args)

    if fetch:
        return c.fetchall()

    conn.commit()


# =========================================================
# HELPERS
# =========================================================

def mention(user_id, name):

    return (
        f'<a href="tg://user?id={user_id}">'
        f'{escape(name or "User")}'
        f'</a>'
    )


def is_group(update):

    return (
        update.effective_chat
        and update.effective_chat.type
        in ("group", "supergroup")
    )


async def is_admin(update, user_id=None):

    uid = user_id or update.effective_user.id

    try:

        member = await update.effective_chat.get_member(uid)

        return member.status in (
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER,
        )

    except Exception:

        return False


# =========================================================
# MAIN KEYBOARD
# =========================================================

def main_kb():

    return InlineKeyboardMarkup([

        [
            InlineKeyboardButton(
                "𓆩♡𓆪 𝘼𝘿𝘿 𝙈𝙀 𝙏𝙊 𝙂𝙍𝙊𝙐𝙋 ＋",
                url=f"https://t.me/{BOT_USERNAME}?startgroup=true"
            )
        ],

        [
            InlineKeyboardButton(
                "♡ 𝘾𝙊𝙐𝙋𝙇𝙀𝙎",
                callback_data="couples"
            ),

            InlineKeyboardButton(
                "♧ 𝙂𝘼𝙈𝙀",
                callback_data="games"
            )
        ],

        [
            InlineKeyboardButton(
                "✈ 𝙃𝙀𝙇𝙋 & 𝘾𝙊𝙈𝙈𝘼𝙉𝘿𝙎",
                callback_data="help"
            )
        ],

        [
            InlineKeyboardButton(
                "⌁ 𝙎𝙐𝙋𝙋𝙊𝙍𝙏 ↗",
                url=SUPPORT_URL
            ),

            InlineKeyboardButton(
                "☁ 𝙐𝙋𝘿𝘼𝙏𝙀𝙎 ↗",
                url=UPDATE_URL
            )
        ],

    ])


# =========================================================
# HELP KEYBOARD
# =========================================================

def help_kb():

    return InlineKeyboardMarkup([

        [
            InlineKeyboardButton(
                "✈ 𝙏𝘼𝙂 𝙎𝙔𝙎𝙏𝙀𝙈",
                callback_data="tag"
            ),

            InlineKeyboardButton(
                "♡ 𝘾𝙊𝙐𝙋𝙇𝙀𝙎",
                callback_data="couples"
            )
        ],

        [
            InlineKeyboardButton(
                "♧ 𝙂𝘼𝙈𝙀𝙎",
                callback_data="games"
            ),

            InlineKeyboardButton(
                "◈ 𝙐𝙎𝙀𝙍 𝙏𝙊𝙊𝙇𝙎",
                callback_data="tools"
            )
        ],

        [
            InlineKeyboardButton(
                "● 𝙒𝙀𝙇𝘾𝙊𝙈𝙀",
                callback_data="welcome"
            )
        ],

        [
            InlineKeyboardButton(
                "⚠ 𝙎𝙀𝘾𝙐𝙍𝙄𝙏𝙔 𝙂𝙐𝘼𝙍𝘿",
                callback_data="security"
            )
        ],

        [
            InlineKeyboardButton(
                "⌂ 𝘽𝘼𝘾𝙆 𝙏𝙊 𝙎𝙏𝘼𝙍𝙏",
                callback_data="home"
            )
        ],

    ])


# =========================================================
# START TEXT
# =========================================================

START = """<b>╭━━━━━━━━━━━━━━━━━━╮</b>
<b>     𓆩♡𓆪 𝙄𝙩'𝙨 𝙈𝙚 — 𝘽𝘼𝘿𝙉𝘼𝙈 🇨🇦</b>
<b>╰━━━━━━━━━━━━━━━━━━╯</b>

<b>        ✦ 𝙎𝙈𝘼𝙍𝙏 𝙏𝘼𝙂 𝘽𝙊𝙏 ✦</b>

<b>╭──────────────────╮</b>
│ ✈️ 𝙁𝙪𝙣 𝘾𝙤𝙣𝙫𝙚𝙧𝙨𝙖𝙩𝙞𝙤𝙣𝙨
│ 🥳 𝙂𝙧𝙤𝙪𝙥𝙨 & 𝙋𝙧𝙞𝙫𝙖𝙩𝙚
│ 🌈 𝘼𝙘𝙩𝙞𝙫𝙚 + 𝙁𝙪𝙣 𝘾𝙝𝙖𝙩𝙨
│ ⚡ 𝙋𝙧𝙚𝙢𝙞𝙪𝙢 𝙏𝙖𝙜 𝙎𝙮𝙨𝙩𝙚𝙢
│ 🌸 𝙎𝙩𝙮𝙡𝙞𝙨𝙝 & 𝙎𝙢𝙤𝙤𝙩𝙝
│ 🎭 𝙂𝙖𝙢𝙚𝙨 · 𝙁𝙪𝙣 𝙏𝙤𝙤𝙡𝙨
│ 🔮 𝘼𝙣𝙞𝙢𝙚 & 𝘼𝙚𝙨𝙩𝙝𝙚𝙩𝙞𝙘
<b>╰──────────────────╯</b>

<b>          𓆩♡𓆪 𝘾𝙝𝙤𝙤𝙨𝙚 𝘽𝙚𝙡𝙤𝙬</b>"""


# =========================================================
# HELP
# =========================================================

HELP = """<b>╭━━━━━━━━━━━━━━━━━━╮</b>
<b>      🌈 𝙃𝙀𝙇𝙋 𝘾𝙀𝙉𝙏𝙀𝙍</b>
<b>╰━━━━━━━━━━━━━━━━━━╯</b>

<b>✦ 𝙎𝙀𝙇𝙀𝘾𝙏 𝘼 𝘾𝘼𝙏𝙀𝙂𝙊𝙍𝙔 ✦</b>

<i>Choose a section below to explore
all available commands.</i>"""


# =========================================================
# HELP PAGES
# =========================================================

PAGES = {

    "tag": """<b>✈ 𝙏𝘼𝙂 𝙎𝙔𝙎𝙏𝙀𝙈</b>

<b>╭─ 𝙂𝙍𝙊𝙐𝙋 𝘾𝙊𝙈𝙈𝘼𝙉𝘿𝙎</b>

│ • <code>/tagall</code>
│   └─ 𝙏𝙖𝙜 𝙧𝙚𝙘𝙚𝙣𝙩𝙡𝙮 𝙖𝙘𝙩𝙞𝙫𝙚 𝙢𝙚𝙢𝙗𝙚𝙧𝙨
│
│ • <code>/tagadmins</code>
│   └─ 𝙏𝙖𝙜 𝙜𝙧𝙤𝙪𝙥 𝙖𝙙𝙢𝙞𝙣𝙨
│
│ • <code>/cancel</code>
│   └─ 𝙎𝙩𝙤𝙥 𝙩𝙖𝙜𝙜𝙞𝙣𝙜

<b>╰─ 𝘼𝘿𝙈𝙄𝙉</b>

• <code>/tagdelay 2</code>
  └─ 𝙎𝙚𝙩 𝙙𝙚𝙡𝙖𝙮 𝙗𝙚𝙩𝙬𝙚𝙚𝙣 𝙗𝙖𝙩𝙘𝙝𝙚𝙨

<i>Only users seen by the bot can be tagged.</i>""",

    "couples": """<b>♡ 𝘾𝙊𝙐𝙋𝙇𝙀𝙎 𝙎𝙔𝙎𝙏𝙀𝙈</b>

<b>💗 𝘼𝙑𝘼𝙄𝙇𝘼𝘽𝙇𝙀 𝘾𝙊𝙈𝙈𝘼𝙉𝘿𝙎</b>

• <code>/couple</code> — 𝙍𝙖𝙣𝙙𝙤𝙢 𝙘𝙤𝙪𝙥𝙡𝙚
• <code>/setcouple</code> — 𝙋𝙖𝙞𝙧 𝙬𝙞𝙩𝙝 𝙧𝙚𝙥𝙡𝙞𝙚𝙙 𝙪𝙨𝙚𝙧
• <code>/mycouple</code> — 𝙎𝙝𝙤𝙬 𝙮𝙤𝙪𝙧 𝙘𝙤𝙪𝙥𝙡𝙚
• <code>/delcouple</code> — 𝙍𝙚𝙢𝙤𝙫𝙚 𝙘𝙤𝙪𝙥𝙡𝙚
• <code>/ship</code> — 𝘾𝙤𝙢𝙥𝙖𝙩𝙞𝙗𝙞𝙡𝙞𝙩𝙮 𝙜𝙖𝙢𝙚""",

    "games": """<b>♧ 𝙂𝘼𝙈𝙀𝙎 & 𝘼𝘾𝙏𝙄𝙑𝙄𝙏𝙄𝙀𝙎</b>

🎲 <code>/dice</code> — 𝙍𝙤𝙡𝙡 𝙙𝙞𝙘𝙚
🪙 <code>/coin</code> — 𝙃𝙚𝙖𝙙𝙨 𝙤𝙧 𝙩𝙖𝙞𝙡𝙨
💭 <code>/truth</code> — 𝙏𝙧𝙪𝙩𝙝 𝙦𝙪𝙚𝙨𝙩𝙞𝙤𝙣
🔥 <code>/dare</code> — 𝘿𝙖𝙧𝙚 𝙘𝙝𝙖𝙡𝙡𝙚𝙣𝙜𝙚
💘 <code>/ship</code> — 𝙎𝙝𝙞𝙥 𝙩𝙬𝙤 𝙪𝙨𝙚𝙧𝙨
🎱 <code>/8ball</code> — 𝙈𝙖𝙜𝙞𝙘 𝟴-𝙗𝙖𝙡𝙡""",

    "tools": """<b>◈ 𝙐𝙎𝙀𝙍 𝙏𝙊𝙊𝙇𝙎</b>

👤 <code>/id</code> — 𝙐𝙨𝙚𝙧 / 𝙘𝙝𝙖𝙩 𝙄𝘿
🌸 <code>/info</code> — 𝙐𝙨𝙚𝙧 𝙞𝙣𝙛𝙤𝙧𝙢𝙖𝙩𝙞𝙤𝙣
⚡ <code>/ping</code> — 𝘽𝙤𝙩 𝙨𝙩𝙖𝙩𝙪𝙨
🏠 <code>/start</code> — 𝙈𝙖𝙞𝙣 𝙢𝙚𝙣𝙪
✈ <code>/help</code> — 𝙃𝙚𝙡𝙥 𝙘𝙚𝙣𝙩𝙚𝙧""",

    "welcome": """<b>● 𝙒𝙀𝙇𝘾𝙊𝙈𝙀 𝙎𝙔𝙎𝙏𝙀𝙈</b>

• <code>/setwelcome TEXT</code>
  └─ 𝙎𝙚𝙩 𝙜𝙧𝙤𝙪𝙥 𝙬𝙚𝙡𝙘𝙤𝙢𝙚

• <code>/delwelcome</code>
  └─ 𝙍𝙚𝙢𝙤𝙫𝙚 𝙘𝙪𝙨𝙩𝙤𝙢 𝙬𝙚𝙡𝙘𝙤𝙢𝙚

• <code>/welcome</code>
  └─ 𝙎𝙝𝙤𝙬 𝙘𝙪𝙧𝙧𝙚𝙣𝙩 𝙬𝙚𝙡𝙘𝙤𝙢𝙚

<b>𝙑𝘼𝙍𝙄𝘼𝘽𝙇𝙀𝙎</b>

<code>{name}</code>
<code>{mention}</code>
<code>{title}</code>""",

    "security": """<b>⚠ 𝙎𝙀𝘾𝙐𝙍𝙄𝙏𝙔 𝙂𝙐𝘼𝙍𝘿</b>

🛡️ <code>/antispam on</code>
   └─ 𝙀𝙣𝙖𝙗𝙡𝙚 𝙗𝙖𝙨𝙞𝙘 𝙖𝙣𝙩𝙞-𝙨𝙥𝙖𝙢

🛡️ <code>/antispam off</code>
   └─ 𝘿𝙞𝙨𝙖𝙗𝙡𝙚 𝙖𝙣𝙩𝙞-𝙨𝙥𝙖𝙢

🧹 <code>/clean</code>
   └─ 𝘽𝙤𝙩 𝙘𝙤𝙢𝙢𝙖𝙣𝙙 𝙘𝙡𝙚𝙖𝙣𝙪𝙥

🔒 <code>/lock links</code>
   └─ 𝙇𝙤𝙘𝙠 𝙡𝙞𝙣𝙠𝙨

🔓 <code>/unlock links</code>
   └─ 𝙐𝙣𝙡𝙤𝙘𝙠 𝙡𝙞𝙣𝙠𝙨

<i>Security commands require group-admin rights.</i>"""
}


# =========================================================
# START COMMAND
# =========================================================

async def start(update, context):

    if START_IMAGE:

        try:

            await update.message.reply_photo(
                photo=START_IMAGE,
                caption=START,
                parse_mode=ParseMode.HTML,
                reply_markup=main_kb(),
            )

            return

        except Exception as e:

            log.warning(
                "Start image failed: %s",
                e
            )

    await update.message.reply_text(
        START,
        parse_mode=ParseMode.HTML,
        reply_markup=main_kb(),
        disable_web_page_preview=True,
    )


# =========================================================
# HELP COMMAND
# =========================================================

async def help_cmd(update, context):

    await update.message.reply_text(
        HELP,
        parse_mode=ParseMode.HTML,
        reply_markup=help_kb(),
    )


# =========================================================
# BUTTON HANDLER
# =========================================================

async def buttons(update, context):

    q = update.callback_query

    await q.answer()

    if q.data == "home":

        await q.edit_message_text(
            START,
            parse_mode=ParseMode.HTML,
            reply_markup=main_kb(),
        )

    elif q.data == "help":

        await q.edit_message_text(
            HELP,
            parse_mode=ParseMode.HTML,
            reply_markup=help_kb(),
        )

    elif q.data in PAGES:

        await q.edit_message_text(
            PAGES[q.data],
            parse_mode=ParseMode.HTML,
            reply_markup=help_kb(),
        )


# =========================================================
# REMEMBER USERS
# =========================================================

async def remember(update, context):

    u = update.effective_user
    ch = update.effective_chat

    if not u or not ch:
        return

    db(
        """
        INSERT INTO users
        (chat_id,user_id,name,username,last_seen)
        VALUES(?,?,?,?,?)

        ON CONFLICT(chat_id,user_id)
        DO UPDATE SET
        name=excluded.name,
        username=excluded.username,
        last_seen=excluded.last_seen
        """,
        (
            ch.id,
            u.id,
            u.full_name,
            u.username,
            int(time.time()),
        ),
    )


async def track_message(update, context):

    await remember(update, context)


# =========================================================
# ID
# =========================================================

async def id_cmd(update, context):

    u = update.effective_user
    ch = update.effective_chat

    target = u

    if update.message.reply_to_message:

        target = update.message.reply_to_message.from_user

    await update.message.reply_text(
        f"""<b>👤 𝙐𝙎𝙀𝙍 𝙄𝙉𝙁𝙊</b>

👤 <b>𝙐𝙨𝙚𝙧:</b>
{mention(target.id,target.full_name)}

🆔 <b>𝙐𝙨𝙚𝙧 𝙄𝘿:</b>
<code>{target.id}</code>

💬 <b>𝘾𝙝𝙖𝙩 𝙄𝘿:</b>
<code>{ch.id}</code>""",
        parse_mode=ParseMode.HTML,
    )


# =========================================================
# INFO
# =========================================================

async def info_cmd(update, context):

    u = (
        update.message.reply_to_message.from_user
        if update.message.reply_to_message
        else update.effective_user
    )

    username = (
        f"@{escape(u.username)}"
        if u.username
        else "𝙉𝙤 𝙪𝙨𝙚𝙧𝙣𝙖𝙢𝙚"
    )

    await update.message.reply_text(
        f"""<b>🌸 𝙐𝙎𝙀𝙍 𝙄𝙉𝙁𝙊</b>

👤 {mention(u.id,u.full_name)}

🆔 <code>{u.id}</code>

🔗 {username}""",
        parse_mode=ParseMode.HTML,
    )


# =========================================================
# PING
# =========================================================

async def ping(update, context):

    t = time.monotonic()

    msg = await update.message.reply_text(
        "✦ 𝘾𝙝𝙚𝙘𝙠𝙞𝙣𝙜..."
    )

    ms = int(
        (time.monotonic() - t) * 1000
    )

    await msg.edit_text(
        f"✦ <b>𝙋𝙤𝙣𝙜!</b> "
        f"<code>{ms}ms</code> ✨",
        parse_mode=ParseMode.HTML,
    )


# =========================================================
# ADMINS
# =========================================================

async def admins(update, context):

    if not is_group(update):

        return await update.message.reply_text(
            "⚠️ 𝙏𝙝𝙞𝙨 𝙘𝙤𝙢𝙢𝙖𝙣𝙙 𝙬𝙤𝙧𝙠𝙨 𝙞𝙣 𝙜𝙧𝙤𝙪𝙥𝙨."
        )

    admins_list = (
        await update.effective_chat
        .get_administrators()
    )

    text = "<b>✈ 𝙂𝙍𝙊𝙐𝙋 𝘼𝘿𝙈𝙄𝙉𝙎</b>\n\n"

    text += "\n".join(
        f"• {mention(a.user.id,a.user.full_name)}"
        for a in admins_list
    )

    await update.message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
    )


# =========================================================
# TAG ALL
# =========================================================

async def tagall(update, context):

    if not is_group(update):
        return

    if not await is_admin(update):

        return await update.message.reply_text(
            "⚠️ 𝙊𝙣𝙡𝙮 𝙜𝙧𝙤𝙪𝙥 𝙖𝙙𝙢𝙞𝙣𝙨 𝙘𝙖𝙣 𝙪𝙨𝙚 /tagall."
        )

    rows = db(
        """
        SELECT user_id,name
        FROM users
        WHERE chat_id=?
        ORDER BY last_seen DESC
        LIMIT 80
        """,
        (update.effective_chat.id,),
        True,
    )

    rows = [
        (i, n)
        for i, n in rows
        if i != update.effective_user.id
    ]

    if not rows:

        return await update.message.reply_text(
            "🌈 𝙄 𝙝𝙖𝙫𝙚𝙣'𝙩 𝙨𝙚𝙚𝙣 𝙚𝙣𝙤𝙪𝙜𝙝 𝙢𝙚𝙢𝙗𝙚𝙧𝙨 𝙮𝙚𝙩."
        )

    db(
        """
        INSERT INTO tags(chat_id,active)
        VALUES(?,1)

        ON CONFLICT(chat_id)
        DO UPDATE SET active=1
        """,
        (update.effective_chat.id,),
    )

    for start_index in range(
        0,
        len(rows),
        8
    ):

        state = db(
            """
            SELECT active
            FROM tags
            WHERE chat_id=?
            """,
            (update.effective_chat.id,),
            True,
        )

        if not state or not state[0][0]:
            break

        chunk = rows[
            start_index:start_index + 8
        ]

        await update.message.reply_text(
            "✈️ " + " ".join(
                mention(i, n)
                for i, n in chunk
            ),
            parse_mode=ParseMode.HTML,
        )

        await asyncio.sleep(2)

    db(
        """
        UPDATE tags
        SET active=0
        WHERE chat_id=?
        """,
        (update.effective_chat.id,),
    )


# =========================================================
# CANCEL
# =========================================================

async def cancel(update, context):

    db(
        """
        UPDATE tags
        SET active=0
        WHERE chat_id=?
        """,
        (update.effective_chat.id,),
    )

    await update.message.reply_text(
        "🛑 𝙏𝙖𝙜𝙜𝙞𝙣𝙜 𝙨𝙩𝙤𝙥𝙥𝙚𝙙."
    )


# =========================================================
# COUPLE
# =========================================================

async def couple(update, context):

    if not is_group(update):
        return

    rows = db(
        """
        SELECT user_id,name
        FROM users
        WHERE chat_id=?
        ORDER BY RANDOM()
        LIMIT 2
        """,
        (update.effective_chat.id,),
        True,
    )

    if len(rows) < 2:

        return await update.message.reply_text(
            "💞 𝙉𝙚𝙚𝙙 𝙖𝙩 𝙡𝙚𝙖𝙨𝙩 𝟮 𝙖𝙘𝙩𝙞𝙫𝙚 𝙢𝙚𝙢𝙗𝙚𝙧𝙨."
        )

    a, b = rows

    await update.message.reply_text(
        f"""<b>💞 𝙏𝙊𝘿𝘼𝙔'𝙎 𝘾𝙊𝙐𝙋𝙇𝙀</b>

{mention(a[0],a[1])}
        💗
{mention(b[0],b[1])}

<i>𓆩♡𓆪 𝙈𝙖𝙙𝙚 𝙛𝙤𝙧 𝙚𝙖𝙘𝙝 𝙤𝙩𝙝𝙚𝙧?</i>""",
        parse_mode=ParseMode.HTML,
    )


# =========================================================
# SET COUPLE
# =========================================================

async def setcouple(update, context):

    if (
        not is_group(update)
        or not update.message.reply_to_message
    ):

        return await update.message.reply_text(
            "💗 𝙍𝙚𝙥𝙡𝙮 𝙩𝙤 𝙖 𝙪𝙨𝙚𝙧 𝙬𝙞𝙩𝙝 /setcouple"
        )

    a = update.effective_user

    b = (
        update.message
        .reply_to_message
        .from_user
    )

    db(
        """
        INSERT OR REPLACE INTO couples
        VALUES(?,?,?)
        """,
        (
            update.effective_chat.id,
            a.id,
            b.id,
        ),
    )

    db(
        """
        INSERT OR REPLACE INTO couples
        VALUES(?,?,?)
        """,
        (
            update.effective_chat.id,
            b.id,
            a.id,
        ),
    )

    await update.message.reply_text(
        f"""<b>💗 𝘾𝙊𝙐𝙋𝙇𝙀 𝙎𝙀𝙏</b>

{mention(a.id,a.full_name)}
        +
{mention(b.id,b.full_name)}

<i>𓆩♡𓆪 𝙋𝙚𝙧𝙛𝙚𝙘𝙩 𝙢𝙖𝙩𝙘𝙝!</i>""",
        parse_mode=ParseMode.HTML,
    )


# =========================================================
# MY COUPLE
# =========================================================

async def mycouple(update, context):

    r = db(
        """
        SELECT partner_id
        FROM couples
        WHERE chat_id=? AND user_id=?
        """,
        (
            update.effective_chat.id,
            update.effective_user.id,
        ),
        True,
    )

    if not r:

        return await update.message.reply_text(
            "💔 𝙔𝙤𝙪 𝙙𝙤𝙣'𝙩 𝙝𝙖𝙫𝙚 𝙖 𝙘𝙤𝙪𝙥𝙡𝙚 𝙮𝙚𝙩."
        )

    p = db(
        """
        SELECT name
        FROM users
        WHERE chat_id=? AND user_id=?
        """,
        (
            update.effective_chat.id,
            r[0][0],
        ),
        True,
    )

    name = (
        p[0][0]
        if p
        else "Your partner"
    )

    await update.message.reply_text(
        f"""<b>💞 𝙔𝙊𝙐𝙍 𝘾𝙊𝙐𝙋𝙇𝙀</b>

{mention(r[0][0],name)} 💗

<i>𓆩♡𓆪 𝙇𝙤𝙫𝙚 𝙞𝙨 𝙞𝙣 𝙩𝙝𝙚 𝙖𝙞𝙧!</i>""",
        parse_mode=ParseMode.HTML,
    )


# =========================================================
# DELETE COUPLE
# =========================================================

async def delcouple(update, context):

    db(
        """
        DELETE FROM couples
        WHERE chat_id=? AND user_id=?
        """,
        (
            update.effective_chat.id,
            update.effective_user.id,
        ),
    )

    await update.message.reply_text(
        "💔 𝘾𝙤𝙪𝙥𝙡𝙚 𝙧𝙚𝙢𝙤𝙫𝙚𝙙."
    )


# =========================================================
# SHIP
# =========================================================

async def ship(update, context):

    if not is_group(update):
        return

    rows = db(
        """
        SELECT user_id,name
        FROM users
        WHERE chat_id=?
        ORDER BY RANDOM()
        LIMIT 2
        """,
        (update.effective_chat.id,),
        True,
    )

    if len(rows) < 2:

        return await update.message.reply_text(
            "💗 𝙉𝙤𝙩 𝙚𝙣𝙤𝙪𝙜𝙝 𝙖𝙘𝙩𝙞𝙫𝙚 𝙪𝙨𝙚𝙧𝙨."
        )

    score = random.randint(
        0,
        100
    )

    emoji = (
        "💞"
        if score > 70
        else "🌸"
    )

    await update.message.reply_text(
        f"""<b>💘 𝙇𝙊𝙑𝙀 𝙎𝙃𝙄𝙋</b>

{mention(rows[0][0],rows[0][1])}
        ×
{mention(rows[1][0],rows[1][1])}

<b>♡ 𝘾𝙤𝙢𝙥𝙖𝙩𝙞𝙗𝙞𝙡𝙞𝙩𝙮:
{score}%</b> {emoji}""",
        parse_mode=ParseMode.HTML,
    )


# =========================================================
# DICE
# =========================================================

async def dice(update, context):

    result = random.randint(
        1,
        6
    )

    await update.message.reply_text(
        f"🎲 <b>𝙔𝙤𝙪 𝙧𝙤𝙡𝙡𝙚𝙙:</b> "
        f"{result} ✨",
        parse_mode=ParseMode.HTML,
    )


# =========================================================
# COIN
# =========================================================

async def coin(update, context):

    result = random.choice([
        "𝙃𝙚𝙖𝙙𝙨",
        "𝙏𝙖𝙞𝙡𝙨"
    ])

    await update.message.reply_text(
        f"🪙 <b>{result}</b>!",
        parse_mode=ParseMode.HTML,
    )


# =========================================================
# TRUTH / DARE / 8 BALL
# =========================================================

TRUTHS = [
    "𝙒𝙝𝙤 𝙬𝙖𝙨 𝙮𝙤𝙪𝙧 𝙡𝙖𝙨𝙩 𝙘𝙧𝙪𝙨𝙝?",
    "𝙒𝙝𝙖𝙩 𝙞𝙨 𝙮𝙤𝙪𝙧 𝙗𝙞𝙜𝙜𝙚𝙨𝙩 𝙨𝙚𝙘𝙧𝙚𝙩?",
    "𝙒𝙝𝙤 𝙙𝙤 𝙮𝙤𝙪 𝙩𝙚𝙭𝙩 𝙩𝙝𝙚 𝙢𝙤𝙨𝙩?",
]

DARES = [
    "𝙎𝙚𝙣𝙙 𝙖 𝙛𝙪𝙣𝙣𝙮 𝙨𝙩𝙞𝙘𝙠𝙚𝙧.",
    "𝘾𝙝𝙖𝙣𝙜𝙚 𝙮𝙤𝙪𝙧 𝙥𝙧𝙤𝙛𝙞𝙡𝙚 𝙗𝙞𝙤 𝙛𝙤𝙧 𝟱 𝙢𝙞𝙣𝙪𝙩𝙚𝙨.",
    "𝘾𝙤𝙢𝙥𝙡𝙞𝙢𝙚𝙣𝙩 𝙨𝙤𝙢𝙚𝙤𝙣𝙚 𝙞𝙣 𝙩𝙝𝙞𝙨 𝙜𝙧𝙤𝙪𝙥.",
]

ANS = [
    "𝙔𝙚𝙨.",
    "𝙉𝙤.",
    "𝙈𝙖𝙮𝙗𝙚.",
    "𝘿𝙚𝙛𝙞𝙣𝙞𝙩𝙚𝙡𝙮!",
    "𝘼𝙨𝙠 𝙖𝙜𝙖𝙞𝙣 𝙡𝙖𝙩𝙚𝙧.",
    "𝙏𝙝𝙚 𝙨𝙞𝙜𝙣𝙨 𝙨𝙖𝙮 𝙮𝙚𝙨.",
]


async def truth(update, context):

    await update.message.reply_text(
        "💭 <b>𝙏𝙧𝙪𝙩𝙝:</b> "
        + random.choice(TRUTHS),
        parse_mode=ParseMode.HTML,
    )


async def dare(update, context):

    await update.message.reply_text(
        "🔥 <b>𝘿𝙖𝙧𝙚:</b> "
        + random.choice(DARES),
        parse_mode=ParseMode.HTML,
    )


async def ball(update, context):

    await update.message.reply_text(
        "🎱 "
        + random.choice(ANS)
    )


# =========================================================
# WELCOME
# =========================================================

async def welcome_cmd(update, context):

    r = db(
        """
        SELECT welcome,welcome_enabled
        FROM settings
        WHERE chat_id=?
        """,
        (update.effective_chat.id,),
        True,
    )

    if not r:

        return await update.message.reply_text(
            "🔵 <b>𝙒𝙚𝙡𝙘𝙤𝙢𝙚 𝙨𝙮𝙨𝙩𝙚𝙢 𝙞𝙨 𝙊𝙉.</b>\n\n"
            "𝙉𝙤 𝙘𝙪𝙨𝙩𝙤𝙢 𝙩𝙚𝙭𝙩 𝙨𝙚𝙩.",
            parse_mode=ParseMode.HTML,
        )

    await update.message.reply_text(
        f"<b>🔵 𝙒𝙚𝙡𝙘𝙤𝙢𝙚:</b>\n\n"
        f"{escape(r[0][0] or 'Default welcome')}",
        parse_mode=ParseMode.HTML,
    )


# =========================================================
# SET WELCOME
# =========================================================

async def setwelcome(update, context):

    if (
        not is_group(update)
        or not await is_admin(update)
    ):

        return await update.message.reply_text(
            "⚠️ 𝘼𝙙𝙢𝙞𝙣𝙨 𝙤𝙣𝙡𝙮."
        )

    text = (
        update.message.text
        .partition(" ")[2]
        .strip()
    )

    if not text:

        return await update.message.reply_text(
            "𝙐𝙨𝙚:\n\n"
            "<code>/setwelcome "
            "Welcome {mention} to {title} 🌸</code>",
            parse_mode=ParseMode.HTML,
        )

    db(
        """
        INSERT INTO settings
        (chat_id,welcome,welcome_enabled)
        VALUES(?,?,1)

        ON CONFLICT(chat_id)
        DO UPDATE SET
        welcome=excluded.welcome,
        welcome_enabled=1
        """,
        (
            update.effective_chat.id,
            text,
        ),
    )

    await update.message.reply_text(
        "✅ 𝙒𝙚𝙡𝙘𝙤𝙢𝙚 𝙢𝙚𝙨𝙨𝙖𝙜𝙚 𝙨𝙖𝙫𝙚𝙙."
    )


# =========================================================
# DELETE WELCOME
# =========================================================

async def delwelcome(update, context):

    if not await is_admin(update):
        return

    db(
        """
        UPDATE settings
        SET welcome=NULL,
            welcome_enabled=1
        WHERE chat_id=?
        """,
        (update.effective_chat.id,),
    )

    await update.message.reply_text(
        "🗑️ 𝘾𝙪𝙨𝙩𝙤𝙢 𝙬𝙚𝙡𝙘𝙤𝙢𝙚 𝙧𝙚𝙢𝙤𝙫𝙚𝙙."
    )


# =========================================================
# NEW MEMBER
# =========================================================

async def new_member(update, context):

    if not update.chat_member:
        return

    cm = update.chat_member

    if cm.new_chat_member.status not in (
        ChatMemberStatus.MEMBER,
        ChatMemberStatus.RESTRICTED,
    ):
        return

    u = cm.new_chat_member.user
    ch = cm.chat

    r = db(
        """
        SELECT welcome,welcome_enabled
        FROM settings
        WHERE chat_id=?
        """,
        (ch.id,),
        True,
    )

    if r and r[0][1]:

        text = (
            r[0][0]
            or "🌸 Welcome {mention} to <b>{title}</b>!"
        )

    else:

        text = (
            "🌸 Welcome {mention} "
            "to <b>{title}</b>!"
        )

    text = text.replace(
        "{name}",
        escape(u.full_name),
    )

    text = text.replace(
        "{mention}",
        mention(
            u.id,
            u.full_name
        ),
    )

    text = text.replace(
        "{title}",
        escape(
            ch.title or "our group"
        ),
    )

    await context.bot.send_message(
        ch.id,
        text,
        parse_mode=ParseMode.HTML,
    )


# =========================================================
# ANTISPAM
# =========================================================

async def antispam(update, context):

    if not await is_admin(update):

        return await update.message.reply_text(
            "⚠️ 𝘼𝙙𝙢𝙞𝙣𝙨 𝙤𝙣𝙡𝙮."
        )

    arg = (
        context.args[0].lower()
        if context.args
        else ""
    )

    if arg not in ("on", "off"):

        return await update.message.reply_text(
            "𝙐𝙨𝙚:\n"
            "<code>/antispam on</code>\n"
            "<code>/antispam off</code>",
            parse_mode=ParseMode.HTML,
        )

    enabled = (
        1
        if arg == "on"
        else 0
    )

    db(
        """
        INSERT INTO settings
        (chat_id,antispam)
        VALUES(?,?)

        ON CONFLICT(chat_id)
        DO UPDATE SET
        antispam=excluded.antispam
        """,
        (
            update.effective_chat.id,
            enabled,
        ),
    )

    await update.message.reply_text(
        f"🛡️ 𝘼𝙣𝙩𝙞-𝙨𝙥𝙖𝙢 "
        f"{'𝙚𝙣𝙖𝙗𝙡𝙚𝙙' if enabled else '𝙙𝙞𝙨𝙖𝙗𝙡𝙚𝙙'}."
    )


# =========================================================
# LOCK
# =========================================================

async def lock(update, context):

    if not await is_admin(update):
        return

    feature = (
        context.args[0].lower()
        if context.args
        else "links"
    )

    db(
        """
        INSERT OR IGNORE INTO locks
        VALUES(?,?)
        """,
        (
            update.effective_chat.id,
            feature,
        ),
    )

    await update.message.reply_text(
        f"🔒 <b>𝙇𝙤𝙘𝙠 𝙚𝙣𝙖𝙗𝙡𝙚𝙙:</b> "
        f"{escape(feature)}",
        parse_mode=ParseMode.HTML,
    )


# =========================================================
# UNLOCK
# =========================================================

async def unlock(update, context):

    if not await is_admin(update):
        return

    feature = (
        context.args[0].lower()
        if context.args
        else "links"
    )

    db(
        """
        DELETE FROM locks
        WHERE chat_id=? AND feature=?
        """,
        (
            update.effective_chat.id,
            feature,
        ),
    )

    await update.message.reply_text(
        f"🔓 <b>𝙇𝙤𝙘𝙠 𝙙𝙞𝙨𝙖𝙗𝙡𝙚𝙙:</b> "
        f"{escape(feature)}",
        parse_mode=ParseMode.HTML,
    )


# =========================================================
# SECURITY FILTER
# =========================================================

async def security_filter(update, context):

    if (
        not update.message
        or not is_group(update)
    ):
        return

    u = update.effective_user

    if await is_admin(update, u.id):
        return

    text = (
        update.message.text
        or update.message.caption
        or ""
    )

    if (
        "http://" in text
        or "https://" in text
        or "t.me/" in text
    ):

        r = db(
            """
            SELECT 1
            FROM locks
            WHERE chat_id=?
            AND feature='links'
            """,
            (update.effective_chat.id,),
            True,
        )

        if r:

            try:

                await update.message.delete()

            except Exception:

                pass


# =========================================================
# BUILD APPLICATION
# =========================================================

def build():

    app = (
        Application
        .builder()
        .token(TOKEN)
        .build()
    )

    # ---------------- BASIC ----------------

    app.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    app.add_handler(
        CommandHandler(
            "help",
            help_cmd
        )
    )

    app.add_handler(
        CommandHandler(
            "ping",
            ping
        )
    )

    app.add_handler(
        CommandHandler(
            "id",
            id_cmd
        )
    )

    app.add_handler(
        CommandHandler(
            "info",
            info_cmd
        )
    )

    # ---------------- TAG ----------------

    app.add_handler(
        CommandHandler(
            "tagall",
            tagall
        )
    )

    app.add_handler(
        CommandHandler(
            "tagadmins",
            admins
        )
    )

    app.add_handler(
        CommandHandler(
            "cancel",
            cancel
        )
    )

    # ---------------- COUPLES ----------------

    app.add_handler(
        CommandHandler(
            "couple",
            couple
        )
    )

    app.add_handler(
        CommandHandler(
            "setcouple",
            setcouple
        )
    )

    app.add_handler(
        CommandHandler(
            "mycouple",
            mycouple
        )
    )

    app.add_handler(
        CommandHandler(
            "delcouple",
            delcouple
        )
    )

    app.add_handler(
        CommandHandler(
            "ship",
            ship
        )
    )

    # ---------------- GAMES ----------------

    app.add_handler(
        CommandHandler(
            "dice",
            dice
        )
    )

    app.add_handler(
        CommandHandler(
            "coin",
            coin
        )
    )

    app.add_handler(
        CommandHandler(
            "truth",
            truth
        )
    )

    app.add_handler(
        CommandHandler(
            "dare",
            dare
        )
    )

    app.add_handler(
        CommandHandler(
            "8ball",
            ball
        )
    )

    # ---------------- WELCOME ----------------

    app.add_handler(
        CommandHandler(
            "welcome",
            welcome_cmd
        )
    )

    app.add_handler(
        CommandHandler(
            "setwelcome",
            setwelcome
        )
    )

    app.add_handler(
        CommandHandler(
            "delwelcome",
            delwelcome
        )
    )

    # ---------------- SECURITY ----------------

    app.add_handler(
        CommandHandler(
            "antispam",
            antispam
        )
    )

    app.add_handler(
        CommandHandler(
            "lock",
            lock
        )
    )

    app.add_handler(
        CommandHandler(
            "unlock",
            unlock
        )
    )

    # ---------------- BUTTONS ----------------

    app.add_handler(
        CallbackQueryHandler(
            buttons
        )
    )

    # ---------------- NEW MEMBERS ----------------

    app.add_handler(
        ChatMemberHandler(
            new_member,
            ChatMemberHandler.CHAT_MEMBER
        )
    )

    # ---------------- USER TRACKING ----------------

    app.add_handler(
        MessageHandler(
            filters.ALL & ~filters.COMMAND,
            track_message
        )
    )

    # ---------------- SECURITY ----------------

    app.add_handler(
        MessageHandler(
            filters.ALL & ~filters.COMMAND,
            security_filter
        )
    )

    return app


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    app = build()

    log.info(
        "𓆩♡𓆪 BADNAM Mention Bot started successfully"
    )

    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )
