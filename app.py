# ============================================================
# FILE: app.py  — UPGRADED UI VERSION (Color Buttons + SET ADMIN)
# Requirements: flask, telethon, psycopg2-binary, python-telegram-bot>=22.7
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
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
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
LICENSE_BOT_TOKEN  = os.environ.get("LICENSE_BOT_TOKEN", "9285384211:AAFmdMQcxF5kU0EUIXyRue8nBkrlD_4r6ak")
ADMIN_IDS          = list(map(int, os.environ.get("ADMIN_IDS", "8301781046").split(",")))
DEVELOPER_USERNAME = os.environ.get("DEVELOPER_USERNAME", "@NEXEX_99")
APP_NAME           = os.environ.get("APP_NAME", "SuperToolsX")
TG_BOT_LINK        = os.environ.get("TG_BOT_LINK", "https://t.me/SUPER_WORKER_KEY_99_bot")

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
        f"  {emoji}  *{title}*  {emoji}\n"
        f"{line}\n"
    )

def divider() -> str:
    return "┄" * 22 + "\n"

def footer() -> str:
    return f"\n╰─ 👨‍💻 Dev: {DEVELOPER_USERNAME}"

def progress_bar(current: int, total: int, length: int = 10) -> str:
    filled = int(length * current / total)
    bar = "█" * filled + "░" * (length - filled)
    pct = int(100 * current / total)
    return f"[{bar}] {pct}%"

def main_reply_keyboard(is_admin_user: bool = False) -> ReplyKeyboardMarkup:
    rows = [[KeyboardButton("🔑 GET NEW KEY")]]
    if is_admin_user:
        rows.append([KeyboardButton("⚙️ ADMIN PANEL")])
    rows.append([KeyboardButton("ℹ️ INFO"), KeyboardButton("📞 SUPPORT")])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True, one_time_keyboard=False)

# ── Colored InlineKeyboardButton helper ──
# style: "primary" = blue, "success" = green, "danger" = red
# Requires python-telegram-bot >= 22.7 (Bot API 9.4+)
def btn(text: str, callback_data: str = None, url: str = None,
        style: str = None) -> InlineKeyboardButton:
    kwargs = {"text": text}
    if url:
        kwargs["url"] = url
    else:
        kwargs["callback_data"] = callback_data or "noop"
    if style:
        kwargs["style"] = style   # এটাই মূল ফিক্স
    return InlineKeyboardButton(**kwargs)

# ══════════════════════════════════════════════════════════
#  DB SETUP
# ══════════════════════════════════════════════════════════

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


def check_and_increment_key_usage(user_id: int) -> tuple[bool, str]:
    conn = get_db(); cur = conn.cursor()
    cur.execute(
        "SELECT key_count, last_reset FROM user_key_usage WHERE user_id = %s",
        (str(user_id),)
    )
    row = cur.fetchone()
    now   = int(time.time())
    limit = _admin_daily_key_limit["value"]

    if row is None:
        cur.execute(
            "INSERT INTO user_key_usage (user_id, key_count, last_reset) VALUES (%s, 1, %s)",
            (str(user_id), now)
        )
        conn.commit(); cur.close(); conn.close()
        return True, "ok"

    key_count, last_reset = row
    if now - last_reset >= 86400:
        cur.execute(
            "UPDATE user_key_usage SET key_count=1, last_reset=%s WHERE user_id=%s",
            (now, str(user_id))
        )
        conn.commit(); cur.close(); conn.close()
        return True, "ok"

    if limit > 0 and key_count >= limit:
        reset_in = 86400 - (now - last_reset)
        hours_r  = reset_in // 3600
        mins_r   = (reset_in % 3600) // 60
        bar      = progress_bar(key_count, limit)
        cur.close(); conn.close()
        return False, (
            f"📊 আজকের ব্যবহার: {bar}\n\n"
            f"⛔ *{key_count}/{limit}* টি Key নেওয়া হয়েছে\n"
            f"🔄 *{hours_r}h {mins_r}m* পরে Reset হবে"
        )

    cur.execute(
        "UPDATE user_key_usage SET key_count=key_count+1 WHERE user_id=%s",
        (str(user_id),)
    )
    conn.commit(); cur.close(); conn.close()
    return True, "ok"


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

# ── /start ──
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user  = update.effective_user
    name  = user.first_name or "বন্ধু"
    limit = _admin_daily_key_limit["value"]
    hours = _admin_free_key_hours["value"]
    admin = is_admin(user.id)

    # Reply keyboard (bottom bar)
    await update.message.reply_text(
        "🔽 *নিচের মেনু থেকে অপশন বেছে নিন:*",
        parse_mode="Markdown",
        reply_markup=main_reply_keyboard(admin)
    )

    # Inline keyboard — colored buttons (Bot API 9.4 / PTB v22.7+)
    inline_kb = [
        [btn("🔑  GET NEW KEY", callback_data="get_new_key", style="success")],
        [
            btn("ℹ️ Info",    callback_data="info",    style="primary"),
            btn("📞 Support", callback_data="support", style="primary"),
        ],
    ]
    if admin:
        inline_kb.insert(1, [btn("⚙️  ADMIN PANEL", callback_data="admin_panel", style="danger")])

    limit_line = f"∞ Unlimited" if limit == 0 else f"{limit}টি / দিন"

    await update.message.reply_text(
        f"{header(APP_NAME + ' License', '🛡️')}"
        f"👋 স্বাগতম, *{name}!*\n\n"
        f"┌─────────────────────\n"
        f"│ 🔑  Key / দিন :  *{limit_line}*\n"
        f"│ ⏱️  মেয়াদ     :  *{hours} ঘন্টা*\n"
        f"│ 🔒  Device    :  একটি ফোন\n"
        f"└─────────────────────\n"
        f"{footer()}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_kb)
    )


# ── Reply keyboard shortcut handler ──
async def handle_reply_kb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text  = update.message.text
    user  = update.effective_user
    admin = is_admin(user.id)

    if text == "🔑 GET NEW KEY":
        allowed, msg = check_and_increment_key_usage(user.id)
        if not allowed:
            await update.message.reply_text(
                f"{header('LIMIT REACHED', '🚫')}{msg}{footer()}",
                parse_mode="Markdown"
            )
            return ConversationHandler.END

        a = random.randint(10, 99)
        b = random.randint(10, 99)
        _captcha_pending[user.id] = (a + b, time.time() + 120)
        await update.message.reply_text(
            f"{header('CAPTCHA চ্যালেঞ্জ', '🤖')}"
            f"🧮  *{a}  +  {b}  =  ?*\n\n"
            f"✏️ সঠিক উত্তর পাঠান\n"
            f"⏱️ সময় বাকি: *২ মিনিট*\n"
            f"{divider()}"
            f"_/cancel টাইপ করে বাতিল করুন_",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardRemove()
        )
        return CAPTCHA_STATE

    elif text == "⚙️ ADMIN PANEL" and admin:
        await _send_admin_panel_msg(update.message)

    elif text == "ℹ️ INFO":
        await update.message.reply_text(
            f"{header('APP INFO', 'ℹ️')}"
            f"📱 *App:* {APP_NAME}\n"
            f"🤖 *Bot:* {DEVELOPER_USERNAME}\n"
            f"🔗 *Link:* {TG_BOT_LINK}\n"
            f"{divider()}"
            f"🔒 প্রতিটি Key একটি Device-এ লক হয়\n"
            f"⏳ মেয়াদ শেষে Key কাজ করবে না\n"
            f"{footer()}",
            parse_mode="Markdown"
        )

    elif text == "📞 SUPPORT":
        await update.message.reply_text(
            f"{header('SUPPORT', '📞')}"
            f"সমস্যায় পড়লে Developer-কে নক করুন:\n\n"
            f"👤 {DEVELOPER_USERNAME}\n"
            f"🔗 {TG_BOT_LINK}\n"
            f"{footer()}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                btn("📩 Contact Dev", url=TG_BOT_LINK, style="primary")
            ]])
        )


# ── GET NEW KEY (inline button) → CAPTCHA ──
async def cb_get_new_key(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user  = query.from_user

    allowed, msg = check_and_increment_key_usage(user.id)
    if not allowed:
        await query.edit_message_text(
            f"{header('LIMIT REACHED', '🚫')}{msg}{footer()}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(
                [[btn("🔙 Back", callback_data="back_start", style="primary")]]
            )
        )
        return ConversationHandler.END

    a      = random.randint(10, 99)
    b      = random.randint(10, 99)
    _captcha_pending[user.id] = (a + b, time.time() + 120)

    await query.edit_message_text(
        f"{header('CAPTCHA চ্যালেঞ্জ', '🤖')}"
        f"🧮  *{a}  +  {b}  =  ?*\n\n"
        f"✏️ সঠিক উত্তর *টাইপ করে পাঠান*\n"
        f"⏱️ সময় বাকি: *২ মিনিট*\n"
        f"{divider()}"
        f"_/cancel দিয়ে বাতিল করুন_",
        parse_mode="Markdown"
    )
    return CAPTCHA_STATE


async def handle_captcha(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user    = update.effective_user
    uid     = user.id
    text    = update.message.text.strip()
    pending = _captcha_pending.get(uid)

    if not pending:
        await update.message.reply_text(
            "⚠️ আগে /start দিয়ে শুরু করুন।",
            reply_markup=main_reply_keyboard(is_admin(uid))
        )
        return ConversationHandler.END

    correct_ans, expiry = pending
    if time.time() > expiry:
        del _captcha_pending[uid]
        await update.message.reply_text(
            f"{header('TIME OUT!', '⏰')}"
            f"CAPTCHA-র সময় শেষ।\n/start দিয়ে আবার চেষ্টা করুন।",
            parse_mode="Markdown",
            reply_markup=main_reply_keyboard(is_admin(uid))
        )
        return ConversationHandler.END

    if not text.isdigit() or int(text) != correct_ans:
        await update.message.reply_text(
            f"❌ *ভুল উত্তর!*\n\nআবার চেষ্টা করুন 👇\n"
            f"_সঠিক সংখ্যাটি টাইপ করুন_",
            parse_mode="Markdown"
        )
        return CAPTCHA_STATE

    del _captcha_pending[uid]

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
        user_line = f"│ 👤  @{tg_username}\n"
    else:
        user_line = f"│ 👤  {tg_name.strip() or tg_id}\n"

    await update.message.reply_text(
        f"{header('KEY GENERATED ✅', '🎉')}"
        f"┌─────────────────────\n"
        f"{user_line}"
        f"│ ⏱️  মেয়াদ  :  *{_fmt_duration(days)}*\n"
        f"│ 📅  Expire :  *{exp_str}*\n"
        f"│ 🔒  Lock   :  একটি Device\n"
        f"└─────────────────────\n\n"
        f"🔑 *Your License Key:*\n"
        f"`{key}`\n\n"
        f"📋 _Key copy করে App-এ দিন_\n"
        f"{footer()}",
        parse_mode="Markdown",
        reply_markup=main_reply_keyboard(is_admin(uid))
    )
    return ConversationHandler.END


# ── Info & Support inline ──
async def cb_info(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    hours = _admin_free_key_hours["value"]
    limit = _admin_daily_key_limit["value"]
    limit_line = "∞ Unlimited" if limit == 0 else f"{limit}টি / দিন"
    await query.edit_message_text(
        f"{header('APP INFO', 'ℹ️')}"
        f"┌─────────────────────\n"
        f"│ 📱  App    :  *{APP_NAME}*\n"
        f"│ 🔑  Limit  :  *{limit_line}*\n"
        f"│ ⏱️  মেয়াদ  :  *{hours} ঘন্টা*\n"
        f"│ 🔒  Device :  একটি ফোন\n"
        f"└─────────────────────\n"
        f"{footer()}",
        parse_mode="Markdown",
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
        f"👤 *Developer:* {DEVELOPER_USERNAME}\n"
        f"🔗 {TG_BOT_LINK}\n"
        f"{footer()}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [btn("📩 Contact Dev", url=TG_BOT_LINK, style="primary")],
            [btn("🔙 Back", callback_data="back_start", style="primary")],
        ])
    )


# ── Back ──
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
        [
            btn("ℹ️ Info",    callback_data="info",    style="primary"),
            btn("📞 Support", callback_data="support", style="primary"),
        ],
    ]
    if admin:
        inline_kb.insert(1, [btn("⚙️  ADMIN PANEL", callback_data="admin_panel", style="danger")])

    await query.edit_message_text(
        f"{header(APP_NAME + ' License', '🛡️')}"
        f"┌─────────────────────\n"
        f"│ 🔑  Key / দিন :  *{limit_line}*\n"
        f"│ ⏱️  মেয়াদ     :  *{hours} ঘন্টা*\n"
        f"│ 🔒  Device    :  একটি ফোন\n"
        f"└─────────────────────\n"
        f"{footer()}",
        parse_mode="Markdown",
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

    # Admin Panel buttons — color coded:
    # 🔐 Custom Key   → success (green)
    # ⏱️ Duration     → primary (blue)
    # 🚦 Set Limit    → primary (blue)
    # 📋 Keys List    → primary (blue)
    # 👑 Set Admin    → danger  (red) — powerful action
    # 🔙 Back         → primary (blue)
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
        f"│ ⏱️  Free duration :  *{hours}h*\n"
        f"│ 🚦  Daily limit   :  *{limit if limit > 0 else '∞'}*\n"
        f"│ 🔑  Total keys    :  *{total_keys}*\n"
        f"│ ✅  Active keys   :  *{active_keys}*\n"
        f"│ 👑  Total admins  :  *{len(ADMIN_IDS)}*\n"
        f"└─────────────────────\n"
        f"{footer()}"
    )
    if edit:
        await msg_obj.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await msg_obj.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))


async def cb_admin_panel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        await query.answer("❌ Access Denied!", show_alert=True); return
    await _send_admin_panel_msg(query, edit=True)


# ── CUSTOM KEY ──
async def cb_admin_custom_key(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id): return
    await query.edit_message_text(
        f"{header('CUSTOM KEY', '🔐')}"
        f"কত *দিনের* Key বানাবেন?\n\n"
        f"│ `10`   → ১০ দিন\n"
        f"│ `1`    → ১ দিন\n"
        f"│ `0.5`  → ১২ ঘন্টা\n"
        f"│ `30`   → ১ মাস\n"
        f"{divider()}"
        f"_সংখ্যাটি টাইপ করুন 👇_",
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
        await update.message.reply_text("❌ সংখ্যা দিন (যেমন: `10` বা `0.5`)", parse_mode="Markdown")
        return CUSTOM_KEY_DAYS
    key     = create_license_key(days)
    exp     = datetime.datetime.now() + datetime.timedelta(days=days)
    exp_str = exp.strftime("%d/%m/%Y %H:%M")
    await update.message.reply_text(
        f"{header('CUSTOM KEY CREATED ✅', '🔐')}"
        f"🔑 *Key:*\n`{key}`\n\n"
        f"│ ⏱️  মেয়াদ  :  *{_fmt_duration(days)}*\n"
        f"│ 📅  Expire :  *{exp_str}*\n"
        f"{footer()}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(
            [[btn("🔙 Admin Panel", callback_data="admin_panel", style="primary")]]
        )
    )
    return ConversationHandler.END


# ── DURATION ──
async def cb_admin_set_duration(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id): return
    cur_h = _admin_free_key_hours["value"]
    await query.edit_message_text(
        f"{header('KEY DURATION SET', '⏱️')}"
        f"বর্তমান মেয়াদ: *{cur_h} ঘন্টা*\n\n"
        f"User 'GET NEW KEY' চাপলে কত *ঘন্টার* Key পাবে?\n\n"
        f"│ `1`   → ১ ঘন্টা\n"
        f"│ `24`  → ১ দিন\n"
        f"│ `72`  → ৩ দিন\n"
        f"│ `168` → ৭ দিন\n"
        f"{divider()}"
        f"_সংখ্যাটি টাইপ করুন 👇_",
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
        await update.message.reply_text("❌ পূর্ণসংখ্যা দিন (যেমন: `24`)", parse_mode="Markdown")
        return USER_KEY_DURATION
    _admin_free_key_hours["value"] = hours
    await update.message.reply_text(
        f"✅ *Duration Updated!*\n\n"
        f"User এখন থেকে *{hours} ঘন্টার* Key পাবে।",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(
            [[btn("🔙 Admin Panel", callback_data="admin_panel", style="primary")]]
        )
    )
    return ConversationHandler.END


# ── SET LIMIT ──
async def cb_admin_set_limit(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id): return
    current = _admin_daily_key_limit["value"]
    cur_label = "Unlimited ∞" if current == 0 else f"{current}টি"
    await query.edit_message_text(
        f"{header('SET DAILY LIMIT', '🚦')}"
        f"বর্তমান Limit: *{cur_label}*\n\n"
        f"প্রতি User ২৪ ঘন্টায় কয়টি Key নিতে পারবে?\n\n"
        f"│ `0` → Unlimited ∞\n"
        f"│ `1` → দিনে ১টি\n"
        f"│ `3` → দিনে ৩টি\n"
        f"│ `5` → দিনে ৫টি\n"
        f"{divider()}"
        f"_সংখ্যাটি টাইপ করুন 👇_",
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
        await update.message.reply_text("❌ সংখ্যা দিন (`0` = unlimited)", parse_mode="Markdown")
        return SET_LIMIT_STATE
    _admin_daily_key_limit["value"] = limit
    label = "∞ Unlimited" if limit == 0 else f"*{limit}টি*"
    await update.message.reply_text(
        f"✅ *Limit Updated!*\n\n"
        f"প্রতি User প্রতিদিন {label} Key নিতে পারবে।\n"
        f"🔄 ২৪ ঘন্টা পর Automatic Reset।",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(
            [[btn("🔙 Admin Panel", callback_data="admin_panel", style="primary")]]
        )
    )
    return ConversationHandler.END


# ══════════════════════════════════════════════════
#  SET ADMIN — নতুন feature
# ══════════════════════════════════════════════════

async def cb_admin_set_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        await query.answer("❌ Access Denied!", show_alert=True)
        return ConversationHandler.END

    # বর্তমান admin list দেখানো
    admin_list_str = "\n".join([f"│ 👑  `{aid}`" for aid in ADMIN_IDS])

    await query.edit_message_text(
        f"{header('SET ADMIN', '👑')}"
        f"বর্তমান Admin তালিকা:\n"
        f"{admin_list_str}\n\n"
        f"{divider()}"
        f"নতুন Admin যোগ করতে তার *User ID* বা *@username* পাঠান:\n\n"
        f"│ উদাহরণ: `123456789`\n"
        f"│ অথবা: `@username`\n\n"
        f"_/cancel দিয়ে বাতিল করুন_",
        parse_mode="Markdown"
    )
    return SET_ADMIN_STATE


async def handle_set_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid  = update.effective_user.id
    if not is_admin(uid):
        return ConversationHandler.END

    text = update.message.text.strip()

    # Username দিলে — bot দিয়ে ID খোঁজার চেষ্টা
    if text.startswith("@"):
        username = text.lstrip("@")
        try:
            chat = await ctx.bot.get_chat(f"@{username}")
            new_admin_id = chat.id
            new_admin_name = f"@{username}"
        except Exception as e:
            await update.message.reply_text(
                f"❌ *Username পাওয়া যায়নি!*\n\n"
                f"Error: `{str(e)[:100]}`\n\n"
                f"সরাসরি Numeric *User ID* দিন।",
                parse_mode="Markdown"
            )
            return SET_ADMIN_STATE
    elif text.isdigit():
        new_admin_id   = int(text)
        new_admin_name = f"`{new_admin_id}`"
    else:
        await update.message.reply_text(
            "❌ *সঠিক ID বা @username দিন!*\n\n"
            "উদাহরণ: `123456789` বা `@username`",
            parse_mode="Markdown"
        )
        return SET_ADMIN_STATE

    if new_admin_id in ADMIN_IDS:
        await update.message.reply_text(
            f"⚠️ *{new_admin_name}* ইতিমধ্যে Admin আছে!",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(
                [[btn("🔙 Admin Panel", callback_data="admin_panel", style="primary")]]
            )
        )
        return ConversationHandler.END

    ADMIN_IDS.append(new_admin_id)

    await update.message.reply_text(
        f"{header('ADMIN ADDED ✅', '👑')}"
        f"🎉 নতুন Admin যোগ হয়েছে!\n\n"
        f"│ 👑  ID     :  `{new_admin_id}`\n"
        f"│ 📊  মোট   :  *{len(ADMIN_IDS)}* জন Admin\n"
        f"{divider()}"
        f"⚠️ _Note: Server restart হলে এই change হারিয়ে যাবে।_\n"
        f"_Permanent করতে ADMIN\\_IDS env variable আপডেট করুন।_"
        f"{footer()}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(
            [[btn("🔙 Admin Panel", callback_data="admin_panel", style="primary")]]
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
        "SELECT key, expires_at, is_active, device_id, tg_username FROM license_keys ORDER BY created_at DESC LIMIT 10"
    )
    rows = cur.fetchall(); cur.close(); conn.close()
    if not rows:
        await query.edit_message_text(
            f"{header('KEYS LIST', '📋')}কোনো Key নেই।",
            parse_mode="Markdown"
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
        user_str = f"@{tg_user}" if tg_user else "—"
        lines.append(
            f"{status} *#{i}* `{k[-12:]}`\n"
            f"   👤 {user_str}  |  ⏱ {d}d {h}h  |  {dev_str}"
        )
    await query.edit_message_text(
        "\n".join(lines) + footer(),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(
            [[btn("🔙 Admin Panel", callback_data="admin_panel", style="primary")]]
        )
    )


async def cmd_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    _captcha_pending.pop(uid, None)
    await update.message.reply_text(
        "❌ *বাতিল করা হয়েছে।*",
        parse_mode="Markdown",
        reply_markup=main_reply_keyboard(is_admin(uid))
    )
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
                    CallbackQueryHandler(cb_admin_set_admin,    pattern="^admin_set_admin$"),
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND & filters.Regex("^🔑 GET NEW KEY$"),
                        handle_reply_kb
                    ),
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
            bot_app.add_handler(CallbackQueryHandler(cb_admin_panel,    pattern="^admin_panel$"))
            bot_app.add_handler(CallbackQueryHandler(cb_admin_list_keys,pattern="^admin_list_keys$"))
            bot_app.add_handler(CallbackQueryHandler(cb_back_start,     pattern="^back_start$"))
            bot_app.add_handler(CallbackQueryHandler(cb_info,           pattern="^info$"))
            bot_app.add_handler(CallbackQueryHandler(cb_support,        pattern="^support$"))
            bot_app.add_handler(conv)

            # Reply keyboard shortcuts (outside conversation)
            bot_app.add_handler(MessageHandler(
                filters.TEXT & ~filters.COMMAND & filters.Regex("^(⚙️ ADMIN PANEL|ℹ️ INFO|📞 SUPPORT)$"),
                handle_reply_kb
            ))

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
#  EXISTING FLASK ENDPOINTS (unchanged)
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
                step["current"] = 1; await asyncio.sleep(1)
                await client.send_message(BOT, "📋 Tasks")
            elif "Please select a task" in text and step["current"] == 1:
                step["current"] = 2; await asyncio.sleep(1)
                await client.send_message(BOT, "🍪 ($0.0280)")
            elif "🍪:" in text and step["current"] == 2:
                step["current"] = 3; await asyncio.sleep(1)
                await client.send_message(BOT, "🌟2FA:Create FB (No mail) ($0.0280)")
            elif ("Description" in text or "REQUIRED" in text) and step["current"] == 3:
                step["current"] = 4; await asyncio.sleep(1)
                await client.send_message(BOT, "▶️ Start")
            elif ("2FA" in text or "2fa key" in text.lower()) and step["current"] == 4:
                step["current"] = 5; await asyncio.sleep(1)
                await client.send_message(BOT, twofa_key)
            elif ("send the account" in text.lower() or "🍪" in text) and step["current"] == 5:
                step["current"] = 6; await asyncio.sleep(1)
                await client.send_message(BOT, cookie)
            elif ("confirm registration" in text.lower() or "Press the button" in text) and step["current"] == 6:
                step["current"] = 7; await asyncio.sleep(1)
                try:
                    await msg.click(text="✅ Account registered")
                except Exception:
                    await client.send_message(BOT, "✅ Account registered")
            elif "report has been received" in text.lower() and step["current"] == 7:
                step["current"] = 8; sold = True
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
                step["current"] = 1; await asyncio.sleep(0.6)
                await click_or_send(msg, ["task"], "Task")
            elif step["current"] == 1 and ("which platform" in low or "platform" in low):
                step["current"] = 2; await asyncio.sleep(0.6)
                await click_or_send(msg, ["facebook"], "Facebook")
            elif step["current"] == 2 and ("fb cookies" in low or "facebook" in low):
                step["current"] = 3; await asyncio.sleep(0.6)
                await click_or_send(msg, ["fb cookies"], "Fb Cookies (4 BDT)")
            elif step["current"] == 3 and "submit uid" in low:
                step["current"] = 4; await asyncio.sleep(0.6)
                await click_or_send(msg, ["submit uid"], "Submit UID 🆔")
            elif step["current"] == 4 and ("send me the uid" in low or "send uid" in low):
                step["current"] = 5; await asyncio.sleep(0.6)
                await client.send_message(COOKIE_SELL_BOT, uid)
            elif step["current"] == 5 and "uid received" in low:
                step["current"] = 6; await asyncio.sleep(0.6)
                await client.send_message(COOKIE_SELL_BOT, cookie)
            elif step["current"] == 6 and "cookies received" in low:
                step["current"] = 7; await asyncio.sleep(0.6)
                await click_or_send(msg, ["complete and submit"], "Complete and Submit")
            elif step["current"] >= 6 and ("task submitted successfully" in low or "submitted successfully" in low):
                step["current"] = 8; sold = True
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
