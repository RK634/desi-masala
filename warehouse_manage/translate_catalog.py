"""Generate saved product translations using DeepL.
Run from the backend project directory after applying 009_product_translations.sql.
Required environment variable: DEEPL_AUTH_KEY. Uses DATABASE_URL/database.py get_connection.
This script writes translations as reviewed=FALSE so an administrator can review them.
"""
import hashlib
import os
import sys
import urllib.parse
import urllib.request
import json

from database import get_connection

LANGUAGES = {"de": "DE", "fr": "FR", "es": "ES", "pl": "PL", "hi": "HI"}


def translate(text: str, target: str, key: str) -> str:
    if not text:
        return ""
    base = "https://api-free.deepl.com/v2/translate" if key.endswith(":fx") else "https://api.deepl.com/v2/translate"
    payload = urllib.parse.urlencode({"text": text, "source_lang": "EN", "target_lang": target}).encode()
    request = urllib.request.Request(
        base, data=payload,
        headers={"Authorization": f"DeepL-Auth-Key {key}", "Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        data = json.loads(response.read().decode("utf-8"))
    return data["translations"][0]["text"]


def main():
    key = os.getenv("DEEPL_AUTH_KEY")
    if not key:
        sys.exit("Set DEEPL_AUTH_KEY in the backend environment before running this script.")
    with get_connection() as conn:
        products = conn.execute("SELECT id, name, COALESCE(description, '') AS description, COALESCE(category, '') AS category FROM public.products WHERE active = TRUE ORDER BY id").fetchall()
        print(f"Translating {len(products)} active products into {len(LANGUAGES)} languages.")
        for index, product in enumerate(products, start=1):
            product_id = product["id"]
            source_texts = [product["name"], product["description"], product["category"]]
            source_hash = hashlib.sha256("\\0".join(source_texts).encode("utf-8")).hexdigest()
            for code, deepl_code in LANGUAGES.items():
                existing = conn.execute("SELECT source_hash FROM public.product_translations WHERE product_id=%s AND language_code=%s", (product_id, code)).fetchone()
                if existing and existing["source_hash"] == source_hash:
                    continue
                translated = [translate(value, deepl_code, key) if value else "" for value in source_texts]
                conn.execute(
                    """INSERT INTO public.product_translations
                       (product_id, language_code, name, description, category_name, translation_source, reviewed, source_hash, updated_at)
                       VALUES (%s,%s,%s,%s,%s,'deepl',FALSE,%s,NOW())
                       ON CONFLICT (product_id, language_code) DO UPDATE SET
                         name=EXCLUDED.name, description=EXCLUDED.description,
                         category_name=EXCLUDED.category_name, translation_source='deepl',
                         reviewed=FALSE, source_hash=EXCLUDED.source_hash, updated_at=NOW()""",
                    (product_id, code, translated[0], translated[1], translated[2] or None, source_hash),
                )
            if index % 10 == 0:
                print(f"Processed {index}/{len(products)} products")
        conn.commit()
    print("Done. Translations are saved but remain unreviewed, so the storefront will keep showing the original text until reviewed=TRUE.")

if __name__ == "__main__":
    main()
