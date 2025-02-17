import argparse
import json
import re
import torch
from fuzzywuzzy import fuzz
from transformers import BertForTokenClassification, BertTokenizerFast, logging as transformers_logging
transformers_logging.set_verbosity_error()


class FoodAnalyzer:
    def __init__(self, model_path, cuisine_json_path, dish_json_path):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = BertForTokenClassification.from_pretrained(
            'DeepPavlov/rubert-base-cased', 
            num_labels=10
        ).to(self.device)
        self.model.load_state_dict(torch.load(model_path, map_location=self.device, weights_only=True), strict=False)

        self.model.eval()
        
        self.tokenizer = BertTokenizerFast.from_pretrained('DeepPavlov/rubert-base-cased')
        
        with open(cuisine_json_path, 'r', encoding='utf-8') as f:
            self.unique_cuisines = set(json.load(f))
            
        with open(dish_json_path, 'r', encoding='utf-8') as f:
            self.unique_dishes = set(json.load(f))
            
        self.label_map = {
            "O": 0,
            "B-кухня": 1, # начало названия какой-то кухни, которая нравится
            "I-кухня": 2, # продолжение названия какой-то кухни, которая нравится
            "B-блюдо": 3, # начало названия какого-то блюда, которое нравится
            "I-блюдо": 4, #  продолжение названия какого-то блюда, которое нравится
            "B-кухня-негатив": 5, # начало названия какой-то кухни, которая не нравится
            "I-кухня-негатив": 6, # продолжение названия какой-то кухни, которая не нравится
            "B-блюдо-негатив": 7, # начало названия какого-то блюда, которое не нравится
            "I-блюдо-негатив": 8 #  продолжение названия какого-то блюда, которое не нравится
        }
        self.label_map_reverse = {v: k for k, v in self.label_map.items()}

    def analyze(self, text):
        inputs = self.tokenizer(
            text, 
            return_tensors="pt", 
            truncation=True, 
            padding=True
        ).to(self.device)
        
        with torch.no_grad():
            outputs = self.model(**inputs)
            logits = outputs.logits
            
        predicted_labels = torch.argmax(logits, dim=-1).squeeze().tolist()
        tokens = self.tokenizer.convert_ids_to_tokens(inputs["input_ids"].squeeze().tolist())
        
        word_labels = self._align_tokens_with_words(tokens, predicted_labels)
        entities = self._extract_entities(word_labels)

        for word, label in word_labels:
            print(f"{word} - {label}")
        
        return {
            "cuisine_positive": self._process_entities(entities["cuisine_positive"], "cuisine"),
            "cuisine_negative": self._process_entities(entities["cuisine_negative"], "cuisine"),
            "dish_positive": self._process_entities(entities["dish_positive"], "dish"),
            "dish_negative": self._process_entities(entities["dish_negative"], "dish"),
        }
        
    def _align_tokens_with_words(self, tokens, predicted_labels):
        word_labels = []
        current_word = None
        current_label = None
        
        for token, label in zip(tokens, predicted_labels):
            if token in ["[CLS]", "[SEP]", "[PAD]"]:
                continue
                
            if token.startswith("##"):
                current_word += token[2:]
            else:
                if current_word is not None:
                    word_labels.append((current_word, self.label_map_reverse[current_label]))
                current_word = token
                current_label = label
                
        if current_word is not None:
            word_labels.append((current_word, self.label_map_reverse[current_label]))
            
        return word_labels
    
    def _extract_entities(self, word_labels):
        entities = {
            "cuisine_positive": [],
            "cuisine_negative": [],
            "dish_positive": [],
            "dish_negative": [],
        }
        
        current_entities = {
            "cuisine": {"positive": [], "negative": []},
            "dish": {"positive": [], "negative": []}
        }
        
        for word, label in word_labels:
            entity_type = None
            polarity = None
            
            if "кухня" in label:
                entity_type = "cuisine"
                polarity = "positive" if "негатив" not in label else "negative"
            elif "блюдо" in label:
                entity_type = "dish"
                polarity = "positive" if "негатив" not in label else "negative"
                
            if entity_type and polarity:
                if label.startswith("B-"):
                    if current_entities[entity_type][polarity]:
                        entities[f"{entity_type}_{polarity}"].append(
                            " ".join(current_entities[entity_type][polarity]))
                        current_entities[entity_type][polarity] = []
                    current_entities[entity_type][polarity].append(word)
                elif label.startswith("I-"):
                    current_entities[entity_type][polarity].append(word)
            else:
                for entity in ["cuisine", "dish"]:
                    for pol in ["positive", "negative"]:
                        if current_entities[entity][pol]:
                            entities[f"{entity}_{pol}"].append(
                                " ".join(current_entities[entity][pol]))
                            current_entities[entity][pol] = []
                            
        for entity in ["cuisine", "dish"]:
            for pol in ["positive", "negative"]:
                if current_entities[entity][pol]:
                    entities[f"{entity}_{pol}"].append(
                        " ".join(current_entities[entity][pol]))
                        
        return entities
        
    def _process_entities(self, entities, entity_type):
        processed = []
        for entity in entities:
            cleaned = self._clean_and_lemmatize(entity)
            match = (self._check_cuisine_similarity(cleaned) if entity_type == "cuisine"
                     else self._check_dish_similarity(cleaned))
            if match:
                processed.append(match)
            else:
                processed.append(f"({cleaned})")
        return list(set(processed))
    
    @staticmethod
    def _clean_and_lemmatize(text):
        text = re.sub(r'[^\w\s]', '', text)
        return text.strip()
        
    def _check_cuisine_similarity(self, text, threshold=70):
        return self._check_similarity(text, self.unique_cuisines, threshold)
        
    def _check_dish_similarity(self, text, threshold=70):
        return self._check_similarity(text, self.unique_dishes, threshold)
        
    @staticmethod
    def _check_similarity(text, targets, threshold):
        best_match = None
        max_similarity = 0
        for target in targets:
            similarity = fuzz.ratio(text.lower(), target.lower())
            if similarity > max_similarity:
                max_similarity = similarity
                best_match = target
        return best_match if max_similarity >= threshold else None

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Анализ предпочтений в еде')
    parser.add_argument('--text', type=str, help='Текст для анализа')
    args = parser.parse_args()
    
    if not args.text:
        args.text = input("Введите текст для анализа: ")
    
    analyzer = FoodAnalyzer(
        model_path='models/request_processing/request_processing_model.pth',
        cuisine_json_path='data/unique_cuisines.json',
        dish_json_path='data/unique_dishes.json'
    )
    result = analyzer.analyze(args.text)
    
    print("\nПозитивная кухня:")
    print("\n".join(result['cuisine_positive']) if result['cuisine_positive'] else "-")
    
    print("\nНегативная кухня:")
    print("\n".join(result['cuisine_negative']) if result['cuisine_negative'] else "-")
    
    print("\nПозитивные блюда:")
    print("\n".join(result['dish_positive']) if result['dish_positive'] else "-")
    
    print("\nНегативные блюда:")
    print("\n".join(result['dish_negative']) if result['dish_negative'] else "-")