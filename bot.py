import os
from dotenv import load_dotenv
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ConversationHandler,
    ContextTypes
)

load_dotenv()
TOKEN = os.getenv("TOKEN")

# Этапы диалога
(
    START, OFFICE, CUISINE, ALLERGIES, DIVERSITY, LUNCH_DURATION, LUNCH_TYPE, BUDGET
) = range(8)

# Функция для создания клавиатуры

def create_reply_keyboard(options):
    return ReplyKeyboardMarkup(
        [[option] for option in options], resize_keyboard=True, one_time_keyboard=True
    )

# Варианты ответов
office_options = ["пер. Виленский, 14А", "Дегтярный пер., 11Б", "Киевская ул., 5 корп. 4"]
cuisine_options = ["Итальянская", "Японская", "Мексиканская", "Веганская", "Не важно"]
allergy_options = ["Орехи", "Лактоза", "Глютен", "Нет аллергий"]
diversity_options = ["Люблю новые места", "Чаще хожу в проверенные места"]
lunch_duration_options = ["1 час", "45 мин", "30 мин", "20 мин"]
lunch_type_options = ["Полноценный обед", "Бизнес-ланч", "Перекус"]
budget_options = ["до 500 руб.", "500-1000 руб.", "1000+ руб."]

# Начало диалога (стартовый экран)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "Привет! Я помогу тебе подобрать место для обеда.\n"
        "Выбери офис:",
        reply_markup=create_reply_keyboard(office_options)
    )
    return OFFICE

async def office(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["office"] = update.message.text
    await update.message.reply_text("Какую кухню предпочитаешь?", reply_markup=create_reply_keyboard(cuisine_options))
    return CUISINE

async def cuisine(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["cuisine"] = update.message.text
    await update.message.reply_text("Есть ли у тебя аллергии?", reply_markup=create_reply_keyboard(allergy_options))
    return ALLERGIES

async def allergies(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["allergies"] = update.message.text
    await update.message.reply_text("Ты любишь пробовать новые места?", reply_markup=create_reply_keyboard(diversity_options))
    return DIVERSITY

async def diversity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["diversity"] = update.message.text
    await update.message.reply_text("Сколько времени у тебя есть на обед?", reply_markup=create_reply_keyboard(lunch_duration_options))
    return LUNCH_DURATION

async def lunch_duration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["lunch_duration"] = update.message.text
    await update.message.reply_text("Какой у тебя тип обеда?", reply_markup=create_reply_keyboard(lunch_type_options))
    return LUNCH_TYPE

async def lunch_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["lunch_type"] = update.message.text
    await update.message.reply_text("Какой у тебя бюджет?", reply_markup=create_reply_keyboard(budget_options))
    return BUDGET

async def budget(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["budget"] = update.message.text
    summary = (
        f"📍 Офис: {context.user_data.get('office', 'Не указано')}\n"
        f"🍽 Кухня: {context.user_data.get('cuisine', 'Не указано')}\n"
        f"⚠ Аллергии: {context.user_data.get('allergies', 'Не указано')}\n"
        f"🌍 Разнообразие: {context.user_data.get('diversity', 'Не указано')}\n"
        f"⏳ Время на обед: {context.user_data.get('lunch_duration', 'Не указано')}\n"
        f"🥗 Тип обеда: {context.user_data.get('lunch_type', 'Не указано')}\n"
        f"💰 Бюджет: {context.user_data.get('budget', 'Не указано')}\n"
    )
    await update.message.reply_text(f"🎉 Спасибо! Вот твои предпочтения:\n{summary}", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# Команда отмены
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("❌ Диалог отменен.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# Создание приложения
app = ApplicationBuilder().token(TOKEN).build()

# Обработчик диалогов
conv_handler = ConversationHandler(
    entry_points=[CommandHandler("start", start)],
    states={
        OFFICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, office)],
        CUISINE: [MessageHandler(filters.TEXT & ~filters.COMMAND, cuisine)],
        ALLERGIES: [MessageHandler(filters.TEXT & ~filters.COMMAND, allergies)],
        DIVERSITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, diversity)],
        LUNCH_DURATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, lunch_duration)],
        LUNCH_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, lunch_type)],
        BUDGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, budget)],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
)

# Добавление обработчиков
app.add_handler(conv_handler)

# Запуск бота
app.run_polling()
