
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для обработки словацких текстов с помощью UDPipe
Создает корпус предложений с морфологической разметкой
"""

import os
import json
import glob
from collections import defaultdict, Counter
import ufal.udpipe as udpipe
import random

def load_udpipe_model(model_path):
    """Загружает модель UDPipe"""
    print(f"Загружаю модель UDPipe: {model_path}")
    
    # Проверяем существование файла
    if not os.path.exists(model_path):
        raise Exception(f"Файл модели не найден: {model_path}")
    
    try:
        model = udpipe.Model.load(model_path)
        if not model:
            raise Exception(f"Не удалось загрузить модель: {model_path}")
        
        print("Модель загружена успешно")
        pipeline = udpipe.Pipeline(model, "tokenize", udpipe.Pipeline.DEFAULT, udpipe.Pipeline.DEFAULT, "conllu")
        print("Pipeline создан успешно")
        return pipeline
    except Exception as e:
        print(f"Ошибка при загрузке модели: {e}")
        raise

def process_text_with_udpipe(text, pipeline):
    """Обрабатывает текст с помощью UDPipe и возвращает предложения с токенами"""
    # Обработка текста
    processed = pipeline.process(text)
    
    sentences = []
    current_sentence = {"tokens": [], "text": ""}
    
    for line in processed.split('\n'):
        line = line.strip()
        
        # Пропускаем комментарии и пустые строки
        if not line or line.startswith('#'):
            if line.startswith('# text = '):
                current_sentence["text"] = line[9:]  # Убираем "# text = "
            continue
        
        # Конец предложения
        if line == "":
            if current_sentence["tokens"]:
                sentences.append(current_sentence)
                current_sentence = {"tokens": [], "text": ""}
            continue
        
        # Парсим токен
        parts = line.split('\t')
        if len(parts) >= 10:
            token_id = parts[0]
            
            # Пропускаем составные токены (содержат дефис)
            if '-' in token_id:
                continue
                
            form = parts[1]
            lemma = parts[2]
            upos = parts[3]
            feats = parts[5] if parts[5] != '_' else ""
            
            token = {
                "form": form,
                "lemma": lemma,
                "upos": upos,
                "feats": feats
            }
            
            current_sentence["tokens"].append(token)
    
    # Добавляем последнее предложение, если есть
    if current_sentence["tokens"]:
        sentences.append(current_sentence)
    
    return sentences

def extract_sentence_text(tokens):
    """Извлекает текст предложения из токенов"""
    if not tokens:
        return ""
    
    text_parts = []
    for i, token in enumerate(tokens):
        form = token["form"]
        
        # Добавляем пробел перед токеном, кроме первого и знаков препинания
        if i > 0 and not form in '.,!?;:()[]{}"\'-':
            text_parts.append(" ")
        
        text_parts.append(form)
    
    return "".join(text_parts)

def main():
    # Пути
    corpus_dir = "/home/ubuntu/slovak_corpus"
    texts_dir = os.path.join(corpus_dir, "texts")
    model_path = os.path.join(corpus_dir, "models", "slovak-ud-2.1-20180111.udpipe")
    
    sentences_file = os.path.join(corpus_dir, "sentences.jsonl")
    morphology_file = os.path.join(corpus_dir, "morphology_data.jsonl")
    stats_file = os.path.join(corpus_dir, "stats.json")
    
    print("=== ОБРАБОТКА СЛОВАЦКИХ ТЕКСТОВ С UDPIPE ===")
    print(f"Папка с текстами: {texts_dir}")
    print(f"Модель UDPipe: {model_path}")
    
    # Загружаем модель
    pipeline = load_udpipe_model(model_path)
    
    # Получаем список всех текстовых файлов
    text_files = glob.glob(os.path.join(texts_dir, "*.txt"))
    print(f"Найдено файлов: {len(text_files)}")
    
    # Статистика
    total_sentences = 0
    total_tokens = 0
    unique_wordforms = set()
    unique_lemmas = set()
    pos_counter = Counter()
    files_processed = 0
    
    # Открываем файлы для записи
    with open(sentences_file, 'w', encoding='utf-8') as sent_f, \
         open(morphology_file, 'w', encoding='utf-8') as morph_f:
        
        for text_file in text_files:
            print(f"Обрабатываю: {os.path.basename(text_file)}")
            
            # Читаем файл
            with open(text_file, 'r', encoding='utf-8') as f:
                text = f.read().strip()
            
            if not text:
                print(f"  Пустой файл, пропускаю")
                continue
            
            # Обрабатываем текст
            sentences = process_text_with_udpipe(text, pipeline)
            
            # Базовое имя файла для ID
            base_name = os.path.splitext(os.path.basename(text_file))[0]
            
            file_sentences = 0
            for sent_idx, sentence in enumerate(sentences):
                if not sentence["tokens"]:
                    continue
                
                # Создаем ID предложения
                sentence_id = f"{base_name}_{sent_idx+1:03d}"
                
                # Извлекаем текст предложения, если не задан
                if not sentence["text"]:
                    sentence["text"] = extract_sentence_text(sentence["tokens"])
                
                # Записываем предложение
                sent_data = {
                    "sentence_id": sentence_id,
                    "text": sentence["text"],
                    "source": os.path.basename(text_file),
                    "tokens": sentence["tokens"]
                }
                
                sent_f.write(json.dumps(sent_data, ensure_ascii=False) + '\n')
                
                # Записываем морфологические данные для каждого токена
                for token_idx, token in enumerate(sentence["tokens"]):
                    morph_data = {
                        "sentence_id": sentence_id,
                        "token_position": token_idx,
                        "form": token["form"],
                        "lemma": token["lemma"],
                        "upos": token["upos"],
                        "feats": token["feats"]
                    }
                    
                    morph_f.write(json.dumps(morph_data, ensure_ascii=False) + '\n')
                    
                    # Обновляем статистику
                    unique_wordforms.add(token["form"].lower())
                    unique_lemmas.add(token["lemma"].lower())
                    pos_counter[token["upos"]] += 1
                    total_tokens += 1
                
                file_sentences += 1
                total_sentences += 1
            
            print(f"  Предложений: {file_sentences}")
            files_processed += 1
    
    # Сохраняем статистику
    stats = {
        "files_processed": files_processed,
        "total_sentences": total_sentences,
        "total_tokens": total_tokens,
        "unique_wordforms": len(unique_wordforms),
        "unique_lemmas": len(unique_lemmas),
        "pos_distribution": dict(pos_counter),
        "avg_tokens_per_sentence": round(total_tokens / total_sentences, 2) if total_sentences > 0 else 0
    }
    
    with open(stats_file, 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    
    print("\n=== РЕЗУЛЬТАТЫ ОБРАБОТКИ ===")
    print(f"Обработано файлов: {files_processed}")
    print(f"Всего предложений: {total_sentences}")
    print(f"Всего токенов: {total_tokens}")
    print(f"Уникальных словоформ: {len(unique_wordforms)}")
    print(f"Уникальных лемм: {len(unique_lemmas)}")
    print(f"Среднее токенов на предложение: {stats['avg_tokens_per_sentence']}")
    
    print(f"\nТоп-10 частей речи:")
    for pos, count in pos_counter.most_common(10):
        print(f"  {pos}: {count}")
    
    print(f"\nФайлы созданы:")
    print(f"  {sentences_file}")
    print(f"  {morphology_file}")
    print(f"  {stats_file}")
    
    # Проверка качества - показываем несколько случайных предложений
    print(f"\n=== ПРОВЕРКА КАЧЕСТВА ===")
    print("Случайные предложения с морфологией:")
    
    # Читаем несколько случайных предложений для проверки
    with open(sentences_file, 'r', encoding='utf-8') as f:
        all_sentences = f.readlines()
    
    if len(all_sentences) >= 5:
        sample_sentences = random.sample(all_sentences, min(5, len(all_sentences)))
        
        for i, line in enumerate(sample_sentences, 1):
            sent_data = json.loads(line)
            print(f"\n{i}. ID: {sent_data['sentence_id']}")
            print(f"   Текст: {sent_data['text']}")
            print(f"   Источник: {sent_data['source']}")
            print(f"   Токены ({len(sent_data['tokens'])}):")
            
            for token in sent_data['tokens'][:10]:  # Показываем первые 10 токенов
                feats_str = f" [{token['feats']}]" if token['feats'] else ""
                print(f"     {token['form']} -> {token['lemma']} ({token['upos']}){feats_str}")
            
            if len(sent_data['tokens']) > 10:
                print(f"     ... и еще {len(sent_data['tokens']) - 10} токенов")

if __name__ == "__main__":
    main()
