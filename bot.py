# ============================================================
# FILE: bot.py  — License Telegram Bot (standalone)
# Run: python bot.py
# ============================================================

import os
import asyncio
import random
import time
import datetime
import psycopg2

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)

DATABASE_URL       = os.environ.get("DATABASE_URL")
LICENSE_BOT_TOKEN  = os.environ.get("LICENSE_BOT_TOKEN", "9285384211:AAF2tNUo5IpfTg9sEt2EJ8P9gTraXxcMOtI")
ADMIN_IDS          = list(map(int, os.environ.get("ADMIN_IDS", "8301781046").split(",")))
DEVELOPER_USERNAME = os.environ.get("DEVELOPER_USERNAME", "@SUPER_WORKER_KEY_99_bot")
APP_NAME           = os.environ.get("APP_NAME", "SuperToolsX")
TG_BOT_LINK        = os.environ.get("TG_BOT_LINK", "https://t.me/SUPER_WORKER_KEY_99_bot")

CAPTCHA_STATE      = 1
CUSTOM_KEY_DAYS    = 2
USER_KEY_DURATION  = 3

_admin_free_key_hours = {"value": 24}
_captcha_pending      = {}


# ── DB ──
def get_db():
    return psycopg2.connect(DATABASE_URL)


def ensure_license_table():
    conn = get_db(); cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS license_keys (
            key         TEXT PRIMARY KEY,
            created_at  BIGINT NOT NULL,
            expires_at  BIGINT NOT NULL,
            used_by     TEXT DEFAULT NULL,
            used_at     BIGINT DEFAULT NULL,
            is_active   BOOLEAN DEFAULT TRUE
        )
    """)
    conn.commit(); cur.close(); conn.close()

ensure_license_table()


# ── HELPERS ──
def generate_key():
    import string as _s
    part = ''.join(random.choices(_s.ascii_uppercase + _s.digits, k=16))
    return f"STOOLS-{part[:4]}-{part[4:8]}-{part[8:12]}-{part[12:]}"


def create_license_key(days: float) -> str:
    key = generate_key()
    now = int(time.time())
    exp = int(now + days * 86400)
    conn = get_db(); cur = conn.cursor()
    cur.execute(
        "INSERT INTO license_keys (key, created_at, expires_at) VALUES (%s, %s, %s)",
        (key, now, exp)
    )
    conn.commit(); cur.close(); conn.close()
    return key


def _fmt_duration(days: float) -> str:
    total = int(days * 86400)
    if total >= 86400:
        return f"{int(total // 86400)} দিন"
    return f"{int(total // 3600)} ঘন্টা"


def is_admin(uid: int) -> bool:
    return uid in ADMIN_IDS


# ── /start ──
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    keyboard = [[InlineKeyboardButton("🔑 GET NEW KEY", callback_data="get_new_key")]]
    if is_admin(user.id):
        keyboard.append([InlineKeyboardButton("⚙️ ADMIN PANEL", callback_data="admin_panel")])
    await update.message.reply_text(
        f"👋 *স্বাগতম {user.first_name}!*\n\n"
        f"🛡️ *{APP_NAME} License System*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"নিচের বাটনে ক্লিক করে নতুন Key নিন।\n\n"
        f"👨‍💻 Developer: {DEVELOPER_USERNAME}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ── GET NEW KEY → CAPTCHA ──
async def cb_get_new_key(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    a = random.randint(10, 50)
    b = random.randint(10, 50)
    _captcha_pending[query.from_user.id] = (a + b, time.time() + 120)
    await query.edit_message_text(
        f"🤖 *CAPTCHA Verification*\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"*{a} + {b} = ?*\n\n"
        f"সঠিক উত্তর টাইপ করুন (২ মিনিটের মধ্যে):",
        parse_mode="Markdown"
    )
    return CAPTCHA_STATE


async def handle_captcha(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid     = update.effective_user.id
    text    = update.message.text.strip()
    pending = _captcha_pending.get(uid)
    if not pending:
        await update.message.reply_text("⚠️ আগে /start দিয়ে CAPTCHA শুরু করুন।")
        return ConversationHandler.END
    correct, expiry = pending
    if time.time() > expiry:
        del _captcha_pending[uid]
        await update.message.reply_text("⏰ CAPTCHA time out! আবার /start দিন।")
        return ConversationHandler.END
    if not text.isdigit() or int(text) != correct:
        await update.message.reply_text("❌ ভুল উত্তর! আবার চেষ্টা করুন:")
        return CAPTCHA_STATE
    del _captcha_pending[uid]
    hours   = _admin_free_key_hours["value"]
    days    = hours / 24.0
    key     = create_license_key(days)
    exp_str = (datetime.datetime.now() + datetime.timedelta(hours=hours)).strftime("%d/%m/%Y %H:%M")
    await update.message.reply_text(
        f"✅ *CAPTCHA সঠিক!*\n\n"
        f"🔑 *আপনার License Key:*\n"
        f"`{key}`\n\n"
        f"⏱️ *মেয়াদ:* {_fmt_duration(days)}\n"
        f"📅 *Expire:* {exp_str}\n\n"
        f"⚠️ Key copy করে App এ দিন।\n"
        f"👨‍💻 Developer: {DEVELOPER_USERNAME}",
        parse_mode="Markdown"
    )
    return ConversationHandler.END


# ── ADMIN PANEL ──
async def cb_admin_panel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        await query.answer("❌ Access Denied!", show_alert=True); return
    keyboard = [
        [InlineKeyboardButton("🔐 CUSTOM KEY",          callback_data="admin_custom_key")],
        [InlineKeyboardButton("⏱️ USER KEY DURATION",   callback_data="admin_set_duration")],
        [InlineKeyboardButton("📋 ALL KEYS LIST",        callback_data="admin_list_keys")],
    ]
    await query.edit_message_text(
        f"⚙️ *ADMIN PANEL*\n━━━━━━━━━━━━━━━━━━━━\n"
        f"Current free key duration: *{_admin_free_key_hours['value']} ঘন্টা*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def cb_admin_custom_key(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id): return
    await query.edit_message_text(
        "🔐 *CUSTOM KEY*\n\nকত দিনের key বানাবেন?\n\n"
        "উদাহরণ: `10` (১০ দিন) বা `0.5` (১২ ঘন্টা)",
        parse_mode="Markdown"
    )
    return CUSTOM_KEY_DAYS


async def handle_custom_key_days(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    txt = update.message.text.strip().replace(",", ".")
    try:
        days = float(txt)
        assert days > 0
    except:
        await update.message.reply_text("❌ সংখ্যা দিন (যেমন: 10 বা 0.5)")
        return CUSTOM_KEY_DAYS
    key     = create_license_key(days)
    exp_str = (datetime.datetime.now() + datetime.timedelta(days=days)).strftime("%d/%m/%Y %H:%M")
    await update.message.reply_text(
        f"✅ *Custom Key তৈরি!*\n\n"
        f"🔑 `{key}`\n"
        f"⏱️ মেয়াদ: *{_fmt_duration(days)}*\n"
        f"📅 Expire: *{exp_str}*",
        parse_mode="Markdown"
    )
    return ConversationHandler.END


async def cb_admin_set_duration(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id): return
    await query.edit_message_text(
        "⏱️ *USER KEY DURATION SET*\n\n"
        "User 'GET NEW KEY' চাপলে কত ঘন্টার key পাবে?\n\n"
        "উদাহরণ: `24` (১ দিন) বা `1` (১ ঘন্টা)",
        parse_mode="Markdown"
    )
    return USER_KEY_DURATION


async def handle_set_duration(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    txt = update.message.text.strip()
    try:
        hours = int(txt)
        assert hours > 0
    except:
        await update.message.reply_text("❌ পূর্ণসংখ্যা দিন (যেমন: 24)")
        return USER_KEY_DURATION
    _admin_free_key_hours["value"] = hours
    await update.message.reply_text(
        f"✅ *Duration set!*\n\nUser এখন থেকে *{hours} ঘন্টার* key পাবে।",
        parse_mode="Markdown"
    )
    return ConversationHandler.END


async def cb_admin_list_keys(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id): return
    conn = get_db(); cur = conn.cursor()
    cur.execute(
        "SELECT key, expires_at, is_active FROM license_keys ORDER BY created_at DESC LIMIT 10"
    )
    rows = cur.fetchall(); cur.close(); conn.close()
    if not rows:
        await query.edit_message_text("📋 কোনো Key নেই।"); return
    now   = int(time.time())
    lines = ["📋 *শেষ ১০টি Key:*\n"]
    for r in rows:
        k, exp, active = r
        status = "✅" if active and exp > now else "❌"
        rem    = max(0, exp - now)
        d, h   = rem // 86400, (rem % 86400) // 3600
        lines.append(f"{status} `{k}`\n   ⏱ {d}d {h}h বাকি")
    await query.edit_message_text("\n".join(lines), parse_mode="Markdown")


async def cmd_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ বাতিল।")
    return ConversationHandler.END


# ── MAIN ──
async def main():
    bot_app = Application.builder().token(LICENSE_BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(cb_get_new_key,        pattern="^get_new_key$"),
            CallbackQueryHandler(cb_admin_custom_key,   pattern="^admin_custom_key$"),
            CallbackQueryHandler(cb_admin_set_duration, pattern="^admin_set_duration$"),
        ],
        states={
            CAPTCHA_STATE:     [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_captcha)],
            CUSTOM_KEY_DAYS:   [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_custom_key_days)],
            USER_KEY_DURATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_set_duration)],
        },
        fallbacks=[CommandHandler("cancel", cmd_cancel)],
        allow_reentry=True,
    )

    bot_app.add_handler(CommandHandler("start", cmd_start))
    bot_app.add_handler(CallbackQueryHandler(cb_admin_panel,     pattern="^admin_panel$"))
    bot_app.add_handler(CallbackQueryHandler(cb_admin_list_keys, pattern="^admin_list_keys$"))
    bot_app.add_handler(conv)

    print("✅ License Bot polling শুরু...", flush=True)

    await bot_app.initialize()
    await bot_app.start()
    await bot_app.updater.start_polling(
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES,
    )
    print("✅ Bot চলছে!", flush=True)

    # চালু রাখো
    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(main())
