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
from telethon import TelegramClient
from telethon.sessions import StringSession

app = Flask(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL")
BOT = "@Taskl1_bot"


def get_db():
    return psycopg2.connect(DATABASE_URL)


def ensure_pending_table():
    """pending_otp table না থাকলে বানাও"""
    conn = get_db()
    cur  = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS pending_otp (
            phone            TEXT PRIMARY KEY,
            api_id           TEXT NOT NULL,
            api_hash         TEXT NOT NULL,
            phone_code_hash  TEXT NOT NULL
        )
    """)
    conn.commit()
    cur.close()
    conn.close()

ensure_pending_table()


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
        await client.disconnect()
        return result.phone_code_hash

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        phone_code_hash = loop.run_until_complete(_send())
        loop.close()

        # phone_code_hash Supabase এ save করো
        conn = get_db()
        cur  = conn.cursor()
        cur.execute("""
            INSERT INTO pending_otp (phone, api_id, api_hash, phone_code_hash)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (phone) DO UPDATE SET
                api_id          = EXCLUDED.api_id,
                api_hash        = EXCLUDED.api_hash,
                phone_code_hash = EXCLUDED.phone_code_hash
        """, (phone, str(api_id), api_hash, phone_code_hash))
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

    # Supabase থেকে pending_otp data লোড করো
    conn = get_db()
    cur  = conn.cursor()
    cur.execute(
        "SELECT api_id, api_hash, phone_code_hash FROM pending_otp WHERE phone = %s",
        (phone,)
    )
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row:
        return jsonify({"status": "error", "message": "No pending OTP for this phone. SEND OTP আগে দাও।"}), 400

    api_id, api_hash, phone_code_hash = row

    async def _verify():
        # নতুন client বানাও — phone_code_hash DB থেকে নাও
        client = TelegramClient(StringSession(), int(api_id), api_hash)
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

        # user_sessions এ save করো
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

        # pending_otp মুছে দাও
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
        await client.start()

        async with client.conversation(BOT, timeout=60) as conv:
            await conv.send_message("/start")

            while True:
                try:
                    response = await conv.get_response()
                    text = response.text or ""

                    if "First name:" in text and "Password:" in text:
                        dummy_name = ''.join(random.choices(string.ascii_letters, k=6))
                        dummy_pass = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
                        await conv.send_message(
                            f"First name: {dummy_name}\nLast name: User\nPassword: {dummy_pass}"
                        )

                    elif "Please enter your 2FA key" in text:
                        await conv.send_message(twofa_key)

                    elif "send the account 🍪:" in text.lower() or "🍪" in text:
                        await conv.send_message(cookie)

                    elif "Press the button to confirm registration" in text:
                        await response.click(text="✅ Account registered")

                    elif "Your report has been received" in text:
                        await client.send_message(
                            target_username,
                            f"🎉 Account Sold Successfully!\n2FA Key: {twofa_key}"
                        )
                        break

                except asyncio.TimeoutError:
                    break
                except Exception:
                    break

        await client.disconnect()

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_sell())
        loop.close()
        return jsonify({"status": "success", "message": "Sale process completed!"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == "__main__":
    # Single worker — threading=False যাতে asyncio loop conflict না হয়
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=False)
