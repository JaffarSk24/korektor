#!/usr/bin/env python3
import requests
import json
import re
import time

API_URL = "https://sk.wiktionary.org/w/api.php"
OUT_FILE = "examples_dict.json"

# Расширенный словарь нормализаций
FALLBACK_FORMS = {
    "pekna": ["pekná", "pekný"],
    "pristup": ["prístup"],
    "moznost": ["možnosť"],
    "dalsi": ["ďalší"],
    "mozem": ["môžem"],
    "musim": ["musím"],
    "ano": ["áno"],
    "macka": ["mačka"],
    "co": ["čo"],
    "ze": ["že"],
    "su": ["sú"],
    "ta": ["tá"]
}

def fetch_wikislovnik_examples(word: str):
    candidates = [word]
    if word in FALLBACK_FORMS:
        candidates.extend(FALLBACK_FORMS[word])

    headers = {
        "User-Agent": "SlovakKorektorBot/1.0 (https://slovak-corrector.sk; kontakt@slovak-corrector.sk)"
    }

    for cand in candidates:
        params = {
            "action": "query",
            "prop": "revisions",
            "rvprop": "content",
            "rvslots": "main",
            "format": "json",
            "titles": cand,
            "redirects": "1"
        }

        try:
            r = requests.get(API_URL, params=params, headers=headers, timeout=15)
            r.raise_for_status()
            data = r.json()
            
            pages = data.get("query", {}).get("pages", {})
            if not pages:
                continue
            
            page = list(pages.values())[0]
            revs = page.get("revisions")
            if not revs:
                continue

            content = revs[0].get("slots", {}).get("main", {}).get("*", "")
            if not content:
                continue

            # Ищем блок "Príklady"
            m = re.search(r"==\s*Príklady\s*==(.+?)(==|$)", content, re.S | re.I)
            if not m:
                continue

            examples_block = m.group(1)
            # Каждая строка с '*' в этом блоке может быть примером
            lines = [l.strip("* ").strip() for l in examples_block.splitlines() if l.strip().startswith("*")]
            clean_examples = []
            for l in lines:
                l = re.sub(r"'''?", "", l)  # убираем wiki-bold
                l = re.sub(r"\[\[|\]\]", "", l)  # убираем [[ ]] ссылки
                if l:
                    clean_examples.append(l)

            if clean_examples:
                print(f"✅ {word} → použil som stránku '{cand}' ({len(clean_examples)} príkladov)")
                return clean_examples[:5]

        except Exception as e:
            print(f"Error for {cand}: {e}")
            continue

    return []

def main():
    words = ["pekna", "pristup", "dom", "macka", "co"]  # расширенный тестовый список
    db = {}

    print("🔍 Začínam vyhľadávanie príkladov v Wikislovníku...")
    
    for w in words:
        print(f"\n📖 Spracovávam: {w}")
        ex = fetch_wikislovnik_examples(w)
        if ex:
            db[w.lower()] = ex
            print(f"   ✅ Našiel som {len(ex)} príkladov")
            # Ukážeme prvý príklad
            print(f"   📝 Príklad: {ex[0]}")
        else:
            print(f"   ❌ Nenašiel som príklady")
        time.sleep(2)  # trochu dlhšia pauza pre istotu

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

    print(f"\n📁 Hotovo! Uložené {len(db)} slov do {OUT_FILE}")
    
    # Ukážeme čo sa uložilo
    if db:
        print("\n📋 Prehľad uložených slov:")
        for word, examples in db.items():
            print(f"  • {word}: {len(examples)} príkladov")

if __name__ == "__main__":
    main()