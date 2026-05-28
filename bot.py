import logging
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import (Application, CommandHandler, CallbackQueryHandler,
                           ConversationHandler, ContextTypes, MessageHandler, filters)
from database import db
from config import TOKEN, ADMIN_ID, CARD_NUMBER, CARD_HOLDER

CHANNEL_ID = "@parcelgo_board"

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
log = logging.getLogger(__name__)

(MAIN, S_ROUTE, S_CUSTOM, S_TYPE, S_WEIGHT, S_BUDGET, S_CONFIRM,
 T_ROUTE, T_CUSTOM, T_DATE, T_WEIGHT, T_PRICE, T_CONFIRM,
 FREE_POST, SEARCH_FROM, SEARCH_TO, REVIEW_WHO, REVIEW_STARS) = range(18)

ROUTES = [
    ("🇦🇪","Москва → Дубай"),("🇬🇧","Москва → Лондон"),
    ("🇹🇭","Москва → Бангкок"),("🇹🇷","Стамбул → Москва"),
    ("🇩🇪","Дубай → Москва"),("🇬🇪","Берлин → Тбилиси"),
    ("✈️","Москва → Берлин"),("🌍","Москва → Стамбул"),
]
TYPES     = [("📱","Техника"),("👗","Одежда"),("💊","Лекарства"),("📄","Документы"),("🎁","Подарок"),("💄","Косметика"),("🍫","Еда"),("📦","Другое")]
SIZES     = ["📦 Маленькая (влезет в рюкзак)","🎒 Средняя (небольшая сумка)","🧳 Большая (чемодан)","📫 Крупногабаритная"]

DATES     = ["Сегодня","Завтра","Через 2–3 дня","На этой неделе","На следующей неделе","В течение месяца"]
TWEIGHTS  = ["до 1 кг","1–3 кг","3–5 кг","5–10 кг","10+ кг"]

STARS     = ["⭐ 1","⭐⭐ 2","⭐⭐⭐ 3","⭐⭐⭐⭐ 4","⭐⭐⭐⭐⭐ 5"]

def contact_button(label, username):
    return InlineKeyboardButton(label, url=f"https://t.me/{username}")

def contact_label(name, username):
    return f"@{username}" if username else name

def stars_str(rating):
    return "⭐" * round(rating) if rating else "нет отзывов"

# ── КАНАЛ: публикация ─────────────────────────────────────────────────────────
async def publish_to_channel(bot, text, username=None, btn_label=None):
    try:
        kb = []
        if username and btn_label:
            kb.append([InlineKeyboardButton(btn_label, url=f"https://t.me/{username}")])
        await bot.send_message(CHANNEL_ID, text, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(kb) if kb else None)
    except Exception as e:
        log.warning(f"Ошибка публикации в канал: {e}")

# ── ГЛАВНОЕ МЕНЮ ──────────────────────────────────────────────────────────────
async def start(update, ctx):
    user = update.effective_user
    db.upsert_user(user.id, user.first_name, user.username)
    name = user.first_name or "друг"
    u = db.get_user(user.id)
    rating_str = f"⭐ {u['rating']:.1f}" if u and u.get('trips_count') else ""

    text = (f"✦ *ParcelGo* ✦\n━━━━━━━━━━━━━━━━━━━━\n\nПривет, *{name}* 👋 {rating_str}\n\n"
            f"Доставка посылок через попутчиков —\nв *3× дешевле* DHL и *5× быстрее* почты.\n\n"
            f"🌍 Сводим отправителей и попутчиков напрямую — быстро, удобно, бесплатно.\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\nЧто хочешь сделать? 👇")
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 Открыть приложение", web_app=WebAppInfo(url="https://kapunkrabb.github.io/parcelgo-app"))],
        [InlineKeyboardButton("📦 Отправить посылку", callback_data="send")],
        [InlineKeyboardButton("✈️ Я путешественник — заработать", callback_data="travel")],
        [InlineKeyboardButton("🔍 Найти по маршруту", callback_data="search")],
        [InlineKeyboardButton("✍️ Написать объявление", callback_data="freepost")],
        [InlineKeyboardButton("📢 Доска объявлений", url="https://t.me/parcelgo_board")],
        [InlineKeyboardButton("📋 Мои заявки", callback_data="my"), InlineKeyboardButton("⭐ Отзывы", callback_data="review_start")],
        [InlineKeyboardButton("❓ Как работает", callback_data="how"), InlineKeyboardButton("🚫 Стоп-лист", callback_data="blacklist")],
    ])
    if update.message:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)
    else:
        await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)
    return MAIN

async def how(update, ctx):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        "❓ *Как это работает*\n━━━━━━━━━━━━━━━━━━━━\n\n"
        "*📦 Отправить посылку:*\n1️⃣ Выбери маршрут и тип\n2️⃣ Бот найдёт попутчиков\n"
        "3️⃣ Договорись напрямую\n4️⃣ Передай посылку при встрече\n\n"
        "*✈️ Заработать как попутчик:*\n1️⃣ Укажи маршрут и дату\n2️⃣ Найди посылку\n3️⃣ Получи деньги\n\n"
        "*🔍 Поиск по маршруту:*\nВведи откуда и куда — увидишь всех кто едет и все посылки\n\n"
        "*⭐ Отзывы:*\nПосле сделки оставь отзыв — это повышает доверие к тебе\n\n"
        ,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("← Назад", callback_data="back_main")]]))

async def my_req(update, ctx):
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
    await update.callback_query.edit_message_text(text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⭐ Оставить отзыв", callback_data="review_start")],
            [InlineKeyboardButton("← Назад", callback_data="back_main")]]))

async def bl(update, ctx):
    await update.callback_query.answer()
    rows = db.conn.execute(
        "SELECT bl.*, u.name FROM blacklist bl JOIN users u ON bl.user_id=u.id "
        "WHERE bl.is_public=1 ORDER BY bl.banned_at DESC LIMIT 10").fetchall()
    if not rows:
        text = "🚫 *Стоп-лист*\n━━━━━━━━━━━━━━━━━━━━\n\n✅ Список пуст!"
    else:
        lines = ["🚫 *Стоп-лист мошенников*\n━━━━━━━━━━━━━━━━━━━━"]
        for r in rows:
            lines.append(f"❌ *{r['name']}* — {r['reason']}\n   📅 {r['banned_at'][:10]}")
        text = "\n".join(lines)
    await update.callback_query.edit_message_text(text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("← Назад", callback_data="back_main")]]))

# ── ПОИСК ПО МАРШРУТУ ─────────────────────────────────────────────────────────
async def search_start(update, ctx):
    await update.callback_query.answer()
    ctx.user_data.clear()
    await update.callback_query.edit_message_text(
        "🔍 *Поиск по маршруту*\n━━━━━━━━━━━━━━━━━━━━\n\n"
        "*Шаг 1 из 2* — Откуда?\n_Введи город отправления:_\n_Например: Москва_",
        parse_mode="Markdown")
    return SEARCH_FROM

async def search_from(update, ctx):
    ctx.user_data["search_from"] = update.message.text.strip()
    await update.message.reply_text(
        f"✅ Откуда: *{ctx.user_data['search_from']}*\n\n"
        "*Шаг 2 из 2* — Куда?\n_Введи город назначения:_",
        parse_mode="Markdown")
    return SEARCH_TO

async def search_to(update, ctx):
    from_city = ctx.user_data.get("search_from", "")
    to_city = update.message.text.strip()

    travelers = db.find_travelers(from_city, to_city)
    requests = db.find_matches_for_trip(from_city, to_city)

    lines = [f"🔍 *Результаты: {from_city} → {to_city}*\n━━━━━━━━━━━━━━━━━━━━"]

    if travelers:
        lines.append(f"\n✈️ *Попутчики ({len(travelers)}):*")
        for t in travelers:
            label = contact_label(t["name"], t["username"])
            lines.append(f"• {label} | {t['date']} | ⚖️ {t['weight']} | 💰 {t['price']}")
    else:
        lines.append("\n✈️ *Попутчиков нет*")

    if requests:
        lines.append(f"\n📦 *Посылки ({len(requests)}):*")
        for r in requests:
            label = contact_label(r["sender_name"], r["username"])
            lines.append(f"• {label} | 📐 {r['weight']}")
    else:
        lines.append("\n📦 *Посылок нет*")

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

# ── ОТЗЫВЫ И РЕЙТИНГ ─────────────────────────────────────────────────────────
async def review_start(update, ctx):
    await update.callback_query.answer()
    ctx.user_data.clear()
    await update.callback_query.edit_message_text(
        "⭐ *Оставить отзыв*\n━━━━━━━━━━━━━━━━━━━━\n\n"
        "Введи *@username* человека которому хочешь оставить отзыв:\n\n"
        "_Например: @ivanov_",
        parse_mode="Markdown")
    return REVIEW_WHO

async def review_who(update, ctx):
    username = update.message.text.strip().lstrip("@")
    row = db.conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    if not row:
        await update.message.reply_text(
            "❌ Пользователь не найден. Убедись что он пользовался ботом.\nПопробуй ещё раз:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Меню", callback_data="back_main")]]))
        return REVIEW_WHO

    ctx.user_data["review_target_id"] = row["id"]
    ctx.user_data["review_target_name"] = row["name"]
    ctx.user_data["review_target_username"] = username

    kb = [[InlineKeyboardButton(s, callback_data=f"star_{i+1}")] for i, s in enumerate(STARS)]
    kb.append([InlineKeyboardButton("← Отмена", callback_data="back_main")])
    await update.message.reply_text(
        f"👤 *{row['name']}* (@{username})\n\n"
        f"Текущий рейтинг: {stars_str(row['rating'])} {row['rating']:.1f}\n\n"
        "⭐ Выбери оценку:",
        parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
    return REVIEW_STARS

async def review_stars(update, ctx):
    await update.callback_query.answer()
    stars = int(update.callback_query.data.split("_")[1])
    uid = update.effective_user.id
    target_id = ctx.user_data.get("review_target_id")
    target_name = ctx.user_data.get("review_target_name")
    target_username = ctx.user_data.get("review_target_username")

    if uid == target_id:
        await update.callback_query.edit_message_text("❌ Нельзя оставить отзыв самому себе.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Меню", callback_data="back_main")]]))
        return ConversationHandler.END

    db.add_review(uid, target_id, 0, stars)
    updated = db.get_user(target_id)

    reviewer = update.effective_user
    reviewer_label = contact_label(reviewer.first_name, reviewer.username)

    await update.callback_query.edit_message_text(
        f"✅ *Отзыв отправлен!*\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 {target_name}\n"
        f"Новый рейтинг: {'⭐' * stars} ({stars}/5)\n\n"
        f"Общий рейтинг: {updated['rating']:.1f} ({updated['trips_count']} отзывов)",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Главное меню", callback_data="back_main")]]))

    try:
        await ctx.bot.send_message(target_id,
            f"⭐ *Новый отзыв!*\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{'⭐' * stars} ({stars}/5) от {reviewer_label}\n\n"
            f"Ваш рейтинг: {updated['rating']:.1f} ({updated['trips_count']} отзывов)",
            parse_mode="Markdown")
    except:
        pass

    return ConversationHandler.END

# ── СВОБОДНОЕ ОБЪЯВЛЕНИЕ ──────────────────────────────────────────────────────
async def free_post_start(update, ctx):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        "✍️ *Свободное объявление*\n━━━━━━━━━━━━━━━━━━━━\n\n"
        "Напиши своё объявление в свободной форме.\n\n"
        "_Например: Лечу Москва → Пхукет 15 июня, возьму посылку до 3 кг, пишите!_\n\n"
        "Бот опубликует его в канал @parcelgo\\_board 👇",
        parse_mode="Markdown")
    return FREE_POST

async def free_post_send(update, ctx):
    user = update.effective_user
    text = update.message.text.strip()
    author = contact_label(user.first_name, user.username)
    await publish_to_channel(
        ctx.bot,
        f"📣 *Объявление*\n━━━━━━━━━━━━━━━━━━━━\n\n{text}\n\n👤 Автор: {author}",
        user.username, "💬 Написать автору")
    await update.message.reply_text(
        f"✅ *Объявление опубликовано!*\n\n👉 @parcelgo_board",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Главное меню", callback_data="back_main")]]))
    return ConversationHandler.END

# ── ОТПРАВИТЕЛЬ ───────────────────────────────────────────────────────────────
async def send_start(update, ctx):
    await update.callback_query.answer()
    ctx.user_data.clear()
    kb = []
    for i in range(0, len(ROUTES), 2):
        row = [InlineKeyboardButton(f"{ROUTES[i][0]} {ROUTES[i][1]}", callback_data=f"sr_{i}")]
        if i+1 < len(ROUTES):
            row.append(InlineKeyboardButton(f"{ROUTES[i+1][0]} {ROUTES[i+1][1]}", callback_data=f"sr_{i+1}"))
        kb.append(row)
    kb.append([InlineKeyboardButton("✏️ Свой маршрут", callback_data="srcustom")])
    kb.append([InlineKeyboardButton("← Назад", callback_data="back_main")])
    await update.callback_query.edit_message_text(
        "📦 *Отправить посылку*\n━━━━━━━━━━━━━━━━━━━━\n\n*Шаг 1 из 4* — Выбери маршрут 🗺",
        parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
    return S_ROUTE

async def s_custom(update, ctx):
    await update.callback_query.answer()
    ctx.user_data["waiting_custom_route"] = "sender"
    await update.callback_query.edit_message_text(
        "📦 *Свой маршрут*\n━━━━━━━━━━━━━━━━━━━━\n\nНапиши маршрут:\n*Город → Город*\n\nНапример: Москва → Алматы",
        parse_mode="Markdown")
    return S_CUSTOM

async def s_route(update, ctx):
    await update.callback_query.answer()
    idx = int(update.callback_query.data.split("_")[1])
    ctx.user_data["route"] = f"{ROUTES[idx][0]} {ROUTES[idx][1]}"
    kb = []
    for i in range(0, len(TYPES), 2):
        row = [InlineKeyboardButton(f"{TYPES[i][0]} {TYPES[i][1]}", callback_data=f"st_{i}")]
        if i+1 < len(TYPES):
            row.append(InlineKeyboardButton(f"{TYPES[i+1][0]} {TYPES[i+1][1]}", callback_data=f"st_{i+1}"))
        kb.append(row)
    kb.append([InlineKeyboardButton("← Назад", callback_data="send")])
    await update.callback_query.edit_message_text(
        f"📦 *Отправить посылку*\n━━━━━━━━━━━━━━━━━━━━\n\n✅ {ctx.user_data['route']}\n\n*Шаг 2 из 3* — Что отправляешь? 📦",
        parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
    return S_TYPE

async def s_type(update, ctx):
    await update.callback_query.answer()
    idx = int(update.callback_query.data.split("_")[1])
    ctx.user_data["type"] = f"{TYPES[idx][0]} {TYPES[idx][1]}"
    kb = [[InlineKeyboardButton(s, callback_data=f"ss_{i}")] for i, s in enumerate(SIZES)]
    kb.append([InlineKeyboardButton("← Назад", callback_data="send")])
    await update.callback_query.edit_message_text(
        f"📦 *Отправить посылку*\n━━━━━━━━━━━━━━━━━━━━\n\n✅ {ctx.user_data['route']}\n✅ {ctx.user_data['type']}\n\n*Шаг 3 из 3* — Размер посылки 📐",
        parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
    return S_WEIGHT

async def s_weight(update, ctx):
    await update.callback_query.answer()
    idx = int(update.callback_query.data.split("_")[1])
    ctx.user_data["weight"] = SIZES[idx]
    d = ctx.user_data
    await update.callback_query.edit_message_text(
        f"📦 *Подтверди заявку*\n━━━━━━━━━━━━━━━━━━━━\n\n🗺 {d['route']}\n📦 {d['type']}\n📐 {d['weight']}\n💰 Цена по договорённости\n\nВсё верно?",
        parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Создать заявку", callback_data="sc")],
            [InlineKeyboardButton("✏️ Изменить", callback_data="send")]]))
    return S_CONFIRM



async def s_confirm(update, ctx):
    await update.callback_query.answer()
    d = ctx.user_data
    uid = update.effective_user.id
    user = update.effective_user
    parts = d["route"].replace("→","→").split("→")
    from_city = parts[0].strip().lstrip("🇦🇪🇬🇧🇹🇭🇹🇷🇩🇪🇬🇪✈🌍 ").strip()
    to_city = parts[1].strip() if len(parts) > 1 else ""

    req_id = db.add_request(uid, from_city, to_city, d["weight"], d["type"], "договорная")
    travelers = db.find_travelers(from_city, to_city)
    sender_label = contact_label(user.first_name, user.username)

    # Публикуем в канал
    await publish_to_channel(ctx.bot,
        f"📦 *Нужен попутчик!*\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🗺 {d['route']}\n📦 {d['type']} | 📐 {d['weight']}\n💰 Цена по договорённости\n\n"
        f"👤 Отправитель: {sender_label}",
        user.username, "💬 Написать отправителю")

    if travelers:
        lines = [f"✅ *Заявка #{req_id} создана!*\n━━━━━━━━━━━━━━━━━━━━\n\n"
                 f"🗺 {d['route']}\n📦 {d['type']} | 📐 {d['weight']}\n💰 Цена по договорённости\n\n"
                 f"🎉 *Найдено попутчиков: {len(travelers)}*\n━━━━━━━━━━━━━━━━━━━━"]
        kb = []
        for t in travelers:
            label = contact_label(t["name"], t["username"])
            lines.append(f"\n✈️ {label} | {t['date']} | ⚖️ {t['weight']} | 💰 {t['price']}")
            if t["username"]:
                kb.append([contact_button(f"💬 Написать {label}", t["username"])])
        kb.append([InlineKeyboardButton("🏠 Главное меню", callback_data="back_main")])
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
                    f"📦 *Новая посылка по вашему маршруту!*\n━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"🗺 {d['route']}\n📦 {d['type']} | 📐 {d['weight']}\n💰 Цена по договорённости\n\n"
                    f"👤 Отправитель: {sender_label}\n\nДоговоритесь напрямую 👇",
                    parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(t_kb))
            except Exception as e:
                log.warning(f"Уведомление попутчику {t['user_id']}: {e}")
    else:
        await update.callback_query.edit_message_text(
            f"✅ *Заявка #{req_id} создана!*\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🗺 {d['route']}\n📦 {d['type']} | 📐 {d['weight']}\n💰 Цена по договорённости\n\n"
            f"🔍 Ищем попутчиков...\nКак только кто-то зарегистрирует рейс — сразу уведомим! 🙏\n\n"
            f"📢 Объявление опубликовано в @parcelgo_board",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Главное меню", callback_data="back_main")]]))

    try:
        await ctx.bot.send_message(ADMIN_ID,
            f"📦 Заявка #{req_id}\nОт: {user.first_name} (@{user.username})\n"
            f"{d['route']} | {d['type']} | {d['weight']}\nБюджет: договорная\nПопутчиков: {len(travelers)}")
    except: pass
    return ConversationHandler.END

# ── ПОПУТЧИК ──────────────────────────────────────────────────────────────────
async def travel_start(update, ctx):
    await update.callback_query.answer()
    ctx.user_data.clear()
    kb = []
    for i in range(0, len(ROUTES), 2):
        row = [InlineKeyboardButton(f"{ROUTES[i][0]} {ROUTES[i][1]}", callback_data=f"tr_{i}")]
        if i+1 < len(ROUTES):
            row.append(InlineKeyboardButton(f"{ROUTES[i+1][0]} {ROUTES[i+1][1]}", callback_data=f"tr_{i+1}"))
        kb.append(row)
    kb.append([InlineKeyboardButton("✏️ Свой маршрут", callback_data="trcustom")])
    kb.append([InlineKeyboardButton("← Назад", callback_data="back_main")])
    await update.callback_query.edit_message_text(
        "✈️ *Регистрация рейса*\n━━━━━━━━━━━━━━━━━━━━\n\nВозьми посылку и заработай!\n\n*Шаг 1 из 4* — Твой маршрут 🗺",
        parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
    return T_ROUTE

async def t_route(update, ctx):
    await update.callback_query.answer()
    idx = int(update.callback_query.data.split("_")[1])
    ctx.user_data["route"] = f"{ROUTES[idx][0]} {ROUTES[idx][1]}"
    kb = [[InlineKeyboardButton(d, callback_data=f"td_{i}")] for i, d in enumerate(DATES)]
    kb.append([InlineKeyboardButton("← Назад", callback_data="travel")])
    await update.callback_query.edit_message_text(
        f"✈️ *Регистрация рейса*\n━━━━━━━━━━━━━━━━━━━━\n\n✅ {ctx.user_data['route']}\n\n*Шаг 2 из 4* — Когда летишь? 📅",
        parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
    return T_DATE

async def t_date(update, ctx):
    await update.callback_query.answer()
    idx = int(update.callback_query.data.split("_")[1])
    ctx.user_data["date"] = DATES[idx]
    kb = [[InlineKeyboardButton(w, callback_data=f"tw_{i}")] for i, w in enumerate(TWEIGHTS)]
    kb.append([InlineKeyboardButton("← Назад", callback_data="travel")])
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
        f"✈️ *Подтверди рейс*\n━━━━━━━━━━━━━━━━━━━━\n\n🗺 {d['route']}\n📅 {d['date']}\n⚖️ {d['weight']}\n💰 Цена по договорённости\n\nВсё верно?",
        parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Зарегистрировать рейс", callback_data="tc")],
            [InlineKeyboardButton("✏️ Изменить", callback_data="travel")]]))
    return T_CONFIRM



async def t_confirm(update, ctx):
    await update.callback_query.answer()
    d = ctx.user_data
    uid = update.effective_user.id
    user = update.effective_user
    parts = d["route"].replace("→","→").split("→")
    from_city = parts[0].strip().lstrip("🇦🇪🇬🇧🇹🇭🇹🇷🇩🇪🇬🇪✈🌍 ").strip()
    to_city = parts[1].strip() if len(parts) > 1 else ""

    trip_id = db.add_trip(uid, from_city, to_city, d["date"], d["weight"], "договорная", "—")
    matches = db.find_matches_for_trip(from_city, to_city)
    traveler_label = contact_label(user.first_name, user.username)

    # Публикуем в канал
    await publish_to_channel(ctx.bot,
        f"✈️ *Возьму посылку!*\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🗺 {d['route']}\n📅 {d['date']} | ⚖️ до {d['weight']}\n💰 Цена: договорная\n\n"
        f"👤 Попутчик: {traveler_label}",
        user.username, "💬 Написать попутчику")

    if matches:
        lines = [f"✅ *Рейс #{trip_id} зарегистрирован!*\n━━━━━━━━━━━━━━━━━━━━\n\n"
                 f"🗺 {d['route']}\n📅 {d['date']} | ⚖️ {d['weight']}\n💰 договорная\n\n"
                 f"🎉 *Найдено заявок: {len(matches)}*\n━━━━━━━━━━━━━━━━━━━━"]
        kb = []
        for m in matches:
            sender_label = contact_label(m["sender_name"], m["username"])
            lines.append(f"\n📦 {sender_label} | ⚖️ {m['weight']} | 💰 {m['budget']}")
            if m["username"]:
                kb.append([contact_button(f"💬 Написать {sender_label}", m["username"])])
        kb.append([InlineKeyboardButton("🏠 Главное меню", callback_data="back_main")])
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
                    f"🎉 *Найден попутчик по вашему маршруту!*\n━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"✈️ {d['route']}\n📅 {d['date']} | ⚖️ {d['weight']}\n💰 договорная\n\n"
                    f"👤 Попутчик: {traveler_label}\n\nДоговоритесь напрямую 👇",
                    parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(s_kb))
            except Exception as e:
                log.warning(f"Уведомление отправителю {m['user_id']}: {e}")
    else:
        await update.callback_query.edit_message_text(
            f"✅ *Рейс #{trip_id} зарегистрирован!*\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🗺 {d['route']}\n📅 {d['date']} | ⚖️ {d['weight']}\n💰 договорная\n\n"
            f"📭 Как только появятся посылки — сразу уведомим! 🙏\n\n"
            f"📢 Объявление опубликовано в @parcelgo_board",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Главное меню", callback_data="back_main")]]))

    try:
        await ctx.bot.send_message(ADMIN_ID,
            f"✈️ Рейс #{trip_id}\nОт: {user.first_name} (@{user.username})\n"
            f"{d['route']} | {d['date']}\nВес: {d['weight']} | Цена: договорная\nЗаявок: {len(matches)}")
    except: pass
    return ConversationHandler.END

# ── СВОЙ МАРШРУТ ──────────────────────────────────────────────────────────────
async def t_custom(update, ctx):
    await update.callback_query.answer()
    ctx.user_data["waiting_custom_route"] = "traveler"
    await update.callback_query.edit_message_text(
        "✈️ *Свой маршрут*\n━━━━━━━━━━━━━━━━━━━━\n\nНапиши маршрут:\n*Город → Город*\n\nНапример: Москва → Алматы",
        parse_mode="Markdown")
    return T_CUSTOM

async def handle_custom_route(update, ctx):
    text = update.message.text.strip()
    role = ctx.user_data.get("waiting_custom_route", "sender")
    ctx.user_data["route"] = text
    if role == "traveler":
        kb = [[InlineKeyboardButton(d, callback_data=f"td_{i}")] for i, d in enumerate(DATES)]
        kb.append([InlineKeyboardButton("← Назад", callback_data="travel")])
        await update.message.reply_text(
            f"✈️ *Регистрация рейса*\n━━━━━━━━━━━━━━━━━━━━\n\n✅ {text}\n\n*Шаг 2 из 4* — Когда летишь? 📅",
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
            f"📦 *Отправить посылку*\n━━━━━━━━━━━━━━━━━━━━\n\n✅ {text}\n\n*Шаг 2 из 3* — Что отправляешь? 📦",
            parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        return S_TYPE

# ── АДМИН ПАНЕЛЬ ──────────────────────────────────────────────────────────────
async def admin(update, ctx):
    if update.effective_user.id != ADMIN_ID:
        return
    users  = db.conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    reqs   = db.conn.execute("SELECT COUNT(*) FROM requests").fetchone()[0]
    trips  = db.conn.execute("SELECT COUNT(*) FROM trips").fetchone()[0]
    matched = db.conn.execute("SELECT COUNT(*) FROM requests WHERE status='matched'").fetchone()[0]
    done   = db.conn.execute("SELECT COUNT(*) FROM requests WHERE status='completed'").fetchone()[0]
    reviews = db.conn.execute("SELECT COUNT(*) FROM reviews").fetchone()[0]
    await update.message.reply_text(
        f"🔧 *Админ-панель ParcelGo*\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👥 Пользователей: {users}\n"
        f"📦 Заявок всего: {reqs}\n"
        f"✈️ Рейсов всего: {trips}\n"
        f"🤝 Сматчено: {matched}\n"
        f"✅ Завершено: {done}\n"
        f"⭐ Отзывов: {reviews}",
        parse_mode="Markdown")

async def back(update, ctx):
    await update.callback_query.answer()
    dest = update.callback_query.data.split("_", 1)[1]
    if dest == "main":    return await start(update, ctx)
    elif dest == "send":  return await send_start(update, ctx)
    elif dest == "travel":return await travel_start(update, ctx)


# ── МИНИ-АПП: обработка данных ───────────────────────────────────────────────
async def handle_webapp(update, ctx):
    try:
        raw = update.message.web_app_data.data
        data = json.loads(raw)
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

            channel_text = (
                f"📦 *Нужен попутчик!*\n━━━━━━━━━━━━━━━━━━━━\n\n"
                f"🗺 {from_city} → {to_city}\n"
                f"📦 {item} | 📐 {size}{date_part}\n"
                f"💰 Цена по договорённости{note_part}\n\n"
                f"👤 Отправитель: {author}"
            )
            await publish_to_channel(ctx.bot, channel_text, user.username, "💬 Написать отправителю")

            travelers = db.find_travelers(from_city, to_city)
            if travelers:
                kb = []
                for t in travelers:
                    if t["username"]:
                        kb.append([contact_button(f"💬 Написать попутчику @{t['username']}", t["username"])])
                kb.append([InlineKeyboardButton("📢 Канал", url="https://t.me/parcelgo_board")])
                await update.message.reply_text(
                    f"✅ *Заявка #{req_id} создана!*\n\n"
                    f"🗺 {from_city} → {to_city}\n"
                    f"🎉 Найдено попутчиков: {len(travelers)}",
                    parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
                for t in travelers:
                    if t["user_id"] == uid: continue
                    try:
                        t_kb = []
                        if user.username:
                            t_kb.append([contact_button("💬 Написать отправителю", user.username)])
                        await ctx.bot.send_message(t["user_id"],
                            f"📦 *Новая посылка через мини-апп!*\n\n"
                            f"🗺 {from_city} → {to_city}\n📦 {item} | 📐 {size}\n\n"
                            f"👤 Отправитель: {author}",
                            parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(t_kb))
                    except: pass
            else:
                await update.message.reply_text(
                    f"✅ *Заявка #{req_id} создана!*\n\n"
                    f"🗺 {from_city} → {to_city}\n\n"
                    f"🔍 Ищем попутчиков...\n📢 Объявление в @parcelgo_board",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📢 Открыть канал", url="https://t.me/parcelgo_board")]]))

        elif data.get("type") == "travel":
            from_city = data.get("from","")
            to_city = data.get("to","")
            date_str = data.get("date","")
            weight = data.get("weight","")
            transport = data.get("transport","")
            note = data.get("note","")
            note_part = f"\n📝 {note}" if note else ""

            trip_id = db.add_trip(uid, from_city, to_city, date_str, weight, "договорная", "—")

            channel_text = (
                f"✈️ *Возьму посылку!*\n━━━━━━━━━━━━━━━━━━━━\n\n"
                f"🗺 {from_city} → {to_city}\n"
                f"📅 {date_str} | ⚖️ до {weight} | {transport}{note_part}\n\n"
                f"👤 Попутчик: {author}"
            )
            await publish_to_channel(ctx.bot, channel_text, user.username, "💬 Написать попутчику")

            matches = db.find_matches_for_trip(from_city, to_city)
            if matches:
                kb = []
                for m in matches:
                    if m["username"]:
                        kb.append([contact_button(f"💬 Написать отправителю @{m['username']}", m["username"])])
                await update.message.reply_text(
                    f"✅ *Рейс #{trip_id} добавлен!*\n\n"
                    f"🗺 {from_city} → {to_city}\n"
                    f"🎉 Найдено заявок: {len(matches)}",
                    parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
                for m in matches:
                    if m["user_id"] == uid: continue
                    try:
                        s_kb = []
                        if user.username:
                            s_kb.append([contact_button("💬 Написать попутчику", user.username)])
                        await ctx.bot.send_message(m["user_id"],
                            f"🎉 *Найден попутчик через мини-апп!*\n\n"
                            f"✈️ {from_city} → {to_city}\n📅 {date_str} | ⚖️ {weight}\n\n"
                            f"👤 Попутчик: {author}",
                            parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(s_kb))
                    except: pass
            else:
                await update.message.reply_text(
                    f"✅ *Рейс #{trip_id} добавлен!*\n\n"
                    f"🗺 {from_city} → {to_city}\n\n"
                    f"📭 Уведомим когда появятся посылки!\n📢 Объявление в @parcelgo_board",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📢 Открыть канал", url="https://t.me/parcelgo_board")]]))

        elif data.get("type") == "post":
            text = data.get("text","")
            await publish_to_channel(ctx.bot,
                f"📣 *Объявление*\n━━━━━━━━━━━━━━━━━━━━\n\n{text}\n\n👤 Автор: {author}",
                user.username, "💬 Написать автору")
            await update.message.reply_text(
                "✅ *Объявление опубликовано в канале!*\n\n👉 @parcelgo_board",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📢 Открыть канал", url="https://t.me/parcelgo_board")]]))

    except Exception as e:
        log.error(f"webapp handler error: {e}")
        await update.message.reply_text("❌ Ошибка. Попробуйте ещё раз.")

# ── ЗАПУСК ────────────────────────────────────────────────────────────────────
def main():
    app = Application.builder().token(TOKEN).build()

    async def post_init(application):
        await application.bot.delete_webhook(drop_pending_updates=True)
    app.post_init = post_init

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CallbackQueryHandler(send_start,       pattern="^send$"),
            CallbackQueryHandler(travel_start,     pattern="^travel$"),
            CallbackQueryHandler(search_start,     pattern="^search$"),
            CallbackQueryHandler(free_post_start,  pattern="^freepost$"),
            CallbackQueryHandler(review_start,     pattern="^review_start$"),
        ],
        states={
            MAIN: [
                CallbackQueryHandler(send_start,      pattern="^send$"),
                CallbackQueryHandler(travel_start,    pattern="^travel$"),
                CallbackQueryHandler(search_start,    pattern="^search$"),
                CallbackQueryHandler(free_post_start, pattern="^freepost$"),
                CallbackQueryHandler(review_start,    pattern="^review_start$"),
                CallbackQueryHandler(how,             pattern="^how$"),
                CallbackQueryHandler(my_req,          pattern="^my$"),
                CallbackQueryHandler(bl,              pattern="^blacklist$"),
            ],
            S_ROUTE:  [CallbackQueryHandler(s_route, pattern="^sr_"), CallbackQueryHandler(s_custom, pattern="^srcustom$")],
            S_CUSTOM: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_custom_route)],
            S_TYPE:   [CallbackQueryHandler(s_type,   pattern="^st_")],
            S_WEIGHT: [CallbackQueryHandler(s_weight, pattern="^ss_")],
            S_CONFIRM:[CallbackQueryHandler(s_confirm,pattern="^sc$")],
            T_ROUTE:  [CallbackQueryHandler(t_route, pattern="^tr_"), CallbackQueryHandler(t_custom, pattern="^trcustom$")],
            T_CUSTOM: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_custom_route)],
            T_DATE:   [CallbackQueryHandler(t_date,   pattern="^td_")],
            T_WEIGHT: [CallbackQueryHandler(t_weight, pattern="^tw_")],
            T_CONFIRM:[CallbackQueryHandler(t_confirm,pattern="^tc$")],
            FREE_POST:[MessageHandler(filters.TEXT & ~filters.COMMAND, free_post_send)],
            SEARCH_FROM:[MessageHandler(filters.TEXT & ~filters.COMMAND, search_from)],
            SEARCH_TO:  [MessageHandler(filters.TEXT & ~filters.COMMAND, search_to)],
            REVIEW_WHO: [MessageHandler(filters.TEXT & ~filters.COMMAND, review_who)],
            REVIEW_STARS:[CallbackQueryHandler(review_stars, pattern="^star_")],
        },
        fallbacks=[
            CommandHandler("start", start),
            CallbackQueryHandler(back, pattern="^back_"),
        ],
        per_user=True, per_chat=True,
    )
    app.add_handler(conv)
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CallbackQueryHandler(back,           pattern="^back_"))
    app.add_handler(CallbackQueryHandler(how,            pattern="^how$"))
    app.add_handler(CallbackQueryHandler(my_req,         pattern="^my$"))
    app.add_handler(CallbackQueryHandler(bl,             pattern="^blacklist$"))
    app.add_handler(CallbackQueryHandler(search_start,   pattern="^search$"))
    app.add_handler(CallbackQueryHandler(free_post_start,pattern="^freepost$"))
    app.add_handler(CallbackQueryHandler(review_start,   pattern="^review_start$"))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_webapp))
    log.info("🚀 ParcelGo Bot v3 запущен!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()

