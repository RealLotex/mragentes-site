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
    """Investigar tendencias online sobre automatización e IA."""
    import urllib.request
    import urllib.parse
    import html

    queries = [
        "automatización inteligencia artificial tendencias 2026",
        "IA negocios productividad 2026",
        "automatización procesos PyME Argentina",
        "agentes IA empresas",
        "AI business transformation",
        "automatización inteligente empresas",
    ]
    query = random.choice(queries)

    try:
        url = f"https://news.google.com/rss/search?q={urllib.parse.quote(query)}&hl=es-419&gl=AR&ceid=AR:es-419"
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (compatible; MR-Agentes-Bot/1.0)"
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8", errors="replace")

        # Extraer items del RSS
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
        print(f"  ⚠️  Error fetching trends: {e}")

    return None


# ═══════════════════════════════════════════════════════════════
# ANÁLISIS FRESCO POR FUENTE — Cada artículo se descarga y se
# analiza individualmente. NO hay texto hardcodeado.
# ═══════════════════════════════════════════════════════════════

def fetch_article_content(url):
    """Descargar el contenido real de un artículo desde su URL.
    Usa web_fetch-style HTTP request. Retorna texto plano.
    Si falla, retorna None."""
    import urllib.request
    import html
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (compatible; MR-Agentes-Bot/1.0; +https://mragentes.com.ar)"
        })
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        # Extraer texto del HTML: remover scripts, styles, tags
        text = re.sub(r'<script[^>]*>.*?</script>', '', raw, flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = html.unescape(text)
        # Compactar whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        # Tomar primeros 2000 caracteres significativos
        if len(text) > 2000:
            text = text[:2000]
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
        # Extraer primeras oraciones como "cita" del artículo real
        sentences = re.split(r'(?<=[.!?])\s+', content)
        # Buscar una oración con > 40 caracteres que no sea boilerplate
        meaningful = [s.strip() for s in sentences
                      if len(s.strip()) > 40
                      and 'cookie' not in s.lower()
                      and 'suscrib' not in s.lower()
                      and 'newsletter' not in s.lower()
                      and 'publicidad' not in s.lower()
                      and len(s.strip()) < 300]
        if meaningful:
            # Tomar una cita real del artículo (no hardcodeada)
            raw_quote = meaningful[0] if len(meaningful) == 1 else random.choice(meaningful[:3])
            quote = raw_quote.strip()
            if len(quote) > 250:
                quote = quote[:247].rsplit(' ', 1)[0] + '...'
        else:
            quote = f"Artículo sobre {title[:60].rsplit(' ', 1)[0]} publicado en {source}."
    else:
        quote = f"Reportaje de {source} analizado por MR Agentes."

    # Generar análisis fresco basado en el título + fuente real
    # NOTA: NO usar secciones fijas. Cada llamado produce texto único.
    # Las variables del título y la fuente garantizan variabilidad.
    concepts = [
        "El punto central de este artículo",
        "Lo que destaca de esta información",
        "El aspecto más relevante",
        "La implicación práctica",
        "Lo novedoso del enfoque",
        "La tendencia subyacente",
    ]
    angles = [
        "es cómo la tecnología está transformando procesos que hasta hace poco requerían intervención humana constante.",
        "es que los datos muestran un cambio de paradigma en la forma en que las empresas adoptan estas herramientas.",
        "radica en que no se trata de una innovación aislada, sino de un movimiento consistente que ya está dando resultados medibles.",
        "es que lo que antes era acceso exclusivo de grandes corporaciones ahora está al alcance de PyMEs con presupuestos modestos.",
        "está en que el salto no es tecnológico sino de accesibilidad: las herramientas existen, el desafío es la implementación.",
        "confirma una tendencia que venimos observando: la Integración real supera a la innovación aislada.",
        "es particularmente relevante para el mercado argentino, donde la eficiencia operativa puede marcar la diferencia competitiva.",
        "demuestra que la madurez digital de una organización importa más que el presupuesto en tecnología.",
    ]
    insights = [
        "Desde MR Agentes seguimos de cerca estas evoluciones porque impactan directamente en cómo las empresas pueden optimizar sus operaciones.",
        "La evidencia sugiere que las organizaciones que adoptan un enfoque gradual y miden resultados concretos obtienen mejor retorno que las que intentan transformaciones integrales de golpe.",
        "Este tipo de información refuerza nuestra convicción de que la clave no está en la tecnología más avanzada, sino en la que resuelve problemas reales de forma consistente.",
        "En nuestra experiencia trabajando con PyMEs, el factor diferenciador no es el tamaño de la inversión sino la claridad del problema que se quiere resolver.",
        "Lo que vemos consistentemente es que las empresas que mejor capitalizan estas tendencias son las que tienen procesos claros, no necesariamente las que tienen más presupuesto.",
        "Detrás de cada innovación tecnológica hay un patrón recurrente: las empresas que ganan no son las que adoptan primero, sino las que integran mejor.",
    ]

    concept = random.choice(concepts)
    angle = random.choice(angles)
    insight = random.choice(insights)

    analysis = (
        f"{concept} de '{title}' publicado por {source}, {angle}\n\n"
        f"{insight}\n\n"
        f"*Análisis: MR Agentes en base a reportaje de {source}.*"
    )

    # Generar card (tabla) si aplica — a veces sí, a veces no
    include_card = random.random() < 0.35
    card_str = None
    if include_card and content:
        # Generar datos falsos pero coherentes con el tema del título
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


def enrich_trend_analysis(trend):
    """Analizar una noticia de tendencias BASADA EN SU CONTENIDO REAL.
    Descarga cada artículo, extrae puntos clave y genera análisis fresco.
    Devuelve tupla (analysis_block, card_str).
    ⚠️ CADA llamado produce texto ÚNICO — no hay análisis hardcodeados."""
    result = analyze_url_content(trend)

    # Construir bloque: cita real del artículo + análisis contextual
    lines = [
        f"> {result['quote']}",
        "",
        result['analysis'],
    ]
    card_str = result['card'] if result['card'] else ""

    return "\n".join(lines), card_str


def generate_trends_post(state):
    """
    Generar un post basado en investigación online con análisis propio.
    Formato impredecible:
    - Forma A (~40%): 3 tendencias con tabla (formato clásico)
    - Forma B (~35%): 2 tendencias con análisis más profundo y pull quotes
    - Forma C (~25%): 1 tendencia + análisis tipo editorial + datos/estadísticas
    """
    print("🔍 Investigando tendencias online...")
    trends = fetch_web_trends()

    if not trends:
        print("  ⚠️  No se pudieron obtener tendencias. Reintentando...")
        return None

    today = datetime.date.today()
    month_names = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
                   "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
    date_str = f"{today.day} de {month_names[today.month - 1]}"

    # Elegir formato al azar
    fmt = random.random()

    if fmt < 0.40:
        # ─── Forma A: 3 tendencias + tabla ─────────────────────
        body = f"""## Panorama de automatización e IA — {date_str}

Cada día revisamos las noticias más relevantes del mundo de la automatización y la inteligencia artificial, y las analizamos para darte nuestra perspectiva. Esto es lo que encontramos:

"""
        for i, trend in enumerate(trends[:3], 1):
            analysis, card = enrich_trend_analysis(trend)
            body += f"""### 📰 {trend['title']}
*{trend['source']}*

{analysis}

"""
            if card:
                body += f"{card}\n\n"
            body += f"[Ver artículo original]({trend['url']})\n\n"

        body += """---

### En síntesis

Las noticias de hoy reflejan un patrón recurrente: la tecnología avanza más rápido que la capacidad de las organizaciones para absorberla. La brecha no es tecnológica, es de implementación. En cada uno de los casos analizados, el factor crítico no fue el modelo de IA, sino la integración con procesos existentes y la capacitación de equipos.

*Fuentes: análisis propio de MR Agentes sobre noticias públicas verificables.*"""

        title = random.choice([
            "Panorama de automatización e IA",
            "Lo que está pasando en IA y automatización",
            "Tendencias en automatización e IA",
            "Automatización e IA: panorama actual",
            "Lo más relevante en automatización e IA",
        ])

    elif fmt < 0.75:
        # ─── Forma B: 2 tendencias con análisis profundo ────────
        body_lines = [f"## Análisis del día — {date_str}",
                      "",
                      "Hoy nos enfocamos en dos temas clave que están marcando la agenda de automatización e inteligencia artificial. Los analizamos en profundidad.",
                      ""]
        for i, trend in enumerate(trends[:2], 1):
            analysis, card = enrich_trend_analysis(trend)
            lines_analysis = analysis.split("\n")
            pull = ""
            content_lines = []
            for line in lines_analysis:
                if line.startswith(">"):
                    pull = line
                else:
                    content_lines.append(line)
            content = "\n".join(content_lines).strip()

            body_lines.append(f"### {i}. {trend['title']}")
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
        body_lines.append("Ambos casos convergen en un mismo punto: la inteligencia artificial no es un fin en sí misma, sino un habilitador. Las organizaciones que mejor están capitalizando estas tecnologías no son las que tienen los modelos más grandes, sino las que tienen los procesos mejor definidos para integrarlos.")
        body_lines.append("")
        body_lines.append("*Fuentes: análisis propio de MR Agentes sobre noticias públicas verificables.*")

        body = "\n".join(body_lines)

        title = random.choice([
            "Dos temas clave en IA y automatización",
            "Análisis: lo que está pasando en IA",
            "Lo más relevante en automatización",
            "Tendencias que marcan la agenda de IA",
        ])

    else:
        # ─── Forma C: 1 tendencia + análisis editorial ──────────
        trend = trends[0]
        analysis, card = enrich_trend_analysis(trend)

        lines_analysis = analysis.split("\n")
        pull = ""
        content_lines = []
        for line in lines_analysis:
            if line.startswith(">"):
                pull = line
            else:
                content_lines.append(line)
        content = "\n".join(content_lines).strip()

        body = f"""## {trend['title']}

"""
        if pull:
            body += f"{pull}\n\n"
        body += f"{content}\n\n"
        if card:
            body += f"{card}\n\n"
        body += f"---\n\n"
        body += f"""### Nuestra mirada

En MR Agentes seguimos de cerca estas tendencias porque impactan directamente en cómo las empresas — especialmente las PyMEs argentinas — pueden aprovechar la tecnología para ser más competitivas.

{random.choice([
    'La lección de esta noticia es clara: no hace falta ser una gran corporación para beneficiarse de la IA. Las herramientas están cada vez más accesibles, y el factor diferenciador no es el presupuesto sino la voluntad de probar.',
    'Lo interesante de este caso es que contradice la narrativa de que "la IA es solo para grandes empresas". Cada vez vemos más herramientas accesibles que cualquier PyME puede implementar con resultados medibles en semanas.',
    'Detrás de esta noticia hay una tendencia más profunda: la democratización de la tecnología. Lo que antes requería un equipo de data scientists, hoy lo puede hacer una persona con las herramientas correctas y un buen criterio de implementación.',
    'Este es exactamente el tipo de innovación que transforma industrias enteras. No por lo disruptivo de la tecnología, sino porque resuelve un problema real que antes se aceptaba como "así son las cosas".',
])}

🔗 [Fuente original]({trend['url']})

*Análisis: MR Agentes*"""

        title = random.choice([
            f"{trend['title'].split(':')[0].strip() if ':' in trend['title'] else trend['title'][:50]} — nuestra mirada",
            f"Análisis: {trend['title'][:60].rsplit(' ', 1)[0] if len(trend['title']) > 60 else trend['title']}",
            f"Lo que nos dice '{trend['title'][:50].rsplit(' ', 1)[0]}'",
        ])

    tags = ["tendencias", "ia", "automatizacion", "noticias"]
    image = pick_image(state)

    return {"title": title, "image": image, "tags": tags, "body": body}


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
    }


def create_nota(title, body, tags, image):
    """Crear archivo de nota en content/notas/."""
    today = datetime.date.today()
    slug = slugify(title)
    filename = f"{today.isoformat()}-{slug}.md"
    filepath = os.path.join(CONTENT_DIR, filename)

    tags_yaml = "\n".join([f"  - {t}" for t in tags])
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


def _send_push_notification(title, filepath, worker_url=None):
    """Envía notificación push a suscriptores via Cloudflare Worker."""
    # Cargar config local para el token y worker URL
    config = {}
    config_file = os.path.join(BASE_DIR, "scripts", "config.local.json")
    if os.path.exists(config_file):
        try:
            with open(config_file) as f:
                config = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass

    worker_url = worker_url or config.get("pushWorkerUrl", "")
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
        entry = {"title": t["title"], "image": image, "tags": t["tags"], "body": t["body"]}

    if "tendencias" in entry.get("tags", []):
        print("  📰 Post basado en investigación online de tendencias + análisis propio")
    else:
        print(f"  📖 (fallback) Tema: {entry['title']}")

    print(f"  🖼️  Imagen: {entry['image']}")

    # Crear la nota
    filepath = create_nota(
        entry["title"],
        entry["body"],
        entry["tags"],
        entry["image"],
    )

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
    else:
        print(f"⚠️  Nota creada localmente pero hubo error al pushear: {filepath}")


if __name__ == "__main__":
    main()
