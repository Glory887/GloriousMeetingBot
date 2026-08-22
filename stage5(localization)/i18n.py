import json
import os

# Path to the locales folder (relative to this file)
LOCALES_DIR = os.path.join(os.path.dirname(__file__), 'locales')

# Cache for loaded translations to avoid repeated file reads
_cache = {}

def get_text(lang: str, key: str) -> str:
    """
    Retrieve the translation for a given language and key.
    Loads the JSON file if not already cached.
    Returns the key itself if translation is missing (fallback).
    """
    if lang not in _cache:
        try:
            with open(os.path.join(LOCALES_DIR, f'{lang}.json'), 'r', encoding='utf-8') as f:
                _cache[lang] = json.load(f)
        except FileNotFoundError:
            # If language file doesn't exist, use empty dict
            _cache[lang] = {}
    # Return the translation or the key itself if not found
    return _cache[lang].get(key, key)