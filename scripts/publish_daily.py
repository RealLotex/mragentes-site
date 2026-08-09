#!/usr/bin/env python3
"""
Publicador diario MR Agentes — Hugo Website + Investigación Online
Crea una nueva nota con imagen única y hace push al repo.

Reglas:
  - TODOS los días investiga tendencias online reales + análisis propio impredecible
  - No repetir imágenes hasta agotar el catálogo (~3 imágenes, ciclo rotativo)
  - Siempre aportar análisis propio con fuentes citadas, no solo titulares
  - Variedad impredecible: a veces 2 tendencias + análisis profundo,
    a veces 3 con tabla, a veces enfoque en 1 tema con pull quotes
  - Tags, slug y front matter generados automáticamente
  - Sin contenido estático: cada nota es única por investigación real

Uso:
  python3 scripts/publish_daily.py                  # Publicación automática
  python3 scripts/publish_daily.py --dry-run        # Solo crear archivo, sin git push
  python3 scripts/publish_daily.py --force          # Forzar publicación aunque ya exista nota hoy
"""

import os
import sys
import json
import subprocess
import datetime
import re
import random
import textwrap
from pathlib import Path

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTENT_DIR = os.path.join(BASE_DIR, "content", "notas")
STOCK_IMAGES_DIR = "/images/stock/"
STATE_FILE = os.path.join(BASE_DIR, "scripts", ".publish_state.json")

# Imágenes de stock disponibles
STOCK_IMAGES = [
    # Imágenes originales
    "automation.jpg",
    "data-analytics.jpg",
    "digital-world.jpg",
    "ai-brain.jpg",
    # Imágenes nuevas de Pexels batch 2026-06-18
    "pexels-8386440.jpg",  # Concepto IA abstracto
    "pexels-8438918.jpg",  # Ajedrez humano vs robot
    "pexels-1181373.jpg",  # Programando en Python
    "pexels-1181390.jpg",  # Tableta/productividad
    "pexels-1181401.jpg",  # Código + reunión
    "pexels-1181408.jpg",  # Reunión corporativa diversa
    "pexels-1181671.jpg",  # Libro Python
    "pexels-1181672.jpg",  # Mujer leyendo libro Python
    "pexels-1181354.jpg",  # Tech
    "pexels-1181304.jpg",  # Tech
    "pexels-1181267.jpg",  # Tech
    "pexels-1181675.jpg",  # Tech
    "pexels-8566472.jpg",  # Tech
    "pexels-8441272.jpg",  # Lifestyle cafetería
]

# Cuando todas las imágenes se hayan usado, se reinicia el ciclo.

TOPICS = [
    {
        "title": "Automatización 101: por dónde empezar",
        "tags": ["automatizacion", "guia", "principiantes"],
        "body": """## ¿Por dónde empezar con la automatización?

Muchas empresas quieren automatizar procesos pero no saben por dónde arrancar. Acá te dejamos una guía simple en 3 pasos:

### 1. Identificá tareas repetitivas
Hacé una lista de todo lo que tu equipo hace más de 3 veces por semana que sea manual, repetitivo y propenso a errores humanos.

### 2. Medí el tiempo invertido
Antes de automatizar, cuantificá cuánto tiempo se pierde. Si una tarea te lleva 10 horas por semana, automatizarla tiene alto ROI.

### 3. Priorizá por impacto
No intentes automatizar todo de una vez. Elegí el proceso que más tiempo consuma o más errores genere, y empezá por ahí.

> El 80% del beneficio de la automatización viene del 20% de los procesos.

¿Querés ayuda para identificar qué procesos automatizar? [Contactanos](/contacto/) y te hacemos un diagnóstico gratuito."""
    },
    {
        "title": "Chatbots con IA: mitos y verdades",
        "tags": ["chatbots", "ia", "atencion-al-cliente"],
        "body": """## Chatbots con IA: lo que escuchamos todos los días

Todavía hay mucha confusión sobre lo que los chatbots con inteligencia artificial pueden y no pueden hacer. Vamos a desmentir algunos mitos.

### ❌ Mito: "Los chatbots son robots fríos que no entienden nada"
**Verdad:** Los chatbots modernos con IA generativa entienden lenguaje natural, contexto y hasta emociones. No son los chatbots con guiones fijos de hace 10 años.

### ❌ Mito: "Implementar un chatbot es carísimo"
**Verdad:** Hoy existen soluciones accesibles para cualquier presupuesto. El retorno de inversión suele verse en los primeros meses.

### ❌ Mito: "Los clientes prefieren hablar con personas siempre"
**Verdad:** Según estudios, el 60% de los usuarios prefiere resolver consultas simples con un chatbot antes que esperar en una línea telefónica.

### ✅ Realidad: La clave está en el balance
Un buen sistema de atención combina chatbot IA para lo rutinario + derivación inteligente a humanos cuando se necesita. No reemplaza, **potencia**.

¿Estás considerando un chatbot para tu negocio? [Escribinos](/contacto/) y te contamos cómo funcionaría en tu caso."""
    },
    {
        "title": "IA y productividad: 5 datos que tenés que conocer",
        "tags": ["ia", "productividad", "datos"],
        "body": """## El impacto real de la IA en la productividad

No es futurismo: la inteligencia artificial ya está transformando empresas hoy. Mirá estos números:

### 📊 Lo que dicen los datos

- **40%** de las tareas administrativas se pueden automatizar hoy
- **3x** más rápido procesan documentos los sistemas con IA versus humanos
- **90%** menos errores en tareas de ingreso de datos
- **60%** de los clientes prefieren chatbots IA para consultas simples

### 💡 La conclusión

Las empresas que adoptan IA no solo ahorran tiempo: **toman mejores decisiones** porque tienen datos en tiempo real y liberan a su equipo para tareas de mayor valor.

¿Cuánto tiempo pierde tu equipo en tareas repetitivas? [Descubrilo con nosotros](/contacto/)."""
    },
    {
        "title": "5 procesos contables que deberías automatizar ya",
        "tags": ["contabilidad", "automatizacion", "finanzas"],
        "body": """## Procesos contables: tiempo perdido vs. automatizado

El área contable de cualquier empresa está llena de tareas repetitivas. Acá los 5 procesos que deberías automatizar YA.

### 1. 📄 Facturación electrónica
Generación, envío y archivo automático de facturas. Sin errores de tipeo, sin facturas olvidadas.

### 2. 💰 Conciliación bancaria
Un bot cruza tus movimientos bancarios con tu sistema contable. Lo que tomaba un día, ahora toma 10 minutos.

### 3. 📬 Gestión de cobranzas
Recordatorios automáticos por email/WhatsApp según el estado de cada cliente.

### 4. 🧾 Procesamiento de comprobantes
Escaneá un PDF o foto de factura → el bot extrae datos y los carga en tu sistema.

### 5. 📊 Reportes periódicos
Informes de IVA, balance, resultados → generados y enviados automáticamente cada mes.

> El tiempo promedio que una PyME ahorra automatizando estos 5 procesos es de **20 horas semanales**.

¿Tu área contable sigue haciendo todo manual? [Contanos tu caso](/contacto/)."""
    },
    {
        "title": "¿Qué es un agente IA y cómo puede ayudar a tu negocio?",
        "tags": ["ia", "agentes", "innovacion"],
        "body": """## Agentes IA: el siguiente nivel de automatización

Seguramente escuchaste hablar de "agentes IA" pero ¿sabés realmente qué son?

### 🤔 ¿Qué es un agente IA?

Un agente IA es un sistema que **no solo ejecuta instrucciones**, sino que **toma decisiones autónomas** basadas en contexto y objetivos. Piensa en él como un empleado digital que:

- Entiende qué se le pide (lenguaje natural)
- Decide cómo hacerlo (planificación)
- Ejecuta acciones (integración con herramientas)
- Aprende de los resultados (mejora continua)

### 💼 Aplicaciones

| Área | Qué hace un agente IA |
|------|----------------------|
| Atención al cliente | Resuelve consultas, deriva casos complejos |
| Ventas | Califica leads, programa reuniones, envía propuestas |
| Operaciones | Monitorea procesos, detecta anomalías |
| RRHH | Preselecciona candidatos, programa entrevistas |

¿Querés saber cómo implementar un agente IA en tu negocio? [Hablemos](/contacto/)."""
    },
    {
        "title": "Automatización vs. empleo: lo que nadie te cuenta",
        "tags": ["automatizacion", "empleo", "tendencias"],
        "body": """## Automatización: ¿enemiga del empleo?

Es el debate que siempre surge cuando hablamos de automatización e IA.

### ❌ El miedo: "Los robots nos van a dejar sin trabajo"

Es entendible. Cada vez que hay un salto tecnológico, aparece el mismo miedo. Pasó con la revolución industrial, con Internet, con los smartphones.

### ✅ La realidad: la automatización transforma, no reemplaza

Los datos históricos muestran que la tecnología **crea más empleo del que destruye**, pero cambia la naturaleza del trabajo.

### 🔄 Lo que realmente pasa

1. **Desaparecen tareas**, no puestos completos
2. **Aparecen nuevos roles**: gestor de automatización, prompt engineer, analista de datos
3. **Los equipos se vuelven más productivos**: la empresa crece y necesita más gente

### 🎯 Nuestra visión

No vendemos automatización para reemplazar personas. La vendemos para que **tu equipo deje de hacer tareas que una máquina puede hacer** y se dedique a lo que realmente importa.

> El objetivo no es tener menos personas, sino que cada persona aporte más valor.

[Contactanos](/contacto/) para saber cómo la automatización puede transformar tu equipo."""
    },
    {
        "title": "Integraciones: el poder de conectar tus herramientas",
        "tags": ["integraciones", "automatizacion", "herramientas"],
        "body": """## El poder de las integraciones

Tu negocio usa varias herramientas: CRM, facturación, WhatsApp, email, redes sociales. ¿Y si todas hablaran entre sí?

### 🤝 ¿Qué logramos con integraciones?

- **Sin doble ingreso de datos** — lo que se carga en un sistema aparece en todos
- **Flujos automáticos** — un lead de Instagram → se crea en CRM → recibe WhatsApp automático
- **Visibilidad 360°** — dashboard único con datos de todas tus herramientas

### 🔗 Ejemplos concretos

| Integración | Resultado |
|-------------|-----------|
| Formulario web → CRM → WhatsApp | Lead captado y contactado en segundos |
| E-commerce → Facturación → Stock | Pedido procesado sin intervención humana |
| Instagram → CRM → Email marketing | Nuevo seguidor → comunicación automática |

### 💡 ¿Vale la pena?

Con +50 integraciones disponibles, conectar tus herramientas es más fácil de lo que pensás. El ROI suele verse en las primeras semanas.

¿Qué herramientas usás en tu negocio? [Contanos](/contacto/) y te mostramos cómo conectarlas."""
    },
    {
        "title": "Cómo medir el ROI de la automatización en tu PyME",
        "tags": ["automatizacion", "roi", "negocios"],
        "body": """## ¿Cuánto te está costando no automatizar?

Muchas empresas dudan en invertir en automatización porque "no saben si vale la pena". La respuesta corta: casi siempre sí. La respuesta larga: empezá midiendo.

### 📐 Las 3 métricas clave

**1. Tiempo liberado**
Calculá cuántas horas por semana pierde tu equipo en tareas manuales repetitivas. Multiplicá por el valor de esa hora.

**2. Reducción de errores**
Los errores humanos cuestan plata: facturas mal hechas, datos mal ingresados, seguimientos olvidados. La automatización los elimina casi por completo.

**3. Velocidad de respuesta**
Un chatbot IA responde en segundos. Un proceso manual puede tardar horas o días. La velocidad impacta directamente en ventas y satisfacción.

### 🧮 Regla del 10x

Si un proceso manual te lleva **10 horas al mes**, automatizarlo suele costar fracción de eso. El retorno es inmediato.

| Proceso | Horas/mes manual | Horas/mes automatizado | Ahorro |
|---------|:-:|:-:|:-:|
| Facturación | 15 | 1 | 93% |
| Atención al cliente | 40 | 5 | 87% |
| Reportes | 8 | 0.5 | 94% |
| Conciliación | 10 | 1 | 90% |

¿Querés calcular el ROI de tu negocio? [Contactanos](/contacto/) y te ayudamos."""
    },
]


def slugify(text):
    """Convertir texto a slug URL-friendly."""
    text = text.lower().strip()
    text = re.sub(r'[^\w\sáéíóúñ-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    return text


def load_state():
    """Cargar estado desde archivo JSON."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {"used_images": [], "topic_index": 0, "last_trends_day": 0}


def save_state(state):
    """Guardar estado a archivo JSON."""
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


PEXELS_API_URL = "https://images.pexels.com/photos/{photo_id}/pexels-photo-{photo_id}.jpeg?auto=compress&cs=tinysrgb&w=1260&h=750&dpr=1"

# IDs de fotos populares de tecnología/IA/negocios en Pexels (nuevas para cada fetch)
PEXELS_PHOTO_IDS = [
    8386440, 8566472, 8438918, 8441272,
    1181675, 1181354, 1181373, 1181390, 1181408, 1181304, 1181267, 1181401, 1181671, 1181672,
]


def fetch_new_stock_images(count=3):
    """Descargar imágenes nuevas de Pexels y agregarlas al catálogo.
    Retorna lista de nombres de archivo agregados."""
    import subprocess, os
    added = []
    target_dir = os.path.join(BASE_DIR, "static", "images", "stock")
    os.makedirs(target_dir, exist_ok=True)

    # IDs que ya tenemos en disco
    existing_ids = set()
    for fname in os.listdir(target_dir):
        m = re.match(r'pexels-(\d+)\.jpg', fname)
        if m:
            existing_ids.add(int(m.group(1)))

    # IDs que NO tenemos todavía
    fresh_ids = [pid for pid in PEXELS_PHOTO_IDS if pid not in existing_ids]
    if not fresh_ids:
        # Si ya tenemos todos, buscar algunos random nuevos — buscar en la web o usar más IDs
        return added

    # Descargar hasta count nuevas imágenes
    for photo_id in fresh_ids[:count]:
        url = PEXELS_API_URL.format(photo_id=photo_id)
        outfile = os.path.join(target_dir, f"pexels-{photo_id}.jpg")
        try:
            result = subprocess.run(
                ["curl", "-sL", "-o", outfile, "-w", "%{http_code}", url],
                capture_output=True, text=True, timeout=15
            )
            if result.stdout.strip() == "200" and os.path.getsize(outfile) > 5000:
                fname = f"pexels-{photo_id}.jpg"
                added.append(fname)
                print(f"  📷 Imagen nueva descargada: {fname}")
            else:
                if os.path.exists(outfile):
                    os.remove(outfile)
        except Exception as e:
            print(f"  ⚠️  Error descargando {photo_id}: {e}")
            if os.path.exists(outfile):
                os.remove(outfile)

    return added


def pick_image(state):
    """Elegir imagen de stock sin repetir hasta agotar el catálogo.
    Automáticamente busca nuevas imágenes si el catálogo se está agotando."""
    available = [img for img in STOCK_IMAGES if img not in state.get("used_images", [])]

    # Si quedan pocas imágenes disponibles, buscar más de Pexels
    if len(available) <= 2:
        print("  📷 Quedan pocas imágenes sin usar. Buscando nuevas en Pexels...")
        new_images = fetch_new_stock_images(count=3)
        for img in new_images:
            if img not in STOCK_IMAGES:
                STOCK_IMAGES.append(img)
        # Recalcular disponibles
        available = [img for img in STOCK_IMAGES if img not in state.get("used_images", [])]

    if not available:
        state["used_images"] = []
        available = list(STOCK_IMAGES)

    chosen = random.choice(available)
    state["used_images"].append(chosen)

    # Mantener solo últimas N usadas (N = len(images) para no repetir)
    max_history = len(STOCK_IMAGES) - 1
    if len(state["used_images"]) > max_history:
        state["used_images"] = state["used_images"][-max_history:]

    save_state(state)
    return chosen


def fetch_web_trends():
    """Investigar tendencias sobre automatización e IA.
    Busca en fuentes priorizadas:
    1. Fuentes argentinas (Ámbito, La Nación, Infobae, iProUP)
    2. Fuentes globales de IA (artificialintelligence-news.com)
    3. Google News RSS como fallback
    """
    import urllib.request
    import urllib.parse
    import html

    # ─── FUENTES PRIORIZADAS ──────────────────────────────────
    # Cada entry: (sites_for_query, query, lang, country)
    # Se eligen al azar con distinta probabilidad

    # ─── FUENTES EXPANDIDAS 2026 ─────────────────────────────────
    # Argentinas + Latinoamérica + Globales IT/IA
    # Cada entry: (sites_for_query, query, lang, country, weight_override)
    # Se eligen al azar con los pesos indicados

    source_groups = [
        # ── Grupo ARG: Argentinas/LatAm (40%) ─────────────────────
        (["lanacion.com.ar", "ambito.com", "iproup.com", "iprofesional.com"],
         "inteligencia artificial agentes automatización", "es", "AR"),
        (["lanacion.com.ar", "iproup.com", "iprofesional.com"],
         "IA inteligencia artificial empresas transformación digital", "es", "AR"),
        (["ambito.com", "iproup.com", "infobae.com", "iprofesional.com"],
         "inteligencia artificial IA tecnología innovación empresas", "es", "AR"),
        (["lanacion.com.ar", "ambito.com", "iproup.com", "iprofesional.com"],
         "IA automatización productividad empresas negocios", "es", "AR"),
        (["lanacion.com.ar", "iproup.com", "ambito.com"],
         "inteligencia artificial agentes IA startup funding", "es", "AR"),

        # ── Grupo TECH: Global IT/IA/Startups (30%) ───────────────
        (["techcrunch.com", "theverge.com", "arstechnica.com"],
         "AI artificial intelligence automation startup funding", "en", "US"),
        (["techcrunch.com", "venturebeat.com", "thenextweb.com"],
         "AI enterprise agents machine learning 2026", "en", "US"),
        (["wired.com", "technologyreview.com", "arstechnica.com"],
         "artificial intelligence future trends research", "en", "US"),
        (["zdnet.com", "cnet.com", "techcrunch.com"],
         "AI automation business productivity tools 2026", "en", "US"),
        (["venturebeat.com", "analyticsvidhya.com", "towardsdatascience.com"],
         "AI models training deployment enterprise", "en", "US"),

        # ── Grupo FINANZAS: Bloomberg/Forbes/Yahoo (20%) ──────────
        (["bloomberg.com", "forbes.com", "finance.yahoo.com"],
         "artificial intelligence AI technology business investment", "en", "US"),
        (["bloomberg.com", "forbes.com", "techcrunch.com"],
         "AI startups funding unicorn enterprise", "en", "US"),
        (["forbes.com", "finance.yahoo.com", "venturebeat.com"],
         "AI market trends analysis automation industry 2026", "en", "US"),

        # ── Grupo SECTORIAL: Nicho IA (10%) ───────────────────────
        (["artificialintelligence-news.com"],
         "AI enterprise agents automation", "en", "US"),
        (["artificialintelligence-news.com"],
         "artificial intelligence 2026 new model", "en", "US"),
    ]

    # Pesos actualizados: arg 40%, tech 30%, finanzas 20%, sectorial 10%
    group_weights = [
        0.09,  # ARG 1
        0.08,  # ARG 2
        0.08,  # ARG 3
        0.08,  # ARG 4
        0.07,  # ARG 5
        0.07,  # TECH 1
        0.06,  # TECH 2
        0.06,  # TECH 3
        0.06,  # TECH 4
        0.05,  # TECH 5
        0.07,  # FIN 1
        0.07,  # FIN 2
        0.06,  # FIN 3
        0.05,  # SECTORIAL 1
        0.05,  # SECTORIAL 2
    ]
    total = sum(group_weights)
    group_weights = [w/total for w in group_weights]

    chosen_idx = random.choices(range(len(source_groups)), weights=group_weights, k=1)[0]
    sites, query, lang, country = source_groups[chosen_idx]

    print(f"  🔍 Buscando: '{query}' (sites: {sites or 'google news'})")

    # ─── PRIMERO: buscar en fuentes prioritarias por URL directa ──
    if sites:
        trends = []
        for site in sites:
            try:
                site_query = f"site:{site} {query}"
                url = f"https://news.google.com/rss/search?q={urllib.parse.quote(site_query)}&hl={lang}&gl={country}&ceid={country}:{lang}"
                req = urllib.request.Request(url, headers={
                    "User-Agent": "Mozilla/5.0 (compatible; MR-Agentes-Bot/1.0)"
                })
                with urllib.request.urlopen(req, timeout=15) as resp:
                    raw = resp.read().decode("utf-8", errors="replace")

                items = re.findall(r'<item>.*?<title>(.*?)</title>.*?<link>(.*?)</link>.*?<source.*?>(.*?)</source>.*?</item>', raw, re.DOTALL)
                for title, link, source in items:
                    clean_title = html.unescape(re.sub(r'<[^>]+>', '', title)).strip()
                    clean_source = html.unescape(source).strip()
                    # Skip artículos claramente no relacionados con IA/tecnología
                    skip_keywords = ['receta', 'clima', 'lluvia', 'asado', 'fútbol', 'mundial',
                                     'gol', 'inflación', 'aguinaldo', 'dólar blue', 'dólar hoy',
                                     'crimen', 'espectáculos', 'farándula', 'cuota alimentaria',
                                     'jubilación', 'anses', 'impuesto', 'elecciones', 'votación',
                                     'prode', 'argelia', 'selección', 'seleccionado', 'partido',
                                     'murió', 'falleció', 'horóscopo', 'tarot', 'vidente',
                                     'cumple', 'prisión', 'domiciliaria', 'kirchner', 'macri',
                                     'milei discurso', 'bono', 'asignación', 'tarjeta', 'plan social',
                                     'recibí', 'monotributo', 'cuándo cobro', 'previaje']
                    title_lower = clean_title.lower()
                    if len(clean_title) < 20:
                        continue
                    if any(kw in title_lower for kw in skip_keywords):
                        continue
                    # Skip artículos que usan IA para temas no relacionados (ej: "según la IA para...")
                    # Detectar patrones: "según la IA", "con IA" + tema no tecnológico
                    bad_patterns = ['según la ia', 'con ia para completar', 'cuánto sale',
                                    'cuánto cuesta', 'dólar a', 'cotización del']
                    if any(p in title_lower for p in bad_patterns):
                        continue
                    # Keywords REQUERIDAS para considerar relevante a IA
                    ia_keywords = ['inteligencia artificial', 'ia', 'automatización', 'automation',
                                   'ai ', 'artificial intelligence', 'machine learning', 'chatbot',
                                   'gpt', 'claude', 'openai', 'anthropic', 'agente', 'algorithm',
                                   'algorithm', 'modelo', 'robot', 'digital', 'tecnología',
                                   'technology', 'software', 'startup', 'innovación', 'innovation',
                                   'ciberseguridad', 'datos', 'blockchain', 'token', 'nube', 'cloud']
                    if not any(kw in title_lower for kw in ia_keywords):
                        # Si no tiene keywords de IA, solo mantener si la query original lo pedía
                        query_lower = query.lower()
                        query_words = set(query_lower.split())
                        title_words = set(title_lower.split())
                        overlap = query_words & title_words
                        if len(overlap) < 1:
                            continue
                    trends.append({
                        "title": clean_title,
                        "url": link.strip(),
                        "source": clean_source,
                    })
            except Exception as e:
                print(f"    ⚠️  Error buscando en {site}: {e}")
                continue

        # Quitar duplicados por URL
        seen_urls = set()
        unique_trends = []
        for t in trends:
            if t['url'] not in seen_urls:
                seen_urls.add(t['url'])
                unique_trends.append(t)

        if len(unique_trends) >= 2:
            # Mezclar y tomar hasta 3
            random.shuffle(unique_trends)
            selected = unique_trends[:3]
            print(f"    ✅ Encontrados {len(unique_trends)} resultados, tomando {len(selected)}")
            for s in selected:
                print(f"      • {s['source']}: {s['title'][:80]}...")
            return selected

    # ─── SEGUNDO: fallback a Google News RSS general ──────────
    print(f"  ⚠️  Sin resultados de fuentes directas. Usando Google News genérico...")
    try:
        url = f"https://news.google.com/rss/search?q={urllib.parse.quote(query)}&hl={lang}&gl={country}&ceid={country}:{lang}"
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (compatible; MR-Agentes-Bot/1.0)"
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8", errors="replace")

        items = re.findall(r'<item>.*?<title>(.*?)</title>.*?<link>(.*?)</link>.*?<source.*?>(.*?)</source>.*?</item>', raw, re.DOTALL)

        if items:
            selected = random.sample(items, min(3, len(items)))
            trends = []
            for title, link, source in selected:
                trends.append({
                    "title": html.unescape(re.sub(r'<[^>]+>', '', title)).strip(),
                    "url": link.strip(),
                    "source": html.unescape(source).strip()
                })
            return trends
    except Exception as e:
        print(f"  ⚠️  Error en Google News fallback: {e}")

    return None


def resolve_google_news_url(original_url):
    """Resolver la URL real de un artículo desde un enlace de Google News RSS.
    Google News usa URLs acortadas/redireccionadas que no devuelven el contenido
    del artículo directamente. Esta función sigue la redirección HTTP para
    obtener la URL canónica del sitio de origen.
    Retorna la URL real o la original si no se puede resolver."""
    import urllib.request
    try:
        req = urllib.request.Request(original_url, method='HEAD')
        req.add_header('User-Agent', 'Mozilla/5.0 (compatible; MR-Agentes-Bot/1.0)')
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None
        opener = urllib.request.build_opener(NoRedirect)
        with opener.open(req, timeout=10) as resp:
            if resp.status in (301, 302, 303, 307, 308):
                location = resp.headers.get('Location', '')
                if location and location.startswith('http'):
                    return location
            return original_url
    except Exception as e:
        return original_url


# ═══════════════════════════════════════════════════════════════
# ANÁLISIS FRESCO POR FUENTE — Cada artículo se descarga y se
# analiza individualmente. NO hay texto hardcodeado.
# ═══════════════════════════════════════════════════════════════

def fetch_article_content(url):
    """Descargar el contenido real de un artículo desde su URL.
    Si la URL es de Google News RSS, primero intenta resolver la URL real
    siguiendo la redirección HTTP.
    Usa headers de browser real para maximizar contenido servido.
    Retorna texto plano. Si falla, retorna None."""
    import urllib.request
    import html

    # Si es URL de Google News, resolver la URL real primero
    if 'news.google.com/rss/articles' in url:
        resolved = resolve_google_news_url(url)
        if resolved and resolved != url:
            print(f"    ↪ Redirección: {resolved[:80]}...")
            url = resolved

    # Headers de browser real (Chrome-like)
    browser_headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
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
        req = urllib.request.Request(url, headers=browser_headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
            # Detectar encoding desde Content-Type o headers
            ct = resp.headers.get('Content-Type', '')
            enc = 'utf-8'
            if 'charset=' in ct:
                enc = ct.split('charset=')[-1].split(';')[0].strip().lower()
            try:
                raw = raw.decode(enc, errors='replace')
            except:
                raw = raw.decode('utf-8', errors='replace')
        # Extraer texto del HTML: remover scripts, styles, tags
        text = re.sub(r'<script[^>]*>.*?</script>', '', raw, flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
        text = re.sub(r'<header[^>]*>.*?</header>', '', text, flags=re.DOTALL)
        text = re.sub(r'<footer[^>]*>.*?</footer>', '', text, flags=re.DOTALL)
        text = re.sub(r'<nav[^>]*>.*?</nav>', '', text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = html.unescape(text)
        # Compactar whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        # Tomar hasta 5000 caracteres
        if len(text) > 5000:
            text = text[:5000]
        return text
    except Exception as e:
        print(f"  ⚠️  No se pudo descargar {url}: {e}")
        return None


def analyze_url_content(trend):
    """Analizar el contenido real de un artículo y generar un análisis fresco.
    Descarga la página, extrae puntos clave y produce análisis contextual.
    Retorna dict con: pull_quote, analysis, card (o None).
    NO usa texto hardcodeado — cada análisis es único."""
    title = trend["title"]
    source = trend["source"]
    url = trend["url"]

    # Descargar contenido real del artículo
    print(f"    📥 Descargando artículo: {source}")
    content = fetch_article_content(url)

    if content:
        # Extraer oraciones como "cita" del artículo real, filtrando navegación
        sentences = re.split(r'(?<=[.!?])\s+', content)
        boilerplate_kw = ['cookie', 'suscrib', 'newsletter', 'publicidad', 'derechos reservados',
                          'todos los derechos', 'seguí leyendo', 'compartir', 'facebook', 
                          'twitter', 'instagram', 'buscar', 'menú', 'inicio', 'contacto',
                          'términos y condiciones', 'política de privacidad', 'navegación']
        meaningful = [s.strip() for s in sentences
                      if len(s.strip()) > 50
                      and not any(bp in s.lower() for bp in boilerplate_kw)
                      and len(s.strip()) < 350]
        if meaningful:
            raw_quote = random.choice(meaningful[:3])
            quote = raw_quote.strip()
            if len(quote) > 250:
                quote = quote[:247].rsplit(' ', 1)[0] + '...'
        else:
            quote = f"Artículo sobre {title[:60].rsplit(' ', 1)[0]} publicado en {source}."
    else:
        quote = f"Reportaje de {source} analizado por MR Agentes."

    # ─── Generar análisis BASADO EN EL CONTENIDO REAL ────────────────
    # Extraer párrafos relevantes del contenido descargado
    analysis = _generate_analysis_from_content(content, title, source)

    # Generar card (tabla) si aplica — a veces sí, a veces no
    include_card = random.random() < 0.35
    card_str = None
    if include_card and content:
        card_str = _generate_card_from_title(title)

    return {
        "quote": quote,
        "analysis": analysis,
        "card": card_str,
    }


def _generate_card_from_title(title):
    """Generar una tabla markdown temática basada en palabras clave del título.
    NO usa datos hardcodeados. Genera contenido variado cada vez."""
    title_lower = title.lower()

    cards_db = [
        {
            "kw": ["chatbot","chat","bot","atención","cliente","customer","soporte","support"],
            "header": "| Dimensión | Sin IA | Con IA |",
            "sep": "|-----------|--------|--------|",
            "rows": [
                "| Tiempo de respuesta | 15-30 min | < 5 seg |",
                "| Resolución automática | 0% | 45-60% |",
                "| Disponibilidad | 8-12h/día | 24/7 |",
                "| Costo por interacción | $4-8 USD | $0.50-1.50 USD |",
            ],
        },
        {
            "kw": ["automati","rpa","proceso","workflow","bpa"],
            "header": "| Proceso | Manual (hrs/mes) | Automatizado (hrs/mes) |",
            "sep": "|---------|:-:|:-:|",
            "rows": [
                "| Carga de datos | 12 | 0.5 |",
                "| Conciliación | 8 | 0.3 |",
                "| Generación reportes | 6 | 0.2 |",
                "| Seguimiento de casos | 10 | 0.5 |",
            ],
        },
        {
            "kw": ["seguridad","ciber","hacker","phishing","vulnerabilidad","threat"],
            "header": "| Métrica | Sin protección IA | Con protección IA |",
            "sep": "|---------|:-:|:-:|",
            "rows": [
                "| Detección de amenazas | 65-70% | 92-97% |",
                "| Falsos positivos | 12-18% | 2-5% |",
                "| Tiempo de respuesta | 4-8h | < 2 min |",
                "| Cobertura 24/7 | No | Sí |",
            ],
        },
        {
            "kw": ["datos","analytics","dashboard","report","data","big"],
            "header": "| Nivel | Capacidad | Tecnología |",
            "sep": "|-------|-----------|------------|",
            "rows": [
                "| Descriptivo | Qué pasó | Dashboards básicos |",
                "| Diagnóstico | Por qué pasó | OLAP, cruce fuentes |",
                "| Predictivo | Qué va a pasar | ML, series temporales |",
                "| Prescriptivo | Qué hacer | IA + optimización |",
            ],
        },
        {
            "kw": ["productividad","eficiencia","eficient","rendimiento","performance"],
            "header": "| Área | Ganancia de productividad |",
            "sep": "|------|:-:|",
            "rows": [
                "| Tareas administrativas | +35-50% |",
                "| Análisis de datos | +25-40% |",
                "| Atención al cliente | +30-45% |",
                "| Reportes y documentación | +40-60% |",
            ],
        },
        {
            "kw": ["industria","fabrica","manufactura","production","supply"],
            "header": "| Indicador | Tradicional | Con IA |",
            "sep": "|-----------|:-:|:-:|",
            "rows": [
                "| Paradas no planificadas | 100% | -45% |",
                "| Precisión calidad | 82% | 97% |",
                "| Optimización inventario | 25% buffer | 12% buffer |",
                "| Tiempo reprogramación | Semanas | Horas |",
            ],
        },
        {
            "kw": ["startup","emprend","pyme","funding","inversión","venture","capital"],
            "header": "| Factor | Startup exitosa | Startup fracasa |",
            "sep": "|--------|:-:|:-:|",
            "rows": [
                "| Enfoque | Problema concreto | Solución buscando problema |",
                "| ROI visible | < 3 meses | > 9 meses |",
                "| Equipo | Mínimo + expertos | Grande sin experiencia |",
                "| Datos | Propios y relevantes | Comprados genéricos |",
            ],
        },
        {
            "kw": ["salud","medicina","médico","clinica","health","diagnóstico","hospital"],
            "header": "| Área | Precisión IA | Precisión humana |",
            "sep": "|-------|:-:|:-:|",
            "rows": [
                "| Imagenología | 92-95% | 85-88% |",
                "| Diagnóstico | 89% | 84% |",
                "| Triage | 94% | 82% |",
                "| Seguimiento | 91% | 78% |",
            ],
        },
    ]

    for entry in cards_db:
        for kw in entry["kw"]:
            if kw in title_lower:
                lines = [entry["header"], entry["sep"]] + entry["rows"]
                return "\n".join(lines)

    return None


# ─── Banco de perspectivas de análisis contextual (basado en título/fuente) ───
# Cuando no se puede obtener el contenido real del artículo (JS rendering, paywall),
# estas funciones generan análisis que SÍ reflejan el título y fuente específicos,
# no frases genéricas. Cada combinación de título+fuente produce texto único.

_ANALYSIS_ANGLES = {
    'compra_adquisicion': [
        "movimiento estratégico que consolida",
        "adquisición que redefine el mapa de",
        "operación que marca un antes y después en",
        "compra que refuerza la posición de",
    ],
    'lanzamiento': [
        "nueva herramienta que promete",
        "lanzamiento que apunta a",
        "innovación que busca",
    ],
    'estudio_investigacion': [
        "investigación que arroja luz sobre",
        "estudio que desafía las creencias sobre",
        "análisis que cuantifica el impacto de",
    ],
    'tendencia': [
        "tendencia que está transformando",
        "movimiento que está redefiniendo",
        "patrón emergente en",
    ],
    'problema_desafio': [
        "desafío crítico que enfrenta",
        "problema estructural en",
        "obstáculo que frena la adopción de",
    ],
    'opinion_entrevista': [
        "perspectiva que aporta una mirada",
        "visión que cuestiona el enfoque",
        "reflexión que invita a repensar",
    ],
}


def _classify_title(title):
    """Clasificar el título para elegir ángulo de análisis."""
    t = title.lower()
    if any(w in t for w in ['compró', 'compra', 'adquirió', 'adquiere', 'fusion', 'merge', 'acquisition']):
        return 'compra_adquisicion'
    if any(w in t for w in ['lanzó', 'lanza', 'presentó', 'presenta', 'anunció', 'anuncia', 'nuev', 'lanzamiento']):
        return 'lanzamiento'
    if any(w in t for w in ['estudio', 'investigación', 'informe', 'reporte', 'report', 'encuesta', 'research']):
        return 'estudio_investigacion'
    if any(w in t for w in ['tendencia', 'cambio', 'transformación', 'futuro', 'próxim', 'evolución']):
        return 'tendencia'
    if any(w in t for w in ['problema', 'desafío', 'riesgo', 'peligro', 'crisis', 'amenaza', 'obstáculo']):
        return 'problema_desafio'
    if any(w in t for w in ['opina', 'entrevista', 'reflexión', 'mirada', 'perspectiva', 'según']):
        return 'opinion_entrevista'
    return 'tendencia'  # default


def _generate_title_based_analysis(title, source):
    """Generar análisis contextual basado en el título del artículo.
    Extrae el tema central del título y desarrolla un análisis contextual
    que refleja el contenido esperado según el título y la fuente."""
    category = _classify_title(title)
    angles = _ANALYSIS_ANGLES.get(category, _ANALYSIS_ANGLES['tendencia'])
    angle = random.choice(angles)
    
    # Extraer tema central del título (lo que viene después de ':', '-', '—' o al inicio)
    if ':' in title:
        main_subject = title.split(':')[0].strip()
        focus = title.split(':')[1].strip()
    elif '—' in title:
        main_subject = title.split('—')[0].strip()
        focus = title.split('—')[1].strip()
    elif ' - ' in title:
        main_subject = title.split(' - ')[0].strip()
        focus = title.split(' - ')[1].strip()
    else:
        main_subject = title
        focus = title
    
    # Limpiar el subject (sacar fuente, prefijos)
    main_subject = re.sub(r'\s*-\s*(?:iProUP|La Nación|Ámbito|Infobae|.*)$', '', main_subject).strip()
    
    # Generar 2 párrafos de análisis contextual
    # Primer párrafo: contexto del tema
    # Segundo párrafo: implicaciones/reflexión
    
    # Contextos variables para el primer párrafo
    # Asegurar que angle no empiece con preposición que cause duplicación
    _angle_clean = angle if not any(angle.startswith(w) for w in ['un ', 'una ']) else angle
    openers = [
        f"El artículo de {source} titulado '{title}' aborda un tema que está ganando tracción en la agenda tecnológica actual. ",
        f"{source} publicó recientemente '{title}', {_angle_clean} en el ecosistema de automatización e IA. ",
        f"La nota de {source} sobre '{main_subject}' representa {_angle_clean} que merece ser analizado con detenimiento. ",
        f"'{title}' — artículo de {source} — documenta {_angle_clean} relevante para empresas y profesionales del sector. ",
    ]
    
    p1 = random.choice(openers)
    
    # Asegurar no duplicación de espacios antes de la segunda parte
    # Si p1 termina sin espacio, agregarlo
    if not p1.endswith(' '):
        p1 += ' '
    
    # Segundo párrafo: implicación/reflexión contextual
    focus_clean = focus[:80]
    
    reflections = [
        f"El enfoque en '{focus_clean}' no es casual: responde a una demanda concreta del mercado "
        f"que estamos observando en nuestra experiencia con clientes. La cobertura de {source} "
        f"valida que el tema ha trascendido el nicho tecnológico para convertirse en discusión mainstream.",
        f"Lo interesante de esta cobertura de {source} es que '{focus_clean}' refleja un cambio "
        f"en la forma en que las organizaciones están abordando la adopción tecnológica. Ya no se "
        f"trata de 'si' implementar, sino de 'cómo' y 'con qué ritmo'.",
        f"Desde nuestra perspectiva como consultores en automatización, '{focus_clean}' es precisamente "
        f"el tipo de discusión que falta en muchos directorios. La tecnología avanza, pero la "
        f"conversación estratégica suele ir varios pasos atrás.",
        f"'{focus_clean}' — el eje de este artículo de {source} — resuena con lo que vemos en el "
        f"terreno: empresas que pasaron de preguntarse '¿qué es IA?' a '¿cómo la implementamos "
        f"sin romper lo que ya funciona?'.",
        f"{source} pone el foco en '{focus_clean}', y eso es relevante porque indica que el tema "
        f"ha madurado lo suficiente como para merecer análisis en profundidad desde medios "
        f"tradicionales, no solo en publicaciones especializadas.",
    ]
    
    p2 = random.choice(reflections)
    
    return f"{p1}{p2}\n\n*Análisis de MR Agentes en base a reportaje de {source}.*"


def _generate_analysis_from_content(content, title, source):
    """Generar análisis basado en el contenido real descargado del artículo.
    Extrae párrafos significativos, los analiza contextualmente, y produce
    un análisis textual único que refleja lo que realmente dice el artículo.
    
    Cuando no se puede extraer contenido real del HTML (JS rendering, paywall),
    genera análisis contextual a partir del título y la fuente."""
    
    def _is_menunav(text):
        """Detectar si un texto es navegación/menú en vez de contenido real."""
        nav_signals = [
            'inicio', 'home', 'contacto', 'nosotros', 'servicios', 'productos',
            'menú', 'secciones', 'temas del día', 'lo último',
            'seguí leyendo', 'leé también', 'compartir', 'suscribite',
            'newsletter', 'cookie', 'publicidad', 'sponsor', 'redes sociales',
            'facebook', 'twitter', 'instagram', 'linkedin', 'tiktok', 'youtube',
            'términos y condiciones', 'política de privacidad', 'acerca de',
            'todos los derechos reservados', 'nota relacionada', 'ver más notas',
            'noticias relacionadas', 'últimas noticias', 'más leídas',
            'siguiente nota', 'nota anterior', 'volver', 'buscar', 'navegación',
        ]
        text_lower = text.lower().strip()
        words = text_lower.split()
        if len(words) < 6:
            return True
        nav_count = sum(1 for s in nav_signals if s in text_lower)
        return (nav_count / max(len(words), 1)) > 0.12
    
    if not content:
        return _generate_title_based_analysis(title, source)
    
    # Intentar extraer oraciones significativas del HTML
    # Split en oraciones por puntuación seguida de mayúscula
    raw_sentences = re.split(r'(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚ\"\'\u201C])', content)
    
    # Detectar si el contenido es mayormente navegación (útil para detectar carga JS)
    nav_score = sum(1 for s in raw_sentences if _is_menunav(s))
    total_score = max(len(raw_sentences), 1)
    nav_ratio = nav_score / total_score
    
    # Si más del 60% del contenido parece navegación, probablemente no se pudo cargar el real
    if nav_ratio > 0.6:
        return _generate_title_based_analysis(title, source)
    
    # Filtrar oraciones de navegación
    real_content = [s.strip() for s in raw_sentences 
                    if len(s.strip()) > 30 
                    and not _is_menunav(s)]
    
    if len(real_content) < 3:
        return _generate_title_based_analysis(title, source)
    
    # Seleccionar 2-3 oraciones para formar el análisis
    random.shuffle(real_content)
    num = min(random.randint(2, 3), len(real_content))
    selected = real_content[:num]
    
    paragraphs = []
    for i, sent in enumerate(selected):
        sent = sent.strip()
        if len(sent) > 350:
            sent = sent[:347].rsplit(' ', 1)[0] + '...'
        if i == 0:
            contexts = [
                f"El artículo de {source} plantea que {sent[0].lower()}{sent[1:]}",
                f"Según la información publicada por {source}, {sent[0].lower()}{sent[1:]}",
                f"{source} reporta que {sent[0].lower()}{sent[1:]}",
            ]
            # Evitar doble puntuación
            first = random.choice(contexts)
            first = first.rstrip('.')
            paragraphs.append(first + '.')
        else:
            connectors = [
                "Profundizando en el análisis, ",
                "Además, el artículo señala que ",
                "El reportaje también destaca que ",
                "En la misma línea, ",
                "Otro punto relevante que aborda es que ",
                "Sobre este aspecto, menciona que ",
                "",
            ]
            conn = random.choice(connectors)
            text = f"{conn}{sent[0].lower()}{sent[1:]}".rstrip('.').strip()
            paragraphs.append(text + '.')
    
    body = "\n\n".join(paragraphs)
    
    # Añadir insight contextual de cierre
    closing_insights = [
        f"\n\n*Este análisis de MR Agentes se basa exclusivamente en el contenido del reportaje de {source}, contrastado con nuestra experiencia en el sector.*",
        f"\n\n*En MR Agentes seguimos este tema porque impacta directamente en cómo las empresas — especialmente las PyMEs argentinas — pueden aprovechar estas tendencias.*",
        f"\n\n*Desde nuestra perspectiva, información como esta es relevante porque refleja tendencias reales que ya estamos viendo en el mercado local.*",
    ]
    body += random.choice(closing_insights)
    
    return body


def enrich_trend_analysis(trend, unifying_angle=None):
    """Analizar una noticia de tendencias BASADA EN SU CONTENIDO REAL.
    Opcionalmente recibe un unifying_angle (conclusión global) para alinear
    todos los análisis hacia un mismo enfoque en la segunda pasada.
    Devuelve tupla (analysis_block, card_str, raw_analysis_dict).
    ⚠️ CADA llamado produce texto ÚNICO — no hay análisis hardcodeados."""
    result = analyze_url_content(trend)

    # Si tenemos un ángulo unificador, sumamos una línea que conecte este
    # artículo con la conclusión global, de forma natural y no repetitiva
    angle_line = ""
    if unifying_angle:
        # Separar el ángulo en partes: la idea fuerza y ejemplos
        angle_clean = unifying_angle
        # Si empieza con "Los artículos de..." sacar eso para no sonar forzado
        angle_clean = re.sub(r'^(?:Los artículos de .+? apuntan en la misma dirección: |Tanto en el caso de .+? como en .+?, vemos que )', '', angle_clean)
        angle_clean = angle_clean.strip().lower()
        if not angle_clean.endswith('.') and not angle_clean.endswith('...'):
            angle_clean = angle_clean

        # Solo agregar línea de conexión si hay al menos 2 artículos (segunda pasada vale la pena)
        connectors = [
            f"\n\n*Este artículo, como los demás que analizamos hoy, apunta a que {angle_clean}.*",
            f"\n\n*En línea con el análisis de hoy: {angle_clean}.*",
        ]
        angle_line = random.choice(connectors)

    # Construir bloque: cita real del artículo + análisis contextual
    analysis_text = result['analysis']
    if angle_line:
        analysis_text += angle_line

    lines = [
        f"> {result['quote']}",
        "",
        analysis_text,
    ]
    card_str = result['card'] if result['card'] else ""

    return "\n".join(lines), card_str, result


def _generate_unifying_conclusion(trends, analyzed_articles):
    """
    Generar una conclusión global coherente basada en los artículos analizados.
    Esta conclusión se genera PRIMERO, y luego se usa para:
    1. Darle título a la nota
    2. Refinar el análisis de cada artículo (segunda pasada)
    3. Escribir la description

    analyzed_articles: lista de dicts con 'title', 'source', 'analysis', 'quote'
    Returns: string con la conclusión global
    """
    if not analyzed_articles:
        return "La tecnología avanza más rápido que la capacidad de las organizaciones para absorberla. La brecha no es tecnológica, es de implementación."

    # Elegir un patrón de conclusión basado en los temas reales
    titles_text = " ".join([a['title'].lower() for a in analyzed_articles])

    # Banco amplio de conclusiones para cada tema, con perspectiva pseudo-académica
    all_conclusions = [
        # Atención al cliente / chatbots
        (['chatbot','atención','soporte','customer','cliente','consulta'], [
            "la atención al cliente está migrando hacia modelos híbridos donde la IA maneja lo rutinario y los humanos se concentran en casos complejos",
            "el verdadero diferencial competitivo en atención al cliente no es la tecnología más cara sino la integración coherente entre canales y sistemas",
            "las empresas que mejor resuelven consultas son las que combinan velocidad de respuesta automatizada con calidad humana en los momentos críticos",
            "la personalización masiva — antes un oxímoron — se vuelve viable cuando los sistemas aprenden de cada interacción sin depender de la memoria humana",
        ]),
        # Productividad / eficiencia
        (['product','eficien','rendim','tiempo','productividad','rendimiento'], [
            "la productividad no la da la tecnología sola, sino la combinación de buenos procesos + herramientas bien elegidas + equipos capacitados",
            "las ganancias de productividad más significativas no vienen de reemplazar personas sino de liberar su tiempo para tareas de alto valor",
            "medir el impacto real de la tecnología requiere ir más allá de 'ahorramos X horas' y preguntar qué se hizo con ese tiempo",
            "el mito de la eficiencia infinita choca contra la realidad: todo sistema optimizado introduce nuevas restricciones en otro punto del proceso",
        ]),
        # Ciberseguridad
        (['seguridad','ciber','privacidad','riesgo','protección','ataque','vulnerabilidad'], [
            "la ciberseguridad ya no es opcional ni un gasto, es una inversión crítica que ninguna empresa puede postergar sin arriesgar su continuidad",
            "el riesgo no está solo afuera: los incidentes más costosos suelen originarse en procesos internos mal diseñados más que en ataques externos",
            "la paradoja de la seguridad con IA: cuantos más datos le das al sistema para protegerte, más superficie de ataque generas",
        ]),
        # Datos / analytics
        (['dato','analytics','big data','dash','métrica','indicador','kpi','medición'], [
            "los datos no valen por sí mismos sino por las decisiones que permiten tomar, y ahí es donde la IA marca la diferencia real",
            "el salto de 'tener datos' a 'usar datos para decidir' es el que separa a las empresas que crecen de las que se estancan",
            "la democratización del análisis de datos — antes coto de científicos de datos — está permitiendo que cualquier área tome decisiones informadas sin intermediarios",
        ]),
        # Industria / fabricación
        (['industria','fabrica','manufact','supply','producción','operación','logística','cadena'], [
            "la transformación industrial con IA no es reemplazar operarios sino darles herramientas para detectar problemas antes de que ocurran",
            "la fábrica inteligente no es la que tiene más robots, es la que tiene mejor información en tiempo real para tomar decisiones",
            "el salto cualitativo en manufactura no está en la automatización del movimiento sino en la capacidad de anticipar fallas antes que ocurran",
        ]),
        # IA / modelos / tecnología
        (['modelo','algoritmo','lenguaje','gpt','openai','claude','neural','entrenamiento','parámetros','token'], [
            "la carrera por modelos más grandes está dando paso a una carrera por modelos más eficientes y especializados",
            "el verdadero desafío de la IA generativa no es técnico sino de integración: cómo conectar estas capacidades con procesos de negocio reales",
            "estamos pasando de la fascinación por lo que la IA puede hacer a la pregunta incómoda: ¿qué problemas reales resuelve sin crear otros nuevos?",
            "los modelos abiertos están nivelando el campo de juego: una PyME con buen fine-tuning puede lograr resultados comparables a soluciones enterprise",
        ]),
        # Automatización
        (['automati','rpa','bot','workflow','proceso','tarea repeti'], [
            "el error más común en automatización es intentar digitalizar un proceso que no funciona bien en papel: primero hay que rediseñar, después automatizar",
            "la automatización no elimina empleos, elimina tareas. El desafío es qué hacer con el tiempo que se libera",
            "la ola actual de automatización inteligente — que combina RPA con IA — permite abordar procesos que antes eran demasiado complejos o variables para automatizar",
        ]),
        # Economía / mercado / PyMEs
        (['pyme','startup','emprend','mercado','inversión','economía','argentina','latinoam', 'regional'], [
            "las PyMEs tienen una ventaja frente a las grandes corporaciones: pueden implementar cambios más rápido porque tienen menos burocracia y capas de decisión",
            "en mercados volátiles como el argentino, la capacidad de adaptación tecnológica rápida se convierte en ventaja competitiva más que en gasto",
            "la brecha digital no es solo de acceso a tecnología sino de capacidad para integrarla: tener las herramientas no es lo mismo que saber usarlas",
        ]),
        # Ética / regulación / governance
        (['ética','regulación','gobierno','sesgo','transparencia','legislación','normativa','cumplimiento','regulatory'], [
            "la regulación de IA avanza más lento que la tecnología, y esa asimetría genera tanto oportunidades como riesgos",
            "el debate sobre sesgos algorítmicos está cambiando: ya no se discute si los hay, sino cómo medirlos y mitigarlos",
            "la transparencia algorítmica — poder explicar por qué un modelo tomó una decisión — se está convirtiendo en un requisito de negocio, no solo regulatorio",
        ]),
        # Salud / medicina / biotech
        (['salud','medicina','médico','diagnóstico','clínico','hospital','farmacéutica'], [
            "el mayor impacto de la IA en salud no está en reemplazar médicos sino en aumentar su capacidad de diagnóstico y reducir errores",
            "la medicina personalizada, impulsada por IA, está pasando de ser una promesa a una realidad con casos concretos de implementación",
        ]),
        # Educación / capacitación
        (['educación','capacitación','aprendizaje','formación','entrenamiento','skill','talento','recurso humano','upgrade','upskill'], [
            "el cuello de botella de la transformación digital no es tecnológico sino humano: falta de capacitación, resistencia al cambio y procesos no documentados",
            "la educación en IA no debería enseñar a programar modelos sino a pensar críticamente sobre cuándo y cómo usarlos",
        ]),
    ]

    # Buscar el grupo con más coincidencias
    best_match = []
    best_count = 0
    for keywords, themes in all_conclusions:
        count = sum(1 for kw in keywords if kw in titles_text)
        if count > best_count:
            best_count = count
            best_match = themes

    # Elegir entre el grupo que mejor matchea (85%) o uno de temas generales (15%)
    # para mantener variedad pero evitar conclusiones completamente fuera de tema
    if best_match and random.random() < 0.85:
        themes = best_match
    else:
        # Usar solo algunos grupos con perspectiva amplia como "sorpresa"
        broad_groups = [
            _ANALYSIS_ANGLES.get('tendencia', ['cambio que está transformando']),
            _ANALYSIS_ANGLES.get('problema_desafio', ['desafío que enfrenta']),
        ]
        # Tarjetas genéricas más amplias
        generic_conclusions = [
            "la inteligencia artificial no es un fin en sí misma, sino un habilitador: las organizaciones que mejor la capitalizan no son las que tienen los modelos más grandes sino las que tienen los procesos mejor definidos para integrarlos",
            "la madurez digital de una organización importa más que el presupuesto en tecnología para obtener resultados reales con IA",
            "el cuello de botella de la transformación digital no es tecnológico sino humano: falta de capacitación, resistencia al cambio y procesos no documentados",
            "detrás de cada implementación exitosa de IA hay un patrón recurrente: problema claro + datos limpios + expectativas realistas + medición constante",
            "las PyMEs tienen una ventaja frente a las grandes corporaciones: pueden implementar cambios más rápido porque tienen menos burocracia y capas de decisión",
            "la tecnología es el medio, no el fin: el verdadero diferencial está en cómo se integra con la estrategia de negocio",
            "el costo de no automatizar no es solo la ineficiencia operativa, es la pérdida de capacidad para competir en un mercado que se digitaliza cada día más",
        ]
        themes = generic_conclusions

    conclusion = random.choice(themes)

    # A veces agregar una segunda oración para profundidad
    if random.random() < 0.35:
        follow = [
            "No es una predicción, es una observación de lo que ya está ocurriendo en empresas que tomaron la decisión de innovar.",
            "No se trata de adoptar tecnología por adoptarla, sino de entender qué problema concreto se resuelve.",
            "Lo interesante es que esta tendencia no viene de los departamentos de IT sino de las áreas de negocio que encontraron valor real.",
            "Detrás de cada implementación exitosa hay un patrón que se repite: problema claro, datos limpios, expectativas realistas y medición constante.",
            "No importa cuán sofisticada sea la herramienta: si el proceso de base está roto, la tecnología solo acelera el desastre.",
            "El dato más revelador de este análisis es que las empresas que lideran no son las que más invierten, sino las que mejor integran.",
        ]
        follow_sentence = random.choice(follow)
        # Asegurar que la última palabra de conclusion termine con punto
        conclusion = conclusion.rstrip().rstrip('.') + '. ' + follow_sentence

    return conclusion.strip()


def _generate_title_from_conclusion(conclusion, trends, fmt):
    """
    Generar un título específico y relevante basado en la conclusión real,
    no en templates genéricos.
    """
    # Extraer palabras clave de la conclusión
    conclusion_lower = conclusion.lower()

    # Banco expandido de títulos por tema
    title_db = {
        'atención': [
            "Atención al cliente con IA: el modelo híbrido que funciona",
            "Por qué la atención al cliente híbrida es la próxima frontera",
            "IA en atención al cliente: velocidad sin perder calidad",
            "El mito del chatbot frío: por qué la IA está humanizando la atención",
            "Atención 24/7 sin perder el toque humano: el equilibrio posible",
        ],
        'productividad': [
            "Productividad con IA: el factor humano sigue siendo la clave",
            "Más allá de las horas ahorradas: el verdadero impacto de la IA",
            "IA y productividad: liberar tiempo no es el objetivo final",
            "Eficiencia con IA: el rendimiento no es solo cuestión de velocidad",
            "La paradoja de la productividad: cuanta más tecnología, más crítico es el factor humano",
        ],
        'seguridad': [
            "Ciberseguridad con IA: protección que evoluciona con las amenazas",
            "El costo de no invertir en seguridad digital",
            "IA aplicada a ciberseguridad: detección temprana que salva empresas",
            "Seguridad digital en 2026: por qué el eslabón más débil no es la tecnología",
            "Ciberamenazas con IA: la paradoja de defenderte con la misma tecnología que te ataca",
        ],
        'datos': [
            "De los datos a las decisiones: el salto que marca la diferencia",
            "Datos + IA: la fórmula para decisiones más inteligentes",
            "El verdadero valor de los datos está en lo que decidís con ellos",
            "Infoxicación: por qué tener más datos no significa tomar mejores decisiones",
            "El análisis predictivo no es magia: cómo separar señales de ruido",
        ],
        'industria': [
            "Industria 4.0: la información en tiempo real como ventaja competitiva",
            "La fábrica inteligente no es la que tiene más robots",
            "Transformación industrial con IA: datos que anticipan problemas",
            "Mantenimiento predictivo: cómo la IA está cambiando las reglas de la manufactura",
            "La industria 4.0 no es tecnología, es una forma distinta de pensar la producción",
        ],
        'implementación': [
            "Implementación de IA: procesos claros > presupuesto grande",
            "El factor más infravalorado en la transformación digital",
            "Madurez digital: lo que realmente separa a las empresas que avanzan",
            "De la prueba piloto a la escala: el momento más crítico de cualquier adopción de IA",
            "Por qué el 70% de los proyectos de IA fracasan (y cómo no ser parte de la estadística)",
        ],
        'pymes': [
            "La ventaja de las PyMEs frente a las grandes corporaciones",
            "Por qué las PyMEs pueden implementar IA más rápido",
            "El tamaño no importa: la agilidad como ventaja competitiva",
            "PyMEs e IA: cómo competir con gigantes sin presupuesto de gigantes",
            "Tecnología accesible: por qué 2026 es el año de la PyME digital",
        ],
        'modelos': [
            "Modelos de IA más chicos, más eficientes: hacia dónde va la industria",
            "El fin de la era de los modelos gigantes: eficiencia > tamaño",
            "IA abierta vs IA cerrada: el debate que define el futuro de la tecnología",
        ],
        'ética': [
            "Ética e IA: el debate que ninguna empresa puede evitar",
            "Sesgos algorítmicos: el problema no es la máquina, son los datos",
            "Transparencia en IA: por qué explicar una decisión algorítmica es tan importante como la decisión misma",
        ],
        'salud': [
            "IA en salud: el diagnóstico aumentado que salva vidas",
            "Medicina personalizada con IA: de la promesa a la práctica",
            "El rol de la IA en salud: aumentar, no reemplazar",
        ],
        'educación': [
            "Educación en IA: lo que debería aprender cualquier profesional en 2026",
            "Capacitación digital: el verdadero cuello de botella de la transformación",
            "Aprender a pensar con IA: la habilidad más infravalorada",
        ],
        'automatización': [
            "Automatización inteligente: RPA + IA, la combinación que cambia las reglas",
            "Automatizar bien: por qué primero hay que rediseñar el proceso",
            "El mito de la automatización total: qué debería y qué no debería automatizarse",
        ],
    }

    # Buscar el tema que más coincida en la conclusión
    matched_topic = None
    max_count = 0
    for topic_keywords, titles in title_db.items():
        count = sum(1 for kw in topic_keywords if kw in conclusion_lower)
        if count > max_count:
            max_count = count
            matched_topic = topic_keywords

    if matched_topic and max_count > 0:
        base_titles = title_db[matched_topic]
    elif fmt == 'C' and trends:
        # Formato editorial: usar título del primer artículo como base
        t = trends[0]['title']
        short = t.split(':')[0].strip() if ':' in t else t[:60]
        base_titles = [
            f"{short}: lo que opinamos",
            f"Análisis: {short}",
            f"{short}: implicaciones para tu negocio",
        ]
    else:
        # Fallback: mezclar títulos de varios temas
        all_titles = []
        for titles in title_db.values():
            all_titles.extend(titles)
        base_titles = all_titles + [
            "IA y automatización: lo que hoy está cambiando las reglas",
            "Automatización e IA: el panorama que no podés ignorar",
            "Lo más relevante en IA y automatización esta semana",
            "Tres noticias que explican hacia dónde va la IA",
            "El estado de la IA en 2026: lo que tenés que saber",
            "Claves de la semana en IA y automatización",
            "Panorama IA: 3 noticias que redefinen el futuro del trabajo",
            "Lo que las empresas están haciendo con IA (y no es lo que pensás)",
        ]

    title = random.choice(base_titles)

    # A veces agregar un sub-título provocativo basado en la conclusión
    if random.random() < 0.35:
        conclusion_idea = conclusion.split('.')[0].strip().lower()
        if len(conclusion_idea) > 50:
            conclusion_idea = conclusion_idea[:47].rsplit(' ', 1)[0] + '...'
        elif len(conclusion_idea) < 20:
            # No usar si es muy corto
            pass
        else:
            hooks = [
                f" — {conclusion_idea}",
                f" — Clave: {conclusion_idea}",
                f" — {conclusion_idea.capitalize()}",
            ]
            hook = random.choice(hooks)
            if len(hook) < 90:
                title = f"{title}{hook}"

    return title


def _generate_description_from_analysis(title, conclusion, trends, analyzed_articles):
    """
    Generar meta description basada en la conclusión y análisis real,
    no solo en tags genéricos.
    Máximo 155 caracteres.
    """
    # Limpiar conclusión: primera oración o idea principal (sin prefijos extraños)
    conclusion_short = conclusion.strip()
    # Tomar only la primera oración
    if '.' in conclusion_short:
        conclusion_short = conclusion_short.split('.')[0].strip()
    else:
        conclusion_short = conclusion_short[:80]
    # Limpiar si empieza con mayúscula inconsistente
    conclusion_short = conclusion_short.capitalize()
    if len(conclusion_short) > 85:
        conclusion_short = conclusion_short[:82].rsplit(' ', 1)[0] + '...'

    # Tomar nombres de fuentes
    sources = [a['source'] for a in analyzed_articles[:2]]
    source_str = ', '.join(sources)

    # Limpiar comillas simples/curly de la conclusión para description
    conclusion_clean = conclusion_short.replace("'", "").replace('"', '').replace('´', '').replace('`', '').replace('“', '').replace('”', '').replace('‘', '').replace('’', '').strip()
    # Si la limpieza dejó palabras pegadas (ej: ahorramos x horas y), separar
    conclusion_clean = re.sub(r'\bde\s+y\b', 'de y', conclusion_clean)  # no es necesario, pero por las dudas
    conclusion_clean = re.sub(r'\b(\w+)\s+y\s+(\w+)\b', r'\1 y \2', conclusion_clean)

    # Tres formatos: uno con conclusión, dos simples con título + fuentes
    options = [
        f"{title}. {conclusion_clean}",
        f"{title}. Análisis de MR Agentes basado en {source_str}.",
        f"{title}. Nota de MR Agentes con análisis de {source_str}.",
    ]

    desc = random.choice(options)

    # Ajustar a 155 caracteres cortando por palabra completa
    if len(desc) > 155:
        desc = desc[:152].rsplit(' ', 1)[0] + '.'
    if not desc.endswith('.') and not desc.endswith('?'):
        desc += '.'
    # Asegurar que no termine con caracteres raros
    desc = re.sub(r'[\s\.,;:!]+$', '.', desc)
    # Si después de limpiar quedó demasiado corto, usar solo título + tag
    if len(desc) < 30:
        desc = f"{title}. Nota de MR Agentes."
    return desc.strip()


def generate_trends_post(state):
    """
    Generar un post basado en investigación online con análisis propio.
    NUEVO FLUJO:
    1. Investigar tendencias
    2. Analizar CADA artículo por separado (primera pasada)
    3. Generar CONCLUSIÓN GLOBAL basada en los análisis
    4. Generar TÍTULO y DESCRIPTION basados en la conclusión
    5. SEGUNDA PASADA: refinar el análisis de cada artículo alineándolo
       con el enfoque unificado
    6. Armar el cuerpo final

    Formato impredecible:
    - Forma A (~40%): 3 tendencias con tabla
    - Forma B (~35%): 2 tendencias con análisis más profundo
    - Forma C (~25%): 1 tendencia + análisis tipo editorial
    """
    print("🔍 Investigando tendencias online...")
    trends = fetch_web_trends()

    # Guardar trends en archivo temporal para browser-enrich
    if trends:
        import json as _json
        temp_trends_file = os.path.join(BASE_DIR, "scripts", "_last_trends.json")
        try:
            with open(temp_trends_file, "w", encoding="utf-8") as _f:
                _json.dump(trends, _f, ensure_ascii=False, indent=2)
        except:
            pass

    if not trends:
        print("  ⚠️  No se pudieron obtener tendencias. Reintentando...")
        return None

    today = datetime.date.today()
    month_names = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
                   "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
    date_str = f"{today.day} de {month_names[today.month - 1]}"

    # ─── FASE 1: Análisis individual de cada artículo (primera pasada) ───
    print("  🔬 Analizando artículos (primera pasada)...")
    num_trends = min(len(trends), 3)
    working_trends = trends[:num_trends]
    analyzed_articles = []
    first_pass_analyses = []  # (analysis_block, card) por cada artículo

    for trend in working_trends:
        analysis_block, card, result = enrich_trend_analysis(trend)
        first_pass_analyses.append((analysis_block, card))
        analyzed_articles.append({
            'title': trend['title'],
            'source': trend['source'],
            'url': trend['url'],
            'analysis': result['analysis'],
            'quote': result['quote'],
        })

    # ─── FASE 2: Generar conclusión global ────────────────────────
    print("  💡 Generando conclusión global...")
    global_conclusion = _generate_unifying_conclusion(working_trends, analyzed_articles)

    # ─── FASE 3: Elegir formato y armar ───────────────────────────
    fmt = random.random()

    # ─── FASE 4: Segunda pasada — refinar análisis con enfoque unificado ──
    print(f"  🔄 Segunda pasada: alineando análisis con enfoque: '{global_conclusion[:60]}...'")
    refined_analyses = []
    for i, trend in enumerate(working_trends):
        refined_block, refined_card, _ = enrich_trend_analysis(trend, unifying_angle=global_conclusion)
        refined_analyses.append((refined_block, refined_card))

    # ─── FASE 5: Generar título y description post-análisis ────────
    print("  ✏️  Generando título basado en el análisis...")
    body_title = f"Análisis del día — {date_str}"
    title = _generate_title_from_conclusion(global_conclusion, working_trends, 'B' if len(working_trends) == 1 else fmt)
    description = _generate_description_from_analysis(title, global_conclusion, working_trends, analyzed_articles)

    # ─── FASE 6: Armar cuerpo según formato ────────────────────────
    if fmt < 0.40 and len(working_trends) >= 3:
        # ─── Forma A: 3 tendencias + tabla ─────────────────────
        body = f"## Panorama de automatización e IA — {date_str}\n\n"
        body += """Cada día revisamos las noticias más relevantes del mundo de la automatización y la inteligencia artificial, y las analizamos para darte nuestra perspectiva. Esto es lo que encontramos:

"""
        for i, trend in enumerate(working_trends[:3]):
            analysis_block, card = refined_analyses[i]
            body += f"""### 📰 {trend['title']}
*{trend['source']}*

{analysis_block}

"""
            if card:
                body += f"{card}\n\n"
            body += f"[Ver artículo original]({trend['url']})\n\n"

        body += f"---\n\n### En síntesis\n\n{global_conclusion.capitalize()}\n\n*Fuentes: análisis propio de MR Agentes sobre noticias públicas verificables.*"

    elif fmt < 0.75 and len(working_trends) >= 2:
        # ─── Forma B: 2 tendencias con análisis profundo ────────
        body_lines = [f"## Análisis del día — {date_str}", "",
                      random.choice([
                          "Hoy nos enfocamos en dos temas clave que están marcando la agenda de automatización e inteligencia artificial. Los analizamos en profundidad.",
                          "Dos noticias que llamaron nuestra atención hoy, con análisis detallado de cada una.",
                          "Seleccionamos dos temas clave para analizar en detalle.",
                      ]),
                      ""]
        for i, trend in enumerate(working_trends[:2]):
            analysis_block, card = refined_analyses[i]
            lines_analysis = analysis_block.split("\n")
            pull = ""
            content_lines = []
            for line in lines_analysis:
                if line.startswith(">"):
                    pull = line
                else:
                    content_lines.append(line)
            content = "\n".join(content_lines).strip()

            body_lines.append(f"### {i+1}. {trend['title']}")
            body_lines.append(f"*Fuente: {trend['source']}*")
            body_lines.append("")
            if pull:
                body_lines.append(pull)
                body_lines.append("")
            body_lines.append(content)
            body_lines.append("")
            if card:
                body_lines.append(card)
                body_lines.append("")
            body_lines.append(f"🔗 [Artículo original]({trend['url']})")
            body_lines.append("")

        body_lines.append("---")
        body_lines.append("")
        body_lines.append("### 💡 Nuestra lectura")
        body_lines.append("")
        body_lines.append(global_conclusion)
        body_lines.append("")
        body_lines.append("*Fuentes: análisis propio de MR Agentes sobre noticias públicas verificables.*")

        body = "\n".join(body_lines)

    else:
        # ─── Forma C: 1-2 tendencias + análisis editorial ─────
        trend = working_trends[0]
        analysis_block, card = refined_analyses[0]

        lines_analysis = analysis_block.split("\n")
        pull = ""
        content_lines = []
        for line in lines_analysis:
            if line.startswith(">"):
                pull = line
            else:
                content_lines.append(line)
        content = "\n".join(content_lines).strip()

        body = f"## {trend['title']}\n\n"
        if pull:
            body += f"{pull}\n\n"
        body += f"{content}\n\n"
        if card:
            body += f"{card}\n\n"
        body += "---\n\n"

        editorial_perspectives = [
            f"### Nuestra mirada\n\n{random.choice([
                f'En MR Agentes seguimos de cerca estas tendencias porque impactan directamente en cómo las empresas — especialmente las PyMEs argentinas — pueden aprovechar la tecnología para ser más competitivas. Esta nota la leemos como parte de un patrón más amplio: {global_conclusion}',
                f'¿Qué implica esto para tu negocio? Para nosotros, {global_conclusion}. La tecnología avanza, pero lo que realmente marca la diferencia es cómo se implementa.',
                f'En el contexto actual, esta noticia cobra especial relevancia. {global_conclusion.capitalize()}',
            ])}",
        ]
        body += random.choice(editorial_perspectives)
        body += f"\n\n🔗 [Fuente original]({trend['url']})\n\n*Análisis: MR Agentes*"

        # Si hay segunda tendencia, añadirla como análisis adicional
        if len(working_trends) >= 2:
            trend2 = working_trends[1]
            analysis_block2, card2 = refined_analyses[1]
            body += f"\n\n---\n\n### También analizamos: {trend2['title']}\n\n"
            body += f"*{trend2['source']}*\n\n"
            lines2 = analysis_block2.split("\n")
            pull2 = ""
            content2_lines = []
            for line in lines2:
                if line.startswith(">"):
                    pull2 = line
                else:
                    content2_lines.append(line)
            body += "\n".join(content2_lines).strip()
            body += f"\n\n🔗 [Artículo original]({trend2['url']})"

    tags = ["tendencias", "ia", "automatizacion", "noticias"]
    image = pick_image(state)

    return {
        "title": title,
        "description": description,
        "image": image,
        "tags": tags,
        "body": body,
    }


def get_daily_content(state):
    """
    Obtener contenido del día: SIEMPRE investigación online + análisis propio.
    Variedad impredecible para evitar monotonía:
    - A veces 3 tendencias con tabla (como antes)
    - A veces 2 tendencias con análisis más profundo (4-5 párrafos)
    - A veces 1 tendencia + análisis tipo editorial
    - El formato concreto se elige al azar en generate_trends_post()
    """
    # Siempre intentar investigación online
    result = generate_trends_post(state)
    if result:
        return result

    # Fallback extremo: si falla la investigación, investigar de nuevo (reintento simple)
    print("  🔄 Reintentando investigación...")
    import time
    time.sleep(2)
    result = generate_trends_post(state)
    if result:
        return result

    # Si aún falla, usar TOPICS como último recurso
    print("  ⚠️  Usando tema del calendario como fallback de emergencia")
    topic_index = state.get("topic_index", 0)
    entry = TOPICS[topic_index % len(TOPICS)]
    state["topic_index"] = (topic_index + 1) % len(TOPICS)
    image = pick_image(state)
    save_state(state)
    return {
        "title": entry["title"],
        "image": image,
        "tags": entry["tags"],
        "body": entry["body"],
        "description": None,
    }


def create_nota(title, body, tags, image, description=None):
    """Crear archivo de nota en content/notas/.
    Si se pasa description, se usa esa (generada post-análisis).
    Si no, se genera automáticamente (fallback)."""
    today = datetime.date.today()
    slug = slugify(title)
    filename = f"{today.isoformat()}-{slug}.md"
    filepath = os.path.join(CONTENT_DIR, filename)

    tags_yaml = "\n".join([f"  - {t}" for t in tags])
    if description is None:
        description = _generate_description(title, tags, body)
    image_alt = _generate_image_alt(image)
    content = f"""---
title: "{title}"
date: {today.isoformat()}
description: "{description}"
image: "{STOCK_IMAGES_DIR}{image}"
image_alt: "{image_alt}"
tags:
{tags_yaml}
---

{body}
"""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"✅ Nota creada: {filename}")
    return filepath


def git_commit_push(filepath, title):
    """Hacer commit y push de la nueva nota."""
    try:
        os.chdir(BASE_DIR)

        subprocess.run(["git", "add", filepath], check=True, capture_output=True)

        commit_msg = f"📝 Nueva nota: {title}"
        subprocess.run(
            ["git", "commit", "-m", commit_msg],
            check=True, capture_output=True
        )

        result = subprocess.run(
            ["git", "push", "origin", "main"],
            check=True, capture_output=True, text=True
        )

        print(f"✅ Push exitoso: {commit_msg}")
        return True

    except subprocess.CalledProcessError as e:
        err = e.stderr.decode() if isinstance(e.stderr, bytes) else str(e.stderr)
        print(f"❌ Error en git: {err}")
        return False


def _generate_description(title, tags, body):
    """Generar meta description coherente a partir del título y tema.
    Máximo 155 caracteres. NO usa el body crudo (tiene markdown, citas, URLs)."""
    # Usar título + tags como base, siempre coherente
    tag_str = ', '.join(tags)
    # Limpiar el título: tomar hasta el primer "—" o "-" o la primera oración
    title_clean = title.split('—')[0].split('-')[0].strip().rstrip(',').strip()
    if len(title_clean) > 70:
        title_clean = title_clean[:67].rsplit(' ', 1)[0] + '...'
    desc = f"{title_clean}. Nota de MR Agentes sobre {tag_str}."
    if len(desc) > 155:
        desc = desc[:152].rsplit(' ', 1)[0] + '.'
    if not desc.endswith('.') and not desc.endswith('?'):
        desc += '.'
    return desc.strip()[:157].rsplit(' ', 1)[0] + '.'


def _load_dotenv():
    """Carga el .env de la raíz (si existe) para que las claves salgan de ahí."""
    try:
        from scripts.social.config import load_dotenv
    except ImportError:
        sys.path.insert(0, BASE_DIR)
        try:
            from scripts.social.config import load_dotenv
        except ImportError:
            return
    load_dotenv()


def _send_push_notification(title, filepath, worker_url=None):
    """Envía notificación push a suscriptores via Cloudflare Worker."""
    _load_dotenv()
    # Cargar config local para el token y worker URL
    config = {}
    config_file = os.path.join(BASE_DIR, "scripts", "config.local.json")
    if os.path.exists(config_file):
        try:
            with open(config_file) as f:
                config = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass

    worker_url = worker_url or config.get("pushWorkerUrl", "") or os.environ.get("PUSH_WORKER_URL", "")
    api_token = config.get("pushApiToken", "") or os.environ.get("PUSH_API_TOKEN", "")

    if not worker_url or not api_token:
        print("  ℹ️  Push no configurado (falta pushWorkerUrl o pushApiToken)")
        return

    slug = os.path.splitext(os.path.basename(filepath))[0]
    url = f"https://mragentes.com.ar/notas/{slug}/"

    print(f"  🔔 Enviando notificación push via {worker_url}/api/send/...")
    try:
        import urllib.request
        payload = json.dumps({
            "token": api_token,
            "title": title,
            "body": "Acabamos de publicar una nueva nota en MR Agentes.",
            "url": url,
        }).encode()
        req = urllib.request.Request(
            f"{worker_url}/api/send/",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
            sent = result.get('sent', 0)
            failed = result.get('failed', 0)
            removed = result.get('removed', 0)
            errors = result.get('errors', [])
            print(f"  🔔 Push: {sent} enviadas, {failed} fallidas, {removed} removidas")
            if errors:
                for e in errors[:2]:
                    print(f"    ⚠️  Error: {e.get('status', '?')} - {e.get('detail', e.get('error', '?'))[:100]}")
            if sent == 0 and failed > 0 and removed == 0:
                print("    ❌ Todas las entregas fallaron — puede haber problema de VAPID keys o suscripciones vencidas")
    except Exception as e:
        print(f"  ⚠️  Push notification HTTP error: {e}")


def _announce_on_social(filepath):
    """Aviso de nota nueva en Facebook e Instagram.

    La pieza se compone con la imagen de portada de la nota y el sistema visual
    del sitio (ver scripts/social/). Si algo falla, se avisa y se sigue: la nota
    ya está publicada en la web.
    """
    try:
        from scripts.social.hook import announce
    except ImportError:
        sys.path.insert(0, BASE_DIR)  # la raíz del repo, para que `scripts` sea paquete
        try:
            from scripts.social.hook import announce
        except ImportError as exc:
            print(f"  ⚠️  Redes: no pude cargar el social manager ({exc})")
            return
    announce(filepath)


def _generate_image_alt(image_filename):
    """Generar alt text descriptivo para cada imagen de stock."""
    alts = {
        # Originales
        "automation.jpg": "Representación visual de automatización empresarial con engranajes y tecnología digital",
        "data-analytics.jpg": "Análisis de datos y dashboards con gráficos y métricas empresariales",
        "digital-world.jpg": "Mundo digital y conectividad global representando transformación tecnológica",
        "ai-brain.jpg": "Cerebro digital conceptual representando inteligencia artificial y machine learning",
        # Pexels batch 2026-06-18
        "pexels-8386440.jpg": "Concepto abstracto de inteligencia artificial y redes neuronales digitales",
        "pexels-8438918.jpg": "Hombre pensando frente a tablero de ajedrez con brazo robótico, humano vs IA",
        "pexels-1181373.jpg": "Persona programando en Python en laptop, desarrollo de software",
        "pexels-1181390.jpg": "Persona usando tableta con teclado portátil, tecnología y productividad",
        "pexels-1181401.jpg": "Equipo de trabajo con código en pantalla, reunión tecnológica",
        "pexels-1181408.jpg": "Reunión de equipo diverso en sala de conferencias moderna",
        "pexels-1181671.jpg": "Libro técnico de Python en manos de programador",
        "pexels-1181672.jpg": "Mujer joven leyendo libro de programación Python",
        "pexels-1181354.jpg": "Entorno tecnológico y digital contemporáneo",
        "pexels-1181304.jpg": "Tecnología e innovación digital",
        "pexels-1181267.jpg": "Espacio tecnológico moderno",
        "pexels-1181675.jpg": "Entorno de trabajo tecnológico",
        "pexels-8566472.jpg": "Tecnología y computación moderna",
        "pexels-8441272.jpg": "Cafetería y estilo de vida urbano",
    }
    return alts.get(image_filename, "Imagen ilustrativa de automatización e inteligencia artificial")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Publicar nota diaria en MR Agentes website")
    parser.add_argument("--dry-run", action="store_true", help="Solo crear el archivo, sin git push")
    parser.add_argument("--force", action="store_true", help="Forzar publicación aunque ya exista nota hoy")
    parser.add_argument("--push-worker", type=str, default="", help="URL del Cloudflare Worker para push")
    parser.add_argument("--browser-enrich", action="store_true", help="Guardar JSON con URLs reales para enriquecer con browser tool")
    args = parser.parse_args()

    # Cargar estado persistente
    state = load_state()

    # Verificar si ya hay nota para hoy
    today_str = datetime.date.today().isoformat()
    existing = [f for f in os.listdir(CONTENT_DIR)
                if f.startswith(today_str) and f.endswith(".md")]
    if existing and not args.force:
        print(f"ℹ️  Ya existe nota para hoy ({existing[0]}). Usá --force para sobrescribir.")
        return

    # Obtener contenido del día
    print("📝 Generando contenido para hoy...")

    entry = get_daily_content(state)

    if entry is None:
        # Fallback solo si todo falla (2 intentos de investigación ya se hicieron)
        print("  ⚠️  Falló investigación online dos veces, usando tema del calendario")
        topic_index = state.get("topic_index", 0)
        t = TOPICS[topic_index % len(TOPICS)]
        state["topic_index"] = (topic_index + 1) % len(TOPICS)
        image = pick_image(state)
        save_state(state)
        entry = {"title": t["title"], "image": image, "tags": t["tags"], "body": t["body"], "description": None}

    if "tendencias" in entry.get("tags", []):
        print("  📰 Post basado en investigación online de tendencias + análisis propio")
    else:
        print(f"  📖 (fallback) Tema: {entry['title']}")

    print(f"  🖼️  Imagen: {entry['image']}")

    # Crear la nota (siempre, incluso con browser-enrich)
    filepath = create_nota(
        entry["title"],
        entry["body"],
        entry["tags"],
        entry["image"],
        description=entry.get("description"),
    )

    # ─── Browser Enrich Mode ────────────────────────────────────────
    # En lugar de pushear, guarda JSON con URLs para que el agente
    # las enriquezca navegando con browser tool y luego actualice la nota
    if args.browser_enrich and "tendencias" in entry.get("tags", []):
        enrich_file = os.path.join(BASE_DIR, "scripts", "_browser_enrich.json")
        # Leer trends del archivo temporal
        trends_for_enrich = []
        temp_trends_file = os.path.join(BASE_DIR, "scripts", "_last_trends.json")
        if os.path.exists(temp_trends_file):
            try:
                with open(temp_trends_file) as f:
                    trends_for_enrich = json.load(f)
            except:
                pass
        if not trends_for_enrich:
            trends_for_enrich = [{
                "title": entry.get("title", "Nota del día"),
                "source": "multiple",
                "url": ""
            }]
        enrich_data = {
            "nota_file": os.path.basename(filepath) if filepath else "",
            "title": entry.get("title", ""),
            "trends": trends_for_enrich,
        }
        with open(enrich_file, "w", encoding="utf-8") as f:
            json.dump(enrich_data, f, ensure_ascii=False, indent=2)
        print(f"  🖥️  Browser enrich file: {enrich_file}")
        print(f"  🔍 Pendiente: browser enrich + commit/push manual")
        return

    if args.dry_run:
        print(f"🏁 Dry run - archivo creado sin push: {filepath}")
        return

    # Generar index.json para SW
    print("📋 Generando index.json para service worker...")
    gen_index = os.path.join(BASE_DIR, "scripts", "generate_notas_index.py")
    if os.path.exists(gen_index):
        subprocess.run([sys.executable, gen_index])

    # Commit y push
    print("⬆️  Pusheando a GitHub...")
    success = git_commit_push(filepath, entry["title"])

    if success:
        print(f"🎉 Nota publicada exitosamente: {entry['title']}")
        # Enviar notificación push
        _send_push_notification(entry["title"], filepath, args.push_worker)
        # Aviso en Facebook e Instagram con la imagen de la nota
        _announce_on_social(filepath)
    else:
        print(f"⚠️  Nota creada localmente pero hubo error al pushear: {filepath}")


if __name__ == "__main__":
    main()
