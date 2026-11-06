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
LICENSE_BOT_TOKEN  = os.environ.get("LICENSE_BOT_TOKEN")
ADMIN_IDS          = list(map(int, os.environ.get("ADMIN_IDS", "8301781046").split(",")))
DEVELOPER_USERNAME = os.environ.get("DEVELOPER_USERNAME", "@NEXEX_99")
APP_NAME           = os.environ.get("APP_NAME", "SuperToolsX")
TG_BOT_LINK        = os.environ.get("TG_BOT_LINK", "https://t.me/SUPER_WORKER_KEY_99_bot")

# ── FORCE JOIN CONFIG ──
FORCE_CHANNEL_USERNAME = "@SUPER_WORKERS"
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
    # ✅ Bot API 9.4 — real button color (success=green / danger=red / primary=blue)
    if style in ("success", "danger", "primary"):
        kwargs["style"] = style
    return InlineKeyboardButton(**kwargs)

# ── Force Join Check Helper ──
# ★ FIX 2: Exception হলে True return করো
# আগে False ছিল — bot admin না থাকলে সব user blocked হয়ে যেত
async def is_joined(update: Update, ctx: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
    try:
        member = await ctx.bot.get_chat_member(FORCE_CHANNEL_USERNAME, user_id)
        if member.status in ['left', 'kicked']:
            return False
        return True
    except Exception as e:
        print(f"Force Join Check Error: {e}", flush=True)
        return True  # ★ FIX: False → True (bot admin না থাকলে ঢুকতে দেবে)


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
    # ★ FIX 3: sold_keys table — duplicate sell prevention এর জন্য
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sold_keys (
            id         SERIAL PRIMARY KEY,
            tg_user_id TEXT NOT NULL,
            twofa_key  TEXT NOT NULL,
            sold_at    BIGINT NOT NULL,
            UNIQUE(twofa_key)
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

    joined = await is_joined(update, ctx, user.id)
    if not joined:
        await update.message.reply_text(
            f"{header('JOIN REQUIRED', '⚠️')}"
            f"🚀 বটটি ব্যবহার করতে আপনাকে আমাদের চ্যানেলে জয়েন করতে হবে:\n\n"
            f"👇 নিচের বাটনে ক্লিক করে জয়েন করুন:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [btn("📢 Join Channel", url=FORCE_CHANNEL_LINK, style="success")],
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
                    [btn("⚙️  ADMIN PANEL", callback_data="admin_panel", style="primary")]
                    if admin else []
                ),
                [
                    btn("ℹ️ Info", callback_data="info", style="primary"),
                    btn("📞 Support", callback_data="support", style="primary"),
                ],
            ]
        )
    )


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
                    [btn("⚙️  ADMIN PANEL", callback_data="admin_panel", style="primary")]
                    if admin else []
                ),
                [
                    btn("ℹ️ Info", callback_data="info", style="primary"),
                    btn("📞 Support", callback_data="support", style="primary"),
                ],
            ]
        )
    )


async def cb_get_new_key(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user  = query.from_user

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
                [[btn("🔙 Back", callback_data="back_start", style="danger")]]
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
            [[btn("🔙 Back", callback_data="back_start", style="danger")]]
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
            [[btn("🔙 Back", callback_data="back_start", style="danger")]]
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
            [btn("🔙 Back", callback_data="back_start", style="danger")],
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
        inline_kb.append([btn("⚙️  ADMIN PANEL", callback_data="admin_panel", style="primary")])
    inline_kb.append([
        btn("ℹ️ Info", callback_data="info", style="primary"),
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
            btn("🔐 Custom Key", callback_data="admin_custom_key", style="success"),
            btn("⏱️ Duration", callback_data="admin_set_duration", style="primary"),
        ],
        [
            btn("🚦 Set Limit", callback_data="admin_set_limit", style="primary"),
            btn("📋 Keys List", callback_data="admin_list_keys", style="primary"),
        ],
        [
            btn("👑 SET ADMIN", callback_data="admin_set_admin", style="danger"),
        ],
        [btn("🔙 Back", callback_data="back_start", style="danger")],
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
            [[btn("🔙 Admin Panel", callback_data="admin_panel", style="danger")]]
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
            [[btn("🔙 Admin Panel", callback_data="admin_panel", style="danger")]]
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
            [[btn("🔙 Admin Panel", callback_data="admin_panel", style="danger")]]
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
                [[btn("🔙 Admin Panel", callback_data="admin_panel", style="danger")]]
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
            [[btn("🔙 Admin Panel", callback_data="admin_panel", style="danger")]]
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
                [[btn("🔙 Admin Panel", callback_data="admin_panel", style="danger")]]
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
            [[btn("🔙 Admin Panel", callback_data="admin_panel", style="danger")]]
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
                bot_app.add_handler(CallbackQueryHandler(cb_admin_panel,     pattern="^admin_panel$"))
                bot_app.add_handler(CallbackQueryHandler(cb_admin_list_keys, pattern="^admin_list_keys$"))
                bot_app.add_handler(CallbackQueryHandler(cb_back_start,      pattern="^back_start$"))
                bot_app.add_handler(CallbackQueryHandler(cb_info,            pattern="^info$"))
                bot_app.add_handler(CallbackQueryHandler(cb_support,         pattern="^support$"))
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

                # ★ FIX: পুরানো webhook/session clear করো — Conflict error ঠেকাতে
                try:
                    await bot_app.bot.delete_webhook(drop_pending_updates=True)
                    print("[LICENSE BOT] ✅ Webhook cleared.", flush=True)
                except Exception as e:
                    print(f"[LICENSE BOT] ⚠️ Webhook clear failed (ok): {e}", flush=True)

                # ★ FIX: Conflict হলে ৩০ সেকেন্ড অপেক্ষা করো — পুরানো instance বন্ধ হওয়ার জন্য
                await asyncio.sleep(30)

                await bot_app.start()
                await bot_app.updater.start_polling(
                    drop_pending_updates=True,
                    allowed_updates=Update.ALL_TYPES,
                    error_callback=lambda err: print(f"[LICENSE BOT] ⚠️ Poll error: {err}", flush=True),
                )
                print("[LICENSE BOT] ✅ Polling active!", flush=True)

                while True:
                    await asyncio.sleep(3600)

            except telegram.error.Conflict as e:
                # ★ FIX: Conflict error — পুরানো instance চলছে, বেশি অপেক্ষা করো
                print(f"[LICENSE BOT] ⚠️ Conflict detected, waiting 60s for old instance to die: {e}", flush=True)
                if bot_app:
                    try:
                        if bot_app.updater and bot_app.updater.running:
                            await bot_app.updater.stop()
                        if bot_app.running:
                            await bot_app.stop()
                        await bot_app.shutdown()
                    except Exception:
                        pass
                await asyncio.sleep(60)

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
    data     = request.get_json(silent=True) or {}
    api_id   = int(data.get("api_id", 0))
    api_hash = data.get("api_hash", "")
    phone    = data.get("phone", "")

    if not api_id or not api_hash or not phone:
        return jsonify({"status": "error", "message": "api_id, api_hash, phone দরকার।"}), 400

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
    data            = request.get_json(silent=True) or {}
    phone           = data.get("phone", "")
    otp             = data.get("otp", "")
    tg_user_id      = data.get("tg_user_id", "")
    target_username = data.get("target_username", "")

    if not phone or not otp or not tg_user_id:
        return jsonify({"status": "error", "message": "phone, otp, tg_user_id দরকার।"}), 400

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


# ══════════════════════════════════════════════════════════
# /automate_sale  ★ FIXED — Atomic lock (race condition proof)
# ══════════════════════════════════════════════════════════
# In-memory lock: একই key এর দুটো request একই সময়ে ঢুকলে
# দ্বিতীয়টা তাৎক্ষণিক reject হবে — DB hit করার আগেই।
_sale_in_progress = set()
_sale_lock = threading.Lock()

@app.route("/automate_sale", methods=["POST"])
def automate_sale():
    data       = request.get_json(silent=True) or {}
    tg_user_id = str(data.get("tg_user_id", "")).strip()
    twofa_key  = str(data.get("twofa_key", "")).strip()
    cookie     = str(data.get("cookie", "")).strip()

    if not tg_user_id or not twofa_key or not cookie:
        return jsonify({"status": "error", "message": "tg_user_id, twofa_key, cookie দরকার।"}), 400

    # ══ STEP 1: In-memory lock — race condition block ══
    # একই twofa_key নিয়ে দুটো thread একসাথে ঢুকতে পারবে না
    with _sale_lock:
        if twofa_key in _sale_in_progress:
            return jsonify({"status": "duplicate", "message": "এই key এখন process হচ্ছে!"}), 409
        _sale_in_progress.add(twofa_key)

    try:
        # ══ STEP 2: DB duplicate check ══
        conn = get_db(); cur = conn.cursor()
        cur.execute("SELECT id FROM sold_keys WHERE twofa_key = %s", (twofa_key,))
        already = cur.fetchone()
        cur.close(); conn.close()
        if already:
            return jsonify({"status": "duplicate", "message": "এই key আগেই sell হয়েছে!"}), 409

        # ══ STEP 3: ATOMIC LOCK — INSERT আগে, Telegram পরে ══
        # এটাই সবচেয়ে গুরুত্বপূর্ণ fix।
        # আগে sold_keys তে "pending" row ঢোকাও।
        # যদি অন্য request আগেই ঢুকিয়ে থাকে → INSERT fail → duplicate return।
        conn_lock = get_db(); cur_lock = conn_lock.cursor()
        try:
            cur_lock.execute("""
                INSERT INTO sold_keys (tg_user_id, twofa_key, sold_at)
                VALUES (%s, %s, %s)
            """, (tg_user_id, twofa_key, int(time.time())))
            conn_lock.commit()
        except Exception:
            # UNIQUE constraint violated → অন্য request আগেই insert করেছে
            conn_lock.rollback()
            cur_lock.close(); conn_lock.close()
            return jsonify({"status": "duplicate", "message": "এই key আগেই sell হয়েছে!"}), 409
        cur_lock.close(); conn_lock.close()

        # ══ STEP 4: Session load ══
        conn = get_db(); cur = conn.cursor()
        cur.execute(
            "SELECT session_string, api_id, api_hash, target_username FROM user_sessions WHERE user_id = %s",
            (tg_user_id,)
        )
        row = cur.fetchone(); cur.close(); conn.close()
        if not row:
            # Lock row মুছে দাও যেন পরে retry করা যায়
            conn_del = get_db(); cur_del = conn_del.cursor()
            cur_del.execute("DELETE FROM sold_keys WHERE twofa_key = %s", (twofa_key,))
            conn_del.commit(); cur_del.close(); conn_del.close()
            return jsonify({"status": "error", "message": "User not found."}), 404

        session_string, api_id, api_hash, target_username = row

        # ══ STEP 5: Telegram sell flow ══
        async def _sell():
            client = TelegramClient(StringSession(session_string), int(api_id), api_hash)
            await client.connect()

            if not await client.is_user_authorized():
                await client.disconnect()
                raise RuntimeError("Session expire হয়েছে। আবার connect করুন।")

            sold = False
            step = {"current": 0}
            too_often_retry = {"count": 0, "max": 5}

            @client.on(events.NewMessage(from_users=BOT))
            async def handler(event):
                nonlocal sold
                msg  = event.message
                text = msg.text or ""
                if sold: return
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
                    if target_username:
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
                # ══ STEP 6: sell_stats update (sold_keys ইতিমধ্যে STEP 3 এ insert হয়েছে) ══
                conn2 = get_db(); cur2 = conn2.cursor()
                cur2.execute("""
                    INSERT INTO sell_stats (user_id, sell_count) VALUES (%s, 1)
                    ON CONFLICT (user_id) DO UPDATE SET sell_count = sell_stats.sell_count + 1
                """, (tg_user_id,))
                conn2.commit(); cur2.close(); conn2.close()
                return jsonify({"status": "success", "message": "Sale সম্পন্ন!"})

            # Telegram flow সম্পন্ন হয়নি — lock row মুছে দাও যেন retry করা যায়
            conn_del = get_db(); cur_del = conn_del.cursor()
            cur_del.execute("DELETE FROM sold_keys WHERE twofa_key = %s", (twofa_key,))
            conn_del.commit(); cur_del.close(); conn_del.close()
            return jsonify({"status": "timeout", "message": "Flow incomplete।"})

        except Exception as e:
            # Exception হলেও lock row মুছে দাও
            try:
                conn_del = get_db(); cur_del = conn_del.cursor()
                cur_del.execute("DELETE FROM sold_keys WHERE twofa_key = %s", (twofa_key,))
                conn_del.commit(); cur_del.close(); conn_del.close()
            except Exception:
                pass
            return jsonify({"status": "error", "message": str(e)}), 500

    finally:
        # ══ সবসময় in-memory lock ছেড়ে দাও ══
        with _sale_lock:
            _sale_in_progress.discard(twofa_key)


@app.route("/automate_cookie_sale", methods=["POST"])
def automate_cookie_sale():
    # ★ Cookie sell permanently disabled — শুধু 2FA sell চালু আছে
    return jsonify({"status": "disabled", "message": "Cookie sell বন্ধ আছে। শুধু 2FA sell চালু।"}), 410


@app.route("/check_session", methods=["POST"])
def check_session():
    data       = request.get_json(silent=True) or {}
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
