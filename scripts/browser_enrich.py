#!/usr/bin/env python3
"""
Browser Enrich — MR Agentes
============================
Script complementario a publish_daily.py.
Lee _browser_enrich.json (generado por --browser-enrich), itera sobre las URLs
de artículos fuente, y navega con browser tool para extraer contenido real.

Uso desde el agente:
  1. python3 scripts/publish_daily.py --browser-enrich
     → genera scripts/_browser_enrich.json y la nota .md base
  2. El agente toma el JSON, navega cada URL con browser,
     extrae contenido, y corre este script para actualizar la nota.
  3. python3 scripts/browser_enrich.py --update ruta/a/la/nota.md

Modo CLI manual (si no se usa browser tool):
  python3 scripts/browser_enrich.py --enrich-file scripts/_browser_enrich.json
  → navega con requests+headers forzados e intenta extraer contenido.
"""

import os
import sys
import json
import re
import html
import urllib.request
import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(BASE_DIR, "scripts")
CONTENT_DIR = os.path.join(BASE_DIR, "content", "notas")
ENRICH_FILE = os.path.join(SCRIPTS_DIR, "_browser_enrich.json")
TRENDS_FILE = os.path.join(SCRIPTS_DIR, "_last_trends.json")


def fetch_with_browser_headers(url, timeout=30, max_chars=5000):
    """Descargar artículo con headers de browser real.
    Versión mejorada que incluye cookies y manejo de redirects."""
    headers = {
        "User-Agent": ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"),
        "Accept": ("text/html,application/xhtml+xml,application/xml;q=0.9,"
                   "image/avif,image/webp,image/apng,*/*;q=0.8"),
        "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
    }

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            # Detectar encoding
            ct = resp.headers.get('Content-Type', '')
            enc = 'utf-8'
            if 'charset=' in ct:
                enc = ct.split('charset=')[-1].split(';')[0].strip().lower()
            try:
                raw = raw.decode(enc, errors='replace')
            except:
                raw = raw.decode('utf-8', errors='replace')

        # Extraer texto del HTML
        text = re.sub(r'<script[^>]*>.*?</script>', '', raw, flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
        text = re.sub(r'<header[^>]*>.*?</header>', '', text, flags=re.DOTALL)
        text = re.sub(r'<footer[^>]*>.*?</footer>', '', text, flags=re.DOTALL)
        text = re.sub(r'<nav[^>]*>.*?</nav>', '', text, flags=re.DOTALL)
        # Remover comentarios HTML
        text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = html.unescape(text)
        text = re.sub(r'\s+', ' ', text).strip()
        if len(text) > max_chars:
            text = text[:max_chars]
        return text
    except Exception as e:
        print(f"  ⚠️  Error descargando {url[:80]}: {e}")
        return None


def extract_meaningful_paragraphs(text, min_len=40):
    """Extraer párrafos significativos del texto HTML crudo."""
    if not text:
        return []
    # Boilerplate a filtrar
    nav_kw = ['cookie', 'suscrib', 'newsletter', 'publicidad', 'derechos reservados',
              'todos los derechos', 'compartir', 'facebook', 'twitter', 'instagram',
              'linkedin', 'tiktok', 'menú', 'navegación', 'buscar', 'inicio',
              'términos y condiciones', 'política de privacidad', 'acerca de',
              'nota relacionada', 'noticias relacionadas', 'sponsor', 'publicidad',
              'seguí leyendo', 'leé también', 'últimas noticias', 'más leídas']

    # Dividir en oraciones
    sentences = re.split(r'(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚ\"\'“])', text)

    meaningful = []
    for s in sentences:
        s = s.strip()
        if len(s) < min_len:
            continue
        if any(kw in s.lower() for kw in nav_kw):
            continue
        # Quedarse con contenido con verbo o información sustantiva
        substantive = ['es', 'son', 'está', 'están', 'tiene', 'tienen', 'puede',
                       'debe', 'hace', '%', 'millones', 'empresa', 'sistema',
                       'datos', 'modelo', 'tecnología', 'inteligencia', 'según',
                       'explica', 'dice', 'afirma', 'estudio', 'investigación',
                       'cambio', 'transformación', 'innovación', 'argentina',
                       'mercado', 'cliente', 'productividad']
        if any(m in s.lower() for m in substantive):
            meaningful.append(s)

    if len(meaningful) < 3:
        # Fallback: solo filtrar por longitud
        meaningful = [s.strip() for s in sentences 
                      if len(s.strip()) > 50 
                      and not any(kw in s.lower() for kw in nav_kw)]

    return meaningful


def parse_enrich_file(enrich_path=ENRICH_FILE):
    """Leer el archivo de enriquecimiento."""
    if not os.path.exists(enrich_path):
        print(f"❌ No se encuentra {enrich_path}")
        print("   Ejecutá primero: python3 scripts/publish_daily.py --browser-enrich")
        return None
    with open(enrich_path, encoding='utf-8') as f:
        return json.load(f)


def enrich_trends_from_http(trends):
    """Intentar enriquecer trends descargando con headers de browser real.
    Retorna lista de dicts con: title, source, url, content, paragraphs.
    Los trends que no se puedan descargar se marcan como 'unreachable'."""
    enriched = []
    for trend in trends:
        url = trend.get('url', '')
        title = trend.get('title', '')
        source = trend.get('source', '')

        # Resolver URL de Google News si es necesario
        resolved_url = url
        if 'news.google.com/rss/articles' in url:
            try:
                req = urllib.request.Request(url, method='HEAD')
                req.add_header('User-Agent',
                    'Mozilla/5.0 (compatible; MR-Agentes-Bot/1.0)')
                class NoRedirect(urllib.request.HTTPRedirectHandler):
                    def redirect_request(self, req, fp, code, msg, headers, newurl):
                        return None
                opener = urllib.request.build_opener(NoRedirect)
                with opener.open(req, timeout=10) as resp:
                    if resp.status in (301, 302, 303, 307, 308):
                        loc = resp.headers.get('Location', '')
                        if loc.startswith('http'):
                            resolved_url = loc
            except:
                pass

        print(f"  📥 Intentando: {source} — {title[:60]}...")
        text = fetch_with_browser_headers(resolved_url)

        if text:
            paragraphs = extract_meaningful_paragraphs(text)
            print(f"    ✅ {len(paragraphs)} párrafos ({len(text)} chars)")
            enriched.append({
                'title': title,
                'source': source,
                'url': url,
                'resolved_url': resolved_url,
                'content': text,
                'paragraphs': paragraphs,
                'status': 'ok',
            })
        else:
            print(f"    ❌ No se pudo obtener contenido")
            enriched.append({
                'title': title,
                'source': source,
                'url': url,
                'resolved_url': resolved_url,
                'content': '',
                'paragraphs': [],
                'status': 'unreachable',
            })

    return enriched


def update_nota_with_enriched(enriched_data, nota_filepath=None):
    """Actualizar el archivo .md de la nota con el contenido enriquecido.
    Toma el contenido real de cada artículo y lo inserta en la nota,
    reemplazando los placeholders de análisis genérico."""
    # Leer enrich data
    if isinstance(enriched_data, str):
        with open(enriched_data, encoding='utf-8') as f:
            enrich = json.load(f)
    else:
        enrich = enriched_data

    nota_file = nota_filepath
    if not nota_file:
        # Buscar por nombre en enrich data
        nota_name = enrich.get('nota_file', '')
        if nota_name:
            nota_file = os.path.join(CONTENT_DIR, nota_name)

    if not nota_file or not os.path.exists(nota_file):
        print(f"❌ No se encuentra la nota: {nota_file}")
        return False

    print(f"  📝 Actualizando nota: {nota_file}")
    
    with open(nota_file, encoding='utf-8') as f:
        nota_content = f.read()

    trends = enrich.get('trends', [])

    # Para cada artículo en la nota, buscar si tenemos contenido enriquecido
    for trend in trends:
        title = trend.get('title', '')
        source = trend.get('source', '')
        url = trend.get('url', '')

        # Buscar si hay párrafos enriquecidos
        enriched_pars = trend.get('paragraphs', [])
        content_raw = trend.get('content', '')
        
        if not enriched_pars:
            continue

        # Generar reemplazo con contenido real
        # Tomar 2-3 párrafos significativos
        import random
        random.shuffle(enriched_pars)
        selected = enriched_pars[:min(3, len(enriched_pars))]
        
        enriched_text_parts = []
        for i, par in enumerate(selected):
            par = par.strip()
            if len(par) > 300:
                par = par[:297].rsplit(' ', 1)[0] + '...'
            if i == 0:
                enriched_text_parts.append(
                    f"Según el reportaje de {source}, {par[0].lower()}{par[1:]}"
                )
            else:
                enriched_text_parts.append(
                    f"Además, el artículo señala que {par[0].lower()}{par[1:]}"
                )

        enriched_text = '\n\n'.join(enriched_text_parts)
        enriched_text += (
            f"\n\n*Contenido extraído directamente del artículo de {source}.*"
        )

        # Reemplazar el bloque de análisis en la nota
        # Buscar desde el título del artículo hasta el siguiente título o ---
        # Pattern: ### N. Title \n *Source* \n > quote \n \n analysis \n \n *Análisis* \n \n *En línea...* \n \n [link]
        pattern_start = f"### {trends.index(trend) + 1}. {title}" if trends.index(trend) < 3 else title
        
        # Si reemplazamos el quote + analysis, buscar el patrón
        # > Artículo sobre...\n\n analysis \n\n *Análisis: MR*
        old_quote_pattern = r'(> [^\n]+\n\n).*?(\*Análisis(?: de MR|: MR)[^*]+\*)'
        new_analysis = f"> {selected[0][:200] if selected else 'Artículo analizado'}\n\n{enriched_text}"

        # Reemplazo simple del bloque cita+análisis
        # Buscar el bloque específico de este artículo
        lines = nota_content.split('\n')
        new_lines = []
        in_target = False
        replaced = False

        for i, line in enumerate(lines):
            # Detectar inicio del análisis de este artículo
            if (not replaced and 
                line.startswith(f'###') and 
                f'{title[:40]}' in line and
                trends.index(trend) < len(trends) and
                not in_target):
                in_target = True
                new_lines.append(line)
                continue

            if in_target:
                # Saltar la línea de fuente
                if line.startswith('*Fuente:'):
                    new_lines.append(line)
                    continue
                # Saltar línea de cita > 
                if line.startswith('> '):
                    continue
                # Si llegamos al final del bloque (otro ###, ---, o link 🔗)
                if (line.startswith('###') or line.startswith('---') or 
                    line.startswith('🔗') or line.startswith('[Ver artículo')):
                    # Insertar el análisis enriquecido antes de continuar
                    if selected:
                        quote = selected[0].strip()
                        if len(quote) > 250:
                            quote = quote[:247].rsplit(' ', 1)[0] + '...'
                        new_lines.append(f'> {quote}')
                        new_lines.append('')
                        new_lines.append(enriched_text)
                    new_lines.append('')
                    new_lines.append(line)
                    in_target = False
                    replaced = True
                    continue
                # Saltar líneas del análisis viejo
                if (line.startswith('*Análisis:') or 
                    line.startswith('*Análisis de') or
                    line.startswith('*Este artículo') or
                    line.startswith('*En línea') or
                    line.strip() == '' and 
                    any(l.startswith('*') for l in lines[i:i+3])):
                    continue
                # Si encontramos un link que no es 🔗, puede ser parte del análisis
                if 'Artículo original' in line or '🔗' in line:
                    new_lines.append(line)
                    in_target = False
                    replaced = True
                    continue
            
            if not in_target:
                new_lines.append(line)

        nota_content = '\n'.join(new_lines)

    # Guardar la nota actualizada
    with open(nota_file, 'w', encoding='utf-8') as f:
        f.write(nota_content)

    print(f"✅ Nota actualizada: {nota_file}")
    return True


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Enriquecer nota web con contenido real de artículos")
    parser.add_argument("--enrich-file", type=str, default=ENRICH_FILE,
                        help=f"JSON de enriquecimiento (default: {ENRICH_FILE})")
    parser.add_argument("--update", type=str, default="",
                        help="Actualizar nota .md específica")
    parser.add_argument("--dry-run", action="store_true",
                        help="Mostrar qué se haría sin modificar archivos")
    args = parser.parse_args()

    # Cargar archivo de enriquecimiento
    enrich = parse_enrich_file(args.enrich_file)
    if not enrich:
        return 1

    print(f"📰 Nota: {enrich.get('title', 'Sin título')}")
    print(f"📄 Archivo: {enrich.get('nota_file', 'No especificado')}")

    trends = enrich.get('trends', [])
    print(f"📊 {len(trends)} artículos a enriquecer:")
    for t in trends:
        print(f"   • {t.get('source', '?')}: {t.get('title', '?')[:70]}...")

    # Intentar descargar contenido de cada artículo
    print("\n🔍 Descargando artículos...")
    enriched_trends = enrich_trends_from_http(trends)

    # Actualizar enrich data con resultados
    enrich['trends'] = enriched_trends
    enrich['enriched_at'] = datetime.datetime.now().isoformat()

    if not args.dry_run:
        # Guardar JSON enriquecido
        enrich_out = args.enrich_file.replace('.json', '_enriched.json')
        with open(enrich_out, 'w', encoding='utf-8') as f:
            json.dump(enrich, f, ensure_ascii=False, indent=2)
        print(f"\n💾 Enriquecimiento guardado: {enrich_out}")

        # Actualizar la nota si se especificó
        nota_file = args.update or enrich.get('nota_file', '')
        if nota_file:
            nota_path = os.path.join(CONTENT_DIR, nota_file) \
                if not os.path.isabs(nota_file) else nota_file
            if os.path.exists(nota_path):
                update_nota_with_enriched(enrich, nota_path)
            else:
                print(f"⚠️  No se encuentra {nota_path}")
    else:
        print("\n🏁 Dry run: no se modificaron archivos")
        statuses = [t['status'] for t in enriched_trends]
        ok = sum(1 for s in statuses if s == 'ok')
        unreachable = sum(1 for s in statuses if s == 'unreachable')
        print(f"   {ok} enriquecidos, {unreachable} no disponibles")

    return 0


if __name__ == "__main__":
    sys.exit(main())
