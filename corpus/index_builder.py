#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Создание SQLite индекса словоформ для словацкого корректора
Этап 3: Индексация всех словоформ с примерами предложений
"""

import json
import sqlite3
import os
from collections import defaultdict, Counter
import random
import time

def load_sentences(sentences_file):
    """Загрузка предложений из JSONL файла"""
    sentences = {}
    print(f"Загружаю предложения из {sentences_file}...")
    
    with open(sentences_file, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            if line.strip():
                try:
                    data = json.loads(line)
                    sentences[data['sentence_id']] = data['text']
                except json.JSONDecodeError as e:
                    print(f"Ошибка JSON в строке {line_num}: {e}")
                    continue
    
    print(f"Загружено {len(sentences)} предложений")
    return sentences

def process_morphology_data(morphology_file, sentences):
    """Обработка морфологических данных и группировка по словоформам"""
    print(f"Обрабатываю морфологические данные из {morphology_file}...")
    
    # Структура: wordform -> {lemma, upos, feats_set, frequency, sentence_ids}
    wordforms = defaultdict(lambda: {
        'lemma': None,
        'upos': None,
        'feats_counter': Counter(),
        'frequency': 0,
        'sentence_ids': set()
    })
    
    processed_tokens = 0
    
    with open(morphology_file, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            if line.strip():
                try:
                    data = json.loads(line)
                    form = data['form']
                    lemma = data['lemma']
                    upos = data['upos']
                    feats = data['feats']
                    sentence_id = data['sentence_id']
                    
                    # Пропускаем пустые формы
                    if not form.strip():
                        continue
                    
                    # Обновляем информацию о словоформе
                    wf = wordforms[form]
                    
                    # Устанавливаем основную лемму и POS (первое вхождение)
                    if wf['lemma'] is None:
                        wf['lemma'] = lemma
                        wf['upos'] = upos
                    
                    # Подсчитываем морфологические признаки
                    if feats:
                        wf['feats_counter'][feats] += 1
                    else:
                        wf['feats_counter'][''] += 1
                    
                    # Увеличиваем частотность
                    wf['frequency'] += 1
                    
                    # Добавляем ID предложения (максимум 10 для экономии памяти)
                    if len(wf['sentence_ids']) < 10:
                        wf['sentence_ids'].add(sentence_id)
                    
                    processed_tokens += 1
                    
                    if processed_tokens % 5000 == 0:
                        print(f"Обработано {processed_tokens} токенов...")
                        
                except json.JSONDecodeError as e:
                    print(f"Ошибка JSON в строке {line_num}: {e}")
                    continue
    
    print(f"Обработано {processed_tokens} токенов, найдено {len(wordforms)} уникальных словоформ")
    return wordforms

def select_example_sentences(sentence_ids, sentences, max_examples=5):
    """Выбор разнообразных примеров предложений"""
    available_sentences = []
    
    for sid in sentence_ids:
        if sid in sentences:
            text = sentences[sid].strip()
            # Фильтруем слишком короткие или технические предложения
            if len(text) > 10 and not text.startswith('=') and 'http' not in text:
                available_sentences.append(text)
    
    if not available_sentences:
        # Если нет хороших примеров, берем любые доступные
        for sid in sentence_ids:
            if sid in sentences:
                available_sentences.append(sentences[sid].strip())
                break
    
    # Выбираем разнообразные примеры
    if len(available_sentences) <= max_examples:
        return available_sentences
    
    # Стратегия выбора: первый, последний, средний, и случайные
    selected = []
    selected.append(available_sentences[0])  # первый
    
    if len(available_sentences) > 1:
        selected.append(available_sentences[-1])  # последний
    
    if len(available_sentences) > 2:
        mid = len(available_sentences) // 2
        selected.append(available_sentences[mid])  # средний
    
    # Добавляем случайные до max_examples
    remaining = [s for s in available_sentences if s not in selected]
    random.shuffle(remaining)
    
    while len(selected) < max_examples and remaining:
        selected.append(remaining.pop())
    
    return selected[:max_examples]

def create_sqlite_database(wordforms_data, sentences, db_file):
    """Создание SQLite базы данных с индексом"""
    print(f"Создаю SQLite базу данных {db_file}...")
    
    # Удаляем существующую базу
    if os.path.exists(db_file):
        os.remove(db_file)
    
    conn = sqlite3.connect(db_file)
    conn.execute("PRAGMA encoding = 'UTF-8'")
    conn.execute("PRAGMA journal_mode = WAL")
    
    cursor = conn.cursor()
    
    # Создаем таблицу
    cursor.execute('''
        CREATE TABLE wordforms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            wordform TEXT NOT NULL,
            lemma TEXT NOT NULL,
            upos TEXT NOT NULL,
            feats TEXT,
            frequency INTEGER DEFAULT 1,
            sentences TEXT NOT NULL
        )
    ''')
    
    # Подготавливаем данные для вставки
    insert_data = []
    stats = {
        'total_wordforms': 0,
        'pos_distribution': Counter(),
        'total_examples': 0,
        'feats_coverage': set()
    }
    
    print("Подготавливаю данные для вставки...")
    
    for wordform, data in wordforms_data.items():
        # Определяем наиболее частые морфологические признаки
        most_common_feats = data['feats_counter'].most_common(1)[0][0] if data['feats_counter'] else ''
        
        # Выбираем примеры предложений
        example_sentences = select_example_sentences(data['sentence_ids'], sentences)
        
        if not example_sentences:
            print(f"Предупреждение: нет примеров для словоформы '{wordform}'")
            example_sentences = [f"Пример с '{wordform}' недоступен."]
        
        # Сериализуем примеры в JSON
        sentences_json = json.dumps(example_sentences, ensure_ascii=False)
        
        insert_data.append((
            wordform,
            data['lemma'],
            data['upos'],
            most_common_feats,
            data['frequency'],
            sentences_json
        ))
        
        # Обновляем статистику
        stats['total_wordforms'] += 1
        stats['pos_distribution'][data['upos']] += 1
        stats['total_examples'] += len(example_sentences)
        if most_common_feats:
            stats['feats_coverage'].add(most_common_feats)
    
    # Массовая вставка данных
    print(f"Вставляю {len(insert_data)} записей в базу данных...")
    
    conn.execute("BEGIN TRANSACTION")
    cursor.executemany('''
        INSERT INTO wordforms (wordform, lemma, upos, feats, frequency, sentences)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', insert_data)
    conn.commit()
    
    # Создаем индексы
    print("Создаю индексы...")
    cursor.execute("CREATE INDEX idx_wordform ON wordforms(wordform)")
    cursor.execute("CREATE INDEX idx_lemma ON wordforms(lemma)")
    cursor.execute("CREATE INDEX idx_upos ON wordforms(upos)")
    cursor.execute("CREATE INDEX idx_frequency ON wordforms(frequency DESC)")
    
    # Оптимизируем базу данных
    print("Оптимизирую базу данных...")
    cursor.execute("VACUUM")
    cursor.execute("ANALYZE")
    
    conn.close()
    
    # Финализируем статистику
    stats['avg_examples_per_wordform'] = stats['total_examples'] / stats['total_wordforms']
    stats['unique_feats_count'] = len(stats['feats_coverage'])
    stats['pos_distribution'] = dict(stats['pos_distribution'])
    # Конвертируем set в list для JSON сериализации
    stats['feats_coverage'] = list(stats['feats_coverage'])
    
    print(f"База данных создана: {len(insert_data)} словоформ проиндексировано")
    return stats

def create_jsonl_export(wordforms_data, sentences, export_file):
    """Создание JSONL экспорта индекса"""
    print(f"Создаю JSONL экспорт {export_file}...")
    
    with open(export_file, 'w', encoding='utf-8') as f:
        for wordform, data in sorted(wordforms_data.items()):
            # Определяем наиболее частые морфологические признаки
            most_common_feats = data['feats_counter'].most_common(1)[0][0] if data['feats_counter'] else ''
            
            # Выбираем примеры предложений
            example_sentences = select_example_sentences(data['sentence_ids'], sentences)
            
            if not example_sentences:
                example_sentences = [f"Пример с '{wordform}' недоступен."]
            
            record = {
                'wordform': wordform,
                'lemma': data['lemma'],
                'upos': data['upos'],
                'feats': most_common_feats,
                'frequency': data['frequency'],
                'sentences': example_sentences
            }
            
            f.write(json.dumps(record, ensure_ascii=False) + '\n')
    
    print(f"JSONL экспорт создан: {export_file}")

def save_statistics(stats, stats_file):
    """Сохранение статистики индекса"""
    print(f"Сохраняю статистику в {stats_file}...")
    
    with open(stats_file, 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    
    print(f"Статистика сохранена: {stats_file}")

def main():
    """Основная функция"""
    print("=== ЭТАП 3: Создание SQLite индекса словоформ ===")
    start_time = time.time()
    
    # Пути к файлам
    base_dir = "/home/ubuntu/slovak_corpus"
    sentences_file = os.path.join(base_dir, "sentences.jsonl")
    morphology_file = os.path.join(base_dir, "morphology_data.jsonl")
    db_file = os.path.join(base_dir, "index.sqlite")
    export_file = os.path.join(base_dir, "index_export.jsonl")
    stats_file = os.path.join(base_dir, "index_stats.json")
    
    # Проверяем наличие исходных файлов
    if not os.path.exists(sentences_file):
        print(f"Ошибка: файл {sentences_file} не найден")
        return
    
    if not os.path.exists(morphology_file):
        print(f"Ошибка: файл {morphology_file} не найден")
        return
    
    try:
        # Шаг 1: Загружаем предложения
        sentences = load_sentences(sentences_file)
        
        # Шаг 2: Обрабатываем морфологические данные
        wordforms_data = process_morphology_data(morphology_file, sentences)
        
        # Шаг 3: Создаем SQLite базу данных
        stats = create_sqlite_database(wordforms_data, sentences, db_file)
        
        # Шаг 4: Создаем JSONL экспорт
        create_jsonl_export(wordforms_data, sentences, export_file)
        
        # Шаг 5: Сохраняем статистику
        save_statistics(stats, stats_file)
        
        # Итоговый отчет
        elapsed_time = time.time() - start_time
        print("\n=== ИТОГОВЫЙ ОТЧЕТ ===")
        print(f"Время выполнения: {elapsed_time:.2f} секунд")
        print(f"Всего словоформ проиндексировано: {stats['total_wordforms']}")
        print(f"Среднее количество примеров на словоформу: {stats['avg_examples_per_wordform']:.2f}")
        print(f"Уникальных морфологических признаков: {stats['unique_feats_count']}")
        print("\nРаспределение по частям речи:")
        for pos, count in sorted(stats['pos_distribution'].items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"  {pos}: {count}")
        
        print(f"\nФайлы созданы:")
        print(f"  - SQLite база: {db_file}")
        print(f"  - JSONL экспорт: {export_file}")
        print(f"  - Статистика: {stats_file}")
        
        print("\n=== ЭТАП 3 ЗАВЕРШЕН УСПЕШНО ===")
        
    except Exception as e:
        print(f"Ошибка при выполнении: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
