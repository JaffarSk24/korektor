from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
import os
from typing import Dict, List, Optional
import nltk
import json
import re
import threading
import sqlite3

CORPUS_DB = "/opt/korektor/corpus/index.sqlite"

def _filter_slovak_only(text: str) -> bool:
    forbidden = set("ěřůąęół")
    return not any(ch in text.lower() for ch in forbidden)

def get_examples_from_corpus(word: str, limit: int = 3) -> List[str]:
    try:
        conn = sqlite3.connect(CORPUS_DB)
        cur = conn.cursor()
        cur.execute(
            "SELECT sentences FROM wordforms WHERE wordform = ? COLLATE NOCASE OR lemma = ? COLLATE NOCASE LIMIT 1",
            (word, word)
        )
        row = cur.fetchone()
        conn.close()
        if not row or not row[0]:
            return []
        lines = json.loads(row[0])
        out = []
        for s in lines:
            s = re.sub(r"\s+", " ", s).strip()
            if s and _filter_slovak_only(s):
                out.append(s)
            if len(out) >= limit:
                break
        return out
    except Exception as e:
        print("Corpus error:", e)
        return []

PUNCT_AVAILABLE = False
try:
    from deepmultilingualpunctuation import PunctuationModel
    punct_model = PunctuationModel()
    PUNCT_AVAILABLE = True
except Exception:
    PUNCT_AVAILABLE = False

try:
    nltk.data.find('corpora/wordnet')
    nltk.data.find('corpora/omw-1.4')
except LookupError:
    pass

app = FastAPI(title="Slovak Text Fix API", version="1.2.4")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

LANGUAGETOOL_URL = os.getenv("LANGUAGETOOL_URL", "http://languagetool-sk:8010")
REQUEST_TIMEOUT = 30

class CheckRequest(BaseModel):
    text: str
    language: Optional[str] = "sk-SK"
    level: Optional[str] = "picky"

def restore_punctuation(text: str) -> str:
    if not PUNCT_AVAILABLE:
        return text
    try:
        return punct_model.restore_punctuation(text)
    except Exception:
        return text

def lt_check(text: str, language="sk-SK", level="picky") -> Dict:
    try:
        payload = {"text": text, "language": language, "level": level}
        if (language or "").lower() in ("auto", "auto-detect", "auto_detect"):
            payload["preferredVariants"] = "sk-SK"
        response = requests.post(
            f"{LANGUAGETOOL_URL}/v2/check",
            data=payload,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            timeout=REQUEST_TIMEOUT,
        )
    except Exception as e:
        return {"_error": "request_failed", "_exception": str(e)}

    if response.status_code != 200:
        return {"_error": "lt_http_error", "_status": response.status_code, "_body": response.text}

    try:
        return response.json()
    except Exception as e:
        return {"_error": "invalid_json", "_body": response.text, "_exception": str(e)}

DIACRITIC_MAP = {
    "a": ["á", "ä"], "c": ["č"], "d": ["ď"], "e": ["é"],
    "i": ["í"], "l": ["ľ", "ĺ"], "n": ["ň"], "o": ["ó"],
    "r": ["ŕ"], "s": ["š"], "t": ["ť"], "u": ["ú"], "y": ["ý"], "z": ["ž"]
}

def diacritic_fixes(word: str) -> List[str]:
    fixes = []
    for i, ch in enumerate(word):
        if ch in DIACRITIC_MAP:
            for variant in DIACRITIC_MAP[ch]:
                fixes.append(word[:i] + variant + word[i+1:])
    return fixes

def match_case(original: str, suggestion: str) -> str:
    if original.istitle():
        return suggestion.capitalize()
    if original.isupper():
        return suggestion.upper()
    return suggestion

SPECIFIC_DIACRITIC_MAP = {
    r"\bco\b": "čo",
    r"\bmacka\b": "mačka",
    r"\bca\b": "ča",
    r"\bze\b": "že",
    r"\bsu\b": "sú",
    r"\bdalsi\b": "ďalší",
    r"\bnajdalsi\b": "najďalší",
    r"\bakoho\b": "akého",
    r"\bmozem\b": "môžem",
    r"\bmusim\b": "musím",
    r"\bano\b": "áno",
    r"(?<!prosim )(?<!prosím )\bta\b": "tá",
    r"(?<=\bprosim )ta\b": "ťa",
    r"(?<=\bprosím )ta\b": "ťa",
}

COLLECTED_DIACRITICS_FILE = "collected_diacritics.json"
_collected_lock = threading.Lock()

def log_suspect_words(text: str, matches: List[Dict]):
    try:
        already_known = set()
        for pattern in SPECIFIC_DIACRITIC_MAP.keys():
            match = re.search(r'\\b([a-zA-Záäčďéíĺľňóôŕšťúýž]+)\\b', pattern)
            if match:
                already_known.add(match.group(1).lower())
        words = re.findall(r"[a-zA-Záäčďéíĺľňóôŕšťúýž]{2,}", text.lower())
        suspects = []
        for w in words:
            if not any(ch in w for ch in "áäčďéíĺľňóôŕšťúýž"):
                if w not in already_known:
                    suspects.append(w)
        if not suspects:
            return
        with _collected_lock:
            db = {}
            if os.path.exists(COLLECTED_DIACRITICS_FILE):
                with open(COLLECTED_DIACRITICS_FILE, "r", encoding="utf-8") as f:
                    try:
                        db = json.load(f)
                    except Exception:
                        db = {}
            for w in suspects:
                db[w] = db.get(w, 0) + 1
            with open(COLLECTED_DIACRITICS_FILE, "w", encoding="utf-8") as f:
                json.dump(db, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("log_suspect_words error:", e)

def extract_sentence(text: str, start: int, end: int) -> str:
    left = text.rfind('.', 0, start)
    left_q = text.rfind('?', 0, start)
    left_e = text.rfind('!', 0, start)
    left = max(left, left_q, left_e)
    right_dot = text.find('.', end)
    right_q = text.find('?', end)
    right_e = text.find('!', end)
    candidates = [pos for pos in [right_dot, right_q, right_e] if pos != -1]
    right = min(candidates) if candidates else -1
    sent = text[(left + 1 if left != -1 else 0):(right + 1 if right != -1 else len(text))].strip()
    return sent if sent else text.strip()

EXAMPLES_DB = {}
EXAMPLES_FILE = "examples.cleaned.json"
if os.path.exists(EXAMPLES_FILE):
    with open(EXAMPLES_FILE, "r", encoding="utf-8") as f:
        EXAMPLES_DB = json.load(f)

FALLBACK_EXAMPLES: Dict[str, List[str]] = {
    "čo": ["Čo robíš teraz?"],
    "že": ["Myslím, že to je pravda."],
    "sú": ["Deti sú doma."],
    "áno": ["Áno, rozumiem ti."],
    "musím": ["Musím ísť do práce."],
    "môžem": ["Môžem vám pomôcť?"],
    "ďalší": ["Prišiel ďalší hosť."],
    "najďalší": ["To je ten najďalší termín."],
    "tá": ["Tá kniha je veľmi zaujímavá."],
    "ťa": ["Prosím ťa, počkaj chvíľu."]
}

def _clean_examples(lines: List[str]) -> List[str]:
    out = []
    for l in lines:
        l = re.sub(r"\s+", " ", l).strip()
        out.append(l)
    return out

def get_fallback_example(word: str) -> List[str]:
    forms = [word, word.lower(), word.capitalize()]
    for form in forms:
        if form in EXAMPLES_DB and EXAMPLES_DB[form]:
            cleaned = _clean_examples(EXAMPLES_DB[form])
            if cleaned:
                return cleaned[:3]
    low = word.lower()
    if low in FALLBACK_EXAMPLES and FALLBACK_EXAMPLES[low]:
        return [FALLBACK_EXAMPLES[low][0]]
    return []

def add_diacritic_warnings(text: str, existing_matches: List[Dict]) -> List[Dict]:
    new_matches = []
    for pattern, correct in SPECIFIC_DIACRITIC_MAP.items():
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            offset = match.start()
            length = len(match.group())
            word_original = match.group()
            correct_cased = match_case(word_original, correct)
            corpus_examples = get_examples_from_corpus(correct_cased, limit=3)
            if corpus_examples:
                examples = [f"{correct_cased}: {ex}" for ex in corpus_examples]
            else:
                ex_lines = get_fallback_example(correct_cased)
                if ex_lines:
                    examples = [f"{correct_cased}: {ex}" for ex in ex_lines]
                else:
                    examples = [f"Namiesto '{word_original}' použite '{correct_cased}'."]
            new_matches.append({
                "offset": offset,
                "length": length,
                "message": f"Možno chýba diakritika: mysleli ste '{correct_cased}'?",
                "rule": "CUSTOM_DIACRITICS",
                "category": "TYPOS",
                "replacements": [{"value": correct_cased}],
                "examples": examples,
                "usage_rules": [
                    f"Správne použitie: {correct_cased} sa často používa v bežnej komunikácii.",
                    f"Vo formálnom texte sa uprednostňuje tvar: {correct_cased}."
                ]
            })
    return new_matches

def detect_enumeration_errors(text: str) -> List[Dict]:
    matches = []
    if " a " in text:
        parts = text.split(" a ")
        left = parts[0]
        if "," not in left and len(left.split()) >= 2:
            off = text.rfind(" a ")
            matches.append({
                "offset": off,
                "length": 1,
                "message": "Možno chýba čiarka v enumerácii",
                "rule": "ENUM_COMMA",
                "category": "PUNCTUATION",
                "replacements": [{"value": ", a"}],
                "examples": ["Deti, mačky a psy sú povolené."],
                "usage_rules": [
                    "Správne použitie: pred spojkou 'a' vymenúvacieho zoznamu sa píše čiarka."
                ]
            })
    return matches

@app.get("/")
def root():
    return {
        "message": "OK",
        "LANGUAGETOOL_URL": LANGUAGETOOL_URL,
        "punctuation_model": PUNCT_AVAILABLE,
        "version": "1.2.4"
    }

def dedupe_matches(matches: List[Dict]) -> List[Dict]:
    seen=set();out=[]
    for m in matches:
        key=(m["offset"],m["length"],m.get("rule"))
        if key not in seen:
            seen.add(key)
            out.append(m)
    return out

@app.post("/check")
def api_check(req: CheckRequest):
    text = req.text or ""
    if not text.strip():
        return {"matches": [], "text": text}
    text_for_check = restore_punctuation(text)
    matches: List[Dict] = []
    lt_json = lt_check(text_for_check, req.language or "sk-SK", req.level or "picky")
    if isinstance(lt_json, dict) and not lt_json.get("_error"):
        for m in lt_json.get("matches", []):
            word_original = text_for_check[m.get("offset", 0): m.get("offset", 0) + m.get("length", 0)]
            reps = [{"value": match_case(word_original, r.get("value", ""))}
                    for r in (m.get("replacements") or []) if r.get("value")]
            if not reps:
                word = text_for_check[m.get("offset", 0): m.get("offset", 0) + m.get("length", 0)]
                fixes = diacritic_fixes(word)
                reps = [{"value": match_case(word, f)} for f in fixes]
            examples = []
            if reps:
                for r in reps[:3]:
                    w = r["value"]
                    ex_lines = get_fallback_example(w)
                    if ex_lines:
                        examples.extend([f"{w}: {ex}" for ex in ex_lines])
                if not examples:
                    examples = get_fallback_example(reps[0]["value"])
            wrong_word = text_for_check[m.get("offset", 0): m.get("offset", 0) + m.get("length", 0)]
            corpus_examples = get_examples_from_corpus(wrong_word, limit=3)
            if corpus_examples:
                for ex in corpus_examples:
                    if len(examples) < 3:
                        examples.append(f"{wrong_word}: {ex}")
            matches.append({
                "offset": m.get("offset", 0),
                "length": m.get("length", 0),
                "message": m.get("message", ""),
                "rule": (m.get("rule", {}) or {}).get("id", ""),
                "category": (m.get("rule", {}) or {}).get("category", {}).get("id", ""),
                "replacements": reps[:5],
                "examples": examples[:3],
                "usage_rules": [
                    f"Správne použitie: {reps[0]['value']} sa často používa v bežnej komunikácii.",
                    f"Vo formálnom texte sa uprednostňuje tvar: {reps[0]['value']}."
                ] if reps else []
            })
    diacritic_matches = add_diacritic_warnings(text_for_check, matches)
    matches.extend(diacritic_matches)
    matches.extend(detect_enumeration_errors(text_for_check))
    log_suspect_words(text_for_check, matches)
    matches = dedupe_matches(matches)
    return {"matches": matches, "text": text_for_check}