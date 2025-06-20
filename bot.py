import os, json, random, html, re, telebot
from telebot import types

TOKEN = os.getenv("BOT_TOKEN") or "YOUR_TOKEN_HERE"
DATA_FILE = "data.json"
bot = telebot.TeleBot(TOKEN, parse_mode="Markdown")

# ───────── storage ───────── #
def _load():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump({"chats": {}}, f)
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def _save():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(DATA, f, ensure_ascii=False, indent=2)

DATA = _load()

def _chat(cid: int):
    cid = str(cid)
    if cid not in DATA["chats"]:
        DATA["chats"][cid] = {
            "current_list": "default",
            "lists": {
                "default": {
                    "name": "🌞 Идеи для досуга 2025 🔥",
                    "ideas": [],
                    "history": []
                }
            }
        }
    return DATA["chats"][cid]

def _cur(cid: int):
    return _chat(cid)["lists"][_chat(cid)["current_list"]]

# ───────── helpers ───────── #
def _combo(i_id, pl_idx):
    return f"{i_id}:{'none' if pl_idx is None else pl_idx}"

def _renumber(ideas):
    for n, it in enumerate(ideas, 1):
        it["id"] = n

def _make_link(text: str, url: str) -> str:
    return f'<a href="{html.escape(url, quote=True)}">{html.escape(text)}</a>'

def _auto_linkify(text_html: str) -> str:
    """
    Превращает `Текст https://url` или Markdown `[Текст](url)` в кликабельную ссылку.
    Если в строке уже есть <a href=…>, оставляет как есть.
    """
    if "<a href" in text_html:
        return text_html  # уже отформатировано через меню «Ссылка» Telegram

    md = re.search(r"\[([^\]]+)]\((https?://[^\s)]+)\)", text_html)
    if md:                                   # Markdown
        return (_make_link(md.group(1), md.group(2))
                .join([text_html[:md.start()].strip(), text_html[md.end():].strip()])
                ).strip()

    url_match = re.search(r"(https?://\S+)$", text_html)
    if url_match:
        url = url_match.group(1)
        text_part = text_html[:url_match.start()].rstrip()
        if text_part:
            return _make_link(text_part, url)
    return text_html

def _parse_place_msg(msg_html: str):
    """
    'номер_идеи …'  ➜ (idea_id:int, place_html:str)  или None.
    Использует _auto_linkify для ссылки.
    """
    m = re.match(r"\s*(\d+)\s+(.+)", msg_html, re.DOTALL)
    if not m:
        return None
    idea_id, rest = int(m.group(1)), _auto_linkify(m.group(2).strip())
    return idea_id, rest

def _fmt_html(ideas, used):
    out = []
    for idea in ideas:
        used_pl = [idx for idx, _ in enumerate(idea["places"]) if _combo(idea["id"], idx) in used]
        full = (idea["places"] and len(used_pl) == len(idea["places"])) or \
               (not idea["places"] and _combo(idea["id"], None) in used)
        line = f"<b>{idea['id']}.</b> {idea['text']}"
        out.append(f"<s>{line}</s>" if full else line)
        for idx, pl in enumerate(idea["places"]):
            pl_line = f"📍 {pl['name']}"
            out.append(f"<s>{pl_line}</s>" if idx in used_pl else pl_line)
        out.append("")
    return "\n".join(out).strip()

# ───────── keyboards ───────── #
def _menu():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(types.InlineKeyboardButton("🎲 Получить идею", callback_data="get"))
    kb.add(types.InlineKeyboardButton("💡 Добавить идею", callback_data="addidea"),
           types.InlineKeyboardButton("📍 Добавить место", callback_data="addplace"))
    kb.add(types.InlineKeyboardButton("🗑 Удалить идею", callback_data="delidea"),
           types.InlineKeyboardButton("🗑 Удалить место", callback_data="delplace"))
    kb.add(types.InlineKeyboardButton("🗒 Все идеи", callback_data="list"),
           types.InlineKeyboardButton("◀️ Сменить список", callback_data="lists"))
    return kb

# ───────── core ───────── #
def _send_rand(cid: int):
    cur = _cur(cid)
    if not cur["ideas"]:
        return bot.send_message(cid, "📭 В этом списке пока нет идей.")
    pairs = [(it, idx if it["places"] else None)
             for it in cur["ideas"]
             for idx in (range(len(it["places"])) if it["places"] else [None])]
    used = set(cur["history"])
    avail = [(i, p) for i, p in pairs if _combo(i["id"], p) not in used]
    if not avail:
        return bot.send_message(cid, "⚠️ Все идеи в этом списке уже использованы.")
    idea, pl = random.choice(avail)
    cur["history"].append(_combo(idea["id"], pl))
    _save()
    txt = f"<b>{idea['text']}</b>"
    if pl is not None:
        txt += f"\n📍 {idea['places'][pl]['name']}"
    bot.send_message(cid, txt, parse_mode="HTML")

def _add_idea(cid: int, html_text: str):
    cur = _cur(cid)
    cur["ideas"].append({"id": len(cur["ideas"]) + 1, "text": _auto_linkify(html_text), "places": []})
    _save()
    bot.send_message(cid, "✅ Идея добавлена", reply_markup=_menu())

def _add_place(cid: int, idea_id: int, place_html: str):
    cur = _cur(cid)
    if not (1 <= idea_id <= len(cur["ideas"])):
        return bot.send_message(cid, "❌ Идея с таким номером не найдена.")
    cur["ideas"][idea_id - 1]["places"].append({"name": _auto_linkify(place_html)})
    _save()
    bot.send_message(cid, "📍 Место добавлено", reply_markup=_menu())

def _del_idea(cid: int, idea_id_raw: str):
    try:
        idea_id = int(idea_id_raw)
    except ValueError:
        return bot.send_message(cid, "⚠️ Номер должен быть целым")
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

# ───────── lists ───────── #
def _show_lists(cid: int):
    ch = _chat(cid)
    kb = types.InlineKeyboardMarkup()
    for k, lst in ch["lists"].items():
        title = ("✅ " if k == ch["current_list"] else "") + lst["name"]
        kb.add(types.InlineKeyboardButton(title, callback_data=f"use:{k}"))
    kb.add(types.InlineKeyboardButton("📋 Создать список", callback_data="new"),
           types.InlineKeyboardButton("❌ Удалить список", callback_data="dellist"))
    bot.send_message(cid, "🔄 Выберите список:", reply_markup=kb)

def _create_list(cid: int, name_html: str):
    key = html.unescape(name_html).lower().replace(" ", "_")
    ch = _chat(cid)
    if key in ch["lists"]:
        return bot.send_message(cid, "⚠️ Такой список уже существует.")
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

# ───────── list ideas ───────── #
def _list_ideas(cid: int):
    cur = _cur(cid)
    if not cur["ideas"]:
        return bot.send_message(cid, "📭 В этом списке пока нет идей.")
    used = set(cur["history"])
    header = f"<b>{html.escape(cur['name'])}</b>\n\n"
    body = _fmt_html(cur["ideas"], used)
    for chunk in (body[i:i + 4000] for i in range(0, len(body), 4000)):
        bot.send_message(cid, header + chunk, parse_mode="HTML")
        header = ""

# ───────── command helpers ───────── #
def _split_cmd(txt: str):
    return txt.split(" ", 1)[1].strip() if " " in txt else ""

# ───────── message handlers ───────── #
@bot.message_handler(commands=["start", "help"])
def start(m):
    bot.send_message(m.chat.id,
        "👋 Я бот идей.\n\n"
        "Команды:\n"
        "• /idea — случайная идея\n"
        "• /addidea Текст [ссылка]\n"
        "• /addplace ID текст [ссылка]\n"
        "  Пример: 3 Покататься https://сайт\n"
        "• /listideas — все идеи",
        reply_markup=_menu())

@bot.message_handler(commands=["idea"])
def cmd_idea(m):  _send_rand(m.chat.id)

@bot.message_handler(commands=["addidea"])
def cmd_addidea(m):
    html_text = _split_cmd(m.html_text or m.text)
    if not html_text:
        return bot.reply_to(m, "⚠️ После команды введите текст идеи.")
    _add_idea(m.chat.id, html_text)

@bot.message_handler(commands=["addplace"])
def cmd_addplace(m):
    parsed = _parse_place_msg((m.html_text or m.text).replace("/addplace", "", 1))
    if not parsed:
        return bot.reply_to(m, "⚠️ Формат: /addplace ID место")
    _add_place(m.chat.id, *parsed)

@bot.message_handler(commands=["deleteidea"])
def cmd_delidea(m):
    _del_idea(m.chat.id, _split_cmd(m.text))

@bot.message_handler(commands=["deleteplace"])
def cmd_delplace(m):
    a = _split_cmd(m.text).split()
    if len(a) != 2 or not (a[0].isdigit() and a[1].isdigit()):
        return bot.reply_to(m, "⚠️ Формат: /deleteplace ID номер")
    _del_place(m.chat.id, int(a[0]), int(a[1]))

@bot.message_handler(commands=["listideas"])
def cmd_list(m):
    _list_ideas(m.chat.id)

# ───────── callbacks ───────── #
@bot.callback_query_handler(func=lambda _:_)
def cb(call):
    d, cid = call.data, call.message.chat.id
    if d == "get": _send_rand(cid)
    elif d == "addidea":
        msg = bot.send_message(cid, "✏️ Текст новой идеи (можно добавить ссылку после пробела):", parse_mode="HTML")
        bot.register_next_step_handler(msg, lambda m:_add_idea(cid, (m.html_text or m.text).strip()))
    elif d == "addplace":
        msg = bot.send_message(cid,
            "✏️ Введите одно сообщение:\n`номер_идеи текст [ссылка]`\n"
            "Примеры:\n`3 Парк https://ostrovmechty.ru`\n`3 Прогулка в [Парке](https://...)`",
            parse_mode="Markdown")
        bot.register_next_step_handler(msg, lambda m:_handle_place(cid, m))
    elif d == "delidea":
        msg = bot.send_message(cid, "🗑 Номер идеи для удаления?")
        bot.register_next_step_handler(msg, lambda m:_del_idea(cid, m.text))
    elif d == "delplace":
        msg = bot.send_message(cid, "🗑 Введите `номер_идеи номер_места`")
        bot.register_next_step_handler(msg, lambda m:_handle_delplace(cid, m.text))
    elif d == "list": _list_ideas(cid)
    elif d == "lists": _show_lists(cid)
    elif d.startswith("use:"):
        _chat(cid)["current_list"] = d.split(":", 1)[1]; _save()
        bot.edit_message_reply_markup(cid, call.message.id, reply_markup=_menu())
    elif d == "new":
        msg = bot.send_message(cid, "📋 Название списка:", parse_mode="HTML")
        bot.register_next_step_handler(msg, lambda m:_create_list(cid, (m.html_text or m.text).strip()))
    elif d == "dellist": _delete_list(cid)

# ───────── callback helpers ───────── #
def _handle_place(cid, m):
    parsed = _parse_place_msg(m.html_text or m.text)
    if not parsed:
        return bot.reply_to(m, "⚠️ Формат: номер_идеи текст [ссылка]")
    _add_place(cid, *parsed)

def _handle_delplace(cid, txt):
    a = txt.split()
    if len(a) != 2 or not (a[0].isdigit() and a[1].isdigit()):
        return bot.send_message(cid, "⚠️ Формат: номер_идеи номер_места")
    _del_place(cid, int(a[0]), int(a[1]))

# ───────── run ───────── #
if __name__ == "__main__":
    bot.polling(skip_pending=True)
