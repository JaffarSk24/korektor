import json
import re

def is_valid_slovak_word(word):
    """Проверяет, является ли слово валидным словацким словом"""
    if not word or len(word) < 2:
        return False
    
    # Исключаем явно несловацкие слова
    non_slovak_words = {'free', 'wiki', 'the', 'and', 'or', 'of', 'in', 'to', 'for'}
    if word.lower() in non_slovak_words:
        return False
    
    # Слово должно содержать только буквы, цифры, дефисы
    if not re.match(r'^[a-záäčďéíĺľňóôŕšťúýž\-]+$', word.lower()):
        return False
    
    return True

def is_valid_example(example):
    """Проверяет, является ли пример валидным предложением"""
    if not example or len(example.strip()) < 10:
        return False
    
    # Исключаем только явный служебный мусор
    unwanted_markers = [
        'Etymológia', 'Výslovnosť', 'IPA', 'Kategória', 'Podstatné meno', 
        'Slovenčina', 'Angličtina', 'Minimumsk', 'Význam', 'Príznaky',
        'Zo staro', 'Z w:', 'z pragma', 'ktoré vychádza', 'Doplňte zdroj',
        'rod ženský', 'rod mužský', 'slangový výraz', 'Slangové výrazy',
        'Upraviť', 'Príkladsk', '<ref', '</ref>', 'Možno hľadáte',
        'Pozri aj', 'Viď aj'
    ]
    
    for marker in unwanted_markers:
        if marker in example:
            return False
    
    # Пример должен содержать пробелы (т.е. быть предложением)
    if ' ' not in example.strip():
        return False
    
    # Пример должен содержать хотя бы одну словацкую диакритику
    slovak_diacritics = 'áäčďéíĺľňóôŕšťúýž'
    if not any(char in example.lower() for char in slovak_diacritics):
        return False
    
    return True

def clean_example(example):
    """Очищает пример от лишних символов"""
    example = ' '.join(example.split())
    example = example.strip()
    return example

# Загружаем исходный файл
with open('examples.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

cleaned_data = {}
valid_count = 0

for word, examples in data.items():
    if not is_valid_slovak_word(word):
        continue
    
    valid_examples = []
    for example in examples:
        if is_valid_example(example):
            cleaned_example = clean_example(example)
            if cleaned_example and len(cleaned_example) > 15:
                valid_examples.append(cleaned_example)
    
    if valid_examples:
        cleaned_data[word] = [valid_examples[0]]
        valid_count += 1

with open('examples.cleaned.json', 'w', encoding='utf-8') as f:
    json.dump(cleaned_data, f, ensure_ascii=False, indent=2)

print(f"OK: {valid_count} слов с валидными примерами сохранено в examples.cleaned.json")