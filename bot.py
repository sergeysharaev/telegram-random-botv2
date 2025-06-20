import telebot
import os
import json
import random
from telebot import types

TOKEN = os.getenv("BOT_TOKEN") or "YOUR_TOKEN_HERE"
DATA_FILE = "data.json"
bot = telebot.TeleBot(TOKEN)

def load_data():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "current_list": "default",
                "lists": {
                    "default": {
                        "name": "🌞 Идеи для досуга 2025 🔥",
                        "ideas": [],
                        "history": {},
                        "place_history": {}
                    }
                }
            }, f, ensure_ascii=False, indent=2)
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

data = load_data()

def current():
    return data["lists"][data["current_list"]]

def main_menu():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton("🎲 Получить идею", callback_data="get_idea"))
    markup.add(
        types.InlineKeyboardButton("💡 Добавить идею", callback_data="addidea"),
        types.InlineKeyboardButton("📍 Добавить место", callback_data="addplace")
    )
    markup.add(
        types.InlineKeyboardButton("🗑 Удалить идею", callback_data="deleteidea"),
        types.InlineKeyboardButton("🗑 Удалить место", callback_data="deleteplace")
    )
    markup.add(
        types.InlineKeyboardButton("🗒 Все идеи", callback_data="list_ideas"),
        types.InlineKeyboardButton("◀️ Сменить список", callback_data="switchlist")
    )
    markup.add(
        types.InlineKeyboardButton("📋 Создать список", callback_data="new_list"),
        types.InlineKeyboardButton("❌ Удалить список", callback_data="delete_list")
    )
    return markup

@bot.message_handler(commands=["start", "help"])
def handle_help(message):
    bot.send_message(message.chat.id,
        f"👋 Я бот для идей досуга!\n\n"
        f"📌 Активный список: *{data['lists'][data['current_list']]['name']}*\n\n"
        "🔹 /idea — получить случайную идею\n"
        "/addidea текст — добавить идею\n"
        "/addplace ID Место — добавить место к идее\n"
        "/deleteidea ID — удалить идею\n"
        "/deleteplace ID НомерМеста — удалить место\n"
        "/listideas — показать все идеи",
        reply_markup=main_menu(), parse_mode="Markdown")

@bot.message_handler(commands=["addidea"])
def add_idea(message):
    text = message.text[9:].strip()
    if not text:
        bot.send_message(message.chat.id, "⚠️ Напиши текст идеи после /addidea")
        return
    ideas = current()["ideas"]
    ideas.append({"id": len(ideas) + 1, "text": text, "places": []})
    save_data(data)
    bot.send_message(message.chat.id, f"✅ Идея добавлена под номером {len(ideas)}")

@bot.message_handler(commands=["addplace"])
def add_place(message):
    try:
        parts = message.text.split(maxsplit=2)
        idea_id = int(parts[1]) - 1
        place = parts[2]
        ideas = current()["ideas"]
        if 0 <= idea_id < len(ideas):
            ideas[idea_id]["places"].append({"name": place})
            save_data(data)
            bot.send_message(message.chat.id, f"📍 Место добавлено к идее {idea_id + 1}")
        else:
            bot.send_message(message.chat.id, "❌ Идея с таким ID не найдена.")
    except:
        bot.send_message(message.chat.id, "⚠️ Формат: /addplace ID Место")

@bot.message_handler(commands=["deleteidea"])
def delete_idea(message):
    try:
        idea_id = int(message.text.split()[1])
        ideas = current()["ideas"]
        if 1 <= idea_id <= len(ideas):
            del ideas[idea_id - 1]
            for i, idea in enumerate(ideas, 1):
                idea["id"] = i
            current()["history"] = {}
            current()["place_history"] = {}
            save_data(data)
            bot.send_message(message.chat.id, f"🗑 Идея {idea_id} удалена и порядок обновлён.")
        else:
            bot.send_message(message.chat.id, f"❌ Идея {idea_id} не найдена.")
    except:
        bot.send_message(message.chat.id, "⚠️ Формат: /deleteidea ID")

@bot.message_handler(commands=["deleteplace"])
def delete_place(message):
    try:
        parts = message.text.split(maxsplit=2)
        idea_id = int(parts[1]) - 1
        place_idx = int(parts[2]) - 1
        ideas = current()["ideas"]
        if 0 <= idea_id < len(ideas) and 0 <= place_idx < len(ideas[idea_id]["places"]):
            removed = ideas[idea_id]["places"].pop(place_idx)
            save_data(data)
            bot.send_message(message.chat.id, f"🗑 Место удалено: {removed['name']}")
        else:
            bot.send_message(message.chat.id, "❌ Неверный ID идеи или номер места.")
    except:
        bot.send_message(message.chat.id, "⚠️ Формат: /deleteplace ID НомерМеста")

@bot.message_handler(commands=["listideas"])
def list_ideas(message):
    ideas = current()["ideas"]
    if not ideas:
        bot.send_message(message.chat.id, "📭 Идей пока нет.")
        return
    lines = []
    for idea in ideas:
        lines.append(f"{idea['id']}. {idea['text']}")
        for idx, place in enumerate(idea["places"], 1):
            lines.append(f"   📍 {idx}) {place['name']}")
    full = "\n".join(lines)
    chunks = [full[i:i+4000] for i in range(0, len(full), 4000)]
    for part in chunks:
        bot.send_message(message.chat.id, part)

def send_random_idea(chat_id):
    c = current()
    chat_id_str = str(chat_id)
    history = c["history"].get(chat_id_str, [])
    available = [i for i in c["ideas"] if i["id"] not in history]

    if not available:
        bot.send_message(chat_id, "✅ Все идеи уже были. Обнуляю список.")
        c["history"][chat_id_str] = []
        c["place_history"][chat_id_str] = {}
        save_data(data)
        return

    idea = random.choice(available)
    c["history"].setdefault(chat_id_str, []).append(idea["id"])
    response = f"📍 *{idea['text']}*"

    if idea["places"]:
        used_places = c["place_history"].setdefault(chat_id_str, {}).setdefault(str(idea["id"]), [])
        place_options = [p for idx, p in enumerate(idea["places"]) if idx not in used_places]
        if not place_options:
            used_places.clear()
            place_options = idea["places"]
        place = random.choice(place_options)
        place_index = idea["places"].index(place)
        used_places.append(place_index)
        response += f"\n📍 {place['name']}"

    save_data(data)
    bot.send_message(chat_id, response, parse_mode="Markdown", reply_markup=main_menu())

@bot.message_handler(commands=["idea"])
def handle_idea(message):
    send_random_idea(message.chat.id)

@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    if call.data == "get_idea":
        send_random_idea(call.message.chat.id)
    elif call.data == "list_ideas":
        list_ideas(call.message)
    elif call.data == "switchlist":
        markup = types.InlineKeyboardMarkup()
        for key, val in data["lists"].items():
            text = "✅ " + val["name"] if key == data["current_list"] else val["name"]
            markup.add(types.InlineKeyboardButton(text, callback_data=f"use_{key}"))
        bot.send_message(call.message.chat.id, "🔄 Выбери список:", reply_markup=markup)
    elif call.data == "new_list":
        bot.send_message(call.message.chat.id, "✏️ Введите название нового списка:")
        bot.register_next_step_handler(call.message, handle_new_list)
    elif call.data == "delete_list":
        if data["current_list"] == "default":
            bot.send_message(call.message.chat.id, "❌ Нельзя удалить список по умолчанию.")
        else:
            del data["lists"][data["current_list"]]
            data["current_list"] = "default"
            save_data(data)
            bot.send_message(call.message.chat.id, "🗑 Список удалён. Переключено на default.")
    elif call.data.startswith("use_"):
        list_key = call.data[4:]
        if list_key in data["lists"]:
            data["current_list"] = list_key
            save_data(data)
            bot.send_message(call.message.chat.id, f"✅ Переключено на список: {data['lists'][list_key]['name']}")

def handle_new_list(message):
    key = message.text.lower().replace(" ", "_")
    if key in data["lists"]:
        bot.send_message(message.chat.id, "⚠️ Список с таким ключом уже существует.")
        return
    data["lists"][key] = {
        "name": message.text,
        "ideas": [],
        "history": {},
        "place_history": {}
    }
    data["current_list"] = key
    save_data(data)
    bot.send_message(message.chat.id, f"✅ Список создан и выбран: {message.text}")

bot.polling()
