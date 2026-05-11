import re
import unicodedata

def _normalize_text_key(text):
    text = text or ""
    pattern = r'(?m)^\s*(?:[\(（]?(?:[\d]+|[a-zA-Z]|[一二三四五六七八九十百千万]+)[.\)）\]、](?!\d)\s*|[•·*+\-]\s*)'
    text = re.sub(pattern, '', text)
    text = unicodedata.normalize("NFKC", text)
    return "".join(ch for ch in text if unicodedata.category(ch)[0] not in {"Z", "C"})

print("1. Hello ->", _normalize_text_key("1. Hello"))
print("Hello ->", _normalize_text_key("Hello"))
print("- Test ->", _normalize_text_key("- Test"))
print("Test ->", _normalize_text_key("Test"))
