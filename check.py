# ==========================================================
#  ZENEX OTP BOT v18.0 PRO EDITION — PART 1/5
#  Config + Emoji + Load/Save + Firebase + API + Watcher
# ==========================================================

import telebot
import html
import requests
import time
import threading
import re
import json
import os
import random
import string
import traceback
from telebot import types
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

# ================== CONFIG ==================
BOT_TOKEN    = os.environ.get("BOT_TOKEN", "")
ADMIN_ID     = int(os.environ.get("ADMIN_ID", "0") or "0")
OTP_GROUP_ID = int(os.environ.get("OTP_GROUP_ID", "0") or "0")
FIREBASE_URL = os.environ.get("FIREBASE_URL", "https://your-firebase.firebaseio.com")

ZENEX_BASE    = "https://api.zenexnetwork.com"
STEX_BASE     = "https://api.2oo9.cloud/MXS47FLFX0U/tness/@public/api"
VOLTX_BASE    = "https://api.2oo9.cloud/MXS47FLFX0U/tnevs/@public/api"
SLVIRTUAL_BASE = "https://slvirtualnumber.com"

EMOJI_SAVE_FILE   = "custom_emojis.json"
COLOR_SAVE_FILE   = "button_colors.json"
EMOJI_STATE_FILE  = "emoji_state.json"
ADMIN_SAVE_FILE   = "admins.json"
LABEL_SAVE_FILE   = "button_labels.json"
SETTINGS_FILE     = "bot_settings.json"

FORCE_PREMIUM = True

# ================== BTN_EMOJI ==================
BTN_EMOJI = {
    "phone":  "5337132498965010628", "pin":    "5352922460897452503",
    "graph":  "5352877703043258544", "money":  "5190576863226933563",
    "rocket": "5352597830089347330", "no":     "5420130255174145507",
    "ok":     "5352694861990501856", "key":    "5197288647275071607",
    "user":   "5352861489541714456", "fire":   "5337267511261960341",
    "crown":  "5352838545826420397", "gear":   "5420155432272438703",
    "star":   "5352552689983067014",
}

BODY_EMOJIS = {
    "✅": "5352694861990501856", "❌": "5420130255174145507",
    "⚠️": "5336944168944047463", "🔥": "5337267511261960341",
    "💸": "5348469219761626211", "🎁": "5420396762189831222",
    "💬": "5337302974806922068", "🔐": "5337255927735163754",
    "📱": "5337132498965010628", "🔗": "5420517437885943844",
    "⚙️": "5420155432272438703", "🗑": "5422557736330106570",
    "📊": "5353032893096567467", "🔢": "5352862640592949843",
    "👤": "5352861489541714456", "🚀": "5352597830089347330",
    "💎": "5352838545826420397", "📍": "5352922460897452503",
    "👋": "5353027129250453493", "✨": "5352552689983067014",
    "📤": "5353001161878182134", "🌐": "5334590977837403844",
    "🔑": "5197288647275071607", "💰": "5190576863226933563",
    "🟢": "5192812028632274956", "📈": "5352877703043258544",
    "🔔": "5352980533150259581", "🏦": "5348469219761626211",
    "⚡": "5352597830089347330", "🔄": "5352597830089347330",
    "🏆": "5352552689983067014", "🥇": "5352552689983067014",
    "📡": "5352877703043258544", "🕐": "5352980533150259581",
    "📅": "5352980533150259581", "➕": "5352694861990501856",
    "🎨": "5352552689983067014", "🔧": "5420155432272438703",
    "🆔": "5352861489541714456", "📝": "5337302974806922068",
    "🔵": "5192812028632274956", "🟣": "5352838545826420397",
    "🎭": "5352552689983067014", "🔴": "5420130255174145507",
    "👑": "5352838545826420397", "🔒": "5353022963132174959",
}

# ================== LOAD / SAVE ==================
def load_json(path):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[LOAD ERR] {path}: {e}")
    return {}

def save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"[SAVE] {path} → {len(data)} items")
        return True
    except Exception as e:
        print(f"[SAVE ERR] {path}: {e}")
        return False

CUSTOM_EMOJI  = load_json(EMOJI_SAVE_FILE)
BUTTON_COLORS = load_json(COLOR_SAVE_FILE)
EXTRA_ADMINS  = load_json(ADMIN_SAVE_FILE)
CUSTOM_LABELS = load_json(LABEL_SAVE_FILE)

def load_emoji_state():
    if os.path.exists(EMOJI_STATE_FILE):
        try:
            with open(EMOJI_STATE_FILE, "r") as f:
                data = json.load(f)
                return {"premium": data.get("premium_on", True),
                        "free":    data.get("free_on", True)}
        except: pass
    return {"premium": True, "free": True}

EMOJI_STATE = load_emoji_state()
EMOJI_ON      = EMOJI_STATE["premium"]
FREE_EMOJI_ON = EMOJI_STATE["free"]

def save_emoji_state():
    try:
        with open(EMOJI_STATE_FILE, "w") as f:
            json.dump({"premium_on": EMOJI_ON, "free_on": FREE_EMOJI_ON}, f)
    except: pass

def get_emoji_id(emoji_char):
    return CUSTOM_EMOJI.get(emoji_char) or BODY_EMOJIS.get(emoji_char)

def is_admin(user_id):
    if user_id == ADMIN_ID: return True
    info = EXTRA_ADMINS.get(str(user_id))
    return bool(info and info.get("active", True))

def is_owner(user_id):
    return user_id == ADMIN_ID

# ================== ALL BUTTONS ==================
ALL_BUTTONS = {
    "btn_get_number":    "📲 GET NUMBER",
    "btn_profile":       "👤 PROFILE",
    "btn_balance":       "💰 MY BALANCE",
    "btn_top_reward":    "🏆 TOP REWARD",
    "btn_zenex":         "⚡ ZENEX",
    "btn_stex":          "🔵 STEX",
    "btn_voltx":         "🟣 VOLTX",
    "btn_number":        "📱 Number Button",
    "btn_change":        "🔄 CHANGE",
    "btn_back":          "🔙 BACK",
    "btn_set_speed":     "⚡ SET SPEED",
    "btn_filter":        "🔧 FILTER SERVICE",
    "btn_today_otp":     "📊 TODAY OTP",
    "btn_all_users":     "👥 ALL USERS",
    "btn_manage_keys":   "🔑 MANAGE KEYS",
    "btn_custom_emoji":  "🎨 SET CUSTOM EMOJI",
    "btn_custom_color":  "🎨 CUSTOM COLOR",
    "btn_emoji_toggle":  "🎭 EMOJI ON/OFF",
    "btn_set_admin":     "👑 SET ADMIN",
    "btn_back_to_bot":   "🔙 BACK TO BOT",
    "btn_emoji_control": "🎛 EMOJI CONTROL",
    "btn_search_user":   "🔍 SEARCH USER",
    "btn_system":        "⚙️ SYSTEM",
    "btn_otp_edit":      "🎁 OTP EDIT",
    "btn_chatter_baal":  "💬 CHATTER BAAL",
    "btn_otp_group":     "📢 OTP GROUP",
    "btn_admin_panel":   "👑 ADMIN PANEL",
    "btn_slvirtual":     "🌐 SL VIRTUAL",
    "btn_traffic":       "📡 TRAFFIC CHECK",
}

def get_label(key, default):
    return CUSTOM_LABELS.get(key, default)

# ================== PREMIUM ==================
PREMIUM_STATE = {"is_premium": True, "checked": True, "source": "forced"}

def check_bot_premium():
    if not EMOJI_ON:
        PREMIUM_STATE["is_premium"] = False
        PREMIUM_STATE["source"] = "emoji_off"
        return False
    if FORCE_PREMIUM:
        PREMIUM_STATE["is_premium"] = True
        PREMIUM_STATE["source"] = "forced"
        return True
    try:
        me = bot.get_me()
        is_prem = bool(getattr(me, "is_premium", False))
        PREMIUM_STATE["is_premium"] = is_prem
        PREMIUM_STATE["source"] = "telegram"
        return is_prem
    except:
        PREMIUM_STATE["is_premium"] = False
        PREMIUM_STATE["source"] = "error"
        return False

def check_owner_premium(msg=None):
    if not PREMIUM_STATE["checked"]:
        check_bot_premium()

def pem(text):
    if not FREE_EMOJI_ON:
        all_emojis = set(BODY_EMOJIS.keys()) | set(CUSTOM_EMOJI.keys())
        for emoji in sorted(all_emojis, key=len, reverse=True):
            text = text.replace(emoji, "")
        return re.sub(r'\s+', ' ', text).strip()
    if EMOJI_ON and PREMIUM_STATE["is_premium"]:
        all_emojis = set(BODY_EMOJIS.keys()) | set(CUSTOM_EMOJI.keys())
        for emoji in sorted(all_emojis, key=len, reverse=True):
            eid = get_emoji_id(emoji)
            if eid and emoji in text:
                text = text.replace(emoji, f'<tg-emoji emoji-id="{eid}">{emoji}</tg-emoji>')
    return text

def btn_eid(name):
    if not FREE_EMOJI_ON: return None
    if not EMOJI_ON: return None
    if not PREMIUM_STATE["is_premium"]: return None
    custom = CUSTOM_EMOJI.get(f"__inline_{name}")
    if custom: return custom
    return BTN_EMOJI.get(name)

def emoji_status_str():
    p = "🟢" if EMOJI_ON else "🔴"
    f = "🟢" if FREE_EMOJI_ON else "🔴"
    return f"Premium {p} | Free {f}"

def btn_style(key, default=None):
    return BUTTON_COLORS.get(key) or default

# ================== BOT SETTINGS ==================
settings = {
    "zenex_keys": [],
    "stex_keys": [],
    "voltx_keys": [],
    "slvirtual_keys": [],
    "otp_reward": 0.30,
    "min_withdraw": 30.0,
    "max_withdraw": 10000.0,
    "withdraw_on": True,
    "w_methods": {"bkash": True, "nagad": True, "binance": True, "rocket": True},
    "binance_rate": 128.0,
    "w_limits": {
        "bkash":   {"min": 50.0,   "max": 1000.0},
        "nagad":   {"min": 50.0,   "max": 1000.0},
        "rocket":  {"min": 50.0,   "max": 1000.0},
        "binance": {"min": 5.0,    "max": 500.0},
    },
    "allowed_services": [],
    "speed_mode": "ELITE FAST",
    "fw_groups": [],
    "refer_reward": 2.0,
    "refer_enabled": True,
    "top_reward_enabled": True,
    "top_reward_count": 3,
    "top_reward_prices": {"1": 50.0, "2": 30.0, "3": 20.0},
    "top_auto_add": False,
    "must_join_enabled": True,
    "must_join_channels": [{"name": "MAIN CHANNEL", "id": "-1004339378904", "link": "https://t.me/yourchannel", "username": "@yourchannel"}],
    "payment_channel_enabled": True,
    "payment_channel_id": "",
    "payment_channel_name": "PAYMENT CHANNEL",
    "payment_channel_link": "",
    "otp_group_link": "",
    "daily_limit": 0,
    "change_cooldown_seconds": 10,
}

saved_settings = load_json(SETTINGS_FILE)
if saved_settings:
    for k, v in saved_settings.items():
        if k in settings:
            settings[k] = v
    print(f"[SETTINGS] Loaded {len(saved_settings)} keys")

def save_settings():
    save_json(SETTINGS_FILE, settings)

SPEED_MODES = {"SUPER FAST": 2.0, "ELITE FAST": 3.0, "RANDOM": 5.0}

# ================== GLOBAL ==================
number_owner   = {}
processed_ids  = set()
group_seen     = set()
OTP_NUMBER_MAP = {}
lock = threading.Lock()
TEMP_ADDKEY = {}
bot = telebot.TeleBot(BOT_TOKEN, threaded=True)
session = requests.Session()
user_data = {}

EMOJI_CONTROL_MODE = {}

# CHANGE COOLDOWN
CHANGE_COOLDOWN = {}
USER_STATE = {}
TEMP_WITHDRAW = {}

last_msg_time = {}
def is_spam(chat_id, cooldown=0.3):
    now = time.time()
    last = last_msg_time.get(chat_id, 0)
    if now - last < cooldown: return True
    last_msg_time[chat_id] = now
    return False

def get_user(chat_id):
    if chat_id not in user_data:
        user_data[chat_id] = {"service": None, "prefix": None, "numbers": [], "panel": "zenex"}
    return user_data[chat_id]

def assign_numbers(chat_id, service, numbers, panel="zenex"):
    with lock:
        for num in list(number_owner.keys()):
            info = number_owner[num]
            if chat_id in info["users"]:
                info["users"].remove(chat_id)
                if not info["users"]:
                    del number_owner[num]
        for n in numbers:
            if n in number_owner:
                if chat_id not in number_owner[n]["users"]:
                    number_owner[n]["users"].append(chat_id)
            else:
                number_owner[n] = {
                    "users": [chat_id],
                    "service": service,
                    "panel": panel
                }
        u = get_user(chat_id)
        u["numbers"] = list(numbers)
        u["service"] = service
        u["panel"]   = panel
        print(f"[TRACKER] {chat_id} → {len(numbers)} numbers | {service} | {panel}")
    for n in numbers:
        threading.Thread(target=check_one_number, args=(n,), daemon=True).start()

# ================== FIREBASE ==================
def fb_get(path):
    try:
        r = requests.get(f"{FIREBASE_URL}/{path}.json", timeout=8)
        return r.json()
    except Exception as e:
        print(f"[FB GET ERR] {path}: {e}")
        return None

def fb_set(path, data):
    try:
        requests.put(f"{FIREBASE_URL}/{path}.json", json=data, timeout=8)
    except Exception as e:
        print(f"[FB SET ERR] {path}: {e}")

def fb_update(path, data):
    try:
        requests.patch(f"{FIREBASE_URL}/{path}.json", json=data, timeout=8)
    except Exception as e:
        print(f"[FB UPD ERR] {path}: {e}")

def fb_push(path, data):
    try:
        requests.post(f"{FIREBASE_URL}/{path}.json", json=data, timeout=8)
    except Exception as e:
        print(f"[FB PUSH ERR] {path}: {e}")

def fb_delete(path):
    try:
        requests.delete(f"{FIREBASE_URL}/{path}.json", timeout=8)
    except Exception as e:
        print(f"[FB DEL ERR] {path}: {e}")

def db_get_user(chat_id):
    data = fb_get(f"users/{chat_id}")
    if not data:
        new = {
            "chat_id": chat_id, "balance": 0.0, "total_otp": 0,
            "refer_balance": 0.0, "total_refer": 0, "ref_by": None,
            "today_otp": 0,
            "today_date": datetime.now().strftime("%Y-%m-%d"),
            "banned": False, "username": "", "first_name": "",
            "joined": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        fb_set(f"users/{chat_id}", new)
        return new
    today = datetime.now().strftime("%Y-%m-%d")
    if data.get("today_date") != today:
        data["today_otp"] = 0
        data["today_date"] = today
        fb_update(f"users/{chat_id}", {"today_otp": 0, "today_date": today})
    return data

def db_add_reward(chat_id, number, service, otp_code, panel):
    try:
        user = db_get_user(chat_id)
        new_bal = round(float(user.get("balance", 0)) + settings["otp_reward"], 2)
        new_total = int(user.get("total_otp", 0)) + 1
        new_today = int(user.get("today_otp", 0)) + 1
        fb_update(f"users/{chat_id}", {
            "balance": new_bal, "total_otp": new_total, "today_otp": new_today
        })
        fb_push("today_otps", {
            "chat_id": chat_id, "number": number, "service": service,
            "otp": otp_code, "panel": panel,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "time": datetime.now().strftime("%H:%M:%S")
        })
        fb_push(f"otp_history/{chat_id}", {
            "number": number, "service": service, "otp": otp_code,
            "panel": panel,
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        return new_bal
    except Exception as e:
        print(f"[DB REWARD] err: {e}")
        return None

def db_today_otps():
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        data = fb_get("today_otps")
        if not data: return []
        return [v for v in data.values() if v.get("date") == today]
    except: return []

# ================== OTP EXTRACT ==================
def extract_otp(text):
    text = re.sub(r'[\u200B-\u200D\uFEFF]', '', str(text))
    g = re.search(r'G-(\d{4,8})', text, re.I)
    if g: return g.group(1)
    kw = re.search(r'(?:code|otp|pin|is)\s*[:\-=]?\s*(\d{4,8})', text, re.I)
    if kw: return kw.group(1)
    six = re.findall(r'(?<!\d)\d{6}(?!\d)', text)
    if six: return six[0]
    digits = re.findall(r'(?<!\d)\d{4,8}(?!\d)', text)
    if digits: return digits[0]
    return None


def make_filter_number(number):
    """237628386002 → 2376SUPER002"""
    try:
        clean = re.sub(r'\D', '', str(number))
        if len(clean) < 7:
            return f"filter {clean}"
        return f"{clean[:4]}SUPER{clean[-3:]}"
    except:
        return f"filter {number}"


# ================== MUST JOIN ==================
def check_must_join(chat_id):
    if not settings.get("must_join_enabled"): return True
    channels = settings.get("must_join_channels", [])
    if not channels: return True
    for ch in channels:
        try:
            ch_id = ch.get("id")
            if not ch_id: continue
            member = bot.get_chat_member(ch_id, chat_id)
            if member.status in ["left", "kicked"]:
                return False
        except Exception as e:
            print(f"[MUSTJOIN] check error for {chat_id} in {ch_id}: {e}")
            continue
    return True

def send_join_message(chat_id):
    kb = types.InlineKeyboardMarkup(row_width=1)
    channels = settings.get("must_join_channels", [])
    for ch in channels:
        name = ch.get("name", "CHANNEL")
        link = ch.get("link", "https://t.me/")
        kb.add(types.InlineKeyboardButton(
            text=f"📢 JOIN {name}",
            url=link,
            style="primary"))
    kb.add(types.InlineKeyboardButton(
        text="✅ JOINED — CHECK AGAIN",
        callback_data="check_join",
        style="success",
        icon_custom_emoji_id=btn_eid("ok")))
    text = pem(
        f"⚠️ <b>MUST JOIN REQUIRED</b>\n\n"
        f"Bot ব্যবহার করতে নিচের চ্যানেলে জয়েন করুন:\n\n"
        f"জয়েন করার পর <b>CHECK AGAIN</b> চাপুন।")
    bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=kb)

# ================== OTP SEND ==================
def send_otp_message(chat_id, number, service, otp_code, panel, created=""):
    try:
        if check_must_join(chat_id):
            new_bal = db_add_reward(chat_id, number, service, otp_code, panel)
        else:
            new_bal = None
            print(f"[OTP] ⚠️ {chat_id} not in must-join, no reward")
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton(
            text=f"📋  {otp_code}",
            copy_text=types.CopyTextButton(text=otp_code),
            style=btn_style("btn_number", "success"),
            icon_custom_emoji_id=btn_eid("ok")))
        bal_line = f"\n💸 <b>Balance:</b> <code>৳{new_bal}</code>" if new_bal else ""
        msg = pem(
            f"╔══════════════════╗\n   🔥 <b>OTP RECEIVED</b> 🔥\n╚══════════════════╝\n\n"
            f"📱 <b>Number:</b>  <code>{html.escape(str(number))}</code>\n"
            f"🌐 <b>Service:</b>  <code>{html.escape(str(service.upper()))}</code>\n"
            f"🔑 <b>OTP Code:</b>  <code>{html.escape(str(otp_code))}</code>{bal_line}")
        bot.send_message(chat_id, msg, parse_mode="HTML", reply_markup=kb)
        print(f"[OTP] ✅ Sent {otp_code} → {chat_id}")
    except Exception as e:
        print(f"[OTP] User err: {e}")

def send_group_message(number, service, otp_code, panel, created=""):
    for gid in settings["fw_groups"]:
        try:
            filter_num = make_filter_number(number)
            
            # Main channel + Number bot link
            main_ch = settings.get("main_channel_link", "")
            bot_username = settings.get("number_bot_username", "")
            
            if bot_username:
                bot_link = f"https://t.me/{bot_username.replace('@','')}?start=auto"
            else:
                bot_link = settings.get("number_bot_link", "https://t.me/")
            
            kb = types.InlineKeyboardMarkup(row_width=1)
            
            # NUMBER BOT বাটন — সরাসরি (auto start সহ)
            kb.add(types.InlineKeyboardButton(
                text="🤖 NUMBER BOT",
                url=bot_link,
                style="primary",
                icon_custom_emoji_id=btn_eid("phone")))
            
            # MAIN CHANNEL বাটন — সরাসরি
            if main_ch:
                kb.add(types.InlineKeyboardButton(
                    text="📢 MAIN CHANNEL",
                    url=main_ch,
                    style="success",
                    icon_custom_emoji_id=btn_eid("fire")))
            
            # OTP COPY বাটন
            kb.add(types.InlineKeyboardButton(
                text=f"📋  {otp_code}",
                copy_text=types.CopyTextButton(text=otp_code),
                style=btn_style("btn_number", "primary"),
                icon_custom_emoji_id=btn_eid("ok")))
            
            msg = pem(
                f"🔔 <b>NEW OTP</b>\n\n"
                f"📱 <code>{html.escape(str(filter_num))}</code>\n🌐 <code>{html.escape(str(service.upper()))}</code>\n"
                f"🔑 <code>{html.escape(str(otp_code))}</code>\n⚙️ <code>SUPER WORK</code>\n"
                f"🕐 <code>{html.escape(str(created))}</code>")
            # NOTE: panel name intentionally hidden from group
            bot.send_message(gid, msg, parse_mode="HTML", reply_markup=kb)
            print(f"[GROUP] ✅ {otp_code} → {gid} | {filter_num}")
        except Exception as e:
            print(f"[GROUP] err: {e}")


def process_otp(uid, number, service, otp_code, panel, created=""):
    with lock:
        info = number_owner.get(number)
        if not info: return
        owners = list(info["users"])
    group_key = f"{otp_code}_{service}_{panel}_{number}"
    with lock:
        if group_key in group_seen: return
        group_seen.add(group_key)
        if len(group_seen) > 2000: group_seen.clear()
    send_group_message(number, service, otp_code, panel, created)
    for chat_id in owners:
        send_otp_message(chat_id, number, service, otp_code, panel, created)

# ================== API ==================
def zenex_get_ranges(service=None):
    for key in settings["zenex_keys"]:
        try:
            r = session.get(f"{ZENEX_BASE}/v1/active-ranges",
                            headers={"mapikey": key}, timeout=15)
            res = r.json()
            if res.get("success"):
                ranges = res["data"]["active_ranges"]
                if service:
                    ranges = [x for x in ranges if x["service"].lower() == service.lower()]
                ranges.sort(key=lambda x: x["hits"], reverse=True)
                return ranges
        except Exception as e:
            print(f"[ZENEX ERR] {e}")
    return []
def zenex_get_number(prefix):
    import subprocess, json
    for key in settings["zenex_keys"]:
        try:
            payload = {"range": prefix, "is_national": False, "remove_plus": False}
            json_payload = json.dumps(payload).replace('"', '\\"')
            cmd = f'curl -s -X POST "{ZENEX_BASE}/v1/getnum" -H "mapikey: {key}" -H "Content-Type: application/json" -d "{json_payload}"'
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
            if res.returncode == 0:
                data = json.loads(res.stdout)
                if data.get("meta", {}).get("code") == 200:
                    return data["data"].get("full_number")
        except Exception as e:
            print(f"[CURL ZENEX GETNUM ERR] {e}")
    return None
def zenex_fetch_otps(number):
    import subprocess, json
    for key in settings["zenex_keys"]:
        try:
            cmd = f'curl -s -H "mapikey: {key}" "{ZENEX_BASE}/v1/numsuccess/info?number={number}"'
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
            if res.returncode == 0:
                data = json.loads(res.stdout)
                if data.get("meta", {}).get("code") == 200:
                    return data["data"].get("otps", [])
        except Exception as e:
            print(f"[CURL ZENEX OTP ERR] {e}")
    return []
def stex_get_services():
    for key in settings["stex_keys"]:
        try:
            return session.get(f"{STEX_BASE}/services",
                               headers={"mauthapi": key}, timeout=10).json().get("data", [])
        except: pass
    return []

def stex_get_number(service, country=""):
    for key in settings["stex_keys"]:
        try:
            params = {"service": service}
            if country: params["country"] = country
            d = session.post(f"{STEX_BASE}/getnum",
                             headers={"mauthapi": key},
                             json=params, timeout=12).json()
            if d.get("meta", {}).get("code") == 200:
                return d["data"].get("number")
        except: pass
    return None

def stex_fetch_otps(number):
    for key in settings["stex_keys"]:
        try:
            res = session.get(f"{STEX_BASE}/numsuccess",
                              headers={"mauthapi": key},
                              params={"number": number}, timeout=8).json()
            if res.get("meta", {}).get("code") == 200:
                return res["data"].get("otps", [])
        except: pass
    return []

def voltx_get_services():
    for key in settings["voltx_keys"]:
        try:
            return session.get(f"{VOLTX_BASE}/services",
                               headers={"mauthapi": key}, timeout=10).json().get("data", [])
        except: pass
    return []

def voltx_get_number(service, country=""):
    for key in settings["voltx_keys"]:
        try:
            params = {"service": service}
            if country: params["country"] = country
            d = session.post(f"{VOLTX_BASE}/getnum",
                             headers={"mauthapi": key},
                             json=params, timeout=12).json()
            if d.get("meta", {}).get("code") == 200:
                return d["data"].get("number")
        except: pass
    return None

def voltx_fetch_otps(number):
    for key in settings["voltx_keys"]:
        try:
            res = session.get(f"{VOLTX_BASE}/numsuccess",
                              headers={"mauthapi": key},
                              params={"number": number}, timeout=8).json()
            if res.get("meta", {}).get("code") == 200:
                return res["data"].get("otps", [])
        except: pass
    return []

# ================== SL VIRTUAL API ==================
def slvirtual_get_services():
    for key in settings["slvirtual_keys"]:
        try:
            r = session.get(f"{SLVIRTUAL_BASE}/api/v1/developer/available-services",
                            headers={"X-API-KEY": key},
                            params={"service": "any"}, timeout=10)
            res = r.json()
            if res.get("status") == "success":
                return res.get("data", [])
        except: pass
    return []

def slvirtual_get_countries(service="any"):
    for key in settings["slvirtual_keys"]:
        try:
            r = session.get(f"{SLVIRTUAL_BASE}/api/v1/developer/available-countries",
                            headers={"X-API-KEY": key},
                            params={"service": service}, timeout=15)
            res = r.json()
            if res.get("status") == "success":
                return res.get("data", [])
        except Exception as e:
            print(f"[SLVIRTUAL COUNTRY ERR] {e}")
    return []
def slvirtual_get_number(service, country_code="", tag="", range_prefix=""):
    for key in settings["slvirtual_keys"]:
        try:
            payload = {
                "service": "ANY (All Services)",
                "countryCode": country_code.upper() if country_code else "ET"
            }
            if tag: payload["tag"] = tag
            if range_prefix: payload["rangePrefix"] = str(range_prefix)

            print(f"\n[API REQ] {payload}\n")
            r = session.post(f"{SLVIRTUAL_BASE}/api/v1/developer/rent",
                             headers={"X-API-KEY": key, "Content-Type": "application/json"},
                             json=payload, timeout=15)
            res = r.json()
            
            if res.get("status") == "success":
                data = res.get("data", {})
                print(f"\n[API SUCCESS] {data.get('phoneNumber')}\n")
                return {"number": data.get("phoneNumber"), "rentalId": data.get("rentalId")}
            else:
                print(f"\n[API ERROR] {res}\n")
        except Exception as e:
            print(f"\n[API EXC] {e}\n")
    return None
def slvirtual_fetch_otps(rental_id):
    import subprocess, json
    for key in settings["slvirtual_keys"]:
        try:
            cmd = f'curl -s -H "X-API-KEY: {key}" "{SLVIRTUAL_BASE}/api/v1/developer/check-otp/{rental_id}"'
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
            if res.returncode == 0:
                data = json.loads(res.stdout)
                if data.get("status") == "success":
                    d = data.get("data", {})
                    if d.get("status") == "RECEIVED":
                        msgs = d.get("messages", [])
                        return [{"otp": m.get("otpCode") or m.get("fullSms", ""), "nid": m.get("id"), "created_at": m.get("receivedAt", ""), "number": d.get("phoneNumber", "")} for m in msgs]
        except Exception as e:
            print(f"[CURL SLV OTP ERR] {e}")
    return []
def slvirtual_get_traffic_24h():
    for key in settings["slvirtual_keys"]:
        try:
            r = session.get(f"{SLVIRTUAL_BASE}/api/v1/developer/live-console?limit=50",
                            headers={"X-API-KEY": key}, timeout=10)
            res = r.json()
            if res.get("status") == "success":
                data = res.get("data", [])
                # ডাটা রাখার স্ট্রাকচার: { "Country (Prefix)": { "total": X, "services": { "Facebook": Y } } }
                range_data = {}
                
                for item in data:
                    prefix = item.get("rangePrefix", "Unknown")
                    country = item.get("country", "Unknown")
                    flag = item.get("flag", "🌐")
                    svc_name = item.get("service", "Unknown").upper()
                    
                    key_str = f"{flag} {country.upper()} ({prefix})"
                    
                    if key_str not in range_data:
                        range_data[key_str] = {"total": 0, "services": {}}
                        
                    range_data[key_str]["total"] += 1
                    range_data[key_str]["services"][svc_name] = range_data[key_str]["services"].get(svc_name, 0) + 1
                    
                return range_data
        except Exception as e:
            print(f"[TRAFFIC ERR] {e}")
    return {}

def check_one_number(number):
    try:
        with lock:
            info = number_owner.get(number)
            if not info: return
            panel   = info.get("panel", "zenex")
            service = info.get("service", "unknown")
        if panel == "zenex":        otps = zenex_fetch_otps(number)
        elif panel == "stex":       otps = stex_fetch_otps(number)
        elif panel == "voltx":      otps = voltx_fetch_otps(number)
        elif panel == "slvirtual":
            rental_id = SLVIRTUAL_RENTALS.get(number)
            if not rental_id: return
            otps = slvirtual_fetch_otps(rental_id)
        else: return
        if not otps: return
        clean_expected = re.sub(r'\D', '', str(number))
        for item in otps:
            api_number = re.sub(r'\D', '', str(item.get("number") or ""))
            if not api_number or api_number != clean_expected:
                continue
            uid = item.get("nid") or item.get("otp_id") or str(item)
            uid_key = f"{panel}_{number}_{uid}"
            with lock:
                if uid_key in processed_ids: continue
                processed_ids.add(uid_key)
                if len(processed_ids) > 5000: processed_ids.clear()
            raw     = item.get("otp") or ""
            created = item.get("created_at") or ""
            otp_code = extract_otp(raw) or ""
            if not otp_code or len(str(otp_code)) < 3:
                continue
            with lock:
                bind_key = f"{panel}_{otp_code}"
                existing = OTP_NUMBER_MAP.get(bind_key)
                if existing and existing != number: continue
                OTP_NUMBER_MAP[bind_key] = number
                if len(OTP_NUMBER_MAP) > 2000: OTP_NUMBER_MAP.clear()
            print(f"[WATCHER] ✅ {panel.upper()} OTP → {otp_code} | {number} | {service}")
            process_otp(uid, number, service, otp_code, panel, created)
    except Exception as e:
        print(f"[WATCHER] {number} err: {e}")

def global_otp_watcher():
    print("[WATCHER] ✅ OTP Watcher Started")
    executor = ThreadPoolExecutor(max_workers=30)
    while True:
        try:
            with lock: numbers = list(number_owner.keys())
            if numbers:
                list(executor.map(check_one_number, numbers))
        except Exception as e:
            print(f"[WATCHER] err: {e}")
        time.sleep(SPEED_MODES.get(settings["speed_mode"], 3.0))

print("[PART 1/5] ✅ Loaded Config + API + Watcher")
# ==========================================================
#  ZENEX OTP BOT v18.0 PRO EDITION — PART 2/5
#  User Keyboards + Start + Profile + Balance + Withdraw +
#  Top Reward + Get Number + Change (Cooldown) + Search
# ==========================================================

# ================== USER KEYBOARDS ==================
def main_menu(chat_id=None):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(
        types.KeyboardButton(text=get_label("btn_get_number", "📲 GET NUMBER"),
                              style=btn_style("btn_get_number", "primary"),
                              icon_custom_emoji_id=btn_eid("phone")),
        types.KeyboardButton(text=get_label("btn_profile", "👤 PROFILE"),
                              style=btn_style("btn_profile", "primary"),
                              icon_custom_emoji_id=btn_eid("user")))
    kb.row(
        types.KeyboardButton(text=get_label("btn_top_reward", "🏆 TOP REWARD"),
                              style=btn_style("btn_top_reward", "success"),
                              icon_custom_emoji_id=btn_eid("star")),
        types.KeyboardButton(text=get_label("btn_balance", "💰 MY BALANCE"),
                              style=btn_style("btn_balance", "success"),
                              icon_custom_emoji_id=btn_eid("money")))
    if settings.get("slvirtual_keys"):
        kb.row(
            types.KeyboardButton(text="📡 TRAFFIC CHECK",
                                  style="primary",
                                  icon_custom_emoji_id=btn_eid("graph")))
    if chat_id and is_admin(chat_id):
        kb.row(
            types.KeyboardButton(text=get_label("btn_admin_panel", "👑 ADMIN PANEL"),
                                  style=btn_style("btn_admin_panel", "primary"),
                                  icon_custom_emoji_id=btn_eid("crown")))
    return kb

def panel_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=2)
    btns = [types.InlineKeyboardButton(
        text=get_label("btn_zenex", "⚡ ZENEX"),
        callback_data="panel:zenex",
        style=btn_style("btn_zenex", "primary"),
        icon_custom_emoji_id=btn_eid("fire"))]
    if settings["stex_keys"]:
        btns.append(types.InlineKeyboardButton(
            text=get_label("btn_stex", "🔵 STEX"),
            callback_data="panel:stex",
            style=btn_style("btn_stex", "primary")))
    if settings["voltx_keys"]:
        btns.append(types.InlineKeyboardButton(
            text=get_label("btn_voltx", "🟣 VOLTX"),
            callback_data="panel:voltx",
            style=btn_style("btn_voltx", "primary")))
    if settings["slvirtual_keys"]:
        btns.append(types.InlineKeyboardButton(
            text=get_label("btn_slvirtual", "🌐 SL VIRTUAL"),
            callback_data="panel:slvirtual",
            style=btn_style("btn_slvirtual", "success"),
            icon_custom_emoji_id=btn_eid("rocket")))
    kb.add(*btns)
    return kb

def get_merged_services():
    """
    সব active panel এর services collect করে।
    Returns: list of (display_name, panel, raw_service)
    যেমন: [("FACEBOOK 1", "zenex", "facebook"), ("FACEBOOK 2", "slvirtual", "facebook")]
    Traffic count দিয়ে sort করা।
    """
    # Traffic data (SL Virtual থেকে) — service → count
    traffic = {}
    if settings.get("slvirtual_keys"):
        try:
            traffic = slvirtual_get_traffic_24h() or {}
            # lowercase key
            traffic = {k.lower(): v for k, v in traffic.items()}
        except: pass

    # সব panel এর services collect
    panel_services = []  # list of (panel, service_lower)

    # ZENEX
    if settings.get("zenex_keys"):
        try:
            ranges = zenex_get_ranges()
            svcs = sorted(set(x["service"].lower() for x in ranges))
            if settings["allowed_services"]:
                svcs = [s for s in svcs if s in settings["allowed_services"]]
            for s in svcs:
                panel_services.append(("zenex", s))
        except: pass

    # STEX
    if settings.get("stex_keys"):
        try:
            svcs = sorted(set(s.get("name","").lower() for s in stex_get_services()))
            for s in svcs:
                if s: panel_services.append(("stex", s))
        except: pass

    # VOLTX
    if settings.get("voltx_keys"):
        try:
            svcs = sorted(set(s.get("name","").lower() for s in voltx_get_services()))
            for s in svcs:
                if s: panel_services.append(("voltx", s))
        except: pass

    # SL VIRTUAL
    if settings.get("slvirtual_keys"):
        try:
            raw = slvirtual_get_services()
            svcs = sorted(set(s.get("service","").lower() for s in raw if s.get("service")))
            for s in svcs:
                if s: panel_services.append(("slvirtual", s))
        except: pass

    # Group করা: service_name → list of panels
    from collections import defaultdict
    svc_panels = defaultdict(list)
    for panel, svc in panel_services:
        svc_panels[svc].append(panel)

    # Build final list with numbering
    result = []  # (display_name, panel, raw_service, traffic_count)
    for svc, panels in svc_panels.items():
        tc = traffic.get(svc, 0)
        if len(panels) == 1:
            result.append((svc.upper(), panels[0], svc, tc))
        else:
            for i, panel in enumerate(panels, 1):
                result.append((f"{svc.upper()} {i}", panel, svc, tc))

    # Traffic count দিয়ে sort (বেশি আগে)
    result.sort(key=lambda x: x[3], reverse=True)
    return result

def services_keyboard(panel="zenex", cb="svc"):
    """
    panel="merged" হলে সব panel merge করে দেখায়।
    Otherwise পুরানো single-panel behavior।
    """
    kb = types.InlineKeyboardMarkup(row_width=2)

    if panel == "merged":
        merged = get_merged_services()
        btns = []
        for display, p, svc, tc in merged[:24]:
            tc_str = f" 🔥{tc}" if tc > 0 else ""
            btns.append(types.InlineKeyboardButton(
                text=f"⚡ {display}{tc_str}",
                callback_data=f"{cb}:{p}:{svc}",
                style=btn_style("btn_zenex", "primary"),
                icon_custom_emoji_id=btn_eid("fire")
            ))
        kb.add(*btns)
        kb.row(types.InlineKeyboardButton(
            text=get_label("btn_back", "🔙 BACK"),
            callback_data="back_main",
            style=btn_style("btn_back", "danger"),
            icon_custom_emoji_id=btn_eid("no")))
        return kb

    # Single panel (admin use / legacy)
    if panel == "zenex":
        ranges = zenex_get_ranges()
        services = sorted(set(x["service"].lower() for x in ranges))
        if settings["allowed_services"]:
            services = [s for s in services if s in settings["allowed_services"]]
    elif panel == "stex":
        services = sorted(set(s.get("name", "").lower() for s in stex_get_services()))
    elif panel == "voltx":
        services = sorted(set(s.get("name", "").lower() for s in voltx_get_services()))
    elif panel == "slvirtual":
        raw = slvirtual_get_services()
        services = sorted(set(s.get("service", "").lower() for s in raw if s.get("service")))
    else:
        services = []

    btns = []
    for s in services[:20]:
        display = s.strip().upper()
        if not display: continue
        btns.append(types.InlineKeyboardButton(
            text=f"⚡ {display}",
            callback_data=f"{cb}:{panel}:{s}",
            style=btn_style("btn_zenex", "primary"),
            icon_custom_emoji_id=btn_eid("fire")
        ))
    kb.add(*btns)
    kb.row(types.InlineKeyboardButton(
        text=get_label("btn_back", "🔙 BACK"),
        callback_data="back_main",
        style=btn_style("btn_back", "danger"),
        icon_custom_emoji_id=btn_eid("no")))
    return kb

def numbers_keyboard(service, numbers, panel, country_code=""):
    kb = types.InlineKeyboardMarkup(row_width=1)
    for n in numbers:
        kb.add(types.InlineKeyboardButton(
            text=f"📱  {n}",
            copy_text=types.CopyTextButton(text=n),
            style=btn_style("btn_number", "primary"),
            icon_custom_emoji_id=btn_eid("phone")))
            
    # CHANGE বাটনের জন্য country_code পাস করা
    cb_data = f"change:{panel}:{service}"
    if panel == "slvirtual" and country_code:
        cb_data += f":{country_code}"
        
    kb.row(
        types.InlineKeyboardButton(
            text=get_label("btn_change", "🔄 CHANGE"),
            callback_data=cb_data,
            style=btn_style("btn_change", "success"),
            icon_custom_emoji_id=btn_eid("rocket")),
        types.InlineKeyboardButton(
            text=get_label("btn_back", "🔙 BACK"),
            callback_data="back_main",
            style=btn_style("btn_back", "danger"),
            icon_custom_emoji_id=btn_eid("no")))
            
    if panel == "zenex":
        kb.row(types.InlineKeyboardButton(
            text="📡 SET PREFIX",
            callback_data=f"show_prefix:{panel}:{service}",
            style="primary",
            icon_custom_emoji_id=btn_eid("pin")))
            
    otp_group_link = settings.get("otp_group_link", "")
    if otp_group_link:
        kb.row(types.InlineKeyboardButton(
            text=get_label("btn_otp_group", "📢 OTP GROUP"),
            url=otp_group_link,
            style=btn_style("btn_otp_group", "success"),
            icon_custom_emoji_id=btn_eid("user")))
    else:
        kb.row(types.InlineKeyboardButton(
            text=get_label("btn_otp_group", "📢 OTP GROUP"),
            callback_data="user_otp_group",
            style=btn_style("btn_otp_group", "success"),
            icon_custom_emoji_id=btn_eid("user")))
    return kb

def build_range_inline_keyboard(ranges):
    kb = types.InlineKeyboardMarkup(row_width=1)
    medals = ["🥇", "🥈", "🥉"]
    for i, r in enumerate(ranges[:15], 1):
        rank = medals[i-1] if i <= 3 else f"{i:>2}."
        btn_text = f"{rank}  {r['range']}  │  {r['service'].upper()}  │  {r['hits']}"
        kb.add(types.InlineKeyboardButton(
            text=btn_text,
            copy_text=types.CopyTextButton(text=r['range']),
            style="primary" if i <= 3 else None))
    return kb



# ================== STATE MANAGEMENT ==================
def set_user_state(chat_id, state):
    """User এর state সেট করা"""
    USER_STATE[chat_id] = state
    print(f"[STATE] {chat_id} → {state}")


def get_user_state(chat_id):
    """User এর state পাওয়া"""
    return USER_STATE.get(chat_id)


def clear_user_state(chat_id):
    """User এর state মুছে ফেলা"""
    USER_STATE.pop(chat_id, None)


def is_main_menu_button(text):
    """চেক করা এটা main menu বাটন কি না"""
    if not text:
        return False
    menu_buttons = [
        get_label("btn_get_number", "📲 GET NUMBER"),
        get_label("btn_profile", "👤 PROFILE"),
        get_label("btn_balance", "💰 MY BALANCE"),
        get_label("btn_top_reward", "🏆 TOP REWARD"),
        get_label("btn_admin_panel", "👑 ADMIN PANEL"),
        "GET NUMBER", "PROFILE", "MY BALANCE", "TOP REWARD",
        "ADMIN PANEL",
        "📲 GET NUMBER", "👤 PROFILE",
        "💰 MY BALANCE", "🏆 TOP REWARD", "👑 ADMIN PANEL",
    ]
    return text in menu_buttons


def cancel_flow_and_redirect(msg, target_handler=None):
    """Flow বাতিল করে main menu এ ফিরে যাওয়া"""
    chat_id = msg.chat.id
    clear_user_state(chat_id)
    bot.send_message(chat_id,
        pem("❌ <b>আগের কাজ বাতিল হয়েছে।</b>\n\n"
            f"আবার শুরু করুন।"),
        parse_mode="HTML",
        reply_markup=main_menu(chat_id))

# ================== CHECK JOIN CALLBACK ==================
@bot.callback_query_handler(func=lambda c: c.data == "user_otp_group")
def cb_user_otp_group(call):
    group_link = settings.get("otp_group_link", "")
    if not group_link:
        bot.answer_callback_query(
            call.id,
            "❌ OTP Group link এখনো সেট করা হয়নি! Admin কে বলুন।",
            show_alert=True)
        return
    # সরাসরি URL বাটন সহ message (Telegram popup দেখাবে)
    bot.answer_callback_query(call.id, "📢 OTP Group এ যাচ্ছি...")
    try:
        bot.send_message(call.message.chat.id,
            pem(f"📢 <b>OTP GROUP</b>\n\n👇 ক্লিক করে জয়েন করুন:"),
            parse_mode="HTML",
            reply_markup=types.InlineKeyboardMarkup().add(
                types.InlineKeyboardButton(
                    text="📢 JOIN OTP GROUP",
                    url=group_link,
                    style="success",
                    icon_custom_emoji_id=btn_eid("ok"))))
    except Exception as e:
        print(f"[OTP GROUP] redirect err: {e}")

@bot.callback_query_handler(func=lambda c: c.data == "check_join")
def cb_check_join(call):
    if check_must_join(call.message.chat.id):
        bot.answer_callback_query(call.id, "✅ Verified!")
        try: bot.delete_message(call.message.chat.id, call.message.message_id)
        except: pass
        try: cmd_start(call.message)
        except: pass
    else:
        bot.answer_callback_query(call.id, "❌ এখনো জয়েন করেননি!", show_alert=True)

# ================== /start ==================
@bot.message_handler(commands=['start'])
def cmd_start(msg):
    check_owner_premium(msg)
    chat_id = msg.chat.id
    clear_user_state(chat_id)
    
    # Auto start detect (from ?start=auto)
    args = msg.text.split() if msg.text else []
    if len(args) > 1 and args[1] == "auto":
        # সরাসরি GET NUMBER flow শুরু
        try:
            if not check_must_join(chat_id):
                send_join_message(chat_id)
                return
            get_user(chat_id)
            threading.Thread(target=lambda: db_get_user(chat_id), daemon=True).start()
            # GET NUMBER keyboard দেখানো
            bot.send_message(chat_id,
                pem("📍 <b>Select Service:</b>"),
                parse_mode="HTML",
                reply_markup=services_keyboard("merged", "svc"))
            return
        except Exception as e:
            print(f"[AUTO START] err: {e}")
    if not check_must_join(chat_id):
        send_join_message(chat_id)
        return
    get_user(chat_id)
    threading.Thread(target=lambda: db_get_user(chat_id), daemon=True).start()
    try:
        fb_update(f"users/{chat_id}", {
            "username": msg.from_user.username or "",
            "first_name": msg.from_user.first_name or ""
        })
    except: pass
    args = msg.text.split()
    if len(args) > 1 and args[1].startswith("ref_"):
        try:
            ref_id = int(args[1].replace("ref_", ""))
            if ref_id != chat_id:
                user = db_get_user(chat_id)
                if not user.get("ref_by"):
                    fb_update(f"users/{chat_id}", {"ref_by": ref_id})
                    ref_user = db_get_user(ref_id)
                    new_ref_bal = round(float(ref_user.get("refer_balance", 0)) + settings["refer_reward"], 2)
                    new_ref_count = int(ref_user.get("total_refer", 0)) + 1
                    fb_update(f"users/{ref_id}", {
                        "refer_balance": new_ref_bal,
                        "total_refer": new_ref_count
                    })
                    try:
                        bot.send_message(ref_id, pem(
                            f"🎁 <b>NEW REFERRAL!</b>\n\n"
                            f"👤 একজন নতুন ইউজার জয়েন করেছে আপনার লিংকে!\n"
                            f"💰 আপনি পেয়েছেন: <code>৳{settings['refer_reward']}</code>"),
                            parse_mode="HTML")
                    except: pass
        except: pass
    text = pem(
        f"╔════════════════════╗\n  💎 <b>SUPER OTP WORK</b> 💎\n╚════════════════════╝\n\n"
        f"✅ OTP Watcher: <b>ACTIVE</b>\n"
        f"💸 Per OTP Reward: <b>৳{settings['otp_reward']}</b>\n"
        f"🚀 Panels: <b>SUPER OTP WORK</b>\n\n"
        f"✨ Get number → Send OTP → Earn!")
    bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=main_menu(chat_id))

@bot.message_handler(commands=['chatid'])
def cmd_chatid(msg):
    bot.reply_to(msg, f"<code>{msg.chat.id}</code>", parse_mode="HTML")

@bot.message_handler(commands=['help'])
def cmd_help(msg):
    text = pem(
        f"📖 <b>HELP</b>\n\n"
        f"1️⃣ GET NUMBER → Service select → 3 numbers\n"
        f"2️⃣ Number এ OTP এলে auto reward\n"
        f"3️⃣ MY BALANCE → Withdraw\n"
        f"4️⃣ PROFILE → Refer link\n"
        f"5️⃣ TOP REWARD → Leaderboard")
    bot.send_message(msg.chat.id, text, parse_mode="HTML")

# ================== PROFILE ==================
@bot.message_handler(func=lambda m: m.text in [
    get_label("btn_profile", "👤 PROFILE"), "PROFILE", "👤 PROFILE"
])
def menu_profile(msg):
    clear_user_state(msg.chat.id)
    chat_id = msg.chat.id
    if not check_must_join(chat_id):
        send_join_message(chat_id)
        return
    user = db_get_user(chat_id)
    history = fb_get(f"otp_history/{chat_id}") or {}
    total_otp = len(history) if history else int(user.get("total_otp", 0))
    service_stats = {}
    for v in history.values():
        svc = v.get("service", "unknown").upper()
        service_stats[svc] = service_stats.get(svc, 0) + 1
    top_service = max(service_stats, key=service_stats.get) if service_stats else "N/A"
    ref_count = int(user.get("total_refer", 0))
    ref_balance = float(user.get("refer_balance", 0))
    ref_by = user.get("ref_by", "None")
    text = pem(
        f"╔══════════════════╗\n   👤 <b>MY PROFILE</b>\n╚══════════════════╝\n\n"
        f"🆔 <b>ID:</b> <code>{chat_id}</code>\n"
        f"👤 <b>Name:</b> <code>{user.get('first_name', 'User')}</code>\n"
        f"📅 <b>Joined:</b> <code>{user.get('joined', 'N/A')}</code>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>Total OTP:</b> <code>{total_otp}</code>\n"
        f"📈 <b>Today OTP:</b> <code>{user.get('today_otp', 0)}</code>\n"
        f"🌐 <b>Top Service:</b> <code>{top_service}</code>\n"
        f"💰 <b>Balance:</b> <code>৳{user.get('balance', 0.0)}</code>\n"
        f"💸 <b>Refer Balance:</b> <code>৳{ref_balance}</code>\n"
        f"👥 <b>Total Refer:</b> <code>{ref_count}</code>\n"
        f"🔗 <b>Referred By:</b> <code>{ref_by}</code>")
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton(
        text="🔗 MY REFERRAL LINK",
        callback_data="show_reflink",
        style="primary", icon_custom_emoji_id=btn_eid("user")))
    kb.add(types.InlineKeyboardButton(
        text="📜 OTP HISTORY",
        callback_data="otp_history",
        style="primary", icon_custom_emoji_id=btn_eid("graph")))
    bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "show_reflink")
def cb_show_reflink(call):
    chat_id = call.message.chat.id
    me = bot.get_me()
    ref_link = f"https://t.me/{me.username}?start=ref_{chat_id}"
    bot.answer_callback_query(call.id)
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton(
        text="📋 COPY LINK",
        copy_text=types.CopyTextButton(text=ref_link),
        style="success",
        icon_custom_emoji_id=btn_eid("ok")))
    bot.send_message(chat_id,
        pem(f"🔗 <b>YOUR REFERRAL LINK</b>\n\n"
            f"<code>{ref_link}</code>\n\n"
            f"👥 প্রতি রেফারে পাবেন: <code>৳{settings['refer_reward']}</code>"),
        parse_mode="HTML", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "otp_history")
def cb_otp_history(call):
    chat_id = call.message.chat.id
    history = fb_get(f"otp_history/{chat_id}") or {}
    if not history:
        bot.answer_callback_query(call.id, "❌ No OTP history yet!", show_alert=True)
        return
    items = sorted(history.values(), key=lambda x: x.get("date", ""), reverse=True)[:10]
    lines = [pem(f"📜 <b>LAST 10 OTP</b>\n")]
    for i, o in enumerate(items, 1):
        lines.append(
            f"{i}. 📱 <code>{o.get('number','?')}</code>\n"
            f"   🌐 <code>{o.get('service','?').upper()}</code> | "
            f"🔑 <code>{o.get('otp','?')}</code>\n"
            f"   🕐 <code>{o.get('date','?')}</code>\n")
    bot.answer_callback_query(call.id)
    bot.send_message(chat_id, "\n".join(lines), parse_mode="HTML")

# ================== BALANCE ==================
@bot.message_handler(func=lambda m: m.text in [
    get_label("btn_balance", "💰 MY BALANCE"), "MY BALANCE", "💰 MY BALANCE"
])
def menu_balance(msg):
    clear_user_state(msg.chat.id)
    if not check_must_join(msg.chat.id):
        send_join_message(msg.chat.id)
        return
    user = db_get_user(msg.chat.id)
    text = pem(
        f"╔══════════════════╗\n   💰 <b>MY BALANCE</b>\n╚══════════════════╝\n\n"
        f"💸 <b>Balance:</b> <code>৳{user.get('balance', 0.0)}</code>\n"
        f"💵 <b>Refer Balance:</b> <code>৳{user.get('refer_balance', 0.0)}</code>\n"
        f"📊 <b>Total OTP:</b> <code>{user.get('total_otp', 0)}</code>\n"
        f"📈 <b>Today OTP:</b> <code>{user.get('today_otp', 0)}</code>\n"
        f"📅 <b>Joined:</b> <code>{user.get('joined', 'N/A')}</code>")
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton(
        text="💸 WITHDRAW",
        callback_data="withdraw_start",
        style="success", icon_custom_emoji_id=btn_eid("money")))
    kb.add(types.InlineKeyboardButton(
        text="📊 MY WITHDRAWS",
        callback_data="my_withdraws",
        style="primary", icon_custom_emoji_id=btn_eid("graph")))
    bot.send_message(msg.chat.id, text, parse_mode="HTML", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "withdraw_start")
def cb_withdraw_start(call):
    if not check_must_join(call.message.chat.id):
        bot.answer_callback_query(call.id, "⚠️ Please join first!", show_alert=True)
        send_join_message(call.message.chat.id)
        return
    if not settings.get("withdraw_on", True):
        bot.answer_callback_query(call.id, "❌ WITHDRAW CURRENTLY OFF!", show_alert=True)
        return
    chat_id = call.message.chat.id
    user = db_get_user(chat_id)
    total_bal = float(user.get("balance", 0)) + float(user.get("refer_balance", 0))
    
    methods = settings.get("w_methods", {})
    w_limits = settings.get("w_limits", {})
    
    # প্রতিটা wallet এর min চেক করা
    wallets = [
        ("bkash",   "📱 bKash",   "success"),
        ("nagad",   "📱 Nagad",   "success"),
        ("rocket",  "🚀 Rocket",  "primary"),
        ("binance", "🟡 Binance", "primary"),
    ]
    
    kb = types.InlineKeyboardMarkup(row_width=2)
    available_count = 0
    hidden_wallets = []
    
    for key, label, style in wallets:
        if not methods.get(key):
            continue
        lim = w_limits.get(key, {"min": 50, "max": 1000})
        min_amt = lim.get("min", 50)
        max_amt = lim.get("max", 1000)
        
        # balance min এর চেয়ে কম হলে hide
        if total_bal < min_amt:
            min_str = str(int(min_amt)) if float(min_amt) == int(min_amt) else str(min_amt)
            hidden_wallets.append(f"{label.upper()} (MIN ৳{min_str})")
            continue
        
        def fmt(v):
            return str(int(v)) if float(v) == int(v) else str(v)
        if key == "binance":
            kb.add(types.InlineKeyboardButton(
                text=f"{label.upper()} (MIN ৳{fmt(min_amt)} - MAX ৳{fmt(max_amt)})",
                callback_data=f"w_method:{key}", style=style))
        else:
            kb.add(types.InlineKeyboardButton(
                text=f"{label.upper()} (MIN ৳{fmt(min_amt)} - MAX ৳{fmt(max_amt)})",
                callback_data=f"w_method:{key}", style=style))
        available_count += 1
    
    kb.row(types.InlineKeyboardButton(text=get_label("btn_back", "🔙 BACK"),
        callback_data="back_to_balance", style="danger",
        icon_custom_emoji_id=btn_eid("no")))
    
    # কোন method নেই
    if available_count == 0:
        hidden_text = "\n".join(hidden_wallets) if hidden_wallets else "কোনো method নেই"
        bot.answer_callback_query(call.id,
            f"❌ আপনার balance ৳{round(total_bal, 2)}\n\nনিচের method এর minimum এর চেয়ে কম:\n{hidden_text}",
            show_alert=True)
        return
    
    bot.answer_callback_query(call.id)
    
    # hidden wallets এর জন্য warning
    warn_text = ""
    if hidden_wallets:
        warn_text = f"\n\n⚠️ <b>যে method দেখাচ্ছে না:</b>\n"
        for hw in hidden_wallets:
            warn_text += f"   ❌ {hw}\n"
    
    try:
        bot.edit_message_text(
            pem(f"💸 <b>WITHDRAW</b>\n\n"
                f"💰 Available: <code>৳{round(total_bal, 2)}</code>\n"
                f"👇 পেমেন্ট মেথড সিলেক্ট করুন:{warn_text}"),
            chat_id=chat_id, message_id=call.message.message_id,
            parse_mode="HTML", reply_markup=kb)
    except: pass

@bot.callback_query_handler(func=lambda c: c.data == "back_to_balance")
def cb_back_to_balance(call):
    chat_id = call.message.chat.id
    user = db_get_user(chat_id)
    text = pem(
        f"╔══════════════════╗\n   💰 <b>MY BALANCE</b>\n╚══════════════════╝\n\n"
        f"💸 <b>Balance:</b> <code>৳{user.get('balance', 0.0)}</code>\n"
        f"💵 <b>Refer Balance:</b> <code>৳{user.get('refer_balance', 0.0)}</code>\n"
        f"📊 <b>Total OTP:</b> <code>{user.get('total_otp', 0)}</code>")
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton(text="💸 WITHDRAW",
        callback_data="withdraw_start", style="success",
        icon_custom_emoji_id=btn_eid("money")))
    kb.add(types.InlineKeyboardButton(text="📊 MY WITHDRAWS",
        callback_data="my_withdraws", style="primary",
        icon_custom_emoji_id=btn_eid("graph")))
    try:
        bot.edit_message_text(text, chat_id=chat_id,
            message_id=call.message.message_id,
            parse_mode="HTML", reply_markup=kb)
    except: pass

@bot.callback_query_handler(func=lambda c: c.data.startswith("w_method:"))
def cb_w_method(call):
    method = call.data.split(":")[1]
    chat_id = call.message.chat.id
    bot.answer_callback_query(call.id)
    
    if method == "binance":
        rate = settings.get("binance_rate", 128.0)
        text = pem(
            f"🟡 <b>BINANCE WITHDRAW</b>\n\n"
            f"💱 <b>Rate:</b> <code>৳{rate} = 1 USDT</code>\n\n"
            f"📝 আপনার <b>Binance UID</b> পাঠান:\n\n"
            f"উদাহরণ: <code>123456789</code>\n\n"
            f"👇 এখন UID পাঠান:")
    else:
        text = pem(
            f"📱 <b>{method.upper()} WITHDRAW</b>\n\n"
            f"📝 আপনার {method.upper()} নাম্বার পাঠান:\n\n"
            f"উদাহরণ: <code>01XXXXXXXXX</code>")
    
    try:
        bot.edit_message_text(text,
            chat_id=chat_id, message_id=call.message.message_id,
            parse_mode="HTML")
    except: pass
    bot.register_next_step_handler(call.message, withdraw_get_account, method)

def withdraw_get_account(msg, method):
    chat_id = msg.chat.id
    account = msg.text.strip() if msg.text else ""
    
    # Main menu buttons চেক — বাতিল করতে হবে
    cancel_texts = [
        get_label("btn_get_number", "📲 GET NUMBER"),
        get_label("btn_profile", "👤 PROFILE"),
        get_label("btn_balance", "💰 MY BALANCE"),
        get_label("btn_top_reward", "🏆 TOP REWARD"),
        get_label("btn_admin_panel", "👑 ADMIN PANEL"),
        "GET NUMBER", "PROFILE", "MY BALANCE", "TOP REWARD",
        "ADMIN PANEL", "📲 GET NUMBER", "👤 PROFILE",
        "💰 MY BALANCE", "🏆 TOP REWARD", "👑 ADMIN PANEL",
    ]
    if account in cancel_texts or account.startswith("/"):
        bot.send_message(chat_id,
            pem("❌ <b>Withdraw বাতিল হয়েছে।</b>\n\n"
                f"আবার শুরু করুন।"),
            parse_mode="HTML",
            reply_markup=main_menu(chat_id))
        return
    
    if not account:
        bot.send_message(chat_id, "❌ খালি পাঠাবেন না!")
        return
    w_limits = settings.get("w_limits", {})
    lim = w_limits.get(method, {"min": 50.0, "max": 1000.0})
    min_amt = lim.get("min", 50.0)
    max_amt = lim.get("max", 1000.0)
    if method == "binance":
        rate = settings.get("binance_rate", 128.0)
        amount_text = f"(৳{min_amt:.0f} - ৳{max_amt:.0f})\n💱 Rate: ৳{rate} = 1 USDT"
    else:
        amount_text = f"(৳{min_amt:.0f} - ৳{max_amt:.0f})"
    msg2 = bot.send_message(chat_id,
        pem(f"💰 <b>AMOUNT</b>\n\n"
            f"কত টাকা withdraw করতে চান? {amount_text}"),
        parse_mode="HTML")
    bot.register_next_step_handler(msg2, withdraw_get_amount, method, account)

def withdraw_get_amount(msg, method, account):
    chat_id = msg.chat.id
    text_input = msg.text.strip() if msg.text else ""
    
    # Main menu buttons চেক — বাতিল করতে হবে
    cancel_texts = [
        get_label("btn_get_number", "📲 GET NUMBER"),
        get_label("btn_profile", "👤 PROFILE"),
        get_label("btn_balance", "💰 MY BALANCE"),
        get_label("btn_top_reward", "🏆 TOP REWARD"),
        get_label("btn_admin_panel", "👑 ADMIN PANEL"),
        "GET NUMBER", "PROFILE", "MY BALANCE", "TOP REWARD",
        "ADMIN PANEL", "📲 GET NUMBER", "👤 PROFILE",
        "💰 MY BALANCE", "🏆 TOP REWARD", "👑 ADMIN PANEL",
    ]
    if text_input in cancel_texts or text_input.startswith("/"):
        bot.send_message(chat_id,
            pem("❌ <b>Withdraw বাতিল হয়েছে।</b>\n\n"
                f"আবার শুরু করুন।"),
            parse_mode="HTML",
            reply_markup=main_menu(chat_id))
        return
    
    try:
        amount = float(text_input)
    except:
        bot.send_message(chat_id, "❌ সঠিক amount দিন!")
        return
    
    w_limits = settings.get("w_limits", {})
    lim = w_limits.get(method, {"min": 50.0, "max": 1000.0})
    min_amt = lim.get("min", 50.0)
    max_amt = lim.get("max", 1000.0)
    
    if amount < min_amt or amount > max_amt:
        if method == "binance":
            bot.send_message(chat_id,
                pem(f"❌ <b>BINANCE Limit</b>\n\n"
                    f"Min: <code>{min_amt} USDT</code> | Max: <code>{max_amt} USDT</code>\n"
                    f"আপনি পাঠিয়েছেন: <code>{amount} USDT</code>"),
                parse_mode="HTML")
        else:
            bot.send_message(chat_id,
                f"❌ Amount ৳{min_amt} - ৳{max_amt} এর মধ্যে হতে হবে!")
        return
    
    user = db_get_user(chat_id)
    total_bal = float(user.get("balance", 0)) + float(user.get("refer_balance", 0))
    if amount > total_bal:
        bot.send_message(chat_id, "❌ আপনার পর্যাপ্ত balance নেই!")
        return
    
    if method == "binance":
        rate = settings.get("binance_rate", 128.0)
        usdt_amount = round(amount / rate, 4)
        text = pem(
            f"⚠️ <b>CONFIRM WITHDRAW</b>\n\n"
            f"💳 <b>Method:</b> <code>BINANCE</code>\n"
            f"🆔 <b>Binance UID:</b> <code>{account}</code>\n"
            f"💰 <b>Amount:</b> <code>৳{amount}</code>\n"
            f"💱 <b>You will receive:</b> <code>{usdt_amount} USDT</code>\n"
            f"📊 <b>Rate:</b> <code>৳{rate} = 1 USDT</code>\n\n"
            f"নিশ্চিত হলে CONFIRM চাপুন:")
    else:
        text = pem(
            f"⚠️ <b>CONFIRM WITHDRAW</b>\n\n"
            f"💳 <b>Method:</b> <code>{method.upper()}</code>\n"
            f"📝 <b>Account:</b> <code>{account}</code>\n"
            f"💰 <b>Amount:</b> <code>৳{amount}</code>\n\n"
            f"নিশ্চিত হলে CONFIRM চাপুন:")
    
    # Temp ID তৈরি
    temp_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
    TEMP_WITHDRAW[temp_id] = {
        "method": method,
        "account": account,
        "amount": amount,
        "chat_id": chat_id,
    }
    
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton(text="✅ CONFIRM",
            callback_data=f"wc:{temp_id}",
            style="success", icon_custom_emoji_id=btn_eid("ok")),
        types.InlineKeyboardButton(text="❌ CANCEL",
            callback_data="w_cancel",
            style="danger", icon_custom_emoji_id=btn_eid("no")))
    bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("wc:"))
def cb_w_confirm(call):
    temp_id = call.data.split(":", 1)[1]
    data = TEMP_WITHDRAW.get(temp_id)
    if not data:
        bot.answer_callback_query(call.id, "❌ Session expired! আবার try করুন।", show_alert=True)
        return
    method = data["method"]
    account = data["account"]
    amount = float(data["amount"])
    chat_id = data["chat_id"]
    TEMP_WITHDRAW.pop(temp_id, None)
    user = db_get_user(chat_id)
    total_bal = float(user.get("balance", 0)) + float(user.get("refer_balance", 0))
    if amount > total_bal:
        bot.answer_callback_query(call.id, "❌ Balance কমে গেছে!", show_alert=True)
        return
    new_bal = round(total_bal - amount, 2)
    fb_update(f"users/{chat_id}", {"balance": new_bal, "refer_balance": 0})
    wd_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    fb_set(f"withdraws/{wd_id}", {
        "wd_id": wd_id, "chat_id": chat_id, "method": method,
        "account": account, "amount": amount, "status": "pending",
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    bot.answer_callback_query(call.id, "✅ Request submitted!")
    try: bot.delete_message(chat_id, call.message.message_id)
    except: pass
    if method == "binance":
        rate = settings.get("binance_rate", 128.0)
        usdt_amount = round(amount / rate, 4)
        bot.send_message(chat_id,
            pem(f"✅ <b>WITHDRAW REQUEST SUBMITTED</b>\n\n"
                f"🆔 <b>ID:</b> <code>{wd_id}</code>\n"
                f"💳 <b>Method:</b> <code>BINANCE</code>\n"
                f"🆔 <b>Binance UID:</b> <code>{account}</code>\n"
                f"💰 <b>Amount:</b> <code>৳{amount}</code>\n"
                f"💱 <b>You will receive:</b> <code>{usdt_amount} USDT</code>\n"
                f"📊 <b>Status:</b> <code>⏳ PENDING</code>\n\n"
                f"Admin approve করলে USDT পাবেন।"),
            parse_mode="HTML")
    else:
        bot.send_message(chat_id,
            pem(f"✅ <b>WITHDRAW REQUEST SUBMITTED</b>\n\n"
                f"🆔 <b>ID:</b> <code>{wd_id}</code>\n"
                f"💳 <b>Method:</b> <code>{method.upper()}</code>\n"
                f"📝 <b>Account:</b> <code>{account}</code>\n"
                f"💰 <b>Amount:</b> <code>৳{amount}</code>\n"
                f"📊 <b>Status:</b> <code>⏳ PENDING</code>\n\n"
                f"Admin approve করলে টাকা পাবেন।"),
            parse_mode="HTML")

    # Withdraw notification message
    if method == "binance":
        rate = settings.get("binance_rate", 128.0)
        usdt_amount = round(amount / rate, 4)
        wd_msg_text = pem(
            f"💸 <b>NEW WITHDRAW REQUEST (BINANCE)</b>\n\n"
            f"🆔 <b>ID:</b> <code>{wd_id}</code>\n"
            f"👤 <b>User:</b> <code>{chat_id}</code>\n"
            f"💳 <b>Method:</b> <code>BINANCE</code>\n"
            f"🆔 <b>Binance UID:</b> <code>{account}</code>\n"
            f"💰 <b>Amount:</b> <code>৳{amount}</code>\n"
            f"💱 <b>Send USDT:</b> <code>{usdt_amount} USDT</code>\n"
            f"📊 <b>Rate:</b> <code>৳{rate} = 1 USDT</code>\n"
            f"📅 <b>Status:</b> <code>⏳ PENDING</code>\n\n"
            f"⚙️ Admin — Approve / Reject করুন:")
    else:
        wd_msg_text = pem(
            f"💸 <b>NEW WITHDRAW REQUEST</b>\n\n"
            f"🆔 <b>ID:</b> <code>{wd_id}</code>\n"
            f"👤 <b>User:</b> <code>{chat_id}</code>\n"
            f"💳 <b>Method:</b> <code>{method.upper()}</code>\n"
            f"📝 <b>Account:</b> <code>{account}</code>\n"
            f"💰 <b>Amount:</b> <code>৳{amount}</code>\n"
            f"📊 <b>Status:</b> <code>⏳ PENDING</code>\n\n"
            f"⚙️ Admin — Approve / Reject করুন:")

    wd_kb = types.InlineKeyboardMarkup(row_width=2)
    wd_kb.add(
        types.InlineKeyboardButton(text="✅ APPROVE",
            callback_data=f"w_admin:approve:{wd_id}", style="success"),
        types.InlineKeyboardButton(text="❌ REJECT",
            callback_data=f"w_admin:reject:{wd_id}", style="danger"))

    # শুধু Admins এ পাঠানো হবে (Payment Channel এ না)
    for admin_id in [ADMIN_ID] + [int(k) for k, v in EXTRA_ADMINS.items() if v.get("active")]:
        try:
            bot.send_message(admin_id, wd_msg_text,
                parse_mode="HTML", reply_markup=wd_kb)
        except: pass

@bot.callback_query_handler(func=lambda c: c.data == "w_cancel")
def cb_w_cancel(call):
    bot.answer_callback_query(call.id, "❌ Cancelled")
    try: bot.delete_message(call.message.chat.id, call.message.message_id)
    except: pass

@bot.callback_query_handler(func=lambda c: c.data == "my_withdraws")
def cb_my_withdraws(call):
    chat_id = call.message.chat.id
    all_wd = fb_get("withdraws") or {}
    my_wd = [v for v in all_wd.values() if str(v.get("chat_id")) == str(chat_id)]
    if not my_wd:
        bot.answer_callback_query(call.id, "❌ No withdraws yet!", show_alert=True)
        return
    my_wd.sort(key=lambda x: x.get("date", ""), reverse=True)
    lines = [pem(f"📊 <b>MY WITHDRAWS</b> ({len(my_wd)})\n")]
    for w in my_wd[:10]:
        status_emoji = {"pending": "⏳", "approved": "✅", "rejected": "❌"}.get(w.get("status"), "❓")
        lines.append(
            f"{status_emoji} <code>{w.get('wd_id','?')}</code>\n"
            f"   💰 ৳{w.get('amount', 0)} | {w.get('method','?').upper()}\n"
            f"   📊 {w.get('status','?').upper()}\n"
            f"   🕐 {w.get('date','?')}\n")
    bot.answer_callback_query(call.id)
    bot.send_message(chat_id, "\n".join(lines), parse_mode="HTML")

# ================== TOP REWARD ==================
@bot.message_handler(func=lambda m: m.text in [
    get_label("btn_top_reward", "🏆 TOP REWARD"), "TOP REWARD", "🏆 TOP REWARD"
])
def menu_top_reward(msg):
    clear_user_state(msg.chat.id)
    if not check_must_join(msg.chat.id):
        send_join_message(msg.chat.id)
        return
    chat_id = msg.chat.id
    today = datetime.now().strftime("%Y-%m-%d")
    today_otps = db_today_otps()
    user_counts = {}
    for o in today_otps:
        cid = str(o.get("chat_id"))
        user_counts[cid] = user_counts.get(cid, 0) + 1
    sorted_users = sorted(user_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    lines = [pem(
        f"╔══════════════════╗\n   🏆 <b>TOP REWARD</b>\n╚══════════════════╝\n\n"
        f"📅 <b>Date:</b> <code>{today}</code>\n"
        f"📊 <b>Total OTP Today:</b> <code>{len(today_otps)}</code>\n"
        f"👥 <b>Active Users:</b> <code>{len(user_counts)}</code>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🏆 <b>LEADERBOARD</b>\n")]
    medals = ["🥇", "🥈", "🥉"]
    for i, (cid, count) in enumerate(sorted_users, 1):
        medal = medals[i-1] if i <= 3 else f"{i}."
        name = "User"
        try:
            u = fb_get(f"users/{cid}") or {}
            name = u.get("first_name") or u.get("username") or f"User_{cid}"
        except: pass
        prize = ""
        if i <= settings.get("top_reward_count", 3):
            p = settings.get("top_reward_prices", {}).get(str(i), 0)
            if p: prize = f" 🎁 ৳{p}"
        lines.append(f"{medal} <b>{name}</b> — <code>{count} OTP</code>{prize}")
    if not sorted_users:
        lines.append("❌ আজকে এখনো কেউ OTP আনে নি।")
    lines.append(f"\n━━━━━━━━━━━━━━━━━━\n💡 প্রতিদিন রিসেট হয়!")
    bot.send_message(chat_id, "\n".join(lines), parse_mode="HTML")

# ================== TRAFFIC CHECK ==================
@bot.message_handler(func=lambda m: m.text == "📡 TRAFFIC CHECK")
def menu_traffic_check(msg):
    clear_user_state(msg.chat.id)
    if not check_must_join(msg.chat.id):
        send_join_message(msg.chat.id)
        return
    if not settings.get("slvirtual_keys"):
        bot.send_message(msg.chat.id, pem("❌ <b>SL Virtual key নেই।</b>"), parse_mode="HTML")
        return
        
    # সার্ভিস সিলেক্ট করার বাটন দেখানো
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton(text="📘 FACEBOOK TRAFFIC", callback_data="show_traffic:facebook", style="primary"))
    kb.add(types.InlineKeyboardButton(text="💬 WHATSAPP TRAFFIC", callback_data="show_traffic:whatsapp", style="success"))
    kb.add(types.InlineKeyboardButton(text="📸 INSTAGRAM TRAFFIC", callback_data="show_traffic:instagram", style="danger"))
    
    bot.send_message(msg.chat.id, pem("📡 <b>কোন সার্ভিসের ট্রাফিক দেখতে চান?</b>"), parse_mode="HTML", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("show_traffic:"))
def cb_show_traffic(call):
    svc_filter = call.data.split(":")[1]
    bot.answer_callback_query(call.id, "⏳ Loading...")
    threading.Thread(target=show_traffic_data, args=(call.message.chat.id, svc_filter), daemon=True).start()

@bot.callback_query_handler(func=lambda c: c.data.startswith("traffic_refresh:"))
def cb_traffic_refresh_new(call):
    svc_filter = call.data.split(":")[1]
    bot.answer_callback_query(call.id, "⏳ Refreshing...")
    threading.Thread(target=show_traffic_data_edit, args=(call.message.chat.id, call.message.message_id, svc_filter), daemon=True).start()

def build_traffic_text_and_kb(svc_filter="facebook"):
    import pycountry
    import phonenumbers
    from phonenumbers import geocoder
    
    all_traffic = {}
    
    # ১. SL Virtual এর ডাটা
    sl_traffic = slvirtual_get_traffic_24h() or {}
    for key, info in sl_traffic.items():
        for s_name, s_count in info["services"].items():
            if s_name.lower() == svc_filter.lower():
                match = re.search(r'([^ ]+)\s+([^(]+)\(([^)]+)\)', key)
                if match:
                    flag = match.group(1)
                    country_name = match.group(2).strip()
                    prefix = match.group(3).strip()
                    clean_key = f"{flag} {country_name}"
                    if clean_key not in all_traffic:
                        all_traffic[clean_key] = {"total": 0, "prefixes": []}
                    all_traffic[clean_key]["total"] += s_count
                    if prefix not in all_traffic[clean_key]["prefixes"]:
                        all_traffic[clean_key]["prefixes"].append(prefix)

    # ২. ZENEX এর ডাটা
    zenex_ranges = zenex_get_ranges(svc_filter) or []
    for r in zenex_ranges:
        pfx = str(r.get("range", "")).replace("XXX", "")
        hits = r.get("hits", 0)
        service_name = r.get("service", "").lower()
        
        if pfx and hits > 0 and service_name == svc_filter.lower():
            flag, c_name, c_code = "🌐", "GLOBAL", "UN"
            try:
                test_num = "+" + re.sub(r'[^0-9]', '', pfx)
                parsed = phonenumbers.parse(test_num, None)
                region = geocoder.region_code_for_number(parsed)
                if region:
                    country_obj = pycountry.countries.get(alpha_2=region)
                    c_name = country_obj.name.upper() if country_obj else geocoder.description_for_number(parsed, "en").upper()
                    flag = "".join(chr(ord(c) + 127397) for c in region.upper())
            except: pass
            
            clean_key = f"{flag} {c_name}"
            if clean_key not in all_traffic:
                all_traffic[clean_key] = {"total": 0, "prefixes": []}
            all_traffic[clean_key]["total"] += hits
            if pfx not in all_traffic[clean_key]["prefixes"]:
                all_traffic[clean_key]["prefixes"].append(pfx)

    if not all_traffic:
        return None, None

    sorted_data = sorted(all_traffic.items(), key=lambda x: x[1]["total"], reverse=True)
    total_otps = sum(info["total"] for _, info in sorted_data)

    lines = [pem(
        f"╔══════════════════════╗\n"
        f"   📡 <b>{svc_filter.upper()} TRAFFIC</b>\n"
        f"╚══════════════════════╝\n\n"
        f"⏱ <b>Top Active Countries</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
    )]
    
    medals = ["🥇", "🥈", "🥉"]
    country_counts = {}
    
    for i, (country_name, info) in enumerate(sorted_data[:10], 1):
        if country_name not in country_counts:
            country_counts[country_name] = 1
            display_name = country_name
        else:
            country_counts[country_name] += 1
            display_name = f"{country_name} {country_counts[country_name]}"
            
        rank = medals[i-1] if i <= 3 else f"{i:>2}."
        count = info["total"]
        percent = round((count / total_otps) * 100, 1) if total_otps else 0
        bar_len = int(percent / 10)
        bar = "🟩" * bar_len + "⬜" * (10 - bar_len)
        
        lines.append(
            f"{rank} <b>{display_name}</b>\n"
            f"   {bar}\n"
            f"   <code>{count}</code> OTP <i>({percent}%)</i>\n"
        )
        
    lines.append(f"━━━━━━━━━━━━━━━━━━━━━━\n💡 <i>এই দেশগুলোতে OTP এর ভিড় বেশি!</i>")
    
    # শুধু REFRESH বাটন রাখা হয়েছে
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton(
        text="🔄 REFRESH",
        callback_data=f"traffic_refresh:{svc_filter}",
        style="primary",
        icon_custom_emoji_id=btn_eid("rocket")))
        
    return "\n".join(lines), kb

def show_traffic_data(chat_id, svc_filter="facebook"):
    try:
        text, kb = build_traffic_text_and_kb(svc_filter)
        if not text:
            bot.send_message(chat_id,
                pem("❌ <b>No traffic data found (last 24h)</b>"),
                parse_mode="HTML")
            return
        bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=kb)
    except Exception as e:
        bot.send_message(chat_id, f"❌ Error: {e}")

@bot.callback_query_handler(func=lambda c: c.data == "traffic_refresh")
def cb_traffic_refresh(call):
    bot.answer_callback_query(call.id, "⏳ Refreshing...")
    try:
        bot.edit_message_text(
            pem("⏳ <b>TRAFFIC DATA রিফ্রেশ হচ্ছে...</b>"),
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML")
    except: pass
    threading.Thread(target=show_traffic_data_edit,
        args=(call.message.chat.id, call.message.message_id), daemon=True).start()

def show_traffic_data_edit(chat_id, message_id, svc_filter="facebook"):
    try:
        text, kb = build_traffic_text_and_kb(svc_filter)
        if not text:
            try:
                bot.edit_message_text(pem("❌ <b>No traffic data (last 24h)</b>"),
                    chat_id=chat_id, message_id=message_id, parse_mode="HTML")
            except: pass
            return
        try:
            bot.edit_message_text(text, chat_id=chat_id,
                message_id=message_id, parse_mode="HTML", reply_markup=kb)
        except: pass
    except Exception as e:
        print(f"[TRAFFIC] err: {e}")

# ================== GET NUMBER ==================
@bot.message_handler(func=lambda m: m.text in [
    get_label("btn_get_number", "📲 GET NUMBER"), "GET NUMBER", "📲 GET NUMBER"
])
def menu_get_number(msg):
    clear_user_state(msg.chat.id)
    check_owner_premium(msg)
    if not check_must_join(msg.chat.id):
        send_join_message(msg.chat.id)
        return
    bot.send_message(msg.chat.id, pem(f"📍 <b>Select Service:</b>"),
                     parse_mode="HTML",
                     reply_markup=services_keyboard("merged", "svc"))

@bot.callback_query_handler(func=lambda c: c.data.startswith("panel:"))
def cb_panel(call):
    if not check_must_join(call.message.chat.id):
        bot.answer_callback_query(call.id, "⚠️ Please join first!", show_alert=True)
        send_join_message(call.message.chat.id)
        return
    panel = call.data.split(":")[1]
    get_user(call.message.chat.id)["panel"] = panel
    bot.answer_callback_query(call.id)
    try:
        bot.edit_message_text(pem(f"📍 <b>Select Service:</b>"),
                              chat_id=call.message.chat.id,
                              message_id=call.message.message_id,
                              parse_mode="HTML",
                              reply_markup=services_keyboard(panel, "svc"))
    except: pass


def show_merged_top_ranges(chat_id, message_id, svc):
    import phonenumbers
    from phonenumbers import geocoder
    import pycountry
    import time
    
    def get_full_country_info(prefix):
        try:
            clean_pfx = re.sub(r'[^0-9]', '', str(prefix))
            if not clean_pfx: return "🌐", "GLOBAL", "UN"
            
            test_num = "+" + clean_pfx
            parsed = phonenumbers.parse(test_num, None)
            region = geocoder.region_code_for_number(parsed)
            
            if region:
                country_obj = pycountry.countries.get(alpha_2=region)
                if country_obj:
                    c_name = country_obj.name.upper()
                else:
                    c_name = geocoder.description_for_number(parsed, "en").upper()
                
                flag = "".join(chr(ord(c) + 127397) for c in region.upper())
                return flag, c_name, region
        except:
            pass
        return "🌐", "GLOBAL", "UN"

    all_ranges = []
    
    # ১. SL Virtual এর রেঞ্জ আনা (রিট্রাই লজিক সহ)
    sl_countries = []
    for attempt in range(3):
        try:
            sl_countries = slvirtual_get_countries(svc)
            if sl_countries: break
        except Exception as e:
            print(f"[SLV RETRY {attempt+1}/3] {e}")
            time.sleep(1)
            
    for c in sl_countries:
        pfx = str(c.get("prefix", ""))
        country = c.get("country", "").upper()
        flag = c.get("flag", "🌐")
        c_code = c.get("countryCode", "").upper()
        if pfx:
            all_ranges.append({
                "type": "slvirtual",
                "prefix": pfx,
                "flag": flag,
                "country": country,
                "country_code": c_code
            })
            
    # ২. Zenex এর রেঞ্জ আনা (রিট্রাই লজিক সহ)
    zenex_ranges = []
    for attempt in range(3):
        try:
            zenex_ranges = zenex_get_ranges(svc)
            if zenex_ranges is not None: break
        except Exception as e:
            print(f"[ZENEX RETRY {attempt+1}/3] {e}")
            time.sleep(1)

    for r in zenex_ranges:
        pfx = str(r.get("range", "")).replace("XXX", "")
        if not pfx: continue
        
        flag, c_name, c_code = get_full_country_info(pfx)

        all_ranges.append({
            "type": "zenex",
            "prefix": pfx,
            "flag": flag,
            "country": c_name,
            "country_code": c_code
        })

    if not all_ranges:
        bot.send_message(chat_id, pem("❌ <b>No ranges found or API is down. Please try again!</b>"), parse_mode="HTML")
        return

    # ডুপ্লিকেট প্রিফিক্স বাদ দেওয়া
    seen = set()
    unique_ranges = []
    for r in all_ranges:
        if r["prefix"] not in seen:
            unique_ranges.append(r)
            seen.add(r["prefix"])

    country_counts = {}
    kb = types.InlineKeyboardMarkup(row_width=1)
    lines = [pem(f"╔══════════════════════╗\n   📡 <b>{svc.upper()} RANGES</b>\n╚══════════════════════╝\n")]

    for i, r in enumerate(unique_ranges[:24], 1):
        if r['country_code']:
            base_name = f"{r['flag']} {r['country']} ({r['country_code']})"
        else:
            base_name = f"{r['flag']} {r['country']}"
            
        if base_name not in country_counts:
            country_counts[base_name] = 1
            display_name = base_name
        else:
            country_counts[base_name] += 1
            display_name = f"{base_name} {country_counts[base_name]}"
            
        if r["type"] == "slvirtual":
            cb_data = f"slv_getnum:{svc}:{r['country_code']}:{r['prefix']}"
            style = "success"
        else:
            cb_data = f"user_setpfx:zenex:{svc}:{r['prefix']}"
            style = "primary"
            
        kb.add(types.InlineKeyboardButton(text=display_name, callback_data=cb_data, style=style))

    kb.row(types.InlineKeyboardButton(
        text="🔙 BACK", callback_data="back_main", style="danger"))

    try:
        bot.edit_message_text("\n".join(lines), chat_id=chat_id,
            message_id=message_id, parse_mode="HTML", reply_markup=kb)
    except Exception as e:
        print(f"[MERGED RANGES ERR] {e}")

@bot.callback_query_handler(func=lambda c: c.data.startswith("svc:"))
def cb_service(call):
    if not check_must_join(call.message.chat.id):
        bot.answer_callback_query(call.id, "⚠️ Please join first!", show_alert=True)
        send_join_message(call.message.chat.id)
        return
        
    _, panel, svc = call.data.split(":", 2)
    get_user(call.message.chat.id)["service"] = svc
    
    bot.answer_callback_query(call.id, "⏳ Loading Ranges...")
    try:
        bot.edit_message_text(pem(f"⏳ <b>Loading Active Ranges for {svc.upper()}...</b>"),
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML")
    except: pass
        
    # সরাসরি রেঞ্জ লিস্ট কল করা
    threading.Thread(target=show_merged_top_ranges, args=(call.message.chat.id, call.message.message_id, svc), daemon=True).start()

def show_slvirtual_countries(chat_id, message_id, svc):
    countries = slvirtual_get_countries(svc)
    if not countries:
        try:
            bot.edit_message_text(pem("❌ <b>No countries found!</b>"),
                chat_id=chat_id, message_id=message_id, parse_mode="HTML")
        except: pass
        return
        
    seen = set()
    unique_countries = []
    for c in countries:
        code_str = c.get("countryCode", "")
        if code_str and code_str not in seen:
            unique_countries.append(c)
            seen.add(code_str)

    kb = types.InlineKeyboardMarkup(row_width=2)
    styles = ["success", "primary", "danger"]
    
    for i, c in enumerate(unique_countries[:24]):
        flag = c.get("flag", "🌐")
        country = c.get("country", "Unknown").upper()
        c_code = c.get("countryCode", "").upper()
        
        kb.add(types.InlineKeyboardButton(
            text=f"{flag} {country} ({c_code})",
            callback_data=f"sc:{svc}:{c_code}",
            style=styles[i % 3]))
            
    kb.row(types.InlineKeyboardButton(
        text="🔙 BACK", callback_data="back_main", style="danger"))
        
    text = pem(
        f"╔══════════════════════╗\n"
        f"   🌐 <b>SELECT COUNTRY</b>\n"
        f"╚══════════════════════╝\n\n"
        f"🔧 <b>Service:</b> <code>{svc.upper()}</code>\n"
        f"👇 দেশ সিলেক্ট করো:")
    try:
        bot.edit_message_text(text, chat_id=chat_id, message_id=message_id,
            parse_mode="HTML", reply_markup=kb)
    except: pass


# ================== CHANGE WITH COOLDOWN ==================
@bot.callback_query_handler(func=lambda c: c.data.startswith("change:"))
def cb_change(call):
    try:
        if not check_must_join(call.message.chat.id):
            bot.answer_callback_query(call.id, "⚠️ Please join first!", show_alert=True)
            send_join_message(call.message.chat.id)
            return

        chat_id = call.message.chat.id
        now = time.time()
        cooldown = settings.get("change_cooldown_seconds", 10)
        last = CHANGE_COOLDOWN.get(chat_id, 0)
        elapsed = now - last
        remaining = cooldown - elapsed

        if remaining > 0:
            bot.answer_callback_query(
                call.id,
                f"⏳ Please wait {int(remaining) + 1}s before changing numbers again!",
                show_alert=True)
            return

        CHANGE_COOLDOWN[chat_id] = now
        
        parts = call.data.split(":")
        panel = parts[1]
        svc = parts[2]
        
        # country_code বের করা (যদি থাকে)
        country_code = parts[3] if len(parts) > 3 else get_user(chat_id).get("slv_country", "ET")
        
        if panel == "slvirtual":
            get_user(chat_id)["slv_country"] = country_code

        bot.answer_callback_query(call.id, "🔄 Getting new numbers...")
        try:
            bot.edit_message_text("⏳ Getting new numbers...",
                                  chat_id=chat_id,
                                  message_id=call.message.message_id)
        except: pass
        
        fetch_and_show(chat_id, call.message.message_id, panel, svc, country_code)
    except Exception as e:
        print(f"[CHANGE ERR] {e}")

@bot.callback_query_handler(func=lambda c: c.data == "back_main")
def cb_back(call):
    try:
        bot.edit_message_text("🏠 Main Menu",
                              chat_id=call.message.chat.id,
                              message_id=call.message.message_id)
    except: pass
    bot.send_message(call.message.chat.id, "Choose an option:",
                 reply_markup=main_menu(call.message.chat.id))

# ================== SEARCH PREFIX ==================
@bot.message_handler(func=lambda m: m.text in [
    "🔍 SEARCH PREFIX", "SEARCH PREFIX",
    get_label("btn_search", "🔍 SEARCH PREFIX")
])
def menu_search(msg):
    check_owner_premium(msg)
    if not check_must_join(msg.chat.id):
        send_join_message(msg.chat.id)
        return
    bot.send_message(msg.chat.id, pem(f"📍 <b>Select Service to Search:</b>"),
                     parse_mode="HTML",
                     reply_markup=services_keyboard("zenex", "search"))

@bot.callback_query_handler(func=lambda c: c.data.startswith("search:"))
def cb_search(call):
    if not check_must_join(call.message.chat.id):
        bot.answer_callback_query(call.id, "⚠️ Please join first!", show_alert=True)
        send_join_message(call.message.chat.id)
        return
    _, panel, svc = call.data.split(":", 2)
    ranges = zenex_get_ranges(svc)
    if not ranges:
        bot.answer_callback_query(call.id, "❌ Not found!")
        return
    lines = [pem(f"🔍 <b>{svc.upper()} PREFIXES:</b>\n")]
    kb = types.InlineKeyboardMarkup(row_width=1)
    for r in ranges[:10]:
        lines.append(f"📡 <code>{r['range']}</code> | {r['tag']} | 🔥 <b>{r['hits']}</b>")
        kb.add(types.InlineKeyboardButton(
            text=f"➕ {r['range']}",
            callback_data=f"setpfx:{panel}:{svc}:{r['range']}",
            style=btn_style("btn_zenex", "primary"),
            icon_custom_emoji_id=btn_eid("pin")))
    kb.row(types.InlineKeyboardButton(
        text=get_label("btn_back", "🔙 BACK"),
        callback_data="back_main",
        style=btn_style("btn_back", "danger"),
        icon_custom_emoji_id=btn_eid("no")))
    try:
        bot.edit_message_text("\n".join(lines),
                              chat_id=call.message.chat.id,
                              message_id=call.message.message_id,
                              parse_mode="HTML", reply_markup=kb)
    except: pass

@bot.callback_query_handler(func=lambda c: c.data.startswith("setpfx:"))
def cb_setpfx(call):
    if not check_must_join(call.message.chat.id):
        bot.answer_callback_query(call.id, "⚠️ Please join first!", show_alert=True)
        send_join_message(call.message.chat.id)
        return
    parts = call.data.split(":")
    panel, svc, prefix = parts[1], parts[2], parts[3]
    get_user(call.message.chat.id)["prefix"] = prefix
    bot.answer_callback_query(call.id, f"✅ Prefix: {prefix}")
    try:
        bot.edit_message_text("⏳ Getting numbers...",
                              chat_id=call.message.chat.id,
                              message_id=call.message.message_id)
    except: pass
    fetch_and_show(call.message.chat.id, call.message.message_id, panel, svc)

# ================== ACTIVE RANGE (compat) ==================
@bot.message_handler(func=lambda m: m.text in [
    "📊 ACTIVE RANGE", "ACTIVE RANGE",
    get_label("btn_active_range", "📊 ACTIVE RANGE")
])
def menu_active(msg):
    check_owner_premium(msg)
    if not check_must_join(msg.chat.id):
        send_join_message(msg.chat.id)
        return
    ranges = zenex_get_ranges()
    if not ranges:
        bot.send_message(msg.chat.id, pem("❌ <b>No data!</b>"), parse_mode="HTML")
        return
    text = pem(
        f"╔══════════════════════════════╗\n   📊 <b>TOP ACTIVE RANGES</b> 📊\n╚══════════════════════════════╝\n\n"
        f"🏆 <b>Rank</b> │ 📡 <b>Prefix</b> │ 🌐 <b>Service</b> │ 🔥 <b>Hits</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👆 <i>যেকোনো বাটনে ট্যাপ করলে prefix কপি হবে!</i>")
    bot.send_message(msg.chat.id, text, parse_mode="HTML",
                     reply_markup=build_range_inline_keyboard(ranges))

print("[PART 2/5] ✅ Loaded User Handlers")
# ==========================================================
#  ZENEX OTP BOT v18.0 PRO EDITION — PART 3/5
#  Admin Menu + Set Speed + Filter Service + Today OTP +
#  All Users + Manage Keys + Search User + Emoji Toggle
# ==========================================================

# ================== ADMIN MENU ==================
def admin_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(
        types.KeyboardButton(text=get_label("btn_set_speed", "⚡ SET SPEED"),
                              style=btn_style("btn_set_speed", "primary"),
                              icon_custom_emoji_id=btn_eid("rocket")),
        types.KeyboardButton(text=get_label("btn_filter", "🔧 FILTER SERVICE"),
                              style=btn_style("btn_filter", "primary"),
                              icon_custom_emoji_id=btn_eid("gear")))
    kb.row(
        types.KeyboardButton(text=get_label("btn_today_otp", "📊 TODAY OTP"),
                              style=btn_style("btn_today_otp", "success"),
                              icon_custom_emoji_id=btn_eid("graph")),
        types.KeyboardButton(text=get_label("btn_all_users", "👥 ALL USERS"),
                              style=btn_style("btn_all_users", "success"),
                              icon_custom_emoji_id=btn_eid("user")))
    kb.row(
        types.KeyboardButton(text=get_label("btn_manage_keys", "🔑 MANAGE KEYS"),
                              style=btn_style("btn_manage_keys", "primary"),
                              icon_custom_emoji_id=btn_eid("key")),
        types.KeyboardButton(text=get_label("btn_custom_emoji", "🎨 SET CUSTOM EMOJI"),
                              style=btn_style("btn_custom_emoji", "primary"),
                              icon_custom_emoji_id=btn_eid("crown")))
    kb.row(
        types.KeyboardButton(text=get_label("btn_custom_color", "🎨 CUSTOM COLOR"),
                              style=btn_style("btn_custom_color", "primary"),
                              icon_custom_emoji_id=btn_eid("crown")),
        types.KeyboardButton(text=get_label("btn_emoji_toggle", "🎭 EMOJI ON/OFF"),
                              style=btn_style("btn_emoji_toggle", "success"),
                              icon_custom_emoji_id=btn_eid("star")))
    kb.row(
        types.KeyboardButton(text=get_label("btn_emoji_control", "🎛 EMOJI CONTROL"),
                              style=btn_style("btn_emoji_control", "primary"),
                              icon_custom_emoji_id=btn_eid("crown")),
        types.KeyboardButton(text=get_label("btn_set_admin", "👑 SET ADMIN"),
                              style=btn_style("btn_set_admin", "primary"),
                              icon_custom_emoji_id=btn_eid("crown")))
    kb.row(
        types.KeyboardButton(text=get_label("btn_search_user", "🔍 SEARCH USER"),
                              style=btn_style("btn_search_user", "primary"),
                              icon_custom_emoji_id=btn_eid("user")),
        types.KeyboardButton(text=get_label("btn_system", "⚙️ SYSTEM"),
                              style=btn_style("btn_system", "primary"),
                              icon_custom_emoji_id=btn_eid("gear")))
    kb.row(
        types.KeyboardButton(text=get_label("btn_otp_group", "📢 OTP GROUP"),
                              style=btn_style("btn_otp_group", "success"),
                              icon_custom_emoji_id=btn_eid("user")))
    kb.row(
        types.KeyboardButton(text=get_label("btn_chatter_baal", "💬 CHATTER BAAL"),
                              style=btn_style("btn_chatter_baal", "primary"),
                              icon_custom_emoji_id=btn_eid("star")))
    kb.row(
        types.KeyboardButton(text=get_label("btn_back_to_bot", "🔙 BACK TO BOT"),
                              style=btn_style("btn_back_to_bot", "danger"),
                              icon_custom_emoji_id=btn_eid("no")))
    return kb

@bot.message_handler(func=lambda m: m.text in [
    get_label("btn_admin_panel", "👑 ADMIN PANEL"),
    "ADMIN PANEL", "👑 ADMIN PANEL"
] and is_admin(m.chat.id))
def menu_admin_panel(msg):
    cmd_admin(msg)

@bot.message_handler(func=lambda m: m.text in [
    get_label("btn_chatter_baal", "💬 CHATTER BAAL"),
    "CHATTER BAAL", "💬 CHATTER BAAL"
] and is_admin(m.chat.id))
def menu_chatter_baal(msg):
    msg2 = bot.send_message(msg.chat.id,
        pem("💬 <b>SET MAIN CHANNEL</b>\n\n"
            "আপনার MAIN CHANNEL এর link পাঠান:\n\n"
            "উদাহরণ: <code>https://t.me/yourchannel</code>\n\n"
            "⚠️ এটাও সেট করতে পারবেন:\n"
            "NUMBER BOT username: <code>@YourBot</code>\n\n"
            "Format: <code>channel_link | @bot_username</code>"),
        parse_mode="HTML")
    bot.register_next_step_handler(msg2, save_main_channel)


def save_main_channel(msg):
    if not is_admin(msg.chat.id): return
    link = msg.text.strip() if msg.text else ""
    if is_main_menu_button(link):
        cancel_flow_and_redirect(msg)
        return
    if not link.startswith("http"):
        bot.send_message(msg.chat.id, "❌ সঠিক link দিন (https://...)")
        return
    settings["main_channel_link"] = link
    save_settings()
    bot.send_message(msg.chat.id,
        pem("💬 <b>HELLO চাটের বাল  কি খবর</b> 😎\n\n"
            f"✅ Main Channel link সেভ হয়েছে:\n"
            f"<code>{link}</code>"),
        parse_mode="HTML")


@bot.message_handler(func=lambda m: m.text in [
    get_label("btn_otp_group", "📢 OTP GROUP"),
    "OTP GROUP", "📢 OTP GROUP"
] and is_admin(m.chat.id))
def menu_otp_group_admin(msg):
    msg2 = bot.send_message(msg.chat.id,
        pem("📢 <b>SET OTP GROUP LINK</b>\n\n"
            "আপনার OTP Group এর link পাঠান:\n\n"
            "উদাহরণ: <code>https://t.me/yourgroup</code>"),
        parse_mode="HTML")
    bot.register_next_step_handler(msg2, save_otp_group_link)

def save_otp_group_link(msg):
    if not is_admin(msg.chat.id): return
    link = msg.text.strip()
    
    # Main menu বাটন চেক
    if is_main_menu_button(link):
        cancel_flow_and_redirect(msg)
        return
    
    if not link.startswith("http"):
        # username হলে যোগ করা
        if link.startswith("@"):
            link = "https://t.me/" + link.replace("@", "")
        else:
            bot.send_message(msg.chat.id, "❌ সঠিক link দিন (https://...)")
            return
    
    # t.me/username → https://t.me/username
    if not link.startswith("https://t.me/"):
        link = "https://t.me/" + link.replace("https://", "").replace("http://", "")
    
    settings["otp_group_link"] = link
    save_settings()
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton(
        text="📢 OPEN OTP GROUP",
        url=link,
        style="success",
        icon_custom_emoji_id=btn_eid("ok")))
    bot.send_message(msg.chat.id,
        pem(f"✅ <b>OTP GROUP LINK SAVED!</b>\n\n<code>{link}</code>"),
        parse_mode="HTML", reply_markup=kb)
@bot.message_handler(commands=['admin'])
def cmd_admin(msg):
    check_owner_premium(msg)
    if not is_admin(msg.chat.id):
        bot.reply_to(msg, "❌ Access Denied!")
        return
    today_count = len(db_today_otps())
    text = pem(
        f"╔══════════════════╗\n   👑 <b>ADMIN PANEL</b>\n╚══════════════════╝\n\n"
        f"🎨 <b>Emoji:</b> <code>{emoji_status_str()}</code>\n"
        f"⚡ <b>Speed:</b> <code>{settings['speed_mode']}</code>\n"
        f"🔧 <b>Services:</b> <code>{'ALL' if not settings['allowed_services'] else ', '.join(s.upper() for s in settings['allowed_services'])}</code>\n"
        f"📊 <b>Today OTP:</b> <code>{today_count}</code>\n"
        f"🔑 <b>Zenex:</b> <code>{len(settings['zenex_keys'])}</code> | "
        f"<b>Stex:</b> <code>{len(settings['stex_keys'])}</code> | "
        f"<b>Voltx:</b> <code>{len(settings['voltx_keys'])}</code>\n"
        f"🎨 <b>Colors:</b> <code>{len(BUTTON_COLORS)}</code> | "
        f"<b>Emojis:</b> <code>{len(CUSTOM_EMOJI)}</code>\n"
        f"👑 <b>Admins:</b> <code>{len(EXTRA_ADMINS) + 1}</code>\n"
        f"💸 <b>Withdraw:</b> <code>{'ON' if settings['withdraw_on'] else 'OFF'}</code>\n"
        f"📢 <b>Must Join:</b> <code>{'ON' if settings['must_join_enabled'] else 'OFF'}</code>\n"
        f"👥 <b>Refer:</b> <code>{'ON' if settings['refer_enabled'] else 'OFF'}</code>\n"
        f"🏆 <b>Top Reward:</b> <code>{'ON' if settings['top_reward_enabled'] else 'OFF'}</code>")
    bot.send_message(msg.chat.id, text, parse_mode="HTML", reply_markup=admin_menu())

# ================== SET SPEED ==================
@bot.message_handler(func=lambda m: m.text in [
    "⚡ SET SPEED", get_label("btn_set_speed", "⚡ SET SPEED")
] and is_admin(m.chat.id))
def admin_speed(msg):
    kb = types.InlineKeyboardMarkup(row_width=1)
    for mode, sec in SPEED_MODES.items():
        label = f"{'✅ ' if mode == settings['speed_mode'] else ''}{mode} ({sec}s)"
        kb.add(types.InlineKeyboardButton(text=label,
                                          callback_data=f"set_speed:{mode}",
                                          style="primary"))
    kb.row(types.InlineKeyboardButton(
        text=get_label("btn_back", "🔙 BACK"),
        callback_data="admin_back",
        style="danger", icon_custom_emoji_id=btn_eid("no")))
    bot.send_message(msg.chat.id, pem(f"⚡ <b>SELECT OTP CHECK SPEED:</b>"),
                     parse_mode="HTML", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("set_speed:"))
def cb_set_speed(call):
    if not is_admin(call.message.chat.id): return
    mode = call.data.split(":", 1)[1]
    settings["speed_mode"] = mode
    save_settings()
    bot.answer_callback_query(call.id, f"✅ Speed: {mode}")

# ================== FILTER SERVICE ==================
@bot.message_handler(func=lambda m: m.text in [
    "🔧 FILTER SERVICE", get_label("btn_filter", "🔧 FILTER SERVICE")
] and is_admin(m.chat.id))
def admin_filter(msg):
    ranges = zenex_get_ranges()
    all_svcs = sorted(set(x["service"].lower() for x in ranges))
    kb = types.InlineKeyboardMarkup(row_width=2)
    for svc in all_svcs[:20]:
        is_on = not settings["allowed_services"] or svc in settings["allowed_services"]
        kb.add(types.InlineKeyboardButton(
            text=f"{'✅' if is_on else '❌'} {svc.upper()}",
            callback_data=f"filter:{svc}",
            style="success" if is_on else "danger"))
    kb.row(types.InlineKeyboardButton(
        text="🔄 ALL ON", callback_data="filter_reset",
        style="success", icon_custom_emoji_id=btn_eid("ok")),
        types.InlineKeyboardButton(
        text=get_label("btn_back", "🔙 BACK"),
        callback_data="admin_back",
        style="danger", icon_custom_emoji_id=btn_eid("no")))
    bot.send_message(msg.chat.id,
        pem(f"🔧 <b>SERVICE FILTER:</b>\n✅ = ON | ❌ = OFF"),
        parse_mode="HTML", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("filter:"))
def cb_filter(call):
    if not is_admin(call.message.chat.id): return
    svc = call.data.split(":", 1)[1]
    if not settings["allowed_services"]:
        ranges = zenex_get_ranges()
        all_svcs = set(x["service"].lower() for x in ranges)
        settings["allowed_services"] = list(all_svcs - {svc})
    else:
        if svc in settings["allowed_services"]:
            settings["allowed_services"].remove(svc)
        else:
            settings["allowed_services"].append(svc)
    save_settings()
    bot.answer_callback_query(call.id, f"✅ {svc.upper()}")

@bot.callback_query_handler(func=lambda c: c.data == "filter_reset")
def cb_filter_reset(call):
    if not is_admin(call.message.chat.id): return
    settings["allowed_services"] = []
    save_settings()
    bot.answer_callback_query(call.id, "✅ All ON!")

# ================== TODAY OTP ==================
@bot.message_handler(func=lambda m: m.text in [
    "📊 TODAY OTP", get_label("btn_today_otp", "📊 TODAY OTP")
] and is_admin(m.chat.id))
def admin_today(msg):
    today_list = db_today_otps()
    if not today_list:
        bot.send_message(msg.chat.id, "📊 No OTP today.")
        return
    lines = [pem(f"📊 <b>TODAY OTP — {datetime.now().strftime('%Y-%m-%d')}</b>\n<b>Total: {len(today_list)}</b>\n")]
    for i, o in enumerate(today_list[-20:], 1):
        lines.append(
            f"<code>{i}.</code> 📱<code>{o.get('number','?')}</code>\n"
            f"   🌐<code>{o.get('service','?').upper()}</code> | "
            f"🔑<code>{o.get('otp','?')}</code> | "
            f"⚙️<code>{o.get('panel','?').upper()}</code>\n"
            f"   🕐<code>{o.get('time','?')}</code>\n")
    bot.send_message(msg.chat.id, "\n".join(lines), parse_mode="HTML")

# ================== ALL USERS ==================
@bot.message_handler(func=lambda m: m.text in [
    "👥 ALL USERS", get_label("btn_all_users", "👥 ALL USERS")
] and is_admin(m.chat.id))
def admin_users(msg):
    data = fb_get("users")
    if not data:
        bot.send_message(msg.chat.id, "❌ No users.")
        return
    total = len(data)
    t_otp = sum(int(u.get("total_otp", 0)) for u in data.values())
    t_bal = sum(float(u.get("balance", 0)) for u in data.values())
    t_ref = sum(float(u.get("refer_balance", 0)) for u in data.values())
    banned = sum(1 for u in data.values() if u.get("banned"))
    text = pem(
        f"👥 <b>ALL USERS</b>\n\n"
        f"👤 <b>Users:</b> <code>{total}</code>\n"
        f"🔴 <b>Banned:</b> <code>{banned}</code>\n"
        f"📊 <b>OTP:</b> <code>{t_otp}</code>\n"
        f"💰 <b>Balance:</b> <code>৳{round(t_bal, 2)}</code>\n"
        f"💵 <b>Refer Balance:</b> <code>৳{round(t_ref, 2)}</code>")
    bot.send_message(msg.chat.id, text, parse_mode="HTML")

# ================== MANAGE KEYS ==================
def keys_main_kb():
    kb = types.InlineKeyboardMarkup(row_width=1)
    for panel in ["zenex", "stex", "voltx", "slvirtual"]:
        emoji = {"zenex": "⚡", "stex": "🔵", "voltx": "🟣", "slvirtual": "🌐"}[panel]
        count = len(settings.get(f"{panel}_keys", []))
        kb.add(types.InlineKeyboardButton(
            text=f"{emoji} {panel.upper()} ({count} keys)",
            callback_data=f"keys_panel:{panel}",
            style="primary", icon_custom_emoji_id=btn_eid("key")))
    kb.row(types.InlineKeyboardButton(
        text=get_label("btn_back", "🔙 BACK"),
        callback_data="admin_back",
        style="danger", icon_custom_emoji_id=btn_eid("no")))
    return kb

def keys_panel_kb(panel):
    kb = types.InlineKeyboardMarkup(row_width=1)
    for i, key in enumerate(settings[f"{panel}_keys"]):
        short = key[:8] + "..." + key[-4:] if len(key) > 14 else key
        kb.add(types.InlineKeyboardButton(
            text=f"🔑 {short}",
            callback_data=f"key_view:{panel}:{i}",
            style="success", icon_custom_emoji_id=btn_eid("key")))
    kb.add(types.InlineKeyboardButton(
        text="➕ ADD NEW KEY",
        callback_data=f"addkey:{panel}",
        style="primary", icon_custom_emoji_id=btn_eid("ok")))
    kb.row(types.InlineKeyboardButton(
        text=get_label("btn_back", "🔙 BACK"),
        callback_data="keys_main",
        style="danger", icon_custom_emoji_id=btn_eid("no")))
    return kb

def key_view_kb(panel, idx):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton(text="🗑 DELETE",
            callback_data=f"key_del_confirm:{panel}:{idx}",
            style="danger", icon_custom_emoji_id=btn_eid("no")),
        types.InlineKeyboardButton(text=get_label("btn_back", "🔙 BACK"),
            callback_data=f"keys_panel:{panel}",
            style="primary", icon_custom_emoji_id=btn_eid("no")))
    return kb

@bot.message_handler(func=lambda m: m.text in [
    "🔑 MANAGE KEYS", get_label("btn_manage_keys", "🔑 MANAGE KEYS")
] and is_admin(m.chat.id))
def admin_keys(msg):
    text = pem(
        f"╔══════════════════╗\n   🔑 <b>MANAGE KEYS</b>\n╚══════════════════╝\n\n"
        f"⚡ Zenex: <code>{len(settings['zenex_keys'])}</code> keys\n"
        f"🔵 Stex: <code>{len(settings['stex_keys'])}</code> keys\n"
        f"🟣 Voltx: <code>{len(settings['voltx_keys'])}</code> keys\n"
        f"🌐 SL Virtual: <code>{len(settings['slvirtual_keys'])}</code> keys\n\n"
        f"👆 Panel select করো:")
    bot.send_message(msg.chat.id, text, parse_mode="HTML",
                     reply_markup=keys_main_kb())

@bot.callback_query_handler(func=lambda c: c.data == "keys_main")
def cb_keys_main(call):
    if not is_admin(call.message.chat.id): return
    text = pem(
        f"🔑 <b>MANAGE KEYS</b>\n\n"
        f"⚡ Zenex: <code>{len(settings['zenex_keys'])}</code>\n"
        f"🔵 Stex: <code>{len(settings['stex_keys'])}</code>\n"
        f"🟣 Voltx: <code>{len(settings['voltx_keys'])}</code>\n"
        f"🌐 SL Virtual: <code>{len(settings['slvirtual_keys'])}</code>")
    try:
        bot.edit_message_text(text, chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML", reply_markup=keys_main_kb())
    except:
        bot.send_message(call.message.chat.id, text,
            parse_mode="HTML", reply_markup=keys_main_kb())

@bot.callback_query_handler(func=lambda c: c.data.startswith("keys_panel:"))
def cb_keys_panel(call):
    if not is_admin(call.message.chat.id): return
    panel = call.data.split(":", 1)[1]
    keys = settings[f"{panel}_keys"]
    text = pem(
        f"🔑 <b>{panel.upper()} KEYS</b>\n\n"
        f"Total: <code>{len(keys)}</code> keys\n\n"
        f"👆 Key ট্যাপ করলে details দেখবে:")
    try:
        bot.edit_message_text(text, chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML", reply_markup=keys_panel_kb(panel))
    except:
        bot.send_message(call.message.chat.id, text,
            parse_mode="HTML", reply_markup=keys_panel_kb(panel))

@bot.callback_query_handler(func=lambda c: c.data.startswith("key_view:"))
def cb_key_view(call):
    if not is_admin(call.message.chat.id): return
    _, panel, idx = call.data.split(":")
    idx = int(idx)
    keys = settings[f"{panel}_keys"]
    if idx >= len(keys):
        bot.answer_callback_query(call.id, "❌ Not found!")
        return
    key = keys[idx]
    text = pem(
        f"🔑 <b>KEY DETAILS</b>\n\n"
        f"Panel: <code>{panel.upper()}</code>\n"
        f"Key: <code>{key}</code>\n\n"
        f"⚠️ Delete করতে 🗑 চাপো:")
    try:
        bot.edit_message_text(text, chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML", reply_markup=key_view_kb(panel, idx))
    except:
        bot.send_message(call.message.chat.id, text,
            parse_mode="HTML", reply_markup=key_view_kb(panel, idx))

@bot.callback_query_handler(func=lambda c: c.data.startswith("key_del_confirm:"))
def cb_key_del_confirm(call):
    if not is_admin(call.message.chat.id): return
    _, panel, idx = call.data.split(":")
    idx = int(idx)
    keys = settings[f"{panel}_keys"]
    if idx >= len(keys):
        bot.answer_callback_query(call.id, "❌ Not found!")
        return
    key = keys[idx]
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton(text="✅ CONFIRM DELETE",
            callback_data=f"key_del:{panel}:{idx}",
            style="danger", icon_custom_emoji_id=btn_eid("no")),
        types.InlineKeyboardButton(text="❌ CANCEL",
            callback_data=f"keys_panel:{panel}",
            style="success", icon_custom_emoji_id=btn_eid("ok")))
    text = pem(
        f"⚠️ <b>CONFIRM DELETE?</b>\n\n"
        f"Panel: <code>{panel.upper()}</code>\n"
        f"Key: <code>{key}</code>\n\n"
        f"এই key permanently delete হবে!")
    try:
        bot.edit_message_text(text, chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML", reply_markup=kb)
    except:
        bot.send_message(call.message.chat.id, text,
            parse_mode="HTML", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("key_del:"))
def cb_key_del(call):
    if not is_admin(call.message.chat.id): return
    _, panel, idx = call.data.split(":")
    idx = int(idx)
    keys = settings[f"{panel}_keys"]
    if idx < len(keys):
        removed = keys.pop(idx)
        save_settings()
        bot.answer_callback_query(call.id, "✅ Deleted!")
        print(f"[KEYS] Deleted {panel}: {removed}")
    text = pem(
        f"✅ <b>Key Deleted!</b>\n\n"
        f"🔑 {panel.upper()}: <code>{len(settings[f'{panel}_keys'])}</code> remaining")
    try:
        bot.edit_message_text(text, chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML", reply_markup=keys_panel_kb(panel))
    except:
        bot.send_message(call.message.chat.id, text,
            parse_mode="HTML", reply_markup=keys_panel_kb(panel))

@bot.callback_query_handler(func=lambda c: c.data.startswith("addkey:"))
def cb_addkey(call):
    if not is_admin(call.message.chat.id): return
    panel = call.data.split(":", 1)[1]
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id,
        pem(f"📝 <b>{panel.upper()} NEW KEY</b>\n\nAPI Key পাঠাও:"),
        parse_mode="HTML")
    bot.register_next_step_handler(msg, lambda m: save_api_key(m, panel))

def save_api_key(msg, panel):
    if not is_admin(msg.chat.id): return
    try:
        raw_text = msg.text.strip()
        key = raw_text.split()[0] 
        temp_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        TEMP_ADDKEY[temp_id] = {"panel": panel, "key": key}
        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.add(
            types.InlineKeyboardButton(text="✅ CONFIRM ADD",
                callback_data=f"key_add_ok:{temp_id}",
                style="success", icon_custom_emoji_id=btn_eid("ok")),
            types.InlineKeyboardButton(text="❌ CANCEL",
                callback_data=f"keys_panel:{panel}",
                style="danger", icon_custom_emoji_id=btn_eid("no")))
        text = pem(
            f"⚠️ <b>CONFIRM ADD?</b>\n\n"
            f"Panel: <code>{panel.upper()}</code>\n"
            f"Key: <code>{html.escape(key)}</code>\n\n"
            f"নিশ্চিত হলে CONFIRM চাপো:")
        bot.send_message(msg.chat.id, text, parse_mode="HTML", reply_markup=kb)
    except Exception as e:
        bot.send_message(msg.chat.id, f"❌ Error: {e}")

@bot.callback_query_handler(func=lambda c: c.data.startswith("key_add_ok:"))
def cb_key_add_ok(call):
    if not is_admin(call.message.chat.id): return
    try:
        temp_id = call.data.split(":", 1)[1]
        data = TEMP_ADDKEY.pop(temp_id, None)
        if not data:
            bot.answer_callback_query(call.id, "❌ Session expired! আবার চেষ্টা করুন।", show_alert=True)
            return
        panel = data["panel"]
        key = data["key"]
        added = False
        if panel == "zenex" and key not in settings["zenex_keys"]:
            settings["zenex_keys"].append(key)
            added = True
        elif panel == "stex" and key not in settings["stex_keys"]:
            settings["stex_keys"].append(key)
            added = True
        elif panel == "voltx" and key not in settings["voltx_keys"]:
            settings["voltx_keys"].append(key)
            added = True
        elif panel == "slvirtual" and key not in settings["slvirtual_keys"]:
            settings["slvirtual_keys"].append(key)
            added = True
        if added: 
            save_settings()
        bot.answer_callback_query(call.id, "✅ Added!" if added else "⚠️ Already exists!")
        text = pem(
            f"{'✅' if added else '⚠️'} <b>{'Key Added!' if added else 'Already exists!'}</b>\n\n"
            f"🔑 {panel.upper()}: <code>{len(settings[f'{panel}_keys'])}</code> total")
        try:
            bot.edit_message_text(text, chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="HTML", reply_markup=keys_panel_kb(panel))
        except:
            bot.send_message(call.message.chat.id, text,
                parse_mode="HTML", reply_markup=keys_panel_kb(panel))
    except Exception as e:
        bot.send_message(call.message.chat.id, f"❌ Error: {e}")

# ================== EMOJI ON/OFF ==================
@bot.message_handler(func=lambda m: m.text in [
    "🎭 EMOJI ON/OFF", get_label("btn_emoji_toggle", "🎭 EMOJI ON/OFF")
] and is_admin(m.chat.id))
def admin_emoji_toggle(msg):
    check_owner_premium(msg)
    show_emoji_toggle(msg.chat.id)

def show_emoji_toggle(chat_id, message_id=None):
    p_status = "🟢 ON" if EMOJI_ON else "🔴 OFF"
    f_status = "🟢 ON" if FREE_EMOJI_ON else "🔴 OFF"
    text = pem(
        f"╔══════════════════╗\n   🎭 <b>EMOJI SETTINGS</b>\n╚══════════════════╝\n\n"
        f"💎 <b>Premium Emoji:</b> <code>{p_status}</code>\n"
        f"🆓 <b>Free Emoji:</b> <code>{f_status}</code>\n\n"
        f"⚙️ আলাদা আলাদা টগল করতে পারো:")
    kb = types.InlineKeyboardMarkup(row_width=2)
    if EMOJI_ON:
        kb.add(types.InlineKeyboardButton(text="💎 Premium OFF",
            callback_data="emoji_set:premium:off", style="danger"))
    else:
        kb.add(types.InlineKeyboardButton(text="💎 Premium ON",
            callback_data="emoji_set:premium:on", style="success"))
    if FREE_EMOJI_ON:
        kb.add(types.InlineKeyboardButton(text="🆓 Free OFF",
            callback_data="emoji_set:free:off", style="danger"))
    else:
        kb.add(types.InlineKeyboardButton(text="🆓 Free ON",
            callback_data="emoji_set:free:on", style="success"))
    kb.row(types.InlineKeyboardButton(
        text=get_label("btn_back", "🔙 BACK"),
        callback_data="admin_back",
        style="danger", icon_custom_emoji_id=btn_eid("no")))
    if message_id:
        try:
            bot.edit_message_text(text, chat_id=chat_id, message_id=message_id,
                                  parse_mode="HTML", reply_markup=kb)
            return
        except: pass
    bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("emoji_set:"))
def cb_emoji_set(call):
    global EMOJI_ON, FREE_EMOJI_ON
    if not is_admin(call.message.chat.id): return
    parts = call.data.split(":")
    kind, action = parts[1], parts[2]
    if kind == "premium":
        EMOJI_ON = (action == "on")
        bot.answer_callback_query(call.id, f"💎 Premium {'ON' if EMOJI_ON else 'OFF'}!")
    else:
        FREE_EMOJI_ON = (action == "on")
        bot.answer_callback_query(call.id, f"🆓 Free {'ON' if FREE_EMOJI_ON else 'OFF'}!")
    save_emoji_state()
    check_bot_premium()
    show_emoji_toggle(call.message.chat.id, call.message.message_id)

# ================== ADMIN BACK ==================
@bot.callback_query_handler(func=lambda c: c.data == "admin_back")
def cb_admin_back(call):
    if not is_admin(call.message.chat.id): return
    try:
        bot.edit_message_text("👑 Admin Panel",
                              chat_id=call.message.chat.id,
                              message_id=call.message.message_id)
    except: pass

@bot.message_handler(func=lambda m: m.text in [
    "🔙 BACK TO BOT", get_label("btn_back_to_bot", "🔙 BACK TO BOT")
] and is_admin(m.chat.id))
def admin_back(msg):
    bot.send_message(msg.chat.id, "🏠 Main Menu!", reply_markup=main_menu(msg.chat.id))

# ==========================================================
#              🔍 SEARCH USER
# ==========================================================
@bot.message_handler(func=lambda m: m.text in [
    get_label("btn_search_user", "🔍 SEARCH USER"),
    "SEARCH USER", "🔍 SEARCH USER"
] and is_admin(m.chat.id))
def admin_search_user(msg):
    msg2 = bot.send_message(msg.chat.id,
        pem("🔍 <b>SEARCH USER</b>\n\nUser ID বা Username পাঠান:"),
        parse_mode="HTML")
    bot.register_next_step_handler(msg2, search_user_process)

def search_user_process(msg):
    if not is_admin(msg.chat.id): return
    query = msg.text.strip().replace("@", "")
    if not query:
        bot.send_message(msg.chat.id, "❌ খালি পাঠাবেন না!")
        return
    if query.isdigit():
        user = fb_get(f"users/{query}")
        if not user:
            bot.send_message(msg.chat.id, "❌ User not found!")
            return
        show_user_admin_panel(msg.chat.id, query, user)
    else:
        all_users = fb_get("users") or {}
        found = None
        for uid, u in all_users.items():
            if (u.get("username") or "").lower() == query.lower():
                found = (uid, u)
                break
        if found:
            show_user_admin_panel(msg.chat.id, found[0], found[1])
        else:
            bot.send_message(msg.chat.id, "❌ User not found!")

def show_user_admin_panel(admin_chat, uid, user):
    banned = user.get("banned", False)
    text = pem(
        f"👤 <b>USER DETAILS</b>\n\n"
        f"🆔 <b>ID:</b> <code>{uid}</code>\n"
        f"👤 <b>Name:</b> <code>{user.get('first_name','User')}</code>\n"
        f"🔗 <b>Username:</b> <code>@{user.get('username','')}</code>\n"
        f"📅 <b>Joined:</b> <code>{user.get('joined','N/A')}</code>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💰 <b>Balance:</b> <code>৳{user.get('balance',0)}</code>\n"
        f"💵 <b>Refer Balance:</b> <code>৳{user.get('refer_balance',0)}</code>\n"
        f"📊 <b>Total OTP:</b> <code>{user.get('total_otp',0)}</code>\n"
        f"📈 <b>Today OTP:</b> <code>{user.get('today_otp',0)}</code>\n"
        f"👥 <b>Referrals:</b> <code>{user.get('total_refer',0)}</code>\n"
        f"📊 <b>Status:</b> <code>{'🔴 BANNED' if banned else '🟢 ACTIVE'}</code>")
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(types.InlineKeyboardButton(text="💰 ADD BALANCE",
        callback_data=f"uadmin:addbal:{uid}", style="success"))
    kb.add(types.InlineKeyboardButton(text="💸 CUT BALANCE",
        callback_data=f"uadmin:cutbal:{uid}", style="danger"))
    kb.add(types.InlineKeyboardButton(text="📊 RESET OTP",
        callback_data=f"uadmin:resetotp:{uid}", style="primary"))
    if banned:
        kb.add(types.InlineKeyboardButton(text="🟢 UNBAN",
            callback_data=f"uadmin:unban:{uid}", style="success"))
    else:
        kb.add(types.InlineKeyboardButton(text="🔴 BAN",
            callback_data=f"uadmin:ban:{uid}", style="danger"))
    kb.add(types.InlineKeyboardButton(text="📩 SEND MESSAGE",
        callback_data=f"uadmin:msg:{uid}", style="primary"))
    bot.send_message(admin_chat, text, parse_mode="HTML", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("uadmin:"))
def cb_uadmin(call):
    if not is_admin(call.message.chat.id): return
    parts = call.data.split(":")
    action, uid = parts[1], parts[2]
    if action == "ban":
        fb_update(f"users/{uid}", {"banned": True})
        bot.answer_callback_query(call.id, "🔴 Banned!")
    elif action == "unban":
        fb_update(f"users/{uid}", {"banned": False})
        bot.answer_callback_query(call.id, "🟢 Unbanned!")
    elif action == "resetotp":
        fb_update(f"users/{uid}", {"total_otp": 0, "today_otp": 0})
        bot.answer_callback_query(call.id, "📊 Reset!")
    elif action == "addbal":
        bot.answer_callback_query(call.id)
        msg = bot.send_message(call.message.chat.id,
            pem(f"💰 কত টাকা ADD করবেন? (User: <code>{uid}</code>)"),
            parse_mode="HTML")
        bot.register_next_step_handler(msg, lambda m: uadmin_balance(m, uid, "add"))
        return
    elif action == "cutbal":
        bot.answer_callback_query(call.id)
        msg = bot.send_message(call.message.chat.id,
            pem(f"💸 কত টাকা CUT করবেন? (User: <code>{uid}</code>)"),
            parse_mode="HTML")
        bot.register_next_step_handler(msg, lambda m: uadmin_balance(m, uid, "cut"))
        return
    elif action == "msg":
        bot.answer_callback_query(call.id)
        msg = bot.send_message(call.message.chat.id,
            pem(f"📩 ইউজারকে কী message পাঠাবেন?"), parse_mode="HTML")
        bot.register_next_step_handler(msg, lambda m: uadmin_msg(m, uid))
        return
    user = fb_get(f"users/{uid}") or {}
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except: pass
    show_user_admin_panel(call.message.chat.id, uid, user)

def uadmin_balance(msg, uid, action):
    if not is_admin(msg.chat.id): return
    try:
        amount = float(msg.text.strip())
    except:
        bot.send_message(msg.chat.id, "❌ Invalid!")
        return
    user = fb_get(f"users/{uid}") or {}
    bal = float(user.get("balance", 0))
    if action == "add":
        new_bal = round(bal + amount, 2)
        fb_update(f"users/{uid}", {"balance": new_bal})
        bot.send_message(msg.chat.id, f"✅ ৳{amount} added! New: ৳{new_bal}")
        try:
            bot.send_message(int(uid),
                pem(f"🎁 <b>BALANCE ADDED</b>\n\n"
                    f"💰 ৳{amount} added!\n💸 New: ৳{new_bal}"),
                parse_mode="HTML")
        except: pass
    else:
        new_bal = max(0, round(bal - amount, 2))
        fb_update(f"users/{uid}", {"balance": new_bal})
        bot.send_message(msg.chat.id, f"✅ ৳{amount} cut! New: ৳{new_bal}")

def uadmin_msg(msg, uid):
    if not is_admin(msg.chat.id): return
    try:
        bot.send_message(int(uid),
            pem(f"📩 <b>ADMIN MESSAGE</b>\n\n{msg.text}"), parse_mode="HTML")
        bot.send_message(msg.chat.id, "✅ Message sent!")
    except:
        bot.send_message(msg.chat.id, "❌ Failed to send!")

print("[PART 3/5] ✅ Loaded Admin Panel + Search User + Keys")
# ==========================================================
#  ZENEX OTP BOT v18.0 PRO EDITION — PART 4/5
#  SYSTEM: Withdraw Settings + Broadcast + Leaderboard +
#  Refer + Must Join + Payment Channel
# ==========================================================

# ================== SYSTEM MENU ==================
def system_menu_kb():
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton(text="💸 WITHDRAW SETTING",
        callback_data="sys_withdraw", style="success",
        icon_custom_emoji_id=btn_eid("money")))
    kb.add(types.InlineKeyboardButton(text="📢 BROADCAST MESSAGE",
        callback_data="sys_broadcast", style="primary",
        icon_custom_emoji_id=btn_eid("user")))
    kb.add(types.InlineKeyboardButton(text="🏆 LEADERBOARD SETTINGS",
        callback_data="sys_leaderboard", style="success",
        icon_custom_emoji_id=btn_eid("star")))
    kb.add(types.InlineKeyboardButton(text="👥 REFER SETTINGS",
        callback_data="sys_refer", style="primary",
        icon_custom_emoji_id=btn_eid("user")))
    kb.add(types.InlineKeyboardButton(text="📢 MUST JOIN + PAYMENT",
        callback_data="sys_mustjoin", style="primary",
        icon_custom_emoji_id=btn_eid("fire")))
    kb.add(types.InlineKeyboardButton(text="🎁 OTP EDIT",
        callback_data="sys_otp_edit", style="success",
        icon_custom_emoji_id=btn_eid("star")))
    kb.row(types.InlineKeyboardButton(
        text=get_label("btn_back", "🔙 BACK"),
        callback_data="admin_back",
        style="danger", icon_custom_emoji_id=btn_eid("no")))
    return kb

@bot.message_handler(func=lambda m: m.text in [
    get_label("btn_system", "⚙️ SYSTEM"), "SYSTEM", "⚙️ SYSTEM"
] and is_admin(m.chat.id))
def admin_system(msg):
    text = pem(f"⚙️ <b>SYSTEM SETTINGS</b>\n\nঅপশন সিলেক্ট করুন:")
    bot.send_message(msg.chat.id, text, parse_mode="HTML",
                     reply_markup=system_menu_kb())

@bot.callback_query_handler(func=lambda c: c.data.startswith("sys_"))
def cb_system(call):
    if not is_admin(call.message.chat.id): return
    action = call.data
    if action == "sys_withdraw":
        show_withdraw_settings(call)
    elif action == "sys_broadcast":
        show_broadcast_menu(call)
    elif action == "sys_leaderboard":
        show_leaderboard_settings(call)
    elif action == "sys_refer":
        show_refer_settings(call)
    elif action == "sys_mustjoin":
        show_mustjoin_settings(call)
    elif action == "sys_otp_edit":
        show_otp_edit(call)



# ================== OTP REWARD EDIT ==================
def show_otp_edit(call):
    if not is_admin(call.message.chat.id): return
    current = settings.get("otp_reward", 0.30)
    text = pem(
        f"╔══════════════════╗\n   🎁 <b>OTP REWARD EDIT</b>\n╚══════════════════╝\n\n"
        f"💰 <b>বর্তমান reward:</b> <code>৳{current}</code>\n\n"
        f"⚙️ প্রতি OTP এর জন্য user কত টাকা পাবে সেটা পরিবর্তন করুন।\n\n"
        f"👇 নতুন amount দিতে ট্যাপ করুন:")
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton(
        text=f"✏️ CHANGE REWARD (বর্তমান ৳{current})",
        callback_data="otp_edit_set",
        style="success", icon_custom_emoji_id=btn_eid("ok")))
    kb.row(types.InlineKeyboardButton(
        text=get_label("btn_back", "🔙 BACK"),
        callback_data="sys_back",
        style="danger", icon_custom_emoji_id=btn_eid("no")))
    try:
        bot.edit_message_text(text, chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML", reply_markup=kb)
    except:
        bot.send_message(call.message.chat.id, text,
            parse_mode="HTML", reply_markup=kb)


@bot.callback_query_handler(func=lambda c: c.data == "otp_edit_set")
def cb_otp_edit_set(call):
    if not is_admin(call.message.chat.id): return
    current = settings.get("otp_reward", 0.30)
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id,
        pem(f"🎁 <b>NEW OTP REWARD</b>\n\n"
            f"বর্তমান: <code>৳{current}</code>\n\n"
            f"📝 নতুন amount পাঠান (শুধু number):\n"
            f"উদাহরণ: <code>0.50</code>"),
        parse_mode="HTML")
    bot.register_next_step_handler(msg, otp_edit_save)


def otp_edit_save(msg):
    if not is_admin(msg.chat.id): return
    text_input = msg.text.strip() if msg.text else ""
    
    # Main menu বাটন চেক
    if is_main_menu_button(text_input):
        cancel_flow_and_redirect(msg)
        return
    
    try:
        new_reward = float(text_input)
        if new_reward <= 0:
            bot.send_message(msg.chat.id, "❌ Amount 0 এর চেয়ে বড় হতে হবে!")
            return
    except:
        bot.send_message(msg.chat.id, "❌ সঠিক number দিন!")
        return
    settings["otp_reward"] = new_reward
    save_settings()
    bot.send_message(msg.chat.id,
        pem(f"✅ <b>OTP REWARD UPDATED!</b>\n\n"
            f"🎁 নতুন reward: <code>৳{new_reward}</code>\n\n"
            f"এখন থেকে প্রতিটা OTP তে user ৳{new_reward} পাবে।"),
        parse_mode="HTML")


@bot.callback_query_handler(func=lambda c: c.data == "sys_back")
def cb_sys_back(call):
    if not is_admin(call.message.chat.id): return
    try:
        bot.edit_message_text(
            pem("⚙️ <b>SYSTEM SETTINGS</b>\n\nঅপশন সিলেক্ট করুন:"),
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML", reply_markup=system_menu_kb())
    except: pass

# ==========================================================
#           💸 WITHDRAW SETTINGS
# ==========================================================
def show_withdraw_settings(call):
    wd_on = settings.get("withdraw_on", True)
    methods = settings.get("w_methods", {})
    text = pem(
        f"╔══════════════════╗\n   💸 <b>WITHDRAW SETTINGS</b>\n╚══════════════════╝\n\n"
        f"📊 <b>Status:</b> <code>{'🟢 ON' if wd_on else '🔴 OFF'}</code>\n"
        f"💰 <b>Min:</b> <code>৳{settings['min_withdraw']}</code>\n"
        f"💵 <b>Max:</b> <code>৳{settings['max_withdraw']}</code>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💳 <b>Methods:</b>\n"
        f"📱 bKash: {'🟢' if methods.get('bkash') else '🔴'}\n"
        f"📱 Nagad: {'🟢' if methods.get('nagad') else '🔴'}\n"
        f"🟡 Binance: {'🟢' if methods.get('binance') else '🔴'}\n"
        f"🚀 Rocket: {'🟢' if methods.get('rocket') else '🔴'}")
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton(text="⚙️ WITHDRAW ON/OFF",
        callback_data="wd_toggle", style="primary"))
    kb.add(types.InlineKeyboardButton(text="💳 PAYMENT METHODS",
        callback_data="wd_methods", style="primary"))
    kb.add(types.InlineKeyboardButton(text="💰 WD MIN/MAX",
        callback_data="wd_minmax", style="primary"))
    kb.add(types.InlineKeyboardButton(text="📊 WITHDRAW REQUESTS",
        callback_data="wd_requests", style="success"))
    kb.row(types.InlineKeyboardButton(
        text=get_label("btn_back", "🔙 BACK"),
        callback_data="sys_back",
        style="danger", icon_custom_emoji_id=btn_eid("no")))
    try:
        bot.edit_message_text(text, chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML", reply_markup=kb)
    except:
        bot.send_message(call.message.chat.id, text,
            parse_mode="HTML", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "wd_toggle")
def cb_wd_toggle(call):
    if not is_admin(call.message.chat.id): return
    settings["withdraw_on"] = not settings.get("withdraw_on", True)
    save_settings()
    bot.answer_callback_query(call.id,
        f"Withdraw: {'ON' if settings['withdraw_on'] else 'OFF'}")
    show_withdraw_settings(call)

@bot.callback_query_handler(func=lambda c: c.data == "wd_methods")
def cb_wd_methods(call):
    if not is_admin(call.message.chat.id): return
    methods = settings.get("w_methods", {})
    text = pem("💳 <b>PAYMENT METHODS</b>\n\nটগল করুন:")
    kb = types.InlineKeyboardMarkup(row_width=1)
    for m, label in [("bkash", "📱 bKash"), ("nagad", "📱 Nagad"),
                     ("binance", "🟡 Binance"), ("rocket", "🚀 Rocket")]:
        status = "🟢 ON" if methods.get(m) else "🔴 OFF"
        kb.add(types.InlineKeyboardButton(
            text=f"{label} — {status}",
            callback_data=f"wd_m:{m}",
            style="success" if methods.get(m) else "danger"))
    kb.row(types.InlineKeyboardButton(
        text=get_label("btn_back", "🔙 BACK"),
        callback_data="sys_withdraw",
        style="danger", icon_custom_emoji_id=btn_eid("no")))
    try:
        bot.edit_message_text(text, chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML", reply_markup=kb)
    except: pass

@bot.callback_query_handler(func=lambda c: c.data.startswith("wd_m:"))
def cb_wd_m(call):
    if not is_admin(call.message.chat.id): return
    method = call.data.split(":")[1]
    if "w_methods" not in settings:
        settings["w_methods"] = {}
    settings["w_methods"][method] = not settings["w_methods"].get(method, True)
    save_settings()
    bot.answer_callback_query(call.id,
        f"{method}: {'ON' if settings['w_methods'][method] else 'OFF'}")
    cb_wd_methods(call)

@bot.callback_query_handler(func=lambda c: c.data == "wd_minmax")
def cb_wd_minmax(call):
    if not is_admin(call.message.chat.id): return
    show_wallet_limits(call.message.chat.id, call.message.message_id)


def show_wallet_limits(chat_id, message_id=None):
    limits = settings.get("w_limits", {})
    methods = settings.get("w_methods", {})
    lines = [pem("╔══════════════════╗\n   💰 <b>WITHDRAW MIN/MAX</b>\n╚══════════════════╝\n")]
    kb = types.InlineKeyboardMarkup(row_width=1)
    wallets = [
        ("bkash", "📱 bKash"),
        ("nagad", "📱 Nagad"),
        ("rocket", "🚀 Rocket"),
        ("binance", "🟡 Binance (BEP20)"),
    ]
    for key, label in wallets:
        lim = limits.get(key, {"min": 50.0, "max": 1000.0})
        status = "🟢" if methods.get(key) else "🔴"
        lines.append(
            f"{status} <b>{label}</b>\n"
            f"   💰 Min: <code>৳{lim.get('min', 0)}</code> | "
            f"Max: <code>৳{lim.get('max', 0)}</code>\n"
        )
        kb.add(types.InlineKeyboardButton(
            text=f"⚙️ {label} — Min ৳{lim.get('min', 0)} | Max ৳{lim.get('max', 0)}",
            callback_data=f"wl_set:{key}",
            style="primary" if methods.get(key) else "danger"))
    kb.row(types.InlineKeyboardButton(
        text=get_label("btn_back", "🔙 BACK"),
        callback_data="sys_withdraw",
        style="danger", icon_custom_emoji_id=btn_eid("no")))
    if message_id:
        try:
            bot.edit_message_text("\n".join(lines), chat_id=chat_id,
                message_id=message_id, parse_mode="HTML", reply_markup=kb)
            return
        except: pass
    bot.send_message(chat_id, "\n".join(lines),
        parse_mode="HTML", reply_markup=kb)


@bot.callback_query_handler(func=lambda c: c.data.startswith("wl_set:"))
def cb_wl_set(call):
    if not is_admin(call.message.chat.id): return
    wallet = call.data.split(":")[1]
    lim = settings.get("w_limits", {}).get(wallet, {"min": 50.0, "max": 1000.0})
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id,
        pem(f"💰 <b>{wallet.upper()} MIN AMOUNT</b>\n\n"
            f"বর্তমান Min: <code>৳{lim.get('min', 0)}</code>\n\n"
            f"নতুন Minimum amount পাঠান:"),
        parse_mode="HTML")
    bot.register_next_step_handler(msg, wl_get_min, wallet)


def wl_get_min(msg, wallet):
    if not is_admin(msg.chat.id): return
    try:
        min_val = float(msg.text.strip())
    except:
        bot.send_message(msg.chat.id, "❌ সঠিক number দিন!")
        return
    msg2 = bot.send_message(msg.chat.id,
        pem(f"💵 <b>{wallet.upper()} MAX AMOUNT</b>\n\n"
            f"নতুন Maximum amount পাঠান:"),
        parse_mode="HTML")
    bot.register_next_step_handler(msg2, wl_get_max, wallet, min_val)


def wl_get_max(msg, wallet, min_val):
    if not is_admin(msg.chat.id): return
    try:
        max_val = float(msg.text.strip())
    except:
        bot.send_message(msg.chat.id, "❌ সঠিক number দিন!")
        return
    if "w_limits" not in settings:
        settings["w_limits"] = {}
    settings["w_limits"][wallet] = {"min": min_val, "max": max_val}
    save_settings()
    bot.send_message(msg.chat.id,
        pem(f"✅ <b>{wallet.upper()} UPDATED!</b>\n\n"
            f"💰 Min: <code>৳{min_val}</code>\n"
            f"💵 Max: <code>৳{max_val}</code>"),
        parse_mode="HTML")
    show_wallet_limits(msg.chat.id)

@bot.callback_query_handler(func=lambda c: c.data == "wd_requests")
def cb_wd_requests(call):
    if not is_admin(call.message.chat.id): return
    all_wd = fb_get("withdraws") or {}
    pending = [(k, v) for k, v in all_wd.items() if v.get("status") == "pending"]
    if not pending:
        bot.answer_callback_query(call.id, "No pending requests!", show_alert=True)
        return
    lines = [pem(f"📊 <b>PENDING WITHDRAWS</b> ({len(pending)})\n")]
    kb = types.InlineKeyboardMarkup(row_width=1)
    for wd_id, wd in pending[:10]:
        lines.append(f"🆔 <code>{wd_id}</code> | ৳{wd['amount']} | {wd['method']}")
        kb.add(types.InlineKeyboardButton(
            text=f"⚙️ {wd_id} — ৳{wd['amount']}",
            callback_data=f"wd_view:{wd_id}",
            style="primary"))
    kb.row(types.InlineKeyboardButton(
        text=get_label("btn_back", "🔙 BACK"),
        callback_data="sys_withdraw",
        style="danger", icon_custom_emoji_id=btn_eid("no")))
    try:
        bot.edit_message_text("\n".join(lines),
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML", reply_markup=kb)
    except: pass

@bot.callback_query_handler(func=lambda c: c.data.startswith("wd_view:"))
def cb_wd_view(call):
    if not is_admin(call.message.chat.id): return
    wd_id = call.data.split(":")[1]
    wd = fb_get(f"withdraws/{wd_id}")
    if not wd: return
    text = pem(
        f"💸 <b>WITHDRAW DETAILS</b>\n\n"
        f"🆔 <code>{wd_id}</code>\n"
        f"👤 <code>{wd['chat_id']}</code>\n"
        f"💳 <code>{wd['method'].upper()}</code>\n"
        f"📝 <code>{wd['account']}</code>\n"
        f"💰 <code>৳{wd['amount']}</code>\n"
        f"📅 <code>{wd['date']}</code>\n"
        f"📊 <code>{wd['status'].upper()}</code>")
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton(text="✅ APPROVE",
            callback_data=f"w_admin:approve:{wd_id}", style="success"),
        types.InlineKeyboardButton(text="❌ REJECT",
            callback_data=f"w_admin:reject:{wd_id}", style="danger"))
    kb.row(types.InlineKeyboardButton(
        text=get_label("btn_back", "🔙 BACK"),
        callback_data="wd_requests",
        style="danger", icon_custom_emoji_id=btn_eid("no")))
    try:
        bot.edit_message_text(text, chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML", reply_markup=kb)
    except: pass

@bot.callback_query_handler(func=lambda c: c.data.startswith("w_admin:"))
def cb_w_admin(call):
    if not is_admin(call.message.chat.id): return
    _, action, wd_id = call.data.split(":")
    wd = fb_get(f"withdraws/{wd_id}")
    if not wd:
        bot.answer_callback_query(call.id, "❌ Not found!")
        return
    if wd.get("status") != "pending":
        bot.answer_callback_query(call.id, "⚠️ Already processed!")
        return
    if action == "approve":
        fb_update(f"withdraws/{wd_id}", {
            "status": "approved",
            "approved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
        bot.answer_callback_query(call.id, "✅ Approved!")
        
        # Payment Channel এ notification পাঠানো
        pay_ch = settings.get("payment_channel_id", "")
        if pay_ch and settings.get("payment_channel_enabled", True):
            try:
                method = wd.get("method", "").upper()
                account = wd.get("account", "N/A")
                amount = wd.get("amount", 0)
                
                if wd.get("method") == "binance":
                    rate = settings.get("binance_rate", 128.0)
                    usdt = round(float(amount) / rate, 4)
                    pay_text = pem(
                        f"✅ <b>WITHDRAW APPROVED</b>\n\n"
                        f"🆔 <b>ID:</b> <code>{wd_id}</code>\n"
                        f"👤 <b>User:</b> <code>{wd['chat_id']}</code>\n"
                        f"💳 <b>Method:</b> <code>BINANCE</code>\n"
                        f"🆔 <b>UID:</b> <code>{account}</code>\n"
                        f"💰 <b>Amount:</b> <code>৳{amount}</code>\n"
                        f"💱 <b>Send USDT:</b> <code>{usdt} USDT</code>\n"
                        f"📊 <b>Rate:</b> <code>৳{rate} = 1 USDT</code>\n\n"
                        f"✅ <b>Admin Approved</b>")
                else:
                    pay_text = pem(
                        f"✅ <b>WITHDRAW APPROVED</b>\n\n"
                        f"🆔 <b>ID:</b> <code>{wd_id}</code>\n"
                        f"👤 <b>User:</b> <code>{wd['chat_id']}</code>\n"
                        f"💳 <b>Method:</b> <code>{method}</code>\n"
                        f"📝 <b>Account:</b> <code>{account}</code>\n"
                        f"💰 <b>Amount:</b> <code>৳{amount}</code>\n\n"
                        f"✅ <b>Admin Approved</b>")
                bot.send_message(pay_ch, pay_text, parse_mode="HTML")
                print(f"[WITHDRAW] ✅ Approved → Payment Channel")
            except Exception as e:
                print(f"[WITHDRAW] Channel send err: {e}")
        
        # Binance হলে USDT দেখানো
        if wd.get("method") == "binance":
            rate = settings.get("binance_rate", 128.0)
            usdt_amount = round(float(wd["amount"]) / rate, 4)
            try:
                bot.send_message(wd["chat_id"],
                    pem(f"✅ <b>WITHDRAW APPROVED</b>\n\n"
                        f"🆔 <b>ID:</b> <code>{wd_id}</code>\n"
                        f"💳 <b>Method:</b> <code>BINANCE</code>\n"
                        f"🆔 <b>UID:</b> <code>{wd.get('account', 'N/A')}</code>\n"
                        f"💰 <b>Amount:</b> <code>৳{wd['amount']}</code>\n"
                        f"💱 <b>You received:</b> <code>{usdt_amount} USDT</code>\n"
                        f"📊 <b>Rate:</b> <code>৳{rate} = 1 USDT</code>\n\n"
                        f"✅ আপনার Binance account এ <b>{usdt_amount} USDT</b> পাঠিয়ে দেওয়া হয়েছে!"),
                    parse_mode="HTML")
            except: pass
        else:
            try:
                bot.send_message(wd["chat_id"],
                    pem(f"✅ <b>WITHDRAW APPROVED</b>\n\n"
                        f"🆔 <b>ID:</b> <code>{wd_id}</code>\n"
                        f"💳 <b>Method:</b> <code>{wd['method'].upper()}</code>\n"
                        f"📝 <b>Account:</b> <code>{wd.get('account', 'N/A')}</code>\n"
                        f"💰 <b>Amount:</b> <code>৳{wd['amount']}</code>\n\n"
                        f"✅ টাকা পাঠিয়ে দেওয়া হয়েছে!"),
                    parse_mode="HTML")
            except: pass
    else:
        fb_update(f"withdraws/{wd_id}", {
            "status": "rejected",
            "rejected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
        user = db_get_user(wd["chat_id"])
        new_bal = round(float(user.get("balance", 0)) + wd["amount"], 2)
        fb_update(f"users/{wd['chat_id']}", {"balance": new_bal})
        bot.answer_callback_query(call.id, "❌ Rejected!")
        
        # Payment Channel এ notification
        pay_ch = settings.get("payment_channel_id", "")
        if pay_ch and settings.get("payment_channel_enabled", True):
            try:
                method = wd.get("method", "").upper()
                account = wd.get("account", "N/A")
                amount = wd.get("amount", 0)
                pay_text = pem(
                    f"❌ <b>WITHDRAW REJECTED</b>\n\n"
                    f"🆔 <b>ID:</b> <code>{wd_id}</code>\n"
                    f"👤 <b>User:</b> <code>{wd['chat_id']}</code>\n"
                    f"💳 <b>Method:</b> <code>{method}</code>\n"
                    f"📝 <b>Account:</b> <code>{account}</code>\n"
                    f"💰 <b>Amount:</b> <code>৳{amount}</code>\n\n"
                    f"💰 <b>Refunded to user</b>\n"
                    f"❌ <b>Admin Rejected</b>")
                bot.send_message(pay_ch, pay_text, parse_mode="HTML")
                print(f"[WITHDRAW] ✅ Rejected → Payment Channel")
            except Exception as e:
                print(f"[WITHDRAW] Channel send err: {e}")
        try:
            bot.send_message(wd["chat_id"],
                pem(f"❌ <b>WITHDRAW REJECTED</b>\n\n"
                    f"🆔 <code>{wd_id}</code>\n"
                    f"💰 <code>৳{wd['amount']}</code> refunded!"),
                parse_mode="HTML")
        except: pass
    try: bot.delete_message(call.message.chat.id, call.message.message_id)
    except: pass

# ==========================================================
#           📢 BROADCAST
# ==========================================================
def show_broadcast_menu(call):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton(text="👥 ALL USERS",
            callback_data="bc_all", style="primary"),
        types.InlineKeyboardButton(text="👤 SINGLE USER",
            callback_data="bc_single", style="success"))
    kb.row(types.InlineKeyboardButton(
        text=get_label("btn_back", "🔙 BACK"),
        callback_data="sys_back",
        style="danger", icon_custom_emoji_id=btn_eid("no")))
    try:
        bot.edit_message_text(pem("📢 <b>BROADCAST MESSAGE</b>\n\nকাকে পাঠাবেন?"),
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML", reply_markup=kb)
    except: pass

@bot.callback_query_handler(func=lambda c: c.data == "bc_all")
def cb_bc_all(call):
    if not is_admin(call.message.chat.id): return
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id,
        pem("📢 <b>ALL USERS BROADCAST</b>\n\nMessage পাঠান (HTML supported):"),
        parse_mode="HTML")
    bot.register_next_step_handler(msg, bc_send_all)

def bc_send_all(msg):
    if not is_admin(msg.chat.id): return
    all_users = fb_get("users") or {}
    success = 0
    fail = 0
    status_msg = bot.send_message(msg.chat.id,
        f"📤 Sending to {len(all_users)} users...")
    for uid in all_users.keys():
        try:
            bot.send_message(int(uid), msg.text, parse_mode="HTML")
            success += 1
        except:
            fail += 1
        time.sleep(0.05)
    bot.edit_message_text(
        f"✅ Done!\n\n✅ Success: {success}\n❌ Failed: {fail}",
        chat_id=msg.chat.id, message_id=status_msg.message_id)

@bot.callback_query_handler(func=lambda c: c.data == "bc_single")
def cb_bc_single(call):
    if not is_admin(call.message.chat.id): return
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id,
        pem("👤 <b>SINGLE USER</b>\n\nUser ID পাঠান:"), parse_mode="HTML")
    bot.register_next_step_handler(msg, bc_get_uid)

def bc_get_uid(msg):
    if not is_admin(msg.chat.id): return
    try:
        uid = int(msg.text.strip())
        msg2 = bot.send_message(msg.chat.id,
            pem(f"📝 Message পাঠান (for <code>{uid}</code>):"),
            parse_mode="HTML")
        bot.register_next_step_handler(msg2, lambda m: bc_send_single(m, uid))
    except:
        bot.send_message(msg.chat.id, "❌ Invalid ID!")

def bc_send_single(msg, uid):
    if not is_admin(msg.chat.id): return
    try:
        bot.send_message(uid, msg.text, parse_mode="HTML")
        bot.send_message(msg.chat.id, "✅ Sent!")
    except:
        bot.send_message(msg.chat.id, "❌ Failed!")

# ==========================================================
#           🏆 LEADERBOARD SETTINGS
# ==========================================================
def show_leaderboard_settings(call):
    prices = settings.get("top_reward_prices", {})
    price_str = " | ".join([f"{k}: ৳{v}" for k, v in prices.items()])
    text = pem(
        f"╔══════════════════╗\n   🏆 <b>LEADERBOARD SETTINGS</b>\n╚══════════════════╝\n\n"
        f"📊 <b>Enabled:</b> <code>{'🟢' if settings.get('top_reward_enabled') else '🔴'}</code>\n"
        f"👥 <b>Top Count:</b> <code>{settings.get('top_reward_count')}</code>\n"
        f"💰 <b>Prizes:</b> <code>{price_str}</code>\n\n"
        f"⚙️ <b>Auto Add:</b> <code>{'🟢 ON' if settings.get('top_auto_add') else '🔴 OFF'}</code>")
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton(text="🔛 TOGGLE LEADERBOARD",
        callback_data="lb_toggle", style="primary"))
    kb.add(types.InlineKeyboardButton(text="💰 SET PRIZES",
        callback_data="lb_prices", style="success"))
    kb.add(types.InlineKeyboardButton(text="⚙️ AUTO/MANUAL",
        callback_data="lb_auto", style="primary"))
    kb.add(types.InlineKeyboardButton(text="🏆 SHOW LEADERBOARD",
        callback_data="lb_show", style="success"))
    kb.row(types.InlineKeyboardButton(
        text=get_label("btn_back", "🔙 BACK"),
        callback_data="sys_back",
        style="danger", icon_custom_emoji_id=btn_eid("no")))
    try:
        bot.edit_message_text(text, chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML", reply_markup=kb)
    except: pass

@bot.callback_query_handler(func=lambda c: c.data == "lb_toggle")
def cb_lb_toggle(call):
    if not is_admin(call.message.chat.id): return
    settings["top_reward_enabled"] = not settings.get("top_reward_enabled", True)
    save_settings()
    bot.answer_callback_query(call.id, "Toggled!")
    show_leaderboard_settings(call)

@bot.callback_query_handler(func=lambda c: c.data == "lb_prices")
def cb_lb_prices(call):
    if not is_admin(call.message.chat.id): return
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id,
        pem(f"💰 <b>SET PRIZES</b>\n\nFormat: <code>1:50, 2:30, 3:20</code>"),
        parse_mode="HTML")
    bot.register_next_step_handler(msg, lb_save_prices)

def lb_save_prices(msg):
    if not is_admin(msg.chat.id): return
    try:
        prices = {}
        for part in msg.text.split(","):
            k, v = part.strip().split(":")
            prices[str(int(k.strip()))] = float(v.strip())
        settings["top_reward_prices"] = prices
        settings["top_reward_count"] = len(prices)
        save_settings()
        bot.send_message(msg.chat.id, f"✅ Prizes: {prices}")
    except:
        bot.send_message(msg.chat.id, "❌ Format: 1:50, 2:30, 3:20")

@bot.callback_query_handler(func=lambda c: c.data == "lb_auto")
def cb_lb_auto(call):
    if not is_admin(call.message.chat.id): return
    settings["top_auto_add"] = not settings.get("top_auto_add", False)
    save_settings()
    bot.answer_callback_query(call.id,
        f"Auto: {'ON' if settings['top_auto_add'] else 'OFF'}")
    show_leaderboard_settings(call)

@bot.callback_query_handler(func=lambda c: c.data == "lb_show")
def cb_lb_show(call):
    if not is_admin(call.message.chat.id): return
    today_otps = db_today_otps()
    user_counts = {}
    for o in today_otps:
        cid = str(o.get("chat_id"))
        user_counts[cid] = user_counts.get(cid, 0) + 1
    sorted_users = sorted(user_counts.items(), key=lambda x: x[1], reverse=True)[:15]
    lines = [pem(f"🏆 <b>LEADERBOARD</b>\n")]
    medals = ["🥇", "🥈", "🥉"]
    for i, (cid, count) in enumerate(sorted_users, 1):
        medal = medals[i-1] if i <= 3 else f"{i}."
        lines.append(f"{medal} <code>{cid}</code> — <b>{count} OTP</b>")
    if not sorted_users:
        lines.append("❌ No data.")
    try:
        bot.edit_message_text("\n".join(lines),
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML")
    except: pass

# ==========================================================
#           👥 REFER SETTINGS
# ==========================================================
def show_refer_settings(call):
    text = pem(
        f"╔══════════════════╗\n   👥 <b>REFER SETTINGS</b>\n╚══════════════════╝\n\n"
        f"📊 <b>Enabled:</b> <code>{'🟢' if settings.get('refer_enabled') else '🔴'}</code>\n"
        f"💰 <b>Reward per refer:</b> <code>৳{settings.get('refer_reward')}</code>")
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton(text="🔛 TOGGLE REFER",
        callback_data="ref_toggle", style="primary"))
    kb.add(types.InlineKeyboardButton(text="💰 SET REWARD",
        callback_data="ref_reward", style="success"))
    kb.row(types.InlineKeyboardButton(
        text=get_label("btn_back", "🔙 BACK"),
        callback_data="sys_back",
        style="danger", icon_custom_emoji_id=btn_eid("no")))
    try:
        bot.edit_message_text(text, chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML", reply_markup=kb)
    except: pass

@bot.callback_query_handler(func=lambda c: c.data == "ref_toggle")
def cb_ref_toggle(call):
    if not is_admin(call.message.chat.id): return
    settings["refer_enabled"] = not settings.get("refer_enabled", True)
    save_settings()
    bot.answer_callback_query(call.id, "Toggled!")
    show_refer_settings(call)

@bot.callback_query_handler(func=lambda c: c.data == "ref_reward")
def cb_ref_reward(call):
    if not is_admin(call.message.chat.id): return
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id,
        pem("💰 Reward amount (৳):"), parse_mode="HTML")
    bot.register_next_step_handler(msg, ref_save_reward)

def ref_save_reward(msg):
    if not is_admin(msg.chat.id): return
    try:
        settings["refer_reward"] = float(msg.text.strip())
        save_settings()
        bot.send_message(msg.chat.id,
            f"✅ Refer reward: ৳{settings['refer_reward']}")
    except:
        bot.send_message(msg.chat.id, "❌ Invalid!")

# ==========================================================
#   📢 MUST JOIN + 💳 PAYMENT CHANNEL (UPDATED)
# ==========================================================
def show_mustjoin_settings(call):
    channels = settings.get("must_join_channels", [])
    pay_enabled = settings.get("payment_channel_enabled", True)
    pay_ch_id = settings.get("payment_channel_id", "")
    pay_ch_name = settings.get("payment_channel_name", "PAYMENT CHANNEL")
    pay_ch_link = settings.get("payment_channel_link", "")

    text = pem(
        f"╔══════════════════╗\n   📢 <b>MUST JOIN + PAYMENT</b>\n╚══════════════════╝\n\n"
        f"📊 <b>Main Must Join:</b> <code>{'🟢 ON' if settings.get('must_join_enabled') else '🔴 OFF'}</code>\n"
        f"📋 <b>Channels:</b> <code>{len(channels)}</code>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💳 <b>PAYMENT CHANNEL</b>\n"
        f"📊 Status: <code>{'🟢 ON' if pay_enabled else '🔴 OFF'}</code>\n"
        f"📝 Name: <code>{pay_ch_name}</code>\n"
        f"🆔 ID: <code>{pay_ch_id or 'Not Set'}</code>\n"
        f"🔗 Link: <code>{pay_ch_link or 'Not Set'}</code>")

    kb = types.InlineKeyboardMarkup(row_width=1)
    # Main must join
    kb.add(types.InlineKeyboardButton(text="🔛 TOGGLE MUST JOIN",
        callback_data="mj_toggle", style="primary"))
    kb.add(types.InlineKeyboardButton(text="➕ ADD CHANNEL",
        callback_data="mj_add", style="success"))
    if channels:
        kb.add(types.InlineKeyboardButton(text="🗑 REMOVE CHANNEL",
            callback_data="mj_remove", style="danger"))
    # Payment channel
    kb.add(types.InlineKeyboardButton(
        text=f"💳 PAYMENT CHANNEL {'ON' if pay_enabled else 'OFF'}",
        callback_data="mj_pay_toggle",
        style="success" if pay_enabled else "danger"))
    kb.add(types.InlineKeyboardButton(text="⚙️ SET PAYMENT CHANNEL",
        callback_data="mj_pay_set", style="primary"))
    kb.row(types.InlineKeyboardButton(
        text=get_label("btn_back", "🔙 BACK"),
        callback_data="sys_back",
        style="danger", icon_custom_emoji_id=btn_eid("no")))
    try:
        bot.edit_message_text(text, chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML", reply_markup=kb)
    except: pass

@bot.callback_query_handler(func=lambda c: c.data == "mj_toggle")
def cb_mj_toggle(call):
    if not is_admin(call.message.chat.id): return
    settings["must_join_enabled"] = not settings.get("must_join_enabled", False)
    save_settings()
    bot.answer_callback_query(call.id,
        f"Must Join: {'ON' if settings['must_join_enabled'] else 'OFF'}")
    show_mustjoin_settings(call)

# ---------- ADD CHANNEL (Name + Link) ----------
@bot.callback_query_handler(func=lambda c: c.data == "mj_add")
def cb_mj_add(call):
    if not is_admin(call.message.chat.id): return
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id,
        pem(f"📝 <b>ADD MUST JOIN CHANNEL</b>\n\n"
            f"Format: <code>Channel Name | Channel Link | @username</code>\n\n"
            f"উদাহরণ:\n"
            f"<code>MAIN CHANNEL | https://t.me/mainchannel | @mainchannel</code>\n\n"
            f"⚠️ Bot কে অবশ্যই ঐ channel এ <b>admin</b> বানাতে হবে!"),
        parse_mode="HTML")
    bot.register_next_step_handler(msg, mj_save_channel)

def mj_save_channel(msg):
    if not is_admin(msg.chat.id): return
    try:
        parts = [p.strip() for p in msg.text.split("|")]
        if len(parts) < 2:
            bot.send_message(msg.chat.id,
                "❌ Format: Name | Link | @username")
            return
        name = parts[0]
        link = parts[1] if len(parts) > 1 else ""
        username = parts[2] if len(parts) > 2 else ""
        # Determine chat_id: prefer username, fallback link
        ch_id = username or link
        # Validate
        try:
            test = bot.get_chat(ch_id)
            real_id = str(test.id)
            real_name = test.title or name
        except Exception as e:
            bot.send_message(msg.chat.id,
                f"❌ Cannot access channel: {ch_id}\n\n"
                f"Error: {e}\n\n"
                f"⚠️ Bot কে ওই channel এ admin বানাও!")
            return
        if "must_join_channels" not in settings:
            settings["must_join_channels"] = []
        settings["must_join_channels"].append({
            "name": real_name,
            "id": real_id,
            "link": link,
            "username": username
        })
        save_settings()
        bot.send_message(msg.chat.id,
            pem(f"✅ <b>Channel Added!</b>\n\n"
                f"📝 Name: <code>{real_name}</code>\n"
                f"🆔 ID: <code>{real_id}</code>\n"
                f"🔗 Link: <code>{link}</code>"),
            parse_mode="HTML")
    except Exception as e:
        bot.send_message(msg.chat.id, f"❌ Error: {e}")

@bot.callback_query_handler(func=lambda c: c.data == "mj_remove")
def cb_mj_remove(call):
    if not is_admin(call.message.chat.id): return
    channels = settings.get("must_join_channels", [])
    if not channels:
        bot.answer_callback_query(call.id, "No channels!")
        return
    kb = types.InlineKeyboardMarkup(row_width=1)
    for i, ch in enumerate(channels):
        kb.add(types.InlineKeyboardButton(
            text=f"🗑 {ch.get('name')}",
            callback_data=f"mj_del:{i}", style="danger"))
    kb.row(types.InlineKeyboardButton(
        text=get_label("btn_back", "🔙 BACK"),
        callback_data="sys_mustjoin",
        style="danger", icon_custom_emoji_id=btn_eid("no")))
    try:
        bot.edit_message_text(pem("🗑 <b>REMOVE CHANNEL</b>"),
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML", reply_markup=kb)
    except: pass

@bot.callback_query_handler(func=lambda c: c.data.startswith("mj_del:"))
def cb_mj_del(call):
    if not is_admin(call.message.chat.id): return
    idx = int(call.data.split(":")[1])
    channels = settings.get("must_join_channels", [])
    if idx < len(channels):
        removed = channels.pop(idx)
        save_settings()
        bot.answer_callback_query(call.id, f"🗑 Removed {removed.get('name')}")
    show_mustjoin_settings(call)

# ---------- PAYMENT CHANNEL ----------
@bot.callback_query_handler(func=lambda c: c.data == "mj_pay_toggle")
def cb_mj_pay_toggle(call):
    if not is_admin(call.message.chat.id): return
    settings["payment_channel_enabled"] = not settings.get("payment_channel_enabled", True)
    save_settings()
    bot.answer_callback_query(call.id,
        f"Payment Channel: {'ON' if settings['payment_channel_enabled'] else 'OFF'}")
    show_mustjoin_settings(call)

@bot.callback_query_handler(func=lambda c: c.data == "mj_pay_set")
def cb_mj_pay_set(call):
    if not is_admin(call.message.chat.id): return
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id,
        pem(f"💳 <b>SET PAYMENT CHANNEL</b>\n\n"
            f"Format: <code>Channel ID | Channel Link</code>\n\n"
            f"উদাহরণ:\n"
            f"<code>-1001234567890 | https://t.me/yourchannel</code>\n\n"
            f"⚠️ Bot কে অবশ্যই ঐ channel এ <b>admin</b> বানাতে হবে!"),
        parse_mode="HTML")
    bot.register_next_step_handler(msg, mj_pay_save)

def mj_pay_save(msg):
    if not is_admin(msg.chat.id): return
    try:
        text = msg.text.strip()
        if "|" in text:
            parts = [p.strip() for p in text.split("|")]
            ch_id = parts[0]
            ch_link = parts[1] if len(parts) > 1 else ""
        else:
            ch_id = text
            ch_link = ""
        try:
            test = bot.get_chat(ch_id)
            ch_name = test.title or "PAYMENT CHANNEL"
            real_id = str(test.id)
        except Exception as e:
            bot.send_message(msg.chat.id,
                f"❌ Cannot access channel: {ch_id}\n\n"
                f"Error: {e}\n\n"
                f"⚠️ Bot কে ওই channel এ admin বানাও!")
            return
        settings["payment_channel_id"] = real_id
        settings["payment_channel_link"] = ch_link
        settings["payment_channel_name"] = ch_name
        save_settings()
        bot.send_message(msg.chat.id,
            pem(f"✅ <b>PAYMENT CHANNEL SET!</b>\n\n"
                f"📝 Name: <code>{ch_name}</code>\n"
                f"🆔 ID: <code>{real_id}</code>\n"
                f"🔗 Link: <code>{ch_link or 'Not set'}</code>\n\n"
                f"এখন থেকে সব withdraw request এই channel এ যাবে।"),
            parse_mode="HTML")
    except Exception as e:
        bot.send_message(msg.chat.id, f"❌ Error: {e}")

print("[PART 4/5] ✅ Loaded System (Withdraw + Broadcast + Leaderboard + Refer + MustJoin)")
# ==========================================================
#  ZENEX OTP BOT v18.0 PRO EDITION — PART 5/5
#  EMOJI CONTROL + CUSTOM EMOJI + CUSTOM COLOR +
#  SET ADMIN + DEBUG + WATCHDOG + BOT RUN
# ==========================================================

# ==========================================================
#   🎛 EMOJI CONTROL — LIVE EDIT MODE
# ==========================================================
def ec_main_menu(chat_id, message_id=None):
    text = pem(
        f"╔══════════════════╗\n   🎛 <b>EMOJI CONTROL</b>\n╚══════════════════╝\n\n"
        f"⚙️ কোন mode এ edit করবে?\n\n"
        f"👑 <b>Admin Mode</b> — Admin panel এর keyboard\n"
        f"👤 <b>User Mode</b> — User bot এর keyboard\n\n"
        f"<i>লাইভ edit — এখানে যা change করবেন, সরাসরি bot-এ apply হবে</i>")
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton(text="👑 ADMIN MODE",
        callback_data="ecm:admin", style="primary",
        icon_custom_emoji_id=btn_eid("crown")))
    kb.add(types.InlineKeyboardButton(text="👤 USER MODE",
        callback_data="ecm:user", style="success",
        icon_custom_emoji_id=btn_eid("user")))
    kb.row(types.InlineKeyboardButton(text=get_label("btn_back", "🔙 BACK"),
        callback_data="admin_back", style="danger",
        icon_custom_emoji_id=btn_eid("no")))
    if message_id:
        try:
            bot.edit_message_text(text, chat_id=chat_id, message_id=message_id,
                                  parse_mode="HTML", reply_markup=kb)
            return
        except: pass
    bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=kb)

@bot.message_handler(func=lambda m: m.text in [
    "🎛 EMOJI CONTROL", get_label("btn_emoji_control", "🎛 EMOJI CONTROL")
] and is_admin(m.chat.id))
def admin_emoji_control(msg):
    if not is_admin(msg.chat.id): return
    check_owner_premium(msg)
    ec_main_menu(msg.chat.id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("ecm:"))
def cb_ecm(call):
    if not is_admin(call.message.chat.id): return
    mode = call.data.split(":")[1]
    EMOJI_CONTROL_MODE[call.message.chat.id] = mode
    if mode == "admin":
        ec_show_admin_buttons(call.message.chat.id, call.message.message_id)
    else:
        ec_show_user_buttons(call.message.chat.id, call.message.message_id)

def ec_show_admin_buttons(chat_id, message_id=None):
    text = pem(
        f"👑 <b>ADMIN MODE</b>\n\n"
        f"নিচের বাটনগুলো আপনার bot-এর admin panel-এ যেভাবে দেখায়:\n\n"
        f"👆 ট্যাপ করলে EDIT/NEXT option আসবে")
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.row(
        types.InlineKeyboardButton(text=get_label("btn_set_speed", "⚡ SET SPEED"),
            callback_data="ec_btn:btn_set_speed",
            style=btn_style("btn_set_speed", "primary"),
            icon_custom_emoji_id=btn_eid("rocket")),
        types.InlineKeyboardButton(text=get_label("btn_filter", "🔧 FILTER SERVICE"),
            callback_data="ec_btn:btn_filter",
            style=btn_style("btn_filter", "primary"),
            icon_custom_emoji_id=btn_eid("gear")))
    kb.row(
        types.InlineKeyboardButton(text=get_label("btn_today_otp", "📊 TODAY OTP"),
            callback_data="ec_btn:btn_today_otp",
            style=btn_style("btn_today_otp", "success"),
            icon_custom_emoji_id=btn_eid("graph")),
        types.InlineKeyboardButton(text=get_label("btn_all_users", "👥 ALL USERS"),
            callback_data="ec_btn:btn_all_users",
            style=btn_style("btn_all_users", "success"),
            icon_custom_emoji_id=btn_eid("user")))
    kb.row(
        types.InlineKeyboardButton(text=get_label("btn_manage_keys", "🔑 MANAGE KEYS"),
            callback_data="ec_btn:btn_manage_keys",
            style=btn_style("btn_manage_keys", "primary"),
            icon_custom_emoji_id=btn_eid("key")),
        types.InlineKeyboardButton(text=get_label("btn_custom_emoji", "🎨 SET CUSTOM EMOJI"),
            callback_data="ec_btn:btn_custom_emoji",
            style=btn_style("btn_custom_emoji", "primary"),
            icon_custom_emoji_id=btn_eid("crown")))
    kb.row(
        types.InlineKeyboardButton(text=get_label("btn_custom_color", "🎨 CUSTOM COLOR"),
            callback_data="ec_btn:btn_custom_color",
            style=btn_style("btn_custom_color", "primary"),
            icon_custom_emoji_id=btn_eid("crown")),
        types.InlineKeyboardButton(text=get_label("btn_emoji_toggle", "🎭 EMOJI ON/OFF"),
            callback_data="ec_btn:btn_emoji_toggle",
            style=btn_style("btn_emoji_toggle", "success"),
            icon_custom_emoji_id=btn_eid("star")))
    kb.row(
        types.InlineKeyboardButton(text=get_label("btn_emoji_control", "🎛 EMOJI CONTROL"),
            callback_data="ec_btn:btn_emoji_control",
            style=btn_style("btn_emoji_control", "primary"),
            icon_custom_emoji_id=btn_eid("crown")),
        types.InlineKeyboardButton(text=get_label("btn_set_admin", "👑 SET ADMIN"),
            callback_data="ec_btn:btn_set_admin",
            style=btn_style("btn_set_admin", "primary"),
            icon_custom_emoji_id=btn_eid("crown")))
    kb.row(
        types.InlineKeyboardButton(text=get_label("btn_search_user", "🔍 SEARCH USER"),
            callback_data="ec_btn:btn_search_user",
            style=btn_style("btn_search_user", "primary"),
            icon_custom_emoji_id=btn_eid("user")),
        types.InlineKeyboardButton(text=get_label("btn_system", "⚙️ SYSTEM"),
            callback_data="ec_btn:btn_system",
            style=btn_style("btn_system", "primary"),
            icon_custom_emoji_id=btn_eid("gear")))
    kb.row(types.InlineKeyboardButton(text=get_label("btn_back_to_bot", "🔙 BACK TO BOT"),
            callback_data="ec_btn:btn_back_to_bot",
            style=btn_style("btn_back_to_bot", "danger"),
            icon_custom_emoji_id=btn_eid("no")))
    kb.row(types.InlineKeyboardButton(text="🔙 BACK", callback_data="ec_main",
        style="danger", icon_custom_emoji_id=btn_eid("no")))
    if message_id:
        try:
            bot.edit_message_text(text, chat_id=chat_id, message_id=message_id,
                                  parse_mode="HTML", reply_markup=kb)
            return
        except: pass
    bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=kb)

def ec_show_user_buttons(chat_id, message_id=None):
    text = pem(
        f"👤 <b>USER MODE</b>\n\n"
        f"এটা user bot-এর keyboard। যেকোনো বাটনে ট্যাপ → EDIT/NEXT")
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.row(
        types.InlineKeyboardButton(text=get_label("btn_get_number", "📲 GET NUMBER"),
            callback_data="ec_btn:btn_get_number",
            style=btn_style("btn_get_number", "primary"),
            icon_custom_emoji_id=btn_eid("phone")),
        types.InlineKeyboardButton(text=get_label("btn_profile", "👤 PROFILE"),
            callback_data="ec_btn:btn_profile",
            style=btn_style("btn_profile", "primary"),
            icon_custom_emoji_id=btn_eid("user")))
    kb.row(
        types.InlineKeyboardButton(text=get_label("btn_top_reward", "🏆 TOP REWARD"),
            callback_data="ec_btn:btn_top_reward",
            style=btn_style("btn_top_reward", "success"),
            icon_custom_emoji_id=btn_eid("star")),
        types.InlineKeyboardButton(text=get_label("btn_balance", "💰 MY BALANCE"),
            callback_data="ec_btn:btn_balance",
            style=btn_style("btn_balance", "success"),
            icon_custom_emoji_id=btn_eid("money")))
    kb.row(
        types.InlineKeyboardButton(text=get_label("btn_zenex", "⚡ ZENEX"),
            callback_data="ec_btn:btn_zenex",
            style=btn_style("btn_zenex", "primary"),
            icon_custom_emoji_id=btn_eid("fire")),
        types.InlineKeyboardButton(text=get_label("btn_stex", "🔵 STEX"),
            callback_data="ec_btn:btn_stex",
            style=btn_style("btn_stex", "primary")))
    kb.row(
        types.InlineKeyboardButton(text="⚡ FACEBOOK",
            callback_data="ec_btn:svc_facebook",
            style=btn_style("btn_zenex", "primary"),
            icon_custom_emoji_id=btn_eid("fire")),
        types.InlineKeyboardButton(text="⚡ INSTAGRAM",
            callback_data="ec_btn:svc_instagram",
            style=btn_style("btn_zenex", "primary"),
            icon_custom_emoji_id=btn_eid("fire")))
    kb.row(types.InlineKeyboardButton(text="237625XXX",
        callback_data="ec_btn:btn_number",
        style=btn_style("btn_number", "primary"),
        icon_custom_emoji_id=btn_eid("phone")))
    kb.row(
        types.InlineKeyboardButton(text=get_label("btn_change", "🔄 CHANGE"),
            callback_data="ec_btn:btn_change",
            style=btn_style("btn_change", "success"),
            icon_custom_emoji_id=btn_eid("rocket")),
        types.InlineKeyboardButton(text=get_label("btn_back", "🔙 BACK"),
            callback_data="ec_btn:btn_back",
            style=btn_style("btn_back", "danger"),
            icon_custom_emoji_id=btn_eid("no")))
    kb.row(types.InlineKeyboardButton(text="🔙 BACK", callback_data="ec_main",
        style="danger", icon_custom_emoji_id=btn_eid("no")))
    if message_id:
        try:
            bot.edit_message_text(text, chat_id=chat_id, message_id=message_id,
                                  parse_mode="HTML", reply_markup=kb)
            return
        except: pass
    bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "ec_main")
def cb_ec_main(call):
    if not is_admin(call.message.chat.id): return
    ec_main_menu(call.message.chat.id, call.message.message_id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("ec_btn:"))
def cb_ec_btn(call):
    if not is_admin(call.message.chat.id): return
    btn_key = call.data.split(":", 1)[1]
    mode = EMOJI_CONTROL_MODE.get(call.message.chat.id, "user")
    current_label = get_label(btn_key, ALL_BUTTONS.get(btn_key, btn_key))
    current_emoji = CUSTOM_EMOJI.get(f"__inline_{btn_key}") or BTN_EMOJI.get(btn_key, "None")
    current_color = BUTTON_COLORS.get(btn_key, "Default")
    text = pem(
        f"🎛 <b>BUTTON CONTROL</b>\n\n"
        f"🔖 <b>Button:</b> <code>{btn_key}</code>\n"
        f"📝 <b>Label:</b> <code>{current_label}</code>\n"
        f"🎭 <b>Emoji ID:</b> <code>{current_emoji}</code>\n"
        f"🎨 <b>Color:</b> <code>{current_color}</code>\n"
        f"📊 <b>Mode:</b> <code>{mode.upper()}</code>\n\n"
        f"⚙️ কী করতে চাও?")
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(types.InlineKeyboardButton(text="✏️ EDIT LABEL",
        callback_data=f"ec_edit:label:{btn_key}", style="primary"))
    kb.add(types.InlineKeyboardButton(text="🎭 EDIT EMOJI",
        callback_data=f"ec_edit:emoji:{btn_key}", style="success"))
    kb.add(types.InlineKeyboardButton(text="🎨 EDIT COLOR",
        callback_data=f"ec_edit:color:{btn_key}", style="primary"))
    kb.add(types.InlineKeyboardButton(text="🗑 RESET ALL",
        callback_data=f"ec_edit:reset:{btn_key}", style="danger"))
    kb.row(types.InlineKeyboardButton(text="🔙 BACK",
        callback_data=f"ecm:{mode}", style="danger",
        icon_custom_emoji_id=btn_eid("no")))
    try:
        bot.edit_message_text(text, chat_id=call.message.chat.id,
                              message_id=call.message.message_id,
                              parse_mode="HTML", reply_markup=kb)
    except: pass

@bot.callback_query_handler(func=lambda c: c.data.startswith("ec_edit:"))
def cb_ec_edit(call):
    if not is_admin(call.message.chat.id): return
    parts = call.data.split(":", 2)
    action, btn_key = parts[1], parts[2]
    mode = EMOJI_CONTROL_MODE.get(call.message.chat.id, "user")
    if action == "reset":
        CUSTOM_EMOJI.pop(f"__inline_{btn_key}", None)
        CUSTOM_EMOJI.pop(btn_key, None)
        BUTTON_COLORS.pop(btn_key, None)
        CUSTOM_LABELS.pop(btn_key, None)
        save_json(EMOJI_SAVE_FILE, CUSTOM_EMOJI)
        save_json(COLOR_SAVE_FILE, BUTTON_COLORS)
        save_json(LABEL_SAVE_FILE, CUSTOM_LABELS)
        bot.answer_callback_query(call.id, "🗑 Reset to default!")
        if mode == "admin":
            ec_show_admin_buttons(call.message.chat.id, call.message.message_id)
        else:
            ec_show_user_buttons(call.message.chat.id, call.message.message_id)
        return
    if action == "label":
        msg = bot.send_message(call.message.chat.id,
            pem(f"✏️ <b>NEW LABEL</b>\n\n🔖 বাটন: <code>{btn_key}</code>\n\n"
                f"📝 নতুন label পাঠাও:"), parse_mode="HTML")
        bot.register_next_step_handler(msg, ec_save_label, btn_key, mode)
        return
    if action == "emoji":
        msg = bot.send_message(call.message.chat.id,
            pem(f"🎭 <b>NEW EMOJI ID</b>\n\n🔖 বাটন: <code>{btn_key}</code>\n\n"
                f"📝 Premium emoji ID পাঠাও (শুধু number):"), parse_mode="HTML")
        bot.register_next_step_handler(msg, ec_save_emoji, btn_key, mode)
        return
    if action == "color":
        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.add(
            types.InlineKeyboardButton(text="🔵 Primary",
                callback_data=f"ec_setc:{btn_key}:primary", style="primary"),
            types.InlineKeyboardButton(text="🟢 Success",
                callback_data=f"ec_setc:{btn_key}:success", style="success"))
        kb.add(
            types.InlineKeyboardButton(text="🔴 Danger",
                callback_data=f"ec_setc:{btn_key}:danger", style="danger"),
            types.InlineKeyboardButton(text="⬜ Default",
                callback_data=f"ec_setc:{btn_key}:none"))
        kb.row(types.InlineKeyboardButton(text="🔙 BACK",
            callback_data=f"ec_btn:{btn_key}",
            style="danger", icon_custom_emoji_id=btn_eid("no")))
        try:
            bot.edit_message_text(
                pem(f"🎨 <b>SELECT COLOR</b>\n\n🔖 বাটন: <code>{btn_key}</code>"),
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="HTML", reply_markup=kb)
        except: pass

def ec_save_label(msg, btn_key, mode):
    if not is_admin(msg.chat.id): return
    label = msg.text.strip() if msg.text else ""
    if not label:
        bot.send_message(msg.chat.id, "❌ খালি label দিও না!")
        return
    CUSTOM_LABELS[btn_key] = label
    save_json(LABEL_SAVE_FILE, CUSTOM_LABELS)
    bot.send_message(msg.chat.id,
        pem(f"✅ <b>Label Saved!</b>\n\n🔖 {btn_key} → <code>{label}</code>"),
        parse_mode="HTML")
    if mode == "admin":
        ec_show_admin_buttons(msg.chat.id)
    else:
        ec_show_user_buttons(msg.chat.id)

def ec_save_emoji(msg, btn_key, mode):
    if not is_admin(msg.chat.id): return
    val = msg.text.strip() if msg.text else ""
    if not val.isdigit():
        bot.send_message(msg.chat.id, "❌ শুধু number দাও!")
        return
    CUSTOM_EMOJI[f"__inline_{btn_key}"] = val
    save_json(EMOJI_SAVE_FILE, CUSTOM_EMOJI)
    bot.send_message(msg.chat.id,
        pem(f"✅ <b>Emoji Saved!</b>\n\n🔖 {btn_key} → <code>{val}</code>"),
        parse_mode="HTML")
    if mode == "admin":
        ec_show_admin_buttons(msg.chat.id)
    else:
        ec_show_user_buttons(msg.chat.id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("ec_setc:"))
def cb_ec_setc(call):
    if not is_admin(call.message.chat.id): return
    parts = call.data.split(":", 2)
    btn_key, color = parts[1], parts[2]
    mode = EMOJI_CONTROL_MODE.get(call.message.chat.id, "user")
    if color == "none":
        BUTTON_COLORS.pop(btn_key, None)
    else:
        BUTTON_COLORS[btn_key] = color
    save_json(COLOR_SAVE_FILE, BUTTON_COLORS)
    bot.answer_callback_query(call.id, f"✅ {btn_key} → {color}")
    if mode == "admin":
        ec_show_admin_buttons(call.message.chat.id, call.message.message_id)
    else:
        ec_show_user_buttons(call.message.chat.id, call.message.message_id)

# ==========================================================
#   🎨 SET CUSTOM EMOJI (Preview সহ)
# ==========================================================
def emoji_preview_main(chat_id, message_id=None):
    text = pem(
        f"╔══════════════════╗\n   🎨 <b>CUSTOM EMOJI</b>\n╚══════════════════╝\n\n"
        f"⚙️ কোন keyboard এর emoji এডিট করবে?")
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton(text="📱 INLINE KEYBOARD PREVIEW",
        callback_data="epv:inline", style="primary"))
    kb.add(types.InlineKeyboardButton(text="⌨️ REPLY KEYBOARD PREVIEW",
        callback_data="epv:reply", style="primary"))
    kb.row(types.InlineKeyboardButton(text=get_label("btn_back", "🔙 BACK"),
        callback_data="admin_back", style="danger",
        icon_custom_emoji_id=btn_eid("no")))
    if message_id:
        try:
            bot.edit_message_text(text, chat_id=chat_id, message_id=message_id,
                                  parse_mode="HTML", reply_markup=kb)
            return
        except: pass
    bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=kb)

@bot.message_handler(func=lambda m: m.text in [
    "🎨 SET CUSTOM EMOJI", get_label("btn_custom_emoji", "🎨 SET CUSTOM EMOJI")
] and is_admin(m.chat.id))
def admin_custom_emoji(msg):
    check_owner_premium(msg)
    emoji_preview_main(msg.chat.id)

@bot.callback_query_handler(func=lambda c: c.data == "epv:inline" or c.data == "epv:reply")
def cb_epv_menu(call):
    if not is_admin(call.message.chat.id): return
    kind = call.data.split(":")[1]
    send_emoji_preview(call.message.chat.id, kind, call.message.message_id)

def send_emoji_preview(chat_id, kind, message_id=None):
    kb = types.InlineKeyboardMarkup(row_width=2)
    if kind == "inline":
        kb.row(
            types.InlineKeyboardButton(text="⚡ ZENEX",
                callback_data="eedit:inline:btn_zenex",
                style=btn_style("btn_zenex", "primary"),
                icon_custom_emoji_id=btn_eid("fire")),
            types.InlineKeyboardButton(text="🔵 STEX",
                callback_data="eedit:inline:btn_stex",
                style=btn_style("btn_stex", "primary")))
        kb.row(
            types.InlineKeyboardButton(text="⚡ FACEBOOK",
                callback_data="eedit:inline:svc_facebook",
                style=btn_style("btn_zenex", "primary"),
                icon_custom_emoji_id=btn_eid("fire")),
            types.InlineKeyboardButton(text="⚡ INSTAGRAM",
                callback_data="eedit:inline:svc_instagram",
                style=btn_style("btn_zenex", "primary"),
                icon_custom_emoji_id=btn_eid("fire")))
        kb.row(types.InlineKeyboardButton(text="237625XXX",
                callback_data="eedit:inline:btn_number",
                style=btn_style("btn_number", "primary"),
                icon_custom_emoji_id=btn_eid("phone")))
        kb.row(
            types.InlineKeyboardButton(text="🔄 CHANGE",
                callback_data="eedit:inline:btn_change",
                style=btn_style("btn_change", "success"),
                icon_custom_emoji_id=btn_eid("rocket")),
            types.InlineKeyboardButton(text="🔙 BACK",
                callback_data="eedit:inline:btn_back",
                style=btn_style("btn_back", "danger"),
                icon_custom_emoji_id=btn_eid("no")))
    else:
        kb.row(
            types.InlineKeyboardButton(text="📲 GET NUMBER",
                callback_data="eedit:reply:btn_get_number",
                style=btn_style("btn_get_number", "primary"),
                icon_custom_emoji_id=btn_eid("phone")),
            types.InlineKeyboardButton(text="👤 PROFILE",
                callback_data="eedit:reply:btn_profile",
                style=btn_style("btn_profile", "primary"),
                icon_custom_emoji_id=btn_eid("user")))
        kb.row(
            types.InlineKeyboardButton(text="🏆 TOP REWARD",
                callback_data="eedit:reply:btn_top_reward",
                style=btn_style("btn_top_reward", "success"),
                icon_custom_emoji_id=btn_eid("star")),
            types.InlineKeyboardButton(text="💰 MY BALANCE",
                callback_data="eedit:reply:btn_balance",
                style=btn_style("btn_balance", "success"),
                icon_custom_emoji_id=btn_eid("money")))
        kb.row(
            types.InlineKeyboardButton(text="⚡ SET SPEED",
                callback_data="eedit:reply:btn_set_speed",
                style=btn_style("btn_set_speed", "primary")),
            types.InlineKeyboardButton(text="🔧 FILTER SERVICE",
                callback_data="eedit:reply:btn_filter",
                style=btn_style("btn_filter", "primary")))
        kb.row(
            types.InlineKeyboardButton(text="📊 TODAY OTP",
                callback_data="eedit:reply:btn_today_otp",
                style=btn_style("btn_today_otp", "success")),
            types.InlineKeyboardButton(text="👥 ALL USERS",
                callback_data="eedit:reply:btn_all_users",
                style=btn_style("btn_all_users", "success")))
        kb.row(
            types.InlineKeyboardButton(text="🔑 MANAGE KEYS",
                callback_data="eedit:reply:btn_manage_keys",
                style=btn_style("btn_manage_keys", "primary")),
            types.InlineKeyboardButton(text="🎨 SET CUSTOM EMOJI",
                callback_data="eedit:reply:btn_custom_emoji",
                style=btn_style("btn_custom_emoji", "primary")))
        kb.row(
            types.InlineKeyboardButton(text="🎨 CUSTOM COLOR",
                callback_data="eedit:reply:btn_custom_color",
                style=btn_style("btn_custom_color", "primary")),
            types.InlineKeyboardButton(text="🎭 EMOJI ON/OFF",
                callback_data="eedit:reply:btn_emoji_toggle",
                style=btn_style("btn_emoji_toggle", "success")))
        kb.row(
            types.InlineKeyboardButton(text="🔍 SEARCH USER",
                callback_data="eedit:reply:btn_search_user",
                style=btn_style("btn_search_user", "primary")),
            types.InlineKeyboardButton(text="⚙️ SYSTEM",
                callback_data="eedit:reply:btn_system",
                style=btn_style("btn_system", "primary")))
        kb.row(
            types.InlineKeyboardButton(text="👑 SET ADMIN",
                callback_data="eedit:reply:btn_set_admin",
                style=btn_style("btn_set_admin", "primary")),
            types.InlineKeyboardButton(text="🔙 BACK TO BOT",
                callback_data="eedit:reply:btn_back_to_bot",
                style=btn_style("btn_back_to_bot", "danger")))
    kb.row(types.InlineKeyboardButton(text=get_label("btn_back", "🔙 BACK"),
        callback_data="epv:back", style="danger",
        icon_custom_emoji_id=btn_eid("no")))
    header = pem(
        f"📋 <b>{'INLINE' if kind=='inline' else 'REPLY'} KEYBOARD PREVIEW</b>\n\n"
        f"👆 ট্যাপ করে emoji এডিট করো 👇")
    if message_id:
        try:
            bot.edit_message_text(header, chat_id=chat_id, message_id=message_id,
                                  parse_mode="HTML", reply_markup=kb)
            return
        except: pass
    bot.send_message(chat_id, header, parse_mode="HTML", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "epv:back")
def cb_epv_back(call):
    if not is_admin(call.message.chat.id): return
    emoji_preview_main(call.message.chat.id, call.message.message_id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("eedit:"))
def cb_eedit(call):
    if not is_admin(call.message.chat.id): return
    _, kind, btn_key = call.data.split(":", 2)
    if kind == "inline":
        current = CUSTOM_EMOJI.get(f"__inline_{btn_key}") or BTN_EMOJI.get(btn_key, "None")
        is_custom = f"__inline_{btn_key}" in CUSTOM_EMOJI
    else:
        current = CUSTOM_EMOJI.get(btn_key) or BTN_EMOJI.get(btn_key, "None")
        is_custom = btn_key in CUSTOM_EMOJI
    label = ALL_BUTTONS.get(btn_key, btn_key)
    text = pem(
        f"🎨 <b>EDIT BUTTON EMOJI</b>\n\n"
        f"🔖 <b>বাটন:</b> <code>{label}</code>\n"
        f"🆔 <b>Button Key:</b> <code>{btn_key}</code>\n"
        f"🎯 <b>Current Emoji ID:</b> <code>{current}</code>\n"
        f"📊 <b>Status:</b> <code>{'🟢 Custom' if is_custom else '⚪ Default'}</code>\n\n"
        f"⚙️ কী করতে চাও?")
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(types.InlineKeyboardButton(text="✏️ REPLACE",
        callback_data=f"eact:replace:{kind}:{btn_key}", style="primary"))
    if is_custom:
        kb.add(types.InlineKeyboardButton(text="🗑 REMOVE",
            callback_data=f"eact:remove:{kind}:{btn_key}", style="danger"))
    kb.add(types.InlineKeyboardButton(text="➕ ADD NEW ID",
        callback_data=f"eact:replace:{kind}:{btn_key}", style="success"))
    kb.row(types.InlineKeyboardButton(text=get_label("btn_back", "🔙 BACK"),
        callback_data=f"eact:preview:{kind}:{btn_key}",
        style="danger", icon_custom_emoji_id=btn_eid("no")))
    try:
        bot.edit_message_text(text, chat_id=call.message.chat.id,
                              message_id=call.message.message_id,
                              parse_mode="HTML", reply_markup=kb)
    except: pass

@bot.callback_query_handler(func=lambda c: c.data.startswith("eact:"))
def cb_eact(call):
    if not is_admin(call.message.chat.id): return
    parts = call.data.split(":")
    action, kind, btn_key = parts[1], parts[2], parts[3]
    if action == "preview":
        try: bot.delete_message(call.message.chat.id, call.message.message_id)
        except: pass
        send_emoji_preview(call.message.chat.id, kind)
        return
    if action == "remove":
        if kind == "inline":
            CUSTOM_EMOJI.pop(f"__inline_{btn_key}", None)
        else:
            CUSTOM_EMOJI.pop(btn_key, None)
        save_json(EMOJI_SAVE_FILE, CUSTOM_EMOJI)
        bot.answer_callback_query(call.id, "🗑 Removed!")
        try: bot.delete_message(call.message.chat.id, call.message.message_id)
        except: pass
        send_emoji_preview(call.message.chat.id, kind)
        return
    msg = bot.send_message(call.message.chat.id,
        pem(f"✏️ <b>NEW EMOJI ID</b>\n\n🔖 বাটন: <code>{btn_key}</code>\n\n"
            f"📝 নতুন <b>premium emoji ID</b> পাঠাও:"),
        parse_mode="HTML")
    bot.register_next_step_handler(msg, emoji_confirm_new_id, kind, btn_key)

def emoji_confirm_new_id(msg, kind, btn_key):
    if not is_admin(msg.chat.id): return
    val = msg.text.strip() if msg.text else ""
    if not val.isdigit():
        bot.send_message(msg.chat.id, "❌ শুধু number দাও!")
        return
    label = ALL_BUTTONS.get(btn_key, btn_key)
    text = pem(
        f"⚠️ <b>CONFIRM?</b>\n\n"
        f"🔖 বাটন: <code>{label}</code>\n"
        f"🆔 Key: <code>{btn_key}</code>\n"
        f"🆕 New ID: <code>{val}</code>\n\n"
        f"নিশ্চিত হলে CONFIRM চাপো:")
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton(text="✅ CONFIRM",
            callback_data=f"eok:{kind}:{btn_key}:{val}", style="success"),
        types.InlineKeyboardButton(text="❌ CANCEL",
            callback_data=f"eact:preview:{kind}:{btn_key}", style="danger"))
    bot.send_message(msg.chat.id, text, parse_mode="HTML", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("eok:"))
def cb_emoji_ok(call):
    if not is_admin(call.message.chat.id): return
    _, kind, btn_key, val = call.data.split(":", 3)
    if kind == "inline":
        CUSTOM_EMOJI[f"__inline_{btn_key}"] = val
    else:
        CUSTOM_EMOJI[btn_key] = val
    save_json(EMOJI_SAVE_FILE, CUSTOM_EMOJI)
    bot.answer_callback_query(call.id, "✅ Saved!")
    bot.send_message(call.message.chat.id,
        pem(f"✅ <b>Emoji Updated!</b>\n\nবাটন: <code>{btn_key}</code>\nNew: <code>{val}</code>"),
        parse_mode="HTML")
    try: bot.delete_message(call.message.chat.id, call.message.message_id)
    except: pass
    send_emoji_preview(call.message.chat.id, kind)

# ==========================================================
#   🎨 CUSTOM COLOR (Preview সহ)
# ==========================================================
def color_preview_main(chat_id, message_id=None):
    text = pem(
        f"╔══════════════════╗\n   🎨 <b>CUSTOM COLOR</b>\n╚══════════════════╝\n\n"
        f"⚙️ কোন keyboard এর কালার এডিট করবে?")
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton(text="📱 INLINE KEYBOARD COLORS",
        callback_data="cpv:inline", style="primary"))
    kb.add(types.InlineKeyboardButton(text="⌨️ REPLY KEYBOARD COLORS",
        callback_data="cpv:reply", style="primary"))
    kb.row(types.InlineKeyboardButton(text=get_label("btn_back", "🔙 BACK"),
        callback_data="admin_back", style="danger",
        icon_custom_emoji_id=btn_eid("no")))
    if message_id:
        try:
            bot.edit_message_text(text, chat_id=chat_id, message_id=message_id,
                                  parse_mode="HTML", reply_markup=kb)
            return
        except: pass
    bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=kb)

@bot.message_handler(func=lambda m: m.text in [
    "🎨 CUSTOM COLOR", get_label("btn_custom_color", "🎨 CUSTOM COLOR")
] and is_admin(m.chat.id))
def admin_custom_color(msg):
    check_owner_premium(msg)
    color_preview_main(msg.chat.id)

@bot.callback_query_handler(func=lambda c: c.data == "cpv:inline" or c.data == "cpv:reply")
def cb_cpv_menu(call):
    if not is_admin(call.message.chat.id): return
    kind = call.data.split(":")[1]
    send_color_preview(call.message.chat.id, kind, call.message.message_id)

def send_color_preview(chat_id, kind, message_id=None):
    kb = types.InlineKeyboardMarkup(row_width=2)
    if kind == "inline":
        kb.row(
            types.InlineKeyboardButton(text="⚡ ZENEX",
                callback_data="cedit:inline:btn_zenex",
                style=btn_style("btn_zenex", "primary"),
                icon_custom_emoji_id=btn_eid("fire")),
            types.InlineKeyboardButton(text="🔵 STEX",
                callback_data="cedit:inline:btn_stex",
                style=btn_style("btn_stex", "primary")))
        kb.row(
            types.InlineKeyboardButton(text="⚡ FACEBOOK",
                callback_data="cedit:inline:svc_facebook",
                style=btn_style("btn_zenex", "primary"),
                icon_custom_emoji_id=btn_eid("fire")),
            types.InlineKeyboardButton(text="⚡ INSTAGRAM",
                callback_data="cedit:inline:svc_instagram",
                style=btn_style("btn_zenex", "primary"),
                icon_custom_emoji_id=btn_eid("fire")))
        kb.row(types.InlineKeyboardButton(text="237625XXX",
                callback_data="cedit:inline:btn_number",
                style=btn_style("btn_number", "primary"),
                icon_custom_emoji_id=btn_eid("phone")))
        kb.row(
            types.InlineKeyboardButton(text="🔄 CHANGE",
                callback_data="cedit:inline:btn_change",
                style=btn_style("btn_change", "success"),
                icon_custom_emoji_id=btn_eid("rocket")),
            types.InlineKeyboardButton(text="🔙 BACK",
                callback_data="cedit:inline:btn_back",
                style=btn_style("btn_back", "danger"),
                icon_custom_emoji_id=btn_eid("no")))
    else:
        kb.row(
            types.InlineKeyboardButton(text="📲 GET NUMBER",
                callback_data="cedit:reply:btn_get_number",
                style=btn_style("btn_get_number", "primary"),
                icon_custom_emoji_id=btn_eid("phone")),
            types.InlineKeyboardButton(text="👤 PROFILE",
                callback_data="cedit:reply:btn_profile",
                style=btn_style("btn_profile", "primary"),
                icon_custom_emoji_id=btn_eid("user")))
        kb.row(
            types.InlineKeyboardButton(text="🏆 TOP REWARD",
                callback_data="cedit:reply:btn_top_reward",
                style=btn_style("btn_top_reward", "success"),
                icon_custom_emoji_id=btn_eid("star")),
            types.InlineKeyboardButton(text="💰 MY BALANCE",
                callback_data="cedit:reply:btn_balance",
                style=btn_style("btn_balance", "success"),
                icon_custom_emoji_id=btn_eid("money")))
        kb.row(
            types.InlineKeyboardButton(text="⚡ SET SPEED",
                callback_data="cedit:reply:btn_set_speed",
                style=btn_style("btn_set_speed", "primary")),
            types.InlineKeyboardButton(text="🔧 FILTER SERVICE",
                callback_data="cedit:reply:btn_filter",
                style=btn_style("btn_filter", "primary")))
        kb.row(
            types.InlineKeyboardButton(text="📊 TODAY OTP",
                callback_data="cedit:reply:btn_today_otp",
                style=btn_style("btn_today_otp", "success")),
            types.InlineKeyboardButton(text="👥 ALL USERS",
                callback_data="cedit:reply:btn_all_users",
                style=btn_style("btn_all_users", "success")))
        kb.row(
            types.InlineKeyboardButton(text="🔑 MANAGE KEYS",
                callback_data="cedit:reply:btn_manage_keys",
                style=btn_style("btn_manage_keys", "primary")),
            types.InlineKeyboardButton(text="🎨 SET CUSTOM EMOJI",
                callback_data="cedit:reply:btn_custom_emoji",
                style=btn_style("btn_custom_emoji", "primary")))
        kb.row(
            types.InlineKeyboardButton(text="🎨 CUSTOM COLOR",
                callback_data="cedit:reply:btn_custom_color",
                style=btn_style("btn_custom_color", "primary")),
            types.InlineKeyboardButton(text="🎭 EMOJI ON/OFF",
                callback_data="cedit:reply:btn_emoji_toggle",
                style=btn_style("btn_emoji_toggle", "success")))
        kb.row(
            types.InlineKeyboardButton(text="🔍 SEARCH USER",
                callback_data="cedit:reply:btn_search_user",
                style=btn_style("btn_search_user", "primary")),
            types.InlineKeyboardButton(text="⚙️ SYSTEM",
                callback_data="cedit:reply:btn_system",
                style=btn_style("btn_system", "primary")))
        kb.row(
            types.InlineKeyboardButton(text="👑 SET ADMIN",
                callback_data="cedit:reply:btn_set_admin",
                style=btn_style("btn_set_admin", "primary")),
            types.InlineKeyboardButton(text="🔙 BACK TO BOT",
                callback_data="cedit:reply:btn_back_to_bot",
                style=btn_style("btn_back_to_bot", "danger")))
    kb.row(types.InlineKeyboardButton(text=get_label("btn_back", "🔙 BACK"),
        callback_data="cpv:back", style="danger",
        icon_custom_emoji_id=btn_eid("no")))
    header = pem(
        f"📋 <b>{'INLINE' if kind=='inline' else 'REPLY'} KEYBOARD COLORS</b>\n\n"
        f"👆 ট্যাপ করে কালার এডিট করো 👇")
    if message_id:
        try:
            bot.edit_message_text(header, chat_id=chat_id, message_id=message_id,
                                  parse_mode="HTML", reply_markup=kb)
            return
        except: pass
    bot.send_message(chat_id, header, parse_mode="HTML", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "cpv:back")
def cb_cpv_back(call):
    if not is_admin(call.message.chat.id): return
    color_preview_main(call.message.chat.id, call.message.message_id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("cedit:"))
def cb_cedit(call):
    if not is_admin(call.message.chat.id): return
    _, kind, btn_key = call.data.split(":", 2)
    current = BUTTON_COLORS.get(btn_key)
    cur_emoji = {"primary": "🔵", "success": "🟢", "danger": "🔴", None: "⬜"}.get(current, "⬜")
    label = ALL_BUTTONS.get(btn_key, btn_key)
    text = pem(
        f"🎨 <b>SET COLOR</b>\n\n"
        f"🔖 বাটন: <code>{label}</code>\n"
        f"📊 বর্তমান: {cur_emoji} <code>{current or 'Default'}</code>\n\n"
        f"কালার সিলেক্ট করো:")
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton(text="🔵 Primary",
            callback_data=f"cset:{kind}:{btn_key}:primary", style="primary"),
        types.InlineKeyboardButton(text="🟢 Success",
            callback_data=f"cset:{kind}:{btn_key}:success", style="success"))
    kb.add(
        types.InlineKeyboardButton(text="🔴 Danger",
            callback_data=f"cset:{kind}:{btn_key}:danger", style="danger"),
        types.InlineKeyboardButton(text="⬜ Default",
            callback_data=f"cset:{kind}:{btn_key}:none"))
    kb.row(types.InlineKeyboardButton(text=get_label("btn_back", "🔙 BACK"),
        callback_data=f"cedit:back:{kind}:{btn_key}",
        style="danger", icon_custom_emoji_id=btn_eid("no")))
    try:
        bot.edit_message_text(text, chat_id=call.message.chat.id,
                              message_id=call.message.message_id,
                              parse_mode="HTML", reply_markup=kb)
    except: pass

@bot.callback_query_handler(func=lambda c: c.data.startswith("cedit:back:"))
def cb_cedit_back(call):
    if not is_admin(call.message.chat.id): return
    kind = call.data.split(":")[2]
    try: bot.delete_message(call.message.chat.id, call.message.message_id)
    except: pass
    send_color_preview(call.message.chat.id, kind)

@bot.callback_query_handler(func=lambda c: c.data.startswith("cset:"))
def cb_cset(call):
    if not is_admin(call.message.chat.id): return
    _, kind, btn_key, color = call.data.split(":", 3)
    if color == "none":
        BUTTON_COLORS.pop(btn_key, None)
    else:
        BUTTON_COLORS[btn_key] = color
    save_json(COLOR_SAVE_FILE, BUTTON_COLORS)
    bot.answer_callback_query(call.id, f"✅ {btn_key} → {color}")
    try: bot.delete_message(call.message.chat.id, call.message.message_id)
    except: pass
    send_color_preview(call.message.chat.id, kind)

# ==========================================================
#           👑 SET ADMIN
# ==========================================================
def admin_system_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton(text="👥 ACTIVE ADMINS",
        callback_data="adm_list", style="primary"))
    kb.add(types.InlineKeyboardButton(text="➕ CREATE NEW ADMIN",
        callback_data="adm_create", style="success"))
    kb.row(types.InlineKeyboardButton(text=get_label("btn_back", "🔙 BACK"),
        callback_data="admin_back", style="danger",
        icon_custom_emoji_id=btn_eid("no")))
    return kb

@bot.message_handler(func=lambda m: m.text in [
    "👑 SET ADMIN", get_label("btn_set_admin", "👑 SET ADMIN")
] and is_admin(m.chat.id))
def admin_set_admin(msg):
    if msg.chat.id != ADMIN_ID:
        bot.reply_to(msg, "❌ Only OWNER can manage admins!")
        return
    text = pem(
        f"╔══════════════════╗\n   👑 <b>ADMIN SYSTEM</b>\n╚══════════════════╝\n\n"
        f"👤 <b>Owner:</b> <code>{ADMIN_ID}</code>\n"
        f"👥 <b>Extra Admins:</b> <code>{len(EXTRA_ADMINS)}</code>\n\n"
        f"⚙️ অপশন সিলেক্ট করো:")
    bot.send_message(msg.chat.id, text, parse_mode="HTML",
                     reply_markup=admin_system_keyboard())

@bot.callback_query_handler(func=lambda c: c.data == "adm_list")
def cb_adm_list(call):
    if call.message.chat.id != ADMIN_ID: return
    if not EXTRA_ADMINS:
        text = pem(f"👥 <b>ACTIVE ADMINS</b>\n\n❌ কোনো extra admin নেই।")
        kb = types.InlineKeyboardMarkup()
        kb.row(types.InlineKeyboardButton(text=get_label("btn_back", "🔙 BACK"),
            callback_data="adm_menu", style="danger",
            icon_custom_emoji_id=btn_eid("no")))
        try:
            bot.edit_message_text(text, chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="HTML", reply_markup=kb)
        except: pass
        return
    kb = types.InlineKeyboardMarkup(row_width=1)
    for uid, info in EXTRA_ADMINS.items():
        active = info.get("active", True)
        icon = "🟢" if active else "🔴"
        name = info.get("name", "Admin")
        kb.add(types.InlineKeyboardButton(
            text=f"{icon} {name}  │  {uid}",
            callback_data=f"adm_view:{uid}"))
    kb.row(types.InlineKeyboardButton(text=get_label("btn_back", "🔙 BACK"),
        callback_data="adm_menu", style="danger",
        icon_custom_emoji_id=btn_eid("no")))
    text = pem(f"👥 <b>ACTIVE ADMINS</b>\n\nTotal: <code>{len(EXTRA_ADMINS)}</code>\n\n🟢 Active | 🔴 Disabled")
    try:
        bot.edit_message_text(text, chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML", reply_markup=kb)
    except: pass

@bot.callback_query_handler(func=lambda c: c.data == "adm_menu")
def cb_adm_menu(call):
    if call.message.chat.id != ADMIN_ID: return
    text = pem(
        f"╔══════════════════╗\n   👑 <b>ADMIN SYSTEM</b>\n╚══════════════════╝\n\n"
        f"👤 <b>Owner:</b> <code>{ADMIN_ID}</code>\n"
        f"👥 <b>Extra:</b> <code>{len(EXTRA_ADMINS)}</code>")
    try:
        bot.edit_message_text(text, chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML", reply_markup=admin_system_keyboard())
    except: pass

@bot.callback_query_handler(func=lambda c: c.data.startswith("adm_view:"))
def cb_adm_view(call):
    if call.message.chat.id != ADMIN_ID: return
    uid = call.data.split(":", 1)[1]
    info = EXTRA_ADMINS.get(uid)
    if not info:
        bot.answer_callback_query(call.id, "❌ Not found!")
        return
    active = info.get("active", True)
    user_db = db_get_user(int(uid)) or {}
    name = info.get("name", "Admin")
    added = info.get("added", "N/A")
    text = pem(
        f"👤 <b>ADMIN DETAILS</b>\n\n"
        f"🆔 <b>User ID:</b> <code>{uid}</code>\n"
        f"📝 <b>Name:</b> <code>{name}</code>\n"
        f"📊 <b>Status:</b> <code>{'🟢 Active' if active else '🔴 Disabled'}</code>\n"
        f"📅 <b>Added:</b> <code>{added}</code>\n\n"
        f"💰 <b>Balance:</b> <code>৳{user_db.get('balance', 0)}</code>\n"
        f"📈 <b>OTP:</b> <code>{user_db.get('total_otp', 0)}</code>")
    kb = types.InlineKeyboardMarkup(row_width=2)
    if active:
        kb.add(types.InlineKeyboardButton(text="🔴 DISABLE",
            callback_data=f"adm_disable:{uid}", style="danger"))
    else:
        kb.add(types.InlineKeyboardButton(text="🟢 ENABLE",
            callback_data=f"adm_enable:{uid}", style="success"))
    kb.add(types.InlineKeyboardButton(text="🗑 REMOVE",
        callback_data=f"adm_remove:{uid}", style="danger"))
    kb.row(types.InlineKeyboardButton(text=get_label("btn_back", "🔙 BACK"),
        callback_data="adm_list", style="danger",
        icon_custom_emoji_id=btn_eid("no")))
    try:
        bot.edit_message_text(text, chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML", reply_markup=kb)
    except: pass

@bot.callback_query_handler(func=lambda c: c.data.startswith("adm_disable:"))
def cb_adm_disable(call):
    if call.message.chat.id != ADMIN_ID: return
    uid = call.data.split(":", 1)[1]
    if uid in EXTRA_ADMINS:
        EXTRA_ADMINS[uid]["active"] = False
        save_json(ADMIN_SAVE_FILE, EXTRA_ADMINS)
        fb_set("extra_admins", EXTRA_ADMINS)
    bot.answer_callback_query(call.id, "🔴 Disabled!")
    cb_adm_view(call)

@bot.callback_query_handler(func=lambda c: c.data.startswith("adm_enable:"))
def cb_adm_enable(call):
    if call.message.chat.id != ADMIN_ID: return
    uid = call.data.split(":", 1)[1]
    if uid in EXTRA_ADMINS:
        EXTRA_ADMINS[uid]["active"] = True
        save_json(ADMIN_SAVE_FILE, EXTRA_ADMINS)
        fb_set("extra_admins", EXTRA_ADMINS)
    bot.answer_callback_query(call.id, "🟢 Enabled!")
    cb_adm_view(call)

@bot.callback_query_handler(func=lambda c: c.data.startswith("adm_remove:"))
def cb_adm_remove(call):
    if call.message.chat.id != ADMIN_ID: return
    uid = call.data.split(":", 1)[1]
    if uid in EXTRA_ADMINS:
        del EXTRA_ADMINS[uid]
        save_json(ADMIN_SAVE_FILE, EXTRA_ADMINS)
        fb_set("extra_admins", EXTRA_ADMINS)
    bot.answer_callback_query(call.id, "🗑 Removed!")
    cb_adm_list(call)

@bot.callback_query_handler(func=lambda c: c.data == "adm_create")
def cb_adm_create(call):
    if call.message.chat.id != ADMIN_ID: return
    msg = bot.send_message(call.message.chat.id,
        pem(f"➕ <b>CREATE NEW ADMIN</b>\n\n📝 User ID পাঠাও:"),
        parse_mode="HTML")
    bot.register_next_step_handler(msg, adm_create_get_id)

def adm_create_get_id(msg):
    if msg.chat.id != ADMIN_ID: return
    try:
        uid = int(msg.text.strip())
    except:
        bot.send_message(msg.chat.id, "❌ Invalid ID!")
        return
    if uid == ADMIN_ID:
        bot.send_message(msg.chat.id, "❌ Owner already admin!")
        return
    user_db = db_get_user(uid) or {}
    name = user_db.get("username") or user_db.get("first_name") or f"User_{uid}"
    text = pem(
        f"👤 <b>USER DETAILS</b>\n\n"
        f"🆔 <b>ID:</b> <code>{uid}</code>\n"
        f"📝 <b>Name:</b> <code>{name}</code>\n"
        f"💰 <b>Balance:</b> <code>৳{user_db.get('balance', 0)}</code>\n"
        f"📈 <b>OTP:</b> <code>{user_db.get('total_otp', 0)}</code>\n"
        f"📅 <b>Joined:</b> <code>{user_db.get('joined', 'N/A')}</code>\n\n"
        f"⚠️ এই ইউজারকে admin বানাতে চাও?")
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton(text="✅ CONFIRM",
            callback_data=f"adm_do_add:{uid}", style="success"),
        types.InlineKeyboardButton(text="❌ CANCEL",
            callback_data="adm_menu", style="danger"))
    bot.send_message(msg.chat.id, text, parse_mode="HTML", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("adm_do_add:"))
def cb_adm_do_add(call):
    if call.message.chat.id != ADMIN_ID: return
    uid = call.data.split(":", 1)[1]
    EXTRA_ADMINS[uid] = {
        "name": f"Admin_{uid}",
        "active": True,
        "added": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    save_json(ADMIN_SAVE_FILE, EXTRA_ADMINS)
    fb_set("extra_admins", EXTRA_ADMINS)
    bot.answer_callback_query(call.id, "✅ Admin added!")
    cb_adm_menu(call)

# ==========================================================
#                  DEBUG COMMANDS
# ==========================================================
@bot.message_handler(commands=['debug'])
def cmd_debug(msg):
    if not is_admin(msg.chat.id): return
    lines = [pem("🔍 <b>BOT STATE DEBUG</b>\n")]
    with lock:
        lines.append(f"📊 <b>number_owner:</b> {len(number_owner)}")
        for n, info in list(number_owner.items())[:10]:
            lines.append(f"  📱 <code>{n}</code>")
            lines.append(f"     users={info['users']}")
            lines.append(f"     service={info['service']}")
            lines.append(f"     panel={info['panel']}")
        lines.append(f"\n📊 <b>processed_ids:</b> {len(processed_ids)}")
        lines.append(f"📊 <b>group_seen:</b> {len(group_seen)}")
        lines.append(f"📊 <b>OTP_NUMBER_MAP:</b> {len(OTP_NUMBER_MAP)}")
        lines.append(f"📊 <b>CUSTOM_EMOJI:</b> {len(CUSTOM_EMOJI)}")
        lines.append(f"📊 <b>BUTTON_COLORS:</b> {len(BUTTON_COLORS)}")
        lines.append(f"📊 <b>CUSTOM_LABELS:</b> {len(CUSTOM_LABELS)}")
        lines.append(f"📊 <b>CHANGE_COOLDOWN:</b> {len(CHANGE_COOLDOWN)}")
    bot.send_message(msg.chat.id, "\n".join(lines), parse_mode="HTML")

@bot.message_handler(commands=['stats'])
def cmd_stats(msg):
    if not check_must_join(msg.chat.id):
        send_join_message(msg.chat.id)
        return
    user = db_get_user(msg.chat.id)
    history = fb_get(f"otp_history/{msg.chat.id}") or {}
    text = pem(
        f"📊 <b>YOUR STATS</b>\n\n"
        f"💰 <b>Balance:</b> <code>৳{user.get('balance', 0.0)}</code>\n"
        f"💵 <b>Refer Balance:</b> <code>৳{user.get('refer_balance', 0.0)}</code>\n"
        f"📈 <b>Total OTP:</b> <code>{user.get('total_otp', 0)}</code>\n"
        f"📅 <b>Today OTP:</b> <code>{user.get('today_otp', 0)}</code>\n"
        f"👥 <b>Referrals:</b> <code>{user.get('total_refer', 0)}</code>\n"
        f"📜 <b>History Count:</b> <code>{len(history)}</code>")
    bot.send_message(msg.chat.id, text, parse_mode="HTML")

# ================== SET PREFIX (User) ==================
@bot.callback_query_handler(func=lambda c: c.data.startswith("show_prefix:"))
def cb_show_prefix(call):
    if not check_must_join(call.message.chat.id):
        bot.answer_callback_query(call.id, "⚠️ Please join first!", show_alert=True)
        send_join_message(call.message.chat.id)
        return
        
    parts = call.data.split(":")
    panel, svc = parts[1], parts[2]
    
    ranges = zenex_get_ranges(svc)
    if not ranges:
        bot.answer_callback_query(call.id, "❌ No range found!", show_alert=True)
        return

    bot.answer_callback_query(call.id)

    u = get_user(call.message.chat.id)
    current_prefix = u.get("prefix", "")

    medals = ["🥇", "🥈", "🥉"]
    color_styles = ["success", "primary", "primary", None, None]

    lines = [pem(
        f"╔══════════════════════╗\n"
        f"   📡 <b>{svc.upper()} — RANGES</b>\n"
        f"╚══════════════════════╝\n\n"
        f"🔥 <b>Hit Count দেখে range বেছে নাও!</b>\n"
        f"👆 ক্লিক করলেই ওই range এ নাম্বার আসবে\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
    )]

    for i, r in enumerate(ranges[:15], 1):
        rank = medals[i-1] if i <= 3 else f"{i:>2}."
        is_active = "  ✅ <b>ACTIVE</b>" if r["range"] == current_prefix else ""
        lines.append(
            f"{rank} <code>{r['range']}</code>  │  🔥 <b>{r['hits']}</b>  │  🏷 {r.get('tag','')}{is_active}")

    if current_prefix:
        lines.append(f"\n📡 <b>Current:</b> <code>{current_prefix}</code>")
    else:
        lines.append(f"\n📡 <b>Current:</b> Auto (Best Range)")

    kb = types.InlineKeyboardMarkup(row_width=1)
    for i, r in enumerate(ranges[:15], 1):
        style = color_styles[i-1] if i <= len(color_styles) else None
        rank = medals[i-1] if i <= 3 else f"{i}."
        active_mark = " ✅" if r["range"] == current_prefix else ""
        kb.add(types.InlineKeyboardButton(
            text=f"{rank} {r['range']}  🔥{r['hits']}{active_mark}",
            callback_data=f"user_setpfx:{panel}:{svc}:{r['range']}",
            style=style,
            icon_custom_emoji_id=btn_eid("pin")))

    if current_prefix:
        kb.row(types.InlineKeyboardButton(
            text="🗑 REMOVE RANGE (Auto)",
            callback_data=f"user_rmpfx:{panel}:{svc}",
            style="danger",
            icon_custom_emoji_id=btn_eid("no")))

    kb.row(types.InlineKeyboardButton(
        text="🔙 BACK",
        callback_data=f"back_to_numbers:{panel}:{svc}",
        style="danger",
        icon_custom_emoji_id=btn_eid("no")))

    try:
        bot.edit_message_text(
            "\n".join(lines),
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML",
            reply_markup=kb)
    except: pass

@bot.callback_query_handler(func=lambda c: c.data.startswith("user_setpfx:"))
def cb_user_setpfx(call):
    if not check_must_join(call.message.chat.id):
        bot.answer_callback_query(call.id, "⚠️ Please join first!", show_alert=True)
        send_join_message(call.message.chat.id)
        return
    parts = call.data.split(":", 3)
    panel, svc, prefix = parts[1], parts[2], parts[3]
    get_user(call.message.chat.id)["prefix"] = prefix
    bot.answer_callback_query(call.id, f"✅ Prefix set: {prefix}")
    try:
        bot.edit_message_text(
            pem(f"⏳ <b>Getting numbers for</b> <code>{prefix}</code>..."),
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML")
    except: pass
    fetch_and_show(call.message.chat.id, call.message.message_id, panel, svc)


@bot.callback_query_handler(func=lambda c: c.data.startswith("user_rmpfx:"))
def cb_user_rmpfx(call):
    parts = call.data.split(":", 2)
    panel, svc = parts[1], parts[2]
    get_user(call.message.chat.id)["prefix"] = None
    bot.answer_callback_query(call.id, "✅ Prefix removed! Auto mode on.")
    try:
        bot.edit_message_text(
            pem(f"⏳ <b>Auto range এ নাম্বার আনছি...</b>"),
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML")
    except: pass
    fetch_and_show(call.message.chat.id, call.message.message_id, panel, svc)


@bot.callback_query_handler(func=lambda c: c.data.startswith("back_to_numbers:"))
def cb_back_to_numbers(call):
    parts = call.data.split(":", 2)
    panel, svc = parts[1], parts[2]
    bot.answer_callback_query(call.id)
    try:
        bot.edit_message_text(
            pem(f"⏳ <b>{svc.upper()}</b> — Getting numbers..."),
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML")
    except: pass
    fetch_and_show(call.message.chat.id, call.message.message_id, panel, svc)


# ==========================================================
#                  WATCHDOG + BOT RUN
# ==========================================================
def watchdog():
    while True:
        time.sleep(300)
        try:
            bot.get_me()
            print("[WATCHDOG] ✅ Bot alive")
        except Exception as e:
            print(f"[WATCHDOG] ⚠️ Bot seems down: {e}")



# ================== FLASK HTTP SERVER (Render এর জন্য) ==================
import os as _os
try:
    from flask import Flask as _Flask
    _flask_app = _Flask(__name__)
    
    @_flask_app.route("/")
    def _home():
        return "✅ SUPER OTP WORK Bot is running!"
    
    @_flask_app.route("/health")
    def _health():
        return "OK"
    
    def _run_flask():
        port = int(_os.environ.get("PORT", 10000))
        _flask_app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
    
    _flask_thread = threading.Thread(target=_run_flask, daemon=True)
    _flask_thread.start()
    print("[FLASK] ✅ HTTP Server started on port " + str(_os.environ.get("PORT", 5000)))
except Exception as e:
    print(f"[FLASK] ⚠️ Flask error: {e}")


if __name__ == "__main__":
    print("=" * 60)
    print("🚀 ZENEX OTP Bot v18.0 PRO EDITION")
    print("=" * 60)

    try:
        fb_admins = fb_get("extra_admins")
        if fb_admins and isinstance(fb_admins, dict):
            EXTRA_ADMINS.update(fb_admins)
            print(f"[MAIN] ✅ Firebase থেকে {len(fb_admins)} admin loaded")
    except Exception as e:
        print(f"[MAIN] ⚠️ Firebase admin load error: {e}")

    print(f"📢 Group ID       : {OTP_GROUP_ID}")
    print(f"👤 Owner ID       : {ADMIN_ID}")
    print(f"⚡ Speed Mode     : {settings['speed_mode']}")
    print(f"🎨 Custom Emojis  : {len(CUSTOM_EMOJI)}")
    print(f"🎨 Custom Colors  : {len(BUTTON_COLORS)}")
    print(f"📝 Custom Labels  : {len(CUSTOM_LABELS)}")
    print(f"👑 Extra Admins   : {len(EXTRA_ADMINS)}")
    print(f"🎭 Emoji Premium  : {'ON' if EMOJI_ON else 'OFF'}")
    print(f"🎭 Emoji Free     : {'ON' if FREE_EMOJI_ON else 'OFF'}")
    print(f"💸 Withdraw       : {'ON' if settings['withdraw_on'] else 'OFF'}")
    print(f"📢 Must Join      : {'ON' if settings['must_join_enabled'] else 'OFF'}")
    print(f"💳 Payment Channel: {settings.get('payment_channel_id') or 'Not Set'}")
    print(f"👥 Refer          : {'ON' if settings['refer_enabled'] else 'OFF'}")
    print(f"🏆 Leaderboard    : {'ON' if settings['top_reward_enabled'] else 'OFF'}")
    print(f"⏱ Change Cooldown : {settings.get('change_cooldown_seconds', 10)}s")
    print(f"🔑 Zenex Keys     : {len(settings['zenex_keys'])}")
    print(f"🔑 Stex Keys      : {len(settings['stex_keys'])}")
    print(f"🔑 Voltx Keys     : {len(settings['voltx_keys'])}")
    print(f"🌐 SL Virtual Keys: {len(settings['slvirtual_keys'])}")
    print("=" * 60)

    check_bot_premium()
    print(f"🎯 Emoji Mode : {'🎨 PREMIUM' if PREMIUM_STATE['is_premium'] else '⚪ FREE'}")
    print("=" * 60)

    processed_ids.clear()
    group_seen.clear()
    OTP_NUMBER_MAP.clear()
    print("[MAIN] ✅ RAM cache cleared")
    print("[MAIN] ✅ API number-field filter is ON")
    print("[MAIN] ✅ CHANGE cooldown active")
    print("[MAIN] ✅ MUST JOIN + PAYMENT CHANNEL ready")

    watcher_thread = threading.Thread(target=global_otp_watcher, daemon=True)
    watcher_thread.start()
    print("[MAIN] ✅ OTP Watcher thread started")

    watchdog_thread = threading.Thread(target=watchdog, daemon=True)
    watchdog_thread.start()
    print("[MAIN] ✅ Watchdog thread started")

    print("[MAIN] ✅ Bot is now polling...")
    print("=" * 60)

    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except KeyboardInterrupt:
            print("\n[MAIN] 🛑 Bot stopped by user")
            break
        except Exception as e:
            print(f"\n[MAIN] ❌ Error: {e}")
            print("[MAIN] 🔄 Restarting in 5 seconds...")
            time.sleep(5)

print("[PART 5/5] ✅ Loaded EMOJI CONTROL + CUSTOM + SET ADMIN + BOT RUN")












def cb_new_country(call):
    parts = call.data.split(":")
    svc, country_code = parts[1], parts[2]
    get_user(call.message.chat.id)["slv_country"] = country_code
    
    bot.answer_callback_query(call.id, "⏳ Getting numbers...")
    try:
        bot.edit_message_text(
            pem(f"⏳ <b>Getting number for {country_code.upper()}...</b>"),
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML")
    except: pass
    
    # সরাসরি নাম্বার আনতে পাঠানো (রেঞ্জ ছাড়া)
    fetch_and_show(call.message.chat.id, call.message.message_id, "slvirtual", svc, country_code)




@bot.callback_query_handler(func=lambda c: c.data.startswith("back_ranges:"))
def cb_back_to_ranges(call):
    parts = call.data.split(":")
    svc = parts[1]
    country_code = parts[2]
    
    bot.answer_callback_query(call.id, "⏳ Loading Ranges...")
    
    # user এর state সেভ করা
    u = get_user(call.message.chat.id)
    u["service"] = svc
    u["slv_country"] = country_code
    
    # রেঞ্জ লিস্ট দেখানোর ফাংশন কল করা
    show_slvirtual_ranges(call.message.chat.id, call.message.message_id, svc, country_code)

@bot.callback_query_handler(func=lambda c: c.data.startswith("traffic_getnum:"))
def cb_traffic_getnum(call):
    parts = call.data.split(":")
    svc_filter = parts[1]
    pfx = parts[2]
    
    bot.answer_callback_query(call.id, "⏳ Getting number...")
    try:
        bot.edit_message_text(
            pem(f"⏳ <b>Getting number for {pfx}...</b>"),
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML")
    except: pass
    
    # SL Virtual নাকি Zenex সেটা বের করা
    if len(pfx) >= 5: # SL Virtual এর প্রিফিক্স সাধারণত ৩-৪ ডিজিটের হয়, তবে ফুল নাম্বারের ক্ষেত্রে
        # এখানে সরাসরি fetch_and_show কল করা (এটা SL VIRTUAL ধরে নিচ্ছি)
        fetch_and_show(call.message.chat.id, call.message.message_id, "slvirtual", svc_filter, "ET", pfx)
    else:
        # ZENEX এর জন্য
        fetch_and_show(call.message.chat.id, call.message.message_id, "zenex", svc_filter, "", pfx)



@bot.callback_query_handler(func=lambda c: c.data == "back_to_slv_countries")
def cb_back_to_countries(call):
    bot.answer_callback_query(call.id, "⏳ Loading...")
    show_slvirtual_countries(call.message.chat.id, call.message.message_id, "any (all services)")



# ================== SL VIRTUAL SMART HANDLERS ==================
def show_slvirtual_ranges(chat_id, message_id, svc, country_code):
    try:
        print(f"\n[DEBUG] Fetching ranges for {country_code}...\n")
        
        countries = slvirtual_get_countries(svc)
        prefix_to_use = None
        
        for c in countries:
            if c.get("countryCode", "").upper() == country_code.upper():
                prefix_to_use = c.get("prefix")
                break
                
        if not prefix_to_use:
            try:
                kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton(
                    text="🔙 BACK", callback_data="back_main", style="danger"))
                bot.edit_message_text("❌ No ranges found for this country.", chat_id=chat_id, message_id=message_id, reply_markup=kb)
            except: pass
            return

        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.add(types.InlineKeyboardButton(
            text=f"📡 RANGE: {prefix_to_use}",
            callback_data=f"slv_getnum:{svc}:{country_code}:{prefix_to_use}",
            style="success"))
            
        kb.row(types.InlineKeyboardButton(
            text="🔙 BACK TO COUNTRIES", callback_data=f"sc:{svc}:{country_code}", style="danger"))

        text = pem(
            f"╔══════════════════════╗\n"
            f"   📡 <b>ACTIVE RANGES</b>\n"
            f"╚══════════════════════╝\n\n"
            f"🌐 <b>Country:</b> <code>{country_code.upper()}</code>\n"
            f"👇 যেকোনো রেঞ্জ সিলেক্ট করুন:")

        print(f"[DEBUG] Editing message with range {prefix_to_use}...\n")
        bot.edit_message_text(text, chat_id=chat_id,
            message_id=message_id,
            parse_mode="HTML", reply_markup=kb)
    except Exception as e:
        print(f"\n[RANGE ERR] {e}\n")
        bot.send_message(chat_id, f"❌ Range Error: {e}")

def fetch_and_show(chat_id, message_id, panel, svc, country_code="", range_prefix=""):
    try:
        numbers = []
        
        if panel == "zenex":
            ranges = zenex_get_ranges(svc)
            u = get_user(chat_id)
            user_prefix = u.get("prefix")
            valid_prefixes = [r["range"] for r in ranges]
            if user_prefix and user_prefix in valid_prefixes:
                prefix = user_prefix
            else:
                u["prefix"] = None
                prefix = ranges[0]["range"] if ranges else None
                
            if not prefix:
                bot.edit_message_text(pem("❌ <b>No range found for this service!</b>"),
                    chat_id=chat_id, message_id=message_id, parse_mode="HTML")
                return
                
            get_user(chat_id)["prefix"] = prefix
            with ThreadPoolExecutor(max_workers=3) as ex:
                results = list(ex.map(lambda _: zenex_get_number(prefix), range(3)))
            numbers = [n for n in results if n]

        elif panel in ["stex", "voltx"]:
            for _ in range(3):
                n = stex_get_number(svc) if panel == "stex" else voltx_get_number(svc)
                if n: numbers.append(n)
                time.sleep(0.3)
                
        elif panel == "slvirtual":
            if not country_code:
                country_code = get_user(chat_id).get("slv_country", "ET")
                
            countries = slvirtual_get_countries(svc)
            tag_to_use = None
            prefix_from_api = range_prefix
            
            for c in countries:
                if c.get("countryCode", "").upper() == country_code.upper():
                    tags = c.get("tags", [])
                    if tags: tag_to_use = tags[0] 
                    if not prefix_from_api:
                        prefix_from_api = c.get("prefix")
                    break
                    
            print(f"\n[SLVIRTUAL] Requesting {svc.upper()} for {country_code.upper()} - Range: {prefix_from_api} - Tag: {tag_to_use}\n")
                    
            for _ in range(3):
                try:
                    result = slvirtual_get_number(svc, country_code, tag_to_use, prefix_from_api)
                    if result and result.get("number"):
                        num = result["number"]
                        numbers.append(num)
                        SLVIRTUAL_RENTALS[num] = result.get("rentalId")
                except Exception as e:
                    print(f"\n[SLVIRTUAL] ❌ Error: {e}\n")
                time.sleep(0.4)

        if not numbers:
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton(
                text="🔙 BACK TO RANGES", callback_data=f"back_ranges:{svc}:{country_code}", 
                style="danger", icon_custom_emoji_id=btn_eid("no")))
                    
            bot.edit_message_text(
                pem(f"❌ <b>NO NUMBERS AVAILABLE!</b>\n\n"
                    f"⚠️ এই রেঞ্জে এই মুহূর্তে কোনো নাম্বার স্টকে নেই।\n"
                    f"অনুগ্রহ করে অন্য রেঞ্জ সিলেক্ট করুন।"),
                chat_id=chat_id, message_id=message_id,
                parse_mode="HTML", reply_markup=kb)
            return

        get_user(chat_id)["numbers"] = numbers
        assign_numbers(chat_id, svc, numbers, panel)

        import phonenumbers
        from phonenumbers import geocoder
        import pycountry
        
        u = get_user(chat_id)
        active_prefix = u.get("prefix", "") or range_prefix or ""
        
        prefix_display = ""
        if active_prefix:
            flag, c_name, c_code = "🌐", "GLOBAL", ""
            try:
                test_num = "+" + re.sub(r'[^0-9]', '', str(active_prefix))
                parsed = phonenumbers.parse(test_num, None)
                region = geocoder.region_code_for_number(parsed)
                if region:
                    country_obj = pycountry.countries.get(alpha_2=region)
                    c_name = country_obj.name.upper() if country_obj else geocoder.description_for_number(parsed, "en").upper()
                    c_code = region
                    flag = "".join(chr(ord(c) + 127397) for c in region.upper())
            except: pass
            
            prefix_display = f"\n📡 <b>Prefix:</b> <code>{flag} {c_name} ({c_code}) ({active_prefix})</code>"
        
        text = pem(
            f"╔══════════════════╗\n  📱 <b>{svc.upper()}</b>\n╚══════════════════╝\n\n"
            f"✅ <b>3 Numbers Ready!</b>{prefix_display}\n"
            f"👆 Tap number to copy!\n🟢 OTP Watcher: <b>ACTIVE</b>")
            
        bot.edit_message_text(text, chat_id=chat_id, message_id=message_id,
                              parse_mode="HTML",
                              reply_markup=numbers_keyboard(svc, numbers, panel, country_code))
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        bot.send_message(chat_id, f"❌ <b>FETCH ERROR:</b>\n<code>{e}</code>", parse_mode="HTML")

@bot.callback_query_handler(func=lambda c: c.data.startswith("back_ranges:"))
def cb_back_ranges(call):
    parts = call.data.split(":")
    svc, country_code = parts[1], parts[2]
    bot.answer_callback_query(call.id, "⏳ Loading...")
    show_slvirtual_ranges(call.message.chat.id, call.message.message_id, svc, country_code)



@bot.callback_query_handler(func=lambda c: c.data.startswith("slv_getnum:"))
def cb_slv_getnum(call):
    try:
        parts = call.data.split(":")
        svc, country_code, range_prefix = parts[1], parts[2].upper(), parts[3]
        
        bot.answer_callback_query(call.id, "⏳ Getting number...")
        bot.edit_message_text(
            pem(f"⏳ <b>Getting number for {range_prefix}...</b>"),
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML")
            
        fetch_and_show(call.message.chat.id, call.message.message_id, "slvirtual", svc, country_code, range_prefix)
    except Exception as e:
        bot.send_message(call.message.chat.id, f"❌ Error: {e}")

def fetch_and_show(chat_id, message_id, panel, svc, country_code="", range_prefix=""):
    try:
        numbers = []
        
        if panel == "zenex":
            ranges = zenex_get_ranges(svc)
            u = get_user(chat_id)
            user_prefix = u.get("prefix")
            valid_prefixes = [r["range"] for r in ranges]
            if user_prefix and user_prefix in valid_prefixes:
                prefix = user_prefix
            else:
                u["prefix"] = None
                prefix = ranges[0]["range"] if ranges else None
                
            if not prefix:
                bot.edit_message_text(pem("❌ <b>No range found for this service!</b>"),
                    chat_id=chat_id, message_id=message_id, parse_mode="HTML")
                return
                
            get_user(chat_id)["prefix"] = prefix
            with ThreadPoolExecutor(max_workers=3) as ex:
                results = list(ex.map(lambda _: zenex_get_number(prefix), range(3)))
            numbers = [n for n in results if n]

        elif panel in ["stex", "voltx"]:
            for _ in range(3):
                n = stex_get_number(svc) if panel == "stex" else voltx_get_number(svc)
                if n: numbers.append(n)
                time.sleep(0.3)
                
        elif panel == "slvirtual":
            if not country_code:
                country_code = get_user(chat_id).get("slv_country", "ET")
                
            countries = slvirtual_get_countries(svc)
            tag_to_use = None
            prefix_from_api = range_prefix
            
            for c in countries:
                if c.get("countryCode", "").upper() == country_code.upper():
                    tags = c.get("tags", [])
                    if tags: tag_to_use = tags[0] 
                    if not prefix_from_api:
                        prefix_from_api = c.get("prefix")
                    break
                    
            print(f"\n[SLVIRTUAL] Requesting {svc.upper()} for {country_code.upper()} - Range: {prefix_from_api} - Tag: {tag_to_use}\n")
                    
            for _ in range(3):
                try:
                    result = slvirtual_get_number(svc, country_code, tag_to_use, prefix_from_api)
                    if result and result.get("number"):
                        num = result["number"]
                        numbers.append(num)
                        SLVIRTUAL_RENTALS[num] = result.get("rentalId")
                except Exception as e:
                    print(f"\n[SLVIRTUAL] ❌ Error: {e}\n")
                time.sleep(0.4)

        if not numbers:
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton(
                text="🔙 BACK TO RANGES", callback_data=f"back_ranges:{svc}:{country_code}", 
                style="danger", icon_custom_emoji_id=btn_eid("no")))
                    
            bot.edit_message_text(
                pem(f"❌ <b>NO NUMBERS AVAILABLE!</b>\n\n"
                    f"⚠️ এই রেঞ্জে এই মুহূর্তে কোনো নাম্বার স্টকে নেই।\n"
                    f"অনুগ্রহ করে অন্য রেঞ্জ সিলেক্ট করুন।"),
                chat_id=chat_id, message_id=message_id,
                parse_mode="HTML", reply_markup=kb)
            return

        get_user(chat_id)["numbers"] = numbers
        assign_numbers(chat_id, svc, numbers, panel)

        import phonenumbers
        from phonenumbers import geocoder
        import pycountry
        
        u = get_user(chat_id)
        active_prefix = u.get("prefix", "") or range_prefix or ""
        
        prefix_display = ""
        if active_prefix:
            flag, c_name, c_code = "🌐", "GLOBAL", ""
            try:
                test_num = "+" + re.sub(r'[^0-9]', '', str(active_prefix))
                parsed = phonenumbers.parse(test_num, None)
                region = geocoder.region_code_for_number(parsed)
                if region:
                    country_obj = pycountry.countries.get(alpha_2=region)
                    c_name = country_obj.name.upper() if country_obj else geocoder.description_for_number(parsed, "en").upper()
                    c_code = region
                    flag = "".join(chr(ord(c) + 127397) for c in region.upper())
            except: pass
            
            prefix_display = f"\n📡 <b>Prefix:</b> <code>{flag} {c_name} ({c_code}) ({active_prefix})</code>"
        
        text = pem(
            f"╔══════════════════╗\n  📱 <b>{svc.upper()}</b>\n╚══════════════════╝\n\n"
            f"✅ <b>3 Numbers Ready!</b>{prefix_display}\n"
            f"👆 Tap number to copy!\n🟢 OTP Watcher: <b>ACTIVE</b>")
            
        bot.edit_message_text(text, chat_id=chat_id, message_id=message_id,
                              parse_mode="HTML",
                              reply_markup=numbers_keyboard(svc, numbers, panel, country_code))
    except Exception as e:
        import traceback
        error_msg = traceback.format_exc()
        print(f"\n[FETCH ERROR]\n{error_msg}\n")
        bot.send_message(chat_id, f"❌ <b>FETCH ERROR:</b>\n<code>{e}</code>", parse_mode="HTML")
