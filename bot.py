import os, json, random, html, re, telebot
from telebot import types

TOKEN = os.getenv("BOT_TOKEN") or "YOUR_TOKEN_HERE"
DATA_FILE = "data.json"
bot = telebot.TeleBot(TOKEN, parse_mode="Markdown")            # по умолчанию Markdown

# ──────── storage ────────
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
                    "ideas": [],     # [{"id":1,"text":"...","places":[{"name":"..."}]}]
                    "history": []    # ["1:none", "2:0", ...]
                }
            }
        }
    return DATA["chats"][cid]

def _cur(cid: int):
    return _chat(cid)["lists"][_chat(cid)["current_list"]]

# ──────── helpers ────────
def _combo(i_id, pl_idx):
    return f"{i_id}:{'none' if pl_idx is None else pl_idx}"

def _renumber(ideas):
    for i, it in enumerate(ideas, 1):
        it["id"] = i

def _alink(text: str, url: str) -> str:
    return f'<a href="{html.escape(url, quote=True)}">{html.escape(text)}</a>'

def _auto_linkify(html_text: str) -> str:
    """‘Текст url’ или Markdown ‘[текст](url)’ → кликабельная ссылка."""
    if "<a href" in html_text:             # уже ссылка
        return html_text

    md = re.search(r"\[([^\]]+)]\((https?://[^\s)]+)\)", html_text)
    if md:  # Markdown
        return re.sub(r"\[([^\]]+)]\((https?://[^\s)]+)\)",
                      lambda m: _alink(m.group(1), m.group(2)), html_text, count=1)

    url = re.search(r"https?://\S+", html_text)
    if url:
        url_str = url.group(0)
        before  = html_text[:url.start()].rstrip()
        after   = html_text[url.end():].lstrip()
        if before:
            link = _alink(before, url_str)
            return f"{link} {after}".strip()
    return html_text                            # ничего не трогаем

def _parse_place_msg(msg_html: str):
    """`номер_идеи ...` → (int, str) или None; второе поле проходит автолинковку."""
    m = re.match(r"\s*(\d+)\s+(.+)", msg_html, re.DOTALL)
    if not m:
        return None
    idea_id = int(m.group(1))
    place_html = _auto_linkify(m.group(2).strip())
    return idea_id, place_html

def _format_ideas_html(ideas, used):
    lines = []
    for idea in ideas:
        used_pl = [i for i, _ in enumerate(idea["places"]) if _combo(idea["id"], i) in used]
        full = (idea["places"] and len(used_pl) == len(idea["places"])) or \
               (not idea["places"] and _combo(idea["id"], None) in used)
        headline = f"<b>{idea['id']}.</b> {idea['text']}"
        lines.append(f"<s>{headline}</s>" if full else headline)
        for idx, plc in enumerate(idea["places"]):
            pl_line = f"📍 {plc['name']}"
            lines.append(f"<s>{pl_line}</s>" if idx in used_pl else pl_line)
        lines.append("")
    return "\n".join(lines).strip()

# ──────── keyboards ────────
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

# ──────── core ────────
def _send_rand(cid: int):
    cur = _cur(cid)
    if not cur["ideas"]:
        return bot.send_message(cid, "📭 В этом списке пока нет идей.")
    combos = [(it, idx if it["places"] else None)
              for it in cur["ideas"]
              for idx in (range(len(it["places"])) if it["places"] else [None])]
    used = set(cur["history"])
    avail = [(i, p) for i, p in combos if _combo(i["id"], p) not in used]
    if not avail:
        return bot.send_message(cid, "⚠️ Все идеи в этом списке уже использованы.")
    idea, pl = random.choice(avail)
    cur["history"].append(_combo(idea["id"], pl))
    _save()
    text = f"<b>{idea['text']}</b>"
    if pl is not None:
        text += f"\n📍 {idea['places'][pl]['name']}"
    bot.send_message(cid, text, parse_mode="HTML")

def _add_idea(cid: int, html_text: str):
    cur = _cur(cid)
    cur["ideas"].append({
        "id": len(cur["ideas"]) + 1,
        "text": _auto_linkify(html_text),
        "places": []
    })
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
    _renumber(cur["ideas"]); cur["history"] = []; _save()
    bot.send_message(cid, "🗑 Идея удалена", reply_markup=_menu())

def _del_place(cid: int, idea_id: int, pl_idx: int):
    cur = _cur(cid)
    if not (1 <= idea_id <= len(cur["ideas"])):
        return bot.send_message(cid, "❌ Идея не найдена.")
    places = cur["ideas"][idea_id - 1]["places"]
    if not (1 <= pl_idx <= len(places)):
        return bot.send_message(cid, "❌ Место не найдено.")
    places.pop(pl_idx - 1); cur["history"] = []; _save()
    bot.send_message(cid, "🗑 Место удалено", reply_markup=_menu())

# ──────── lists ────────
def _show_lists(cid: int):
    ch = _chat(cid); kb = types.InlineKeyboardMarkup()
    for key, lst in ch["lists"].items():
        title = ("✅ " if key == ch["current_list"] else "") + lst["name"]
        kb.add(types.InlineKeyboardButton(title, callback_data=f"use:{key}"))
    kb.add(types.InlineKeyboardButton("📋 Создать список", callback_data="newlist"),
           types.InlineKeyboardButton("❌ Удалить список", callback_data="dellist"))
    bot.send_message(cid, "🔄 Выберите список:", reply_markup=kb)

def _create_list(cid: int, name_html: str):
    key = html.unescape(name_html).lower().replace(" ", "_")
    ch = _chat(cid)
    if key in ch["lists"]:
        return bot.send_message(cid, "⚠️ Такой список уже существует.")
    ch["lists"][key] = {"name": name_html, "ideas": [], "history": []}
    ch["current_list"] = key; _save()
    bot.send_message(cid, "✅ Список создан и выбран", reply_markup=_menu())

def _delete_list(cid: int):
    ch = _chat(cid)
    if len(ch["lists"]) == 1:
        return bot.send_message(cid, "❌ Нельзя удалить последний список.")
    del ch["lists"][ch["current_list"]]
    ch["current_list"] = next(iter(ch["lists"])); _save()
    bot.send_message(cid, "🗑 Список удалён", reply_markup=_menu())

# ──────── list ideas ────────
def _list_ideas(cid: int):
    cur = _cur(cid)
    if not cur["ideas"]:
        return bot.send_message(cid, "📭 В этом списке пока нет идей.")
    used = set(cur["history"]); header=f"<b>{html.escape(cur['name'])}</b>\n\n"
    body = _format_ideas_html(cur["ideas"], used)
    for chunk in (body[i:i+4000] for i in range(0, len(body), 4000)):
        bot.send_message(cid, header + chunk, parse_mode="HTML"); header=""

# ──────── command handlers ────────
@bot.message_handler(commands=["start", "help"])
def start(m):
    bot.send_message(m.chat.id,
        "👋 Бот идей.\n\n"
        "Примеры добавления:\n"
        "• /addidea Катание https://wake.ru\n"
        "• /addplace 2 Парк https://ostrov.rf\n",
        reply_markup=_menu())

@bot.message_handler(commands=["idea"])
def cmd_idea(m): _send_rand(m.chat.id)

@bot.message_handler(commands=["addidea"])
def cmd_addidea(m):
    txt = (m.html_text or m.text).split(" ", 1)
    if len(txt) < 2:
        return bot.reply_to(m, "⚠️ После команды введите текст идеи.")
    _add_idea(m.chat.id, txt[1].strip())

@bot.message_handler(commands=["addplace"])
def cmd_addplace(m):
    parsed = _parse_place_msg((m.html_text or m.text).replace("/addplace", "", 1))
    if not parsed:
        return bot.reply_to(m, "⚠️ Формат: /addplace ID место")
    _add_place(m.chat.id, *parsed)

@bot.message_handler(commands=["deleteidea"])
def cmd_delidea(m): _del_idea(m.chat.id, m.text.split(" ", 1)[-1])

@bot.message_handler(commands=["deleteplace"])
def cmd_delplace(m):
    p = m.text.split()
    if len(p) != 3 or not (p[1].isdigit() and p[2].isdigit()):
        return bot.reply_to(m, "⚠️ Формат: /deleteplace ID номер")
    _del_place(m.chat.id, int(p[1]), int(p[2]))

@bot.message_handler(commands=["listideas"])
def cmd_listideas(m): _list_ideas(m.chat.id)

# ──────── callback handlers ────────
@bot.callback_query_handler(func=lambda _:_)
def cb(call):
    d, cid = call.data, call.message.chat.id
    if d == "get": _send_rand(cid)
    elif d == "addidea":
        msg = bot.send_message(cid, "✏️ Текст идеи (после пробела можно добавить ссылку):", parse_mode="HTML")
        bot.register_next_step_handler(msg, lambda m:_add_idea(cid, (m.html_text or m.text).strip()))
    elif d == "addplace":
        msg = bot.send_message(cid,
            "✏️ Одно сообщение: `номер_идеи текст [ссылка]`\n"
            "Пример: `3 Кафе https://cafe.ru`", parse_mode="Markdown")
        bot.register_next_step_handler(msg, lambda m:_handle_place(cid, m))
    elif d == "delidea":
        msg = bot.send_message(cid, "🗑 Номер идеи?")
        bot.register_next_step_handler(msg, lambda m:_del_idea(cid, m.text))
    elif d == "delplace":
        msg = bot.send_message(cid, "🗑 Введите `номер_идеи номер_места`")
        bot.register_next_step_handler(msg, lambda m:_handle_delplace(cid, m.text))
    elif d == "list": _list_ideas(cid)
    elif d == "lists": _show_lists(cid)
    elif d.startswith("use:"):
        _chat(cid)["current_list"] = d.split(":", 1)[1]; _save()
        bot.edit_message_reply_markup(cid, call.message.id, reply_markup=_menu())
    elif d == "newlist":
        msg = bot.send_message(cid, "📋 Название списка:", parse_mode="HTML")
        bot.register_next_step_handler(msg, lambda m:_create_list(cid, (m.html_text or m.text).strip()))
    elif d == "dellist": _delete_list(cid)

# ──────── post-callback helpers ────────
def _handle_place(cid, m):
    parsed = _parse_place_msg(m.html_text or m.text)
    if not parsed:
        return bot.reply_to(m, "⚠️ Формат: номер_идеи текст [ссылка]")
    _add_place(cid, *parsed)

def _handle_delplace(cid, txt):
    p = txt.split()
    if len(p) != 2 or not (p[0].isdigit() and p[1].isdigit()):
        return bot.send_message(cid, "⚠️ Формат: номер_идеи номер_места")
    _del_place(cid, int(p[0]), int(p[1]))

# ──────── run ────────
if __name__ == "__main__":
    bot.polling(skip_pending=True)
