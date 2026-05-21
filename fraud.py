"""
fraud.py — система жалоб и защиты от мошенников
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler, ConversationHandler, MessageHandler, filters
from database import db
from config import ADMIN_ID

# Состояния
REPORT_REASON, REPORT_DETAILS = range(20, 22)

FRAUD_REASONS = [
    ("💸 Взял деньги и пропал",        "money_gone"),
    ("📦 Не доставил посылку",          "not_delivered"),
    ("🪪 Фальшивые документы",          "fake_docs"),
    ("💬 Угрозы / шантаж",             "threats"),
    ("📦 Вскрыл / украл из посылки",    "stolen"),
    ("🤖 Фейковый аккаунт",            "fake_account"),
    ("⚠️ Другое",                       "other"),
]

# ── Инициализация таблиц жалоб ────────────────────────────────────────────────
def init_fraud_tables():
    db.conn.executescript("""
        ALTER TABLE users ADD COLUMN status TEXT DEFAULT 'active';
        ALTER TABLE users ADD COLUMN reports_count INTEGER DEFAULT 0;
        ALTER TABLE users ADD COLUMN banned_at TEXT;
        ALTER TABLE users ADD COLUMN ban_reason TEXT;
    """) if not _column_exists("users", "status") else None

    db.conn.executescript("""
        CREATE TABLE IF NOT EXISTS reports (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            reporter_id  INTEGER NOT NULL,
            accused_id   INTEGER NOT NULL,
            req_id       INTEGER,
            reason_code  TEXT    NOT NULL,
            reason_text  TEXT,
            details      TEXT,
            status       TEXT    DEFAULT 'pending',
            admin_note   TEXT,
            created_at   TEXT    DEFAULT (datetime('now')),
            FOREIGN KEY (reporter_id) REFERENCES users(id),
            FOREIGN KEY (accused_id)  REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS blacklist (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER NOT NULL UNIQUE,
            banned_by    INTEGER,
            reason       TEXT,
            evidence     TEXT,
            banned_at    TEXT DEFAULT (datetime('now')),
            is_public    INTEGER DEFAULT 1
        );
    """)
    db.conn.commit()


def _column_exists(table, col):
    cur = db.conn.execute(f"PRAGMA table_info({table})")
    return any(row[1] == col for row in cur.fetchall())


# ── Проверка при показе профиля/маршрута ──────────────────────────────────────
def get_user_fraud_status(user_id: int) -> dict:
    """
    Возвращает:
      status: 'clean' | 'warned' | 'suspected' | 'banned'
      reports: количество жалоб
      label: строка для отображения
    """
    # Проверяем чёрный список
    in_bl = db.conn.execute(
        "SELECT * FROM blacklist WHERE user_id=?", (user_id,)
    ).fetchone()
    if in_bl:
        return {"status": "banned", "reports": 0, "label": "🚫 МОШЕННИК — заблокирован"}

    # Считаем подтверждённые жалобы
    confirmed = db.conn.execute(
        "SELECT COUNT(*) FROM reports WHERE accused_id=? AND status='confirmed'",
        (user_id,)
    ).fetchone()[0]

    pending = db.conn.execute(
        "SELECT COUNT(*) FROM reports WHERE accused_id=? AND status='pending'",
        (user_id,)
    ).fetchone()[0]

    total = confirmed + pending

    if confirmed >= 3 or total >= 5:
        return {"status": "suspected", "reports": total,
                "label": f"⚠️ ПОДОЗРИТЕЛЬНЫЙ — {total} жалоб"}
    elif total >= 1:
        return {"status": "warned", "reports": total,
                "label": f"⚡ Есть жалоба ({total})"}
    return {"status": "clean", "reports": 0, "label": ""}


def fraud_warning_text(user_id: int) -> str:
    """Текст предупреждения для показа перед сделкой"""
    fs = get_user_fraud_status(user_id)
    if fs["status"] == "banned":
        return (
            "\n\n🚫 *ВНИМАНИЕ! МОШЕННИК*\n"
            "Этот пользователь заблокирован за мошенничество.\n"
            "Не совершай с ним никаких сделок!"
        )
    elif fs["status"] == "suspected":
        return (
            f"\n\n⚠️ *ОСТОРОЖНО! {fs['reports']} жалоб*\n"
            "На этого пользователя поступило несколько жалоб.\n"
            "Будь внимателен при совершении сделки."
        )
    elif fs["status"] == "warned":
        return (
            f"\n\n⚡ *Внимание: есть жалоба*\n"
            "На этого пользователя поступала жалоба.\n"
            "Проверь отзывы перед сделкой."
        )
    return ""


# ── Кнопка «Пожаловаться» ─────────────────────────────────────────────────────
def report_button(accused_id: int, req_id: int = 0) -> InlineKeyboardButton:
    return InlineKeyboardButton(
        "🚨 Пожаловаться",
        callback_data=f"report_start_{accused_id}_{req_id}"
    )


async def report_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    parts = update.callback_query.data.split("_")
    accused_id = int(parts[2])
    req_id     = int(parts[3])

    ctx.user_data["report_accused"] = accused_id
    ctx.user_data["report_req"]     = req_id

    accused = db.get_user(accused_id)
    fs = get_user_fraud_status(accused_id)

    # Проверяем не жаловался ли уже
    already = db.conn.execute(
        "SELECT id FROM reports WHERE reporter_id=? AND accused_id=? AND status='pending'",
        (update.effective_user.id, accused_id)
    ).fetchone()
    if already:
        await update.callback_query.edit_message_text(
            "ℹ️ Ты уже подал жалобу на этого пользователя.\nМы рассматриваем её.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("← Назад", callback_data="back_start")
            ]])
        )
        return ConversationHandler.END

    name = accused["name"] if accused else f"ID {accused_id}"
    extra = f"\n{fs['label']}" if fs["label"] else ""

    keyboard = [[InlineKeyboardButton(r, callback_data=f"report_reason_{code}")]
                for r, code in FRAUD_REASONS]
    keyboard.append([InlineKeyboardButton("← Отмена", callback_data="back_start")])

    await update.callback_query.edit_message_text(
        f"🚨 *Жалоба на пользователя {name}*{extra}\n\n"
        f"Выбери причину жалобы:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return REPORT_REASON


async def report_reason(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    code = update.callback_query.data.replace("report_reason_", "")
    reason_text = next((r for r, c in FRAUD_REASONS if c == code), code)

    ctx.user_data["report_code"]   = code
    ctx.user_data["report_reason"] = reason_text

    await update.callback_query.edit_message_text(
        f"🚨 Причина: *{reason_text}*\n\n"
        f"Опиши подробнее что произошло:\n"
        f"_Например: дата, сумма, что обещал и что сделал_\n\n"
        f"Или нажми /skip чтобы пропустить",
        parse_mode="Markdown"
    )
    return REPORT_DETAILS


async def report_skip(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    ctx.user_data["report_details"] = ""
    return await _save_report(update, ctx)


async def report_details(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    ctx.user_data["report_details"] = update.message.text.strip()
    return await _save_report(update, ctx)


async def _save_report(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    d = ctx.user_data
    reporter_id = update.effective_user.id
    accused_id  = d["report_accused"]
    req_id      = d.get("report_req", 0)

    # Сохраняем жалобу
    cur = db.conn.execute(
        "INSERT INTO reports (reporter_id,accused_id,req_id,reason_code,reason_text,details) VALUES (?,?,?,?,?,?)",
        (reporter_id, accused_id, req_id, d["report_code"], d["report_reason"], d.get("report_details",""))
    )
    db.conn.commit()
    report_id = cur.lastrowid

    # Считаем сколько жалоб на обвиняемого
    total = db.conn.execute(
        "SELECT COUNT(*) FROM reports WHERE accused_id=?", (accused_id,)
    ).fetchone()[0]

    # Если жалоб >= 3 — авто-уведомление админу с пометкой СРОЧНО
    urgency = "🚨🚨🚨 СРОЧНО" if total >= 3 else "📋 Новая жалоба"

    accused = db.get_user(accused_id)
    accused_name = accused["name"] if accused else f"ID {accused_id}"

    # Уведомляем администратора
    keyboard = [
        [
            InlineKeyboardButton("🚫 Заблокировать", callback_data=f"admin_ban_{accused_id}_{report_id}"),
            InlineKeyboardButton("✅ Отклонить жалобу", callback_data=f"admin_dismiss_{report_id}"),
        ],
        [InlineKeyboardButton("👀 Все жалобы на пользователя", callback_data=f"admin_all_reports_{accused_id}")],
    ]

    try:
        msg = update.message or update.callback_query.message
        await msg.bot.send_message(
            ADMIN_ID,
            f"{urgency} #{report_id}\n\n"
            f"👤 Обвиняемый: *{accused_name}* (ID: `{accused_id}`)\n"
            f"📝 Причина: {d['report_reason']}\n"
            f"📄 Детали: {d.get('report_details','—') or '—'}\n"
            f"🔗 Заявка: #{req_id if req_id else '—'}\n"
            f"📊 Всего жалоб на пользователя: *{total}*\n\n"
            f"От: ID {reporter_id}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception:
        pass

    text = (
        f"✅ *Жалоба принята* (#{report_id})\n\n"
        f"Мы рассмотрим её в течение 24 часов.\n"
        f"При подтверждении мошенничества пользователь будет заблокирован "
        f"и внесён в публичный чёрный список.\n\n"
        f"Спасибо что делаешь сервис безопаснее! 🛡"
    )
    reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Главное меню", callback_data="back_start")]])

    if update.message:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=reply_markup)
    else:
        await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=reply_markup)

    return ConversationHandler.END


# ── ADMIN: заблокировать пользователя ─────────────────────────────────────────
async def admin_ban_user(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer("🚫 Пользователь заблокирован")
    parts = update.callback_query.data.split("_")
    accused_id = int(parts[2])
    report_id  = int(parts[3])

    accused = db.get_user(accused_id)
    name = accused["name"] if accused else f"ID {accused_id}"

    # Добавляем в чёрный список
    db.conn.execute(
        "INSERT OR REPLACE INTO blacklist (user_id, banned_by, reason) VALUES (?,?,?)",
        (accused_id, update.effective_user.id, "Подтверждённое мошенничество")
    )
    db.conn.execute(
        "UPDATE reports SET status='confirmed' WHERE accused_id=? AND status='pending'",
        (accused_id,)
    )
    db.conn.commit()

    # Уведомляем все стороны с активными заявками
    active_requests = db.conn.execute(
        "SELECT DISTINCT r.user_id FROM requests r "
        "JOIN trips t ON r.trip_id = t.id "
        "WHERE (t.user_id=? OR r.user_id=?) AND r.status NOT IN ('completed','cancelled')",
        (accused_id, accused_id)
    ).fetchall()

    warned_count = 0
    for row in active_requests:
        victim_id = row[0]
        if victim_id == accused_id:
            continue
        try:
            await ctx.bot.send_message(
                victim_id,
                f"🚨 *Важное предупреждение!*\n\n"
                f"Пользователь, с которым у тебя была активная заявка, "
                f"заблокирован за мошенничество.\n\n"
                f"Если ты уже перевёл деньги — немедленно напиши нам: @{ctx.bot.username}\n"
                f"Мы поможем разобраться.",
                parse_mode="Markdown"
            )
            warned_count += 1
        except Exception:
            pass

    # Сообщаем и мошеннику
    try:
        await ctx.bot.send_message(
            accused_id,
            "🚫 *Твой аккаунт заблокирован*\n\n"
            "На тебя поступили жалобы, подтверждённые администрацией.\n"
            "Ты внесён в публичный чёрный список сервиса.\n\n"
            "Если считаешь это ошибкой — напиши @support",
            parse_mode="Markdown"
        )
    except Exception:
        pass

    await update.callback_query.edit_message_text(
        f"🚫 *{name}* (ID: {accused_id}) заблокирован\n\n"
        f"• Внесён в чёрный список\n"
        f"• Все жалобы помечены как подтверждённые\n"
        f"• Предупреждено пострадавших: {warned_count}",
        parse_mode="Markdown"
    )


# ── ADMIN: отклонить жалобу ───────────────────────────────────────────────────
async def admin_dismiss_report(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer("✅ Жалоба отклонена")
    report_id = int(update.callback_query.data.split("_")[2])

    report = db.conn.execute("SELECT * FROM reports WHERE id=?", (report_id,)).fetchone()
    db.conn.execute("UPDATE reports SET status='dismissed' WHERE id=?", (report_id,))
    db.conn.commit()

    # Уведомляем жалобщика
    if report:
        try:
            await ctx.bot.send_message(
                report["reporter_id"],
                f"ℹ️ По твоей жалобе #{report_id} мы провели проверку.\n"
                f"На данный момент оснований для блокировки не найдено.\n"
                f"Если ситуация повторится — сообщи снова.",
                parse_mode="Markdown"
            )
        except Exception:
            pass

    await update.callback_query.edit_message_text(
        f"✅ Жалоба #{report_id} отклонена. Пользователь уведомлён.",
        parse_mode="Markdown"
    )


# ── ADMIN: все жалобы на пользователя ────────────────────────────────────────
async def admin_all_reports(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    accused_id = int(update.callback_query.data.split("_")[3])

    reports = db.conn.execute(
        "SELECT * FROM reports WHERE accused_id=? ORDER BY created_at DESC LIMIT 10",
        (accused_id,)
    ).fetchall()

    if not reports:
        await update.callback_query.answer("Жалоб не найдено", show_alert=True)
        return

    accused = db.get_user(accused_id)
    name = accused["name"] if accused else f"ID {accused_id}"

    text = f"📋 *Все жалобы на {name}*\n\n"
    for r in reports:
        status_emoji = {"pending":"⏳","confirmed":"✅","dismissed":"❌"}.get(r["status"],"❓")
        text += (
            f"{status_emoji} #{r['id']} | {r['reason_text']}\n"
            f"   {r['details'][:50] + '...' if r['details'] and len(r['details'])>50 else r['details'] or '—'}\n"
            f"   📅 {r['created_at'][:10]}\n\n"
        )

    keyboard = [
        [InlineKeyboardButton("🚫 Заблокировать", callback_data=f"admin_ban_{accused_id}_{reports[0]['id']}")],
        [InlineKeyboardButton("← Закрыть", callback_data="back_start")],
    ]
    await update.callback_query.edit_message_text(text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard))


# ── Публичный чёрный список (команда /blacklist) ──────────────────────────────
async def show_blacklist(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    rows = db.conn.execute(
        "SELECT bl.*, u.name, u.username FROM blacklist bl "
        "JOIN users u ON bl.user_id = u.id "
        "WHERE bl.is_public=1 ORDER BY bl.banned_at DESC LIMIT 20"
    ).fetchall()

    if not rows:
        await update.message.reply_text("✅ Чёрный список пуст. Все участники чисты!")
        return

    text = "🚫 *Чёрный список ParcelGold*\n\n"
    for r in rows:
        uname = f"@{r['username']}" if r["username"] else ""
        text += f"• *{r['name']}* {uname} — {r['reason']} | {r['banned_at'][:10]}\n"
    text += "\n_Обновляется в реальном времени. Не работайте с этими людьми._"

    await update.message.reply_text(text, parse_mode="Markdown")


# ── ConversationHandler для жалоб ─────────────────────────────────────────────
def get_report_conversation():
    from telegram.ext import CommandHandler
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(report_start, pattern="^report_start_")],
        states={
            REPORT_REASON:  [CallbackQueryHandler(report_reason, pattern="^report_reason_")],
            REPORT_DETAILS: [
                CommandHandler("skip", report_skip),
                MessageHandler(filters.TEXT & ~filters.COMMAND, report_details),
            ],
        },
        fallbacks=[CallbackQueryHandler(lambda u,c: ConversationHandler.END, pattern="^back_start$")],
        per_user=True, per_chat=True,
    )


# ── Регистрация всех хендлеров ────────────────────────────────────────────────
def register_fraud_handlers(app):
    from telegram.ext import CommandHandler
    init_fraud_tables()

    app.add_handler(get_report_conversation())
    app.add_handler(CallbackQueryHandler(admin_ban_user,      pattern="^admin_ban_"))
    app.add_handler(CallbackQueryHandler(admin_dismiss_report,pattern="^admin_dismiss_"))
    app.add_handler(CallbackQueryHandler(admin_all_reports,   pattern="^admin_all_reports_"))
    app.add_handler(CommandHandler("blacklist", show_blacklist))
