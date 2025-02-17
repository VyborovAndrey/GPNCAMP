import os
import logging
import json
import re
from dotenv import load_dotenv
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes
)
from collections import defaultdict
from typing import Set, Dict, Any

# Включаем логирование
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

load_dotenv()
TOKEN = os.getenv("TOKEN")

# Имя бота (без @)
BOT_USERNAME = "LunchBuddy1Bot"

# Функция для удаления эмодзи из строки
def remove_emojis(text: str) -> str:
    emoji_pattern = re.compile(
        "["
        u"\U0001F600-\U0001F64F"  # эмодзи лица
        u"\U0001F300-\U0001F5FF"  # символы и пиктограммы
        u"\U0001F680-\U0001F6FF"  # транспорт и карты
        u"\U0001F1E0-\U0001F1FF"  # флаги
        u"\U0001F900-\U0001F9FF"  # дополнительные эмодзи
        "]+", 
        flags=re.UNICODE
    )
    return emoji_pattern.sub("", text).strip()

# Функция для рекурсивной очистки ключей словаря
def clean_dict_keys(d: dict) -> dict:
    cleaned = {}
    for key, value in d.items():
        new_key = remove_emojis(key) if isinstance(key, str) else key
        if isinstance(value, dict):
            cleaned[new_key] = clean_dict_keys(value)
        else:
            cleaned[new_key] = value
    return cleaned

##########################
#  ЧАСТЬ 1. ОПРОС (POLL)
##########################

# Функция инициализации хранилища данных для опроса (для конкретной группы)
def init_group_data() -> Dict[str, Any]:
    return {
        "office": {},           # {user_id: выбранный офис}
        "wanted_cuisines": defaultdict(set),  # {вариант: {user_id, ...}}
        "food_restrictions": defaultdict(set),# {вариант: {user_id, ...}}
        "price_limit": {},      # {user_id: выбранный чек}
        "walk_time": {},        # {user_id: выбранное время}
        "all_users": set()      # все участники опроса
    }

# Карты для преобразования бюджетов и времени ходьбы в числовые значения
BUDGET_MAP = {
    "💵 До 500 руб.": 500,
    "💵 До 1000 руб.": 1000,
    "💵 До 1500 руб.": 1500,
    "💵 Без разницы": 999999
}
WALK_TIME_MAP = {
    "🚶 До 5 минут": 5,
    "🚶 До 10 минут": 10,
    "🚶 До 15 минут": 15
}

# Варианты ответов для опроса
office_options = ["пер. Виленский, 14А", "Дегтярный пер., 11Б", "Киевская ул., 5 корп. 4"]
cuisine_options = ["🍲 Русская", "🍽️ Европейская", "🍜 Азиатская", "🍔 Фастфуд", "🏢 Бизнес-ланч"]
restriction_options = [
    "🥗 Вегетарианские блюда",
    "🌱 Постное меню",
    "Нет ограничений"
]
budget_options = ["💵 До 500 руб.", "💵 До 1000 руб.", "💵 До 1500 руб.", "💵 Без разницы"]
walk_time_options = ["🚶 До 5 минут", "🚶 До 10 минут", "🚶 До 15 минут"]

# Конфигурация этапов опроса
state_settings = {
    "office": {
        "text": "1️⃣ Выберите ваш офис:",
        "options": office_options,
        "prefix": "office",
        "next_state": "cuisine",
        "type": "single"  # выбор только один; переход осуществляется кнопкой "➡️ Далее"
    },
    "cuisine": {
        "text": "2️⃣ Выберите желаемую кухню (можно несколько):",
        "options": cuisine_options,
        "prefix": "cuisine",
        "next_state": "restrictions",
        "prev_state": "office",
        "type": "multi"
    },
    "restrictions": {
        "text": "3️⃣ Выберите ограничения по питанию (если есть):",
        "options": restriction_options,
        "prefix": "restrictions",
        "next_state": "budget",
        "prev_state": "cuisine",
        "type": "multi"
    },
    "budget": {
        "text": "4️⃣ Выберите желаемый средний чек:",
        "options": budget_options,
        "prefix": "budget",
        "next_state": "walk_time",
        "prev_state": "restrictions",
        "type": "single"  # одиночный выбор, без автоперехода
    },
    "walk_time": {
        "text": "5️⃣ Выберите время в пути:",
        "options": walk_time_options,
        "prefix": "walkTime",
        "next_state": "finish",
        "prev_state": "budget",
        "type": "single"  # теперь выбор только один
    }
}

def create_inline_keyboard(options, prefix, selected_values: Set[str], next_step=None, prev_step=None) -> InlineKeyboardMarkup:
    """
    Строит инлайн-клавиатуру с кнопками вариантов и навигационными кнопками.
    """
    keyboard = []
    for i, option in enumerate(options):
        display_text = f"✅ {option}" if option in selected_values else option
        keyboard.append([InlineKeyboardButton(display_text, callback_data=f"{prefix}_{i}")])
    
    nav_buttons = []
    if prev_step:
        nav_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"prev_{prev_step}"))
    if next_step:
        nav_buttons.append(InlineKeyboardButton("➡️ Далее", callback_data=f"next_{next_step}"))
    if nav_buttons:
        keyboard.append(nav_buttons)
    return InlineKeyboardMarkup(keyboard)

def get_selected_values(state: str, user_id: int, group_data: dict) -> Set[str]:
    """
    Возвращает множество выбранных значений для конкретного этапа и пользователя.
    """
    if state == "office":
        value = group_data["office"].get(user_id)
        return {value} if value else set()
    elif state == "budget":
        value = group_data["price_limit"].get(user_id)
        return {value} if value else set()
    elif state == "walk_time":
        value = group_data["walk_time"].get(user_id)
        return {value} if value else set()
    elif state == "cuisine":
        return {option for option, users in group_data["wanted_cuisines"].items() if user_id in users}
    elif state == "restrictions":
        return {option for option, users in group_data["food_restrictions"].items() if user_id in users}
    return set()

async def show_state(query, state: str, user_id: int, group_data: dict):
    """
    Отображает сообщение и клавиатуру для выбранного этапа опроса.
    """
    if state == "finish":
        await query.edit_message_text("Опрос завершён!\n\nСпасибо за участие.")
        return

    settings = state_settings[state]
    text = settings["text"]
    options = settings["options"]
    prefix = settings["prefix"]
    next_state = settings.get("next_state")
    prev_state = settings.get("prev_state")
    selected = get_selected_values(state, user_id, group_data)
    reply_markup = create_inline_keyboard(options, prefix, selected, next_step=next_state, prev_step=prev_state)
    await query.edit_message_text(text, reply_markup=reply_markup)

def reset_user_answers(user_id: int, group_data: dict):
    """
    Сбрасывает ответы пользователя (при повторном прохождении опроса).
    """
    group_data["office"].pop(user_id, None)
    group_data["price_limit"].pop(user_id, None)
    group_data["walk_time"].pop(user_id, None)

    for field in ["wanted_cuisines", "food_restrictions"]:
        for option in list(group_data[field].keys()):
            group_data[field][option].discard(user_id)
            if len(group_data[field][option]) == 0:
                del group_data[field][option]

    group_data["all_users"].add(user_id)

async def poll_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Запуск опроса в личном чате.
    Теперь данные опроса сохраняются для конкретной группы, идентификатор которой хранится в context.user_data["group_id"].
    """
    if update.effective_chat.type != "private":
        await update.effective_message.reply_text("Пожалуйста, напишите мне в личном чате для прохождения опроса.")
        return

    # Получаем идентификатор группы, для которой запускается опрос
    group_id = context.user_data.get("group_id")
    if not group_id:
        logging.error("Poll start: group_id не найден в user_data")
        await update.message.reply_text("Ошибка: не удалось определить группу.")
        return

    if "group_answers" not in context.bot_data:
        context.bot_data["group_answers"] = {}
    if group_id not in context.bot_data["group_answers"]:
        context.bot_data["group_answers"][group_id] = init_group_data()
    group_data = context.bot_data["group_answers"][group_id]

    user_id = update.effective_user.id
    reset_user_answers(user_id, group_data)

    initial_state = "office"
    settings = state_settings[initial_state]
    text = settings["text"]
    reply_markup = create_inline_keyboard(settings["options"], settings["prefix"], set(), next_step=settings["next_state"])

    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup)
    elif update.callback_query and update.callback_query.message:
        await update.callback_query.message.reply_text(text, reply_markup=reply_markup)
    else:
        logging.error("Не найден объект сообщения для отправки опроса.")

async def handle_selection(update_query, state: str, option_index: int, user_id: int, group_data: dict):
    """
    Обрабатывает выбор варианта для этапа опроса.
    """
    settings = state_settings[state]
    option = settings["options"][option_index]

    if settings["type"] == "single":
        if state == "office":
            group_data["office"][user_id] = option
        elif state == "budget":
            group_data["price_limit"][user_id] = option
        elif state == "walk_time":
            group_data["walk_time"][user_id] = option

        selected = get_selected_values(state, user_id, group_data)
        await update_query.edit_message_reply_markup(
            create_inline_keyboard(settings["options"], settings["prefix"], selected,
                                     next_step=settings.get("next_state"),
                                     prev_step=settings.get("prev_state"))
        )
    else:
        if state == "restrictions":
            if option == "Нет ограничений":
                for opt in list(group_data["food_restrictions"].keys()):
                    if user_id in group_data["food_restrictions"][opt]:
                        group_data["food_restrictions"][opt].remove(user_id)
                        if len(group_data["food_restrictions"][opt]) == 0:
                            del group_data["food_restrictions"][opt]
                if "Нет ограничений" not in group_data["food_restrictions"]:
                    group_data["food_restrictions"]["Нет ограничений"] = set()
                group_data["food_restrictions"]["Нет ограничений"].add(user_id)
            else:
                if "Нет ограничений" in group_data["food_restrictions"]:
                    group_data["food_restrictions"]["Нет ограничений"].discard(user_id)
                    if len(group_data["food_restrictions"]["Нет ограничений"]) == 0:
                        del group_data["food_restrictions"]["Нет ограничений"]

                if option not in group_data["food_restrictions"]:
                    group_data["food_restrictions"][option] = set()

                if user_id in group_data["food_restrictions"][option]:
                    group_data["food_restrictions"][option].remove(user_id)
                    if len(group_data["food_restrictions"][option]) == 0:
                        del group_data["food_restrictions"][option]
                else:
                    group_data["food_restrictions"][option].add(user_id)

        elif state == "cuisine":
            if option not in group_data["wanted_cuisines"]:
                group_data["wanted_cuisines"][option] = set()

            if user_id in group_data["wanted_cuisines"][option]:
                group_data["wanted_cuisines"][option].remove(user_id)
                if len(group_data["wanted_cuisines"][option]) == 0:
                    del group_data["wanted_cuisines"][option]
            else:
                group_data["wanted_cuisines"][option].add(user_id)

        selected = get_selected_values(state, user_id, group_data)
        await update_query.edit_message_reply_markup(
            create_inline_keyboard(settings["options"], settings["prefix"], selected,
                                     next_step=settings.get("next_state"),
                                     prev_step=settings.get("prev_state"))
        )

async def handle_next(update_query, next_state: str, user_id: int, group_data: dict):
    await show_state(update_query, next_state, user_id, group_data)

async def handle_prev(update_query, prev_state: str, user_id: int, group_data: dict):
    await show_state(update_query, prev_state, user_id, group_data)

async def poll_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик callback-запросов для опроса.
    """
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    # Получаем group_id из user_data
    group_id = context.user_data.get("group_id")
    if not group_id:
        logging.error("Poll callback: group_id не найден в user_data")
        await query.answer("Ошибка: группа не определена.")
        return

    group_data = context.bot_data.get("group_answers", {}).get(group_id)
    if not group_data:
        logging.error("Poll callback: данные опроса для группы %s не найдены", group_id)
        await query.answer("Ошибка: данные опроса не найдены.")
        return

    group_data["all_users"].add(user_id)

    data = query.data
    if data.startswith("next_"):
        next_state = data.split("_", 1)[1]
        await handle_next(query, next_state, user_id, group_data)
    elif data.startswith("prev_"):
        prev_state = data.split("_", 1)[1]
        await handle_prev(query, prev_state, user_id, group_data)
    else:
        try:
            prefix, index_str = data.split("_", 1)
            option_index = int(index_str)
        except (ValueError, IndexError):
            await query.answer("Некорректные данные!")
            return

        state = None
        for key, stg in state_settings.items():
            if stg["prefix"] == prefix:
                state = key
                break
        if not state:
            await query.answer("Неизвестный этап!")
            return

        await handle_selection(query, state, option_index, user_id, group_data)

def calculate_set_distribution(votes_dict, total_users):
    """
    Возвращает словарь {вариант: доля} для вариантов с хотя бы одним голосом.
    """
    result = {}
    for option, users_set in votes_dict.items():
        if len(users_set) > 0:
            result[option] = round(len(users_set) / total_users, 2)
    return result

def calculate_single_distribution(single_dict, total_users):
    from collections import defaultdict
    counts = defaultdict(int)
    for ans in single_dict.values():
        counts[ans] += 1
    result = {}
    for option, count in counts.items():
        result[option] = round(count / total_users, 2)
    return result

def send_to_recommendation_module(user_answers: dict) -> str:
    """
    Заглушка для отправки данных в модуль рекомендаций.
    Здесь в будущем будет реализована логика получения рекомендаций на основе user_answers.
    Пока что функция просто логирует полученные данные и возвращает тестовый ответ.
    """
    import logging
    logging.info("Отправка данных в модуль рекомендаций: %s", user_answers)
    # Здесь можно сделать вызов реальной функции из модуля рекомендаций, например:
    # return recommendation_module.get_recommendations(user_answers)
    return "Заглушка: рекомендации пока не реализованы."


def get_user_answers(group_data: dict) -> dict:
    """
    Формирует итоговый словарь user_answers на основе данных опроса.
    """
    total_users = len(group_data["all_users"])
    if total_users == 0:
        return {}

    # Распределение голосов для вариантов с множественным выбором
    wanted_cuisines_dist = calculate_set_distribution(group_data["wanted_cuisines"], total_users)
    food_restrictions_dist = calculate_set_distribution(group_data["food_restrictions"], total_users)

    # Распределение голосов для вариантов с одиночным выбором
    walk_time_dist = calculate_single_distribution(group_data["walk_time"], total_users)
    office_dist = calculate_single_distribution(group_data["office"], total_users)
    budget_dist = calculate_single_distribution(group_data["price_limit"], total_users)

    # Определяем офис с наибольшим числом голосов
    chosen_office = max(office_dist, key=office_dist.get, default="Не выбрано")

    # Преобразуем текстовые варианты для времени и бюджета в числовые значения
    numeric_walk_time_dist = {WALK_TIME_MAP.get(option, option): val for option, val in walk_time_dist.items()}
    numeric_budget_dist = {BUDGET_MAP.get(option, option): val for option, val in budget_dist.items()}

    user_answers = {
        "office": office_dist,           # распределение голосов по офисам
        # "chosen_office": chosen_office,    # наиболее выбранный офис
        "wanted_cuisines": wanted_cuisines_dist,
        "price_limit": numeric_budget_dist,
        "food_restrictions": food_restrictions_dist,
        "walk_time": numeric_walk_time_dist
    }

    return clean_dict_keys(user_answers)


async def poll_results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Команда /pollresults – выводит результаты опроса для конкретной группы.
    Кроме того, итоговый словарь user_answers отправляется в модуль рекомендаций.
    Доступна только в группе.
    """
    if update.effective_chat.type == "private":
        await update.message.reply_text("Команда /pollresults доступна только в группе.")
        return

    group_id = update.effective_chat.id
    group_data = context.bot_data.get("group_answers", {}).get(group_id)
    if not group_data:
        await update.message.reply_text("Пока никто не проголосовал.")
        return

    # Формируем итоговый словарь user_answers
    user_answers = get_user_answers(group_data)
    
    # Отправляем данные в модуль рекомендаций (заглушка)
    recommendations = send_to_recommendation_module(user_answers)

    # Формируем текст для вывода результатов опроса
    summary = (
        "📊 Итоговые предпочтения:\n\n"
        f"1️⃣ Офис (наиболее голосов): {user_answers.get('chosen_office', 'Не выбрано')}\n\n"
        "2️⃣ Желаемая кухня:\n" + "\n".join([f"{k}: {v}" for k, v in user_answers.get("wanted_cuisines", {}).items()]) + "\n\n"
        "3️⃣ Ограничения по питанию:\n" + "\n".join([f"{k}: {v}" for k, v in user_answers.get("food_restrictions", {}).items()]) + "\n\n"
        "4️⃣ Желаемый средний чек:\n" + "\n".join([f"{k}: {v}" for k, v in user_answers.get("price_limit", {}).items()]) + "\n\n"
        "5️⃣ Время в пути:\n" + "\n".join([f"{k}: {v}" for k, v in user_answers.get("walk_time", {}).items()]) + "\n\n"
        "user_answers = " + json.dumps(user_answers, ensure_ascii=False) + "\n\n"
        f"Рекомендации: {recommendations}"
    )

    await update.message.reply_text(summary)


##########################
#  ЧАСТЬ 2. ПРИГЛАШЕНИЕ
##########################

def get_group_members(chat_id, bot_data):
    if "group_members" not in bot_data:
        bot_data["group_members"] = {}
    return bot_data["group_members"].setdefault(chat_id, {})

def get_invitation(chat_id, bot_data):
    if "invitations" not in bot_data:
        bot_data["invitations"] = {}
    return bot_data["invitations"].get(chat_id)

def set_invitation(chat_id, invitation, bot_data):
    if "invitations" not in bot_data:
        bot_data["invitations"] = {}
    bot_data["invitations"][chat_id] = invitation

def create_invitation_keyboard(chat_id, bot_data):
    """
    Строит клавиатуру для выбора участников приглашения.
    """
    members = get_group_members(chat_id, bot_data)
    invitation = get_invitation(chat_id, bot_data)
    keyboard = []
    for user_id, name in members.items():
        text = f"✅ {name}" if user_id in invitation["invitees"] else name
        keyboard.append([InlineKeyboardButton(text, callback_data=f"invite_{user_id}")])
    keyboard.append([InlineKeyboardButton("➡️ Далее", callback_data="invite_next")])
    return InlineKeyboardMarkup(keyboard)

def create_response_keyboard(group_id):
    """
    Строит клавиатуру для ответа на приглашение в ЛС.
    """
    keyboard = [
        [
            InlineKeyboardButton("✅ Принять", callback_data=f"response_{group_id}_accept"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"response_{group_id}_decline")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

async def join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Команда /join – участники группы регистрируются для приглашений.
    """
    chat = update.effective_chat
    if chat.type not in ["group", "supergroup"]:
        await update.message.reply_text("Эту команду можно использовать только в группе.")
        return
    user = update.effective_user
    members = get_group_members(chat.id, context.bot_data)
    members[user.id] = user.full_name
    await update.message.reply_text(f"{user.full_name}, вы зарегистрированы для приглашений в этой группе.")

async def start_invitation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Команда /start в группе – организатор создаёт приглашение.
    """
    chat = update.effective_chat
    if chat.type not in ["group", "supergroup"]:
        await update.message.reply_text("Команда для приглашения доступна только в группе.")
        return
    organizer = update.effective_user
    members = get_group_members(chat.id, context.bot_data)
    members[organizer.id] = organizer.full_name

    invitation = {
        "organizer_id": organizer.id,
        "organizer_username": organizer.full_name,
        "invitees": set(),
        "responses": {}  # статусы: "pending", "accepted", "declined"
    }
    set_invitation(chat.id, invitation, context.bot_data)

    reply_markup = create_invitation_keyboard(chat.id, context.bot_data)
    await update.message.reply_text(
        f"{organizer.full_name}, выберите участников, которых хотите пригласить на обед:",
        reply_markup=reply_markup
    )

async def invitation_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик callback-запросов для выбора участников приглашения.
    """
    query = update.callback_query
    await query.answer()
    chat = update.effective_chat  # группа
    data = query.data
    invitation = get_invitation(chat.id, context.bot_data)
    if not invitation:
        await query.answer("Приглашение не найдено.")
        return

    if data.startswith("invite_") and data != "invite_next":
        try:
            user_id = int(data.split("_")[1])
        except ValueError:
            await query.answer("Некорректные данные.")
            return
        if user_id in invitation["invitees"]:
            invitation["invitees"].remove(user_id)
        else:
            invitation["invitees"].add(user_id)
        reply_markup = create_invitation_keyboard(chat.id, context.bot_data)
        await query.edit_message_reply_markup(reply_markup=reply_markup)
    elif data == "invite_next":
        logging.info(f"invite_next pressed; invitees: {invitation['invitees']}")
        if not invitation["invitees"]:
            await query.answer("Вы не выбрали ни одного участника.", show_alert=True)
            return
        for uid in invitation["invitees"]:
            invitation["responses"][uid] = "pending"
        await query.edit_message_text("Приглашения отправлены выбранным участникам.")
        # Отправка личных сообщений приглашенным
        for uid in invitation["invitees"]:
            logging.info(f"Отправляем приглашение пользователю {uid}")
            try:
                await context.bot.send_message(
                    chat_id=uid,
                    text=f"Вам пришло приглашение на сегодняшний обед. Примите его?",
                    reply_markup=create_response_keyboard(chat.id)
                )
            except Exception as e:
                logging.error(f"Ошибка отправки сообщения пользователю {uid}: {e}")
    else:
        await query.answer("Неизвестное действие.")

async def response_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик callback-запросов для ответа на приглашение в ЛС.
    """
    query = update.callback_query
    await query.answer()
    data = query.data
    parts = data.split("_")
    if len(parts) != 3:
        await query.answer("Некорректные данные.")
        return
    _, group_id_str, decision = parts
    try:
        group_id = int(group_id_str)
    except ValueError:
        await query.answer("Некорректный идентификатор группы.")
        return
    invitation = get_invitation(group_id, context.bot_data)
    if not invitation:
        await query.edit_message_text("Приглашение не найдено или истекло.")
        return
    user_id = query.from_user.id
    if user_id not in invitation["responses"]:
        await query.edit_message_text("Вы не были приглашены.")
        return
    if decision == "accept":
        invitation["responses"][user_id] = "accepted"
        # Сохраняем флаг и идентификатор группы в user_data, чтобы опрос знал, к какой группе относится
        context.user_data["invitation_accepted"] = True
        context.user_data["group_id"] = group_id
        await query.edit_message_text("Вы приняли приглашение на обед!\nЗапускаем опрос...")
        await poll_start(update, context)
    elif decision == "decline":
        invitation["responses"][user_id] = "declined"
        await query.edit_message_text("Вы отклонили приглашение.")
    else:
        await query.answer("Неизвестное решение.")

async def invitation_results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Команда /invite_results – выводит результаты приглашения в группе.
    """
    chat = update.effective_chat
    if chat.type not in ["group", "supergroup"]:
        await update.message.reply_text("Эту команду можно использовать только в группе.")
        return
    invitation = get_invitation(chat.id, context.bot_data)
    if not invitation:
        await update.message.reply_text("Нет активных приглашений в этой группе.")
        return
    members = get_group_members(chat.id, context.bot_data)
    results_text = f"Приглашение от {invitation['organizer_username']}:\n\n"
    for uid in invitation["invitees"]:
        name = members.get(uid, "Неизвестно")
        status = invitation["responses"].get(uid, "pending")
        results_text += f"{name}: {status}\n"
    await update.message.reply_text(results_text)

##########################
#  НОВАЯ КОМАНДА: ПРИВЕТСТВИЕ (/hello)
##########################

async def hello_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Команда /hello – приветствие бота.
    """
    if update.effective_chat.type == "private":
        await update.message.reply_text(
            "Привет! Я ваш LunchBuddy.\n\n"
            "Чтобы я добавил вас в список приглашений, убедитесь, что вы уже зарегистрированы в группе, "
            "где я добавлен. Для регистрации в группе используйте команду /join."
        )
    else:
        await update.message.reply_text(
            "Пожалуйста, напишите мне в личном чате команду Старт "
            "для начала диалога и возможности отправки вам приглашений от коллег"
        )

##########################
#  ЕДИНЫЙ ВХОД /START
##########################

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Если команда /start вызвана в личном чате:
      - если приглашение не принято – приветствие;
      - если принято – запускается опрос.
    Если команда вызвана в группе – инициируется приглашение.
    """
    if update.effective_chat.type == "private":
        if not context.user_data.get("invitation_accepted", False):
            await hello_command(update, context)
            return
        await poll_start(update, context)
    else:
        await start_invitation(update, context)

##########################
#  РЕГИСТРАЦИЯ ОБРАБОТЧИКОВ
##########################

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("hello", hello_command))
app.add_handler(CallbackQueryHandler(poll_callback, pattern=r"^(office_|cuisine_|restrictions_|budget_|walkTime_|next_|prev_)"))
app.add_handler(CommandHandler("pollresults", poll_results))
app.add_handler(CommandHandler("join", join))
app.add_handler(CallbackQueryHandler(invitation_callback, pattern=r"^(invite_|invite_next)"))
app.add_handler(CallbackQueryHandler(response_callback, pattern=r"^response_"))
app.add_handler(CommandHandler("invite_results", invitation_results))

app.run_polling()
