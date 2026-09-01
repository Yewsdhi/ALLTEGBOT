from telegram import Update
from telegram.ext import ContextTypes
from tagall_system import remember_users_from_message, send_tagall

async def track_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Attach this to MessageHandler(filters.ALL, track_members)."""
    if update.effective_message:
        remember_users_from_message(update.effective_message)

async def tagall_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ready handler for /tagall <message>."""
    if not update.effective_chat or not update.effective_message:
        return

    text = " ".join(context.args).strip()

    # If /tagall is a reply, use the replied message text/caption.
    if update.effective_message.reply_to_message:
        replied = update.effective_message.reply_to_message
        reply_text = replied.text or replied.caption or ""
        if reply_text:
            text = reply_text

    await send_tagall(
        context.bot,
        update.effective_chat.id,
        text
    )
