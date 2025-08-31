#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Упрощенный скрипт для обработки словацких текстов с помощью UDPipe
"""

import os
import json
import glob
from collections import Counter
import ufal.udpipe as udpipe

def test_udpipe():
    """Тестирует работу UDPipe с простым текстом"""
    model_path = "/home/ubuntu/slovak_corpus/models/slovak-ud-2.1-20180111.udpipe"
    
    print("=== ТЕСТ UDPIPE ===")
    print(f"Путь к модели: {model_path}")
    print(f"Файл существует: {os.path.exists(model_path)}")
    print(f"Размер файла: {os.path.getsize(model_path)} байт")
    
    try:
        print("Загружаю модель...")
        model = udpipe.Model.load(model_path)
        if not model:
            print("ОШИБКА: Модель не загрузилась")
            return False
        
        print("Модель загружена успешно!")
        
        # Создаем pipeline
        pipeline = udpipe.Pipeline(model, "tokenize", udpipe.Pipeline.DEFAULT, udpipe.Pipeline.DEFAULT, "conllu")
        print("Pipeline создан!")
        
        # Тестируем на простом тексте
        test_text = "Toto je test. Druhá veta."
        print(f"Тестовый текст: {test_text}")
        
        result = pipeline.process(test_text)
        print("Результат обработки:")
        print(result[:500] + "..." if len(result) > 500 else result)
        
        return True
        
    except Exception as e:
        print(f"ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        return False

def process_single_file(file_path, model_path, max_chars=10000):
    """Обрабатывает один файл с ограничением по размеру"""
    print(f"Обрабатываю файл: {os.path.basename(file_path)}")
    
    # Читаем файл
    with open(file_path, 'r', encoding='utf-8') as f:
        text = f.read().strip()
    
    # Ограничиваем размер текста для безопасности
    if len(text) > max_chars:
        text = text[:max_chars]
        print(f"  Текст обрезан до {max_chars} символов")
    
    if not text:
        print("  Пустой файл, пропускаю")
        return []
    
    # Загружаем модель
    model = udpipe.Model.load(model_path)
    if not model:
        raise Exception(f"Не удалось загрузить модель: {model_path}")
    
    pipeline = udpipe.Pipeline(model, "tokenize", udpipe.Pipeline.DEFAULT, udpipe.Pipeline.DEFAULT, "conllu")
    
    # Обрабатываем текст
    try:
        processed = pipeline.process(text)
        sentences = parse_conllu_output(processed)
        print(f"  Получено предложений: {len(sentences)}")
        return sentences
    except Exception as e:
        print(f"  ОШИБКА при обработке: {e}")
        return []

def parse_conllu_output(conllu_text):
    """Парсит вывод CoNLL-U и возвращает предложения"""
    sentences = []
    current_sentence = {"tokens": [], "text": ""}
    
    for line in conllu_text.split('\n'):
        line = line.strip()
        
        if not line:
            # Конец предложения
            if current_sentence["tokens"]:
                # Восстанавливаем текст из токенов если не задан
                if not current_sentence["text"]:
                    current_sentence["text"] = " ".join([t["form"] for t in current_sentence["tokens"]])
                sentences.append(current_sentence)
                current_sentence = {"tokens": [], "text": ""}
            continue
        
        if line.startswith('# text = '):
            current_sentence["text"] = line[9:]  # Убираем "# text = "
            continue
        
        if line.startswith('#'):
            continue
        
        # Парсим токен
        parts = line.split('\t')
        if len(parts) >= 10:
            token_id = parts[0]
            
            # Пропускаем составные токены
            if '-' in token_id or '.' in token_id:
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
    
    # Добавляем последнее предложение
    if current_sentence["tokens"]:
        if not current_sentence["text"]:
            current_sentence["text"] = " ".join([t["form"] for t in current_sentence["tokens"]])
        sentences.append(current_sentence)
    
    return sentences

def main():
    print("=== УПРОЩЕННАЯ ОБРАБОТКА СЛОВАЦКИХ ТЕКСТОВ ===")
    
    # Сначала тестируем UDPipe
    if not test_udpipe():
        print("Тест UDPipe не прошел, завершаю работу")
        return
    
    # Пути
    corpus_dir = "/home/ubuntu/slovak_corpus"
    texts_dir = os.path.join(corpus_dir, "texts")
    model_path = os.path.join(corpus_dir, "models", "slovak-ud-2.1-20180111.udpipe")
    
    sentences_file = os.path.join(corpus_dir, "sentences.jsonl")
    morphology_file = os.path.join(corpus_dir, "morphology_data.jsonl")
    stats_file = os.path.join(corpus_dir, "stats.json")
    
    # Получаем список файлов
    text_files = glob.glob(os.path.join(texts_dir, "*.txt"))
    print(f"\nНайдено файлов: {len(text_files)}")
    
    # Статистика
    total_sentences = 0
    total_tokens = 0
    unique_wordforms = set()
    unique_lemmas = set()
    pos_counter = Counter()
    files_processed = 0
    
    # Обрабатываем файлы по одному
    with open(sentences_file, 'w', encoding='utf-8') as sent_f, \
         open(morphology_file, 'w', encoding='utf-8') as morph_f:
        
        for i, text_file in enumerate(text_files):  # Обрабатываем все файлы
            print(f"\n[{i+1}/{len(text_files)}] Обрабатываю: {os.path.basename(text_file)}")
            
            try:
                sentences = process_single_file(text_file, model_path, max_chars=5000)
                
                if not sentences:
                    continue
                
                # Базовое имя файла для ID
                base_name = os.path.splitext(os.path.basename(text_file))[0]
                
                for sent_idx, sentence in enumerate(sentences):
                    if not sentence["tokens"]:
                        continue
                    
                    # Создаем ID предложения
                    sentence_id = f"{base_name}_{sent_idx+1:03d}"
                    
                    # Записываем предложение
                    sent_data = {
                        "sentence_id": sentence_id,
                        "text": sentence["text"],
                        "source": os.path.basename(text_file),
                        "tokens": sentence["tokens"]
                    }
                    
                    sent_f.write(json.dumps(sent_data, ensure_ascii=False) + '\n')
                    
                    # Записываем морфологические данные
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
                    
                    total_sentences += 1
                
                files_processed += 1
                print(f"  Успешно обработан!")
                
            except Exception as e:
                print(f"  ОШИБКА при обработке файла: {e}")
                continue
    
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
    
    print(f"\n=== РЕЗУЛЬТАТЫ ОБРАБОТКИ ===")
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

if __name__ == "__main__":
    main()
