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

# ── LICENSE BOT CONFIG (Environment Variables দাও) ──
LICENSE_BOT_TOKEN  = os.environ.get("LICENSE_BOT_TOKEN", "9285384211:AAF2tNUo5IpfTg9sEt2EJ8P9gTraXxcMOtI")
ADMIN_IDS          = list(map(int, os.environ.get("ADMIN_IDS", "8301781046").split(",")))
DEVELOPER_USERNAME = os.environ.get("DEVELOPER_USERNAME", "@SUPER_WORKER_KEY_99_bot")
APP_NAME           = os.environ.get("APP_NAME", "SuperToolsX")
TG_BOT_LINK        = os.environ.get("TG_BOT_LINK", "https://t.me/SUPER_WORKER_KEY_99_bot")

# ConversationHandler states
CAPTCHA_STATE      = 1
CUSTOM_KEY_DAYS    = 2
USER_KEY_DURATION  = 3

# Admin default duration for free keys (hours) — admin sets via bot
_admin_free_key_hours = {"value": 24}

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
            is_active   BOOLEAN DEFAULT TRUE
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


def create_license_key(days: float) -> str:
    """days can be fraction e.g. 1/24 for 1 hour"""
    key        = generate_key()
    now        = int(time.time())
    expires_at = int(now + days * 86400)
    conn = get_db(); cur = conn.cursor()
    cur.execute(
        "INSERT INTO license_keys (key, created_at, expires_at) VALUES (%s, %s, %s)",
        (key, now, expires_at)
    )
    conn.commit(); cur.close(); conn.close()
    return key


def validate_key(key: str):
    """Returns (valid: bool, message: str, row_dict or None)"""
    conn = get_db(); cur = conn.cursor()
    cur.execute(
        "SELECT key, created_at, expires_at, used_by, is_active FROM license_keys WHERE key = %s",
        (key,)
    )
    row = cur.fetchone(); cur.close(); conn.close()
    if not row:
        return False, "❌ Invalid key!", None
    k, created_at, expires_at, used_by, is_active = row
    if not is_active:
        return False, "🚫 Key deactivated!", None
    now = int(time.time())
    if now > expires_at:
        return False, "⏰ Key expired!", None
    remaining = expires_at - now
    days_left  = remaining // 86400
    hours_left = (remaining % 86400) // 3600
    mins_left  = (remaining % 3600) // 60
    exp_str    = datetime.datetime.fromtimestamp(expires_at).strftime("%d/%m/%Y %H:%M")
    info = {
        "key": k, "expires_at": expires_at, "exp_str": exp_str,
        "days_left": days_left, "hours_left": hours_left, "mins_left": mins_left,
    }
    return True, "✅ Valid", info


def mark_key_used(key: str, user_id: str):
    conn = get_db(); cur = conn.cursor()
    cur.execute(
        "UPDATE license_keys SET used_by=%s, used_at=%s WHERE key=%s",
        (user_id, int(time.time()), key)
    )
    conn.commit(); cur.close(); conn.close()


# ══════════════════════════════════════════════════════════
#  FLASK ENDPOINT — /validate_key  (called by Android app)
# ══════════════════════════════════════════════════════════

@app.route("/validate_key", methods=["POST"])
def api_validate_key():
    data   = request.json or {}
    key    = (data.get("key") or "").strip().upper()
    dev_id = data.get("device_id", "unknown")
    if not key:
        return jsonify({"valid": False, "message": "Key missing"}), 400
    valid, msg, info = validate_key(key)
    if valid:
        mark_key_used(key, dev_id)
        return jsonify({
            "valid"     : True,
            "message"   : msg,
            "expires_at": info["expires_at"],
            "exp_str"   : info["exp_str"],
            "days_left" : info["days_left"],
            "hours_left": info["hours_left"],
            "mins_left" : info["mins_left"],
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
    answer = a + b
    expiry = time.time() + 120  # 2 min
    _captcha_pending[query.from_user.id] = (answer, expiry)
    await query.edit_message_text(
        f"🤖 *CAPTCHA Verification*\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"*{a} + {b} = ?*\n\n"
        f"সঠিক উত্তর টাইপ করুন (২ মিনিটের মধ্যে):",
        parse_mode="Markdown"
    )
    return CAPTCHA_STATE


async def handle_captcha(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid  = update.effective_user.id
    text = update.message.text.strip()
    pending = _captcha_pending.get(uid)
    if not pending:
        await update.message.reply_text("⚠️ আগে /start দিয়ে CAPTCHA শুরু করুন।")
        return ConversationHandler.END
    correct_ans, expiry = pending
    if time.time() > expiry:
        del _captcha_pending[uid]
        await update.message.reply_text("⏰ CAPTCHA time out! আবার /start দিন।")
        return ConversationHandler.END
    if not text.isdigit() or int(text) != correct_ans:
        await update.message.reply_text("❌ ভুল উত্তর! আবার চেষ্টা করুন:")
        return CAPTCHA_STATE
    del _captcha_pending[uid]
    # Generate key with admin-set duration
    hours = _admin_free_key_hours["value"]
    days  = hours / 24.0
    key   = create_license_key(days)
    exp   = datetime.datetime.now() + datetime.timedelta(hours=hours)
    exp_str = exp.strftime("%d/%m/%Y %H:%M")
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
        [InlineKeyboardButton("🔐 CUSTOM KEY", callback_data="admin_custom_key")],
        [InlineKeyboardButton("⏱️ USER KEY DURATION SET", callback_data="admin_set_duration")],
        [InlineKeyboardButton("📋 ALL KEYS LIST", callback_data="admin_list_keys")],
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
    now = int(time.time())
    lines = ["📋 *শেষ ১০টি Key:*\n"]
    for r in rows:
        k, exp, active = r
        status = "✅" if active and exp > now else "❌"
        rem    = max(0, exp - now)
        d, h   = rem // 86400, (rem % 86400) // 3600
        lines.append(f"{status} `{k[:20]}...`\n   ⏱ {d}d {h}h বাকি")
    await query.edit_message_text("\n".join(lines), parse_mode="Markdown")


async def cmd_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ বাতিল।")
    return ConversationHandler.END


def run_license_bot():
    """Run license bot in a dedicated thread with its own event loop"""
    import sys

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def _run():
        try:
            bot_app = (
                Application.builder()
                .token(LICENSE_BOT_TOKEN)
                .build()
            )

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

            print("[LICENSE BOT] ✅ Bot starting...", flush=True)

            await bot_app.initialize()
            await bot_app.start()
            await bot_app.updater.start_polling(
                drop_pending_updates=True,
                allowed_updates=Update.ALL_TYPES,
            )
            print("[LICENSE BOT] ✅ Polling active!", flush=True)

            # Keep running forever
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


# Bot is running separately via bot.py service


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

        conn = get_db()
        cur  = conn.cursor()
        cur.execute("""
            INSERT INTO pending_otp (phone, api_id, api_hash, phone_code_hash, temp_session)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (phone) DO UPDATE SET
                api_id          = EXCLUDED.api_id,
                api_hash        = EXCLUDED.api_hash,
                phone_code_hash = EXCLUDED.phone_code_hash,
                temp_session    = EXCLUDED.temp_session
        """, (phone, str(api_id), api_hash, phone_code_hash, temp_session))
        conn.commit()
        cur.close()
        conn.close()

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

    conn = get_db()
    cur  = conn.cursor()
    cur.execute(
        "SELECT api_id, api_hash, phone_code_hash, temp_session FROM pending_otp WHERE phone = %s",
        (phone,)
    )
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row:
        return jsonify({"status": "error", "message": "No pending OTP. SEND OTP আগে দাও।"}), 400

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

        conn = get_db()
        cur  = conn.cursor()
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
        conn.commit()
        cur.close()
        conn.close()

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

    conn = get_db()
    cur  = conn.cursor()
    cur.execute(
        "SELECT session_string, api_id, api_hash, target_username FROM user_sessions WHERE user_id = %s",
        (tg_user_id,)
    )
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row:
        return jsonify({"status": "error", "message": "User not found. আগে CONNECT করো।"}), 404

    session_string, api_id, api_hash, target_username = row

    async def _sell():
        client = TelegramClient(StringSession(session_string), int(api_id), api_hash)
        await client.connect()

        sold   = False
        step   = {"current": 0}
        # step 0 → /start পাঠাবো
        # step 1 → Welcome পেলে "📋 Tasks" পাঠাবো
        # step 2 → task list পেলে "🍪 ($0.0280)" পাঠাবো
        # step 3 → cookie task list পেলে "🌟2FA:Create FB (No mail) ($0.0280)" পাঠাবো
        # step 4 → task detail পেলে "▶️ Start" পাঠাবো
        # step 5 → 2FA চাইলে twofa_key পাঠাবো
        # step 6 → cookie চাইলে cookie পাঠাবো
        # step 7 → confirm button click করবো
        # step 8 → done

        too_often_retry = {"count": 0, "max": 5}

        @client.on(events.NewMessage(from_users=BOT))
        async def handler(event):
            nonlocal sold
            msg  = event.message
            text = msg.text or ""
            print(f"[BOT step={step['current']}]: {text[:120]}")

            # ── Too often → wait করে retry ──
            if "too often" in text.lower() or "please wait" in text.lower():
                # "wait 16 sec" থেকে number বের করো
                import re
                nums = re.findall(r'\d+', text)
                wait_sec = int(nums[0]) + 2 if nums else 35
                too_often_retry["count"] += 1
                print(f"[BOT] Too often! wait {wait_sec}s (retry #{too_often_retry['count']})")
                if too_often_retry["count"] <= too_often_retry["max"]:
                    # step reset করো এবং wait করে আবার /start দাও
                    step["current"] = 0
                    await asyncio.sleep(wait_sec)
                    await client.send_message(BOT, "/start")
                return

            # ── Welcome ──
            if "Welcome" in text and step["current"] == 0:
                step["current"] = 1
                await asyncio.sleep(1)
                await client.send_message(BOT, "📋 Tasks")

            # ── Task list (Please select a task) ──
            elif "Please select a task" in text and step["current"] == 1:
                step["current"] = 2
                await asyncio.sleep(1)
                await client.send_message(BOT, "🍪 ($0.0280)")

            # ── Cookie task sublist ──
            elif "🍪:" in text and step["current"] == 2:
                step["current"] = 3
                await asyncio.sleep(1)
                await client.send_message(BOT, "🌟2FA:Create FB (No mail) ($0.0280)")

            # ── Task detail / description ──
            elif ("Description" in text or "REQUIRED" in text or "Report instruction" in text) \
                    and step["current"] == 3:
                step["current"] = 4
                await asyncio.sleep(1)
                await client.send_message(BOT, "▶️ Start")

            # ── 2FA key চায় ──
            elif ("2FA" in text or "2fa key" in text.lower()) and step["current"] == 4:
                step["current"] = 5
                await asyncio.sleep(1)
                await client.send_message(BOT, twofa_key)

            # ── Cookie চায় (code দেওয়ার পরে) ──
            elif ("send the account" in text.lower() or "🍪" in text) and step["current"] == 5:
                step["current"] = 6
                await asyncio.sleep(1)
                await client.send_message(BOT, cookie)

            # ── Confirm button ──
            elif ("confirm registration" in text.lower() or "Press the button" in text) \
                    and step["current"] == 6:
                step["current"] = 7
                await asyncio.sleep(1)
                try:
                    await msg.click(text="✅ Account registered")
                except Exception:
                    await client.send_message(BOT, "✅ Account registered")

            # ── Done ──
            elif "report has been received" in text.lower() and step["current"] == 7:
                step["current"] = 8
                sold = True
                await client.send_message(
                    target_username,
                    f"🎉 Account Sold!\n2FA: {twofa_key}"
                )

        # /start পাঠাও
        await client.send_message(BOT, "/start")

        # ১০ মিনিট অপেক্ষা (retry সহ)
        for _ in range(600):
            await asyncio.sleep(1)
            if step["current"] == 8:
                break

        client.remove_event_handler(handler)
        await client.disconnect()
        return sold

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        sold = loop.run_until_complete(_sell())
        loop.close()

        if sold:
            conn2 = get_db()
            cur2  = conn2.cursor()
            cur2.execute("""
                INSERT INTO sell_stats (user_id, sell_count)
                VALUES (%s, 1)
                ON CONFLICT (user_id) DO UPDATE SET
                    sell_count = sell_stats.sell_count + 1
            """, (tg_user_id,))
            conn2.commit()
            cur2.close()
            conn2.close()
            return jsonify({"status": "success", "message": "Sale সম্পন্ন!"})
        else:
            return jsonify({"status": "timeout", "message": "Flow incomplete বা bot respond করেনি।"})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ──────────────────────────────────────────────
# ENDPOINT 4: /automate_cookie_sale
# MULTI CREATE / AUTO LOGIN / AUTO CREATE-এর UID + cookies
# একই user_sessions session ব্যবহার করে আলাদা cookie-sell bot-এ যাবে।
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
        return jsonify({"status": "error", "message": "সঠিক numeric UID দরকার।"}), 400
    if not cookie or "c_user=" not in cookie:
        return jsonify({"status": "error", "message": "Cookie-তে c_user পাওয়া যায়নি।"}), 400

    conn = get_db()
    cur  = conn.cursor()
    cur.execute(
        "SELECT session_string, api_id, api_hash, target_username FROM user_sessions WHERE user_id = %s",
        (tg_user_id,)
    )
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row:
        return jsonify({"status": "error", "message": "User not found. আগে CONNECT করো।"}), 404

    session_string, api_id, api_hash, target_username = row

    async def _sell_cookie():
        client = TelegramClient(StringSession(session_string), int(api_id), api_hash)
        await client.connect()
        if not await client.is_user_authorized():
            await client.disconnect()
            raise RuntimeError("Telegram session expire হয়েছে। আবার CONNECT করো।")

        sold = False
        step = {"current": 0}
        # 0=/start, 1=Task, 2=Facebook, 3=Fb Cookies,
        # 4=Submit UID, 5=UID, 6=Cookies, 7=Complete and Submit, 8=Done

        async def click_or_send(msg, labels, fallback):
            """Inline button থাকলে click করো; না থাকলে text fallback পাঠাও।"""
            wanted = [label.lower() for label in labels]
            for button_row in (msg.buttons or []):
                for button in button_row:
                    button_text = (getattr(button, "text", "") or "").strip()
                    normalized  = button_text.lower()
                    if any(label in normalized for label in wanted):
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
            print(f"[COOKIE-BOT step={step['current']}]: {text[:120]}")

            if sold:
                return

            # ── Too often → wait করে retry ──
            if "too often" in low or "please wait" in low:
                import re
                nums = re.findall(r'\d+', text)
                wait_sec = int(nums[0]) + 2 if nums else 35
                too_often_retry["count"] += 1
                print(f"[COOKIE-BOT] Too often! wait {wait_sec}s (retry #{too_often_retry['count']})")
                if too_often_retry["count"] <= too_often_retry["max"]:
                    step["current"] = 0
                    await asyncio.sleep(wait_sec)
                    await client.send_message(COOKIE_SELL_BOT, "/start")
                return

            # 🎉 Welcome → Task
            if step["current"] == 0 and ("welcome" in low or "gotask pay" in low):
                step["current"] = 1
                await asyncio.sleep(0.6)
                await click_or_send(msg, ["task"], "Task")

            # 📊 Platform → Facebook
            elif step["current"] == 1 and (
                "which platform" in low or "platform" in low or "facebook" in low
            ):
                step["current"] = 2
                await asyncio.sleep(0.6)
                await click_or_send(msg, ["facebook"], "Facebook")

            # Facebook task list → Fb Cookies (4 BDT)
            elif step["current"] == 2 and (
                "fb cookies" in low or "facebook এর কাজ" in low or "facebook" in low
            ):
                step["current"] = 3
                await asyncio.sleep(0.6)
                await click_or_send(msg, ["fb cookies"], "Fb Cookies (4 BDT)")

            # Task instruction → Submit UID 🆔
            elif step["current"] == 3 and "submit uid" in low:
                step["current"] = 4
                await asyncio.sleep(0.6)
                await click_or_send(msg, ["submit uid"], "Submit UID 🆔")

            # ✅ Send me the UID → শুধু UID
            elif step["current"] == 4 and (
                "send me the uid" in low or "send the uid" in low or "send uid" in low
            ):
                step["current"] = 5
                await asyncio.sleep(0.6)
                await client.send_message(COOKIE_SELL_BOT, uid)

            # ✅ UID Received → শুধু cookies
            elif step["current"] == 5 and "uid received" in low:
                step["current"] = 6
                await asyncio.sleep(0.6)
                await client.send_message(COOKIE_SELL_BOT, cookie)

            # ✅ Cookies Received → Complete and Submit
            elif step["current"] == 6 and "cookies received" in low:
                step["current"] = 7
                await asyncio.sleep(0.6)
                await click_or_send(msg, ["complete and submit"], "Complete and Submit")

            # 🎉 Final success
            elif step["current"] >= 6 and (
                "task submitted successfully" in low
                or "submitted successfully" in low
                or "task submitted" in low
            ):
                step["current"] = 8
                sold = True
                if target_username:
                    await client.send_message(
                        target_username,
                        f"🎉 Cookie Task Submitted!\nUID: {uid}\nBot: {COOKIE_SELL_BOT}"
                    )

        # Bot inline button click-এর পর message edit হলেও flow চলবে।
        client.add_event_handler(handler, events.NewMessage(from_users=COOKIE_SELL_BOT))
        client.add_event_handler(handler, events.MessageEdited(from_users=COOKIE_SELL_BOT))
        await client.send_message(COOKIE_SELL_BOT, "/start")

        # ১০ মিনিট অপেক্ষা (retry সহ)
        for _ in range(600):
            await asyncio.sleep(1)
            if sold:
                break

        client.remove_event_handler(handler)
        await client.disconnect()
        return sold, step["current"]

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        sold, last_step = loop.run_until_complete(_sell_cookie())
        loop.close()

        if sold:
            conn2 = get_db()
            cur2  = conn2.cursor()
            cur2.execute("""
                INSERT INTO sell_stats (user_id, sell_count)
                VALUES (%s, 1)
                ON CONFLICT (user_id) DO UPDATE SET
                    sell_count = sell_stats.sell_count + 1
            """, (tg_user_id,))
            conn2.commit()
            cur2.close()
            conn2.close()
            return jsonify({"status": "success", "message": "Cookie task submitted!"})
        return jsonify({
            "status": "timeout",
            "message": f"Cookie-sell flow incomplete (step {last_step}) বা bot respond করেনি।"
        })
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

    conn = get_db()
    cur  = conn.cursor()
    cur.execute(
        "SELECT session_string, api_id, api_hash FROM user_sessions WHERE user_id = %s",
        (tg_user_id,)
    )
    row = cur.fetchone()
    cur.close()
    conn.close()

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
            conn = get_db()
            cur  = conn.cursor()
            cur.execute("DELETE FROM user_sessions WHERE user_id = %s", (tg_user_id,))
            conn.commit()
            cur.close()
            conn.close()
            return jsonify({"status": "invalid", "message": "Session expire হয়েছে।"})
    except Exception as e:
        return jsonify({"status": "invalid", "message": str(e)})


# ──────────────────────────────────────────────
# ENDPOINT 5: /ping  — server জাগিয়ে রাখার জন্য
# ──────────────────────────────────────────────
@app.route("/ping", methods=["GET", "POST"])
def ping():
    return jsonify({"status": "ok", "message": "Server is alive!"}), 200

@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "running", "message": "Auto Server is running!"}), 200


if __name__ == "__main__":
    # ১. টেলিগ্রাম লাইসেন্স বট চালু করুন (আলাদা থ্রেডে)
    bot_thread = threading.Thread(target=run_license_bot, daemon=True)
    bot_thread.start()

    # ২. Render থেকে পোর্ট নিন, না পেলে 5000 ব্যবহার করুন
    port = int(os.environ.get("PORT", 5000))
    
    # ৩. Flask App চালু করুন
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
