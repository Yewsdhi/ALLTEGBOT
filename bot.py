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

OWNER_URL = os.getenv(
    "OWNER_URL",
    "https://t.me/your_username"
)

# Direct image URL for /start
START_IMAGE = os.getenv("START_IMAGE", "")

DEFAULT_TAG_DELAY = 2

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

conn.executescript("""
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
    antispam INTEGER DEFAULT 0,
    tag_delay REAL DEFAULT 2
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

# Old database compatibility
try:
    conn.execute(
        "ALTER TABLE settings ADD COLUMN tag_delay REAL DEFAULT 2"
    )
    conn.commit()
except sqlite3.OperationalError:
    pass


# =========================================================
# DATABASE HELPER
# =========================================================

def db(sql, args=(), fetch=False):
    cursor = conn.cursor()
    cursor.execute(sql, args)

    if fetch:
        return cursor.fetchall()

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
    if not update.effective_chat:
        return False

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
# START MESSAGE
# =========================================================

START = """<b>╭━━━━━━━━━━━━━━━━━━━━╮</b>
<b>   𓆩♡𓆪 𝙄𝙩'𝙨 𝙈𝙚 — 𝘽𝘼𝘿𝙉𝘼𝙈 🇨🇦</b>
<b>╰━━━━━━━━━━━━━━━━━━━━╯</b>

<b>       ✦ 𝙎𝙈𝘼𝙍𝙏 𝙏𝘼𝙂 𝘽𝙊𝙏 ✦</b>

<b>╭────────────────────╮</b>
<b>│ ✈️ 𝙁𝙪𝙣 𝘾𝙤𝙣𝙫𝙚𝙧𝙨𝙖𝙩𝙞𝙤𝙣𝙨</b>
<b>│ 🥳 𝙂𝙧𝙤𝙪𝙥𝙨 & 𝙋𝙧𝙞𝙫𝙖𝙩𝙚</b>
<b>│ 🌈 𝘼𝙘𝙩𝙞𝙫𝙚 + 𝙁𝙪𝙣 𝘾𝙝𝙖𝙩𝙨</b>
<b>│ ⚡ 𝙋𝙧𝙚𝙢𝙞𝙪𝙢 𝙏𝙖𝙜 𝙎𝙮𝙨𝙩𝙚𝙢</b>
<b>│ 🌸 𝙎𝙩𝙮𝙡𝙞𝙨𝙝 & 𝙎𝙢𝙤𝙤𝙩𝙝</b>
<b>│ 🎭 𝙂𝙖𝙢𝙚𝙨 · 𝙁𝙪𝙣 𝙏𝙤𝙤𝙡𝙨</b>
<b>│ 🔮 𝘼𝙣𝙞𝙢𝙚 & 𝘼𝙚𝙨𝙩𝙝𝙚𝙩𝙞𝙘</b>
<b>╰────────────────────╯</b>

<b>        𓆩♡𓆪 𝘾𝙝𝙤𝙤𝙨𝙚 𝘽𝙚𝙡𝙤𝙬</b>"""


# =========================================================
# OWNER PANEL
# =========================================================

OWNER_TEXT = """<b>🌟 PREMIUM OWNER PANEL 🌟</b>

<b>👑 Meet The Master Behind This Bot 👑</b>
<b>——————————————</b>

<b>Name:</b> - <b>𝘽𝘼𝘿𝙉𝘼𝙈 ⚡️</b>

<b>Role:</b> <b>Bot Developer & Owner</b>
<b>Power:</b> <b>⚡ Full Access</b>

<b>——————————————</b>

<b>✨ This bot exists because of his
skills & creativity.</b>

<b>🔥 All premium features, tag systems
& automation flows are crafted by him.</b>

<b>🌸 Aesthetic Mind · Smart Developer ·
Friendly Personality</b>

<b>💬 You can contact him for support or
collaborations.</b>

<b>🪄 “Behind every smooth bot… there
is a sleepless owner.”</b>"""


# =========================================================
# MAIN KEYBOARD
# =========================================================

def main_kb():
    return InlineKeyboardMarkup([

        [
            InlineKeyboardButton(
                "💗  𝘼𝘿𝘿 𝙈𝙀 𝙏𝙊 𝙂𝙍𝙊𝙐𝙋  ＋",
                url=f"https://t.me/{BOT_USERNAME}?startgroup=true"
            )
        ],

        [
            InlineKeyboardButton(
                "🥳  𝘾𝙊𝙐𝙋𝙇𝙀𝙎",
                callback_data="couples"
            ),
            InlineKeyboardButton(
                "😎  𝙂𝘼𝙈𝙀",
                callback_data="games"
            )
        ],

        [
            InlineKeyboardButton(
                "✈️  𝙃𝙀𝙇𝙋 & 𝘾𝙊𝙈𝙈𝘼𝙉𝘿𝙎",
                callback_data="help"
            )
        ],

        [
            InlineKeyboardButton(
                "👑  𝙊𝙒𝙉𝙀𝙍 𝙋𝘼𝙉𝙀𝙇",
                callback_data="owner"
            )
        ],

        [
            InlineKeyboardButton(
                "🔮  𝙎𝙐𝙋𝙋𝙊𝙍𝙏 ↗",
                url=SUPPORT_URL
            ),
            InlineKeyboardButton(
                "☁️  𝙐𝙋𝘿𝘼𝙏𝙀𝙎 ↗",
                url=UPDATE_URL
            )
        ],
    ])


# =========================================================
# OWNER KEYBOARD
# =========================================================

def owner_kb():
    return InlineKeyboardMarkup([

        [
            InlineKeyboardButton(
                "👑  𝘾𝙊𝙉𝙏𝘼𝘾𝙏 𝙊𝙒𝙉𝙀𝙍 ↗",
                url=OWNER_URL
            )
        ],

        [
            InlineKeyboardButton(
                "⌂  𝘽𝘼𝘾𝙆 𝙏𝙊 𝙎𝙏𝘼𝙍𝙏",
                callback_data="home"
            )
        ],
    ])


# =========================================================
# HELP
# =========================================================

HELP = """<b>╭━━━━━━━━━━━━━━━━━━━━╮</b>
<b>       🌈 𝙃𝙀𝙇𝙋 𝘾𝙀𝙉𝙏𝙀𝙍</b>
<b>╰━━━━━━━━━━━━━━━━━━━━╯</b>

<b>✦ 𝙎𝙀𝙇𝙀𝘾𝙏 𝘼 𝘾𝘼𝙏𝙀𝙂𝙊𝙍𝙔 ✦</b>

<i>Choose a section below to explore
all available commands.</i>"""


def help_kb():
    return InlineKeyboardMarkup([

        [
            InlineKeyboardButton(
                "✈️  𝙏𝘼𝙂 𝙎𝙔𝙎𝙏𝙀𝙈",
                callback_data="tag"
            ),
            InlineKeyboardButton(
                "🥳  𝘾𝙊𝙐𝙋𝙇𝙀𝙎",
                callback_data="couples"
            )
        ],

        [
            InlineKeyboardButton(
                "😎  𝙂𝘼𝙈𝙀𝙎",
                callback_data="games"
            ),
            InlineKeyboardButton(
                "🌈  𝙐𝙎𝙀𝙍 𝙏𝙊𝙊𝙇𝙎",
                callback_data="tools"
            )
        ],

        [
            InlineKeyboardButton(
                "🔵  𝙒𝙀𝙇𝘾𝙊𝙈𝙀",
                callback_data="welcome"
            )
        ],

        [
            InlineKeyboardButton(
                "⚠️  𝙎𝙀𝘾𝙐𝙍𝙄𝙏𝙔 𝙂𝙐𝘼𝙍𝘿",
                callback_data="security"
            )
        ],

        [
            InlineKeyboardButton(
                "🌈  𝘽𝘼𝘾𝙆 𝙏𝙊 𝙎𝙏𝘼𝙍𝙏",
                callback_data="home"
            )
        ],
    ])


# =========================================================
# HELP PAGES
# =========================================================

PAGES = {

    "tag": """<b>✈️ 𝙏𝘼𝙂 𝙎𝙔𝙎𝙏𝙀𝙈</b>

<b>𝙂𝙍𝙊𝙐𝙋 𝘾𝙊𝙈𝙈𝘼𝙉𝘿𝙎</b>

• <code>/tagall</code> — 𝙩𝙖𝙜 𝙖𝙘𝙩𝙞𝙫𝙚 𝙢𝙚𝙢𝙗𝙚𝙧𝙨
• <code>/tagadmins</code> — 𝙩𝙖𝙜 𝙜𝙧𝙤𝙪𝙥 𝙖𝙙𝙢𝙞𝙣𝙨
• <code>/cancel</code> — 𝙨𝙩𝙤𝙥 𝙩𝙖𝙜𝙜𝙞𝙣𝙜
• <code>/tagdelay 2</code> — 𝙨𝙚𝙩 𝙙𝙚𝙡𝙖𝙮

<i>Only users seen by the bot can be tagged.</i>""",

    "couples": """<b>🥳 𝘾𝙊𝙐𝙋𝙇𝙀𝙎 𝙎𝙔𝙎𝙏𝙀𝙈</b>

• <code>/couple</code> — 𝙧𝙖𝙣𝙙𝙤𝙢 𝙘𝙤𝙪𝙥𝙡𝙚
• <code>/setcouple</code> — 𝙥𝙖𝙞𝙧 𝙧𝙚𝙥𝙡𝙞𝙚𝙙 𝙪𝙨𝙚𝙧
• <code>/mycouple</code> — 𝙨𝙝𝙤𝙬 𝙘𝙤𝙪𝙥𝙡𝙚
• <code>/delcouple</code> — 𝙧𝙚𝙢𝙤𝙫𝙚 𝙘𝙤𝙪𝙥𝙡𝙚
• <code>/ship</code> — 𝙘𝙤𝙢𝙥𝙖𝙩𝙞𝙗𝙞𝙡𝙞𝙩𝙮""",

    "games": """<b>😎 𝙂𝘼𝙈𝙀𝙎 & 𝘼𝘾𝙏𝙄𝙑𝙄𝙏𝙄𝙀𝙎</b>

🎲 <code>/dice</code> — 𝙧𝙤𝙡𝙡 𝙙𝙞𝙘𝙚
🪙 <code>/coin</code> — 𝙝𝙚𝙖𝙙𝙨 / 𝙩𝙖𝙞𝙡𝙨
💭 <code>/truth</code> — 𝙩𝙧𝙪𝙩𝙝
🔥 <code>/dare</code> — 𝙙𝙖𝙧𝙚
💘 <code>/ship</code> — 𝙨𝙝𝙞𝙥
🎱 <code>/8ball</code> — 𝙢𝙖𝙜𝙞𝙘 8-ball""",

    "tools": """<b>🌈 𝙐𝙎𝙀𝙍 𝙏𝙊𝙊𝙇𝙎</b>

👤 <code>/id</code> — 𝙪𝙨𝙚𝙧 / 𝙘𝙝𝙖𝙩 𝙄𝘿
🌸 <code>/info</code> — 𝙪𝙨𝙚𝙧 𝙞𝙣𝙛𝙤
⚡ <code>/ping</code> — 𝙗𝙤𝙩 𝙨𝙩𝙖𝙩𝙪𝙨
🏠 <code>/start</code> — 𝙢𝙖𝙞𝙣 𝙢𝙚𝙣𝙪
✈️ <code>/help</code> — 𝙝𝙚𝙡𝙥 𝙘𝙚𝙣𝙩𝙚𝙧""",

    "welcome": """<b>🔵 𝙒𝙀𝙇𝘾𝙊𝙈𝙀 𝙎𝙔𝙎𝙏𝙀𝙈</b>

• <code>/setwelcome TEXT</code>
• <code>/delwelcome</code>
• <code>/welcome</code>

<b>𝙑𝘼𝙍𝙄𝘼𝘽𝙇𝙀𝙎</b>

<code>{name}</code>
<code>{mention}</code>
<code>{title}</code>""",

    "security": """<b>⚠️ 𝙎𝙀𝘾𝙐𝙍𝙄𝙏𝙔 𝙂𝙐𝘼𝙍𝘿</b>

🛡️ <code>/antispam on</code>
🛡️ <code>/antispam off</code>
🔒 <code>/lock links</code>
🔓 <code>/unlock links</code>

<i>Security commands require group-admin rights.</i>"""
}


# =========================================================
# START COMMAND
# =========================================================

async def start(update, context):

    if not update.message:
        return

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

    query = update.callback_query

    if not query:
        return

    try:
        await query.answer()
    except Exception:
        pass

    data = query.data

    # OWNER
    if data == "owner":

        text = OWNER_TEXT
        keyboard = owner_kb()

    # HOME
    elif data == "home":

        text = START
        keyboard = main_kb()

    # HELP
    elif data == "help":

        text = HELP
        keyboard = help_kb()

    # PAGES
    elif data in PAGES:

        text = PAGES[data]
        keyboard = help_kb()

    else:
        return

    # If start is a photo
    if query.message and query.message.photo:

        try:
            await query.edit_message_caption(
                caption=text,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard,
            )
            return

        except Exception as e:
            log.warning(
                "Caption edit failed: %s",
                e
            )

    # Normal text message
    try:

        await query.edit_message_text(
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
            disable_web_page_preview=True,
        )

    except Exception as e:

        log.warning(
            "Button edit failed: %s",
            e
        )


# =========================================================
# REMEMBER USERS
# =========================================================

async def remember(update, context):

    user = update.effective_user
    chat = update.effective_chat

    if not user or not chat:
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
            chat.id,
            user.id,
            user.full_name,
            user.username,
            int(time.time()),
        ),
    )


async def track_message(update, context):
    await remember(update, context)


# =========================================================
# ID COMMAND
# =========================================================

async def id_cmd(update, context):

    target = update.effective_user

    if update.message.reply_to_message:
        target = update.message.reply_to_message.from_user

    await update.message.reply_text(
        f"""<b>👤 𝙐𝙎𝙀𝙍</b>

<b>👤 {mention(target.id,target.full_name)}</b>

<b>🆔 𝙐𝙨𝙚𝙧 𝙄𝘿:</b>
<code>{target.id}</code>

<b>💬 𝘾𝙝𝙖𝙩 𝙄𝘿:</b>
<code>{update.effective_chat.id}</code>""",
        parse_mode=ParseMode.HTML,
    )


# =========================================================
# INFO
# =========================================================

async def info_cmd(update, context):

    user = (
        update.message.reply_to_message.from_user
        if update.message.reply_to_message
        else update.effective_user
    )

    username = (
        f"@{escape(user.username)}"
        if user.username
        else "No username"
    )

    await update.message.reply_text(
        f"""<b>🌸 𝙐𝙎𝙀𝙍 𝙄𝙉𝙁𝙊</b>

<b>👤 {mention(user.id,user.full_name)}</b>

<b>🆔 𝙄𝘿:</b>
<code>{user.id}</code>

<b>🔗 𝙐𝙨𝙚𝙧𝙣𝙖𝙢𝙚:</b>
{username}""",
        parse_mode=ParseMode.HTML,
    )


# =========================================================
# PING
# =========================================================

async def ping(update, context):

    started = time.monotonic()

    message = await update.message.reply_text(
        "✦ <b>𝘾𝙝𝙚𝙘𝙠𝙞𝙣𝙜...</b>",
        parse_mode=ParseMode.HTML,
    )

    ms = int(
        (time.monotonic() - started) * 1000
    )

    await message.edit_text(
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
        await update.effective_chat.get_administrators()
    )

    text = "<b>✈️ 𝙂𝙍𝙊𝙐𝙋 𝘼𝘿𝙈𝙄𝙉𝙎</b>\n\n"

    text += "\n".join(
        f"• {mention(a.user.id,a.user.full_name)}"
        for a in admins_list
    )

    await update.message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
    )


# =========================================================
# TAG DELAY
# =========================================================

async def tagdelay(update, context):

    if not is_group(update):
        return

    if not await is_admin(update):
        return await update.message.reply_text(
            "⚠️ <b>𝘼𝙙𝙢𝙞𝙣𝙨 𝙤𝙣𝙡𝙮.</b>",
            parse_mode=ParseMode.HTML,
        )

    if not context.args:
        return await update.message.reply_text(
            "𝙐𝙨𝙚: <code>/tagdelay 2</code>",
            parse_mode=ParseMode.HTML,
        )

    try:

        delay = float(context.args[0])

        if delay < 0.5 or delay > 30:
            raise ValueError

    except ValueError:

        return await update.message.reply_text(
            "⚠️ 𝘿𝙚𝙡𝙖𝙮 0.5–30 seconds ke beech hona chahiye."
        )

    db(
        """
        INSERT INTO settings(chat_id,tag_delay)
        VALUES(?,?)

        ON CONFLICT(chat_id)
        DO UPDATE SET tag_delay=excluded.tag_delay
        """,
        (
            update.effective_chat.id,
            delay,
        ),
    )

    await update.message.reply_text(
        f"✅ <b>𝙏𝙖𝙜 𝙙𝙚𝙡𝙖𝙮:</b> "
        f"<code>{delay:g}s</code>",
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
            "⚠️ <b>𝙊𝙣𝙡𝙮 𝙜𝙧𝙤𝙪𝙥 𝙖𝙙𝙢𝙞𝙣𝙨 𝙘𝙖𝙣 𝙪𝙨𝙚 /tagall.</b>",
            parse_mode=ParseMode.HTML,
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
        row for row in rows
        if row[0] != update.effective_user.id
    ]

    if not rows:
        return await update.message.reply_text(
            "🌈 <b>I haven't seen enough members yet.</b>",
            parse_mode=ParseMode.HTML,
        )

    setting = db(
        """
        SELECT tag_delay
        FROM settings
        WHERE chat_id=?
        """,
        (update.effective_chat.id,),
        True,
    )

    delay = (
        float(setting[0][0])
        if setting
        and setting[0][0] is not None
        else DEFAULT_TAG_DELAY
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

    for start_index in range(0, len(rows), 8):

        state = db(
            "SELECT active FROM tags WHERE chat_id=?",
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
                mention(uid, name)
                for uid, name in chunk
            ),
            parse_mode=ParseMode.HTML,
        )

        await asyncio.sleep(delay)

    db(
        "UPDATE tags SET active=0 WHERE chat_id=?",
        (update.effective_chat.id,),
    )


# =========================================================
# CANCEL
# =========================================================

async def cancel(update, context):

    if not is_group(update):
        return

    db(
        "UPDATE tags SET active=0 WHERE chat_id=?",
        (update.effective_chat.id,),
    )

    await update.message.reply_text(
        "🛑 <b>𝙏𝙖𝙜𝙜𝙞𝙣𝙜 𝙨𝙩𝙤𝙥𝙥𝙚𝙙.</b>",
        parse_mode=ParseMode.HTML,
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
            "💞 <b>Need at least 2 active members.</b>",
            parse_mode=ParseMode.HTML,
        )

    a, b = rows

    await update.message.reply_text(
        f"""<b>💞 𝙏𝙊𝘿𝘼𝙔'𝙎 𝘾𝙊𝙐𝙋𝙇𝙀</b>

<b>{mention(a[0],a[1])}</b>  💗  <b>{mention(b[0],b[1])}</b>""",
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
            "💗 <b>Reply to a user with /setcouple</b>",
            parse_mode=ParseMode.HTML,
        )

    a = update.effective_user
    b = update.message.reply_to_message.from_user

    db(
        "INSERT OR REPLACE INTO couples VALUES(?,?,?)",
        (
            update.effective_chat.id,
            a.id,
            b.id,
        ),
    )

    db(
        "INSERT OR REPLACE INTO couples VALUES(?,?,?)",
        (
            update.effective_chat.id,
            b.id,
            a.id,
        ),
    )

    await update.message.reply_text(
        f"💗 {mention(a.id,a.full_name)} + "
        f"{mention(b.id,b.full_name)}",
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
            "💔 <b>You don't have a couple yet.</b>",
            parse_mode=ParseMode.HTML,
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
        f"💞 <b>Your couple:</b> "
        f"{mention(r[0][0],name)}",
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
        "💔 <b>Couple removed.</b>",
        parse_mode=ParseMode.HTML,
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
            "💗 <b>Not enough active users.</b>",
            parse_mode=ParseMode.HTML,
        )

    score = random.randint(0, 100)

    await update.message.reply_text(
        f"""💘 <b>{mention(rows[0][0],rows[0][1])}</b>
×
<b>{mention(rows[1][0],rows[1][1])}</b>

<b>Compatibility: {score}%</b> 💞""",
        parse_mode=ParseMode.HTML,
    )


# =========================================================
# GAMES
# =========================================================

async def dice(update, context):

    await update.message.reply_text(
        f"🎲 <b>You rolled:</b> "
        f"<b>{random.randint(1,6)}</b>",
        parse_mode=ParseMode.HTML,
    )


async def coin(update, context):

    await update.message.reply_text(
        f"🪙 <b>{random.choice(['Heads','Tails'])}</b>",
        parse_mode=ParseMode.HTML,
    )


TRUTHS = [
    "Who was your last crush?",
    "What is your biggest secret?",
    "Who do you text the most?",
]

DARES = [
    "Send a funny sticker.",
    "Change your profile bio for 5 minutes.",
    "Compliment someone in this group.",
]

ANS = [
    "Yes.",
    "No.",
    "Maybe.",
    "Definitely!",
    "Ask again later.",
    "The signs say yes.",
]


async def truth(update, context):

    await update.message.reply_text(
        "💭 <b>Truth:</b> " + random.choice(TRUTHS),
        parse_mode=ParseMode.HTML,
    )


async def dare(update, context):

    await update.message.reply_text(
        "🔥 <b>Dare:</b> " + random.choice(DARES),
        parse_mode=ParseMode.HTML,
    )


async def ball(update, context):

    await update.message.reply_text(
        "🎱 <b>" + random.choice(ANS) + "</b>",
        parse_mode=ParseMode.HTML,
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
            "🔵 <b>Welcome system is ON.</b>\n"
            "<i>No custom text set.</i>",
            parse_mode=ParseMode.HTML,
        )

    await update.message.reply_text(
        f"<b>🔵 Welcome:</b>\n"
        f"{escape(r[0][0] or 'Default welcome')}",
        parse_mode=ParseMode.HTML,
    )


async def setwelcome(update, context):

    if (
        not is_group(update)
        or not await is_admin(update)
    ):
        return await update.message.reply_text(
            "⚠️ <b>Admins only.</b>",
            parse_mode=ParseMode.HTML,
        )

    text = update.message.text.partition(" ")[2].strip()

    if not text:
        return await update.message.reply_text(
            "Use:\n"
            "<code>/setwelcome Welcome {mention} to {title}</code>",
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
        "✅ <b>Welcome message saved.</b>",
        parse_mode=ParseMode.HTML,
    )


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
        "🗑️ <b>Custom welcome removed.</b>",
        parse_mode=ParseMode.HTML,
    )


async def new_member(update, context):

    if not update.chat_member:
        return

    cm = update.chat_member

    if cm.new_chat_member.status not in (
        ChatMemberStatus.MEMBER,
        ChatMemberStatus.RESTRICTED,
    ):
        return

    user = cm.new_chat_member.user
    chat = cm.chat

    r = db(
        """
        SELECT welcome,welcome_enabled
        FROM settings
        WHERE chat_id=?
        """,
        (chat.id,),
        True,
    )

    text = (
        r[0][0]
        if r and r[0][1]
        else "🌸 Welcome {mention} to <b>{title}</b>!"
    )

    text = text.replace(
        "{name}",
        escape(user.full_name)
    )

    text = text.replace(
        "{mention}",
        mention(user.id,user.full_name)
    )

    text = text.replace(
        "{title}",
        escape(chat.title or "our group")
    )

    await context.bot.send_message(
        chat.id,
        text,
        parse_mode=ParseMode.HTML,
    )


# =========================================================
# SECURITY
# =========================================================

async def antispam(update, context):

    if not await is_admin(update):
        return await update.message.reply_text(
            "⚠️ <b>Admins only.</b>",
            parse_mode=ParseMode.HTML,
        )

    arg = (
        context.args[0].lower()
        if context.args
        else ""
    )

    if arg not in ("on", "off"):
        return await update.message.reply_text(
            "Use <code>/antispam on</code> "
            "or <code>/antispam off</code>",
            parse_mode=ParseMode.HTML,
        )

    enabled = 1 if arg == "on" else 0

    db(
        """
        INSERT INTO settings(chat_id,antispam)
        VALUES(?,?)

        ON CONFLICT(chat_id)
        DO UPDATE SET antispam=excluded.antispam
        """,
        (
            update.effective_chat.id,
            enabled,
        ),
    )

    await update.message.reply_text(
        f"🛡️ <b>Anti-spam "
        f"{'enabled' if enabled else 'disabled'}.</b>",
        parse_mode=ParseMode.HTML,
    )


async def lock(update, context):

    if not await is_admin
