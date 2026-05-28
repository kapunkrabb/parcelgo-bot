import logging
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (Application, CommandHandler, CallbackQueryHandler,
                           ConversationHandler, ContextTypes, MessageHandler, filters)
from database import db
from config import TOKEN, ADMIN_ID, CARD_NUMBER, CARD_HOLDER

CHANNEL_ID = "@parcelgo_board"

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
log = logging.getLogger(__name__)

(MAIN, S_ROUTE, S_CUSTOM, S_TYPE, S_SIZE, S_CONFIRM,
 T_ROUTE, T_CUSTOM, T_DATE, T_WEIGHT, T_CONFIRM,
 FREE_POST, SEARCH_FROM, SEARCH_TO, REVIEW_WHO, REVIEW_STARS,
 PHONE_VERIFY) = range(17)

ROUTES = [
    ("🇦🇪","Москва → Дубай"),
    ("🇹🇷","Москва → Стамбул"),
    ("🇹🇭","Москва → Пхукет"),
    ("🇬🇪","Москва → Тбилиси"),
    ("🇦🇲","Москва → Ереван"),
    ("🇬🇧","Москва → Лондон"),
    ("🇩🇪","Москва → Берлин"),
    ("🇮🇩","Москва → Бали"),
]
TYPES   = [("📱","Техника"),("👗","Одежда"),("💊","Лекарства"),("📄","Документы"),("🎁","Подарок"),("💄","Косметика"),("🍫","Еда"),("📦","Другое")]
SIZES   = ["📦 Маленькая (рюкзак)","🎒 Средняя (сумка)","🧳 Большая (чемодан)","📫 Крупногабаритная"]
DATES   = ["Сегодня","Завтра","Через 2–3 дня","На этой неделе","На следующей неделе","В течение месяца"]
TWEIGHTS= ["до 1 кг","1–3 кг","3–5 кг","5–10 кг","10+ кг"]
STARS   = ["⭐ 1","⭐⭐ 2","⭐⭐⭐ 3","⭐⭐⭐⭐ 4","⭐⭐⭐⭐⭐ 5"]

def contact_button(label, username):
    return InlineKeyboardButton(label, url=f"https://t.me/{username}")

def contact_label(name, username):
    return f"@{username}" if username else name

def stars_str(rating):
    return "⭐" * round(rating) if rating else "нет отзывов"

async def publish_to_channel(bot, text, username=None, btn_label=None):
    try:
        kb = []
        if username and btn_label:
            kb.append([InlineKeyboardButton(btn_label, url=f"https://t.me/{username}")])
        await bot.send_message(CHANNEL_ID, text, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(kb) if kb else None)
    except Exception as e:
        log.warning(f"Канал: {e}")

def is_verified(uid):
    u = db.get_user(uid)
    return u and u.get("phone")

# ── ВЕРИФИКАЦИЯ ───────────────────────────────────────────────────────────────
async def verify_phone(update, ctx):
    user = update.effective_user
    db.upsert_user(user.id, user.first_name, user.username)
    if is_verified(user.id):
        return await start(update, ctx)
    phone_kb = ReplyKeyboardMarkup(
        [[KeyboardButton("📱 Поделиться номером телефона", request_contact=True)]],
        resize_keyboard=True, one_time_keyboard=True)
    msg = update.message or (update.callback_query and update.callback_query.message)
    if msg:
        await msg.reply_text(
            "👋 Добро пожаловать в *ParcelGo*!\n━━━━━━━━━━━━━━━━━━━━\n\n"
            "🔐 *Верификация по номеру телефона*\n\n"
            "Для защиты от мошенников нам нужен ваш номер.\n\n"
            "Нажмите кнопку ниже — Telegram поделится номером автоматически.\n\n"
            "🔒 Номер хранится только в нашей базе данных.",
            parse_mode="Markdown", reply_markup=phone_kb)
    return PHONE_VERIFY

async def handle_phone(update, ctx):
    contact = update.message.contact
    if not contact:
        await update.message.reply_text("Пожалуйста используйте кнопку ниже.",
            reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton("📱 Поделиться номером телефона", request_contact=True)]],
                resize_keyboard=True, one_time_keyboard=True))
        return PHONE_VERIFY
    user = update.effective_user
    phone = contact.phone_number
    db.conn.execute("UPDATE users SET phone=? WHERE id=?", (phone, user.id))
    db.conn.commit()
    await update.message.reply_text(
        f"✅ *Верификация пройдена!*\n\nТелефон сохранён. Добро пожаловать!",
        parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())
    return await start(update, ctx)

# ── ГЛАВНОЕ МЕНЮ ──────────────────────────────────────────────────────────────
async def start(update, ctx):
    user = update.effective_user
    db.upsert_user(user.id, user.first_name, user.username)
    if not is_verified(user.id):
        return await verify_phone(update, ctx)
    name = user.first_name or "друг"
    u = db.get_user(user.id)
    rating_str = f" | ⭐{u['rating']:.1f}" if u and u.get('trips_count') else ""
    no_username = "\n\n⚠️ У вас нет @username — другие не смогут написать вам. Установите его в настройках Telegram." if not user.username else ""
    text = (f"✦ *ParcelGo* ✦\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Привет, *{name}* 👋{rating_str}{no_username}\n\n"
            f"Сводим отправителей и попутчиков напрямую —\nбыстро, удобно, бесплатно.\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\nЧто хочешь сделать? 👇")
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 Открыть приложение", web_app=WebAppInfo(url="https://kapunkrabb.github.io/parcelgo-app"))],
        [InlineKeyboardButton("📦 Отправить посылку", callback_data="send")],
        [InlineKeyboardButton("✈️ Я путешественник — возьму посылку", callback_data="travel")],
        [InlineKeyboardButton("🔍 Найти по маршруту", callback_data="search")],
        [InlineKeyboardButton("✍️ Написать объявление", callback_data="freepost")],
        [InlineKeyboardButton("📢 Доска объявлений", url="https://t.me/parcelgo_board")],
        [InlineKeyboardButton("📋 Мои заявки", callback_data="my"), InlineKeyboardButton("⭐ Отзывы", callback_data="review_start")],
        [InlineKeyboardButton("❓ Как работает", callback_data="how"), InlineKeyboardButton("🚫 Стоп-лист", callback_data="blacklist")],
    ])
    if update.message:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)
    elif update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)
    return MAIN

async def how(update, ctx):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        "❓ *Как это работает*\n━━━━━━━━━━━━━━━━━━━━\n\n"
        "*📦 Отправить посылку:*\n1️⃣ Выбери маршрут\n2️⃣ Укажи тип и размер\n"
        "3️⃣ Бот найдёт попутчиков и уведомит\n4️⃣ Договорись напрямую\n\n"
        "*✈️ Заработать как попутчик:*\n1️⃣ Укажи маршрут и дату\n"
        "2️⃣ Бот найдёт посылки\n3️⃣ Договорись и получи оплату\n\n"
        "*🔍 Поиск:* введи маршрут — увидишь всех\n\n"
        "*⭐ Отзывы:* оставляй после сделки — повышает доверие\n\n"
        "*🛡 Безопасность:*\n• Верификация по телефону\n• Стоп-лист мошенников\n• Деньги напрямую между людьми",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("← Назад", callback_data="back_main")]]))

async def my_req(update, ctx):
    if update.callback_query:
        await update.callback_query.answer()
    uid = update.effective_user.id
    reqs = db.get_user_requests(uid)
    trips = db.get_user_trips(uid)
    u = db.get_user(uid)
    if not reqs and not trips:
        text = "📋 *Мои заявки*\n━━━━━━━━━━━━━━━━━━━━\n\nПока нет активных заявок."
    else:
        lines = ["📋 *Мои заявки*\n━━━━━━━━━━━━━━━━━━━━"]
        if u:
            lines.append(f"⭐ Рейтинг: {u['rating']:.1f} ({u['trips_count']} отзывов)")
        if reqs:
            lines.append("\n*📦 Посылки:*")
            for r in reqs:
                e = {"pending":"⏳","matched":"🤝","completed":"✅","cancelled":"❌"}.get(r["status"],"❓")
                lines.append(f"{e} {r['from_city']} → {r['to_city']} | {r['weight']}")
        if trips:
            lines.append("\n*✈️ Мои рейсы:*")
            for t in trips:
                lines.append(f"🛫 {t['from_city']} → {t['to_city']} | {t['date']}")
        text = "\n".join(lines)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("⭐ Оставить отзыв", callback_data="review_start")],
        [InlineKeyboardButton("🗑 Отменить заявку", callback_data="cancel_menu")],
        [InlineKeyboardButton("← Назад", callback_data="back_main")]])
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)
    else:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)

async def bl(update, ctx):
    await update.callback_query.answer()
    rows = db.conn.execute(
        "SELECT bl.*, u.name FROM blacklist bl JOIN users u ON bl.user_id=u.id "
        "WHERE bl.is_public=1 ORDER BY bl.banned_at DESC LIMIT 10").fetchall()
    text = ("🚫 *Стоп-лист*\n━━━━━━━━━━━━━━━━━━━━\n\n✅ Список пуст!" if not rows else
            "🚫 *Стоп-лист*\n━━━━━━━━━━━━━━━━━━━━\n\n" +
            "\n".join(f"❌ *{r['name']}* — {r['reason']}\n   📅 {r['banned_at'][:10]}" for r in rows))
    await update.callback_query.edit_message_text(text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("← Назад", callback_data="back_main")]]))

# ── ОТМЕНА ЗАЯВКИ ─────────────────────────────────────────────────────────────
async def cancel_menu_cb(update, ctx):
    await update.callback_query.answer()
    uid = update.effective_user.id
    reqs = [r for r in db.get_user_requests(uid) if r["status"] == "pending"]
    trips = [t for t in db.get_user_trips(uid) if t["status"] == "active"]
    if not reqs and not trips:
        await update.callback_query.edit_message_text("Нет активных заявок для отмены.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("← Назад", callback_data="my")]]))
        return
    kb = []
    for r in reqs:
        kb.append([InlineKeyboardButton(f"❌ Посылка: {r['from_city']} → {r['to_city']}", callback_data=f"cancel_req_{r['id']}")])
    for t in trips:
        kb.append([InlineKeyboardButton(f"❌ Рейс: {t['from_city']} → {t['to_city']} | {t['date']}", callback_data=f"cancel_trip_{t['id']}")])
    kb.append([InlineKeyboardButton("← Назад", callback_data="my")])
    await update.callback_query.edit_message_text("🗑 *Что отменить?*\n━━━━━━━━━━━━━━━━━━━━",
        parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))

async def cancel_req_cb(update, ctx):
    await update.callback_query.answer()
    req_id = int(update.callback_query.data.split("_")[2])
    uid = update.effective_user.id
    req = db.get_request(req_id)
    if req and req["user_id"] == uid:
        db.update_request_status(req_id, "cancelled")
        await update.callback_query.edit_message_text("✅ Заявка отменена.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Меню", callback_data="back_main")]]))
    else:
        await update.callback_query.edit_message_text("❌ Заявка не найдена.")

async def cancel_trip_cb(update, ctx):
    await update.callback_query.answer()
    trip_id = int(update.callback_query.data.split("_")[2])
    uid = update.effective_user.id
    trip = db.get_trip(trip_id)
    if trip and trip["user_id"] == uid:
        db.conn.execute("UPDATE trips SET status='cancelled' WHERE id=?", (trip_id,))
        db.conn.commit()
        await update.callback_query.edit_message_text("✅ Рейс отменён.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Меню", callback_data="back_main")]]))

# ── ПОИСК ─────────────────────────────────────────────────────────────────────
async def search_start(update, ctx):
    await update.callback_query.answer()
    ctx.user_data.clear()
    await update.callback_query.edit_message_text(
        "🔍 *Поиск по маршруту*\n━━━━━━━━━━━━━━━━━━━━\n\n*Шаг 1 из 2* — Откуда?\n_Введи город:_",
        parse_mode="Markdown")
    return SEARCH_FROM

async def search_from(update, ctx):
    ctx.user_data["search_from"] = update.message.text.strip()
    await update.message.reply_text(
        f"✅ Откуда: *{ctx.user_data['search_from']}*\n\n*Шаг 2 из 2* — Куда?\n_Введи город:_",
        parse_mode="Markdown")
    return SEARCH_TO

async def search_to(update, ctx):
    from_city = ctx.user_data.get("search_from","")
    to_city = update.message.text.strip()
    travelers = db.find_travelers(from_city, to_city)
    requests = db.find_matches_for_trip(from_city, to_city)
    lines = [f"🔍 *{from_city} → {to_city}*\n━━━━━━━━━━━━━━━━━━━━"]
    if travelers:
        lines.append(f"\n✈️ *Попутчики ({len(travelers)}):*")
        for t in travelers:
            lines.append(f"• {contact_label(t['name'],t['username'])} | {t['date']} | ⚖️ {t['weight']}")
    else:
        lines.append("\n✈️ Попутчиков нет")
    if requests:
        lines.append(f"\n📦 *Посылки ({len(requests)}):*")
        for r in requests:
            lines.append(f"• {contact_label(r['sender_name'],r['username'])} | 📐 {r['weight']}")
    else:
        lines.append("\n📦 Посылок нет")
    kb = []
    for t in travelers:
        if t.get("username"):
            kb.append([contact_button(f"💬 Написать попутчику @{t['username']}", t["username"])])
    for r in requests:
        if r.get("username"):
            kb.append([contact_button(f"💬 Написать отправителю @{r['username']}", r["username"])])
    kb.append([InlineKeyboardButton("🏠 Главное меню", callback_data="back_main")])
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(kb))
    return ConversationHandler.END

# ── ОТЗЫВЫ ────────────────────────────────────────────────────────────────────
async def review_start(update, ctx):
    await update.callback_query.answer()
    ctx.user_data.clear()
    await update.callback_query.edit_message_text(
        "⭐ *Оставить отзыв*\n━━━━━━━━━━━━━━━━━━━━\n\nВведи *@username* человека:",
        parse_mode="Markdown")
    return REVIEW_WHO

async def review_who(update, ctx):
    username = update.message.text.strip().lstrip("@")
    row = db.conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    if not row:
        await update.message.reply_text("❌ Пользователь не найден. Попробуй ещё раз:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Меню", callback_data="back_main")]]))
        return REVIEW_WHO
    ctx.user_data["review_target_id"] = row["id"]
    ctx.user_data["review_target_name"] = row["name"]
    kb = [[InlineKeyboardButton(s, callback_data=f"star_{i+1}")] for i,s in enumerate(STARS)]
    kb.append([InlineKeyboardButton("← Отмена", callback_data="back_main")])
    await update.message.reply_text(
        f"👤 *{row['name']}* (@{username})\n\nВыбери оценку:",
        parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
    return REVIEW_STARS

async def review_stars(update, ctx):
    await update.callback_query.answer()
    stars = int(update.callback_query.data.split("_")[1])
    uid = update.effective_user.id
    target_id = ctx.user_data.get("review_target_id")
    if uid == target_id:
        await update.callback_query.edit_message_text("❌ Нельзя оставить отзыв самому себе.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Меню", callback_data="back_main")]]))
        return ConversationHandler.END
    db.add_review(uid, target_id, 0, stars)
    updated = db.get_user(target_id)
    await update.callback_query.edit_message_text(
        f"✅ *Отзыв отправлен!*\n\n{'⭐'*stars} ({stars}/5)\n"
        f"Новый рейтинг: {updated['rating']:.1f} ({updated['trips_count']} отзывов)",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Главное меню", callback_data="back_main")]]))
    try:
        reviewer = update.effective_user
        await ctx.bot.send_message(target_id,
            f"⭐ *Новый отзыв!*\n\n{'⭐'*stars} от {contact_label(reviewer.first_name,reviewer.username)}\n"
            f"Рейтинг: {updated['rating']:.1f}",
            parse_mode="Markdown")
    except: pass
    return ConversationHandler.END

# ── СВОБОДНОЕ ОБЪЯВЛЕНИЕ ──────────────────────────────────────────────────────
async def free_post_start(update, ctx):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        "✍️ *Свободное объявление*\n━━━━━━━━━━━━━━━━━━━━\n\n"
        "Напиши своё объявление в свободной форме:\n\n"
        "_Например: Лечу Москва → Пхукет 15 июня, возьму посылку до 3 кг, пишите!_",
        parse_mode="Markdown")
    return FREE_POST

async def free_post_send(update, ctx):
    user = update.effective_user
    text = update.message.text.strip()
    if len(text) < 10:
        await update.message.reply_text("❌ Слишком короткое. Напиши подробнее:")
        return FREE_POST
    author = contact_label(user.first_name, user.username)
    await publish_to_channel(ctx.bot,
        f"📣 *Объявление*\n━━━━━━━━━━━━━━━━━━━━\n\n{text}\n\n👤 Автор: {author}",
        user.username, "💬 Написать автору")
    await update.message.reply_text("✅ Объявление опубликовано в @parcelgo_board!",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Меню", callback_data="back_main")]]))
    return ConversationHandler.END

# ── ОТПРАВИТЕЛЬ ───────────────────────────────────────────────────────────────
async def send_start(update, ctx):
    await update.callback_query.answer()
    ctx.user_data.clear()
    kb = [[InlineKeyboardButton(f"{e} {n}", callback_data=f"sr_{i}")] for i,(e,n) in enumerate(ROUTES)]
    kb.append([InlineKeyboardButton("✏️ Свой маршрут", callback_data="srcustom")])
    kb.append([InlineKeyboardButton("← Назад", callback_data="back_main")])
    await update.callback_query.edit_message_text(
        "📦 *Отправить посылку*\n━━━━━━━━━━━━━━━━━━━━\n\n"
        "*Шаг 1 из 3* — Выбери маршрут 🗺\n_На следующем шаге можно изменить направление_ 🔄",
        parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
    return S_ROUTE

async def s_custom(update, ctx):
    await update.callback_query.answer()
    ctx.user_data["waiting_custom_route"] = "sender"
    await update.callback_query.edit_message_text(
        "📦 *Свой маршрут*\n━━━━━━━━━━━━━━━━━━━━\n\n"
        "Напиши в формате: *Город → Город*\n\n"
        "Примеры:\n• Москва → Алматы\n• Ташкент → Москва\n• Нью-Йорк → Лондон\n\n"
        "_Используй стрелку → между городами_",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("← Назад", callback_data="send")]]))
    return S_CUSTOM

async def s_route(update, ctx):
    await update.callback_query.answer()
    data = update.callback_query.data
    if data.startswith("sr_flip_"):
        idx = int(data.split("_")[2])
        route = ctx.user_data.get("route","")
        parts = route.split("→")
        if len(parts) == 2:
            a = parts[0].strip()
            b = parts[1].strip()
            # Strip emoji from city a
            a_clean = a
            for e,n in ROUTES:
                a_clean = a_clean.replace(e,"").strip()
            ctx.user_data["route"] = f"{ROUTES[idx][0]} {b} → {a_clean}"
    else:
        idx = int(data.split("_")[1])
        ctx.user_data["route"] = f"{ROUTES[idx][0]} {ROUTES[idx][1]}"
        ctx.user_data["route_idx"] = idx

    idx = ctx.user_data.get("route_idx", 0)
    route = ctx.user_data["route"]
    kb = []
    for i in range(0, len(TYPES), 2):
        row = [InlineKeyboardButton(f"{TYPES[i][0]} {TYPES[i][1]}", callback_data=f"st_{i}")]
        if i+1 < len(TYPES):
            row.append(InlineKeyboardButton(f"{TYPES[i+1][0]} {TYPES[i+1][1]}", callback_data=f"st_{i+1}"))
        kb.append(row)
    kb.append([InlineKeyboardButton("🔄 Изменить направление", callback_data=f"sr_flip_{idx}")])
    kb.append([InlineKeyboardButton("← Назад", callback_data="send")])
    await update.callback_query.edit_message_text(
        f"📦 *Отправить посылку*\n━━━━━━━━━━━━━━━━━━━━\n\n✅ {route}\n\n*Шаг 2 из 3* — Что отправляешь? 📦",
        parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
    return S_TYPE

async def s_type(update, ctx):
    await update.callback_query.answer()
    idx = int(update.callback_query.data.split("_")[1])
    ctx.user_data["type"] = f"{TYPES[idx][0]} {TYPES[idx][1]}"
    kb = [[InlineKeyboardButton(s, callback_data=f"ss_{i}")] for i,s in enumerate(SIZES)]
    kb.append([InlineKeyboardButton("← Назад", callback_data=f"sr_{ctx.user_data.get('route_idx',0)}")])
    await update.callback_query.edit_message_text(
        f"📦 *Отправить посылку*\n━━━━━━━━━━━━━━━━━━━━\n\n✅ {ctx.user_data['route']}\n✅ {ctx.user_data['type']}\n\n*Шаг 3 из 3* — Размер посылки 📐",
        parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
    return S_SIZE

async def s_size(update, ctx):
    await update.callback_query.answer()
    idx = int(update.callback_query.data.split("_")[1])
    ctx.user_data["size"] = SIZES[idx]
    d = ctx.user_data
    await update.callback_query.edit_message_text(
        f"📦 *Подтверди заявку*\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🗺 {d['route']}\n📦 {d['type']}\n📐 {d['size']}\n💰 Цена по договорённости\n\nВсё верно?",
        parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Создать заявку", callback_data="sc")],
            [InlineKeyboardButton("✏️ Изменить", callback_data="send")]]))
    return S_CONFIRM

async def s_confirm(update, ctx):
    await update.callback_query.answer()
    d = ctx.user_data
    uid = update.effective_user.id
    user = update.effective_user
    parts = d["route"].split("→")
    from_city = parts[0].strip()
    for e,n in ROUTES:
        from_city = from_city.replace(e,"").strip()
    to_city = parts[1].strip() if len(parts)>1 else ""

    req_id = db.add_request(uid, from_city, to_city, d["size"], d["type"], "договорная")
    travelers = db.find_travelers(from_city, to_city)
    sender_label = contact_label(user.first_name, user.username)

    await publish_to_channel(ctx.bot,
        f"📦 *Нужен попутчик!*\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🗺 {d['route']}\n📦 {d['type']} | 📐 {d['size']}\n💰 Цена по договорённости\n\n"
        f"👤 Отправитель: {sender_label}",
        user.username, "💬 Написать отправителю")

    if travelers:
        lines = [f"✅ *Заявка #{req_id} создана!*\n\n🗺 {d['route']}\n\n🎉 *Найдено попутчиков: {len(travelers)}*\n━━━━━━━━━━━━━━━━━━━━"]
        kb = []
        for t in travelers:
            label = contact_label(t["name"], t["username"])
            lines.append(f"\n✈️ {label} | {t['date']} | ⚖️ {t['weight']}")
            if t["username"]:
                kb.append([contact_button(f"💬 Написать {label}", t["username"])])
        kb.append([InlineKeyboardButton("🏠 Меню", callback_data="back_main")])
        await update.callback_query.edit_message_text("\n".join(lines), parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(kb))
        for t in travelers:
            if t["user_id"] == uid: continue
            try:
                t_kb = []
                if user.username:
                    t_kb.append([contact_button("💬 Написать отправителю", user.username)])
                t_kb.append([InlineKeyboardButton("⭐ Оставить отзыв", callback_data="review_start")])
                await ctx.bot.send_message(t["user_id"],
                    f"📦 *Новая посылка по вашему маршруту!*\n\n🗺 {d['route']}\n📦 {d['type']} | 📐 {d['size']}\n\n👤 {sender_label}",
                    parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(t_kb))
            except: pass
    else:
        await update.callback_query.edit_message_text(
            f"✅ *Заявка #{req_id} создана!*\n\n🗺 {d['route']}\n📦 {d['type']} | 📐 {d['size']}\n\n"
            f"🔍 Ищем попутчиков...\n📢 Объявление опубликовано в @parcelgo_board",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Меню", callback_data="back_main")]]))
    try:
        await ctx.bot.send_message(ADMIN_ID,
            f"📦 Заявка #{req_id}\nОт: {user.first_name} (@{user.username})\n{d['route']} | {d['type']} | {d['size']}\nПопутчиков: {len(travelers)}")
    except: pass
    return ConversationHandler.END

# ── ПОПУТЧИК ──────────────────────────────────────────────────────────────────
async def travel_start(update, ctx):
    await update.callback_query.answer()
    ctx.user_data.clear()
    kb = [[InlineKeyboardButton(f"{e} {n}", callback_data=f"tr_{i}")] for i,(e,n) in enumerate(ROUTES)]
    kb.append([InlineKeyboardButton("✏️ Свой маршрут", callback_data="trcustom")])
    kb.append([InlineKeyboardButton("← Назад", callback_data="back_main")])
    await update.callback_query.edit_message_text(
        "✈️ *Регистрация рейса*\n━━━━━━━━━━━━━━━━━━━━\n\nВозьми посылку и помоги!\n\n"
        "*Шаг 1 из 3* — Твой маршрут 🗺\n_На следующем шаге можно изменить направление_ 🔄",
        parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
    return T_ROUTE

async def t_custom(update, ctx):
    await update.callback_query.answer()
    ctx.user_data["waiting_custom_route"] = "traveler"
    await update.callback_query.edit_message_text(
        "✈️ *Свой маршрут*\n━━━━━━━━━━━━━━━━━━━━\n\n"
        "Напиши в формате: *Город → Город*\n\n"
        "Примеры:\n• Москва → Алматы\n• Бангкок → Москва\n• Дубай → Тбилиси",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("← Назад", callback_data="travel")]]))
    return T_CUSTOM

async def t_route(update, ctx):
    await update.callback_query.answer()
    data = update.callback_query.data
    if data.startswith("tr_flip_"):
        idx = int(data.split("_")[2])
        route = ctx.user_data.get("route","")
        parts = route.split("→")
        if len(parts) == 2:
            a = parts[0].strip()
            b = parts[1].strip()
            for e,n in ROUTES:
                a = a.replace(e,"").strip()
            ctx.user_data["route"] = f"{ROUTES[idx][0]} {b} → {a}"
    else:
        idx = int(data.split("_")[1])
        ctx.user_data["route"] = f"{ROUTES[idx][0]} {ROUTES[idx][1]}"
        ctx.user_data["route_idx"] = idx

    idx = ctx.user_data.get("route_idx", 0)
    route = ctx.user_data["route"]
    kb = [[InlineKeyboardButton(d, callback_data=f"td_{i}")] for i,d in enumerate(DATES)]
    kb.append([InlineKeyboardButton("🔄 Изменить направление", callback_data=f"tr_flip_{idx}")])
    kb.append([InlineKeyboardButton("← Назад", callback_data="travel")])
    await update.callback_query.edit_message_text(
        f"✈️ *Регистрация рейса*\n━━━━━━━━━━━━━━━━━━━━\n\n✅ {route}\n\n*Шаг 2 из 3* — Когда едешь? 📅",
        parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
    return T_DATE

async def t_date(update, ctx):
    await update.callback_query.answer()
    idx = int(update.callback_query.data.split("_")[1])
    ctx.user_data["date"] = DATES[idx]
    kb = [[InlineKeyboardButton(w, callback_data=f"tw_{i}")] for i,w in enumerate(TWEIGHTS)]
    kb.append([InlineKeyboardButton("← Назад", callback_data=f"tr_{ctx.user_data.get('route_idx',0)}")])
    await update.callback_query.edit_message_text(
        f"✈️ *Регистрация рейса*\n━━━━━━━━━━━━━━━━━━━━\n\n✅ {ctx.user_data['route']}\n✅ {ctx.user_data['date']}\n\n*Шаг 3 из 3* — Сколько кг возьмёшь? ⚖️",
        parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
    return T_WEIGHT

async def t_weight(update, ctx):
    await update.callback_query.answer()
    idx = int(update.callback_query.data.split("_")[1])
    ctx.user_data["weight"] = TWEIGHTS[idx]
    d = ctx.user_data
    await update.callback_query.edit_message_text(
        f"✈️ *Подтверди рейс*\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🗺 {d['route']}\n📅 {d['date']}\n⚖️ {d['weight']}\n💰 Цена по договорённости\n\nВсё верно?",
        parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Зарегистрировать рейс", callback_data="tc")],
            [InlineKeyboardButton("✏️ Изменить", callback_data="travel")]]))
    return T_CONFIRM

async def t_confirm(update, ctx):
    await update.callback_query.answer()
    d = ctx.user_data
    uid = update.effective_user.id
    user = update.effective_user
    parts = d["route"].split("→")
    from_city = parts[0].strip()
    for e,n in ROUTES:
        from_city = from_city.replace(e,"").strip()
    to_city = parts[1].strip() if len(parts)>1 else ""

    trip_id = db.add_trip(uid, from_city, to_city, d["date"], d["weight"], "договорная", "—")
    matches = db.find_matches_for_trip(from_city, to_city)
    traveler_label = contact_label(user.first_name, user.username)

    await publish_to_channel(ctx.bot,
        f"✈️ *Возьму посылку!*\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🗺 {d['route']}\n📅 {d['date']} | ⚖️ до {d['weight']}\n💰 Цена по договорённости\n\n"
        f"👤 Попутчик: {traveler_label}",
        user.username, "💬 Написать попутчику")

    if matches:
        lines = [f"✅ *Рейс #{trip_id} зарегистрирован!*\n\n🗺 {d['route']}\n\n🎉 *Найдено заявок: {len(matches)}*\n━━━━━━━━━━━━━━━━━━━━"]
        kb = []
        for m in matches:
            sender_label = contact_label(m["sender_name"], m["username"])
            lines.append(f"\n📦 {sender_label} | 📐 {m['weight']}")
            if m["username"]:
                kb.append([contact_button(f"💬 Написать {sender_label}", m["username"])])
        kb.append([InlineKeyboardButton("🏠 Меню", callback_data="back_main")])
        await update.callback_query.edit_message_text("\n".join(lines), parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(kb))
        for m in matches:
            if m["user_id"] == uid: continue
            try:
                s_kb = []
                if user.username:
                    s_kb.append([contact_button("💬 Написать попутчику", user.username)])
                s_kb.append([InlineKeyboardButton("⭐ Оставить отзыв", callback_data="review_start")])
                await ctx.bot.send_message(m["user_id"],
                    f"🎉 *Найден попутчик!*\n\n✈️ {d['route']}\n📅 {d['date']} | ⚖️ {d['weight']}\n\n👤 {traveler_label}",
                    parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(s_kb))
            except: pass
    else:
        await update.callback_query.edit_message_text(
            f"✅ *Рейс #{trip_id} зарегистрирован!*\n\n🗺 {d['route']}\n📅 {d['date']} | ⚖️ {d['weight']}\n\n"
            f"📭 Уведомим когда появятся посылки!\n📢 Объявление в @parcelgo_board",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Меню", callback_data="back_main")]]))
    try:
        await ctx.bot.send_message(ADMIN_ID,
            f"✈️ Рейс #{trip_id}\nОт: {user.first_name} (@{user.username})\n{d['route']} | {d['date']}\nВес: {d['weight']}\nЗаявок: {len(matches)}")
    except: pass
    return ConversationHandler.END

# ── СВОЙ МАРШРУТ (текст) ─────────────────────────────────────────────────────
async def handle_custom_route(update, ctx):
    text = update.message.text.strip()
    if "→" not in text and "->" not in text:
        await update.message.reply_text(
            "❌ Неверный формат.\n\nИспользуй стрелку: *Город → Город*\n_Например: Москва → Алматы_",
            parse_mode="Markdown")
        return S_CUSTOM if ctx.user_data.get("waiting_custom_route") == "sender" else T_CUSTOM
    text = text.replace("->", "→")
    ctx.user_data["route"] = text
    ctx.user_data["route_idx"] = 0
    role = ctx.user_data.get("waiting_custom_route","sender")
    if role == "traveler":
        kb = [[InlineKeyboardButton(d, callback_data=f"td_{i}")] for i,d in enumerate(DATES)]
        kb.append([InlineKeyboardButton("← Назад", callback_data="travel")])
        await update.message.reply_text(
            f"✈️ *Регистрация рейса*\n\n✅ {text}\n\n*Шаг 2 из 3* — Когда едешь? 📅",
            parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        return T_DATE
    else:
        kb = []
        for i in range(0, len(TYPES), 2):
            row = [InlineKeyboardButton(f"{TYPES[i][0]} {TYPES[i][1]}", callback_data=f"st_{i}")]
            if i+1 < len(TYPES):
                row.append(InlineKeyboardButton(f"{TYPES[i+1][0]} {TYPES[i+1][1]}", callback_data=f"st_{i+1}"))
            kb.append(row)
        kb.append([InlineKeyboardButton("← Назад", callback_data="send")])
        await update.message.reply_text(
            f"📦 *Отправить посылку*\n\n✅ {text}\n\n*Шаг 2 из 3* — Что отправляешь? 📦",
            parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        return S_TYPE

# ── МИНИ-АПП ──────────────────────────────────────────────────────────────────
async def handle_webapp(update, ctx):
    try:
        data = json.loads(update.message.web_app_data.data)
        user = update.effective_user
        uid = user.id
        db.upsert_user(uid, user.first_name, user.username)
        author = contact_label(user.first_name, user.username)

        if data.get("type") == "send":
            from_city = data.get("from","")
            to_city = data.get("to","")
            item = data.get("item","")
            size = data.get("size","")
            date_str = data.get("date","")
            note = data.get("note","")
            date_part = f" | до {date_str}" if date_str else ""
            note_part = f"\n📝 {note}" if note else ""
            req_id = db.add_request(uid, from_city, to_city, size, item, "договорная")
            await publish_to_channel(ctx.bot,
                f"📦 *Нужен попутчик!*\n━━━━━━━━━━━━━━━━━━━━\n\n"
                f"🗺 {from_city} → {to_city}\n📦 {item} | 📐 {size}{date_part}\n"
                f"💰 Цена по договорённости{note_part}\n\n👤 {author}",
                user.username, "💬 Написать отправителю")
            travelers = db.find_travelers(from_city, to_city)
            if travelers:
                kb = []
                for t in travelers:
                    if t["username"]:
                        kb.append([contact_button(f"💬 Написать @{t['username']}", t["username"])])
                kb.append([InlineKeyboardButton("📢 Канал", url="https://t.me/parcelgo_board")])
                await update.message.reply_text(
                    f"✅ Заявка #{req_id} создана!\n🎉 Найдено попутчиков: {len(travelers)}",
                    reply_markup=InlineKeyboardMarkup(kb))
            else:
                await update.message.reply_text(
                    f"✅ Заявка #{req_id} создана!\n🔍 Ищем попутчиков...\n📢 Объявление в @parcelgo_board",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📢 Канал", url="https://t.me/parcelgo_board")]]))

        elif data.get("type") == "travel":
            from_city = data.get("from","")
            to_city = data.get("to","")
            date_str = data.get("date","")
            weight = data.get("weight","")
            transport = data.get("transport","")
            note_part = f"\n📝 {data.get('note','')}" if data.get("note") else ""
            trip_id = db.add_trip(uid, from_city, to_city, date_str, weight, "договорная","—")
            await publish_to_channel(ctx.bot,
                f"✈️ *Возьму посылку!*\n━━━━━━━━━━━━━━━━━━━━\n\n"
                f"🗺 {from_city} → {to_city}\n📅 {date_str} | ⚖️ до {weight} | {transport}{note_part}\n\n👤 {author}",
                user.username, "💬 Написать попутчику")
            matches = db.find_matches_for_trip(from_city, to_city)
            if matches:
                kb = [[contact_button(f"💬 Написать @{m['username']}", m["username"])] for m in matches if m.get("username")]
                kb.append([InlineKeyboardButton("📢 Канал", url="https://t.me/parcelgo_board")])
                await update.message.reply_text(
                    f"✅ Рейс #{trip_id} добавлен!\n🎉 Найдено заявок: {len(matches)}",
                    reply_markup=InlineKeyboardMarkup(kb))
            else:
                await update.message.reply_text(
                    f"✅ Рейс #{trip_id} добавлен!\n📭 Уведомим когда появятся посылки!",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📢 Канал", url="https://t.me/parcelgo_board")]]))

        elif data.get("type") == "post":
            text = data.get("text","")
            await publish_to_channel(ctx.bot,
                f"📣 *Объявление*\n━━━━━━━━━━━━━━━━━━━━\n\n{text}\n\n👤 {author}",
                user.username, "💬 Написать автору")
            await update.message.reply_text("✅ Объявление в @parcelgo_board!",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📢 Канал", url="https://t.me/parcelgo_board")]]))
    except Exception as e:
        log.error(f"webapp: {e}")
        await update.message.reply_text("❌ Ошибка. Попробуйте ещё раз.")

# ── АДМИН ─────────────────────────────────────────────────────────────────────
async def admin(update, ctx):
    if update.effective_user.id != ADMIN_ID: return
    users   = db.conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    verified= db.conn.execute("SELECT COUNT(*) FROM users WHERE phone IS NOT NULL").fetchone()[0]
    reqs    = db.conn.execute("SELECT COUNT(*) FROM requests").fetchone()[0]
    trips   = db.conn.execute("SELECT COUNT(*) FROM trips").fetchone()[0]
    reviews = db.conn.execute("SELECT COUNT(*) FROM reviews").fetchone()[0]
    await update.message.reply_text(
        f"🔧 *Админ-панель*\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👥 Пользователей: {users}\n✅ Верифицировано: {verified}\n"
        f"📦 Заявок: {reqs}\n✈️ Рейсов: {trips}\n⭐ Отзывов: {reviews}",
        parse_mode="Markdown")

async def help_cmd(update, ctx):
    await update.message.reply_text(
        "📖 *Справка ParcelGo*\n━━━━━━━━━━━━━━━━━━━━\n\n"
        "/start — главное меню\n/help — эта справка\n"
        "/myreqs — мои заявки\n/cancel — отменить заявку\n\n"
        "⚠️ Без @username другие не смогут написать вам напрямую.\n"
        "Установите его: Настройки → Изменить профиль → Имя пользователя",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Меню", callback_data="back_main")]]))

async def back(update, ctx):
    await update.callback_query.answer()
    dest = update.callback_query.data.split("_",1)[1]
    if dest == "main":    return await start(update, ctx)
    elif dest == "send":  return await send_start(update, ctx)
    elif dest == "travel":return await travel_start(update, ctx)

# ── ЗАПУСК ────────────────────────────────────────────────────────────────────
def main():
    app = Application.builder().token(TOKEN).build()

    async def post_init(application):
        await application.bot.delete_webhook(drop_pending_updates=True)
    app.post_init = post_init

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", verify_phone),
            CallbackQueryHandler(send_start,      pattern="^send$"),
            CallbackQueryHandler(travel_start,    pattern="^travel$"),
            CallbackQueryHandler(search_start,    pattern="^search$"),
            CallbackQueryHandler(free_post_start, pattern="^freepost$"),
            CallbackQueryHandler(review_start,    pattern="^review_start$"),
        ],
        states={
            PHONE_VERIFY: [MessageHandler(filters.CONTACT, handle_phone)],
            MAIN: [
                CallbackQueryHandler(send_start,      pattern="^send$"),
                CallbackQueryHandler(travel_start,    pattern="^travel$"),
                CallbackQueryHandler(search_start,    pattern="^search$"),
                CallbackQueryHandler(free_post_start, pattern="^freepost$"),
                CallbackQueryHandler(review_start,    pattern="^review_start$"),
                CallbackQueryHandler(how,             pattern="^how$"),
                CallbackQueryHandler(my_req,          pattern="^my$"),
                CallbackQueryHandler(bl,              pattern="^blacklist$"),
                CallbackQueryHandler(cancel_menu_cb,  pattern="^cancel_menu$"),
            ],
            S_ROUTE:  [
                CallbackQueryHandler(s_route,    pattern="^sr_"),
                CallbackQueryHandler(s_custom,   pattern="^srcustom$"),
            ],
            S_CUSTOM: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_custom_route)],
            S_TYPE:   [
                CallbackQueryHandler(s_type,     pattern="^st_"),
                CallbackQueryHandler(s_route,    pattern="^sr_"),
                CallbackQueryHandler(send_start, pattern="^send$"),
            ],
            S_SIZE:   [
                CallbackQueryHandler(s_size,     pattern="^ss_"),
                CallbackQueryHandler(s_route,    pattern="^sr_"),
            ],
            S_CONFIRM:[
                CallbackQueryHandler(s_confirm,  pattern="^sc$"),
                CallbackQueryHandler(send_start, pattern="^send$"),
            ],
            T_ROUTE:  [
                CallbackQueryHandler(t_route,       pattern="^tr_"),
                CallbackQueryHandler(t_custom,      pattern="^trcustom$"),
            ],
            T_CUSTOM: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_custom_route)],
            T_DATE:   [
                CallbackQueryHandler(t_date,        pattern="^td_"),
                CallbackQueryHandler(t_route,       pattern="^tr_"),
                CallbackQueryHandler(travel_start,  pattern="^travel$"),
            ],
            T_WEIGHT: [
                CallbackQueryHandler(t_weight,      pattern="^tw_"),
                CallbackQueryHandler(t_route,       pattern="^tr_"),
            ],
            T_CONFIRM:[
                CallbackQueryHandler(t_confirm,     pattern="^tc$"),
                CallbackQueryHandler(travel_start,  pattern="^travel$"),
            ],
            FREE_POST:    [MessageHandler(filters.TEXT & ~filters.COMMAND, free_post_send)],
            SEARCH_FROM:  [MessageHandler(filters.TEXT & ~filters.COMMAND, search_from)],
            SEARCH_TO:    [MessageHandler(filters.TEXT & ~filters.COMMAND, search_to)],
            REVIEW_WHO:   [MessageHandler(filters.TEXT & ~filters.COMMAND, review_who)],
            REVIEW_STARS: [CallbackQueryHandler(review_stars, pattern="^star_")],
        },
        fallbacks=[
            CommandHandler("start", verify_phone),
            CallbackQueryHandler(back, pattern="^back_"),
        ],
        per_user=True, per_chat=True,
    )
    app.add_handler(conv)
    app.add_handler(CommandHandler("admin",  admin))
    app.add_handler(CommandHandler("help",   help_cmd))
    app.add_handler(CommandHandler("myreqs", my_req))
    app.add_handler(CommandHandler("cancel", cancel_menu_cb))
    app.add_handler(CallbackQueryHandler(back,           pattern="^back_"))
    app.add_handler(CallbackQueryHandler(how,            pattern="^how$"))
    app.add_handler(CallbackQueryHandler(my_req,         pattern="^my$"))
    app.add_handler(CallbackQueryHandler(bl,             pattern="^blacklist$"))
    app.add_handler(CallbackQueryHandler(search_start,   pattern="^search$"))
    app.add_handler(CallbackQueryHandler(free_post_start,pattern="^freepost$"))
    app.add_handler(CallbackQueryHandler(review_start,   pattern="^review_start$"))
    app.add_handler(CallbackQueryHandler(cancel_menu_cb, pattern="^cancel_menu$"))
    app.add_handler(CallbackQueryHandler(cancel_req_cb,  pattern="^cancel_req_"))
    app.add_handler(CallbackQueryHandler(cancel_trip_cb, pattern="^cancel_trip_"))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_webapp))
    log.info("🚀 ParcelGo Bot v8 запущен!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()

