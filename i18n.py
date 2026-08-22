import json
import os

LOCALES_DIR = os.path.join(os.path.dirname(__file__), 'locales')
_cache = {}

def get_text(lang: str, key: str) -> str:
    if lang not in _cache:
        try:
            with open(os.path.join(LOCALES_DIR, f'{lang}.json'), 'r', encoding='utf-8') as f:
                _cache[lang] = json.load(f)
        except FileNotFoundError:
            _cache[lang] = {}
    return _cache[lang].get(key, key)