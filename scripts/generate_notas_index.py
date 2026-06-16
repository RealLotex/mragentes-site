#!/usr/bin/env python3
"""Genera /notas/index.json con lista de notas para el Service Worker."""
import os, json, re

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTENT_DIR = os.path.join(BASE_DIR, "content", "notas")

def parse_front_matter(content):
    m = re.search(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
    if not m:
        return {}
    front = m.group(1)
    result = {}
    for key in ['title', 'date', 'description']:
        # Try quoted string
        p = re.search(r'^' + key + r':\s*"(.+?)"', front, re.MULTILINE)
        if p:
            result[key] = p.group(1)
        else:
            # Try plain string
            p = re.search(r'^' + key + r':\s*(.+)$', front, re.MULTILINE)
            if p:
                result[key] = p.group(1).strip().strip("'").strip('"')
    return result

def slugify(text):
    text = text.lower().strip()
    text = re.sub(r'[^\w\sáéíóúñ-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    return text

def main():
    notas = []
    if not os.path.exists(CONTENT_DIR):
        print("No content/notas dir")
        return

    for fname in sorted(os.listdir(CONTENT_DIR)):
        if not fname.endswith(".md") or fname == "_index.md":
            continue
        fpath = os.path.join(CONTENT_DIR, fname)
        with open(fpath, encoding="utf-8") as f:
            content = f.read()

        meta = parse_front_matter(content)
        title = meta.get('title', '')
        date = meta.get('date', '')[:10]
        desc = meta.get('description', '')[:200]

        if not title:
            continue

        # Build URL from date + slug
        slug = slugify(title)
        date_part = fname[:10] if fname[:10].isdigit() else date[:10]
        url = f"/notas/{date_part}-{slug}/"

        notas.append({
            "title": title,
            "date": date,
            "description": desc,
            "url": url,
        })

    # Write to static/notas/ for Hugo to serve
    static_dir = os.path.join(BASE_DIR, "static", "notas")
    os.makedirs(static_dir, exist_ok=True)
    with open(os.path.join(static_dir, "index.json"), "w", encoding="utf-8") as f:
        json.dump(notas, f, ensure_ascii=False, indent=2)
    print(f"✅ index.json generado con {len(notas)} notas en static/notas/")

if __name__ == "__main__":
    main()
