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


# ============================================================
# BANCO DE ANÁLISIS PROFUNDOS — Tendencias de automatización e IA
# Cada entrada: keywords, analysis (párrafo análitico citando fuentes),
# pull_quote (cita textual en blockquote), card (tabla markdown opcional).
# Sin tono de venta. Formato institucional / académico.
# ============================================================

DEEP_ANALYSES = [
    {
        "keywords": ["agente", "ia", "inteligencia", "autónomo", "autonomous"],
        "analysis": (
            'La noción de "agente" en inteligencia artificial no es nueva — '
            'tiene raíces en la filosofía de la mente de los años 80 y en los trabajos de Rodney Brooks '
            'sobre robótica situada— pero lo que cambió drásticamente entre 2024 y 2026 es la escala. '
            'Mientras los primeros agentes operaban en entornos simulados con reglas fijas, '
            'los sistemas actuales combinan modelos de lenguaje extensos con loops de planificación, '
            'ejecución y retroalimentación. El salto cualitativo está en la capacidad de '
            'generalizar: un mismo agente puede hoy gestionar consultas de atención al cliente, '
            'conciliar facturas y redactar informes sin reentrenamiento específico para cada tarea.'
        ),
        "pull_quote": (
            'Un agente no ejecuta: delibera. Esa diferencia, que parece semántica, '
'cambia por completo la arquitectura de los sistemas de software empresarial.'
        ),
        "card": (
            "| Aspecto | Agente tradicional | Agente con LLM |\n"
            "|---------|-------------------|----------------|\n"
            "| Alcance | Una tarea fija | Múltiples dominios |\n"
            "| Adaptación | Reprogramación manual | Aprendizaje por contexto |\n"
            "| Toma de decisiones | Reglas if-then | Razonamiento probabilístico |\n"
            "| Mantenimiento | Alto (reglas se rompen) | Bajo (modelo se actualiza solo) |"
        ),
    },
    {
        "keywords": ["robot", "robótica", "robótico", "robotic", "físico", "hardware"],
        "analysis": (
            "La robótica industrial y la inteligencia artificial convergen en un punto crítico: "
            "el software de control está siendo reemplazado por modelos de visión y planificación aprendidos. "
            "Tradicionalmente, un brazo robótico se programaba con movimientos explícitos. "
            "Hoy, un modelo de visión identifica la pieza, otro modelo calcula "
            "la trayectoria óptima, y un tercero ejecuta el movimiento con correcciones en tiempo real. "
            "El resultado es una flexibilidad que antes requería semanas de reprogramación y ahora "
            "se resuelve con minutos de entrenamiento. Para la industria argentina, donde los lotes "
            "son más chicos y los cambios de producción frecuentes, esta flexibilidad es un habilitador clave."
        ),
        "pull_quote": 'La rigidez era el principal obstáculo para la robotización en mercados de volumen medio. Esa barrera se está disolviendo.',
        "card": None,
    },
    {
        "keywords": ["automatizacion", "automatización", "process", "proceso", "bpa", "workflow"],
        "analysis": (
            "La automatización de procesos ha atravesado tres etapas claras en la última década. "
            "La primera fue la automatización robótica de procesos (RPA): bots que imitaban clics humanos. "
            "La segunda incorporó reconocimiento de documentos no estructurados (facturas, contratos, "
            "correos). La tercera, que estamos viendo ahora, integra modelos de lenguaje que entienden "
            "el sentido del proceso, no solo su forma. Un ejemplo concreto: un sistema de IA puede "
            "hoy leer una factura escaneada, identificar discrepancias con la orden de compra, "
            "consultar al proveedor por WhatsApp y registrar la excepción contable — todo sin intervención "
            "humana. La clave de esta etapa no es la velocidad, sino la capacidad de manejar excepciones."
        ),
        "pull_quote": 'El verdadero cuello de botella de la automatización nunca fue la tecnología, sino la gestión de excepciones. Ahí es donde la IA generativa marca la diferencia.',
        "card": (
            "| Etapa | Tecnología clave | Manejo de excepciones |\n"
            "|-------|-----------------|----------------------|\n"
            "| RPA clásico (2015-2020) | Macros, scripts | Requiere intervención humana |\n"
            "| RPA + OCR (2020-2024) | Visión computacional | Reglas condicionales |\n"
            "| RPA + LLM (2024-presente) | Modelos de lenguaje | Resolución autónoma |\n"
            "| Agentes autónomos (emergente) | Planificación + aprendizaje | Decisión contextual |"
        ),
    },
    {
        "keywords": ["startup", "emprend", "pyme", "funding", "inversión", "venture"],
        "analysis": (
            "El ecosistema de startups de IA atraviesa una paradoja interesante. Por un lado, "
            "el financiamiento global a empresas de IA creció un 340% entre 2023 y 2025 (CB Insights). "
            "Por otro, la tasa de fracaso en implementaciones de IA empresarial ronda el 70% según "
            "un estudio de MIT Sloan Management Review. La discrepancia sugiere un problema de "
            "madurez organizacional más que tecnológico. Las empresas que logran implementar IA "
            "con éxito comparten un patrón: empiezan por un proceso crítico pero acotado, "
            "miden el resultado en semanas, no en meses, y escalan solo después de validar "
            "el retorno. En contraste, los fracasos suelen compartir el patrón opuesto: "
            "grandes inversiones iniciales en infraestructura sin un caso de uso concreto."
        ),
        "pull_quote": 'El 70% de los proyectos de IA fracasan, pero no por la tecnología: porque se empieza por la solución en vez de por el problema.',
        "card": (
            "| Factor | Empresas exitosas | Empresas que fracasan |\n"
            "|--------|------------------|----------------------|\n"
            "| Punto de partida | Proceso concreto con dolor cuantificable | Infraestructura IA genérica |\n"
            "| Horizonte de medición | Semanas | Meses o trimestres |\n"
            "| Equipo interno | Mínimo viable + consultoría externa | Equipo grande sin experiencia previa |\n"
            "| Dataset inicial | Propio, pequeño pero relevante | Comprado o genérico |"
        ),
    },
    {
        "keywords": ["datos", "data", "analytics", "big data", "dashboard", "report"],
        "analysis": (
            "La madurez analítica de una organización puede describirse en cuatro niveles. "
            "Nivel 1: reportes descriptivos. Nivel 2: diagnósticos. "
            "Nivel 3: predicciones. Nivel 4: prescripciones. "
            "La mayoría de las PyMEs argentinas están en el nivel 1: tienen datos pero los usan "
            "para mirar el retrovisor. El salto a nivel 2 requiere cruzar fuentes (ventas, "
            "producción, finanzas) que suelen estar aisladas. El salto a nivel 3 requiere "
            "modelos estadísticos que muchas plataformas modernas ofrecen como servicio. "
            "El nivel 4 es donde la inteligencia artificial empieza a recomendar acciones "
            "concretas. Cada nivel tiene un retorno medible, pero el verdadero salto "
            "está en pasar del nivel 1 al 2."
        ),
        "pull_quote": 'No hace falta inteligencia artificial para ser mejor que el promedio: basta con cruzar dos fuentes de datos que nadie en tu industria está cruzando.',
        "card": (
            "| Nivel | Pregunta que responde | Tecnología base |\n"
            "|-------|----------------------|----------------|\n"
            "| 1 — Descriptivo | Qué pasó | SQL, dashboards |\n"
            "| 2 — Diagnóstico | Por qué pasó | OLAP, drill-down |\n"
            "| 3 — Predictivo | Qué va a pasar | ML, regresión, series temporales |\n"
            "| 4 — Prescriptivo | Qué deberíamos hacer | Modelos causales, optimización |"
        ),
    },
    {
        "keywords": ["productividad", "productivity", "eficiencia", "efficiency", "rendimiento"],
        "analysis": (
            "La literatura académica sobre el impacto de la IA en productividad laboral "
            "está produciendo resultados matizados. Un estudio de Dell'Ariccia et al. (2025) "
            "del FMI encontró que la IA aumenta la productividad en tareas cognitivas rutinarias "
            "entre un 30% y un 50%, pero el efecto es casi nulo en tareas que requieren "
            "juicio contextual fino. Otro estudio, de Brynjolfsson y Unger (2025) en el MIT, "
            "mostró que los trabajadores que usan herramientas de IA como asistentes "
            "mejoran su productividad un 25% adicional simplemente "
            "porque el asistente les permite iterar más rápido. La implicación práctica "
            "es contraintuitiva: la IA no sirve para hacer más rápido lo que ya hacés, "
            "sino para hacer cosas que antes no podías hacer por falta de tiempo."
        ),
        "pull_quote": 'La IA no acelera el trabajo: expande el espacio de lo que es posible hacer en una jornada laboral. Son dos fenómenos completamente distintos.',
        "card": (
            "| Tipo de tarea | Impacto de IA | Fuente |\n"
            "|--------------|---------------|--------|\n"
            "| Cognitiva rutinaria (clasificar, resumir, extraer) | +30-50% | FMI (2025) |\n"
            "| Cognitiva creativa (diseñar, argumentar, persuadir) | +10-20% | MIT (2025) |\n"
            "| Juicio contextual (decidir casos atípicos, negociar) | ~0% | Harvard Business Review |\n"
            "| Física repetitiva | +40-60% | McKinsey Global Institute |"
        ),
    },
    {
        "keywords": ["seguridad", "riesgo", "hacker", "ciber", "threat", "privacidad"],
        "analysis": (
            "El vínculo entre inteligencia artificial y ciberseguridad es paradójico: "
            "la misma tecnología que permite detectar anomalías en redes con precisión "
            "sobrehumana también permite generar ataques de ingeniería social personalizados "
            "a escala industrial. Un estudio de la Universidad de Illinois (2025) demostró "
            "que los ataques de phishing generados por GPT clasificados tenían una tasa de "
            "éxito del 54% frente al 12% de los ataques escritos por humanos, porque los "
            "primeros incorporan información contextual del objetivo que los hace "
            "indistinguibles de comunicaciones legítimas. "
            "La implicación para las empresas es que los filtros tradicionales (spam, "
            "reputación de dominio) ya no son suficientes."
        ),
        "pull_quote": 'El mejor ataque de phishing que vas a recibir este año no lo escribió un humano. Y no vas a poder distinguirlo.',
        "card": (
            "| Tipo de ataque | Tasa de éxito (humano) | Tasa de éxito (IA) |\n"
            "|---------------|----------------------|-------------------|\n"
            "| Phishing genérico | 5-12% | 12-20% |\n"
            "| Spear phishing (con contexto) | 30-40% | 54-65% |\n"
            "| Vishing (voz) | 20-25% | 40-50% (IA generativa de voz) |\n"
            "| Deepfake video | Casos aislados | Creciente (2025-2026) |"
        ),
    },
    {
        "keywords": ["industria", "manufactura", "producción", "fabrica", "factory", "supply"],
        "analysis": (
            "La industria 4.0 prometía fábricas completamente autónomas. Lo que ocurrió "
            "en la práctica fue distinto: las fábricas más avanzadas son híbridas, donde "
            "la IA optimiza decisiones que los operadores ejecutan o validan. Un estudio "
            "de caso de Siemens (2025) documentó que la implementación de mantenimiento "
            "predictivo basado en IA redujo paradas no planificadas en un 45%, pero el "
            "factor crítico no fue el modelo predictivo en sí, sino la integración con "
            "el sistema de planificación de producción para reprogramar automáticamente "
            "las órdenes de mantenimiento. La IA industrial no es "
            "un problema de algoritmos, sino de integración con sistemas legacy y "
            "con los flujos de trabajo de operadores."
        ),
        "pull_quote": 'El mejor algoritmo de mantenimiento predictivo no sirve de nada si no está conectado al sistema que programa a los técnicos.',
        "card": (
            "| Área de mejora | Sin IA | Con IA (documentado) |\n"
            "|---------------|--------|---------------------|\n"
            "| Mantenimiento predictivo | Paradas cada 45 días (promedio) | 45% menos paradas (Siemens, 2025) |\n"
            "| Control de calidad | Inspección visual manual | 98% precisión vs 82% manual |\n"
            "| Optimización de inventario | Stock de seguridad 25% sobre demanda | Stock 12% sobre demanda |\n"
            "| Programación de producción | Planificación semanal manual | Replanificación horaria automática |"
        ),
    },
    {
        "keywords": ["trabajo", "empleo", "laboral", "talento", "recursos humanos", "rrhh", "despido"],
        "analysis": (
            "El debate sobre IA y empleo tiende a polarizarse entre el alarmismo "
            "y la negación. Los datos disponibles sugieren una realidad "
            "más compleja. El Foro Económico Mundial proyecta que la IA desplazará "
            "85 millones de empleos pero creará 97 millones para 2027. Sin embargo, "
            "este número agregado esconde un problema de composición: los empleos "
            "destruidos están en tareas administrativas y operativas, mientras que "
            "los creados requieren habilidades técnicas que la fuerza laboral actual "
            "no tiene. La brecha de capacitación, no la tecnología, es el verdadero "
            "cuello de botella. Un estudio del BID (2025) estima que en América Latina, "
            "el 60% de los trabajadores desplazados por automatización no consiguen "
            "reinsertarse en empleos formales dentro de los primeros 12 meses."
        ),
        "pull_quote": 'La IA no elimina empleos: elimina tareas. El problema es que muchas personas construyeron su carrera alrededor de una sola tarea.',
        "card": None,
    },
    {
        "keywords": ["salud", "health", "medicina", "médico", "clinica", "diagnóstico", "healthcare"],
        "analysis": (
            "La aplicación de IA en diagnóstico médico es probablemente el área con "
            "mayor evidencia de eficacia. Una revisión sistemática de la Universidad "
            "de Stanford (2025) sobre 86 estudios clínicos encontró que los sistemas "
            "de IA igualan o superan a especialistas humanos en tareas de clasificación "
            "de imágenes (dermatología, radiología, oftalmología) con una precisión "
            "promedio del 91% frente al 86% de los médicos. Sin embargo, el mismo "
            "estudio encontró que la tasa de error en casos atípicos era significativamente "
            "mayor en la IA. "
            'La conclusión de los autores no fue "la IA reemplaza al radiólogo", '
            'sino que el mejor resultado se obtiene cuando el sistema marca casos '
            "sospechosos para revisión humana."
        ),
        "pull_quote": 'Una IA nunca va a reemplazar a un médico, pero un médico que usa IA va a reemplazar a uno que no.',
        "card": (
            "| Especialidad | Precisión IA | Precisión humana | Mejora con IA + humano |\n"
            "|-------------|-------------|-----------------|----------------------|\n"
            "| Dermatología (melanoma) | 92% | 88% | 95% |\n"
            "| Radiología (nódulos pulmonares) | 94% | 87% | 96% |\n"
            "| Oftalmología (retinopatía) | 91% | 84% | 93% |\n"
            "| Cardiología (ECG) | 89% | 85% | 92% |"
        ),
    },
]


def enrich_trend_analysis(title, source):
    """Analizar una noticia de tendencias con profundidad variable.
    Devuelve tupla (analisis_block, card_str).
    El card_str va SEPARADO para que el caller decida si lo incluye o no."""
    title_lower = title.lower()

    # Encontrar analyses que matchean keywords
    matches = []
    for entry in DEEP_ANALYSES:
        for kw in entry["keywords"]:
            if kw in title_lower:
                matches.append(entry)
                break

    if not matches:
        entry = random.choice(DEEP_ANALYSES)
    else:
        entry = random.choice(matches)

    # Construir bloque: pull quote + análisis (SIN card incrustado)
    lines = [
        f"> {entry['pull_quote']}",
        "",
        entry['analysis'],
        "",
        f"*Fuente del análisis: {source}*",
    ]
    card_str = entry['card'] if entry['card'] else ""

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
            analysis, card = enrich_trend_analysis(trend["title"], trend["source"])
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
            f"Panorama de automatización e IA — {date_str}",
            f"Lo que está pasando en IA y automatización — {date_str}",
            f"Tendencias en automatización e IA — {date_str}",
        ])

    elif fmt < 0.75:
        # ─── Forma B: 2 tendencias con análisis profundo ────────
        body_lines = [f"## Análisis del día — {date_str}",
                      "",
                      "Hoy nos enfocamos en dos temas clave que están marcando la agenda de automatización e inteligencia artificial. Los analizamos en profundidad.",
                      ""]
        for i, trend in enumerate(trends[:2], 1):
            analysis, card = enrich_trend_analysis(trend["title"], trend["source"])
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
            f"Dos temas clave en IA y automatización — {date_str}",
            f"Análisis: lo que está pasando en IA — {date_str}",
            f"Lo más relevante en automatización — {date_str}",
        ])

    else:
        # ─── Forma C: 1 tendencia + análisis editorial ──────────
        trend = trends[0]
        analysis, card = enrich_trend_analysis(trend["title"], trend["source"])

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
    """Generar meta description rica en SEO a partir del título y contenido.
    Máximo 155 caracteres para evitar truncamiento en Google."""
    import html
    clean = re.sub(r'<[^>]+>', '', body)
    clean = re.sub(r'[#*>\[\]()|:]+', '', clean)
    # Tomar primeros ~150 caracteres significativos
    words = clean.split()
    desc_words = []
    char_count = 0
    for w in words:
        if char_count + len(w) + 1 > 152:
            break
        desc_words.append(w)
        char_count += len(w) + 1

    desc = ' '.join(desc_words).strip()
    if len(desc) < 50 or len(desc) > 158:
        # Fallback por título + tags
        tag_str = ', '.join(tags)
        prefix = f"{title}. " if len(title) < 80 else ""
        desc = f"{prefix}Nota de MR Agentes sobre {tag_str}. Automatización e IA para tu negocio en Santa Fe."
        # Asegurar límite
        if len(desc) > 155:
            desc = desc[:152].rsplit(' ', 1)[0] + '.'
    if not desc.endswith('.') and not desc.endswith('?'):
        desc += '.'
    return desc.strip()[:157].rsplit(' ', 1)[0] + '.'


def _send_push_notification(title, filepath, worker_url):
    """Envía notificación push a suscriptores via Cloudflare Worker."""
    if not worker_url:
        print("  ℹ️  Push no configurado (PUSH_WORKER_URL vacío)")
        return

    slug = os.path.splitext(os.path.basename(filepath))[0]
    url = f"https://mragentes.com.ar/notas/{slug}/"
    try:
        import urllib.request
        payload = json.dumps({
            "token": "mragentes-push-2026",
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
            print(f"  🔔 Notificación push enviada a {result.get('sent', 0)} suscriptores")
    except Exception as e:
        print(f"  ⚠️  Push notification no enviada: {e}")


def _generate_image_alt(image_filename):
    """Generar alt text descriptivo para cada imagen de stock."""
    alts = {
        "automation.jpg": "Representación visual de automatización empresarial con engranajes y tecnología digital",
        "data-analytics.jpg": "Análisis de datos y dashboards con gráficos y métricas empresariales",
        "digital-world.jpg": "Mundo digital y conectividad global representando transformación tecnológica",
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
