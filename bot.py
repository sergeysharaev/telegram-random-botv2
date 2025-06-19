import telebot
import os
import json
import random
from telebot import types

TOKEN = os.getenv("BOT_TOKEN") or "YOUR_TOKEN_HERE"
DATA_FILE = "data.json"
bot = telebot.TeleBot(TOKEN)

# === Загрузка и сохранение ===

def load_data():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump({"ideas": [], "history": {}, "place_history": {}}, f, ensure_ascii=False, indent=2)
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

data = load_data()

# === Кнопки ===

def main_menu():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🎲 Получить идею", callback_data="get_idea"))
    markup.add(types.InlineKeyboardButton("➕ Добавить идею", switch_inline_query_current_chat="/addidea "))
    markup.add(types.InlineKeyboardButton("🗒 Все идеи", callback_data="list_ideas"))
    return markup

@bot.message_handler(commands=["start", "help"])
def handle_help(message):
    bot.send_message(message.chat.id,
        "👋 Я бот для идей досуга!

"
        "📌 /idea — получить случайную идею
"
        "📌 /addidea текст — добавить идею
"
        "📌 /addplace ID Место — добавить место к идее
"
        "📌 /deleteidea ID — удалить идею
"
        "📌 /deleteplace ID Место# — удалить место из идеи
"
        "📌 /listideas — показать все идеи",
        reply_markup=main_menu()
    )

# === Добавление ===

@bot.message_handler(commands=["addidea"])
def add_idea(message):
    text = message.text[9:].strip()
    if not text:
        bot.send_message(message.chat.id, "⚠️ Напиши текст идеи после /addidea")
        return
    idea_id = max([i["id"] for i in data["ideas"]], default=0) + 1
    data["ideas"].append({"id": idea_id, "text": text, "places": []})
    save_data(data)
    bot.send_message(message.chat.id, f"✅ Идея добавлена под номером {idea_id}")

@bot.message_handler(commands=["addplace"])
def add_place(message):
    try:
        parts = message.text.split(maxsplit=2)
        idea_id = int(parts[1])
        place = parts[2]
    except:
        bot.send_message(message.chat.id, "⚠️ Формат: /addplace ID Место")
        return
    for idea in data["ideas"]:
        if idea["id"] == idea_id:
            idea["places"].append({"name": place})
            save_data(data)
            bot.send_message(message.chat.id, f"💡 Место добавлено к идее {idea_id}")
            return
    bot.send_message(message.chat.id, f"❌ Идея с ID {idea_id} не найдена.")

# === Удаление ===

@bot.message_handler(commands=["deleteidea"])
def delete_idea(message):
    try:
        idea_id = int(message.text.split()[1])
    except:
        bot.send_message(message.chat.id, "⚠️ Формат: /deleteidea ID")
        return
    before = len(data["ideas"])
    data["ideas"] = [i for i in data["ideas"] if i["id"] != idea_id]
    if len(data["ideas"]) < before:
        save_data(data)
        bot.send_message(message.chat.id, f"🗑 Идея {idea_id} удалена.")
    else:
        bot.send_message(message.chat.id, f"❌ Идея с ID {idea_id} не найдена.")

@bot.message_handler(commands=["deleteplace"])
def delete_place(message):
    try:
        parts = message.text.split(maxsplit=2)
        idea_id = int(parts[1])
        place_idx = int(parts[2]) - 1
    except:
        bot.send_message(message.chat.id, "⚠️ Формат: /deleteplace ID НомерМеста")
        return
    for idea in data["ideas"]:
        if idea["id"] == idea_id:
            if 0 <= place_idx < len(idea["places"]):
                removed = idea["places"].pop(place_idx)
                save_data(data)
                bot.send_message(message.chat.id, f"🗑 Место удалено: {removed['name']}")
                return
    bot.send_message(message.chat.id, f"❌ Не удалось удалить место.")

# === Список всех идей ===

@bot.message_handler(commands=["listideas"])
def list_ideas(message):
    if not data["ideas"]:
        bot.send_message(message.chat.id, "📭 Идей пока нет.")
        return
    lines = []
    for idea in data["ideas"]:
        lines.append(f"{idea['id']}. {idea['text']}")
        for idx, place in enumerate(idea["places"], 1):
            lines.append(f"   💡 {idx}) {place['name']}")
    full = "\n".join(lines)
    if len(full) < 4000:
        bot.send_message(message.chat.id, full)
    else:
        # разбить на части
        chunks = [full[i:i+4000] for i in range(0, len(full), 4000)]
        for part in chunks:
            bot.send_message(message.chat.id, part)

# === Получение идеи ===

def send_random_idea(chat_id):
    chat_id_str = str(chat_id)
    history = data["history"].get(chat_id_str, [])
    available = [i for i in data["ideas"] if i["id"] not in history]

    if not available:
        bot.send_message(chat_id, "✅ Все идеи уже были. Обнуляю список.")
        data["history"][chat_id_str] = []
        data["place_history"][chat_id_str] = {}
        save_data(data)
        return

    idea = random.choice(available)
    data["history"].setdefault(chat_id_str, []).append(idea["id"])
    response = f"💡 *{idea['text']}*"

    if idea["places"]:
        used_places = data["place_history"].setdefault(chat_id_str, {}).setdefault(str(idea["id"]), [])
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

# === Обработка кнопок ===

@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    if call.data == "get_idea":
        send_random_idea(call.message.chat.id)
    elif call.data == "list_ideas":
        list_ideas(call.message)

bot.polling()