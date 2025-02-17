import json
import random
import re

with open('data/unique_dishes_all.json', 'r', encoding='utf-8') as file:
    dishes = json.load(file)

with open('data/unique_cuisines_all.json', 'r', encoding='utf-8') as file:
    cuisines = json.load(file)

def flatten_dict(lst):
    """
    Рекурсивно преобразует вложенные списки в плоский список.

    Args:
        lst (list): Входной список, возможно, содержащий вложенные списки.

    Returns:
        list: Плоский список без вложенности.
    """
    flat_list = []
    for item in lst:
        if isinstance(item, list):
            flat_list.extend(flatten_dict(item))
        else:
            flat_list.append(item)
    return flat_list


def generate_queries_and_labels(patterns, counts, cuisines, dishes):
    """
    Генерирует запросы и соответствующие метки на основе шаблонов.

    Args:
        patterns (list): Список шаблонов для генерации запросов.
        counts (int): Количество повторений для каждого шаблона.
        cuisines (list): Список кухонь для подстановки в шаблоны.
        dishes (list): Список блюд для подстановки в шаблоны.

    Returns:
        tuple: Кортеж из двух списков: queries (запросы) и labels (метки).
    """
    queries = []
    labels = []

    for _ in range(counts):
        for pattern in patterns:
            query = pattern
            words = query.split()
            label_list = ["O"] * len(words)
            positions = []

            for idx, word in enumerate(words):
                if '{' in word and '}' in word:
                    positions.append(idx)

            for pos in positions:
                part = re.findall(r'\{(.*?)\}', words[pos])[0]
                label_type, positive_or_negative = part.split("_")

                if label_type == "cuisine":
                    cuisine = random.choice(cuisines)
                    query = query.replace(f"{{{part}}}", cuisine, 1)
                    tag_name = "B-кухня" if positive_or_negative == "positive" else "B-кухня-негатив"
                    labels_temp = [tag_name] * len(cuisine.split())
                    if len(labels_temp) > 1:
                        for i in range(1, len(labels_temp)):
                            labels_temp[i] = tag_name.replace("B", "I")
                elif label_type == "dish":
                    dish = random.choice(dishes)
                    query = query.replace(f"{{{part}}}", dish, 1)
                    tag_name = "B-блюдо" if positive_or_negative == "positive" else "B-блюдо-негатив"
                    labels_temp = [tag_name] * len(dish.split())
                    if len(labels_temp) > 1:
                        for i in range(1, len(labels_temp)):
                            labels_temp[i] = tag_name.replace("B", "I")

                label_list[pos] = labels_temp

            label_list = flatten_dict(label_list)
            queries.append([query.replace(" .", ".").replace(" ,", ",")])
            labels.append(label_list)

    return queries, labels

# Загрузка существующих данных
with open('data/data_request_processing.json', 'r', encoding='utf-8') as file:
    json_data = json.load(file)

queries1 = json_data["texts"]
labels1 = json_data["labels"]


# Загрузка шаблонов
with open('data/data_request_processing_patterns.json', 'r', encoding='utf-8') as file:
    patterns = json.load(file)

# Генерация новых данных
counts = 2
queries, labels = generate_queries_and_labels(patterns, counts, cuisines, dishes)
queries.extend(queries1)
labels.extend(labels1)

result = {
    "texts": queries,
    "labels": labels
}

with open("data/data_request_processing_full.json", "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=4)