import os
import random
import sqlite3
import logging
import time
import asyncio
from html import escape
from contextlib import closing

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    BotCommand,
)
from telegram.constants import ParseMode, ChatMemberStatus
from telegram.error import BadRequest, Forbidden, TelegramError
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ChatMemberHandler,
    ContextTypes,
    filters,
)

# =========================================================
# CONFIG
# =========================================================

TOKEN = os.getenv("BOT_TOKEN")
BOT_USERNAME = os.getenv("BOT_USERNAME", "").lstrip("@")

SUPPORT_URL = os.getenv("SUPPORT_URL", "https://t.me/")
UPDATE_URL = os.getenv("UPDATE_URL", "https://t.me/")
OWNER_URL = os.getenv("OWNER_URL", "https://t.me/")
START_IMAGE = os.getenv("START_IMAGE", "")
OWNER_CHAT_ID = os.getenv("OWNER_CHAT_ID")

DB = os.getenv("DB_PATH", "alltegbot.db")
DEFAULT_TAG_DELAY = 2.0
MAX_TAG_USERS = max(1, min(int(os.getenv("MAX_TAG_USERS", "80")), 200))
TAG_CHUNK_SIZE = max(1, min(int(os.getenv("TAG_CHUNK_SIZE", "8")), 10))

# Anti-spam: delete repeated messages from a user inside this window.
SPAM_WINDOW = max(1, int(os.getenv("SPAM_WINDOW", "8")))
SPAM_MAX_MESSAGES = max(2, int(os.getenv("SPAM_MAX_MESSAGES", "6")))

if not TOKEN:
    raise RuntimeError("BOT_TOKEN is missing")

# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("alltegbot")

# =========================================================
# DATABASE
# =========================================================

conn = sqlite3.connect(DB, check_same_thread=False, timeout=30)
conn.row_factory = sqlite3.Row
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA synchronous=NORMAL")
conn.execute("PRAGMA busy_timeout=30000")

conn.executescript(
    """
    CREATE TABLE IF NOT EXISTS users(
        chat_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        name TEXT,
        username TEXT,
        last_seen INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY(chat_id,user_id)
    );

    CREATE TABLE IF NOT EXISTS couples(
        chat_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        partner_id INTEGER NOT NULL,
        PRIMARY KEY(chat_id,user_id)
    );

    CREATE TABLE IF NOT EXISTS settings(
        chat_id INTEGER PRIMARY KEY,
        welcome TEXT,
        welcome_enabled INTEGER NOT NULL DEFAULT 1,
        antispam INTEGER NOT NULL DEFAULT 0,
        tag_delay REAL NOT NULL DEFAULT 2
    );

    CREATE TABLE IF NOT EXISTS tags(
        chat_id INTEGER PRIMARY KEY,
        active INTEGER NOT NULL DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS locks(
        chat_id INTEGER NOT NULL,
        feature TEXT NOT NULL,
        PRIMARY KEY(chat_id,feature)
    );
    """
)
conn.commit()


def db(sql, args=(), fetch=False):
    with closing(conn.cursor()) as cur:
        cur.execute(sql, args)
        if fetch:
            return cur.fetchall()
        conn.commit()
        return None


# =========================================================
# HELPERS
# =========================================================

def mention(user_id, name):
    return f'<a href="tg://user?id={int(user_id)}">{escape(name or "User")}</a>'


def is_group(update: Update):
    return bool(
        update.effective_chat
        and update.effective_chat.type in ("group", "supergroup")
    )


async def is_admin(update: Update, user_id=None):
    if not update.effective_chat:
        return False
    uid = user_id or (update.effective_user.id if update.effective_user else None)
    if uid is None:
        return False
    try:
        member = await update.effective_chat.get_member(uid)
        return member.status in (
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER,
        )
    except TelegramError:
        return False


async def require_group_admin(update: Update):
    if not is_group(update):
        if update.effective_message:
            await update.effective_message.reply_text(
                "⚠️ This command works only in groups."
            )
        return False
    if not await is_admin(update):
        if update.effective_message:
            await update.effective_message.reply_text(
                "⚠️ <b>Admins only.</b>", parse_mode=ParseMode.HTML
            )
        return False
    return True


def ensure_settings(chat_id):
    db(
        "INSERT OR IGNORE INTO settings(chat_id) VALUES(?)",
        (chat_id,),
    )


def get_tag_delay(chat_id):
    row = db(
        "SELECT tag_delay FROM settings WHERE chat_id=?",
        (chat_id,),
        True,
    )
    if not row or row[0]["tag_delay"] is None:
        return DEFAULT_TAG_DELAY
    return float(row[0]["tag_delay"])


# =========================================================
# START / HELP UI
# =========================================================

START = """<b>╭━━━━━━━━━━━━━━━━━━━━╮</b>
<b>       𓆩♡𓆪 𝙍𝙊𝙔𝘼𝙇 𝙏𝘼𝙂 𝘽𝙊𝙏</b>
<b>╰━━━━━━━━━━━━━━━━━━━━╯</b>

<b>       ✦ 𝙎𝙈𝘼𝙍𝙏 𝙏𝘼𝙂 𝙎𝙔𝙎𝙏𝙀𝙈 ✦</b>

<b>╭────────────────────╮</b>
<b>│ ✈️ 𝙏𝙖𝙜 & 𝙜𝙧𝙤𝙪𝙥 𝙩𝙤𝙤𝙡𝙨</b>
<b>│ 💞 𝘾𝙤𝙪𝙥𝙡𝙚 & 𝙨𝙝𝙞𝙥</b>
<b>│ 🎭 𝙂𝙖𝙢𝙚𝙨 & 𝙛𝙪𝙣</b>
<b>│ 👋 𝙒𝙚𝙡𝙘𝙤𝙢𝙚</b>
<b>│ 🛡️ 𝙎𝙚𝙘𝙪𝙧𝙞𝙩𝙮</b>
<b>╰────────────────────╯</b>

<b>𓆩♡𓆪 Choose a section below</b>"""

OWNER_TEXT = """<b>🌟 𝙊𝙒𝙉𝙀𝙍 𝙋𝘼𝙉𝙀𝙇 🌟</b>

<b>👑 Bot Owner / Developer</b>

Use the button below to contact the owner.
"""

HELP = """<b>╭━━━━━━━━━━━━━━━━━━━━╮</b>
<b>       🌈 𝙃𝙀𝙇𝙋 𝘾𝙀𝙉𝙏𝙀𝙍</b>
<b>╰━━━━━━━━━━━━━━━━━━━━╯</b>

<i>Select a category to see commands.</i>"""

PAGES = {
    "tag": """<b>✈️ 𝙏𝘼𝙂 𝙎𝙔𝙎𝙏𝙀𝙈</b>

• <code>/tagall</code> — tag remembered active members
• <code>/tagadmins</code> — tag current group admins
• <code>/cancel</code> — stop an active tag
• <code>/tagdelay 2</code> — set delay (0.5–30s)

<i>Telegram does not provide bots a full member list. The bot can tag members it has seen.</i>""",
    "couples": """<b>🥳 𝘾𝙊𝙐𝙋𝙇𝙀 𝙎𝙔𝙎𝙏𝙀𝙈</b>

• <code>/couple</code> — random couple
• <code>/setcouple</code> — pair the replied user
• <code>/mycouple</code> — show your couple
• <code>/delcouple</code> — remove your couple
• <code>/ship</code> — compatibility score""",
    "games": """<b>😎 𝙂𝘼𝙈𝙀𝙎</b>

🎲 <code>/dice</code> — roll dice
🪙 <code>/coin</code> — heads/tails
💭 <code>/truth</code> — truth
🔥 <code>/dare</code> — dare
💘 <code>/ship</code> — compatibility
🎱 <code>/8ball</code> — magic 8-ball""",
    "tools": """<b>🌈 𝙐𝙎𝙀𝙍 𝙏𝙊𝙊𝙇𝙎</b>

👤 <code>/id</code> — user/chat ID
🌸 <code>/info</code> — user information
⚡ <code>/ping</code> — bot status
👮 <code>/admins</code> — group admins""",
    "welcome": """<b>🔵 𝙒𝙀𝙇𝘾𝙊𝙈𝙀</b>

• <code>/setwelcome TEXT</code>
• <code>/delwelcome</code>
• <code>/welcome</code>

Variables:
<code>{name}</code> <code>{mention}</code> <code>{title}</code>""",
    "security": """<b>⚠️ 𝙎𝙀𝘾𝙐𝙍𝙄𝙏𝙔</b>

• <code>/antispam on</code>
• <code>/antispam off</code>
• <code>/lock links</code>
• <code>/unlock links</code>

<i>The bot must be an administrator for deletion-based protection.</i>""",
}


def main_kb():
    add_url = (
        f"https://t.me/{BOT_USERNAME}?startgroup=true"
        if BOT_USERNAME
        else "https://t.me/"
    )
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💗 𝘼𝘿𝘿 𝙈𝙀 𝙏𝙊 𝙂𝙍𝙊𝙐𝙋 ＋", url=add_url)],
        [
            InlineKeyboardButton("🥳 𝘾𝙊𝙐𝙋𝙇𝙀𝙎", callback_data="couples"),
            InlineKeyboardButton("😎 𝙂𝘼𝙈𝙀𝙎", callback_data="games"),
        ],
        [InlineKeyboardButton("✈️ 𝙃𝙀𝙇𝙋 & 𝘾𝙊𝙈𝙈𝘼𝙉𝘿𝙎", callback_data="help")],
        [InlineKeyboardButton("👑 𝙊𝙒𝙉𝙀𝙍 𝙋𝘼𝙉𝙀𝙇", callback_data="owner")],
        [
            InlineKeyboardButton("🔮 𝙎𝙐𝙋𝙋𝙊𝙍𝙏 ↗", url=SUPPORT_URL),
            InlineKeyboardButton("☁️ 𝙐𝙋𝘿𝘼𝙏𝙀𝙎 ↗", url=UPDATE_URL),
        ],
    ])


def owner_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👑 𝘾𝙊𝙉𝙏𝘼𝘾𝙏 𝙊𝙒𝙉𝙀𝙍 ↗", url=OWNER_URL)],
        [InlineKeyboardButton("⌂ 𝘽𝘼𝘾𝙆", callback_data="home")],
    ])


def help_kb():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✈️ 𝙏𝘼𝙂", callback_data="tag"),
            InlineKeyboardButton("🥳 𝘾𝙊𝙐𝙋𝙇𝙀𝙎", callback_data="couples"),
        ],
        [
            InlineKeyboardButton("😎 𝙂𝘼𝙈𝙀𝙎", callback_data="games"),
            InlineKeyboardButton("🌈 𝙏𝙊𝙊𝙇𝙎", callback_data="tools"),
        ],
        [InlineKeyboardButton("🔵 𝙒𝙀𝙇𝘾𝙊𝙈𝙀", callback_data="welcome")],
        [InlineKeyboardButton("⚠️ 𝙎𝙀𝘾𝙐𝙍𝙄𝙏𝙔", callback_data="security")],
        [InlineKeyboardButton("🌈 𝘽𝘼𝘾𝙆", callback_data="home")],
    ])


# =========================================================
# START / BUTTONS
# =========================================================

async def notify_owner_new_start(update, context):
    if not OWNER_CHAT_ID or not update.effective_user:
        return
    try:
        if int(OWNER_CHAT_ID) == update.effective_user.id:
            return
    except (TypeError, ValueError):
        return

    user = update.effective_user
    chat = update.effective_chat
    chat_text = f"\n<b>💬 Chat:</b> {escape(chat.title)}" if chat and chat.title else ""
    username = f"@{escape(user.username)}" if user.username else "No username"

    text = (
        "<b>🔔 NEW BOT START</b>\n\n"
        f"<b>👤 User:</b> {mention(user.id, user.full_name)}\n"
        f"<b>🆔 ID:</b> <code>{user.id}</code>\n"
        f"<b>🔗 Username:</b> {username}{chat_text}"
    )
    try:
        await context.bot.send_message(
            chat_id=int(OWNER_CHAT_ID),
            text=text,
            parse_mode=ParseMode.HTML,
        )
    except TelegramError:
        log.exception("Owner notification failed")


async def start(update, context):
    if not update.message:
        return
    await notify_owner_new_start(update, context)

    if START_IMAGE:
        try:
            await update.message.reply_photo(
                START_IMAGE,
                caption=START,
                parse_mode=ParseMode.HTML,
                reply_markup=main_kb(),
            )
            return
        except TelegramError:
            log.warning("START_IMAGE failed; using text", exc_info=True)

    await update.message.reply_text(
        START,
        parse_mode=ParseMode.HTML,
        reply_markup=main_kb(),
        disable_web_page_preview=True,
    )


async def help_cmd(update, context):
    await update.message.reply_text(
        HELP, parse_mode=ParseMode.HTML, reply_markup=help_kb()
    )


async def buttons(update, context):
    query = update.callback_query
    if not query:
        return
    try:
        await query.answer()
    except TelegramError:
        pass

    data = query.data
    if data == "home":
        text, keyboard = START, main_kb()
    elif data == "help":
        text, keyboard = HELP, help_kb()
    elif data == "owner":
        text, keyboard = OWNER_TEXT, owner_kb()
    elif data in PAGES:
        text, keyboard = PAGES[data], help_kb()
    else:
        return

    try:
        if query.message and query.message.photo:
            await query.edit_message_caption(
                caption=text,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard,
            )
        else:
            await query.edit_message_text(
                text=text,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard,
                disable_web_page_preview=True,
            )
    except BadRequest as e:
        if "Message is not modified" not in str(e):
            log.warning("Button edit failed: %s", e)


# =========================================================
# USER TRACKING
# =========================================================

async def remember(update, context):
    user = update.effective_user
    chat = update.effective_chat
    if not user or not chat:
        return
    db(
        """
        INSERT INTO users(chat_id,user_id,name,username,last_seen)
        VALUES(?,?,?,?,?)
        ON CONFLICT(chat_id,user_id) DO UPDATE SET
          name=excluded.name,
          username=excluded.username,
          last_seen=excluded.last_seen
        """,
        (chat.id, user.id, user.full_name, user.username, int(time.time())),
    )


async def track_message(update, context):
    await remember(update, context)


# =========================================================
# BASIC COMMANDS
# =========================================================

async def id_cmd(update, context):
    target = update.effective_user
    if update.message.reply_to_message and update.message.reply_to_message.from_user:
        target = update.message.reply_to_message.from_user

    await update.message.reply_text(
        f"<b>👤 {mention(target.id, target.full_name)}</b>\n\n"
        f"<b>🆔 User ID:</b> <code>{target.id}</code>\n"
        f"<b>💬 Chat ID:</b> <code>{update.effective_chat.id}</code>",
        parse_mode=ParseMode.HTML,
    )


async def info_cmd(update, context):
    user = (
        update.message.reply_to_message.from_user
        if update.message.reply_to_message and update.message.reply_to_message.from_user
        else update.effective_user
    )
    username = f"@{escape(user.username)}" if user.username else "No username"
    await update.message.reply_text(
        f"<b>🌸 USER INFO</b>\n\n"
        f"👤 {mention(user.id, user.full_name)}\n"
        f"🆔 <code>{user.id}</code>\n"
        f"🔗 {username}",
        parse_mode=ParseMode.HTML,
    )


async def ping(update, context):
    started = time.monotonic()
    msg = await update.message.reply_text("✦ <b>Checking...</b>", parse_mode=ParseMode.HTML)
    ms = int((time.monotonic() - started) * 1000)
    await msg.edit_text(
        f"✦ <b>Pong!</b> <code>{ms}ms</code> ✨",
        parse_mode=ParseMode.HTML,
    )


async def admins(update, context):
    if not is_group(update):
        return await update.message.reply_text("⚠️ Groups only.")
    try:
        admins_list = await update.effective_chat.get_administrators()
    except TelegramError:
        return await update.message.reply_text("⚠️ I cannot read the admin list.")
    lines = [f"• {mention(a.user.id, a.user.full_name)}" for a in admins_list]
    await update.message.reply_text(
        "<b>✈️ GROUP ADMINS</b>\n\n" + "\n".join(lines),
        parse_mode=ParseMode.HTML,
    )


# =========================================================
# TAGGING
# =========================================================

async def tagdelay(update, context):
    if not await require_group_admin(update):
        return
    if not context.args:
        return await update.message.reply_text("Use: <code>/tagdelay 2</code>", parse_mode=ParseMode.HTML)
    try:
        delay = float(context.args[0])
        if not 0.5 <= delay <= 30:
            raise ValueError
    except ValueError:
        return await update.message.reply_text(
            "⚠️ Delay must be between 0.5 and 30 seconds."
        )

    db(
        """
        INSERT INTO settings(chat_id,tag_delay) VALUES(?,?)
        ON CONFLICT(chat_id) DO UPDATE SET tag_delay=excluded.tag_delay
        """,
        (update.effective_chat.id, delay),
    )
    await update.message.reply_text(
        f"✅ Tag delay set to <code>{delay:g}s</code>.",
        parse_mode=ParseMode.HTML,
    )


def set_tag_active(chat_id, active):
    db(
        """
        INSERT INTO tags(chat_id,active) VALUES(?,?)
        ON CONFLICT(chat_id) DO UPDATE SET active=excluded.active
        """,
        (chat_id, 1 if active else 0),
    )


def tag_is_active(chat_id):
    row = db("SELECT active FROM tags WHERE chat_id=?", (chat_id,), True)
    return bool(row and row[0]["active"])


async def send_tag_chunks(message, rows, delay, prefix="✈️"):
    chat_id = message.chat_id
    set_tag_active(chat_id, True)
    try:
        for start_index in range(0, len(rows), TAG_CHUNK_SIZE):
            if not tag_is_active(chat_id):
                break
            chunk = rows[start_index:start_index + TAG_CHUNK_SIZE]
            await message.reply_text(
                prefix + " " + " ".join(mention(r["user_id"], r["name"]) for r in chunk),
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
            if start_index + TAG_CHUNK_SIZE < len(rows):
                await asyncio.sleep(delay)
    finally:
        set_tag_active(chat_id, False)


async def tagall(update, context):
    if not await require_group_admin(update):
        return

    rows = db(
        """
        SELECT user_id,name FROM users
        WHERE chat_id=?
        ORDER BY last_seen DESC
        LIMIT ?
        """,
        (update.effective_chat.id, MAX_TAG_USERS),
        True,
    )
    rows = [r for r in rows if r["user_id"] != update.effective_user.id]

    if not rows:
        return await update.message.reply_text(
            "🌈 No remembered members yet. Let members send messages first."
        )

    # Prevent two simultaneous /tagall runs.
    if tag_is_active(update.effective_chat.id):
        return await update.message.reply_text(
            "⏳ A tag is already running. Use /cancel first."
        )

    await send_tag_chunks(update.message, rows, get_tag_delay(update.effective_chat.id))


async def tagadmins(update, context):
    if not await require_group_admin(update):
        return

    if tag_is_active(update.effective_chat.id):
        return await update.message.reply_text("⏳ A tag is already running. Use /cancel first.")

    try:
        admins_list = await update.effective_chat.get_administrators()
    except TelegramError:
        return await update.message.reply_text("⚠️ I cannot read the admin list.")

    rows = [
        {"user_id": a.user.id, "name": a.user.full_name}
        for a in admins_list
        if not a.user.is_bot
    ]
    if not rows:
        return await update.message.reply_text("No taggable admins found.")

    await send_tag_chunks(update.message, rows, get_tag_delay(update.effective_chat.id), prefix="👮")


async def cancel(update, context):
    if not await require_group_admin(update):
        return
    set_tag_active(update.effective_chat.id, False)
    await update.message.reply_text("🛑 <b>Tagging stopped.</b>", parse_mode=ParseMode.HTML)


# =========================================================
# COUPLES
# =========================================================

async def couple(update, context):
    if not is_group(update):
        return
    rows = db(
        """
        SELECT user_id,name FROM users
        WHERE chat_id=? AND user_id != ?
        ORDER BY RANDOM() LIMIT 2
        """,
        (update.effective_chat.id, update.effective_user.id),
        True,
    )
    if len(rows) < 2:
        return await update.message.reply_text("💞 Need at least 2 remembered members.")
    await update.message.reply_text(
        f"<b>💞 TODAY'S COUPLE</b>\n\n"
        f"{mention(rows[0]['user_id'], rows[0]['name'])} 💗 "
        f"{mention(rows[1]['user_id'], rows[1]['name'])}",
        parse_mode=ParseMode.HTML,
    )


async def setcouple(update, context):
    if not is_group(update) or not update.message.reply_to_message:
        return await update.message.reply_text("💗 Reply to a user with /setcouple.")

    a = update.effective_user
    b = update.message.reply_to_message.from_user
    if not b:
        return await update.message.reply_text("⚠️ Target user not found.")
    if a.id == b.id:
        return await update.message.reply_text("😄 You cannot couple yourself.")

    db("INSERT OR REPLACE INTO couples VALUES(?,?,?)", (update.effective_chat.id, a.id, b.id))
    db("INSERT OR REPLACE INTO couples VALUES(?,?,?)", (update.effective_chat.id, b.id, a.id))
    db(
        """
        INSERT INTO users(chat_id,user_id,name,username,last_seen)
        VALUES(?,?,?,?,?)
        ON CONFLICT(chat_id,user_id) DO UPDATE SET
          name=excluded.name, username=excluded.username, last_seen=excluded.last_seen
        """,
        (update.effective_chat.id, b.id, b.full_name, b.username, int(time.time())),
    )
    await update.message.reply_text(
        f"💗 {mention(a.id,a.full_name)} + {mention(b.id,b.full_name)}",
        parse_mode=ParseMode.HTML,
    )


async def mycouple(update, context):
    if not update.effective_chat or not update.effective_user:
        return
    r = db(
        "SELECT partner_id FROM couples WHERE chat_id=? AND user_id=?",
        (update.effective_chat.id, update.effective_user.id),
        True,
    )
    if not r:
        return await update.message.reply_text("💔 You don't have a couple yet.")

    p = db(
        "SELECT name FROM users WHERE chat_id=? AND user_id=?",
        (update.effective_chat.id, r[0]["partner_id"]),
        True,
    )
    name = p[0]["name"] if p else "Your partner"
    await update.message.reply_text(
        f"💞 <b>Your couple:</b> {mention(r[0]['partner_id'], name)}",
        parse_mode=ParseMode.HTML,
    )


async def delcouple(update, context):
    if not update.effective_chat or not update.effective_user:
        return
    r = db(
        "SELECT partner_id FROM couples WHERE chat_id=? AND user_id=?",
        (update.effective_chat.id, update.effective_user.id),
        True,
    )
    db(
        "DELETE FROM couples WHERE chat_id=? AND user_id=?",
        (update.effective_chat.id, update.effective_user.id),
    )
    if r:
        db(
            "DELETE FROM couples WHERE chat_id=? AND user_id=?",
            (update.effective_chat.id, r[0]["partner_id"]),
        )
    await update.message.reply_text("💔 Couple removed.")


async def ship(update, context):
    if not is_group(update):
        return
    rows = db(
        """
        SELECT user_id,name FROM users
        WHERE chat_id=? AND user_id != ?
        ORDER BY RANDOM() LIMIT 2
        """,
        (update.effective_chat.id, update.effective_user.id),
        True,
    )
    if len(rows) < 2:
        return await update.message.reply_text("💗 Not enough remembered members.")

    score = random.randint(0, 100)
    await update.message.reply_text(
        f"💘 {mention(rows[0]['user_id'],rows[0]['name'])}\n"
        f"×\n"
        f"{mention(rows[1]['user_id'],rows[1]['name'])}\n\n"
        f"<b>Compatibility: {score}%</b> 💞",
        parse_mode=ParseMode.HTML,
    )


# =========================================================
# GAMES
# =========================================================

TRUTHS = [
    "Who was your last crush?",
    "What is your biggest secret?",
    "Who do you text the most?",
    "What is one thing you would never tell your friends?",
]
DARES = [
    "Send a funny sticker.",
    "Compliment someone in this group.",
    "Send your next message using only emojis.",
    "Say something nice about the person above.",
]
ANS = ["Yes.", "No.", "Maybe.", "Definitely!", "Ask again later.", "The signs say yes."]


async def dice(update, context):
    await update.message.reply_text(f"🎲 <b>You rolled: {random.randint(1,6)}</b>", parse_mode=ParseMode.HTML)


async def coin(update, context):
    await update.message.reply_text(f"🪙 <b>{random.choice(['Heads','Tails'])}</b>", parse_mode=ParseMode.HTML)


async def truth(update, context):
    await update.message.reply_text("💭 <b>Truth:</b> " + escape(random.choice(TRUTHS)), parse_mode=ParseMode.HTML)


async def dare(update, context):
    await update.message.reply_text("🔥 <b>Dare:</b> " + escape(random.choice(DARES)), parse_mode=ParseMode.HTML)


async def ball(update, context):
    await update.message.reply_text("🎱 <b>" + escape(random.choice(ANS)) + "</b>", parse_mode=ParseMode.HTML)


# =========================================================
# WELCOME
# =========================================================

async def welcome_cmd(update, context):
    if not update.effective_chat:
        return
    ensure_settings(update.effective_chat.id)
    r = db(
        "SELECT welcome,welcome_enabled FROM settings WHERE chat_id=?",
        (update.effective_chat.id,),
        True,
    )
    if not r:
        return await update.message.reply_text("🔵 Welcome system is ON. No custom text set.")

    enabled = bool(r[0]["welcome_enabled"])
    custom = r[0]["welcome"]
    text = custom or "Default welcome"
    await update.message.reply_text(
        f"<b>🔵 Welcome:</b> {'ON' if enabled else 'OFF'}\n{escape(text)}",
        parse_mode=ParseMode.HTML,
    )


async def setwelcome(update, context):
    if not await require_group_admin(update):
        return

    text = update.message.text.partition(" ")[2].strip()
    if not text:
        return await update.message.reply_text(
            "Use:\n<code>/setwelcome Welcome {mention} to {title}</code>",
            parse_mode=ParseMode.HTML,
        )

    db(
        """
        INSERT INTO settings(chat_id,welcome,welcome_enabled)
        VALUES(?,?,1)
        ON CONFLICT(chat_id) DO UPDATE SET
          welcome=excluded.welcome, welcome_enabled=1
        """,
        (update.effective_chat.id, text),
    )
    await update.message.reply_text("✅ <b>Welcome message saved.</b>", parse_mode=ParseMode.HTML)


async def delwelcome(update, context):
    if not await require_group_admin(update):
        return
    db(
        """
        INSERT INTO settings(chat_id,welcome,welcome_enabled)
        VALUES(?,NULL,1)
        ON CONFLICT(chat_id) DO UPDATE SET
          welcome=NULL, welcome_enabled=1
        """,
        (update.effective_chat.id,),
    )
    await update.message.reply_text("🗑️ <b>Custom welcome removed.</b>", parse_mode=ParseMode.HTML)


async def new_member(update, context):
    cm = update.chat_member
    if not cm:
        return

    old = cm.old_chat_member
    new = cm.new_chat_member

    # Only a transition into the member/restricted state counts as a join.
    joined = (
        new.status in (ChatMemberStatus.MEMBER, ChatMemberStatus.RESTRICTED)
        and old.status in (
            ChatMemberStatus.LEFT,
            ChatMemberStatus.KICKED,
        )
    )
    if not joined:
        return

    user = new.user
    chat = cm.chat
    if user.is_bot:
        return

    db(
        """
        INSERT INTO users(chat_id,user_id,name,username,last_seen)
        VALUES(?,?,?,?,?)
        ON CONFLICT(chat_id,user_id) DO UPDATE SET
          name=excluded.name, username=excluded.username, last_seen=excluded.last_seen
        """,
        (chat.id, user.id, user.full_name, user.username, int(time.time())),
    )

    r = db(
        "SELECT welcome,welcome_enabled FROM settings WHERE chat_id=?",
        (chat.id,),
        True,
    )
    if not r or not r[0]["welcome_enabled"]:
        return

    text = r[0]["welcome"] or "🌸 Welcome {mention} to <b>{title}</b>!"
    text = text.replace("{name}", escape(user.full_name))
    text = text.replace("{mention}", mention(user.id, user.full_name))
    text = text.replace("{title}", escape(chat.title or "our group"))

    try:
        await context.bot.send_message(chat.id, text, parse_mode=ParseMode.HTML)
    except TelegramError:
        log.warning("Welcome send failed", exc_info=True)


# =========================================================
# SECURITY
# =========================================================

async def antispam(update, context):
    if not await require_group_admin(update):
        return
    arg = context.args[0].lower() if context.args else ""
    if arg not in ("on", "off"):
        return await update.message.reply_text(
            "Use <code>/antispam on</code> or <code>/antispam off</code>",
            parse_mode=ParseMode.HTML,
        )

    enabled = 1 if arg == "on" else 0
    db(
        """
        INSERT INTO settings(chat_id,antispam) VALUES(?,?)
        ON CONFLICT(chat_id) DO UPDATE SET antispam=excluded.antispam
        """,
        (update.effective_chat.id, enabled),
    )
    await update.message.reply_text(
        f"🛡️ <b>Anti-spam {'enabled' if enabled else 'disabled'}.</b>",
        parse_mode=ParseMode.HTML,
    )


async def lock(update, context):
    if not await require_group_admin(update):
        return
    if not context.args or context.args[0].lower() != "links":
        return await update.message.reply_text("Use <code>/lock links</code>", parse_mode=ParseMode.HTML)
    db(
        "INSERT OR IGNORE INTO locks(chat_id,feature) VALUES(?,?)",
        (update.effective_chat.id, "links"),
    )
    await update.message.reply_text("🔒 <b>Links locked.</b>", parse_mode=ParseMode.HTML)


async def unlock(update, context):
    if not await require_group_admin(update):
        return
    if not context.args or context.args[0].lower() != "links":
        return await update.message.reply_text("Use <code>/unlock links</code>", parse_mode=ParseMode.HTML)
    db(
        "DELETE FROM locks WHERE chat_id=? AND feature=?",
        (update.effective_chat.id, "links"),
    )
    await update.message.reply_text("🔓 <b>Links unlocked.</b>", parse_mode=ParseMode.HTML)


def contains_link(message):
    text = message.text or message.caption or ""
    lowered = text.lower()
    if any(x in lowered for x in ("http://", "https://", "t.me/", "www.")):
        return True

    # Telegram can expose URLs as message entities even when the URL is not
    # literally visible in the text.
    for entities in (message.entities or [], message.caption_entities or []):
        if entities and any(e.type in ("url", "text_link") for e in entities):
            return True
    return False


async def security_guard(update, context):
    message = update.effective_message
    if not message or not is_group(update) or not update.effective_user:
        return
    if update.effective_user.is_bot:
        return

    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    # Link lock
    locked = db(
        "SELECT 1 FROM locks WHERE chat_id=? AND feature='links'",
        (chat_id,),
        True,
    )
    if locked and contains_link(message) and not await is_admin(update):
        try:
            await message.delete()
            return
        except (TelegramError, Forbidden):
            log.debug("Could not delete locked link", exc_info=True)

    # Anti-spam
    setting = db("SELECT antispam FROM settings WHERE chat_id=?", (chat_id,), True)
    if not setting or not setting[0]["antispam"]:
        return
    if await is_admin(update):
        return

    now = time.monotonic()
    key = (chat_id, user_id)
    bucket = context.application.bot_data.setdefault("spam_buckets", {})
    timestamps = bucket.get(key, [])
    timestamps = [t for t in timestamps if now - t <= SPAM_WINDOW]
    timestamps.append(now)
    bucket[key] = timestamps

    if len(timestamps) >= SPAM_MAX_MESSAGES:
        try:
            await message.delete()
        except TelegramError:
            pass
        # Reset after an action so one offender does not trigger every message.
        bucket[key] = []


# =========================================================
# ERRORS / STARTUP
# =========================================================

async def error_handler(update, context):
    log.error(
        "Unhandled exception: %r",
        context.error,
        exc_info=(type(context.error), context.error, context.error.__traceback__)
        if context.error else None,
    )


async def post_init(application):
    commands = [
        ("start", "Main menu"),
        ("help", "Help & commands"),
        ("id", "User/chat ID"),
        ("info", "User information"),
        ("ping", "Bot status"),
        ("admins", "Group admins"),
        ("tagall", "Tag remembered members"),
        ("tagadmins", "Tag group admins"),
        ("cancel", "Stop tagging"),
        ("tagdelay", "Set tag delay"),
        ("couple", "Random couple"),
        ("setcouple", "Set couple by reply"),
        ("mycouple", "Show your couple"),
        ("delcouple", "Remove couple"),
        ("ship", "Compatibility"),
        ("dice", "Roll dice"),
        ("coin", "Heads or tails"),
        ("truth", "Truth"),
        ("dare", "Dare"),
        ("8ball", "Magic 8-ball"),
        ("welcome", "Show welcome"),
        ("setwelcome", "Set welcome"),
        ("delwelcome", "Delete welcome"),
        ("antispam", "Anti-spam on/off"),
        ("lock", "Lock links"),
        ("unlock", "Unlock links"),
    ]
    await application.bot.set_my_commands([BotCommand(a, b) for a, b in commands])
    me = await application.bot.get_me()
    log.info("Logged in as @%s (%s)", me.username, me.id)


def main():
    app = Application.builder().token(TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CallbackQueryHandler(buttons))

    app.add_handler(CommandHandler("id", id_cmd))
    app.add_handler(CommandHandler("info", info_cmd))
    app.add_handler(CommandHandler("ping", ping))
    app.add_handler(CommandHandler("admins", admins))

    app.add_handler(CommandHandler("tagdelay", tagdelay))
    app.add_handler(CommandHandler("tagall", tagall))
    app.add_handler(CommandHandler("tagadmins", tagadmins))
    app.add_handler(CommandHandler("cancel", cancel))

    app.add_handler(CommandHandler("couple", couple))
    app.add_handler(CommandHandler("setcouple", setcouple))
    app.add_handler(CommandHandler("mycouple", mycouple))
    app.add_handler(CommandHandler("delcouple", delcouple))
    app.add_handler(CommandHandler("ship", ship))

    app.add_handler(CommandHandler("dice", dice))
    app.add_handler(CommandHandler("coin", coin))
    app.add_handler(CommandHandler("truth", truth))
    app.add_handler(CommandHandler("dare", dare))
    app.add_handler(CommandHandler("8ball", ball))

    app.add_handler(CommandHandler("welcome", welcome_cmd))
    app.add_handler(CommandHandler("setwelcome", setwelcome))
    app.add_handler(CommandHandler("delwelcome", delwelcome))

    app.add_handler(CommandHandler("antispam", antispam))
    app.add_handler(CommandHandler("lock", lock))
    app.add_handler(CommandHandler("unlock", unlock))

    app.add_handler(
        ChatMemberHandler(new_member, ChatMemberHandler.CHAT_MEMBER)
    )

    # Group 0: remember users before security checks.
    app.add_handler(
        MessageHandler(
            filters.ALL & ~filters.COMMAND,
            track_message,
        ),
        group=0,
    )

    # Group 1: security enforcement.
    app.add_handler(
        MessageHandler(
            filters.ALL & ~filters.COMMAND,
            security_guard,
        ),
        group=1,
    )

    app.add_error_handler(error_handler)

    log.info("Starting ALLTEGBOT...")
    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()
