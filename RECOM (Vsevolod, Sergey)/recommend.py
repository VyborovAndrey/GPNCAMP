from flask import Flask, request, jsonify
import pandas as pd
import requests
from io import StringIO
# Модель весит слишком много, поэтому не вошла
# from processing_requests import FoodAnalyzer
app = Flask(__name__)

# Пока нет автоматизированного парсинга, нет большого смысла смысла от БД, поэтому просто грузим всю инфу в память.
# Если будет автопарсер, то уже можно использовать функцию ниже 
df_office_1 = pd.read_csv('office1.csv')
df_office_2 = pd.read_csv('office2.csv')
df_office_3 = pd.read_csv('office3.csv')

@app.route('/get_data', methods=['POST'])
def get_data():
    global df_office_1
    global df_office_2
    global df_office_3
    try:
        office_1 = requests.get(url='http://127.0.0.1:5000/get_office_1').text
        csv_file = StringIO(office_1)
        df_office_1 = pd.read_csv(csv_file)
        df_office_1 = df_office_1.rename(columns={'office_1_time': 'office_time'})
        office_2 = requests.get(url='http://127.0.0.1:5000/get_office_2').text
        csv_file = StringIO(office_2)
        df_office_2 = pd.read_csv(csv_file)
        df_office_2 = df_office_2.rename(columns={'office_2_time': 'office_time'})
        office_3 = requests.get(url='http://127.0.0.1:5000/get_office_3').text
        csv_file = StringIO(office_3)
        df_office_3 = pd.read_csv(csv_file)
        df_office_3 = df_office_3.rename(columns={'office_3_time': 'office_time'})
        return 200
    except:
        return 400


# analyzer = FoodAnalyzer(
#     model_path='models/request_processing/request_processing_model.pth',
#     cuisine_json_path='data/unique_cuisines.json',
#     dish_json_path='data/unique_dishes.json'
# )


# 🔹 Функция для учета пожеланий по блюдам (без штрафов за негативные блюда)
def adjust_score_by_dishes(row, structured_wishes):
    """
    Проверяет, есть ли позитивные блюда в заведении и корректирует баллы.
    """
    menu = row["Dishes"] if "Dishes" in row and pd.notna(row["Dishes"]) else ""
    menu_items = [dish.strip().lower() for dish in menu.split(";")]  # Разбиваем на список блюд

    positive_dish_bonus = 0

    # Проверяем, есть ли желаемые блюда в меню
    for dish in structured_wishes["positive_dishes"]:
        if dish.lower() in menu_items:
            positive_dish_bonus += 0.1  # +0.5 балла за каждое любимое блюдо

    return positive_dish_bonus

# 🔹 Функция для учета позитивных и негативных кухонь (из `Cuisine`) - доп. баллы по structured_wishes
def adjust_cuisine_score(row, structured_wishes):
    """
    Проверяет, есть ли позитивные или негативные кухни в заведении и корректирует баллы.
    """
    cuisine_list = row["Cuisine"].split(";") if pd.notna(row["Cuisine"]) else []  # Разбиваем строку на список

    positive_cuisine_bonus = 0
    negative_cuisine_penalty = 0

    for cuisine in structured_wishes["positive_cuisines"]:
        if cuisine in cuisine_list:
            positive_cuisine_bonus += 0.2  # Усиливаем баллы за любимые кухни

    for cuisine in structured_wishes["negative_cuisines"]:
        if cuisine in cuisine_list:
            negative_cuisine_penalty -= 0.4  # Штраф за нежелательные кухни

    return positive_cuisine_bonus + negative_cuisine_penalty

# 🔹 Функция для расчета итогового балла заведения (по опросу + дополнительно по structured_wishes)
def calculate_score(row, user_answers, structured_wishes):
    # 🔹 1. Баллы за кухню (по результатам опроса)
    cuisine_score = sum(
        user_answers["wanted_cuisines"].get(c, 0)*2 for c in user_answers["wanted_cuisines"] if row.get(c, False)
    )

    # 🔹 2. Баллы за ограничения по питанию (по результатам опроса)
    restrictions_score = sum(
        user_answers["food_restrictions"].get(r, 0) * 1.5 for r in user_answers["food_restrictions"] if row.get(r, False)
    )

    # 🔹 3. Баллы за цену (по результатам опроса)
    price = row["price_limit"]
    price_score = sum(
        user_answers["price_limit"].get(limit, 0) for limit in user_answers["price_limit"] if pd.notna(price) and price <= int(limit)
    )

    # 🔹 4. Баллы за время в пути (по результатам опроса)
    walk_time = row["office_time"]
    walk_score = sum(
        user_answers["walk_time"].get(limit, 0) for limit in user_answers["walk_time"] if pd.notna(walk_time) and walk_time <= int(limit)
    )

    # 🔹 5. Баллы за рейтинг и отзывы (по результатам опроса)
    rating = row["reviews_general_rating"]
    reviews = row["reviews_general_review_count"]
    rating_score = (1 if rating > 4.5 else 0) + (1 if reviews > 200 else 0)

    # # 🔹 6. ДОПОЛНИТЕЛЬНЫЕ Баллы за structured_wishes (кухни и блюда)
    # structured_cuisine_score = adjust_cuisine_score(row, structured_wishes)
    # structured_dish_score = adjust_score_by_dishes(row, structured_wishes)

    # 🔹 Общая сумма баллов
    # total_score = (cuisine_score + restrictions_score + price_score +
    #                walk_score + rating_score + structured_cuisine_score + structured_dish_score)
    total_score = (cuisine_score + restrictions_score + price_score +
                   walk_score + rating_score)

    return total_score

# def user_wishes(user_wish):
#     result = analyzer.analyze(user_wish)
#     output_for_recommendation_system = {
#     'positive_cuisines': FoodAnalyzer.filter_words(result['cuisine_positive']),
#     'positive_dishes': FoodAnalyzer.filter_words(result['dish_positive']),
#     'negative_cuisines': FoodAnalyzer.filter_words(result['cuisine_negative']),
#     'negative_dishes': FoodAnalyzer.filter_words(result['dish_negative'])
#     }
#     return output_for_recommendation_system

@app.route('/recommendations', methods=['POST'])
def get_recommendation():
    # Получаем входные данные от пользователя
    user_answers = request.json
    if user_answers['office'] == "пер. Виленский, 14А":
        df = df_office_1
    elif user_answers['office'] == "Дегтярный пер., 11Б":
        df = df_office_2
    elif user_answers['office'] == "Киевская ул., 5 корп. 4":
        df = df_office_3
    else:
        return '400, office with this name not found'
    # wished = user_wishes(user_answers['positive'])
    # not_wished = user_wishes(user_answers['negative'])
    # structured_wishes = {
    # key: list(set(wished.get(key, []) + not_wished.get(key, [])))
    # for key in wished.keys() | not_wished.keys()
    # }
    # 🔹 Добавляем колонку с баллами
    df["total_score"] = df.apply(lambda row: calculate_score(row, user_answers, structured_wishes), axis=1)

    # 🔹 Сортируем по баллам, затем по рейтингу, затем по количеству отзывов
    df_sorted = df.sort_values(by=["total_score", "reviews_general_rating", "reviews_general_review_count"], 
                            ascending=[False, False, False])

    # 🔹 Выбираем топ-3 ресторана
    top_3_places = df_sorted.head(3)
    # Преобразуем результат в JSON
    result = list([list(top_3_places['name'].to_list()), list(top_3_places['id'].to_list())])
    return result

if __name__ == '__main__':
    app.run(debug=True, port=5005)