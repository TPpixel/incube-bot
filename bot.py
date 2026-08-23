import json
import os
import html
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

TOKEN = os.environ.get("BOT_TOKEN", "")
OWNER_FILE = os.path.join(os.path.dirname(__file__), "owner.json")
REVIEWS_FILE = os.path.join(os.path.dirname(__file__), "reviews.json")
MESSAGES_FILE = os.path.join(os.path.dirname(__file__), "messages.json")

GAMES = ["Space Hero", "Car Simulator", "Planer", "Beach Shooter", "Hit The Ball"]

WELCOME, CHOOSE_GAME, ENTER_NAME, ENTER_STARS, ENTER_TEXT, ENTER_MSG = range(6)


def load_owner():
    if os.path.exists(OWNER_FILE):
        with open(OWNER_FILE, "r") as f:
            return json.load(f).get("owner_id")
    return None


def save_owner(user_id):
    with open(OWNER_FILE, "w") as f:
        json.dump({"owner_id": user_id}, f)


def load_json(filepath):
    if os.path.exists(filepath):
        with open(filepath, "r") as f:
            return json.load(f)
    return []


def save_json(filepath, data):
    with open(filepath, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def save_review(review):
    reviews = load_json(REVIEWS_FILE)
    review["status"] = "new"
    reviews.append(review)
    save_json(REVIEWS_FILE, reviews)


def save_message(msg):
    messages = load_json(MESSAGES_FILE)
    msg["status"] = "new"
    messages.append(msg)
    save_json(MESSAGES_FILE, messages)


def mark_all_read(filepath):
    data = load_json(filepath)
    for item in data:
        item["status"] = "read"
    save_json(filepath, data)


def count_new(filepath):
    return sum(1 for item in load_json(filepath) if item.get("status") == "new")


def make_stars_html(count):
    return '<img class="star-icon" src="img/star.png">' * count


def make_review_html(review):
    star_img = '<img class="star-icon" src="img/star.png">'
    stars_lines = "\n".join(
        f"        {star_img}" for _ in range(review["stars"])
    )
    return (
        '<div class="review-card">\n'
        '    <div class="review-header">\n'
        f'        <span class="review-name">{review["name"]}</span>\n'
        '        <span class="review-stars">\n'
        f"{stars_lines}\n"
        '        </span>\n'
        '    </div>\n'
        f'    <p class="review-text">{review["text"]}</p>\n'
        '</div>'
    )


GAME_SLUGS = {
    "Space Hero": "spacehero",
    "Car Simulator": "carsim",
    "Planer": "planer",
    "Beach Shooter": "beachshooter",
    "Hit The Ball": "hitball",
}


def owner_menu_keyboard():
    new_reviews = count_new(REVIEWS_FILE)
    new_messages = count_new(MESSAGES_FILE)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            f"Отзывы ({new_reviews} новых)",
            callback_data="owner_reviews"
        )],
        [InlineKeyboardButton(
            f"Сообщения ({new_messages} новых)",
            callback_data="owner_messages"
        )],
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    owner_id = load_owner()

    if owner_id is None:
        save_owner(user_id)
        await update.message.reply_text(
            "Ты установлен как владелец бота.\n"
            "Пользователи смогут писать тебе отзывы."
        )
        return ConversationHandler.END

    if user_id == owner_id:
        await update.message.reply_text(
            "Привет, владелец!",
            reply_markup=owner_menu_keyboard(),
        )
        return ConversationHandler.END

    keyboard = [
        [InlineKeyboardButton("Оставить отзыв", callback_data="start_review")],
        [InlineKeyboardButton("Сообщение автору", callback_data="start_msg")],
    ]
    await update.message.reply_text(
        "Привет! Добро пожаловать.",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return WELCOME


async def welcome_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    choice = query.data

    if choice == "start_review":
        keyboard = [
            [InlineKeyboardButton(g, callback_data=f"game:{g}")]
            for g in GAMES
        ]
        await query.edit_message_text(
            "Выбери игру:",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return CHOOSE_GAME
    elif choice == "start_msg":
        await query.edit_message_text("Напиши сообщение для автора:")
        return ENTER_MSG


async def game_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    game = query.data.split(":", 1)[1]
    context.user_data["game"] = game
    await query.edit_message_text(
        f"Игра: {game}\nКак тебя зовут? (имя или ник):"
    )
    return ENTER_NAME


async def enter_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text
    keyboard = [
        [InlineKeyboardButton(f"{i} \u2b50", callback_data=f"stars:{i}")]
        for i in range(1, 6)
    ]
    await update.message.reply_text(
        "Оцени игру:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return ENTER_STARS


async def stars_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    stars = int(query.data.split(":", 1)[1])
    context.user_data["stars"] = stars
    await query.edit_message_text(f"Оценка: {stars}/5\nНапиши свой отзыв:")
    return ENTER_TEXT


async def enter_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    review = {
        "game": context.user_data["game"],
        "name": context.user_data["name"],
        "stars": context.user_data["stars"],
        "text": update.message.text,
        "user": user.username or user.first_name,
        "user_id": user.id,
    }
    save_review(review)

    owner_id = load_owner()
    if owner_id:
        stars_str = "\u2b50" * review["stars"]
        readable = (
            "\U0001f4dd \u041d\u043e\u0432\u044b\u0439 \u043e\u0442\u0437\u044b\u0432!\n\n"
            f"\U0001f3ae \u0418\u0433\u0440\u0430: {review['game']}\n"
            f"\U0001f464 \u0418\u043c\u044f: {review['name']}\n"
            f"\u2b50 \u041e\u0446\u0435\u043d\u043a\u0430: {stars_str}/5\n"
            f"\U0001f4ac \u0422\u0435\u043a\u0441\u0442: {review['text']}\n"
            f"\U0001f517 Telegram: @{review['user']}"
        )
        await context.bot.send_message(chat_id=owner_id, text=readable)

        html_code = make_review_html(review)
        escaped = html.escape(html_code)
        html_msg = f"<pre>{escaped}</pre>"
        await context.bot.send_message(
            chat_id=owner_id, text=html_msg, parse_mode="HTML"
        )

    await update.message.reply_text(
        "\u0421\u043f\u0430\u0441\u0438\u0431\u043e \u0437\u0430 \u043e\u0442\u0437\u044b\u0432! "
        "\u041e\u043d \u0431\u0443\u0434\u0435\u0442 \u043e\u043f\u0443\u0431\u043b\u0438\u043a\u043e\u0432\u0430\u043d "
        "\u043f\u043e\u0441\u043b\u0435 \u043f\u0440\u043e\u0432\u0435\u0440\u043a\u0438."
    )
    return ConversationHandler.END


async def enter_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    msg = {
        "text": update.message.text,
        "user": user.username or user.first_name,
        "user_id": user.id,
    }
    save_message(msg)

    owner_id = load_owner()
    if owner_id:
        text = (
            "\U0001f4e9 \u0421\u043e\u043e\u0431\u0449\u0435\u043d\u0438\u0435 \u043e\u0442 "
            "\u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044f!\n\n"
            f"\U0001f464 \u0418\u043c\u044f: {user.first_name}"
            f"{' (@' + user.username + ')' if user.username else ''}\n"
            f"\U0001f517 Telegram: tg://user?id={user.id}\n\n"
            f"\U0001f4ac \u0421\u043e\u043e\u0431\u0449\u0435\u043d\u0438\u0435:\n{update.message.text}"
        )
        await context.bot.send_message(chat_id=owner_id, text=text)

    await update.message.reply_text(
        "\u0421\u043e\u043e\u0431\u0449\u0435\u043d\u0438\u0435 \u043e\u0442\u043f\u0440\u0430\u0432\u043b\u0435\u043d\u043e!"
    )
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("\u041e\u0442\u043c\u0435\u043d\u0435\u043d\u043e.")
    return ConversationHandler.END


async def owner_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "owner_reviews":
        new_count = count_new(REVIEWS_FILE)
        if new_count == 0:
            await query.edit_message_text(
                "Новых отзывов нет.",
                reply_markup=owner_menu_keyboard(),
            )
            return
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                "Посмотреть",
                callback_data="owner_view_reviews"
            )],
            [InlineKeyboardButton(
                "Назад",
                callback_data="owner_back"
            )],
        ])
        await query.edit_message_text(
            f"Новых отзывов: {new_count}",
            reply_markup=keyboard,
        )

    elif data == "owner_view_reviews":
        reviews = load_json(REVIEWS_FILE)
        new_reviews = [r for r in reviews if r.get("status") == "new"]
        if not new_reviews:
            await query.edit_message_text(
                "Новых отзывов нет.",
                reply_markup=owner_menu_keyboard(),
            )
            return
        await query.edit_message_text(
            f"{len(new_reviews)} новых отзывов:"
        )
        for r in new_reviews:
            stars_str = "\u2b50" * r["stars"]
            text = (
                f"\U0001f3ae \u0418\u0433\u0440\u0430: {r['game']}\n"
                f"\U0001f464 \u0418\u043c\u044f: {r['name']}\n"
                f"\u2b50 \u041e\u0446\u0435\u043d\u043a\u0430: {stars_str}/5\n"
                f"\U0001f4ac \u0422\u0435\u043a\u0441\u0442: {r['text']}\n"
                f"\U0001f517 @{r['user']}"
            )
            await context.bot.send_message(
                chat_id=query.message.chat.id, text=text
            )
            html_code = make_review_html(r)
            escaped = html.escape(html_code)
            html_msg = f"<pre>{escaped}</pre>"
            await context.bot.send_message(
                chat_id=query.message.chat.id,
                text=html_msg,
                parse_mode="HTML",
            )
        mark_all_read(REVIEWS_FILE)
        await context.bot.send_message(
            chat_id=query.message.chat.id,
            text="\u2705 \u0412\u0441\u0435 \u043d\u043e\u0432\u044b\u0435 \u043e\u0442\u0437\u044b\u0432\u044b \u043f\u0440\u043e\u0447\u0438\u0442\u0430\u043d\u044b.",
            reply_markup=owner_menu_keyboard(),
        )

    elif data == "owner_messages":
        new_count = count_new(MESSAGES_FILE)
        if new_count == 0:
            await query.edit_message_text(
                "Новых сообщений нет.",
                reply_markup=owner_menu_keyboard(),
            )
            return
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                "Посмотреть",
                callback_data="owner_view_messages"
            )],
            [InlineKeyboardButton(
                "Назад",
                callback_data="owner_back"
            )],
        ])
        await query.edit_message_text(
            f"Новых сообщений: {new_count}",
            reply_markup=keyboard,
        )

    elif data == "owner_view_messages":
        messages = load_json(MESSAGES_FILE)
        new_messages = [m for m in messages if m.get("status") == "new"]
        if not new_messages:
            await query.edit_message_text(
                "Новых сообщений нет.",
                reply_markup=owner_menu_keyboard(),
            )
            return
        await query.edit_message_text(
            f"{len(new_messages)} новых сообщений:"
        )
        for m in new_messages:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(
                    "Ответить",
                    callback_data=f"reply:{m['user_id']}"
                )],
            ])
            text = (
                f"\U0001f464 {m['user']}\n"
                f"\U0001f517 tg://user?id={m['user_id']}\n\n"
                f"\U0001f4ac {m['text']}"
            )
            await context.bot.send_message(
                chat_id=query.message.chat.id,
                text=text,
                reply_markup=keyboard,
            )
        mark_all_read(MESSAGES_FILE)
        await context.bot.send_message(
            chat_id=query.message.chat.id,
            text="\u2705 \u0412\u0441\u0435 \u043d\u043e\u0432\u044b\u0435 \u0441\u043e\u043e\u0431\u0449\u0435\u043d\u0438\u044f \u043f\u0440\u043e\u0447\u0438\u0442\u0430\u043d\u044b.",
            reply_markup=owner_menu_keyboard(),
        )

    elif data == "owner_back":
        await query.edit_message_text(
            "Привет, владелец!",
            reply_markup=owner_menu_keyboard(),
        )

    elif data.startswith("reply:"):
        target_user_id = int(data.split(":", 1)[1])
        context.user_data["reply_to"] = target_user_id
        await query.edit_message_text(
            f"Напиши ответ пользователю:"
        )


async def owner_reply_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    owner_id = load_owner()
    if user_id != owner_id:
        return
    target_user_id = context.user_data.get("reply_to")
    if not target_user_id:
        return
    context.user_data.pop("reply_to", None)
    await context.bot.send_message(
        chat_id=target_user_id,
        text=f"\U0001f4e9 \u041e\u0442\u0432\u0435\u0442 \u043e\u0442 \u0430\u0432\u0442\u043e\u0440\u0430:\n\n{update.message.text}",
    )
    await update.message.reply_text(
        "\u041e\u0442\u0432\u0435\u0442 \u043e\u0442\u043f\u0440\u0430\u0432\u043b\u0435\u043d!",
        reply_markup=owner_menu_keyboard(),
    )


def main():
    from telegram.request import HTTPXRequest
    request = HTTPXRequest(connect_timeout=30, read_timeout=30, write_timeout=30)
    app = Application.builder().token(TOKEN).request(request).build()

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CommandHandler("review", start),
        ],
        states={
            WELCOME: [
                CallbackQueryHandler(
                    welcome_chosen,
                    pattern=r"^start_(review|msg)$"
                ),
            ],
            CHOOSE_GAME: [
                CallbackQueryHandler(game_chosen, pattern=r"^game:")
            ],
            ENTER_NAME: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, enter_name
                )
            ],
            ENTER_STARS: [
                CallbackQueryHandler(stars_chosen, pattern=r"^stars:")
            ],
            ENTER_TEXT: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, enter_text
                )
            ],
            ENTER_MSG: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, enter_msg
                )
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(
        owner_callback,
        pattern=r"^owner_|^reply:"
    ))
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        owner_reply_handler
    ))

    print("Бот запущен!")
    app.run_polling()


if __name__ == "__main__":
    main()
