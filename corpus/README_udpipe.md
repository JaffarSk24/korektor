
# Обработка словацких текстов с UDPipe

## Файлы

- `process_udpipe.py` - основной скрипт обработки
- `models/slovak-snk-ud-2.12-230717.udpipe` - словацкая модель UDPipe
- `sentences.jsonl` - корпус предложений с морфологией (результат)
- `morphology_data.jsonl` - морфологические данные по токенам (результат)
- `stats.json` - статистика обработки (результат)

## Использование

```bash
cd /home/ubuntu/slovak_corpus
python3 process_udpipe.py
```

## Формат данных

### sentences.jsonl
Каждая строка - JSON объект предложения:
```json
{
  "sentence_id": "hviezdoslav_hajnikova_zena_001",
  "text": "Bola raz jedna žena, ktorá mala veľmi krásne vlasy.",
  "source": "hviezdoslav_hajnikova_zena.txt",
  "tokens": [...]
}
```

### morphology_data.jsonl
Каждая строка - JSON объект токена:
```json
{
  "sentence_id": "hviezdoslav_hajnikova_zena_001",
  "token_position": 0,
  "form": "Bola",
  "lemma": "byť",
  "upos": "AUX",
  "feats": "Gender=Fem|Number=Sing|Tense=Past|VerbForm=Part"
}
```
