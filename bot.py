import os
from dotenv import load_dotenv
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes
)
from collections import defaultdict

load_dotenv()
TOKEN = os.getenv("TOKEN")

# Этапы голосования (для удобства)
OFFICE, CUISINE, RESTRICTIONS, BUDGET, WALK_TIME = range(5)

# Карты для преобразования текстовых вариантов в числа (для итогового словаря)
BUDGET_MAP = {
    "💵 До 500 руб.": 500,
    "💵 До 1000 руб.": 1000,
    "💵 До 1500 руб.": 1500,
    "💵 Без разницы": 999999  # условное значение
}
WALK_TIME_MAP = {
    "🚶 До 5 минут": 5,
    "🚶 До 10 минут": 10,
    "🚶 До 15 минут": 15
}

def init_group_data():
    """
    Структура данных опроса.
    Для вопросов с одним выбором (офис, бюджет) будем хранить словари:
      user_id -> выбранный вариант.
    Для вопросов с несколькими вариантами (кухня, ограничения, время) – defaultdict(set).
    """
    return {
        "office": {},           # {user_id: выбранный офис}
        "wanted_cuisines": defaultdict(set),  # {вариант: {user_id1, user_id2, ...}}
        "food_restrictions": defaultdict(set),
        "price_limit": {},      # {user_id: выбранный чек}
        "walk_time": defaultdict(set),
        "all_users": set()      # для подсчёта общего числа участников
    }

def create_inline_keyboard(options, prefix, selected_values, next_step=None, prev_step=None):
    """
    Формирует клавиатуру из вариантов.
      options     - список вариантов (строк)
      prefix      - префикс для callback_data (например, "office")
      selected_values - множество выбранных вариантов (для много-выбора) 
                         или множество из одного элемента (для единственного выбора)
      next_step   - если указан, добавляет кнопку "➡️ Далее" с callback_data "next_{next_step}"
      prev_step   - если указан, добавляет кнопку "⬅️ Назад" с callback_data "prev_{prev_step}"
    """
    keyboard = []
    for i, option in enumerate(options):
        mark = f"✅ {option}" if option in selected_values else option
        keyboard.append([InlineKeyboardButton(mark, callback_data=f"{prefix}_{i}")])
    
    nav_buttons = []
    if prev_step:
        nav_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"prev_{prev_step}"))
    if next_step:
        nav_buttons.append(InlineKeyboardButton("➡️ Далее", callback_data=f"next_{next_step}"))
    if nav_buttons:
        keyboard.append(nav_buttons)
    return InlineKeyboardMarkup(keyboard)

# Варианты ответов
office_options = ["пер. Виленский, 14А", "Дегтярный пер., 11Б", "Киевская ул., 5 корп. 4"]
cuisine_options = ["🍲 Русская", "🍽️ Европейская", "🍜 Азиатская", "🍔 Фастфуд", "🏢 Бизнес-ланч", "🌱 Постное меню"]
restriction_options = [
    "🥗 Вегетарианские блюда",
    "🌱 Веганские блюда",
    "🥜 Без глютена / аллергия на орехи",
    "🍲 Халяль / Кошерное питание",
    "Нет ограничений"
]
budget_options = ["💵 До 500 руб.", "💵 До 1000 руб.", "💵 До 1500 руб.", "💵 Без разницы"]
walk_time_options = ["🚶 До 5 минут", "🚶 До 10 минут", "🚶 До 15 минут"]

# Команда /start — сбрасываем данные и начинаем опрос
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.bot_data["group_answers"] = init_group_data()
    await update.message.reply_text(
        "Привет! Все участники группы голосуют за предпочтения для обеда.\n\n1️⃣ Выберите ваш офис:",
        reply_markup=create_inline_keyboard(office_options, "office", set(), next_step="cuisine")
    )
    return OFFICE

# Обработчик callback-запросов (нажатия кнопок)
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user_id = query.from_user.id
    # Разбиваем callback_data по последнему символу '_'
    action, index = query.data.rsplit("_", 1)
    group_data = context.bot_data["group_answers"]
    group_data["all_users"].add(user_id)

    # Обработка возврата назад
    if action == "prev":
        if index == "office":
            # Переходим к офису
            user_office = group_data["office"].get(user_id)
            selected = {user_office} if user_office else set()
            await query.edit_message_text(
                "1️⃣ Выберите ваш офис:",
                reply_markup=create_inline_keyboard(office_options, "office", selected, next_step="cuisine")
            )
            return OFFICE
        elif index == "cuisine":
            selected = {c for c, users in group_data["wanted_cuisines"].items() if user_id in users}
            await query.edit_message_text(
                "2️⃣ Выберите желаемую кухню (можно несколько):",
                reply_markup=create_inline_keyboard(cuisine_options, "cuisine", selected, next_step="restrictions", prev_step="office")
            )
            return CUISINE
        elif index == "restrictions":
            selected = {r for r, users in group_data["food_restrictions"].items() if user_id in users}
            await query.edit_message_text(
                "3️⃣ Выберите ограничения по питанию (если есть):",
                reply_markup=create_inline_keyboard(restriction_options, "restrictions", selected, next_step="budget", prev_step="cuisine")
            )
            return RESTRICTIONS
        elif index == "budget":
            user_budget = group_data["price_limit"].get(user_id)
            selected = {user_budget} if user_budget else set()
            await query.edit_message_text(
                "4️⃣ Выберите желаемый средний чек:",
                reply_markup=create_inline_keyboard(budget_options, "budget", selected, next_step="walk_time", prev_step="restrictions")
            )
            return BUDGET
        elif index == "walk_time":
            selected = {t for t, users in group_data["walk_time"].items() if user_id in users}
            await query.edit_message_text(
                "5️⃣ Выберите время в пути (можно несколько):",
                reply_markup=create_inline_keyboard(walk_time_options, "walk_time", selected, next_step="finish", prev_step="budget")
            )
            return WALK_TIME

    # Обработка выбора вариантов
    elif action == "office":
        selected_office = office_options[int(index)]
        group_data["office"][user_id] = selected_office
        await query.edit_message_text(
            f"✅ Офис выбран: {selected_office}\n\n2️⃣ Выберите желаемую кухню (можно несколько):",
            reply_markup=create_inline_keyboard(cuisine_options, "cuisine", set(), next_step="restrictions", prev_step="office")
        )
        return CUISINE

    elif action == "cuisine":
        selected_cuisine = cuisine_options[int(index)]
        # Множественный выбор: добавляем/убираем пользователя в множестве
        if user_id in group_data["wanted_cuisines"][selected_cuisine]:
            group_data["wanted_cuisines"][selected_cuisine].remove(user_id)
        else:
            group_data["wanted_cuisines"][selected_cuisine].add(user_id)
        selected = {c for c, users in group_data["wanted_cuisines"].items() if user_id in users}
        await query.edit_message_reply_markup(
            reply_markup=create_inline_keyboard(cuisine_options, "cuisine", selected, next_step="restrictions", prev_step="office")
        )

    elif action == "next" and index == "restrictions":
        await query.edit_message_text(
            "3️⃣ Выберите ограничения по питанию (если есть):",
            reply_markup=create_inline_keyboard(restriction_options, "restrictions", set(), next_step="budget", prev_step="cuisine")
        )
        return RESTRICTIONS

    elif action == "restrictions":
        selected_restriction = restriction_options[int(index)]
        if user_id in group_data["food_restrictions"][selected_restriction]:
            group_data["food_restrictions"][selected_restriction].remove(user_id)
        else:
            group_data["food_restrictions"][selected_restriction].add(user_id)
        selected = {r for r, users in group_data["food_restrictions"].items() if user_id in users}
        await query.edit_message_reply_markup(
            reply_markup=create_inline_keyboard(restriction_options, "restrictions", selected, next_step="budget", prev_step="cuisine")
        )

    elif action == "next" and index == "budget":
        await query.edit_message_text(
            "4️⃣ Выберите желаемый средний чек:",
            reply_markup=create_inline_keyboard(budget_options, "budget", set(), next_step="walk_time", prev_step="restrictions")
        )
        return BUDGET

    elif action == "budget":
        selected_budget = budget_options[int(index)]
        group_data["price_limit"][user_id] = selected_budget
        await query.edit_message_text(
            f"✅ Средний чек выбран: {selected_budget}\n\n5️⃣ Выберите время в пути (можно несколько):",
            reply_markup=create_inline_keyboard(walk_time_options, "walk_time", set(), next_step="finish", prev_step="budget")
        )
        return WALK_TIME

    elif action == "walk_time":
        selected_walk_time = walk_time_options[int(index)]
        if user_id in group_data["walk_time"][selected_walk_time]:
            group_data["walk_time"][selected_walk_time].remove(user_id)
        else:
            group_data["walk_time"][selected_walk_time].add(user_id)
        selected = {t for t, users in group_data["walk_time"].items() if user_id in users}
        await query.edit_message_reply_markup(
            reply_markup=create_inline_keyboard(walk_time_options, "walk_time", selected, next_step="finish", prev_step="budget")
        )

    elif action == "next" and index == "finish":
        await query.edit_message_text("Готово! Введите /results, чтобы посмотреть итоговое распределение голосов.")
        return

    await query.answer()

# Команда /results — показать результаты опроса и итоговый словарь user_answers
async def results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    group_data = context.bot_data.get("group_answers", init_group_data())
    total_users = len(group_data["all_users"])
    if total_users == 0:
        await update.message.reply_text("Пока никто не проголосовал.")
        return

    def calculate_set_distribution(votes_dict):
        result = {}
        for option, users_set in votes_dict.items():
            count = len(users_set)
            result[option] = round(count / total_users, 2)
        return result

    def calculate_single_distribution(single_dict):
        counts = defaultdict(int)
        for ans in single_dict.values():
            counts[ans] += 1
        result = {}
        for option, count in counts.items():
            result[option] = round(count / total_users, 2)
        return result

    # Распределения для вопросов с множественным выбором
    wanted_cuisines_dist = calculate_set_distribution(group_data["wanted_cuisines"])
    food_restrictions_dist = calculate_set_distribution(group_data["food_restrictions"])
    walk_time_dist = calculate_set_distribution(group_data["walk_time"])
    # Распределения для вопросов с одним выбором
    office_dist = calculate_single_distribution(group_data["office"])
    budget_dist = calculate_single_distribution(group_data["price_limit"])

    # Определяем выбранный офис (наиболее популярных)
    chosen_office = max(office_dist, key=office_dist.get, default="Не выбрано")

    # Преобразуем бюджет и время в пути в числовые значения для итогового словаря
    numeric_budget_dist = {}
    for option_str, weight in budget_dist.items():
        if option_str in BUDGET_MAP:
            numeric_budget_dist[BUDGET_MAP[option_str]] = weight
        else:
            numeric_budget_dist[option_str] = weight

    numeric_walk_time_dist = {}
    for option_str, weight in walk_time_dist.items():
        if option_str in WALK_TIME_MAP:
            numeric_walk_time_dist[WALK_TIME_MAP[option_str]] = weight
        else:
            numeric_walk_time_dist[option_str] = weight

    # Можно убрать вариант "Нет ограничений", если он есть, или оставить
    cleaned_food_restrictions = {
        k: v for k, v in food_restrictions_dist.items() if k != "Нет ограничений" and v > 0
    }

    # Формируем итоговый словарь user_answers
    user_answers = {
        "wanted_cuisines": wanted_cuisines_dist,
        "price_limit": numeric_budget_dist,
        "food_restrictions": cleaned_food_restrictions,
        "walk_time": numeric_walk_time_dist
    }

    summary = (
        "📊 Итоговые предпочтения группы:\n\n"
        f"1️⃣ Офис (максимум голосов): {chosen_office}\n\n"
        "2️⃣ Желаемая кухня:\n" + "\n".join([f"{k}: {v}" for k, v in wanted_cuisines_dist.items()]) + "\n\n"
        "3️⃣ Ограничения по питанию:\n" + "\n".join([f"{k}: {v}" for k, v in food_restrictions_dist.items()]) + "\n\n"
        "4️⃣ Желаемый средний чек:\n" + "\n".join([f"{k}: {v}" for k, v in budget_dist.items()]) + "\n\n"
        "5️⃣ Время в пути:\n" + "\n".join([f"{k}: {v}" for k, v in walk_time_dist.items()])
    )

    final_message = (
        summary +
        "\n\n" +
        "user_answers = {\n"
        f'    "wanted_cuisines": {wanted_cuisines_dist},\n'
        f'    "price_limit": {numeric_budget_dist},\n'
        f'    "food_restrictions": {cleaned_food_restrictions},\n'
        f'    "walk_time": {numeric_walk_time_dist}\n'
        "}"
    )

    await update.message.reply_text(final_message)

# Создаем и запускаем бота
app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(handle_callback))
app.add_handler(CommandHandler("results", results))
app.run_polling()
