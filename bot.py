
import os
import random
import sqlite3
import logging
import time
from html import escape

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode, ChatMemberStatus
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, ChatMemberHandler, filters
)

TOKEN = os.getenv("BOT_TOKEN")
BOT_USERNAME = os.getenv("BOT_USERNAME", "mentionmayabot")
SUPPORT_URL = os.getenv("SUPPORT_URL", "https://t.me/annu_support")
UPDATE_URL = os.getenv("UPDATE_URL", "https://t.me/annu_support")

if not TOKEN:
    raise RuntimeError("BOT_TOKEN is missing")

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("maya")

DB = os.getenv("DB_PATH", "maya.db")
conn = sqlite3.connect(DB, check_same_thread=False)
conn.execute("PRAGMA journal_mode=WAL")
cur = conn.cursor()

cur.executescript("""
CREATE TABLE IF NOT EXISTS users(
  chat_id INTEGER, user_id INTEGER, name TEXT, username TEXT,
  last_seen INTEGER, PRIMARY KEY(chat_id,user_id)
);
CREATE TABLE IF NOT EXISTS couples(
  chat_id INTEGER, user_id INTEGER, partner_id INTEGER,
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
  chat_id INTEGER, feature TEXT, PRIMARY KEY(chat_id,feature)
);
""")
conn.commit()

def db(sql, args=(), fetch=False):
    c = conn.cursor()
    c.execute(sql, args)
    if fetch:
        return c.fetchall()
    conn.commit()

def mention(user_id, name):
    return f'<a href="tg://user?id={user_id}">{escape(name or "User")}</a>'

def is_group(update):
    return update.effective_chat and update.effective_chat.type in ("group", "supergroup")

async def is_admin(update, user_id=None):
    uid = user_id or update.effective_user.id
    try:
        m = await update.effective_chat.get_member(uid)
        return m.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)
    except Exception:
        return False

def main_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💗  ADD ME TO YOUR GROUP  ＋",
                              url=f"https://t.me/{BOT_USERNAME}?startgroup=true")],
        [InlineKeyboardButton("🥳  COUPLES", callback_data="couples"),
         InlineKeyboardButton("😎  GAME", callback_data="games")],
        [InlineKeyboardButton("✈️  HELP & COMMANDS", callback_data="help")],
        [InlineKeyboardButton("🔮  SUPPORT  ↗", url=SUPPORT_URL),
         InlineKeyboardButton("☁️  UPDATES  ↗", url=UPDATE_URL)],
    ])

def help_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✈️  TAG SYSTEM", callback_data="tag"),
         InlineKeyboardButton("🥳  COUPLES", callback_data="couples")],
        [InlineKeyboardButton("😎  GAMES", callback_data="games"),
         InlineKeyboardButton("🌈  USER TOOLS", callback_data="tools")],
        [InlineKeyboardButton("🔵  WELCOME", callback_data="welcome")],
        [InlineKeyboardButton("⚠️  SECURITY GUARD", callback_data="security")],
        [InlineKeyboardButton("🌈  BACK TO START", callback_data="home")]
    ])

START = """<b>♡ It's Me — BADNAM !! 🇨🇦 ♡</b>

<b>📌 A Smart Tag-Bot 📌</b>
✈️ <b>Fun</b> Conversations
🥳 <b>Works</b> in Groups & Private
🌈 <b>Keeps</b> Chats Active + Fun
⚠️ <b>Premium</b> Tag System
🌸 <b>Stylish</b> & Smooth
🎭 <b>Games</b> · Fun Tools
🔵 <b>Anime</b> & Aesthetic Themes"""

HELP = """🌈 <b>HELP CENTER — SELECT CATEGORY</b> 🌈

Choose a section below to see all available commands:"""

PAGES = {
"tag": """✈️ <b>TAG SYSTEM</b>

<b>Group commands</b>
• <code>/tagall</code> — tag recently active members
• <code>/tagadmins</code> — tag group admins
• <code>/cancel</code> — stop tagging

<b>Admin</b>
• <code>/tagdelay 2</code> — set delay between tag batches

<i>Only users seen by the bot can be tagged. Telegram bots cannot directly list every group member.</i>""",

"couples": """🥳 <b>COUPLES SYSTEM</b>

• <code>/couple</code> — random couple
• <code>/setcouple</code> — pair yourself with replied user
• <code>/mycouple</code> — show your couple
• <code>/delcouple</code> — remove your couple
• <code>/ship</code> — compatibility game""",

"games": """😎 <b>GAMES & ACTIVITIES</b>

• <code>/dice</code> — roll dice
• <code>/coin</code> — heads or tails
• <code>/truth</code> — truth question
• <code>/dare</code> — dare challenge
• <code>/ship</code> — ship two users
• <code>/8ball</code> — magic 8-ball""",

"tools": """🌈 <b>USER TOOLS</b>

• <code>/id</code> — user/chat ID
• <code>/info</code> — user information
• <code>/ping</code> — bot status
• <code>/start</code> — main menu
• <code>/help</code> — help center""",

"welcome": """🔵 <b>WELCOME SYSTEM</b>

• <code>/setwelcome TEXT</code> — set group welcome
• <code>/delwelcome</code> — remove custom welcome
• <code>/welcome</code> — show current welcome

Variables: <code>{name}</code>, <code>{mention}</code>, <code>{title}</code>""",

"security": """⚠️ <b>SECURITY GUARD</b>

• <code>/antispam on</code> — enable basic anti-spam
• <code>/antispam off</code> — disable it
• <code>/clean</code> — bot command cleanup
• <code>/lock links</code> — lock links
• <code>/unlock links</code> — unlock links

<i>Security commands require group-admin rights.</i>"""
}

async def start(update, context):
    await update.message.reply_text(START, parse_mode=ParseMode.HTML,
                                    reply_markup=main_kb(),
                                    disable_web_page_preview=True)

async def help_cmd(update, context):
    await update.message.reply_text(HELP, parse_mode=ParseMode.HTML,
                                    reply_markup=help_kb())

async def buttons(update, context):
    q = update.callback_query
    await q.answer()
    if q.data == "home":
        await q.edit_message_text(START, parse_mode=ParseMode.HTML, reply_markup=main_kb())
    elif q.data == "help":
        await q.edit_message_text(HELP, parse_mode=ParseMode.HTML, reply_markup=help_kb())
    elif q.data in PAGES:
        await q.edit_message_text(PAGES[q.data], parse_mode=ParseMode.HTML, reply_markup=help_kb())

async def remember(update, context):
    u = update.effective_user
    ch = update.effective_chat
    if not u or not ch:
        return
    db("""INSERT INTO users(chat_id,user_id,name,username,last_seen)
          VALUES(?,?,?,?,?)
          ON CONFLICT(chat_id,user_id) DO UPDATE SET
          name=excluded.name,username=excluded.username,last_seen=excluded.last_seen""",
       (ch.id,u.id,u.full_name,u.username,int(time.time())))

async def track_message(update, context):
    await remember(update, context)

async def id_cmd(update, context):
    u = update.effective_user
    ch = update.effective_chat
    target = u
    if update.message.reply_to_message:
        target = update.message.reply_to_message.from_user
    await update.message.reply_text(
        f"👤 <b>User:</b> {mention(target.id,target.full_name)}\n"
        f"🆔 <b>User ID:</b> <code>{target.id}</code>\n"
        f"💬 <b>Chat ID:</b> <code>{ch.id}</code>",
        parse_mode=ParseMode.HTML)

async def info_cmd(update, context):
    u = update.message.reply_to_message.from_user if update.message.reply_to_message else update.effective_user
    await update.message.reply_text(
        f"🌸 <b>USER INFO</b>\n\n"
        f"👤 {mention(u.id,u.full_name)}\n"
        f"🆔 <code>{u.id}</code>\n"
        f"🔗 @{escape(u.username) if u.username else 'No username'}",
        parse_mode=ParseMode.HTML)

async def ping(update, context):
    t = time.monotonic()
    msg = await update.message.reply_text("✦ Checking...")
    ms = int((time.monotonic()-t)*1000)
    await msg.edit_text(f"✦ <b>Pong!</b>  `{ms}ms` ✨", parse_mode=ParseMode.HTML)

async def admins(update, context):
    if not is_group(update):
        return await update.message.reply_text("This command works in groups.")
    admins_list = await update.effective_chat.get_administrators()
    text = "✈️ <b>GROUP ADMINS</b>\n\n"
    text += "\n".join(f"• {mention(a.user.id,a.user.full_name)}" for a in admins_list)
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def tagall(update, context):
    if not is_group(update):
        return
    if not await is_admin(update):
        return await update.message.reply_text("⚠️ Only group admins can use /tagall.")
    rows = db("""SELECT user_id,name FROM users WHERE chat_id=?
                 ORDER BY last_seen DESC LIMIT 80""",
              (update.effective_chat.id,), True)
    rows = [(i,n) for i,n in rows if i != update.effective_user.id]
    if not rows:
        return await update.message.reply_text("🌈 I haven't seen enough members yet.")
    db("INSERT INTO tags(chat_id,active) VALUES(?,1) ON CONFLICT(chat_id) DO UPDATE SET active=1",
       (update.effective_chat.id,))
    for start in range(0, len(rows), 8):
        state = db("SELECT active FROM tags WHERE chat_id=?", (update.effective_chat.id,), True)
        if not state or not state[0][0]:
            break
        chunk = rows[start:start+8]
        await update.message.reply_text("✈️ " + " ".join(mention(i,n) for i,n in chunk),
                                        parse_mode=ParseMode.HTML)
        await __import__("asyncio").sleep(2)
    db("UPDATE tags SET active=0 WHERE chat_id=?", (update.effective_chat.id,))

async def cancel(update, context):
    db("UPDATE tags SET active=0 WHERE chat_id=?", (update.effective_chat.id,))
    await update.message.reply_text("🛑 Tagging stopped.")

async def couple(update, context):
    if not is_group(update): return
    rows = db("SELECT user_id,name FROM users WHERE chat_id=? ORDER BY RANDOM() LIMIT 2",
              (update.effective_chat.id,), True)
    if len(rows) < 2:
        return await update.message.reply_text("💞 Need at least 2 active members.")
    a,b = rows
    await update.message.reply_text(
        f"💞 <b>Today's Couple</b>\n\n{mention(a[0],a[1])}  💗  {mention(b[0],b[1])}",
        parse_mode=ParseMode.HTML)

async def setcouple(update, context):
    if not is_group(update) or not update.message.reply_to_message:
        return await update.message.reply_text("Reply to a user with /setcouple")
    a,b = update.effective_user, update.message.reply_to_message.from_user
    db("INSERT OR REPLACE INTO couples VALUES(?,?,?)",(update.effective_chat.id,a.id,b.id))
    db("INSERT OR REPLACE INTO couples VALUES(?,?,?)",(update.effective_chat.id,b.id,a.id))
    await update.message.reply_text(f"💗 {mention(a.id,a.full_name)} + {mention(b.id,b.full_name)}",
                                    parse_mode=ParseMode.HTML)

async def mycouple(update, context):
    r = db("SELECT partner_id FROM couples WHERE chat_id=? AND user_id=?",
           (update.effective_chat.id,update.effective_user.id), True)
    if not r:
        return await update.message.reply_text("💔 You don't have a couple yet.")
    p = db("SELECT name FROM users WHERE chat_id=? AND user_id=?",
           (update.effective_chat.id,r[0][0]), True)
    name = p[0][0] if p else "Your partner"
    await update.message.reply_text(f"💞 Your couple: {mention(r[0][0],name)}",
                                    parse_mode=ParseMode.HTML)

async def delcouple(update, context):
    db("DELETE FROM couples WHERE chat_id=? AND user_id=?",
       (update.effective_chat.id,update.effective_user.id))
    await update.message.reply_text("💔 Couple removed.")

async def ship(update, context):
    if not is_group(update): return
    rows = db("SELECT user_id,name FROM users WHERE chat_id=? ORDER BY RANDOM() LIMIT 2",
              (update.effective_chat.id,), True)
    if len(rows)<2:
        return await update.message.reply_text("💗 Not enough active users.")
    score = random.randint(0,100)
    await update.message.reply_text(
        f"💘 {mention(rows[0][0],rows[0][1])} × {mention(rows[1][0],rows[1][1])}\n\n"
        f"<b>Compatibility: {score}%</b> {'💞' if score>70 else '🌸'}",
        parse_mode=ParseMode.HTML)

async def dice(update, context):
    await update.message.reply_text(f"🎲 You rolled <b>{random.randint(1,6)}</b>!",
                                    parse_mode=ParseMode.HTML)

async def coin(update, context):
    await update.message.reply_text(f"🪙 <b>{random.choice(['Heads','Tails'])}</b>!",
                                    parse_mode=ParseMode.HTML)

TRUTHS = ["Who was your last crush?", "What is your biggest secret?", "Who do you text the most?"]
DARES = ["Send a funny sticker.", "Change your profile bio for 5 minutes.", "Compliment someone in this group."]
ANS = ["Yes.", "No.", "Maybe.", "Definitely!", "Ask again later.", "The signs say yes."]

async def truth(update, context):
    await update.message.reply_text("💭 <b>Truth:</b> " + random.choice(TRUTHS), parse_mode=ParseMode.HTML)

async def dare(update, context):
    await update.message.reply_text("🔥 <b>Dare:</b> " + random.choice(DARES), parse_mode=ParseMode.HTML)

async def ball(update, context):
    await update.message.reply_text("🎱 " + random.choice(ANS))

async def welcome_cmd(update, context):
    r = db("SELECT welcome,welcome_enabled FROM settings WHERE chat_id=?",
           (update.effective_chat.id,), True)
    if not r:
        return await update.message.reply_text("🔵 Welcome system is ON. No custom text set.")
    await update.message.reply_text(f"🔵 <b>Welcome:</b>\n{escape(r[0][0] or 'Default welcome')}",
                                    parse_mode=ParseMode.HTML)

async def setwelcome(update, context):
    if not is_group(update) or not await is_admin(update):
        return await update.message.reply_text("⚠️ Admins only.")
    text = update.message.text.partition(" ")[2].strip()
    if not text:
        return await update.message.reply_text("Use: /setwelcome Welcome {mention} to {title} 🌸")
    db("""INSERT INTO settings(chat_id,welcome,welcome_enabled) VALUES(?,?,1)
          ON CONFLICT(chat_id) DO UPDATE SET welcome=excluded.welcome,welcome_enabled=1""",
       (update.effective_chat.id,text))
    await update.message.reply_text("✅ Welcome message saved.")

async def delwelcome(update, context):
    if not await is_admin(update):
        return
    db("UPDATE settings SET welcome=NULL,welcome_enabled=1 WHERE chat_id=?",(update.effective_chat.id,))
    await update.message.reply_text("🗑️ Custom welcome removed.")

async def new_member(update, context):
    if not update.chat_member:
        return
    cm = update.chat_member
    if cm.new_chat_member.status not in (ChatMemberStatus.MEMBER, ChatMemberStatus.RESTRICTED):
        return
    u = cm.new_chat_member.user
    ch = cm.chat
    r = db("SELECT welcome,welcome_enabled FROM settings WHERE chat_id=?",(ch.id,),True)
    text = r[0][0] if r and r[0][1] else "🌸 Welcome {mention} to <b>{title}</b>!"
    text = text.replace("{name}", escape(u.full_name))
    text = text.replace("{mention}", mention(u.id,u.full_name))
    text = text.replace("{title}", escape(ch.title or "our group"))
    await context.bot.send_message(ch.id, text, parse_mode=ParseMode.HTML)

async def antispam(update, context):
    if not await is_admin(update):
        return await update.message.reply_text("⚠️ Admins only.")
    arg = (context.args[0].lower() if context.args else "")
    if arg not in ("on","off"):
        return await update.message.reply_text("Use /antispam on or /antispam off")
    db("""INSERT INTO settings(chat_id,antispam) VALUES(?,?)
          ON CONFLICT(chat_id) DO UPDATE SET antispam=excluded.antispam""",
       (update.effective_chat.id, 1 if arg=="on" else 0))
    await update.message.reply_text(f"🛡️ Anti-spam {'enabled' if arg=='on' else 'disabled'}.")

async def lock(update, context):
    if not await is_admin(update): return
    feature = context.args[0].lower() if context.args else "links"
    db("INSERT OR IGNORE INTO locks VALUES(?,?)",(update.effective_chat.id,feature))
    await update.message.reply_text(f"🔒 {feature} lock enabled.")

async def unlock(update, context):
    if not await is_admin(update): return
    feature = context.args[0].lower() if context.args else "links"
    db("DELETE FROM locks WHERE chat_id=? AND feature=?",(update.effective_chat.id,feature))
    await update.message.reply_text(f"🔓 {feature} lock disabled.")

async def security_filter(update, context):
    if not update.message or not is_group(update):
        return
    u = update.effective_user
    if await is_admin(update, u.id):
        return
    text = update.message.text or update.message.caption or ""
    if "http://" in text or "https://" in text or "t.me/" in text:
        r = db("SELECT 1 FROM locks WHERE chat_id=? AND feature='links'",
               (update.effective_chat.id,), True)
        if r:
            try:
                await update.message.delete()
            except Exception:
                pass

def build():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("ping", ping))
    app.add_handler(CommandHandler("id", id_cmd))
    app.add_handler(CommandHandler("info", info_cmd))
    app.add_handler(CommandHandler("tagall", tagall))
    app.add_handler(CommandHandler("tagadmins", admins))
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
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(ChatMemberHandler(new_member, ChatMemberHandler.CHAT_MEMBER))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, track_message))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, security_filter))
    return app

if __name__ == "__main__":
    app = build()
    log.info("Maya Mention full bot started")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
