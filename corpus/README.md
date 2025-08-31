# Словацкий лингвистический корпус

Комплексный словацкий корпус для задач обработки естественного языка, морфологического анализа и разработки корректоров орфографии.

## Статистика корпуса

- **Произведений**: 55 словацких литературных текстов
- **Предложений**: 3,689 предложений с морфологической разметкой
- **Словоформ**: 8,433 уникальных словоформ в индексе
- **Примеров использования**: 12,622 контекстных примеров
- **Дата создания**: 30 августа 2025

## Структура корпуса

```
slovak_corpus/
├── README.md                 # Данная инструкция
├── texts/                    # Исходные очищенные тексты (55 файлов)
├── sentences.jsonl           # Предложения с морфологической разметкой
├── index.sqlite             # Основной SQLite индекс словоформ
├── index_export.jsonl       # JSONL экспорт индекса
├── catalog.txt              # Каталог произведений с метаданными
└── stats/                   # Статистика и отчеты
    ├── index_stats.json     # Детальная статистика индекса
    ├── STAGE1_REPORT.md     # Отчет этапа 1: сбор текстов
    ├── ETAP2_REPORT.md      # Отчет этапа 2: морфологический анализ
    └── STAGE3_REPORT.md     # Отчет этапа 3: создание индекса
```

## Использование SQLite индекса

### Подключение к базе данных

```python
import sqlite3

# Подключение к индексу
conn = sqlite3.connect('index.sqlite')
cursor = conn.cursor()

# Просмотр структуры таблицы
cursor.execute("PRAGMA table_info(wordforms)")
columns = cursor.fetchall()
for col in columns:
    print(col)
```

### Примеры SQL-запросов

#### 1. Поиск всех форм слова
```sql
-- Найти все формы слова "dom" (дом)
SELECT lemma, form, pos, feats, examples 
FROM wordforms 
WHERE lemma = 'dom' 
ORDER BY form;
```

#### 2. Поиск по части речи
```sql
-- Найти все существительные в именительном падеже
SELECT lemma, form, feats, examples 
FROM wordforms 
WHERE pos = 'NOUN' 
AND feats LIKE '%Case=Nom%' 
LIMIT 20;
```

#### 3. Поиск по морфологическим признакам
```sql
-- Найти все глаголы в прошедшем времени
SELECT lemma, form, feats, examples 
FROM wordforms 
WHERE pos = 'VERB' 
AND feats LIKE '%Tense=Past%' 
LIMIT 10;
```

#### 4. Статистика по частям речи
```sql
-- Количество словоформ по частям речи
SELECT pos, COUNT(*) as count 
FROM wordforms 
GROUP BY pos 
ORDER BY count DESC;
```

### Python API для работы с корпусом

```python
import sqlite3
import json

class SlovakCorpus:
    def __init__(self, db_path='index.sqlite'):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
    
    def search_lemma(self, lemma):
        """Поиск всех форм леммы"""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM wordforms WHERE lemma = ?", 
            (lemma,)
        )
        return cursor.fetchall()
    
    def search_form(self, form):
        """Поиск по словоформе"""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM wordforms WHERE form = ?", 
            (form,)
        )
        return cursor.fetchall()
    
    def get_examples(self, lemma, limit=5):
        """Получить примеры использования"""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT examples FROM wordforms WHERE lemma = ? LIMIT ?", 
            (lemma, limit)
        )
        results = cursor.fetchall()
        examples = []
        for row in results:
            if row['examples']:
                examples.extend(json.loads(row['examples'])[:limit])
        return examples[:limit]
    
    def close(self):
        self.conn.close()

# Пример использования
corpus = SlovakCorpus()

# Поиск форм слова "kniha" (книга)
forms = corpus.search_lemma('kniha')
for form in forms:
    print(f"{form['form']} - {form['feats']}")

# Получить примеры использования
examples = corpus.get_examples('kniha', 3)
for example in examples:
    print(f"- {example}")

corpus.close()
```

## Формат данных

### sentences.jsonl
Каждая строка содержит JSON-объект с предложением:
```json
{
  "text": "Pôvodný text predloženia.",
  "tokens": [
    {
      "text": "Pôvodný",
      "lemma": "pôvodný",
      "pos": "ADJ",
      "feats": "Animacy=Inan|Case=Nom|Degree=Pos|Gender=Masc|Number=Sing"
    }
  ],
  "source": "filename.txt"
}
```

### index_export.jsonl
Экспорт индекса в формате JSONL:
```json
{
  "lemma": "dom",
  "form": "dome",
  "pos": "NOUN",
  "feats": "Animacy=Inan|Case=Loc|Gender=Masc|Number=Sing",
  "examples": ["V dome bolo ticho.", "Išiel som domov."]
}
```

## Интеграция с корректором орфографии

### Проверка существования словоформы
```python
def is_valid_word(word, corpus_db):
    """Проверить, существует ли словоформа в корпусе"""
    cursor = corpus_db.cursor()
    cursor.execute("SELECT 1 FROM wordforms WHERE form = ?", (word,))
    return cursor.fetchone() is not None

def get_word_suggestions(word, corpus_db, limit=5):
    """Получить предложения для исправления"""
    cursor = corpus_db.cursor()
    # Поиск похожих слов (упрощенный алгоритм)
    cursor.execute(
        "SELECT form FROM wordforms WHERE form LIKE ? LIMIT ?", 
        (f"%{word[:3]}%", limit)
    )
    return [row[0] for row in cursor.fetchall()]
```

### Морфологическая валидация
```python
def validate_morphology(word, expected_pos, corpus_db):
    """Проверить соответствие части речи"""
    cursor = corpus_db.cursor()
    cursor.execute(
        "SELECT pos FROM wordforms WHERE form = ?", 
        (word,)
    )
    results = cursor.fetchall()
    return any(row[0] == expected_pos for row in results)
```

## Добавление новых произведений

### 1. Подготовка текста
```bash
# Очистка текста от лишних символов
python -c "
import re
with open('new_text.txt', 'r', encoding='utf-8') as f:
    text = f.read()
# Удаление лишних пробелов и символов
text = re.sub(r'\s+', ' ', text)
text = re.sub(r'[^\w\s\.\,\!\?\;\:\-\'\"]', '', text)
with open('new_text_clean.txt', 'w', encoding='utf-8') as f:
    f.write(text)
"
```

### 2. Морфологический анализ
```python
import spacy

# Загрузка модели (требует установки: pip install spacy)
nlp = spacy.load("sk_core_news_sm")

def analyze_text(text_file, output_file):
    with open(text_file, 'r', encoding='utf-8') as f:
        text = f.read()
    
    doc = nlp(text)
    sentences = []
    
    for sent in doc.sents:
        tokens = []
        for token in sent:
            if not token.is_space:
                tokens.append({
                    "text": token.text,
                    "lemma": token.lemma_,
                    "pos": token.pos_,
                    "feats": str(token.morph)
                })
        
        if tokens:
            sentences.append({
                "text": sent.text.strip(),
                "tokens": tokens,
                "source": text_file
            })
    
    with open(output_file, 'w', encoding='utf-8') as f:
        for sent in sentences:
            f.write(json.dumps(sent, ensure_ascii=False) + '\n')

# Использование
analyze_text('new_text_clean.txt', 'new_sentences.jsonl')
```

### 3. Обновление индекса
```python
def update_index(sentences_file, db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    with open(sentences_file, 'r', encoding='utf-8') as f:
        for line in f:
            sentence = json.loads(line)
            for token in sentence['tokens']:
                # Проверить, существует ли уже такая словоформа
                cursor.execute(
                    "SELECT examples FROM wordforms WHERE lemma=? AND form=?",
                    (token['lemma'], token['text'])
                )
                result = cursor.fetchone()
                
                if result:
                    # Добавить новый пример
                    examples = json.loads(result[0]) if result[0] else []
                    if sentence['text'] not in examples:
                        examples.append(sentence['text'])
                        cursor.execute(
                            "UPDATE wordforms SET examples=? WHERE lemma=? AND form=?",
                            (json.dumps(examples, ensure_ascii=False), 
                             token['lemma'], token['text'])
                        )
                else:
                    # Создать новую запись
                    cursor.execute(
                        "INSERT INTO wordforms (lemma, form, pos, feats, examples) VALUES (?, ?, ?, ?, ?)",
                        (token['lemma'], token['text'], token['pos'], 
                         token['feats'], json.dumps([sentence['text']], ensure_ascii=False))
                    )
    
    conn.commit()
    conn.close()

# Использование
update_index('new_sentences.jsonl', 'index.sqlite')
```

## Технические требования

### Зависимости Python
```bash
pip install sqlite3 json spacy
python -m spacy download sk_core_news_sm
```

### Системные требования
- Python 3.7+
- SQLite 3.x
- Кодировка UTF-8
- Свободное место: ~50MB для полного корпуса

## Лицензия и авторские права

Корпус создан на основе произведений словацкой литературы, находящихся в общественном достоянии. Морфологическая разметка и индексация выполнены с использованием открытых инструментов NLP.

**Использование**: Корпус предназначен для исследовательских и образовательных целей. При использовании в коммерческих проектах рекомендуется проверить статус авторских прав на исходные тексты.

**Цитирование**: При использовании корпуса в научных работах просьба указывать:
```
Словацкий лингвистический корпус (2025). 55 произведений, 8,433 словоформы. 
Создан с использованием spaCy и Universal Dependencies.
```

## Поддержка и обратная связь

Для вопросов по использованию корпуса, сообщений об ошибках или предложений по улучшению создайте issue в репозитории проекта.

---

*Последнее обновление: 30 августа 2025*