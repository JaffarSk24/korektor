import bz2
import os
import re
import json
import requests
from xml.sax import make_parser, ContentHandler

DUMP_URLS = [
    # Slovak Wiktionary
    "https://dumps.wikimedia.org/skwiktionary/latest/skwiktionary-latest-pages-articles.xml.bz2",
    # Slovak Wikipedia
    "https://dumps.wikimedia.org/skwiki/latest/skwiki-latest-pages-articles.xml.bz2",
    # Slovak Wikibooks
    "https://dumps.wikimedia.org/skwikibooks/latest/skwikibooks-latest-pages-articles.xml.bz2",
    # Slovak Wikisource
    "https://dumps.wikimedia.org/skwikisource/latest/skwikisource-latest-pages-articles.xml.bz2",
]

OUTPUT_FILE = "examples.json"

def download_dump(url):
    file_name = url.split("/")[-1]
    if os.path.exists(file_name):
        print(f"[i] Dump už existuje: {file_name}")
        return file_name
    print(f"[i] Sťahujem dump z {url} ...")
    r = requests.get(url, stream=True)
    with open(file_name, "wb") as f:
        for chunk in r.iter_content(1024 * 1024):
            f.write(chunk)
    print(f"[✓] Hotovo: {file_name}")
    return file_name

def load_existing_examples():
    """Načíta existujúci examples.json ak existuje"""
    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                existing = json.load(f)
            print(f"[i] Načítaný existujúci {OUTPUT_FILE} s {len(existing)} slovami")
            return existing
        except Exception as e:
            print(f"[!] Chyba pri načítaní {OUTPUT_FILE}: {e}")
            return {}
    else:
        print(f"[i] {OUTPUT_FILE} neexistuje, vytvorím nový")
        return {}

class WikiHandler(ContentHandler):
    def __init__(self):
        self.examples = {}
        self.current_title = ""
        self.current_text = ""
        self.in_title = False
        self.in_text = False
        self.total_pages = 0
        self.pages_with_examples = 0

    def startElement(self, name, attrs):
        if name == "title":
            self.in_title = True
            self.current_title = ""
        elif name == "text":
            self.in_text = True
            self.current_text = ""

    def endElement(self, name):
        if name == "title":
            self.in_title = False
        elif name == "text":
            self.in_text = False
        elif name == "page":
            self.total_pages += 1
            if self.total_pages % 1000 == 0:
                print(f"[i] Spracovaných {self.total_pages} stránok, nájdených {self.pages_with_examples} s príkladmi")
            self.process_page()

    def characters(self, content):
        if self.in_title:
            self.current_title += content
        elif self.in_text:
            self.current_text += content

    def process_page(self):
        if not self.current_title or not self.current_text:
            return

        # Normalizujeme a filtrujeme title ako „kandidát slova"
        key = self.current_title.strip()

        # Odsekáme pространства имён a viacslové/technické nadpisy
        if (":" in key) or (" " in key) or any(ch.isdigit() for ch in key):
            return

        # Povoľujeme len slová z latinky s možnými slovenskými diakritikami, dĺžka 2–30
        if not re.fullmatch(r"[A-Za-zÀ-žÁáÄäČčĎďÉéÍíĹĺĽľŇňÓóÔôŔŕŘřŠšŤťÚúÝýŽž]{2,30}", key):
            return

        key = key.lower()

        lines = []

        # Hľadáme sekcie Príklady (rôzne úrovne)
        patterns = [
            r"={2,4}\s*Príklady\s*={2,4}(.+?)(?:={2,4}|$)",
            r"={2,4}\s*Príklad\s*={2,4}(.+?)(?:={2,4}|$)",
            r"={2,4}\s*Použitie\s*={2,4}(.+?)(?:={2,4}|$)",
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, self.current_text, re.S | re.I)
            for m in matches:
                block = m.group(1)
                block_lines = [
                    re.sub(r"('{2,}|[\[\]{}])", "", l.strip("* #").strip())
                    for l in block.splitlines()
                    if l.strip().startswith(("*", "#")) and len(l.strip()) > 10
                ]
                lines.extend([l for l in block_lines if l and len(l.split()) >= 3])

        # Dodatočne: hľadáme vety v texte (5-25 slov)
        sentences = re.split(r'[.!?]\s+', self.current_text)
        for s in sentences:
            s_clean = re.sub(r"['\[\]{}|=*#]", "", s).strip()
            word_count = len(s_clean.split())
            if 5 <= word_count <= 25 and not s_clean.startswith(('http', 'www', 'File:', 'Category:')):
                lines.append(s_clean)

        # Ak sú linky-príklady — ukladáme
        if lines:
            unique_lines = list(dict.fromkeys(lines))[:1]  # len 1 príklad
            if key not in self.examples:
                self.examples[key] = []
            self.examples[key].extend(unique_lines)
            self.pages_with_examples += 1

def parse_dump_streaming(file_name):
    print(f"[i] Streamovo parsujem {file_name}...")
    handler = WikiHandler()
    parser = make_parser()
    parser.setContentHandler(handler)
    
    with bz2.open(file_name, "rt", encoding="utf-8") as f:
        parser.parse(f)
    
    print(f"[✓] Spracovaných {handler.total_pages} stránok, nájdených {handler.pages_with_examples} s príkladmi v {file_name}")
    return handler.examples

def merge_and_clean(existing_dict, new_dicts):
    """Zlúči existujúci slovník s novými a odstráni duplikáty"""
    merged = existing_dict.copy()
    
    for d in new_dicts:
        for word, lines in d.items():
            if word not in merged:
                merged[word] = []
            merged[word].extend(lines)

    cleaned = {}
    for word, lines in merged.items():
        # Odstránime duplikáty a obmedzíme na 1 príklad na slovo
        unique = list(dict.fromkeys(lines))
        cleaned[word] = unique[:1]
    
    return cleaned

if __name__ == "__main__":
    # Načítame existujúci examples.json
    existing_examples = load_existing_examples()
    
    collected = []
    
    for url in DUMP_URLS:
        try:
            f = download_dump(url)
            data = parse_dump_streaming(f)
            collected.append(data)
        except Exception as e:
            print(f"[!] Chyba pri spracovaní {url}: {e}")
            continue

    # Zlúčime s existujúcimi dátami
    final = merge_and_clean(existing_examples, collected)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(final, f, ensure_ascii=False, indent=2)

    print(f"[✓] Uložené do {OUTPUT_FILE} (spolu {len(final)} slov)")
    
    # Ukážka prvých pár slov
    sample_words = list(final.keys())[:5]
    for word in sample_words:
        print(f"  {word}: {len(final[word])} príkladov")