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

pending_clients = {}

def get_db():
    return psycopg2.connect(DATABASE_URL)

@app.route("/send_otp", methods=["POST"])
def send_otp():
    data = request.json
    api_id = int(data["api_id"])
    api_hash = data["api_hash"]
    phone = data["phone"]

    async def _send():
        client = TelegramClient(StringSession(), api_id, api_hash)
        await client.connect()
        result = await client.send_code_request(phone)
        await client.disconnect()
        return result.phone_code_hash

    try:
        # এখানে asyncio.run ব্যবহার করা হয়েছে
        phone_code_hash = asyncio.run(_send())
        pending_clients[phone] = {
            "phone_code_hash": phone_code_hash,
            "api_id": api_id,
            "api_hash": api_hash,
        }
        return jsonify({"status": "otp_sent", "phone": phone})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/verify_otp", methods=["POST"])
def verify_otp():
    data = request.json
    phone = data["phone"]
    otp = data["otp"]
    tg_user_id = data["tg_user_id"]
    target_username = data["target_username"]

    entry = pending_clients.get(phone)
    if not entry:
        return jsonify({"status": "error", "message": "No pending OTP for this phone"}), 400

    async def _verify():
        # নতুন ক্লায়েন্ট তৈরি করা হয়েছে
        client = TelegramClient(StringSession(), entry["api_id"], entry["api_hash"])
        await client.connect()
        await client.sign_in(phone, code=otp, phone_code_hash=entry["phone_code_hash"])
        session_string = client.session.save()
        await client.disconnect()

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO user_sessions (user_id, session_string, api_id, api_hash, target_username)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (user_id) DO UPDATE SET
                session_string  = EXCLUDED.session_string,
                api_id          = EXCLUDED.api_id,
                api_hash        = EXCLUDED.api_hash,
                target_username = EXCLUDED.target_username
        """, (tg_user_id, session_string, str(entry["api_id"]), entry["api_hash"], target_username))
        conn.commit()
        cursor.close()
        conn.close()

    try:
        asyncio.run(_verify())
        pending_clients.pop(phone, None)
        return jsonify({"status": "success", "message": "Session saved!"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/automate_sale", methods=["POST"])
def automate_sale():
    data = request.json
    tg_user_id = data["tg_user_id"]
    twofa_key = data["twofa_key"]
    cookie = data["cookie"]

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT session_string, api_id, api_hash, target_username FROM user_sessions WHERE user_id = %s",
        (tg_user_id,)
    )
    row = cursor.fetchone()
    cursor.close()
    conn.close()

    if not row:
        return jsonify({"status": "error", "message": "User not found"}), 404

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
                        await conv.send_message(f"First name: {dummy_name}\nLast name: User\nPassword: {dummy_pass}")

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
        asyncio.run(_sell())
        return jsonify({"status": "success", "message": "Sale process completed!"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
