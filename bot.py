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
            json.dump({"ideas": [], "history": {}, "place_history": {}}, f, ensure_ascii=False, indent=2)
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main_menu():
    markup = types.InlineKeyboardMarkup()
    markup.row(types.InlineKeyboardButton("🎲 Получить идею", callback_data="get_idea"))
    markup.row(types.InlineKeyboardButton("💡 Добавить идею", callback_data="addidea_hint"),
               types.InlineKeyboardButton("📍 Добавить место", callback_data="addplace_hint"))
    markup.row(types.InlineKeyboardButton("🗑 Удалить идею", callback_data="deleteidea_hint"),
               types.InlineKeyboardButton("🗑 Удалить место", callback_data="deleteplace_hint"))
    markup.row(types.InlineKeyboardButton("🗒 Все идеи", callback_data="list_ideas"))
    return markup


@bot.message_handler(commands=["start", "help"])
def handle_help(message):
    bot.send_message(message.chat.id,
        ("👋 Я бот для идей досуга!\n\n"
         "📌 /idea — получить случайную идею\n"
         "📌 /addidea текст — добавить идею\n"
         "📌 /addplace ID Место — добавить место к идее\n"
         "📌 /deleteidea ID — удалить идею\n"
         "📌 /deleteplace ID НомерМеста — удалить место\n"
         "📌 /listideas — показать все идеи"),
        reply_markup=main_menu()
    )


@bot.message_handler(commands=["addidea"])
def add_idea(message):
    data = load_data()
    text = message.text[9:].strip()
    if not text:
        bot.send_message(message.chat.id, "⚠️ Напиши текст идеи после /addidea")
        return
    data["ideas"].append({"id": len(data["ideas"]) + 1, "text": text, "places": []})
    save_data(data)
    bot.send_message(message.chat.id, f"✅ Идея добавлена под номером {len(data['ideas'])}")


@bot.message_handler(commands=["addplace"])
def add_place(message):
    try:
        data = load_data()
        parts = message.text.split(maxsplit=2)
        idea_id = int(parts[1]) - 1
        place = parts[2]
        if idea_id < 0 or idea_id >= len(data["ideas"]):
            bot.send_message(message.chat.id, "❌ Идея не найдена.")
            return
        data["ideas"][idea_id]["places"].append({"name": place})
        save_data(data)
        bot.send_message(message.chat.id, f"📍 Место добавлено к идее {idea_id+1}")
    except Exception as e:
        print(f"Ошибка при добавлении места: {e}")
        bot.send_message(message.chat.id, "⚠️ Формат: /addplace ID Место")


@bot.message_handler(commands=["deleteidea"])
def delete_idea(message):
    try:
        data = load_data()
        idea_id = int(message.text.split()[1])
        if 1 <= idea_id <= len(data["ideas"]):
            del data["ideas"][idea_id - 1]
            for i, idea in enumerate(data["ideas"], 1):
                idea["id"] = i
            data["history"] = {}
            data["place_history"] = {}
            save_data(data)
            bot.send_message(message.chat.id, f"🗑 Идея {idea_id} удалена и порядок обновлён.")
        else:
            bot.send_message(message.chat.id, f"❌ Идея {idea_id} не найдена.")
    except Exception as e:
        print(f"Ошибка при удалении идеи: {e}")
        bot.send_message(message.chat.id, "⚠️ Формат: /deleteidea ID")


@bot.message_handler(commands=["deleteplace"])
def delete_place(message):
    try:
        data = load_data()
        parts = message.text.split(maxsplit=2)
        idea_id = int(parts[1]) - 1
        place_idx = int(parts[2]) - 1
        if idea_id < 0 or idea_id >= len(data["ideas"]):
            bot.send_message(message.chat.id, "❌ Идея не найдена.")
            return
        if place_idx < 0 or place_idx >= len(data["ideas"][idea_id]["places"]):
            bot.send_message(message.chat.id, "❌ Место не найдено.")
            return
        removed = data["ideas"][idea_id]["places"].pop(place_idx)
        save_data(data)
        bot.send_message(message.chat.id, f"🗑 Место удалено: {removed['name']}")
    except Exception as e:
        print(f"Ошибка при удалении места: {e}")
        bot.send_message(message.chat.id, "⚠️ Формат: /deleteplace ID НомерМеста")


@bot.message_handler(commands=["listideas"])
def list_ideas(message):
    data = load_data()
    if not data["ideas"]:
        bot.send_message(message.chat.id, "📭 Идей пока нет.")
        return
    lines = []
    for idea in data["ideas"]:
        lines.append(f"**{idea['id']}. {idea['text']}**\n")
        for place in idea["places"]:
            lines.append(f"📍 {place['name']}")
        lines.append("")  # пустая строка между идеями
    full = "\n".join(lines)
    chunks = [full[i:i + 4000] for i in range(0, len(full), 4000)]
    for part in chunks:
        bot.send_message(message.chat.id, part, parse_mode="Markdown")


def send_random_idea(chat_id):
    data = load_data()
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
    response = f"**{idea['id']}. {idea['text']}**\n"

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


@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    if call.data == "get_idea":
        send_random_idea(call.message.chat.id)
    elif call.data == "list_ideas":
        list_ideas(call.message)
    elif call.data == "addidea_hint":
        bot.send_message(call.message.chat.id, "✏️ Введите:\n`/addidea Ваша идея`", parse_mode="Markdown")
    elif call.data == "addplace_hint":
        bot.send_message(call.message.chat.id, "✏️ Введите:\n`/addplace ID Место`", parse_mode="Markdown")
    elif call.data == "deleteidea_hint":
        bot.send_message(call.message.chat.id, "✏️ Введите:\n`/deleteidea ID`", parse_mode="Markdown")
    elif call.data == "deleteplace_hint":
        bot.send_message(call.message.chat.id, "✏️ Введите:\n`/deleteplace ID НомерМеста`", parse_mode="Markdown")


bot.polling()
