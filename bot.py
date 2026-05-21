import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ConversationHandler, ContextTypes, MessageHandler, filters
from database import db
from config import TOKEN, ADMIN_ID, CARD_NUMBER, CARD_HOLDER

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
log = logging.getLogger(__name__)

MAIN,S_ROUTE,S_CUSTOM,S_TYPE,S_WEIGHT,S_BUDGET,S_CONFIRM,T_ROUTE,T_CUSTOM,T_DATE,T_WEIGHT,T_PRICE,T_CONFIRM = range(13)

ROUTES = [
    ("🇦🇪","Москва → Дубай"),("🇬🇧","Москва → Лондон"),
    ("🇹🇭","Москва → Бангкок"),("🇹🇷","Стамбул → Москва"),
    ("🇩🇪","Дубай → Москва"),("🇬🇪","Берлин → Тбилиси"),
    ("✈️","Москва → Берлин"),("🌍","Москва → Стамбул"),
]
TYPES = [("📱","Техника"),("👗","Одежда"),("💊","Лекарства"),("📄","Документы"),("🎁","Подарок"),("💄","Косметика"),("🍫","Еда"),("📦","Другое")]
WEIGHTS = ["до 0.5 кг","0.5–1 кг","1–3 кг","3–5 кг","5–10 кг"]
BUDGETS = ["до 1 000 ₽","1 000–2 000 ₽","2 000–4 000 ₽","4 000–7 000 ₽","от 7 000 ₽"]
DATES = ["Сегодня","Завтра","Через 2–3 дня","На этой неделе","На следующей неделе","В течение месяца"]
TWEIGHTS = ["до 1 кг","1–3 кг","3–5 кг","5–10 кг","10+ кг"]
PRICES = ["300–500 ₽/кг","500–800 ₽/кг","800–1200 ₽/кг","1200–2000 ₽/кг","от 2000 ₽/кг"]

def main_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📦  Отправить посылку",callback_data="send")],
        [InlineKeyboardButton("✈️  Я путешественник — заработать",callback_data="travel")],
        [InlineKeyboardButton("📋  Мои заявки",callback_data="my"),InlineKeyboardButton("❓  Как работает",callback_data="how")],
        [InlineKeyboardButton("🚫  Стоп-лист мошенников",callback_data="blacklist")],
    ])

async def start(update,ctx):
    user=update.effective_user
    db.upsert_user(user.id,user.first_name,user.username)
    name=user.first_name or "друг"
    text=(f"✦ *ParcelGo* ✦\n━━━━━━━━━━━━━━━━━━━━\n\nПривет, *{name}* 👋\n\n"
          f"Доставка посылок через попутчиков —\nв *3× дешевле* DHL и *5× быстрее* почты.\n\n"
          f"📊 *Статистика:*\n👥 18 420 участников\n📦 94 700 доставок\n🌍 67 стран\n⭐ 4.92 рейтинг\n\n"
          f"━━━━━━━━━━━━━━━━━━━━\nЧто хочешь сделать? 👇")
    from telegram import WebAppInfo
    app_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 Открыть приложение", web_app=WebAppInfo(url="https://kapunkrabb.github.io/parcelgo-app"))],
        [InlineKeyboardButton("📦  Отправить посылку",callback_data="send")],
        [InlineKeyboardButton("✈️  Я путешественник — заработать",callback_data="travel")],
        [InlineKeyboardButton("📋  Мои заявки",callback_data="my"),InlineKeyboardButton("❓  Как работает",callback_data="how")],
        [InlineKeyboardButton("🚫  Стоп-лист мошенников",callback_data="blacklist")],
    ])
    if update.message:
        await update.message.reply_text(text,parse_mode="Markdown",reply_markup=app_kb)
    else:
        await update.callback_query.edit_message_text(text,parse_mode="Markdown",reply_markup=app_kb)
    return MAIN

async def how(update,ctx):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        "❓ *Как это работает*\n━━━━━━━━━━━━━━━━━━━━\n\n"
        "*📦 Отправить посылку:*\n1️⃣ Выбери маршрут и тип\n2️⃣ Бот найдёт попутчиков\n"
        "3️⃣ Переведи оплату на карту\n4️⃣ Передай посылку при встрече\n\n"
        "*✈️ Заработать как попутчик:*\n1️⃣ Укажи маршрут и дату\n2️⃣ Возьми посылку\n3️⃣ Получи деньги\n\n"
        "*🛡 Безопасность:*\n• Верификация участников\n• Стоп-лист мошенников\n• Деньги переводятся напрямую\n\n"
        "*💰 Комиссия сервиса: 10%*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("← Назад",callback_data="back_main")]]))

async def my_req(update,ctx):
    await update.callback_query.answer()
    uid=update.effective_user.id
    reqs=db.get_user_requests(uid)
    trips=db.get_user_trips(uid)
    if not reqs and not trips:
        text="📋 *Мои заявки*\n━━━━━━━━━━━━━━━━━━━━\n\nПока нет активных заявок."
    else:
        lines=["📋 *Мои заявки*\n━━━━━━━━━━━━━━━━━━━━"]
        if reqs:
            lines.append("\n*📦 Посылки:*")
            for r in reqs:
                e={"pending":"⏳","matched":"🤝","completed":"✅","cancelled":"❌"}.get(r["status"],"❓")
                lines.append(f"{e} {r['from_city']} → {r['to_city']} | {r['weight']} | {r['budget']}")
        if trips:
            lines.append("\n*✈️ Мои рейсы:*")
            for t in trips:
                lines.append(f"🛫 {t['from_city']} → {t['to_city']} | {t['date']}")
        text="\n".join(lines)
    await update.callback_query.edit_message_text(text,parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("← Назад",callback_data="back_main")]]))

async def bl(update,ctx):
    await update.callback_query.answer()
    rows=db.conn.execute("SELECT bl.*,u.name FROM blacklist bl JOIN users u ON bl.user_id=u.id WHERE bl.is_public=1 ORDER BY bl.banned_at DESC LIMIT 10").fetchall()
    if not rows:
        text="🚫 *Стоп-лист*\n━━━━━━━━━━━━━━━━━━━━\n\n✅ Список пуст!"
    else:
        lines=["🚫 *Стоп-лист мошенников*\n━━━━━━━━━━━━━━━━━━━━"]
        for r in rows:
            lines.append(f"❌ *{r['name']}* — {r['reason']}\n   📅 {r['banned_at'][:10]}")
        text="\n".join(lines)
    await update.callback_query.edit_message_text(text,parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("← Назад",callback_data="back_main")]]))

async def send_start(update,ctx):
    await update.callback_query.answer()
    ctx.user_data.clear()
    kb=[]
    for i in range(0,len(ROUTES),2):
        row=[InlineKeyboardButton(f"{ROUTES[i][0]} {ROUTES[i][1]}",callback_data=f"sr_{i}")]
        if i+1<len(ROUTES): row.append(InlineKeyboardButton(f"{ROUTES[i+1][0]} {ROUTES[i+1][1]}",callback_data=f"sr_{i+1}"))
        kb.append(row)
    kb.append([InlineKeyboardButton("✏️ Свой маршрут",callback_data="srcustom")])
    kb.append([InlineKeyboardButton("← Назад",callback_data="back_main")])
    await update.callback_query.edit_message_text("📦 *Отправить посылку*\n━━━━━━━━━━━━━━━━━━━━\n\n*Шаг 1 из 4* — Выбери маршрут 🗺",parse_mode="Markdown",reply_markup=InlineKeyboardMarkup(kb))
    return S_ROUTE

async def s_custom(update,ctx):
    await update.callback_query.answer()
    ctx.user_data["waiting_custom_route"] = "sender"
    await update.callback_query.edit_message_text(
        "📦 *Свой маршрут*\n━━━━━━━━━━━━━━━━━━━━\n\nНапиши маршрут в формате:\n*Город отправки → Город получения*\n\nНапример: Москва → Алматы",
        parse_mode="Markdown")
    return S_CUSTOM

async def t_custom(update,ctx):
    await update.callback_query.answer()
    ctx.user_data["waiting_custom_route"] = "traveler"
    await update.callback_query.edit_message_text(
        "✈️ *Свой маршрут*\n━━━━━━━━━━━━━━━━━━━━\n\nНапиши маршрут в формате:\n*Город отправки → Город получения*\n\nНапример: Москва → Алматы",
        parse_mode="Markdown")
    return T_CUSTOM

async def handle_custom_route(update,ctx):
    text = update.message.text.strip()
    role = ctx.user_data.get("waiting_custom_route","sender")
    ctx.user_data["route"] = text
    if role == "traveler":
        from telegram import InlineKeyboardButton,InlineKeyboardMarkup
        kb=[[InlineKeyboardButton(d,callback_data=f"td_{i}")] for i,d in enumerate(DATES)]
        kb.append([InlineKeyboardButton("← Назад",callback_data="travel")])
        await update.message.reply_text(
            f"✈️ *Регистрация рейса*\n━━━━━━━━━━━━━━━━━━━━\n\n✅ {text}\n\n*Шаг 2 из 4* — Когда летишь? 📅",
            parse_mode="Markdown",reply_markup=InlineKeyboardMarkup(kb))
        return T_DATE
    else:
        from telegram import InlineKeyboardButton,InlineKeyboardMarkup
        kb=[]
        for i in range(0,len(TYPES),2):
            row=[InlineKeyboardButton(f"{TYPES[i][0]} {TYPES[i][1]}",callback_data=f"st_{i}")]
            if i+1<len(TYPES): row.append(InlineKeyboardButton(f"{TYPES[i+1][0]} {TYPES[i+1][1]}",callback_data=f"st_{i+1}"))
            kb.append(row)
        kb.append([InlineKeyboardButton("← Назад",callback_data="send")])
        await update.message.reply_text(
            f"📦 *Отправить посылку*\n━━━━━━━━━━━━━━━━━━━━\n\n✅ {text}\n\n*Шаг 2 из 4* — Что отправляешь? 📦",
            parse_mode="Markdown",reply_markup=InlineKeyboardMarkup(kb))
        return S_TYPE

async def s_route(update,ctx):
    await update.callback_query.answer()
    idx=int(update.callback_query.data.split("_")[1])
    ctx.user_data["route"]=f"{ROUTES[idx][0]} {ROUTES[idx][1]}"
    kb=[]
    for i in range(0,len(TYPES),2):
        row=[InlineKeyboardButton(f"{TYPES[i][0]} {TYPES[i][1]}",callback_data=f"st_{i}")]
        if i+1<len(TYPES): row.append(InlineKeyboardButton(f"{TYPES[i+1][0]} {TYPES[i+1][1]}",callback_data=f"st_{i+1}"))
        kb.append(row)
    kb.append([InlineKeyboardButton("← Назад",callback_data="send")])
    await update.callback_query.edit_message_text(
        f"📦 *Отправить посылку*\n━━━━━━━━━━━━━━━━━━━━\n\n✅ {ctx.user_data['route']}\n\n*Шаг 2 из 4* — Что отправляешь? 📦",
        parse_mode="Markdown",reply_markup=InlineKeyboardMarkup(kb))
    return S_TYPE

async def s_type(update,ctx):
    await update.callback_query.answer()
    idx=int(update.callback_query.data.split("_")[1])
    ctx.user_data["type"]=f"{TYPES[idx][0]} {TYPES[idx][1]}"
    kb=[[InlineKeyboardButton(w,callback_data=f"sw_{i}")] for i,w in enumerate(WEIGHTS)]
    kb.append([InlineKeyboardButton("← Назад",callback_data="send")])
    await update.callback_query.edit_message_text(
        f"📦 *Отправить посылку*\n━━━━━━━━━━━━━━━━━━━━\n\n✅ {ctx.user_data['route']}\n✅ {ctx.user_data['type']}\n\n*Шаг 3 из 4* — Вес ⚖️",
        parse_mode="Markdown",reply_markup=InlineKeyboardMarkup(kb))
    return S_WEIGHT

async def s_weight(update,ctx):
    await update.callback_query.answer()
    idx=int(update.callback_query.data.split("_")[1])
    ctx.user_data["weight"]=WEIGHTS[idx]
    kb=[[InlineKeyboardButton(b,callback_data=f"sb_{i}")] for i,b in enumerate(BUDGETS)]
    kb.append([InlineKeyboardButton("← Назад",callback_data="send")])
    await update.callback_query.edit_message_text(
        f"📦 *Отправить посылку*\n━━━━━━━━━━━━━━━━━━━━\n\n✅ {ctx.user_data['route']}\n✅ {ctx.user_data['type']}\n✅ {ctx.user_data['weight']}\n\n*Шаг 4 из 4* — Бюджет 💰",
        parse_mode="Markdown",reply_markup=InlineKeyboardMarkup(kb))
    return S_BUDGET

async def s_budget(update,ctx):
    await update.callback_query.answer()
    idx=int(update.callback_query.data.split("_")[1])
    ctx.user_data["budget"]=BUDGETS[idx]
    d=ctx.user_data
    await update.callback_query.edit_message_text(
        f"📦 *Подтверди заявку*\n━━━━━━━━━━━━━━━━━━━━\n\n🗺 {d['route']}\n📦 {d['type']}\n⚖️ {d['weight']}\n💰 {d['budget']}\n\nВсё верно?",
        parse_mode="Markdown",reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Создать заявку",callback_data="sc")],
            [InlineKeyboardButton("✏️ Изменить",callback_data="send")]]))
    return S_CONFIRM

async def s_confirm(update,ctx):
    await update.callback_query.answer()
    d=ctx.user_data
    uid=update.effective_user.id
    req_id=db.add_request(uid,d["route"].split("→")[0].strip(),d["route"].split("→")[1].strip(),d["weight"],d["type"],d["budget"])
    try:
        await ctx.bot.send_message(ADMIN_ID,f"📦 Новая заявка #{req_id}\n{d['route']} | {d['type']} | {d['weight']}\nБюджет: {d['budget']}")
    except: pass
    await update.callback_query.edit_message_text(
        f"✅ *Заявка #{req_id} создана!*\n━━━━━━━━━━━━━━━━━━━━\n\n🗺 {d['route']}\n📦 {d['type']} | ⚖️ {d['weight']}\n💰 {d['budget']}\n\n🔍 Ищем попутчиков...\nКак только найдём — сразу уведомим! 🙏",
        parse_mode="Markdown",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Главное меню",callback_data="back_main")]]))
    return ConversationHandler.END

async def travel_start(update,ctx):
    await update.callback_query.answer()
    ctx.user_data.clear()
    kb=[]
    for i in range(0,len(ROUTES),2):
        row=[InlineKeyboardButton(f"{ROUTES[i][0]} {ROUTES[i][1]}",callback_data=f"tr_{i}")]
        if i+1<len(ROUTES): row.append(InlineKeyboardButton(f"{ROUTES[i+1][0]} {ROUTES[i+1][1]}",callback_data=f"tr_{i+1}"))
        kb.append(row)
    kb.append([InlineKeyboardButton("✏️ Свой маршрут",callback_data="trcustom")])
    kb.append([InlineKeyboardButton("← Назад",callback_data="back_main")])
    await update.callback_query.edit_message_text("✈️ *Регистрация рейса*\n━━━━━━━━━━━━━━━━━━━━\n\nВозьми посылку и заработай!\n\n*Шаг 1 из 4* — Твой маршрут 🗺",parse_mode="Markdown",reply_markup=InlineKeyboardMarkup(kb))
    return T_ROUTE

async def t_route(update,ctx):
    await update.callback_query.answer()
    idx=int(update.callback_query.data.split("_")[1])
    ctx.user_data["route"]=f"{ROUTES[idx][0]} {ROUTES[idx][1]}"
    kb=[[InlineKeyboardButton(d,callback_data=f"td_{i}")] for i,d in enumerate(DATES)]
    kb.append([InlineKeyboardButton("← Назад",callback_data="travel")])
    await update.callback_query.edit_message_text(
        f"✈️ *Регистрация рейса*\n━━━━━━━━━━━━━━━━━━━━\n\n✅ {ctx.user_data['route']}\n\n*Шаг 2 из 4* — Когда летишь? 📅",
        parse_mode="Markdown",reply_markup=InlineKeyboardMarkup(kb))
    return T_DATE

async def t_date(update,ctx):
    await update.callback_query.answer()
    idx=int(update.callback_query.data.split("_")[1])
    ctx.user_data["date"]=DATES[idx]
    kb=[[InlineKeyboardButton(w,callback_data=f"tw_{i}")] for i,w in enumerate(TWEIGHTS)]
    kb.append([InlineKeyboardButton("← Назад",callback_data="travel")])
    await update.callback_query.edit_message_text(
        f"✈️ *Регистрация рейса*\n━━━━━━━━━━━━━━━━━━━━\n\n✅ {ctx.user_data['route']}\n✅ {ctx.user_data['date']}\n\n*Шаг 3 из 4* — Сколько кг возьмёшь? ⚖️",
        parse_mode="Markdown",reply_markup=InlineKeyboardMarkup(kb))
    return T_WEIGHT

async def t_weight(update,ctx):
    await update.callback_query.answer()
    idx=int(update.callback_query.data.split("_")[1])
    ctx.user_data["weight"]=TWEIGHTS[idx]
    kb=[[InlineKeyboardButton(p,callback_data=f"tp_{i}")] for i,p in enumerate(PRICES)]
    kb.append([InlineKeyboardButton("← Назад",callback_data="travel")])
    await update.callback_query.edit_message_text(
        f"✈️ *Регистрация рейса*\n━━━━━━━━━━━━━━━━━━━━\n\n✅ {ctx.user_data['route']}\n✅ {ctx.user_data['date']}\n✅ {ctx.user_data['weight']}\n\n*Шаг 4 из 4* — Твоя цена за кг 💰",
        parse_mode="Markdown",reply_markup=InlineKeyboardMarkup(kb))
    return T_PRICE

async def t_price(update,ctx):
    await update.callback_query.answer()
    idx=int(update.callback_query.data.split("_")[1])
    ctx.user_data["price"]=PRICES[idx]
    d=ctx.user_data
    await update.callback_query.edit_message_text(
        f"✈️ *Подтверди рейс*\n━━━━━━━━━━━━━━━━━━━━\n\n🗺 {d['route']}\n📅 {d['date']}\n⚖️ {d['weight']}\n💰 {d['price']}\n\nВсё верно?",
        parse_mode="Markdown",reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Зарегистрировать рейс",callback_data="tc")],
            [InlineKeyboardButton("✏️ Изменить",callback_data="travel")]]))
    return T_CONFIRM

async def t_confirm(update,ctx):
    await update.callback_query.answer()
    d=ctx.user_data
    uid=update.effective_user.id
    user=update.effective_user
    trip_id=db.add_trip(uid,d["route"].split("→")[0].strip(),d["route"].split("→")[1].strip(),d["date"],d["weight"],d["price"],"—")
    # Уведомляем отправителей по этому маршруту
    from_city = d["route"].split("→")[0].strip()
    to_city = d["route"].split("→")[1].strip()
    matches = db.find_matches_for_trip(from_city, to_city, 999)
    for m in matches:
        try:
            await ctx.bot.send_message(
                m["user_id"],
                f"🎉 *Найден попутчик по вашему маршруту!*\n\n"
                f"✈️ {d['route']}\n"
                f"📅 {d['date']} | ⚖️ {d['weight']}\n"
                f"💰 Цена: {d['price']}\n\n"
                f"Открой бота чтобы связаться с попутчиком 👇",
                parse_mode="Markdown"
            )
        except: pass
    try:
        await ctx.bot.send_message(ADMIN_ID,f"✈️ Новый рейс #{trip_id}\n{user.first_name} (@{user.username})\n{d['route']} | {d['date']}\nВес: {d['weight']} | Цена: {d['price']}")
    except: pass
    await update.callback_query.edit_message_text(
        f"✅ *Рейс #{trip_id} зарегистрирован!*\n━━━━━━━━━━━━━━━━━━━━\n\n🗺 {d['route']}\n📅 {d['date']} | ⚖️ {d['weight']}\n💰 {d['price']}\n\n📭 Как только появятся заявки — сразу уведомим!",
        parse_mode="Markdown",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Главное меню",callback_data="back_main")]]))
    return ConversationHandler.END

async def back(update,ctx):
    await update.callback_query.answer()
    dest=update.callback_query.data.split("_",1)[1]
    if dest=="main": return await start(update,ctx)
    elif dest=="send": return await send_start(update,ctx)
    elif dest=="travel": return await travel_start(update,ctx)

def main():
    app=Application.builder().token(TOKEN).build()
    conv=ConversationHandler(
        entry_points=[CommandHandler("start",start),CallbackQueryHandler(send_start,pattern="^send$"),CallbackQueryHandler(travel_start,pattern="^travel$")],
        states={
            MAIN:[CallbackQueryHandler(send_start,pattern="^send$"),CallbackQueryHandler(travel_start,pattern="^travel$"),CallbackQueryHandler(how,pattern="^how$"),CallbackQueryHandler(my_req,pattern="^my$"),CallbackQueryHandler(bl,pattern="^blacklist$")],
            S_ROUTE:[CallbackQueryHandler(s_route,pattern="^sr_"),CallbackQueryHandler(s_custom,pattern="^srcustom$")],
            S_CUSTOM:[MessageHandler(filters.TEXT & ~filters.COMMAND, handle_custom_route)],
            S_TYPE:[CallbackQueryHandler(s_type,pattern="^st_")],
            S_WEIGHT:[CallbackQueryHandler(s_weight,pattern="^sw_")],
            S_BUDGET:[CallbackQueryHandler(s_budget,pattern="^sb_")],
            S_CONFIRM:[CallbackQueryHandler(s_confirm,pattern="^sc$")],
            T_ROUTE:[CallbackQueryHandler(t_route,pattern="^tr_"),CallbackQueryHandler(t_custom,pattern="^trcustom$")],
            T_CUSTOM:[MessageHandler(filters.TEXT & ~filters.COMMAND, handle_custom_route)],
            T_DATE:[CallbackQueryHandler(t_date,pattern="^td_")],
            T_WEIGHT:[CallbackQueryHandler(t_weight,pattern="^tw_")],
            T_PRICE:[CallbackQueryHandler(t_price,pattern="^tp_")],
            T_CONFIRM:[CallbackQueryHandler(t_confirm,pattern="^tc$")],
        },
        fallbacks=[CommandHandler("start",start),CallbackQueryHandler(back,pattern="^back_")],
        per_user=True,per_chat=True,
    )
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(back,pattern="^back_"))
    app.add_handler(CallbackQueryHandler(how,pattern="^how$"))
    app.add_handler(CallbackQueryHandler(my_req,pattern="^my$"))
    app.add_handler(CallbackQueryHandler(bl,pattern="^blacklist$"))
    log.info("🚀 ParcelGo Bot запущен!")
    app.run_polling(drop_pending_updates=True)

if __name__=="__main__":
    main()