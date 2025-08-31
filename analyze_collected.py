#!/usr/bin/env python3
import json

def analyze_collected():
    try:
        with open("collected_diacritics.json", "r", encoding="utf-8") as f:
            data = json.load(f)

        # сортируем по убыванию частоты
        sorted_words = sorted(data.items(), key=lambda x: x[1], reverse=True)

        print("=== ТОП-50 подозрительных слов без диакритики ===")
        for word, count in sorted_words[:50]:
            print(f"{word:15} → {count:3} раз")

    except FileNotFoundError:
        print("Файл collected_diacritics.json не найден")
    except Exception as e:
        print(f"Ошибка: {e}")

if __name__ == "__main__":
    analyze_collected()
