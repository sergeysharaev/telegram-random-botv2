import os
import json
import random
import telebot
from telebot import types

TOKEN = os.getenv("BOT_TOKEN") or "YOUR_TOKEN_HERE"
DATA_FILE = "data.json"
bot = telebot.TeleBot(TOKEN, parse_mode='Markdown')

def load_data():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump({"current_list": "default", "lists": {"default": {
                "name": "🌞 Идеи для досуга 2025 🔥",
                "ideas": [], "history": {}, "place_history": {}
            }}}, f, ensure_ascii=False, indent=2)
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

data = load_data()

def get_current_list():
    return data["lists"][data["current_list"]]

def main_menu():
    markup = types.InlineKeyboardMarkup()
    markup.row(types.InlineKeyboardButton("🎲 Получить идею", callback_data="get_idea"))
    markup.row(types.InlineKeyboardButton("💡 Добавить идею", callback_data="addidea_hint"))
    markup.row(types.InlineKeyboardButton("📍 Добавить место", callback_data="addplace_hint"))
    markup.row(types.InlineKeyboardButton("🗑 Удалить идею", callback_data="deleteidea_hint"))
    markup.row(types.InlineKeyboardButton("🗑 Удалить место", callback_data="deleteplace_hint"))
    markup.row(types.InlineKeyboardButton("📋 Сменить список", callback_data="switch_list"))
    markup.row(types.InlineKeyboardButton("🗒 Все идеи", callback_data="list_ideas"))
    return markup

@bot.message_handler(commands=["start", "help"])
def handle_start(message):
    bot.send_message(message.chat.id, "👋 Я бот для идей досуга!", reply_markup=main_menu())

@bot.message_handler(commands=["addidea"])
def add_idea(message):
    text = message.text[9:].strip()
    if not text:
        bot.reply_to(message, "⚠️ Напиши идею после /addidea")
        return
    clist = get_current_list()
    if any(i["text"].strip().lower() == text.lower() for i in clist["ideas"]):
        bot.reply_to(message, "⚠️ Такая идея уже существует.")
        return
    clist["ideas"].append({"id": len(clist["ideas"]) + 1, "text": text, "places": []})
    save_data(data)
    bot.reply_to(message, f"✅ Идея добавлена под номером {len(clist['ideas'])}")

@bot.message_handler(commands=["addplace"])
def add_place(message):
    try:
        _, idea_id, place = message.text.split(maxsplit=2)
        idea = get_current_list()["ideas"][int(idea_id) - 1]
        if any(p["name"].strip().lower() == place.lower() for p in idea["places"]):
            bot.reply_to(message, "⚠️ Это место уже добавлено к идее.")
            return
        idea["places"].append({"name": place})
        save_data(data)
        bot.reply_to(message, f"📍 Место добавлено к идее {idea_id}")
    except:
        bot.reply_to(message, "⚠️ Формат: /addplace ID Место")

@bot.message_handler(commands=["deleteidea"])
def delete_idea(message):
    try:
        idea_id = int(message.text.split()[1])
        clist = get_current_list()
        del clist["ideas"][idea_id - 1]
        for i, idea in enumerate(clist["ideas"], 1):
            idea["id"] = i
        clist["history"] = {}
        clist["place_history"] = {}
        save_data(data)
        bot.reply_to(message, f"🗑 Идея {idea_id} удалена и порядок обновлён.")
    except:
        bot.reply_to(message, "⚠️ Формат: /deleteidea ID")

@bot.message_handler(commands=["deleteplace"])
def delete_place(message):
    try:
        _, idea_id, place_idx = message.text.split()
        idea = get_current_list()["ideas"][int(idea_id) - 1]
        removed = idea["places"].pop(int(place_idx) - 1)
        save_data(data)
        bot.reply_to(message, f"🗑 Удалено место: {removed['name']}")
    except:
        bot.reply_to(message, "⚠️ Формат: /deleteplace ID НомерМеста")

@bot.message_handler(commands=["listideas"])
def list_ideas(message):
    clist = get_current_list()
    if not clist["ideas"]:
        bot.send_message(message.chat.id, "📭 Идей пока нет.")
        return
    text = f"*{data['lists'][data['current_list']]['name']}*\n\n"
    for idea in clist["ideas"]:
        text += f"{idea['id']}. {idea['text']}\n"
        for idx, place in enumerate(idea["places"], 1):
            text += f"   📍 {idx}) {place['name']}\n"
    for chunk in [text[i:i+4000] for i in range(0, len(text), 4000)]:
        bot.send_message(message.chat.id, chunk)

@bot.message_handler(commands=["idea"])
def send_random(message):
    send_random_idea(message.chat.id)

def send_random_idea(chat_id):
    cid = str(chat_id)
    clist = get_current_list()
    history = clist["history"].get(cid, [])
    available = [i for i in clist["ideas"] if i["id"] not in history]

    if not available:
        clist["history"][cid] = []
        clist["place_history"][cid] = {}
        save_data(data)
        bot.send_message(chat_id, "✅ Все идеи показаны. Начинаю заново.")
        return

    idea = random.choice(available)
    clist["history"].setdefault(cid, []).append(idea["id"])
    result = f"💡 *{idea['text']}*"

    if idea["places"]:
        p_hist = clist["place_history"].setdefault(cid, {}).setdefault(str(idea["id"]), [])
        options = [p for i, p in enumerate(idea["places"]) if i not in p_hist]
        if not options:
            p_hist.clear()
            options = idea["places"]
        place = random.choice(options)
        p_hist.append(idea["places"].index(place))
        result += f"\n📍 {place['name']}"

    save_data(data)
    bot.send_message(chat_id, result, reply_markup=main_menu())

def list_selector():
    markup = types.InlineKeyboardMarkup()
    for key, val in data["lists"].items():
        text = f"✅ {val['name']}" if key == data["current_list"] else val["name"]
        markup.row(types.InlineKeyboardButton(text, callback_data=f"setlist_{key}"))
    markup.row(types.InlineKeyboardButton("➕ Новый список", callback_data="new_list"))
    markup.row(types.InlineKeyboardButton("❌ Удалить список", callback_data="delete_list"))
    return markup

@bot.callback_query_handler(func=lambda c: True)
def handle_callback(call):
    if call.data == "get_idea": send_random_idea(call.message.chat.id)
    elif call.data == "list_ideas": list_ideas(call.message)
    elif call.data == "addidea_hint": bot.send_message(call.message.chat.id, "/addidea Ваша идея")
    elif call.data == "addplace_hint": bot.send_message(call.message.chat.id, "/addplace ID Место")
    elif call.data == "deleteidea_hint": bot.send_message(call.message.chat.id, "/deleteidea ID")
    elif call.data == "deleteplace_hint": bot.send_message(call.message.chat.id, "/deleteplace ID Номер")
    elif call.data == "switch_list": bot.send_message(call.message.chat.id, "📋 Выбери список:", reply_markup=list_selector())
    elif call.data.startswith("setlist_"):
        data["current_list"] = call.data.split("_", 1)[1]
        save_data(data)
        bot.send_message(call.message.chat.id, "✅ Список активирован.", reply_markup=main_menu())
    elif call.data == "new_list":
        msg = bot.send_message(call.message.chat.id, "✏️ Введите название нового списка:")
        bot.register_next_step_handler(msg, create_new_list)
    elif call.data == "delete_list":
        if data["current_list"] == "default":
            bot.send_message(call.message.chat.id, "❌ Нельзя удалить список по умолчанию.")
        else:
            del data["lists"][data["current_list"]]
            data["current_list"] = "default"
            save_data(data)
            bot.send_message(call.message.chat.id, "🗑 Список удалён. Возврат к 'default'.", reply_markup=main_menu())

def create_new_list(message):
    name = message.text.strip()
    key = name.lower().replace(" ", "_")[:32]
    n = 1
    base = key
    while key in data["lists"]:
        key = f"{base}_{n}"
        n += 1
    data["lists"][key] = {"name": name, "ideas": [], "history": {}, "place_history": {}}
    data["current_list"] = key
    save_data(data)
    bot.send_message(message.chat.id, f"✅ Новый список создан и активирован: *{name}*", reply_markup=main_menu())

bot.infinity_polling()
