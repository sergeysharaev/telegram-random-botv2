import os
import json
import random
import html
import re
import telebot
from telebot import types

# ─────────────────── CONFIG ───────────────────
TOKEN = os.getenv("BOT_TOKEN") or "YOUR_TOKEN_HERE"
DATA_FILE = "data.json"

bot = telebot.TeleBot(TOKEN, parse_mode="Markdown")  # Markdown по‑умолчанию, HTML в нужных местах

# ───────────────────— DATA LAYER ───────────────────—

def _load():
    """Читаем общий JSON или создаём новый каркас."""
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", encoding="utf-8") as fp:
            json.dump({"chats": {}}, fp)
    with open(DATA_FILE, "r", encoding="utf-8") as fp:
        return json.load(fp)


def _save():
    with open(DATA_FILE, "w", encoding="utf-8") as fp:
        json.dump(DATA, fp, ensure_ascii=False, indent=2)


DATA = _load()


# ───────────────────— CHAT HELPERS ───────────────────—

def _chat(cid: int):
    """Возвращает/инициализирует структуру чата."""
    cid = str(cid)
    if cid not in DATA["chats"]:
        DATA["chats"][cid] = {
            "current_list": "default",
            "lists": {
                "default": {
                    "name": "🌞 Идеи для досуга 2025 🔥",
                    "ideas": [],
                    "history": []  # список показанных комбинаций idea_id:place_id|none
                }
            }
        }
    return DATA["chats"][cid]


def _cur(cid: int):
    """Текущий активный список чата."""
    ch = _chat(cid)
    return ch["lists"][ch["current_list"]]


# ───────────────────— UTILS ───────────────────—

def _combo(iid: int, pidx):
    return f"{iid}:{'none' if pidx is None else pidx}"


def _renumber(lst):
    """Переприсваивает id после удаления элементов."""
    for i, item in enumerate(lst):
        item["id"] = i + 1


def _alink(text: str, url: str):
    return f'<a href="{html.escape(url, quote=True)}">{html.escape(text)}</a>'


URL_RE = re.compile(r"https?://\S+")
MD_RE = re.compile(r"\[([^\]]+)]\((https?://[^\s)]+)\)")


def _auto_linkify(raw: str) -> str:
    """Преобразует `текст ссылка` или Markdown‑формат в кликабельную HTML‑ссылку."""
    if "<a href" in raw:  # уже ссылка
        return raw
    # markdown
    md = MD_RE.search(raw)
    if md:
        return MD_RE.sub(lambda m: _alink(m.group(1), m.group(2)), raw, count=1)
    # bare url
    url = URL_RE.search(raw)
    if url:
        before, link, after = raw[:url.start()].strip(), url.group(0), raw[url.end():].strip()
        link_html = _alink(before or link, link) if before else _alink(link, link)
        return f"{link_html} {after}".strip()
    return raw


PL_PARSE_RE = re.compile(r"\s*(\d+)\s+(.+)", re.DOTALL)


def _parse_place_msg(msg_html: str):
    """Разбор строки вида "3 Парк https://site.ru". Возвращает (idea_id, html_place) или None."""
    m = PL_PARSE_RE.match(msg_html)
    if not m:
        return None
    return int(m.group(1)), _auto_linkify(m.group(2).strip())


# ───────────────────— FORMATTING ───────────────────—

def _format_ideas_html(ideas, used):
    """Формируем красивый список идей с зачёркиванием использованных."""
    lines = []
    for idea in ideas:
        used_pl = [idx for idx, _ in enumerate(idea["places"]) if _combo(idea["id"], idx) in used]
        idea_used = (
            (not idea["places"] and _combo(idea["id"], None) in used) or
            (idea["places"] and len(used_pl) == len(idea["places"]))
        )
        prefix = "<s>" if idea_used else ""
        suffix = "</s>" if idea_used else ""
        lines.append(f"{prefix}<b>{idea['id']}.</b> {idea['text']}{suffix}")
        for idx, place in enumerate(idea["places"]):
            pl_line = f"📍 {place['name']}"
            if idx in used_pl:
                pl_line = f"<s>{pl_line}</s>"
            lines.append(pl_line)
        lines.append("")
    return "\n".join(lines).strip()


# ───────────────────— KEYBOARDS ───────────────────—

def _menu():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(types.InlineKeyboardButton("🎲 Получить идею", callback_data="get"))
    kb.add(
        types.InlineKeyboardButton("💡 Добавить идею", callback_data="addidea"),
        types.InlineKeyboardButton("📍 Добавить место", callback_data="addplace"),
    )
    kb.add(
        types.InlineKeyboardButton("🗑 Удалить идею", callback_data="delidea"),
        types.InlineKeyboardButton("🗑 Удалить место", callback_data="delplace"),
    )
    kb.add(
        types.InlineKeyboardButton("🗒 Все идеи", callback_data="list"),
        types.InlineKeyboardButton("◀️ Сменить список", callback_data="lists"),
    )
    return kb


# ───────────────────— CORE LOGIC ───────────────────—

def _send_rand(cid: int):
    cur = _cur(cid)
    if not cur["ideas"]:
        return bot.send_message(cid, "📭 В этом списке пока нет идей.")

    combos = [
        (idea, idx if idea["places"] else None)
        for idea in cur["ideas"]
        for idx in (range(len(idea["places"])) if idea["places"] else [None])
    ]
    unused = [c for c in combos if _combo(c[0]["id"], c[1]) not in set(cur["history"])]
    if not unused:
        return bot.send_message(cid, "⚠️ Все идеи в этом списке уже использованы.")

    idea, pl_idx = random.choice(unused)
    cur["history"].append(_combo(idea["id"], pl_idx))
    _save()

    txt = f"<b>{idea['text']}</b>"
    if pl_idx is not None:
        txt += f"\n📍 {idea['places'][pl_idx]['name']}"
    bot.send_message(cid, txt, parse_mode="HTML")


def _add_idea(cid: int, html_text: str):
    cur = _cur(cid)
    cur["ideas"].append({
        "id": len(cur["ideas"]) + 1,
        "text": _auto_linkify(html_text),
        "places": [],
    })
    _save()
    bot.send_message(cid, "✅ Идея добавлена", reply_markup=_menu())


def _add_place(cid: int, idea_id: int, place_html: str):
    cur = _cur(cid)
    if not (1 <= idea_id <= len(cur["ideas"])):
        return bot.send_message(cid, "❌ Идея с таким номером не найдена.")
    cur["ideas"][idea_id - 1]["places"].append({"name": place_html})
    cur["history"] = []  # обнуляем историю — теперь новая комбинация возможна
    _save()
    bot.send_message(cid, "📍 Место добавлено", reply_markup=_menu())


def _del_idea(cid: int, idea_id_raw: str):
    try:
        idea_id = int(idea_id_raw)
    except ValueError:
        return bot.send_message(cid, "⚠️ Номер должен быть целым.")
    cur = _cur(cid)
    if not (1 <= idea_id <= len(cur["ideas"])):
        return bot.send_message(cid, "❌ Идея не найдена.")
    del cur["ideas"][idea_id - 1]
    _renumber(cur["ideas"])
    cur["history"] = []
    _save()
    bot.send_message(cid, "🗑 Идея удалена", reply_markup=_menu())


def _del_place(cid: int, idea_id: int, pl_idx: int):
    cur = _cur(cid)
    if not (1 <= idea_id <= len(cur["ideas"])):
        return bot.send_message(cid, "❌ Идея не найдена.")
    places = cur["ideas"][idea_id - 1]["places"]
    if not (1 <= pl_idx <= len(places)):
        return bot.send_message(cid, "❌ Место не найдено.")
    places.pop(pl_idx - 1)
    cur["history"] = []
    _save()
    bot.send_message(cid, "🗑 Место удалено", reply_markup=_menu())


# ───────────────────— LIST FUNCTIONS ───────────────────—

def _list_ideas(cid: int):
    cur = _cur(cid)
    if not cur["ideas"]:
        return bot.send_message(cid, "📭 В этом списке пока нет идей.")
    header = f"<b>{html.escape(cur['name'])}</b>\n\n"
    body = _format_ideas_html(cur["ideas"], set(cur["history"]))
    # Telegram ограничивает 4096 символов; режем с запасом на заголовок
    for i in range(0, len(body), 4000):
        chunk = body[i:i + 4000]
        bot.send_message(cid, header + chunk, parse_mode="HTML")
        header = ""  # печатаем заголовок только перед первым чанком


# ───────────────────— MULTIPLE LISTS ───────────────────—

def _show_lists(cid: int):
    ch = _chat(cid)
    kb = types.InlineKeyboardMarkup()
    for key, lst in ch["lists"].items():
        title = ("✅ " if key == ch["current_list"] else "") + lst["name"]
        kb.add(types.InlineKeyboardButton(title, callback_data=f"use:{key}"))
    kb.add(
        types.InlineKeyboardButton("📋 Создать список", callback_data="newlist"),
        types.InlineKeyboardButton("❌ Удалить список", callback_data="dellist"),
    )
    bot.send_message(cid, "🔄 Выберите список:", reply_markup=kb)


def _create_list(cid: int, name_html: str):
    key = html.unescape(name_html).lower().replace(" ", "_")
    ch = _chat(cid)
    if key in ch["lists"]:
        return bot.send_message(cid, "⚠️ Список с таким названием уже существует.")
    ch["lists"][key] = {"name": name_html, "ideas": [], "history": []}
    ch["current_list"] = key
    _save()
    bot.send_message(cid, "✅ Список создан и выбран", reply_markup=_menu())


def _delete_list(cid: int):
    ch = _chat(cid)
    if len(ch["lists"]) == 1:
        return bot.send_message(cid, "❌ Нельзя удалить последний список.")
    del ch["lists"][ch["current_list"]]
    ch["current_list"] = next(iter(ch["lists"]))
    _save()
    bot.send_message(cid, "🗑 Список удалён", reply_markup=_menu())

<<<<<<< HEAD
# ─────────────────── LIST IDEAS ───────────────────
def _list_ideas(cid: int):
    cur = _cur(cid)
    if not cur["ideas"]:
        return bot.send_message(cid, "📭 В этом списке пока нет идей.")
    used = set(cur["history"])
    header = f"<b>{html.escape(cur['name'])}</b>\n\n"
    body = _fmt_html(cur["ideas"], used)
    for chunk in (body[i:i+4000] for i in range(0, len(body), 4000)):
        bot.send_message(cid, header + chunk, parse_mode="HTML"); header=""
=======
>>>>>>> f0b9290 (✅ Финальная версия бота с поддержкой списков)

# ───────────────────— MESSAGE HANDLERS ───────────────────—

@bot.message_handler(commands=["start", "help"])
def _cmd_start(m):
    bot.send_message(
        m.chat.id,
        "👋 Я бот идей. Команды не обязательны — пользуйтесь кнопками ниже.\n\n" \
        "Добавить место одним сообщением: `3 Парк https://park.ru`",
        reply_markup=_menu(),
    )


@bot.message_handler(commands=["idea"])
def _cmd_idea(m):
    _send_rand(m.chat.id)


@bot.message_handler(commands=["addidea"])
def _cmd_addidea(m):
    parts = (m.html_text or m.text).split(" ", 1)
    if len(parts) < 2:
        return bot.reply_to(m, "⚠️ После команды введите текст идеи (пример: /addidea Покататься на коньках)")
    _add_idea(m.chat.id, parts[1].strip())


@bot.message_handler(commands=["addplace"])
def _cmd_addplace(m):
    parsed = _parse_place_msg((m.html_text or m.text).replace("/addplace", "", 1))
    if not parsed:
        return bot.reply_to(m, "⚠️ Формат: /addplace ID место [ссылка]")
    _add_place(m.chat.id, *parsed)


@bot.message_handler(commands=["deleteidea"])
def _cmd_delidea(m):
    _del_idea(m.chat.id, m.text.split(" ", 1)[-1])


@bot.message_handler(commands=["deleteplace"])
def _cmd_delplace(m):
    p = m.text.split()
    if len(p) != 3 or not (p[1].isdigit() and p[2].isdigit()):
        return bot.reply_to(m, "⚠️ Формат: /deleteplace ID номер")
    _del_place(m.chat.id, int(p[1]), int(p[2]))


@bot.message_handler(commands=["listideas"])
def _cmd_list(m):
    _list_ideas(m.chat.id)


# ───────────────────— INLINE CALLBACKS ───────────────────—

@bot.callback_query_handler(func=lambda _: True)
def _cb(call):
    cid = call.message.chat.id
    action = call.data

    if action == "get":
        _send_rand(cid)

    elif action == "addidea":
        msg = bot.send_message(cid, "✏️ Текст идеи:", parse_mode="HTML")
        bot.register_next_step_handler(msg, lambda nxt: _add_idea(cid, (nxt.html_text or nxt.text).strip()))

    elif action == "addplace":
        msg = bot.send_message(cid, "✏️ Введите: номер_идеи текст [ссылка]", parse_mode=None)
        bot.register_next_step_handler(msg, lambda nxt: _handle_place(cid, nxt))

    elif action == "delidea":
        msg = bot.send_message(cid, "🗑 Номер идеи?", parse_mode=None)
        bot.register_next_step_handler(msg, lambda nxt: _del_idea(cid, nxt.text))

    elif action == "delplace":
        msg = bot.send_message(cid, "🗑 Введите: номер_идеи номер_места", parse_mode=None)
        bot.register_next_step_handler(msg, lambda nxt: _handle_delplace(cid, nxt.text))

    elif action == "list":
        _list_ideas(cid)

    elif action == "lists":
        _show_lists(cid)

    elif action.startswith("use:"):
        _chat(cid)["current_list"] = action.split(":", 1)[1]
        _save()
        bot.edit_message_reply_markup(cid, call.message.id, reply_markup=_menu())

    elif action == "newlist":
        msg = bot.send_message(cid, "📋 Название списка:", parse_mode="HTML")
        bot.register_next_step_handler(msg, lambda nxt: _create_list(cid, (nxt.html_text or nxt.text).strip()))

    elif action == "dellist":
        _delete_list(cid)


# ───────────────────— POST‑CALLBACK STEPS ───────────────────—

def _handle_place(cid, m):
    parsed = _parse_place_msg(m.html_text or m.text)
    if not parsed:
        msg = bot.reply_to(m, "⚠️ Формат: номер_идеи текст [ссылка]")
        # даём вторую попытку без выхода в меню
        bot.register_next_step_handler(msg, lambda nxt: _handle_place(cid, nxt))
        return
    _add_place(cid, *parsed)


def _handle_delplace(cid, txt):
    p = txt.split()
    if len(p) != 2 or not (p[0].isdigit() and p[1].isdigit()):
        msg = bot.send_message(cid, "⚠️ Формат: номер_идеи номер_места")
        bot.register_next_step_handler(msg, lambda nxt: _handle_delplace(cid, nxt.text))
        return
    _del_place(cid, int(p[0]), int(p[1]))


# ───────────────────— MAIN LOOP ───────────────────—
if __name__ == "__main__":
    print("Bot is running…")
    bot.polling(skip_pending=True)
