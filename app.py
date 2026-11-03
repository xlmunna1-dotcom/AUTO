# ============================================================
# FILE: app.py
# Requirements: flask, telethon, psycopg2-binary, python-telegram-bot
# Run: python app.py
# ============================================================

import os
import asyncio
import random
import string
import time
import datetime
import threading
import psycopg2
from flask import Flask, request, jsonify
from telethon import TelegramClient, events
from telethon.sessions import StringSession
import telegram
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)

app = Flask(__name__)

DATABASE_URL    = os.environ.get("DATABASE_URL")
BOT             = "@Taskl1_bot"
COOKIE_SELL_BOT = "@QuickTaskPay1bot"

# ── LICENSE BOT CONFIG ──
LICENSE_BOT_TOKEN  = os.environ.get("LICENSE_BOT_TOKEN", "9285384211:AAF2tNUo5IpfTg9sEt2EJ8P9gTraXxcMOtI")
ADMIN_IDS          = list(map(int, os.environ.get("ADMIN_IDS", "8301781046").split(",")))
DEVELOPER_USERNAME = os.environ.get("DEVELOPER_USERNAME", "@SUPER_WORKER_KEY_99_bot")
APP_NAME           = os.environ.get("APP_NAME", "SuperToolsX")
TG_BOT_LINK        = os.environ.get("TG_BOT_LINK", "https://t.me/SUPER_WORKER_KEY_99_bot")

# ConversationHandler states
CAPTCHA_STATE      = 1
CUSTOM_KEY_DAYS    = 2
USER_KEY_DURATION  = 3
SET_LIMIT_STATE    = 4

# Admin settings (in-memory; survives until restart)
_admin_free_key_hours  = {"value": 24}
_admin_daily_key_limit = {"value": 1}   # প্রতি ইউজার প্রতিদিন কয়টা key নিতে পারবে

# Pending captcha answers: {user_id: (answer, expiry_ts)}
_captcha_pending = {}


def get_db():
    return psycopg2.connect(DATABASE_URL)


def ensure_tables():
    conn = get_db()
    cur  = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS pending_otp (
            phone            TEXT PRIMARY KEY,
            api_id           TEXT NOT NULL,
            api_hash         TEXT NOT NULL,
            phone_code_hash  TEXT NOT NULL,
            temp_session     TEXT
        )
    """)
    cur.execute("ALTER TABLE pending_otp ADD COLUMN IF NOT EXISTS temp_session TEXT")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_sessions (
            user_id         TEXT PRIMARY KEY,
            session_string  TEXT NOT NULL,
            api_id          TEXT NOT NULL,
            api_hash        TEXT NOT NULL,
            target_username TEXT NOT NULL
        )
    """)
    cur.execute("ALTER TABLE user_sessions ADD COLUMN IF NOT EXISTS api_id TEXT")
    cur.execute("ALTER TABLE user_sessions ADD COLUMN IF NOT EXISTS api_hash TEXT")
    cur.execute("ALTER TABLE user_sessions ADD COLUMN IF NOT EXISTS target_username TEXT")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sell_stats (
            user_id    TEXT PRIMARY KEY,
            sell_count INTEGER DEFAULT 0
        )
    """)
    # ── LICENSE KEYS TABLE ──
    cur.execute("""
        CREATE TABLE IF NOT EXISTS license_keys (
            key         TEXT PRIMARY KEY,
            created_at  BIGINT NOT NULL,
            expires_at  BIGINT NOT NULL,
            used_by     TEXT DEFAULT NULL,
            used_at     BIGINT DEFAULT NULL,
            device_id   TEXT DEFAULT NULL,
            tg_username TEXT DEFAULT NULL,
            tg_name     TEXT DEFAULT NULL,
            tg_id       TEXT DEFAULT NULL,
            is_active   BOOLEAN DEFAULT TRUE
        )
    """)
    cur.execute("ALTER TABLE license_keys ADD COLUMN IF NOT EXISTS device_id   TEXT DEFAULT NULL")
    cur.execute("ALTER TABLE license_keys ADD COLUMN IF NOT EXISTS tg_username TEXT DEFAULT NULL")
    cur.execute("ALTER TABLE license_keys ADD COLUMN IF NOT EXISTS tg_name     TEXT DEFAULT NULL")
    cur.execute("ALTER TABLE license_keys ADD COLUMN IF NOT EXISTS tg_id       TEXT DEFAULT NULL")

    # ── USER KEY USAGE TABLE: per-user per-day limit tracking ──
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_key_usage (
            user_id      TEXT PRIMARY KEY,
            key_count    INTEGER DEFAULT 0,
            last_reset   BIGINT DEFAULT 0
        )
    """)
    conn.commit()
    cur.close()
    conn.close()

ensure_tables()


# ══════════════════════════════════════════════════════════
#  LICENSE KEY HELPERS
# ══════════════════════════════════════════════════════════

def generate_key(prefix="STOOLS"):
    part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=16))
    return f"{prefix}-{part[:4]}-{part[4:8]}-{part[8:12]}-{part[12:]}"


def create_license_key(days: float,
                       tg_username: str = None,
                       tg_name: str = None,
                       tg_id: str = None) -> str:
    key        = generate_key()
    now        = int(time.time())
    expires_at = int(now + days * 86400)
    conn = get_db(); cur = conn.cursor()
    cur.execute(
        """INSERT INTO license_keys
           (key, created_at, expires_at, tg_username, tg_name, tg_id)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        (key, now, expires_at, tg_username, tg_name, tg_id)
    )
    conn.commit(); cur.close(); conn.close()
    return key


def validate_key(key: str, device_id: str = None):
    """Returns (valid: bool, message: str, row_dict or None)"""
    conn = get_db(); cur = conn.cursor()
    cur.execute(
        """SELECT key, created_at, expires_at, used_by, device_id,
                  tg_username, tg_name, tg_id, is_active
           FROM license_keys WHERE key = %s""",
        (key,)
    )
    row = cur.fetchone(); cur.close(); conn.close()
    if not row:
        return False, "❌ Invalid key!", None
    k, created_at, expires_at, used_by, locked_device, \
        tg_username, tg_name, tg_id, is_active = row
    if not is_active:
        return False, "🚫 Key deactivated!", None
    now = int(time.time())
    if now > expires_at:
        return False, "⏰ Key expired!", None

    # ── Device lock ──
    if device_id and locked_device and locked_device != device_id:
        return False, "🔒 This key is locked to another device!", None

    remaining  = expires_at - now
    days_left  = remaining // 86400
    hours_left = (remaining % 86400) // 3600
    mins_left  = (remaining % 3600) // 60
    exp_str    = datetime.datetime.fromtimestamp(expires_at).strftime("%d/%m/%Y %H:%M")
    info = {
        "key"        : k,
        "expires_at" : expires_at,
        "exp_str"    : exp_str,
        "days_left"  : days_left,
        "hours_left" : hours_left,
        "mins_left"  : mins_left,
        "tg_username": tg_username or "",
        "tg_name"    : tg_name     or "",
        "tg_id"      : tg_id       or "",
    }
    return True, "✅ Valid", info


def mark_key_used(key: str, device_id: str):
    conn = get_db(); cur = conn.cursor()
    cur.execute(
        "UPDATE license_keys SET used_by=%s, used_at=%s, device_id=%s WHERE key=%s",
        (device_id, int(time.time()), device_id, key)
    )
    conn.commit(); cur.close(); conn.close()


# ── Per-user daily limit helpers ──

def check_and_increment_key_usage(user_id: int) -> tuple[bool, str]:
    """
    Returns (allowed: bool, message: str)
    Resets counter after 24h.
    """
    conn = get_db(); cur = conn.cursor()
    cur.execute(
        "SELECT key_count, last_reset FROM user_key_usage WHERE user_id = %s",
        (str(user_id),)
    )
    row = cur.fetchone()
    now = int(time.time())
    limit = _admin_daily_key_limit["value"]

    if row is None:
        # প্রথমবার
        cur.execute(
            "INSERT INTO user_key_usage (user_id, key_count, last_reset) VALUES (%s, 1, %s)",
            (str(user_id), now)
        )
        conn.commit(); cur.close(); conn.close()
        return True, "ok"

    key_count, last_reset = row
    # ২৪ ঘন্টা পর reset
    if now - last_reset >= 86400:
        cur.execute(
            "UPDATE user_key_usage SET key_count=1, last_reset=%s WHERE user_id=%s",
            (now, str(user_id))
        )
        conn.commit(); cur.close(); conn.close()
        return True, "ok"

    if key_count >= limit:
        reset_in = 86400 - (now - last_reset)
        hours_r  = reset_in // 3600
        mins_r   = (reset_in % 3600) // 60
        cur.close(); conn.close()
        return False, f"⏳ *LIMIT REACHED!*\n\nআজকের জন্য আপনার সীমা শেষ।\n🔄 Reset হবে *{hours_r} ঘন্টা {mins_r} মিনিট* পরে।"

    cur.execute(
        "UPDATE user_key_usage SET key_count=key_count+1 WHERE user_id=%s",
        (str(user_id),)
    )
    conn.commit(); cur.close(); conn.close()
    return True, "ok"


# ══════════════════════════════════════════════════════════
#  FLASK ENDPOINT — /validate_key  (called by Android app)
# ══════════════════════════════════════════════════════════

@app.route("/validate_key", methods=["POST"])
def api_validate_key():
    data      = request.json or {}
    key       = (data.get("key") or "").strip().upper()
    dev_id    = data.get("device_id", "unknown")
    tg_user   = data.get("tg_username", "")   # Android passes Telegram username if available
    if not key:
        return jsonify({"valid": False, "message": "Key missing"}), 400
    valid, msg, info = validate_key(key, dev_id)
    if valid:
        mark_key_used(key, dev_id)
        return jsonify({
            "valid"      : True,
            "message"    : msg,
            "expires_at" : info["expires_at"],
            "exp_str"    : info["exp_str"],
            "days_left"  : info["days_left"],
            "hours_left" : info["hours_left"],
            "mins_left"  : info["mins_left"],
            "tg_username": info["tg_username"],   # @username (bot থেকে নেওয়া)
            "tg_name"    : info["tg_name"],        # First name
            "tg_id"      : info["tg_id"],          # Telegram user ID
        })
    return jsonify({"valid": False, "message": msg}), 200


# ══════════════════════════════════════════════════════════
#  TELEGRAM LICENSE BOT  (python-telegram-bot v20+)
# ══════════════════════════════════════════════════════════

def _fmt_duration(days: float) -> str:
    total_secs = int(days * 86400)
    if total_secs >= 86400:
        return f"{int(total_secs // 86400)} দিন"
    return f"{int(total_secs // 3600)} ঘন্টা"


def is_admin(uid: int) -> bool:
    return uid in ADMIN_IDS


# ══════════════════════════════════════════════════
#  /start  — Welcome Message
# ══════════════════════════════════════════════════
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    name = user.first_name or "বন্ধু"

    # ── Reply keyboard (colored buttons via Telegram's new update) ──
    from telegram import ReplyKeyboardMarkup, KeyboardButton
    reply_kb = ReplyKeyboardMarkup(
        [[KeyboardButton("🔑 GET NEW KEY")]],
        resize_keyboard=True,
        one_time_keyboard=False,
    )

    # ── Inline keyboard ──
    inline_kb = [[InlineKeyboardButton("🔑 GET NEW KEY", callback_data="get_new_key")]]
    if is_admin(user.id):
        inline_kb.append([InlineKeyboardButton("⚙️ ADMIN PANEL", callback_data="admin_panel")])

    limit = _admin_daily_key_limit["value"]
    await update.message.reply_text(
        f"╔══════════════════════╗\n"
        f"║  🛡️  *SUPER TOOLS KEY*  🛡️  ║\n"
        f"╚══════════════════════╝\n\n"
        f"👋 স্বাগতম, *{name}!*\n\n"
        f"🔐 *{APP_NAME} License System*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"✅ নতুন Key পেতে নিচের বাটনে ক্লিক করুন\n"
        f"⚡ প্রতিদিন *{limit}টি* করে Key নিতে পারবেন\n"
        f"🔒 একটি Key শুধু একটি Device-এ চলবে\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👨‍💻 Developer: {DEVELOPER_USERNAME}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_kb)
    )


# ══════════════════════════════════════════════════
#  GET NEW KEY → CAPTCHA
# ══════════════════════════════════════════════════
async def cb_get_new_key(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user  = query.from_user

    # ── Daily limit check ──
    allowed, msg = check_and_increment_key_usage(user.id)
    if not allowed:
        await query.edit_message_text(
            f"🚫 *LIMIT REACHED!*\n\n{msg}\n\n"
            f"👨‍💻 Developer: {DEVELOPER_USERNAME}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 Back", callback_data="back_start")]]
            )
        )
        return ConversationHandler.END

    a      = random.randint(10, 99)
    b      = random.randint(10, 99)
    answer = a + b
    expiry = time.time() + 120
    _captcha_pending[user.id] = (answer, expiry)

    await query.edit_message_text(
        f"🤖 *CAPTCHA Verification*\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🧮  *{a}  +  {b}  =  ?*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"✏️ সঠিক উত্তর টাইপ করুন\n"
        f"⏱️ সময়: ২ মিনিট",
        parse_mode="Markdown"
    )
    return CAPTCHA_STATE


async def handle_captcha(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user    = update.effective_user
    uid     = user.id
    text    = update.message.text.strip()
    pending = _captcha_pending.get(uid)

    if not pending:
        await update.message.reply_text("⚠️ আগে /start দিয়ে CAPTCHA শুরু করুন।")
        return ConversationHandler.END

    correct_ans, expiry = pending
    if time.time() > expiry:
        del _captcha_pending[uid]
        await update.message.reply_text("⏰ CAPTCHA timeout! /start দিন।")
        return ConversationHandler.END

    if not text.isdigit() or int(text) != correct_ans:
        await update.message.reply_text(
            "❌ *ভুল উত্তর!* আবার চেষ্টা করুন 👇",
            parse_mode="Markdown"
        )
        return CAPTCHA_STATE

    del _captcha_pending[uid]

    # Telegram user info সংরক্ষণ
    tg_username = user.username or ""
    tg_name     = (user.first_name or "") + (" " + (user.last_name or "") if user.last_name else "")
    tg_id       = str(user.id)

    # Key তৈরি — user info সহ DB-তে save হবে
    hours   = _admin_free_key_hours["value"]
    days    = hours / 24.0
    key     = create_license_key(days,
                                  tg_username=tg_username,
                                  tg_name=tg_name.strip(),
                                  tg_id=tg_id)
    exp     = datetime.datetime.now() + datetime.timedelta(hours=hours)
    exp_str = exp.strftime("%d/%m/%Y %H:%M")

    # Bot message-এ username দেখানো
    username_line = ""
    if tg_username:
        username_line = f"👤 Username: *@{tg_username}*\n"
    elif tg_name.strip():
        username_line = f"👤 Name: *{tg_name.strip()}*\n"
    else:
        username_line = f"👤 ID: *{tg_id}*\n"

    await update.message.reply_text(
        f"╔══════════════════════╗\n"
        f"║   ✅  KEY GENERATED!   ║\n"
        f"╚══════════════════════╝\n\n"
        f"{username_line}"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔑 *Your License Key:*\n"
        f"`{key}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏱️ মেয়াদ: *{_fmt_duration(days)}*\n"
        f"📅 Expire: *{exp_str}*\n"
        f"🔒 শুধু একটি Device-এ চলবে\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📋 Key copy করে App-এ দিন\n"
        f"👨‍💻 {DEVELOPER_USERNAME}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🏠 Main Menu", callback_data="back_start")]]
        )
    )
    return ConversationHandler.END


# Back button
async def cb_back_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user  = query.from_user
    limit = _admin_daily_key_limit["value"]
    inline_kb = [[InlineKeyboardButton("🔑 GET NEW KEY", callback_data="get_new_key")]]
    if is_admin(user.id):
        inline_kb.append([InlineKeyboardButton("⚙️ ADMIN PANEL", callback_data="admin_panel")])
    await query.edit_message_text(
        f"╔══════════════════════╗\n"
        f"║  🛡️  *SUPER TOOLS KEY*  🛡️  ║\n"
        f"╚══════════════════════╝\n\n"
        f"✅ প্রতিদিন *{limit}টি* Key নিতে পারবেন\n"
        f"🔒 একটি Key শুধু একটি Device-এ\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👨‍💻 Developer: {DEVELOPER_USERNAME}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_kb)
    )


# ══════════════════════════════════════════════════
#  ADMIN PANEL
# ══════════════════════════════════════════════════
async def cb_admin_panel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        await query.answer("❌ Access Denied!", show_alert=True); return

    limit = _admin_daily_key_limit["value"]
    hours = _admin_free_key_hours["value"]

    keyboard = [
        [InlineKeyboardButton("🔐 CUSTOM KEY",           callback_data="admin_custom_key")],
        [InlineKeyboardButton("⏱️ USER KEY DURATION",    callback_data="admin_set_duration")],
        [InlineKeyboardButton("🚦 SET LIMIT",            callback_data="admin_set_limit")],
        [InlineKeyboardButton("📋 ALL KEYS LIST",        callback_data="admin_list_keys")],
        [InlineKeyboardButton("🔙 Back",                 callback_data="back_start")],
    ]
    await query.edit_message_text(
        f"⚙️ *ADMIN PANEL*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏱️ Free key duration: *{hours} ঘন্টা*\n"
        f"🚦 Daily key limit: *{limit}টি / user*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ── CUSTOM KEY ──
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
    uid = update.effective_user.id
    if not is_admin(uid):
        return ConversationHandler.END
    txt = update.message.text.strip().replace(",", ".")
    try:
        days = float(txt)
        assert days > 0
    except:
        await update.message.reply_text("❌ সংখ্যা দিন (যেমন: 10 বা 0.5)")
        return CUSTOM_KEY_DAYS
    key     = create_license_key(days)
    exp     = datetime.datetime.now() + datetime.timedelta(days=days)
    exp_str = exp.strftime("%d/%m/%Y %H:%M")
    await update.message.reply_text(
        f"✅ *Custom Key তৈরি!*\n\n"
        f"🔑 `{key}`\n"
        f"⏱️ মেয়াদ: *{_fmt_duration(days)}*\n"
        f"📅 Expire: *{exp_str}*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel")]]
        )
    )
    return ConversationHandler.END


# ── USER KEY DURATION ──
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
    uid = update.effective_user.id
    if not is_admin(uid):
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
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel")]]
        )
    )
    return ConversationHandler.END


# ══════════════════════════════════════════════════
#  SET LIMIT — নতুন ফিচার
#  Admin সেট করবে প্রতি user প্রতিদিন কয়টা key নিতে পারবে
# ══════════════════════════════════════════════════
async def cb_admin_set_limit(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id): return
    current = _admin_daily_key_limit["value"]
    await query.edit_message_text(
        f"🚦 *SET LIMIT*\n\n"
        f"বর্তমান limit: *{current}টি / user / দিন*\n\n"
        f"প্রতি User ২৪ ঘন্টায় কয়টি Key নিতে পারবে?\n\n"
        f"উদাহরণ:\n"
        f"• `1` → দিনে মাত্র একটি key\n"
        f"• `3` → দিনে ৩টি key\n"
        f"• `0` → সীমাহীন (unlimited)\n\n"
        f"⚠️ Limit শেষে User কে দেখাবে:\n"
        f"_🚫 LIMIT REACHED — ২৪ ঘন্টা পর Reset হবে_",
        parse_mode="Markdown"
    )
    return SET_LIMIT_STATE


async def handle_set_limit(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_admin(uid):
        return ConversationHandler.END
    txt = update.message.text.strip()
    try:
        limit = int(txt)
        assert limit >= 0
    except:
        await update.message.reply_text("❌ সংখ্যা দিন (0 = unlimited)")
        return SET_LIMIT_STATE
    _admin_daily_key_limit["value"] = limit
    label = f"*{limit}টি*" if limit > 0 else "*Unlimited*"
    await update.message.reply_text(
        f"✅ *Limit set!*\n\n"
        f"প্রতি User এখন থেকে প্রতিদিন {label} key নিতে পারবে।\n"
        f"🔄 ২৪ ঘন্টা পর Automatic Reset।",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel")]]
        )
    )
    return ConversationHandler.END


# ── ALL KEYS LIST ──
async def cb_admin_list_keys(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id): return
    conn = get_db(); cur = conn.cursor()
    cur.execute(
        "SELECT key, expires_at, is_active, device_id FROM license_keys ORDER BY created_at DESC LIMIT 10"
    )
    rows = cur.fetchall(); cur.close(); conn.close()
    if not rows:
        await query.edit_message_text("📋 কোনো Key নেই।"); return
    now = int(time.time())
    lines = ["📋 *শেষ ১০টি Key:*\n"]
    for r in rows:
        k, exp, active, dev = r
        status  = "✅" if active and exp > now else "❌"
        rem     = max(0, exp - now)
        d, h    = rem // 86400, (rem % 86400) // 3600
        dev_str = f"🔒`{dev[:10]}...`" if dev else "🔓 Unused"
        lines.append(f"{status} `{k[:20]}...`\n   ⏱ {d}d {h}h বাকি | {dev_str}")
    await query.edit_message_text(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel")]]
        )
    )


async def cmd_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ বাতিল।")
    return ConversationHandler.END


# ══════════════════════════════════════════════════
#  BOT RUNNER
# ══════════════════════════════════════════════════
def run_license_bot():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def _run():
        try:
            bot_app = Application.builder().token(LICENSE_BOT_TOKEN).build()

            conv = ConversationHandler(
                entry_points=[
                    CallbackQueryHandler(cb_get_new_key,        pattern="^get_new_key$"),
                    CallbackQueryHandler(cb_admin_custom_key,   pattern="^admin_custom_key$"),
                    CallbackQueryHandler(cb_admin_set_duration, pattern="^admin_set_duration$"),
                    CallbackQueryHandler(cb_admin_set_limit,    pattern="^admin_set_limit$"),
                ],
                states={
                    CAPTCHA_STATE:    [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_captcha)],
                    CUSTOM_KEY_DAYS:  [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_custom_key_days)],
                    USER_KEY_DURATION:[MessageHandler(filters.TEXT & ~filters.COMMAND, handle_set_duration)],
                    SET_LIMIT_STATE:  [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_set_limit)],
                },
                fallbacks=[CommandHandler("cancel", cmd_cancel)],
                allow_reentry=True,
            )

            bot_app.add_handler(CommandHandler("start",     cmd_start))
            bot_app.add_handler(CallbackQueryHandler(cb_admin_panel,    pattern="^admin_panel$"))
            bot_app.add_handler(CallbackQueryHandler(cb_admin_list_keys,pattern="^admin_list_keys$"))
            bot_app.add_handler(CallbackQueryHandler(cb_back_start,     pattern="^back_start$"))
            bot_app.add_handler(conv)

            print("[LICENSE BOT] ✅ Bot starting...", flush=True)
            await bot_app.initialize()
            await bot_app.start()
            await bot_app.updater.start_polling(
                drop_pending_updates=True,
                allowed_updates=Update.ALL_TYPES,
            )
            print("[LICENSE BOT] ✅ Polling active!", flush=True)
            while True:
                await asyncio.sleep(3600)
        except Exception as e:
            print(f"[LICENSE BOT] ❌ Error: {e}", flush=True)
            import traceback; traceback.print_exc()

    try:
        loop.run_until_complete(_run())
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()


# ══════════════════════════════════════════════════════════
#  EXISTING FLASK ENDPOINTS  (unchanged — সব রাখা হয়েছে)
# ══════════════════════════════════════════════════════════

# ──────────────────────────────────────────────
# ENDPOINT 1: /send_otp
# ──────────────────────────────────────────────
@app.route("/send_otp", methods=["POST"])
def send_otp():
    data     = request.json
    api_id   = int(data["api_id"])
    api_hash = data["api_hash"]
    phone    = data["phone"]

    async def _send():
        client = TelegramClient(StringSession(), api_id, api_hash)
        await client.connect()
        result = await client.send_code_request(phone)
        phone_code_hash = result.phone_code_hash
        temp_session    = client.session.save()
        await client.disconnect()
        return phone_code_hash, temp_session

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        phone_code_hash, temp_session = loop.run_until_complete(_send())
        loop.close()

        conn = get_db(); cur = conn.cursor()
        cur.execute("""
            INSERT INTO pending_otp (phone, api_id, api_hash, phone_code_hash, temp_session)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (phone) DO UPDATE SET
                api_id          = EXCLUDED.api_id,
                api_hash        = EXCLUDED.api_hash,
                phone_code_hash = EXCLUDED.phone_code_hash,
                temp_session    = EXCLUDED.temp_session
        """, (phone, str(api_id), api_hash, phone_code_hash, temp_session))
        conn.commit(); cur.close(); conn.close()
        return jsonify({"status": "otp_sent", "phone": phone})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ──────────────────────────────────────────────
# ENDPOINT 2: /verify_otp
# ──────────────────────────────────────────────
@app.route("/verify_otp", methods=["POST"])
def verify_otp():
    data            = request.json
    phone           = data["phone"]
    otp             = data["otp"]
    tg_user_id      = data["tg_user_id"]
    target_username = data["target_username"]

    conn = get_db(); cur = conn.cursor()
    cur.execute(
        "SELECT api_id, api_hash, phone_code_hash, temp_session FROM pending_otp WHERE phone = %s",
        (phone,)
    )
    row = cur.fetchone(); cur.close(); conn.close()
    if not row:
        return jsonify({"status": "error", "message": "No pending OTP."}), 400

    api_id, api_hash, phone_code_hash, temp_session = row

    async def _verify():
        client = TelegramClient(StringSession(temp_session), int(api_id), api_hash)
        await client.connect()
        await client.sign_in(phone, otp, phone_code_hash=phone_code_hash)
        session_string = client.session.save()
        await client.disconnect()
        return session_string

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        session_string = loop.run_until_complete(_verify())
        loop.close()

        conn = get_db(); cur = conn.cursor()
        cur.execute("""
            INSERT INTO user_sessions (user_id, session_string, api_id, api_hash, target_username)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (user_id) DO UPDATE SET
                session_string  = EXCLUDED.session_string,
                api_id          = EXCLUDED.api_id,
                api_hash        = EXCLUDED.api_hash,
                target_username = EXCLUDED.target_username
        """, (tg_user_id, session_string, str(api_id), api_hash, target_username))
        cur.execute("DELETE FROM pending_otp WHERE phone = %s", (phone,))
        conn.commit(); cur.close(); conn.close()
        return jsonify({"status": "success", "message": "Session saved!"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ──────────────────────────────────────────────
# ENDPOINT 3: /automate_sale
# ──────────────────────────────────────────────
@app.route("/automate_sale", methods=["POST"])
def automate_sale():
    data       = request.json
    tg_user_id = data["tg_user_id"]
    twofa_key  = data["twofa_key"]
    cookie     = data["cookie"]

    conn = get_db(); cur = conn.cursor()
    cur.execute(
        "SELECT session_string, api_id, api_hash, target_username FROM user_sessions WHERE user_id = %s",
        (tg_user_id,)
    )
    row = cur.fetchone(); cur.close(); conn.close()
    if not row:
        return jsonify({"status": "error", "message": "User not found."}), 404

    session_string, api_id, api_hash, target_username = row

    async def _sell():
        client = TelegramClient(StringSession(session_string), int(api_id), api_hash)
        await client.connect()
        sold = False
        step = {"current": 0}
        too_often_retry = {"count": 0, "max": 5}

        @client.on(events.NewMessage(from_users=BOT))
        async def handler(event):
            nonlocal sold
            msg  = event.message
            text = msg.text or ""

            if "too often" in text.lower() or "please wait" in text.lower():
                import re
                nums = re.findall(r'\d+', text)
                wait_sec = int(nums[0]) + 2 if nums else 35
                too_often_retry["count"] += 1
                if too_often_retry["count"] <= too_often_retry["max"]:
                    step["current"] = 0
                    await asyncio.sleep(wait_sec)
                    await client.send_message(BOT, "/start")
                return

            if "Welcome" in text and step["current"] == 0:
                step["current"] = 1
                await asyncio.sleep(1)
                await client.send_message(BOT, "📋 Tasks")
            elif "Please select a task" in text and step["current"] == 1:
                step["current"] = 2
                await asyncio.sleep(1)
                await client.send_message(BOT, "🍪 ($0.0280)")
            elif "🍪:" in text and step["current"] == 2:
                step["current"] = 3
                await asyncio.sleep(1)
                await client.send_message(BOT, "🌟2FA:Create FB (No mail) ($0.0280)")
            elif ("Description" in text or "REQUIRED" in text) and step["current"] == 3:
                step["current"] = 4
                await asyncio.sleep(1)
                await client.send_message(BOT, "▶️ Start")
            elif ("2FA" in text or "2fa key" in text.lower()) and step["current"] == 4:
                step["current"] = 5
                await asyncio.sleep(1)
                await client.send_message(BOT, twofa_key)
            elif ("send the account" in text.lower() or "🍪" in text) and step["current"] == 5:
                step["current"] = 6
                await asyncio.sleep(1)
                await client.send_message(BOT, cookie)
            elif ("confirm registration" in text.lower() or "Press the button" in text) and step["current"] == 6:
                step["current"] = 7
                await asyncio.sleep(1)
                try:
                    await msg.click(text="✅ Account registered")
                except Exception:
                    await client.send_message(BOT, "✅ Account registered")
            elif "report has been received" in text.lower() and step["current"] == 7:
                step["current"] = 8
                sold = True
                await client.send_message(target_username, f"🎉 Account Sold!\n2FA: {twofa_key}")

        await client.send_message(BOT, "/start")
        for _ in range(600):
            await asyncio.sleep(1)
            if step["current"] == 8: break
        client.remove_event_handler(handler)
        await client.disconnect()
        return sold

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        sold = loop.run_until_complete(_sell())
        loop.close()
        if sold:
            conn2 = get_db(); cur2 = conn2.cursor()
            cur2.execute("""
                INSERT INTO sell_stats (user_id, sell_count) VALUES (%s, 1)
                ON CONFLICT (user_id) DO UPDATE SET sell_count = sell_stats.sell_count + 1
            """, (tg_user_id,))
            conn2.commit(); cur2.close(); conn2.close()
            return jsonify({"status": "success", "message": "Sale সম্পন্ন!"})
        return jsonify({"status": "timeout", "message": "Flow incomplete।"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ──────────────────────────────────────────────
# ENDPOINT 4: /automate_cookie_sale
# ──────────────────────────────────────────────
@app.route("/automate_cookie_sale", methods=["POST"])
def automate_cookie_sale():
    data       = request.get_json(silent=True) or {}
    tg_user_id = str(data.get("tg_user_id", "")).strip()
    uid        = str(data.get("uid", "")).strip()
    cookie     = str(data.get("cookie", "")).strip()

    if not tg_user_id:
        return jsonify({"status": "error", "message": "tg_user_id দরকার।"}), 400
    if not uid.isdigit():
        return jsonify({"status": "error", "message": "Numeric UID দরকার।"}), 400
    if not cookie or "c_user=" not in cookie:
        return jsonify({"status": "error", "message": "Cookie invalid।"}), 400

    conn = get_db(); cur = conn.cursor()
    cur.execute(
        "SELECT session_string, api_id, api_hash, target_username FROM user_sessions WHERE user_id = %s",
        (tg_user_id,)
    )
    row = cur.fetchone(); cur.close(); conn.close()
    if not row:
        return jsonify({"status": "error", "message": "User not found."}), 404

    session_string, api_id, api_hash, target_username = row

    async def _sell_cookie():
        client = TelegramClient(StringSession(session_string), int(api_id), api_hash)
        await client.connect()
        if not await client.is_user_authorized():
            await client.disconnect()
            raise RuntimeError("Session expire হয়েছে।")
        sold = False
        step = {"current": 0}

        async def click_or_send(msg, labels, fallback):
            wanted = [label.lower() for label in labels]
            for button_row in (msg.buttons or []):
                for button in button_row:
                    button_text = (getattr(button, "text", "") or "").strip()
                    if any(label in button_text.lower() for label in wanted):
                        await msg.click(text=button_text)
                        return True
            if fallback:
                await client.send_message(COOKIE_SELL_BOT, fallback)
                return True
            return False

        too_often_retry = {"count": 0, "max": 5}

        async def handler(event):
            nonlocal sold
            msg  = event.message
            text = msg.text or ""
            low  = text.lower()
            if sold: return

            if "too often" in low or "please wait" in low:
                import re
                nums = re.findall(r'\d+', text)
                wait_sec = int(nums[0]) + 2 if nums else 35
                too_often_retry["count"] += 1
                if too_often_retry["count"] <= too_often_retry["max"]:
                    step["current"] = 0
                    await asyncio.sleep(wait_sec)
                    await client.send_message(COOKIE_SELL_BOT, "/start")
                return

            if step["current"] == 0 and ("welcome" in low or "gotask pay" in low):
                step["current"] = 1
                await asyncio.sleep(0.6)
                await click_or_send(msg, ["task"], "Task")
            elif step["current"] == 1 and ("which platform" in low or "platform" in low):
                step["current"] = 2
                await asyncio.sleep(0.6)
                await click_or_send(msg, ["facebook"], "Facebook")
            elif step["current"] == 2 and ("fb cookies" in low or "facebook" in low):
                step["current"] = 3
                await asyncio.sleep(0.6)
                await click_or_send(msg, ["fb cookies"], "Fb Cookies (4 BDT)")
            elif step["current"] == 3 and "submit uid" in low:
                step["current"] = 4
                await asyncio.sleep(0.6)
                await click_or_send(msg, ["submit uid"], "Submit UID 🆔")
            elif step["current"] == 4 and ("send me the uid" in low or "send uid" in low):
                step["current"] = 5
                await asyncio.sleep(0.6)
                await client.send_message(COOKIE_SELL_BOT, uid)
            elif step["current"] == 5 and "uid received" in low:
                step["current"] = 6
                await asyncio.sleep(0.6)
                await client.send_message(COOKIE_SELL_BOT, cookie)
            elif step["current"] == 6 and "cookies received" in low:
                step["current"] = 7
                await asyncio.sleep(0.6)
                await click_or_send(msg, ["complete and submit"], "Complete and Submit")
            elif step["current"] >= 6 and ("task submitted successfully" in low or "submitted successfully" in low):
                step["current"] = 8
                sold = True
                if target_username:
                    await client.send_message(
                        target_username,
                        f"🎉 Cookie Task Submitted!\nUID: {uid}\nBot: {COOKIE_SELL_BOT}"
                    )

        client.add_event_handler(handler, events.NewMessage(from_users=COOKIE_SELL_BOT))
        client.add_event_handler(handler, events.MessageEdited(from_users=COOKIE_SELL_BOT))
        await client.send_message(COOKIE_SELL_BOT, "/start")

        for _ in range(600):
            await asyncio.sleep(1)
            if sold: break

        client.remove_event_handler(handler)
        await client.disconnect()
        return sold, step["current"]

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        sold, last_step = loop.run_until_complete(_sell_cookie())
        loop.close()
        if sold:
            conn2 = get_db(); cur2 = conn2.cursor()
            cur2.execute("""
                INSERT INTO sell_stats (user_id, sell_count) VALUES (%s, 1)
                ON CONFLICT (user_id) DO UPDATE SET sell_count = sell_stats.sell_count + 1
            """, (tg_user_id,))
            conn2.commit(); cur2.close(); conn2.close()
            return jsonify({"status": "success", "message": "Cookie task submitted!"})
        return jsonify({"status": "timeout", "message": f"Incomplete (step {last_step})"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ──────────────────────────────────────────────
# ENDPOINT 5: /check_session
# ──────────────────────────────────────────────
@app.route("/check_session", methods=["POST"])
def check_session():
    data       = request.json
    tg_user_id = data.get("tg_user_id", "")
    if not tg_user_id:
        return jsonify({"status": "invalid"}), 400

    conn = get_db(); cur = conn.cursor()
    cur.execute(
        "SELECT session_string, api_id, api_hash FROM user_sessions WHERE user_id = %s",
        (tg_user_id,)
    )
    row = cur.fetchone(); cur.close(); conn.close()
    if not row:
        return jsonify({"status": "invalid", "message": "Session নেই।"})

    session_string, api_id, api_hash = row

    async def _check():
        client = TelegramClient(StringSession(session_string), int(api_id), api_hash)
        await client.connect()
        authorized = await client.is_user_authorized()
        await client.disconnect()
        return authorized

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        authorized = loop.run_until_complete(_check())
        loop.close()
        if authorized:
            return jsonify({"status": "valid"})
        else:
            conn = get_db(); cur = conn.cursor()
            cur.execute("DELETE FROM user_sessions WHERE user_id = %s", (tg_user_id,))
            conn.commit(); cur.close(); conn.close()
            return jsonify({"status": "invalid", "message": "Session expire হয়েছে।"})
    except Exception as e:
        return jsonify({"status": "invalid", "message": str(e)})


# ──────────────────────────────────────────────
# ENDPOINT: /ping  &  /
# ──────────────────────────────────────────────
@app.route("/ping", methods=["GET", "POST"])
def ping():
    return jsonify({"status": "ok", "message": "Server is alive!"}), 200

@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "running", "message": "Auto Server is running!"}), 200


if __name__ == "__main__":
    bot_thread = threading.Thread(target=run_license_bot, daemon=True)
    bot_thread.start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
