# ============================================================
# FILE: app.py  — FORCE JOIN + EMOJI CAPTCHA + COLORED BUTTONS
# Requirements: flask, gunicorn, telethon, psycopg2-binary, python-telegram-bot>=22.7
# ============================================================

import os
import asyncio
import random
import string
import time
import datetime
import threading
import html
import psycopg2
from flask import Flask, request, jsonify
from telethon import TelegramClient, events
from telethon.sessions import StringSession
import telegram
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
)
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
DEVELOPER_USERNAME = os.environ.get("DEVELOPER_USERNAME", "@NEXEX_99")
APP_NAME           = os.environ.get("APP_NAME", "SuperToolsX")
TG_BOT_LINK        = os.environ.get("TG_BOT_LINK", "https://t.me/SUPER_WORKER_KEY_99_bot")

# ── FORCE JOIN CONFIG ──
FORCE_CHANNEL_USERNAME = "@SUPER_WORKERS"  # চ্যানেলের ইউজারনেম
FORCE_CHANNEL_LINK     = "https://t.me/SUPER_WORKERS"

# ConversationHandler states
CAPTCHA_STATE      = 1
CUSTOM_KEY_DAYS    = 2
USER_KEY_DURATION  = 3
SET_LIMIT_STATE    = 4
SET_ADMIN_STATE    = 5

# Admin settings (in-memory)
_admin_free_key_hours  = {"value": 24}
_admin_daily_key_limit = {"value": 1}

# Pending captcha answers
_captcha_pending = {}

# ══════════════════════════════════════════════════════════
#  UI HELPERS
# ══════════════════════════════════════════════════════════

def header(title: str, emoji: str = "🛡️") -> str:
    line = "▰" * 11
    return (
        f"{line}\n"
        f"  {emoji}  <b>{title}</b>  {emoji}\n"
        f"{line}\n"
    )

def divider() -> str:
    return "┄" * 22 + "\n"

def footer() -> str:
    return f"\n╰─ 👨‍💻 Dev: {DEVELOPER_USERNAME}"

def progress_bar(current: int, total: int, length: int = 10) -> str:
    filled = int(length * current / total) if total else 0
    bar = "█" * filled + "░" * (length - filled)
    pct = int(100 * current / total) if total else 0
    return f"[{bar}] {pct}%"

def esc(text) -> str:
    return html.escape(str(text) if text is not None else "")

def btn(text: str, callback_data: str = None, url: str = None,
        style: str = None) -> InlineKeyboardButton:
    kwargs = {"text": text}
    if url:
        kwargs["url"] = url
    else:
        kwargs["callback_data"] = callback_data or "noop"
    if style:
        kwargs["style"] = style
    return InlineKeyboardButton(**kwargs)

# ── Force Join Check Helper ──
async def is_joined(update: Update, ctx: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
    """ইউজার চ্যানেলে জয়েন করেছে কিনা চেক করে"""
    try:
        member = await ctx.bot.get_chat_member(FORCE_CHANNEL_USERNAME, user_id)
        if member.status in ['left', 'kicked']:
            return False
        return True
    except Exception as e:
        print(f"Force Join Check Error: {e}", flush=True)
        # যদি বট অ্যাডমিন না থাকে বা চ্যানেল না পায়, তবে ইউজারকে ঢুকতে দেবে
        return False


# ══════════════════════════════════════════════════════════
#  DB SETUP
# ══════════════════════════════════════════════════════════

def get_db():
    return psycopg2.connect(DATABASE_URL)


# ══════════════════════════════════════════════════════════
#  AUTO SELL HELPER
# ══════════════════════════════════════════════════════════

def is_task_off_message(text):
    """Bot থেকে আসা 'task off' বা 'conversation reset' message detect করে।"""
    if not text:
        return False
    low = text.lower()
    patterns = [
        "conversation was reset",
        "please start again",
        "start again from the main menu",
        "previous conversation",
        "session expired",
        "task is off", "tasks are off",
        "task not available", "no task available",
        "temporarily unavailable",
        "try again later",
        "under maintenance",
    ]
    return any(p in low for p in patterns)


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


def check_key_usage_limit(user_id: int) -> tuple:
    conn = get_db(); cur = conn.cursor()
    cur.execute(
        "SELECT key_count, last_reset FROM user_key_usage WHERE user_id = %s",
        (str(user_id),)
    )
    row = cur.fetchone()
    now   = int(time.time())
    limit = _admin_daily_key_limit["value"]

    if row is None:
        cur.close(); conn.close()
        return True, "ok"

    key_count, last_reset = row
    if now - last_reset >= 86400:
        cur.close(); conn.close()
        return True, "ok"

    if limit > 0 and key_count >= limit:
        reset_in = 86400 - (now - last_reset)
        hours_r  = reset_in // 3600
        mins_r   = (reset_in % 3600) // 60
        bar      = progress_bar(key_count, limit)
        cur.close(); conn.close()
        return False, (
            f"📊 আজকের ব্যবহার: {bar}\n\n"
            f"⛔ <b>{key_count}/{limit}</b> টি Key নেওয়া হয়েছে\n"
            f"🔄 <b>{hours_r}h {mins_r}m</b> পরে Reset হবে"
        )

    cur.close(); conn.close()
    return True, "ok"


def increment_key_usage(user_id: int):
    conn = get_db(); cur = conn.cursor()
    cur.execute(
        "SELECT key_count, last_reset FROM user_key_usage WHERE user_id = %s",
        (str(user_id),)
    )
    row = cur.fetchone()
    now = int(time.time())

    if row is None:
        cur.execute(
            "INSERT INTO user_key_usage (user_id, key_count, last_reset) VALUES (%s, 1, %s)",
            (str(user_id), now)
        )
    else:
        key_count, last_reset = row
        if now - last_reset >= 86400:
            cur.execute(
                "UPDATE user_key_usage SET key_count=1, last_reset=%s WHERE user_id=%s",
                (now, str(user_id))
            )
        else:
            cur.execute(
                "UPDATE user_key_usage SET key_count=key_count+1 WHERE user_id=%s",
                (str(user_id),)
            )
    conn.commit(); cur.close(); conn.close()


def _fmt_duration(days: float) -> str:
    total_secs = int(days * 86400)
    if total_secs >= 86400:
        return f"{int(total_secs // 86400)} দিন"
    return f"{int(total_secs // 3600)} ঘন্টা"


def is_admin(uid: int) -> bool:
    return uid in ADMIN_IDS


# ══════════════════════════════════════════════════════════
#  FLASK ENDPOINT — /validate_key
# ══════════════════════════════════════════════════════════

@app.route("/validate_key", methods=["POST"])
def api_validate_key():
    data   = request.json or {}
    key    = (data.get("key") or "").strip().upper()
    dev_id = data.get("device_id", "unknown")
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
            "tg_username": info["tg_username"],
            "tg_name"    : info["tg_name"],
            "tg_id"      : info["tg_id"],
        })
    return jsonify({"valid": False, "message": msg}), 200


# ══════════════════════════════════════════════════════════
#  TELEGRAM BOT HANDLERS
# ══════════════════════════════════════════════════════════

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user  = update.effective_user
    
    # ✅ Force Join Check
    joined = await is_joined(update, ctx, user.id)
    if not joined:
        await update.message.reply_text(
            f"{header('JOIN REQUIRED', '⚠️')}"
            f"🚀 বটটি ব্যবহার করতে আপনাকে আমাদের চ্যানেলে জয়েন করতে হবে:\n\n"
            f"👇 নিচের বাটনে ক্লিক করে জয়েন করুন:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [btn("📢 Join Channel", url=FORCE_CHANNEL_LINK, style="primary")],
                [btn("✅ Joined (Check Again)", callback_data="check_join", style="success")]
            ])
        )
        return

    name  = esc(user.first_name or "বন্ধু")
    limit = _admin_daily_key_limit["value"]
    hours = _admin_free_key_hours["value"]
    admin = is_admin(user.id)

    await update.message.reply_text(
        f"{header(APP_NAME + ' License', '🛡️')}"
        f"👋 স্বাগতম, <b>{name}!</b>\n\n"
        f"┌─────────────────────\n"
        f"│ 🔑  Key / দিন :  <b>{'∞ Unlimited' if limit == 0 else f'{limit}টি / দিন'}</b>\n"
        f"│ ⏱️  মেয়াদ     :  <b>{hours} ঘন্টা</b>\n"
        f"│ 🔒  Device    :  একটি ফোন\n"
        f"└─────────────────────\n"
        f"{footer()}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            [
                [btn("🔑  GET NEW KEY", callback_data="get_new_key", style="success")],
                (
                    [btn("⚙️  ADMIN PANEL", callback_data="admin_panel", style="danger")]
                    if admin else []
                ),
                [
                    btn("ℹ️ Info",    callback_data="info",    style="primary"),
                    btn("📞 Support", callback_data="support", style="primary"),
                ],
            ]
        )
    )


# ── "Joined" বাটনে ক্লিক করলে এই ফাংশন চলবে ──
async def cb_check_join(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    joined = await is_joined(update, ctx, query.from_user.id)
    if not joined:
        await query.answer("❌ আপনি এখনো চ্যানেলে জয়েন করেননি!", show_alert=True)
        return
        
    await query.answer("✅ ধন্যবাদ! আপনি সফলভাবে জয়েন করেছেন।", show_alert=True)
    
    user  = query.from_user
    name  = esc(user.first_name or "বন্ধু")
    limit = _admin_daily_key_limit["value"]
    hours = _admin_free_key_hours["value"]
    admin = is_admin(user.id)

    await query.edit_message_text(
        f"{header(APP_NAME + ' License', '🛡️')}"
        f"👋 স্বাগতম, <b>{name}!</b>\n\n"
        f"┌─────────────────────\n"
        f"│ 🔑  Key / দিন :  <b>{'∞ Unlimited' if limit == 0 else f'{limit}টি / দিন'}</b>\n"
        f"│ ⏱️  মেয়াদ     :  <b>{hours} ঘন্টা</b>\n"
        f"│ 🔒  Device    :  একটি ফোন\n"
        f"└─────────────────────\n"
        f"{footer()}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            [
                [btn("🔑  GET NEW KEY", callback_data="get_new_key", style="success")],
                (
                    [btn("⚙️  ADMIN PANEL", callback_data="admin_panel", style="danger")]
                    if admin else []
                ),
                [
                    btn("ℹ️ Info",    callback_data="info",    style="primary"),
                    btn("📞 Support", callback_data="support", style="primary"),
                ],
            ]
        )
    )


async def cb_get_new_key(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user  = query.from_user

    # ✅ ক্যাপচা দেওয়ার আগেও আবার চেক (যদি কেউ মাঝখানে লিভ করে)
    joined = await is_joined(update, ctx, user.id)
    if not joined:
        await query.answer("❌ আগে চ্যানেলে জয়েন করুন!", show_alert=True)
        await cb_check_join(update, ctx)
        return ConversationHandler.END

    allowed, err_msg = check_key_usage_limit(user.id)
    if not allowed:
        await query.edit_message_text(
            f"{header('LIMIT REACHED', '🚫')}{err_msg}\n{footer()}",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                [[btn("🔙 Back", callback_data="back_start", style="primary")]]
            )
        )
        return ConversationHandler.END

    emojis = ["🍎", "🍌", "🚗", "🐶", "🐱", "🍕", "⚽", "🎈", "🌟", "🔥"]
    e1, e2 = random.sample(emojis, 2)
    a = random.randint(10, 99)
    b = random.randint(10, 99)
    
    question_text = f"{e1} {a}  +  {e2} {b}"
    correct_ans = a + b
    
    _captcha_pending[user.id] = (correct_ans, time.time() + 120)

    await query.edit_message_text(
        f"{header('CAPTCHA চ্যালেঞ্জ', '🤖')}"
        f"🧮  <b>{question_text}  =  ?</b>\n\n"
        f"✏️ সঠিক উত্তর <b>শুধু সংখ্যায়</b> টাইপ করে পাঠান\n"
        f"⏱️ সময় বাকি: <b>২ মিনিট</b>\n"
        f"{divider()}"
        f"<i>/cancel দিয়ে বাতিল করুন</i>",
        parse_mode="HTML"
    )
    return CAPTCHA_STATE


async def handle_captcha(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user    = update.effective_user
    uid     = user.id
    text    = update.message.text.strip()
    pending = _captcha_pending.get(uid)

    if not pending:
        await update.message.reply_text("⚠️ আগে /start দিয়ে শুরু করুন।")
        return ConversationHandler.END

    correct_ans, expiry = pending
    if time.time() > expiry:
        del _captcha_pending[uid]
        await update.message.reply_text(
            f"{header('TIME OUT!', '⏰')}"
            f"CAPTCHA-র সময় শেষ।\n/start দিয়ে আবার চেষ্টা করুন।",
            parse_mode="HTML"
        )
        return ConversationHandler.END

    if not text.isdigit() or int(text) != correct_ans:
        await update.message.reply_text(
            f"❌ <b>ভুল উত্তর!</b>\n\nআবার চেষ্টা করুন 👇\n"
            f"<i>শুধু সঠিক সংখ্যাটি টাইপ করুন</i>",
            parse_mode="HTML"
        )
        return CAPTCHA_STATE

    del _captcha_pending[uid]
    increment_key_usage(uid)

    tg_username = user.username or ""
    tg_name     = (user.first_name or "") + (" " + (user.last_name or "") if user.last_name else "")
    tg_id       = str(user.id)

    hours   = _admin_free_key_hours["value"]
    days    = hours / 24.0
    key     = create_license_key(days,
                                  tg_username=tg_username,
                                  tg_name=tg_name.strip(),
                                  tg_id=tg_id)
    exp     = datetime.datetime.now() + datetime.timedelta(hours=hours)
    exp_str = exp.strftime("%d/%m/%Y %H:%M")

    if tg_username:
        user_line = f"│ 👤  @{esc(tg_username)}\n"
    else:
        user_line = f"│ 👤  {esc(tg_name.strip() or tg_id)}\n"

    await update.message.reply_text(
        f"{header('KEY GENERATED ✅', '🎉')}"
        f"┌─────────────────────\n"
        f"{user_line}"
        f"│ ⏱️  মেয়াদ  :  <b>{_fmt_duration(days)}</b>\n"
        f"│ 📅  Expire :  <b>{exp_str}</b>\n"
        f"│ 🔒  Lock   :  একটি Device\n"
        f"└─────────────────────\n\n"
        f"🔑 <b>Your License Key:</b>\n"
        f"<code>{key}</code>\n\n"
        f"📋 <i>Key copy করে App-এ দিন</i>\n"
        f"{footer()}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            [[btn("🔙 Back", callback_data="back_start", style="primary")]]
        )
    )
    return ConversationHandler.END


async def cb_info(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    hours = _admin_free_key_hours["value"]
    limit = _admin_daily_key_limit["value"]
    limit_line = "∞ Unlimited" if limit == 0 else f"{limit}টি / দিন"
    await query.edit_message_text(
        f"{header('APP INFO', 'ℹ️')}"
        f"┌─────────────────────\n"
        f"│ 📱  App    :  <b>{esc(APP_NAME)}</b>\n"
        f"│ 🔑  Limit  :  <b>{limit_line}</b>\n"
        f"│ ⏱️  মেয়াদ  :  <b>{hours} ঘন্টা</b>\n"
        f"│ 🔒  Device :  একটি ফোন\n"
        f"└─────────────────────\n"
        f"{footer()}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            [[btn("🔙 Back", callback_data="back_start", style="primary")]]
        )
    )


async def cb_support(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        f"{header('SUPPORT', '📞')}"
        f"সমস্যায় পড়লে নিচে যোগাযোগ করুন:\n\n"
        f"👤 <b>Developer:</b> {esc(DEVELOPER_USERNAME)}\n"
        f"🔗 {esc(TG_BOT_LINK)}\n"
        f"{footer()}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [btn("📩 Contact Dev", url=TG_BOT_LINK, style="primary")],
            [btn("🔙 Back", callback_data="back_start", style="primary")],
        ])
    )


async def cb_back_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user  = query.from_user
    limit = _admin_daily_key_limit["value"]
    hours = _admin_free_key_hours["value"]
    admin = is_admin(user.id)
    limit_line = "∞ Unlimited" if limit == 0 else f"{limit}টি / দিন"

    inline_kb = [
        [btn("🔑  GET NEW KEY", callback_data="get_new_key", style="success")],
    ]
    if admin:
        inline_kb.append([btn("⚙️  ADMIN PANEL", callback_data="admin_panel", style="danger")])
    inline_kb.append([
        btn("ℹ️ Info",    callback_data="info",    style="primary"),
        btn("📞 Support", callback_data="support", style="primary"),
    ])

    await query.edit_message_text(
        f"{header(APP_NAME + ' License', '🛡️')}"
        f"┌─────────────────────\n"
        f"│ 🔑  Key / দিন :  <b>{limit_line}</b>\n"
        f"│ ⏱️  মেয়াদ     :  <b>{hours} ঘন্টা</b>\n"
        f"│ 🔒  Device    :  একটি ফোন\n"
        f"└─────────────────────\n"
        f"{footer()}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_kb)
    )


# ══════════════════════════════════════════════════
#  ADMIN PANEL
# ══════════════════════════════════════════════════

async def _send_admin_panel_msg(msg_obj, edit=False):
    limit = _admin_daily_key_limit["value"]
    hours = _admin_free_key_hours["value"]
    conn  = get_db(); cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM license_keys")
    total_keys = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM license_keys WHERE is_active=TRUE AND expires_at > %s", (int(time.time()),))
    active_keys = cur.fetchone()[0]
    cur.close(); conn.close()

    keyboard = [
        [
            btn("🔐 Custom Key", callback_data="admin_custom_key",   style="success"),
            btn("⏱️ Duration",   callback_data="admin_set_duration", style="primary"),
        ],
        [
            btn("🚦 Set Limit",  callback_data="admin_set_limit",    style="primary"),
            btn("📋 Keys List",  callback_data="admin_list_keys",    style="primary"),
        ],
        [
            btn("👑 SET ADMIN",  callback_data="admin_set_admin",    style="danger"),
        ],
        [btn("🔙 Back", callback_data="back_start", style="primary")],
    ]
    text = (
        f"{header('ADMIN PANEL', '⚙️')}"
        f"┌─────────────────────\n"
        f"│ ⏱️  Free duration :  <b>{hours}h</b>\n"
        f"│ 🚦  Daily limit   :  <b>{limit if limit > 0 else '∞'}</b>\n"
        f"│ 🔑  Total keys    :  <b>{total_keys}</b>\n"
        f"│ ✅  Active keys   :  <b>{active_keys}</b>\n"
        f"│ 👑  Total admins  :  <b>{len(ADMIN_IDS)}</b>\n"
        f"└─────────────────────\n"
        f"{footer()}"
    )
    if edit:
        await msg_obj.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await msg_obj.reply_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))


async def cb_admin_panel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        await query.answer("❌ Access Denied!", show_alert=True); return
    await _send_admin_panel_msg(query, edit=True)


async def cb_admin_custom_key(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id): return
    await query.edit_message_text(
        f"{header('CUSTOM KEY', '🔐')}"
        f"কত <b>দিনের</b> Key বানাবেন?\n\n"
        f"│ <code>10</code>   → ১০ দিন\n"
        f"│ <code>1</code>    → ১ দিন\n"
        f"│ <code>0.5</code>  → ১২ ঘন্টা\n"
        f"│ <code>30</code>   → ১ মাস\n"
        f"{divider()}"
        f"<i>সংখ্যাটি টাইপ করুন 👇</i>",
        parse_mode="HTML"
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
        await update.message.reply_text(
            "❌ সংখ্যা দিন (যেমন: <code>10</code> বা <code>0.5</code>)",
            parse_mode="HTML"
        )
        return CUSTOM_KEY_DAYS
    key     = create_license_key(days)
    exp     = datetime.datetime.now() + datetime.timedelta(days=days)
    exp_str = exp.strftime("%d/%m/%Y %H:%M")
    await update.message.reply_text(
        f"{header('CUSTOM KEY CREATED ✅', '🔐')}"
        f"🔑 <b>Key:</b>\n<code>{key}</code>\n\n"
        f"│ ⏱️  মেয়াদ  :  <b>{_fmt_duration(days)}</b>\n"
        f"│ 📅  Expire :  <b>{exp_str}</b>\n"
        f"{footer()}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            [[btn("🔙 Admin Panel", callback_data="admin_panel", style="primary")]]
        )
    )
    return ConversationHandler.END


async def cb_admin_set_duration(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id): return
    cur_h = _admin_free_key_hours["value"]
    await query.edit_message_text(
        f"{header('KEY DURATION SET', '⏱️')}"
        f"বর্তমান মেয়াদ: <b>{cur_h} ঘন্টা</b>\n\n"
        f"User 'GET NEW KEY' চাপলে কত <b>ঘন্টার</b> Key পাবে?\n\n"
        f"│ <code>1</code>   → ১ ঘন্টা\n"
        f"│ <code>24</code>  → ১ দিন\n"
        f"│ <code>72</code>  → ৩ দিন\n"
        f"│ <code>168</code> → ৭ দিন\n"
        f"{divider()}"
        f"<i>সংখ্যাটি টাইপ করুন 👇</i>",
        parse_mode="HTML"
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
        await update.message.reply_text(
            "❌ পূর্ণসংখ্যা দিন (যেমন: <code>24</code>)",
            parse_mode="HTML"
        )
        return USER_KEY_DURATION
    _admin_free_key_hours["value"] = hours
    await update.message.reply_text(
        f"✅ <b>Duration Updated!</b>\n\n"
        f"User এখন থেকে <b>{hours} ঘন্টার</b> Key পাবে।",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            [[btn("🔙 Admin Panel", callback_data="admin_panel", style="primary")]]
        )
    )
    return ConversationHandler.END


async def cb_admin_set_limit(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id): return
    current = _admin_daily_key_limit["value"]
    cur_label = "Unlimited ∞" if current == 0 else f"{current}টি"
    await query.edit_message_text(
        f"{header('SET DAILY LIMIT', '🚦')}"
        f"বর্তমান Limit: <b>{cur_label}</b>\n\n"
        f"প্রতি User ২৪ ঘন্টায় কয়টি Key নিতে পারবে?\n\n"
        f"│ <code>0</code> → Unlimited ∞\n"
        f"│ <code>1</code> → দিনে ১টি\n"
        f"│ <code>3</code> → দিনে ৩টি\n"
        f"│ <code>5</code> → দিনে ৫টি\n"
        f"{divider()}"
        f"<i>সংখ্যাটি টাইপ করুন 👇</i>",
        parse_mode="HTML"
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
        await update.message.reply_text(
            "❌ সংখ্যা দিন (<code>0</code> = unlimited)",
            parse_mode="HTML"
        )
        return SET_LIMIT_STATE
    _admin_daily_key_limit["value"] = limit
    label = "∞ Unlimited" if limit == 0 else f"<b>{limit}টি</b>"
    await update.message.reply_text(
        f"✅ <b>Limit Updated!</b>\n\n"
        f"প্রতি User প্রতিদিন {label} Key নিতে পারবে।\n"
        f"🔄 ২৪ ঘন্টা পর Automatic Reset।",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            [[btn("🔙 Admin Panel", callback_data="admin_panel", style="primary")]]
        )
    )
    return ConversationHandler.END


async def cb_admin_set_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        await query.answer("❌ Access Denied!", show_alert=True)
        return ConversationHandler.END

    admin_list_str = "\n".join([f"│ 👑  <code>{aid}</code>" for aid in ADMIN_IDS])

    await query.edit_message_text(
        f"{header('SET ADMIN', '👑')}"
        f"বর্তমান Admin তালিকা:\n"
        f"{admin_list_str}\n\n"
        f"{divider()}"
        f"নতুন Admin যোগ করতে তার <b>User ID</b> বা <b>@username</b> পাঠান:\n\n"
        f"│ উদাহরণ: <code>123456789</code>\n"
        f"│ অথবা: <code>@username</code>\n\n"
        f"<i>/cancel দিয়ে বাতিল করুন</i>",
        parse_mode="HTML"
    )
    return SET_ADMIN_STATE


async def handle_set_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid  = update.effective_user.id
    if not is_admin(uid):
        return ConversationHandler.END

    text = update.message.text.strip()

    if text.startswith("@"):
        username = text.lstrip("@")
        try:
            chat = await ctx.bot.get_chat(f"@{username}")
            new_admin_id = chat.id
            new_admin_name = f"@{username}"
        except Exception as e:
            await update.message.reply_text(
                f"❌ <b>Username পাওয়া যায়নি!</b>\n\n"
                f"Error: <code>{esc(str(e)[:100])}</code>\n\n"
                f"সরাসরি Numeric <b>User ID</b> দিন।",
                parse_mode="HTML"
            )
            return SET_ADMIN_STATE
    elif text.isdigit():
        new_admin_id   = int(text)
        new_admin_name = str(new_admin_id)
    else:
        await update.message.reply_text(
            "❌ <b>সঠিক ID বা @username দিন!</b>\n\n"
            "উদাহরণ: <code>123456789</code> বা <code>@username</code>",
            parse_mode="HTML"
        )
        return SET_ADMIN_STATE

    if new_admin_id in ADMIN_IDS:
        safe_name = esc(new_admin_name)
        await update.message.reply_text(
            f"⚠️ <b>{safe_name}</b> ইতিমধ্যে Admin আছে!",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                [[btn("🔙 Admin Panel", callback_data="admin_panel", style="primary")]]
            )
        )
        return ConversationHandler.END

    ADMIN_IDS.append(new_admin_id)

    await update.message.reply_text(
        f"{header('ADMIN ADDED ✅', '👑')}"
        f"🎉 নতুন Admin যোগ হয়েছে!\n\n"
        f"│ 👑  ID     :  <code>{new_admin_id}</code>\n"
        f"│ 📊  মোট   :  <b>{len(ADMIN_IDS)}</b> জন Admin\n"
        f"{divider()}"
        f"⚠️ <i>Note: Server restart হলে এই change হারিয়ে যাবে।</i>\n"
        f"<i>Permanent করতে ADMIN_IDS env variable আপডেট করুন।</i>\n"
        f"{footer()}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            [[btn("🔙 Admin Panel", callback_data="admin_panel", style="primary")]]
        )
    )
    return ConversationHandler.END


async def cb_admin_list_keys(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id): return
    conn = get_db(); cur = conn.cursor()
    cur.execute(
        "SELECT key, expires_at, is_active, device_id, tg_username FROM license_keys ORDER BY created_at DESC LIMIT 10"
    )
    rows = cur.fetchall(); cur.close(); conn.close()
    if not rows:
        await query.edit_message_text(
            f"{header('KEYS LIST', '📋')}কোনো Key নেই।",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                [[btn("🔙 Admin Panel", callback_data="admin_panel", style="primary")]]
            )
        )
        return
    now   = int(time.time())
    lines = [f"{header('শেষ ১০টি Key', '📋')}"]
    for i, r in enumerate(rows, 1):
        k, exp, active, dev, tg_user = r
        ok      = active and exp > now
        status  = "🟢" if ok else "🔴"
        rem     = max(0, exp - now)
        d, h    = rem // 86400, (rem % 86400) // 3600
        dev_str = "🔒 Locked" if dev else "🔓 Free"
        user_str = f"@{esc(tg_user)}" if tg_user else "—"
        lines.append(
            f"{status} <b>#{i}</b> <code>{k[-12:]}</code>\n"
            f"   👤 {user_str}  |  ⏱ {d}d {h}h  |  {dev_str}"
        )
    await query.edit_message_text(
        "\n".join(lines) + footer(),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            [[btn("🔙 Admin Panel", callback_data="admin_panel", style="primary")]]
        )
    )


async def cmd_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    _captcha_pending.pop(uid, None)
    await update.message.reply_text(
        "❌ <b>বাতিল করা হয়েছে।</b>\n\n/start দিয়ে আবার শুরু করুন।",
        parse_mode="HTML"
    )
    return ConversationHandler.END


# ══════════════════════════════════════════════════
#  BOT RUNNER (With Timeout Fix + Infinite Retry)
# ══════════════════════════════════════════════════
def run_license_bot():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def _run():
        bot_app = None
        while True:
            try:
                bot_app = (
                    Application.builder()
                    .token(LICENSE_BOT_TOKEN)
                    .connect_timeout(30.0)
                    .read_timeout(30.0)
                    .write_timeout(30.0)
                    .pool_timeout(30.0)
                    .get_updates_read_timeout(30.0)
                    .build()
                )

                conv = ConversationHandler(
                    entry_points=[
                        CallbackQueryHandler(cb_get_new_key,        pattern="^get_new_key$"),
                        CallbackQueryHandler(cb_admin_custom_key,   pattern="^admin_custom_key$"),
                        CallbackQueryHandler(cb_admin_set_duration, pattern="^admin_set_duration$"),
                        CallbackQueryHandler(cb_admin_set_limit,    pattern="^admin_set_limit$"),
                        CallbackQueryHandler(cb_admin_set_admin,    pattern="^admin_set_admin$"),
                    ],
                    states={
                        CAPTCHA_STATE:    [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_captcha)],
                        CUSTOM_KEY_DAYS:  [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_custom_key_days)],
                        USER_KEY_DURATION:[MessageHandler(filters.TEXT & ~filters.COMMAND, handle_set_duration)],
                        SET_LIMIT_STATE:  [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_set_limit)],
                        SET_ADMIN_STATE:  [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_set_admin)],
                    },
                    fallbacks=[CommandHandler("cancel", cmd_cancel)],
                    allow_reentry=True,
                )

                bot_app.add_handler(CommandHandler("start", cmd_start))
                bot_app.add_handler(CallbackQueryHandler(cb_check_join,      pattern="^check_join$"))
                bot_app.add_handler(CallbackQueryHandler(cb_admin_panel,    pattern="^admin_panel$"))
                bot_app.add_handler(CallbackQueryHandler(cb_admin_list_keys,pattern="^admin_list_keys$"))
                bot_app.add_handler(CallbackQueryHandler(cb_back_start,     pattern="^back_start$"))
                bot_app.add_handler(CallbackQueryHandler(cb_info,           pattern="^info$"))
                bot_app.add_handler(CallbackQueryHandler(cb_support,        pattern="^support$"))
                bot_app.add_handler(conv)

                print("[LICENSE BOT] ✅ Bot starting...", flush=True)

                for attempt in range(5):
                    try:
                        await bot_app.initialize()
                        print(f"[LICENSE BOT] ✅ Initialize OK (attempt {attempt+1})", flush=True)
                        break
                    except Exception as e:
                        print(f"[LICENSE BOT] ⚠️ Initialize attempt {attempt+1} failed: {e}", flush=True)
                        if attempt == 4:
                            raise
                        await asyncio.sleep(10)

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
                if bot_app:
                    try:
                        if bot_app.updater and bot_app.updater.running:
                            await bot_app.updater.stop()
                        if bot_app.running:
                            await bot_app.stop()
                        await bot_app.shutdown()
                    except Exception:
                        pass
                print("[LICENSE BOT] 🔄 Restarting in 15 seconds...", flush=True)
                await asyncio.sleep(15)

    try:
        loop.run_until_complete(_run())
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()


# ══════════════════════════════════════════════════════════
#  EXISTING FLASK ENDPOINTS
# ══════════════════════════════════════════════════════════

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
                api_id=EXCLUDED.api_id, api_hash=EXCLUDED.api_hash,
                phone_code_hash=EXCLUDED.phone_code_hash, temp_session=EXCLUDED.temp_session
        """, (phone, str(api_id), api_hash, phone_code_hash, temp_session))
        conn.commit(); cur.close(); conn.close()
        return jsonify({"status": "otp_sent", "phone": phone})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


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
                session_string=EXCLUDED.session_string, api_id=EXCLUDED.api_id,
                api_hash=EXCLUDED.api_hash, target_username=EXCLUDED.target_username
        """, (tg_user_id, session_string, str(api_id), api_hash, target_username))
        cur.execute("DELETE FROM pending_otp WHERE phone = %s", (phone,))
        conn.commit(); cur.close(); conn.close()
        return jsonify({"status": "success", "message": "Session saved!"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/automate_sale", methods=["POST"])
def automate_sale():
    data       = request.json
    tg_user_id = data["tg_user_id"]
    twofa_key  = data.get("twofa_key", "").strip()
    cookie     = data.get("cookie", "").strip()

    if not twofa_key:
        return jsonify({"status": "error", "message": "2FA key দরকার।"}), 400
    if not cookie:
        return jsonify({"status": "error", "message": "Cookie দরকার।"}), 400

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
        import re as _re
        client = TelegramClient(StringSession(session_string), int(api_id), api_hash)
        await client.connect()
        if not await client.is_user_authorized():
            await client.disconnect()
            raise RuntimeError("Session expire হয়েছে।")

        sold = False
        step = {"current": 0}
        too_often_retry = {"count": 0, "max": 5}

        async def try_click_or_send(msg, btn_labels, fallback_text):
            """বাটন ক্লিক করার চেষ্টা করে, না পেলে text পাঠায়"""
            wanted = [l.lower() for l in btn_labels]
            for button_row in (msg.buttons or []):
                for button in button_row:
                    bt = (getattr(button, "text", "") or "").strip()
                    if any(w in bt.lower() for w in wanted):
                        try:
                            await msg.click(text=bt)
                            return True
                        except Exception:
                            pass
            if fallback_text:
                await client.send_message(BOT, fallback_text)
                return True
            return False

        @client.on(events.NewMessage(from_users=BOT))
        async def handler(event):
            nonlocal sold
            if sold:
                return
            msg  = event.message
            text = msg.text or ""
            low  = text.lower()

            # ⭐ Task off detect
            if is_task_off_message(text):
                step["current"] = -1
                print(f"[AUTOMATE_SALE] Task off: {text[:80]}", flush=True)
                return

            # Rate limit হ্যান্ডেল
            if "too often" in low or ("please wait" in low and "report" not in low):
                nums = _re.findall(r'\d+', text)
                wait_sec = int(nums[0]) + 2 if nums else 35
                too_often_retry["count"] += 1
                if too_often_retry["count"] <= too_often_retry["max"]:
                    step["current"] = 0
                    await asyncio.sleep(wait_sec)
                    await client.send_message(BOT, "/start")
                return

            # STEP 0 → 1: Welcome message
            if step["current"] == 0 and "welcome" in low:
                step["current"] = 1
                await asyncio.sleep(1)
                await try_click_or_send(msg, ["tasks", "task"], "📋 Tasks")

            # STEP 1 → 2: Task selection menu
            elif step["current"] == 1 and "please select a task" in low:
                step["current"] = 2
                await asyncio.sleep(1)
                await try_click_or_send(msg, ["🍪", "cookie"], "🍪 ($0.0280)")

            # STEP 2 → 3: Cookie task list দেখালে 2FA task বেছে নাও
            elif step["current"] == 2 and "🍪" in text:
                step["current"] = 3
                await asyncio.sleep(1)
                await try_click_or_send(
                    msg,
                    ["2fa", "create fb", "no mail"],
                    "🌟2FA:Create FB (No mail) ($0.0280)"
                )

            # STEP 3 → 4: Task description দেখালে Start দাও
            elif step["current"] == 3 and ("description" in low or "required" in low or "review time" in low):
                step["current"] = 4
                await asyncio.sleep(1)
                await try_click_or_send(msg, ["start", "▶️"], "▶️ Start")

            # STEP 4 → 5: 2FA key চাইলে key পাঠাও
            elif step["current"] == 4 and ("2fa key" in low or "enter your 2fa" in low or "2fa" in low):
                step["current"] = 5
                await asyncio.sleep(1)
                await client.send_message(BOT, twofa_key)

            # STEP 5 → 6: OTP/code দেখালে এবং cookie চাইলে cookie পাঠাও
            elif step["current"] == 5 and (
                "send the account" in low or
                "please send" in low or
                "one-time code" in low or
                "tap the code" in low or
                ("🍪" in text and "send" in low)
            ):
                step["current"] = 6
                await asyncio.sleep(1.5)
                await client.send_message(BOT, cookie)

            # STEP 6 → 7: Confirm registration button আসলে click করো
            elif step["current"] == 6 and (
                "confirm registration" in low or
                "press the button" in low or
                "cancel the task" in low
            ):
                step["current"] = 7
                await asyncio.sleep(1)
                await try_click_or_send(
                    msg,
                    ["account registered", "✅ account", "registered"],
                    "✅ Account registered"
                )

            # STEP 7 → 8: সফলভাবে জমা হলে
            elif step["current"] >= 6 and (
                "report has been received" in low or
                "your report has been received" in low or
                "task submitted successfully" in low or
                "submitted successfully" in low or
                "received! please wait" in low or
                "received" in low and "wait" in low
            ):
                step["current"] = 8
                sold = True
                if target_username:
                    try:
                        await client.send_message(
                            target_username,
                            f"🎉 Account Sold!\n2FA Key: {twofa_key}"
                        )
                    except Exception:
                        pass

        await client.send_message(BOT, "/start")
        for _ in range(600):
            await asyncio.sleep(1)
            if step["current"] == 8:
                break
            if step["current"] == -1:  # ⭐ task_off
                break
        client.remove_event_handler(handler)
        await client.disconnect()
        return sold, step["current"]

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        sold, last_step = loop.run_until_complete(_sell())
        loop.close()
        if sold:
            conn2 = get_db(); cur2 = conn2.cursor()
            cur2.execute("""
                INSERT INTO sell_stats (user_id, sell_count) VALUES (%s, 1)
                ON CONFLICT (user_id) DO UPDATE SET sell_count = sell_stats.sell_count + 1
            """, (tg_user_id,))
            conn2.commit(); cur2.close(); conn2.close()
            return jsonify({"status": "success", "message": "Sale সম্পন্ন! ✅"})
        if last_step == -1:  # ⭐ task_off
            return jsonify({"status": "task_off", "retry_after_seconds": 300})
        return jsonify({"status": "timeout", "message": f"Flow incomplete। Step: {last_step}/8"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ══════════════════════════════════════════════════════════
#  AUTO SELL — /auto_sell  (সম্পূর্ণ আলাদা endpoint)
#  /automate_sale এর সাথে কোনো সম্পর্ক নেই।
# ══════════════════════════════════════════════════════════

@app.route("/auto_sell", methods=["POST"])
def auto_sell_endpoint():
    """
    AUTO SELL Panel এর জন্য আলাদা endpoint।
    /automate_sale এর মতোই bot এ sell করে, কিন্তু:
    - task_off detect করে আলাদা response দেয়
    - rate_limit এ wait_seconds দেয়
    - session_expired detect করে
    - সম্পূর্ণ স্বাধীন ফাংশন
    """
    data = request.json or {}
    tg_user_id = data.get("tg_user_id", "").strip()
    twofa_key  = data.get("twofa_key", "").strip()
    cookie     = data.get("cookie", "").strip()

    if not tg_user_id:
        return jsonify({"status": "error", "message": "tg_user_id প্রয়োজন"}), 400
    if not twofa_key:
        return jsonify({"status": "error", "message": "2FA key প্রয়োজন"}), 400
    if not cookie or "c_user=" not in cookie:
        return jsonify({"status": "error", "message": "Cookie invalid"}), 400

    # ── Session DB থেকে নাও ──
    conn = get_db(); cur = conn.cursor()
    cur.execute(
        "SELECT session_string, api_id, api_hash, target_username "
        "FROM user_sessions WHERE user_id = %s",
        (tg_user_id,)
    )
    row = cur.fetchone(); cur.close(); conn.close()

    if not row:
        return jsonify({
            "status": "session_expired",
            "message": "User session নেই — আগে Connect করুন"
        }), 404

    session_string, api_id, api_hash, target_username = row

    # ── Sell flow (Telethon দিয়ে) ──
    async def _auto_sell():
        import re as _re
        client = TelegramClient(StringSession(session_string), int(api_id), api_hash)
        await client.connect()

        if not await client.is_user_authorized():
            await client.disconnect()
            return "session_expired", "Session expire হয়েছে", 0

        sold = False
        task_off = False
        rate_limit_secs = 0
        step = {"current": 0}
        too_often_retry = {"count": 0, "max": 3}

        async def try_click_or_send(msg, btn_labels, fallback_text):
            wanted = [l.lower() for l in btn_labels]
            for button_row in (msg.buttons or []):
                for button in button_row:
                    bt = (getattr(button, "text", "") or "").strip()
                    if any(w in bt.lower() for w in wanted):
                        try:
                            await msg.click(text=bt)
                            return True
                        except Exception:
                            pass
            if fallback_text:
                await client.send_message(BOT, fallback_text)
                return True
            return False

        @client.on(events.NewMessage(from_users=BOT))
        async def handler(event):
            nonlocal sold, task_off, rate_limit_secs
            if sold or task_off:
                return
            msg  = event.message
            text = msg.text or ""
            low  = text.lower()

            # ⭐ Task off detect
            if is_task_off_message(text):
                task_off = True
                print(f"[AUTO_SELL] Task off: {text[:80]}", flush=True)
                return

            # Rate limit detect
            if "too often" in low or ("please wait" in low and "report" not in low):
                nums = _re.findall(r'\d+', text)
                wait_s = int(nums[0]) + 2 if nums else 35
                too_often_retry["count"] += 1
                if too_often_retry["count"] <= too_often_retry["max"]:
                    step["current"] = 0
                    await asyncio.sleep(wait_s)
                    rate_limit_secs = wait_s
                    await client.send_message(BOT, "/start")
                else:
                    rate_limit_secs = wait_s
                return

            # STEP 0 → 1: Welcome
            if step["current"] == 0 and "welcome" in low:
                step["current"] = 1
                await asyncio.sleep(1)
                await try_click_or_send(msg, ["tasks", "task"], "📋 Tasks")

            # STEP 1 → 2: Task menu
            elif step["current"] == 1 and "please select a task" in low:
                step["current"] = 2
                await asyncio.sleep(1)
                await try_click_or_send(msg, ["🍪", "cookie"], "🍪 ($0.0280)")

            # STEP 2 → 3: Cookie list → 2FA task
            elif step["current"] == 2 and "🍪" in text:
                step["current"] = 3
                await asyncio.sleep(1)
                await try_click_or_send(
                    msg,
                    ["2fa", "create fb", "no mail"],
                    "🌟2FA:Create FB (No mail) ($0.0280)"
                )

            # STEP 3 → 4: Task description → Start
            elif step["current"] == 3 and (
                "description" in low or "required" in low or "review time" in low
            ):
                step["current"] = 4
                await asyncio.sleep(1)
                await try_click_or_send(msg, ["start", "▶️"], "▶️ Start")

            # STEP 4 → 5: 2FA key চাওয়া
            elif step["current"] == 4 and (
                "2fa key" in low or "enter your 2fa" in low or "2fa" in low
            ):
                step["current"] = 5
                await asyncio.sleep(1)
                await client.send_message(BOT, twofa_key)

            # STEP 5 → 6: Cookie চাওয়া
            elif step["current"] == 5 and (
                "send the account" in low
                or "please send" in low
                or "one-time code" in low
                or ("🍪" in text and "send" in low)
            ):
                step["current"] = 6
                await asyncio.sleep(1.5)
                await client.send_message(BOT, cookie)

            # STEP 6 → 7: Confirm registration
            elif step["current"] == 6 and (
                "confirm registration" in low
                or "press the button" in low
            ):
                step["current"] = 7
                await asyncio.sleep(1)
                await try_click_or_send(
                    msg,
                    ["account registered", "✅ account", "registered"],
                    "✅ Account registered"
                )

            # STEP 7 → 8: Success
            elif step["current"] >= 6 and (
                "report has been received" in low
                or "task submitted successfully" in low
                or "submitted successfully" in low
                or ("received" in low and "wait" in low)
            ):
                step["current"] = 8
                sold = True

        await client.send_message(BOT, "/start")
        for _ in range(300):  # 5 min max
            await asyncio.sleep(1)
            if step["current"] == 8:
                break
            if task_off:
                break
            if rate_limit_secs > 0 and too_often_retry["count"] > too_often_retry["max"]:
                break

        client.remove_event_handler(handler)
        await client.disconnect()

        if sold:
            return "success", "Sale সম্পন্ন", 0
        if task_off:
            return "task_off", "Conversation reset — task নেই", 300
        if rate_limit_secs > 0:
            return "rate_limit", "Rate limited", rate_limit_secs
        return "timeout", f"Step: {step['current']}/8", 0

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result_status, result_msg, wait_secs = loop.run_until_complete(_auto_sell())
        loop.close()

        if result_status == "success":
            # Stats update
            conn2 = get_db(); cur2 = conn2.cursor()
            cur2.execute("""
                INSERT INTO sell_stats (user_id, sell_count) VALUES (%s, 1)
                ON CONFLICT (user_id) DO UPDATE SET
                    sell_count = sell_stats.sell_count + 1
            """, (tg_user_id,))
            conn2.commit(); cur2.close(); conn2.close()

            if target_username:
                try:
                    loop2 = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop2)
                    loop2.run_until_complete(_notify_sold(target_username, twofa_key))
                    loop2.close()
                except Exception:
                    pass

            return jsonify({
                "status": "success",
                "message": "✅ Sale সম্পন্ন!"
            })

        if result_status == "task_off":
            return jsonify({
                "status": "task_off",
                "message": result_msg,
                "retry_after_seconds": wait_secs
            })

        if result_status == "rate_limit":
            return jsonify({
                "status": "rate_limit",
                "message": result_msg,
                "wait_seconds": wait_secs
            })

        if result_status == "session_expired":
            return jsonify({
                "status": "session_expired",
                "message": result_msg
            })

        return jsonify({
            "status": "timeout",
            "message": result_msg
        })

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


async def _notify_sold(target_username, twofa_key):
    """AUTO SELL সফল হলে target user কে Telegram এ notify করো।"""
    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute(
            "SELECT session_string, api_id, api_hash FROM user_sessions WHERE user_id = %s",
            (target_username,)
        )
        row = cur.fetchone(); cur.close(); conn.close()
        if row:
            client = TelegramClient(StringSession(row[0]), int(row[1]), row[2])
            await client.connect()
            await client.send_message(
                target_username,
                f"🎉 AUTO SELL সফল!\n2FA Key: {twofa_key}"
            )
            await client.disconnect()
    except Exception:
        pass


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
                        await msg.click(text=button_text); return True
            if fallback:
                await client.send_message(COOKIE_SELL_BOT, fallback); return True
            return False

        too_often_retry = {"count": 0, "max": 5}

        async def handler(event):
            nonlocal sold
            if sold: return
            msg  = event.message
            text = msg.text or ""
            low  = text.lower()

            # Rate limit হ্যান্ডেল
            if "too often" in low or ("please wait" in low and "report" not in low):
                import re as _re2
                nums = _re2.findall(r'\d+', text)
                wait_sec = int(nums[0]) + 2 if nums else 35
                too_often_retry["count"] += 1
                if too_often_retry["count"] <= too_often_retry["max"]:
                    step["current"] = 0
                    await asyncio.sleep(wait_sec)
                    await client.send_message(COOKIE_SELL_BOT, "/start")
                return

            if step["current"] == 0 and ("welcome" in low or "gotask pay" in low or "this bot helps" in low):
                step["current"] = 1; await asyncio.sleep(0.8)
                await click_or_send(msg, ["task", "tasks"], "📋 Tasks")
            elif step["current"] == 1 and ("which platform" in low or "platform" in low or "select" in low):
                step["current"] = 2; await asyncio.sleep(0.8)
                await click_or_send(msg, ["facebook"], "Facebook")
            elif step["current"] == 2 and ("fb cookies" in low or "facebook" in low or "cookie" in low):
                step["current"] = 3; await asyncio.sleep(0.8)
                await click_or_send(msg, ["fb cookies", "cookie"], "Fb Cookies (4 BDT)")
            elif step["current"] == 3 and ("submit uid" in low or "uid" in low):
                step["current"] = 4; await asyncio.sleep(0.8)
                await click_or_send(msg, ["submit uid", "uid"], "Submit UID 🆔")
            elif step["current"] == 4 and ("send me the uid" in low or "send uid" in low or "send your uid" in low):
                step["current"] = 5; await asyncio.sleep(0.8)
                await client.send_message(COOKIE_SELL_BOT, uid)
            elif step["current"] == 5 and ("uid received" in low or "uid" in low and "received" in low):
                step["current"] = 6; await asyncio.sleep(0.8)
                await client.send_message(COOKIE_SELL_BOT, cookie)
            elif step["current"] == 6 and ("cookies received" in low or "cookie received" in low or "received" in low):
                step["current"] = 7; await asyncio.sleep(0.8)
                await click_or_send(msg, ["complete and submit", "complete", "submit"], "Complete and Submit")
            elif step["current"] >= 6 and (
                "task submitted successfully" in low or
                "submitted successfully" in low or
                "report has been received" in low or
                "your report has been received" in low or
                "received! please wait" in low or
                ("received" in low and "wait" in low)
            ):
                step["current"] = 8; sold = True
                if target_username:
                    try:
                        await client.send_message(
                            target_username,
                            f"🎉 Cookie Task Submitted!\nUID: {uid}\nBot: {COOKIE_SELL_BOT}"
                        )
                    except Exception:
                        pass

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
        conn = get_db(); cur = conn.cursor()
        cur.execute("DELETE FROM user_sessions WHERE user_id = %s", (tg_user_id,))
        conn.commit(); cur.close(); conn.close()
        return jsonify({"status": "invalid", "message": "Session expire হয়েছে।"})
    except Exception as e:
        return jsonify({"status": "invalid", "message": str(e)})


@app.route("/ping", methods=["GET", "POST"])
def ping():
    return jsonify({"status": "ok", "message": "Server is alive!"}), 200

@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "running", "message": "Auto Server is running!"}), 200


# ══════════════════════════════════════════════════
#  BOT THREAD
# ══════════════════════════════════════════════════
bot_thread = threading.Thread(target=run_license_bot, daemon=True)
bot_thread.start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
