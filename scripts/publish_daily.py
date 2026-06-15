#!/usr/bin/env python3
"""
Publicador diario MR Agentes — Hugo Website + Investigación Online
Crea una nueva nota con imagen única y hace push al repo.

Reglas:
  - 1 de cada 5 posteos investiga tendencias online reales + análisis propio
  - No repetir imágenes hasta agotar el catálogo (~5 imágenes = ~5 días sin repetir)
  - Siempre aportar valor analizado, no solo titulares
  - Tags, slug y front matter generados automáticamente

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
    "automation.jpg",
    "data-analytics.jpg",
    "digital-world.jpg",
]

# Agrego auto-resize feature: si hay más imágenes en el futuro, se agregan acá.
# La imagen ai-brain.jpg NO está porque se usó en bienvenidos-a-mr-agentes.md.
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


def pick_image(state):
    """Elegir imagen de stock sin repetir hasta agotar el catálogo."""
    available = [img for img in STOCK_IMAGES if img not in state.get("used_images", [])]

    # Si todas se usaron, reiniciar ciclo
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


def enrich_trend_analysis(title, source):
    """Devolver análisis propio MR Agentes según el tema de la noticia."""
    title_lower = title.lower()

    if "agente" in title_lower and ("ia" in title_lower or "inteligencia" in title_lower):
        return (
            "Los agentes IA son el próximo gran salto en automatización. "
            "A diferencia de los chatbots tradicionales, estos sistemas pueden planificar, ejecutar y aprender "
            "de forma autónoma. En MR Agentes ya estamos trabajando con implementaciones de agentes "
            "para atención al cliente y procesos administrativos, y los resultados en productividad "
            "son contundentes. La clave está en empezar con un caso de uso acotado y escalar desde ahí."
        )
    elif "automatizacion" in title_lower or "automatización" in title_lower:
        return (
            "La automatización de procesos ya no es un lujo, es una necesidad competitiva. "
            "Las empresas que automatizan tareas repetitivas liberan hasta un 40% del tiempo de su equipo "
            "para actividades estratégicas. Desde nuestra experiencia trabajando con PyMEs, "
            "los procesos más rentables para automatizar son facturación, conciliación bancaria "
            "y atención al cliente."
        )
    elif "startup" in title_lower or "pyme" in title_lower or "emprend" in title_lower:
        return (
            "Las PyMEs tienen una ventaja frente a las grandes empresas: pueden adoptar tecnología "
            "más rápido. Mientras una corporación tarda meses en implementar un cambio, una PyME "
            "puede hacerlo en semanas. Eso sí, hay que elegir bien las herramientas y evitar "
            "la trampa de comprar software que no se termina usando. Nuestro enfoque es siempre "
            "empezar por el proceso que más dolor genera."
        )
    elif "datos" in title_lower or "data" in title_lower or "analytics" in title_lower:
        return (
            "Los datos son el petróleo del siglo XXI, pero solo valen si se transforman en decisiones. "
            "Muchas empresas recolectan datos pero no los aprovechan porque falta la capa de análisis "
            "automatizado. Un dashboard bien diseñado puede mostrar en segundos lo que antes llevaba "
            "días de análisis manual. El reporting automatizado es de las inversiones con mejor "
            "relación costo-beneficio."
        )
    elif "productividad" in title_lower or "productivity" in title_lower:
        return (
            "El aumento de productividad que promete la IA no es teoría: lo vemos todos los días "
            "en nuestros clientes. Cuando un proceso que tomaba 10 horas semanales se reduce a 30 minutos, "
            "el equipo no solo gana tiempo: gana motivación al dejar atrás tareas tediosas. "
            "La productividad real viene de liberar potencial humano, no de exprimir horas de trabajo."
        )
    else:
        return (
            "Esta tendencia confirma lo que vemos en el día a día: la tecnología avanza rápido "
            "y las empresas que se quedan atrás pierden competitividad. Pero no hace falta "
            "adoptar todo lo nuevo de golpe. Nuestra recomendación es siempre la misma: "
            "identificá el proceso que más tiempo te consuma, midié cuánto te cuesta, y empezá por ahí."
        )


def generate_trends_post(state):
    """Generar un post basado en investigación online con análisis propio."""
    print("🔍 Investigando tendencias online...")
    trends = fetch_web_trends()

    if not trends:
        print("  ⚠️  No se pudieron obtener tendencias. Usando post genérico del calendario.")
        return None

    today = datetime.date.today()
    month_names = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
                   "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
    date_str = f"{today.day} de {month_names[today.month - 1]}"

    body = f"""## Lo que está pasando en automatización e IA — {date_str}

Todas las semanas revisamos las noticias más relevantes del mundo de la automatización y la inteligencia artificial, y las analizamos para darte nuestra perspectiva. Esto es lo que vimos esta semana:

"""
    for i, trend in enumerate(trends, 1):
        analysis = enrich_trend_analysis(trend["title"], trend["source"])
        body += f"""### 📰 {trend['title']}
*{trend['source']}*

{analysis}

[Ver artículo original]({trend['url']})

"""

    body += """### 💡 Nuestra recomendación de esta semana

No hace falta adoptar todo lo nuevo. La estrategia correcta es elegir una tendencia, validar si aplica a tu negocio y empezar con un piloto chico. En MR Agentes te ayudamos a separar el ruido de lo que realmente agrega valor.

¿Querés saber cómo aplicar alguna de estas tendencias en tu negocio? [Contactanos](/contacto/) y lo vemos juntos.

*Este contenido se basa en noticias y fuentes públicas. Recomendamos verificar la información en las fuentes originales.*"""

    title = f"Tendencias en automatización e IA — {date_str}"
    tags = ["tendencias", "ia", "automatizacion", "noticias"]
    image = pick_image(state)

    return {"title": title, "image": image, "tags": tags, "body": body}


def get_daily_content(state):
    """Obtener contenido del día, con 1 de cada 5 posteos siendo investigación online."""
    today = datetime.date.today()
    day_number = today.day

    # Cada 5 días (5, 10, 15, 20, 25, 30): post con investigación online
    if day_number % 5 == 0:
        result = generate_trends_post(state)
        if result:
            return result

    # Contenido del calendario rotativo
    topic_index = state.get("topic_index", 0)
    entry = TOPICS[topic_index % len(TOPICS)]

    # Avanzar índice para próxima vez
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
    content = f"""---
title: "{title}"
date: {today.isoformat()}
description: "Nota de MR Agentes sobre automatizaci&oacute;n e inteligencia artificial."
image: "{STOCK_IMAGES_DIR}{image}"
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


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Publicar nota diaria en MR Agentes website")
    parser.add_argument("--dry-run", action="store_true", help="Solo crear el archivo, sin git push")
    parser.add_argument("--force", action="store_true", help="Forzar publicación aunque ya exista nota hoy")
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
        # Si generate_trends_post falló, fallback a tema del calendario
        print("  ⚠️  Falló tendencias, usando tema del calendario")
        topic_index = state.get("topic_index", 0)
        t = TOPICS[topic_index % len(TOPICS)]
        state["topic_index"] = (topic_index + 1) % len(TOPICS)
        image = pick_image(state)
        save_state(state)
        entry = {"title": t["title"], "image": image, "tags": t["tags"], "body": t["body"]}

    if "tendencias" in entry.get("tags", []):
        print("  📰 Post basado en investigación online de tendencias + análisis propio")
    else:
        print(f"  📖 Tema: {entry['title']}")

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

    # Commit y push
    print("⬆️  Pusheando a GitHub...")
    success = git_commit_push(filepath, entry["title"])

    if success:
        print(f"🎉 Nota publicada exitosamente: {entry['title']}")
    else:
        print(f"⚠️  Nota creada localmente pero hubo error al pushear: {filepath}")


if __name__ == "__main__":
    main()
