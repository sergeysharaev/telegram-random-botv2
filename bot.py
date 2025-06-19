# -*- coding: utf-8 -*-
import telebot
import os
import json
import random
from telebot import types

TOKEN = os.getenv("BOT_TOKEN") or "YOUR_TOKEN_HERE"
DATA_FILE = "data.json"
bot = telebot.TeleBot(TOKEN, parse_mode="Markdown")

# Загружаем и сохраняем JSON

def load_data():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump({"chats": {}}, f, ensure_ascii=False, indent=2)
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

data = load_data()

# Инициализация чата

def init_chat(chat_id):
    str_id = str(chat_id)
    if str_id not in data["chats"]:
        data["chats"][str_id] = {
            "lists": {},
            "current_list": None,
            "state": {}
        }

# Меню

def main_menu():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🎲 Получить идею", callback_data="get_idea")
    )
    markup.add(
        types.InlineKeyboardButton("💡 Добавить идею", callback_data="addidea"),
        types.InlineKeyboardButton("📍 Добавить место", callback_data="addplace")
    )
    markup.add(
        types.InlineKeyboardButton("🗑 Удалить идею", callback_data="deleteidea"),
        types.InlineKeyboardButton("🗑 Удалить место", callback_data="deleteplace")
    )
    markup.add(
        types.InlineKeyboardButton("🗒 Все идеи", callback_data="listideas"),
        types.InlineKeyboardButton("◀️ Сменить список", callback_data="switchlist")
    )
    return markup

# Команды
@bot.message_handler(commands=["start"])
def start(message):
    chat_id = str(message.chat.id)
    init_chat(chat_id)
    bot.send_message(message.chat.id, "👋 Я бот для идей досуга!", reply_markup=main_menu())

# Кнопки
@bot.callback_query_handler(func=lambda call: True)
def handle_buttons(call):
    chat_id = str(call.message.chat.id)
    user_id = str(call.from_user.id)
    init_chat(chat_id)
    chat = data["chats"][chat_id]
    state = chat["state"]

    if call.data == "get_idea":
        show_random_idea(call.message)
        return

    if call.data == "listideas":
        send_idea_list(call.message)
        return

    if call.data == "addidea":
        state[user_id] = {"mode": "addidea"}
        bot.edit_message_text("✏️ Введите идею или нажмите ❌ Отмена.",
                              chat_id=call.message.chat.id,
                              message_id=call.message.message_id,
                              reply_markup=cancel_markup())
        return

    if call.data == "addplace":
        state[user_id] = {"mode": "addplace"}
        bot.edit_message_text("✏️ Введите ID и место (например: `3 Парк Сказка`) или нажмите ❌ Отмена.",
                              chat_id=call.message.chat.id,
                              message_id=call.message.message_id,
                              reply_markup=cancel_markup())
        return

    if call.data == "deleteidea":
        state[user_id] = {"mode": "deleteidea"}
        bot.edit_message_text("✏️ Введите номер идеи для удаления или нажмите ❌ Отмена.",
                              chat_id=call.message.chat.id,
                              message_id=call.message.message_id,
                              reply_markup=cancel_markup())
        return

    if call.data == "deleteplace":
        state[user_id] = {"mode": "deleteplace"}
        bot.edit_message_text("✏️ Введите ID идеи и номер места (например: `2 1`) или нажмите ❌ Отмена.",
                              chat_id=call.message.chat.id,
                              message_id=call.message.message_id,
                              reply_markup=cancel_markup())
        return

    if call.data == "switchlist":
        bot.send_message(call.message.chat.id, "📋 Списоков пока нет (эта часть пока заглушка).", reply_markup=main_menu())

    if call.data == "cancel":
        state.pop(user_id, None)
        bot.edit_message_text("❌ Действие отменено.", chat_id=call.message.chat.id,
                              message_id=call.message.message_id,
                              reply_markup=main_menu())
        save_data()
        return

# Отмена

def cancel_markup():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("❌ Отмена", callback_data="cancel"))
    return markup

# Список идей

def send_idea_list(message):
    chat_id = str(message.chat.id)
    chat = data["chats"][chat_id]
    current_key = chat["current_list"]
    if not current_key or current_key not in chat["lists"]:
        bot.send_message(message.chat.id, "❌ Нет активного списка. Создайте новый.")
        return
    idea_list = chat["lists"][current_key]
   lines = [f"{idea_list['name']}"]
    for idea in idea_list["ideas"]:
        lines.append(f"*{idea['id']}. {idea['text']}*
")
        for place in idea["places"]:
            lines.append(f"📍{place['name']}")
        lines.append("")
    text = "
".join(lines).strip()
    for chunk in [text[i:i+4000] for i in range(0, len(text), 4000)]:
        bot.send_message(message.chat.id, chunk)

# Идея случайная

def show_random_idea(message):
    chat_id = str(message.chat.id)
    chat = data["chats"][chat_id]
    current_key = chat["current_list"]
    if not current_key or current_key not in chat["lists"]:
        bot.send_message(message.chat.id, "❌ Нет активного списка. Создайте новый.")
        return
    idea_list = chat["lists"][current_key]
    if not idea_list["ideas"]:
        bot.send_message(message.chat.id, "📭 Идей пока нет.")
        return
    idea = random.choice(idea_list["ideas"])
    response = f"💡 *{idea['text']}*"
    if idea["places"]:
        response += f"
📍 {random.choice(idea['places'])['name']}"
    bot.send_message(message.chat.id, response)

# Обработка текста
@bot.message_handler(func=lambda msg: True)
def handle_text(message):
    chat_id = str(message.chat.id)
    user_id = str(message.from_user.id)
    init_chat(chat_id)
    chat = data["chats"][chat_id]
    state = chat["state"].get(user_id)
    if not state:
        return
    mode = state.get("mode")
    current_key = chat["current_list"]
    if not current_key or current_key not in chat["lists"]:
        bot.send_message(message.chat.id, "❌ Нет активного списка. Создайте новый.")
        chat["state"].pop(user_id, None)
        save_data()
        return
    lst = chat["lists"][current_key]

    if mode == "addidea":
        new_id = len(lst["ideas"]) + 1
        lst["ideas"].append({"id": new_id, "text": message.text.strip(), "places": []})
        bot.send_message(message.chat.id, f"✅ Идея добавлена под номером {new_id}.", reply_markup=main_menu())

    elif mode == "addplace":
        try:
            parts = message.text.strip().split(maxsplit=1)
            idea_id = int(parts[0]) - 1
            place = parts[1]
            lst["ideas"][idea_id]["places"].append({"name": place})
            bot.send_message(message.chat.id, f"📍 Место добавлено к идее {idea_id+1}.", reply_markup=main_menu())
        except:
            bot.send_message(message.chat.id, "⚠️ Формат: ID Место", reply_markup=main_menu())

    elif mode == "deleteidea":
        try:
            idx = int(message.text.strip()) - 1
            lst["ideas"].pop(idx)
            for i, idea in enumerate(lst["ideas"], 1):
                idea["id"] = i
            bot.send_message(message.chat.id, f"🗑 Идея удалена.", reply_markup=main_menu())
        except:
            bot.send_message(message.chat.id, "⚠️ Неверный номер идеи.", reply_markup=main_menu())

    elif mode == "deleteplace":
        try:
            parts = message.text.strip().split()
            idx = int(parts[0]) - 1
            place_idx = int(parts[1]) - 1
            removed = lst["ideas"][idx]["places"].pop(place_idx)
            bot.send_message(message.chat.id, f"🗑 Удалено место: {removed['name']}", reply_markup=main_menu())
        except:
            bot.send_message(message.chat.id, "⚠️ Ошибка удаления места.", reply_markup=main_menu())

    chat["state"].pop(user_id, None)
    save_data()

# Запуск
bot.infinity_polling()
