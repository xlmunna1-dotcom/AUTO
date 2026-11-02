# ============================================================
# FILE: app.py
# Requirements: flask, telethon, psycopg2-binary
# Run: python app.py
# ============================================================

import os
import asyncio
import random
import string
import psycopg2
from flask import Flask, request, jsonify
from telethon import TelegramClient, events
from telethon.sessions import StringSession

app = Flask(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL")
BOT = "@Taskl1_bot"
COOKIE_SELL_BOT = "@QuickTaskPay1bot"


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
    conn.commit()
    cur.close()
    conn.close()

ensure_tables()


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

        @client.on(events.NewMessage(from_users=BOT))
        async def handler(event):
            nonlocal sold
            msg  = event.message
            text = msg.text or ""
            print(f"[BOT step={step['current']}]: {text[:120]}")

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

        # ৩ মিনিট অপেক্ষা (সব step শেষ হওয়ার জন্য)
        for _ in range(180):
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

        async def handler(event):
            nonlocal sold
            msg  = event.message
            text = msg.text or ""
            low  = text.lower()
            print(f"[COOKIE-BOT step={step['current']}]: {text[:120]}")

            if sold:
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

        for _ in range(180):
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
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
