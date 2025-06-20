import os
import json
import random
import html
import telebot
from telebot import types

TOKEN = os.getenv("BOT_TOKEN") or "YOUR_TOKEN_HERE"
DATA_FILE = "data.json"

bot = telebot.TeleBot(TOKEN, parse_mode="Markdown")   # глобально остаётся Markdown

# ─────────────────── storage ───────────────────
def _load_data():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump({"chats": {}}, f, ensure_ascii=False, indent=2)
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def _save():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(DATA, f, ensure_ascii=False, indent=2)

DATA = _load_data()

def _init_chat(chat_id: int):
    cid = str(chat_id)
    if cid not in DATA["chats"]:
        DATA["chats"][cid] = {
            "current_list": "default",
            "lists": {
                "default": {
                    "name": "🌞 Идеи для досуга 2025 🔥",
                    "ideas": [],    # [{"id": 1, "text": "...", "places": []}, ...]
                    "history": []   # ["1:none", "2:0", ...]
                }
            }
        }

def _chat(chat_id):
    _init_chat(chat_id)
    return DATA["chats"][str(chat_id)]

def _current(chat_id):
    ch = _chat(chat_id)
    return ch["lists"][ch["current_list"]]

# ─────────────────── keyboards ───────────────────
def main_menu():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(types.InlineKeyboardButton("🎲 Получить идею", callback_data="get_idea"))
    kb.add(
        types.InlineKeyboardButton("💡 Добавить идею", callback_data="add_idea"),
        types.InlineKeyboardButton("📍 Добавить место", callback_data="add_place"),
    )
    kb.add(
        types.InlineKeyboardButton("🗑 Удалить идею", callback_data="del_idea"),
        types.InlineKeyboardButton("🗑 Удалить место", callback_data="del_place"),
    )
    kb.add(
        types.InlineKeyboardButton("🗒 Все идеи", callback_data="list_ideas"),
        types.InlineKeyboardButton("◀️ Сменить список", callback_data="switch_list"),
    )
    return kb

# ─────────────────── helpers ───────────────────
def _combo_key(idea_id: int, place_idx):
    """place_idx == None → идея без места"""
    return f"{idea_id}:{'none' if place_idx is None else place_idx}"

def _clear_history(list_obj):
    list_obj["history"] = []

def _renumber(ideas):
    for i, idea in enumerate(ideas, 1):
        idea["id"] = i

def _format_ideas_html(ideas, used_keys):
    """Возвращает HTML-строку с зачёркнутыми идеями/местами."""
    lines = []
    for idea in ideas:
        idea_used_places = []
        for idx, _ in enumerate(idea["places"]):
            if _combo_key(idea["id"], idx) in used_keys:
                idea_used_places.append(idx)
        idea_no_places_key = _combo_key(idea["id"], None)

        idea_fully_striked = (
            (idea["places"] and len(idea_used_places) == len(idea["places"])) or
            (not idea["places"] and idea_no_places_key in used_keys)
        )

        idea_text = f"<b>{idea['id']}. {html.escape(idea['text'])}</b>"
        if idea_fully_striked:
            idea_text = f"<s>{idea_text}</s>"
        lines.append(idea_text)

        for idx, place in enumerate(idea["places"]):
            place_line = f"📍 {html.escape(place['name'])}"
            if idx in idea_used_places:
                place_line = f"<s>{place_line}</s>"
            lines.append(place_line)
        lines.append("")  # пустая строка между идеями
    return "\n".join(lines).strip()

# ─────────────────── commands ───────────────────
@bot.message_handler(commands=["start", "help"])
def handle_start(message):
    bot.send_message(
        message.chat.id,
        "👋 Я бот идей для досуга!\n\n"
        "Пользуйся кнопками или командами:\n"
        "`/idea`, `/addidea текст`, `/addplace ID место`,\n"
        "`/deleteidea ID`, `/deleteplace ID номер`, `/listideas`",
        reply_markup=main_menu(),
    )

@bot.message_handler(commands=["idea"])
def cmd_idea(message):
    _send_random_idea(message.chat.id)

@bot.message_handler(commands=["addidea"])
def cmd_addidea(message):
    text = message.text.partition(" ")[2].strip()
    if not text:
        bot.reply_to(message, "⚠️ После команды напиши текст идеи.")
        return
    _add_idea(message.chat.id, text)

@bot.message_handler(commands=["addplace"])
def cmd_addplace(message):
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3 or not parts[1].isdigit():
        bot.reply_to(message, "⚠️ Формат: /addplace ID место")
        return
    _add_place(message.chat.id, int(parts[1]), parts[2])

@bot.message_handler(commands=["deleteidea"])
def cmd_delidea(message):
    parts = message.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        bot.reply_to(message, "⚠️ Формат: /deleteidea ID")
        return
    _delete_idea(message.chat.id, int(parts[1]))

@bot.message_handler(commands=["deleteplace"])
def cmd_delplace(message):
    parts = message.text.split(maxsplit=2)
    if len(parts) != 3 or not (parts[1].isdigit() and parts[2].isdigit()):
        bot.reply_to(message, "⚠️ Формат: /deleteplace ID номер")
        return
    _delete_place(message.chat.id, int(parts[1]), int(parts[2]))

@bot.message_handler(commands=["listideas"])
def cmd_listideas(message):
    _list_ideas(message.chat.id)

# ─────────────────── callbacks ───────────────────
@bot.callback_query_handler(func=lambda c: True)
def callbacks(call):
    data = call.data
    cid = call.message.chat.id

    if data == "get_idea":
        _send_random_idea(cid)

    elif data == "add_idea":
        msg = bot.send_message(cid, "✏️ Введите текст новой идеи:")
        bot.register_next_step_handler(msg, lambda m: _add_idea(cid, m.text))

    elif data == "add_place":
        msg = bot.send_message(
            cid,
            "✏️ Введите через пробел: `номер_идеи место`\nНапр.: `3 Парк «Сказка»`",
        )
        bot.register_next_step_handler(msg, lambda m: _handle_add_place(cid, m.text))

    elif data == "del_idea":
        msg = bot.send_message(cid, "🗑 Какую идею удалить? Напиши её номер.")
        bot.register_next_step_handler(msg, lambda m: _delete_idea(cid, m.text))

    elif data == "del_place":
        msg = bot.send_message(
            cid, "🗑 Удалить место: напиши `номер_идеи номер_места`"
        )
        bot.register_next_step_handler(msg, lambda m: _handle_del_place(cid, m.text))

    elif data == "list_ideas":
        _list_ideas(cid)

    elif data == "switch_list":
        _show_lists(cid)

    elif data.startswith("use_list:"):
        key = data.split(":", 1)[1]
        ch = _chat(cid)
        if key in ch["lists"]:
            ch["current_list"] = key
            _save()
            bot.answer_callback_query(call.id, "✅ Список выбран")
            bot.edit_message_reply_markup(
                cid, call.message.message_id, reply_markup=main_menu()
            )

    elif data == "new_list":
        msg = bot.send_message(cid, "📋 Введите название нового списка:")
        bot.register_next_step_handler(msg, lambda m: _create_list(cid, m.text))

    elif data == "delete_list":
        _delete_list(cid)

# ─────────────────── core ───────────────────
def _send_random_idea(chat_id):
    """Выдаёт случайную пару (идея, место) без повторов.
       После исчерпания — сообщает об отсутствии идей."""
    cur = _current(chat_id)
    ideas = cur["ideas"]
    if not ideas:
        bot.send_message(chat_id, "📭 В этом списке пока нет идей.")
        return

    # полный набор возможных комбинаций
    all_combos = []
    for idea in ideas:
        if idea["places"]:
            for idx in range(len(idea["places"])):
                all_combos.append((idea, idx))
        else:
            all_combos.append((idea, None))

    used = set(cur.get("history", []))
    available = [
        (idea, idx) for idea, idx in all_combos
        if _combo_key(idea["id"], idx) not in used
    ]

    if not available:
        bot.send_message(chat_id, "⚠️ Все идеи в этом списке уже были использованы.")
        return

    idea, place_idx = random.choice(available)
    cur["history"].append(_combo_key(idea["id"], place_idx))
    _save()

    text = f"*{idea['text']}*"
    if place_idx is not None:
        text += f"\n📍 {idea['places'][place_idx]['name']}"
    bot.send_message(chat_id, text)

# ——— CRUD ———
def _add_idea(chat_id, text):
    cur = _current(chat_id)
    cur["ideas"].append({"id": len(cur["ideas"]) + 1, "text": text, "places": []})
    _clear_history(cur)
    _save()
    bot.send_message(chat_id, "✅ Идея добавлена", reply_markup=main_menu())

def _add_place(chat_id, idea_id, place_text):
    cur = _current(chat_id)
    if not (1 <= idea_id <= len(cur["ideas"])):
        bot.send_message(chat_id, "❌ Идея с таким номером не найдена.")
        return
    cur["ideas"][idea_id - 1]["places"].append({"name": place_text})
    _clear_history(cur)
    _save()
    bot.send_message(chat_id, "📍 Место добавлено", reply_markup=main_menu())

def _handle_add_place(chat_id, text):
    try:
        num, place = text.split(maxsplit=1)
        _add_place(chat_id, int(num), place)
    except Exception:
        bot.send_message(chat_id, "⚠️ Формат: `номер_идеи место`")

def _delete_idea(chat_id, idea_id):
    cur = _current(chat_id)
    try:
        idea_id = int(idea_id)
    except Exception:
        bot.send_message(chat_id, "⚠️ Номер должен быть целым")
        return
    if not (1 <= idea_id <= len(cur["ideas"])):
        bot.send_message(chat_id, "❌ Идея не найдена.")
        return
    del cur["ideas"][idea_id - 1]
    _renumber(cur["ideas"])
    _clear_history(cur)
    _save()
    bot.send_message(chat_id, "🗑 Идея удалена", reply_markup=main_menu())

def _delete_place(chat_id, idea_id, place_idx):
    cur = _current(chat_id)
    if not (1 <= idea_id <= len(cur["ideas"])):
        bot.send_message(chat_id, "❌ Идея не найдена.")
        return
    places = cur["ideas"][idea_id - 1]["places"]
    if not (1 <= place_idx <= len(places)):
        bot.send_message(chat_id, "❌ Место не найдено.")
        return
    places.pop(place_idx - 1)
    _clear_history(cur)
    _save()
    bot.send_message(chat_id, "🗑 Место удалено", reply_markup=main_menu())

def _handle_del_place(chat_id, text):
    try:
        idea, plc = map(int, text.split())
        _delete_place(chat_id, idea, plc)
    except Exception:
        bot.send_message(chat_id, "⚠️ Формат: `номер_идеи номер_места`")

# ——— вывод всех идей ———
def _list_ideas(chat_id):
    cur = _current(chat_id)
    if not cur["ideas"]:
        bot.send_message(chat_id, "📭 В этом списке пока нет идей.")
        return
    used = set(cur.get("history", []))
    header = f"<b>{html.escape(cur['name'])}</b>\n\n"
    body = _format_ideas_html(cur["ideas"], used)
    for chunk in (body[i:i+4000] for i in range(0, len(body), 4000)):
        bot.send_message(chat_id, header + chunk, parse_mode="HTML")
        header = ""  # чтобы заголовок был только в первой части

# ——— управление списками ———
def _show_lists(chat_id):
    ch = _chat(chat_id)
    kb = types.InlineKeyboardMarkup()
    for key, lst in ch["lists"].items():
        title = ("✅ " if key == ch["current_list"] else "") + lst["name"]
        kb.add(types.InlineKeyboardButton(title, callback_data=f"use_list:{key}"))
    kb.add(
        types.InlineKeyboardButton("📋 Создать список", callback_data="new_list"),
        types.InlineKeyboardButton("❌ Удалить список", callback_data="delete_list"),
    )
    bot.send_message(chat_id, "🔄 Выберите список:", reply_markup=kb)

def _create_list(chat_id, name):
    key = name.lower().replace(" ", "_")
    ch = _chat(chat_id)
    if key in ch["lists"]:
        bot.send_message(chat_id, "⚠️ Такой список уже существует.")
        return
    ch["lists"][key] = {"name": name, "ideas": [], "history": []}
    ch["current_list"] = key
    _save()
    bot.send_message(chat_id, "✅ Список создан и выбран", reply_markup=main_menu())

def _delete_list(chat_id):
    ch = _chat(chat_id)
    if len(ch["lists"]) == 1:
        bot.send_message(chat_id, "❌ Нельзя удалить последний список.")
        return
    cur_key = ch["current_list"]
    del ch["lists"][cur_key]
    ch["current_list"] = next(iter(ch["lists"]))
    _save()
    bot.send_message(chat_id, "🗑 Текущий список удалён", reply_markup=main_menu())

# ─────────────────── run ───────────────────
if __name__ == "__main__":
    bot.polling(skip_pending=True)
