#!/usr/bin/env python3
"""
Publicador diario MR Agentes — Hugo Website
Crea una nueva nota y hace push al repo.

Uso:
  python3 scripts/publish_daily.py [--title "Título opcional"] [--content "Contenido opcional"]

Si no se pasa título ni contenido, genera un post automático basado en el calendario
de Instagram o contenido generado por IA.
"""

import os
import sys
import json
import subprocess
import datetime
import re
import random

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTENT_DIR = os.path.join(BASE_DIR, "content", "notas")

# Calendario de contenido (sincronizado con Instagram)
CONTENT_CALENDAR = [
    {
        "title": "Automatización 101: por dónde empezar",
        "tags": ["automatizacion", "guia", "principiantes"],
        "body": """## ¿Por dónde empezar con la automatización?

Muchas empresas quieren automatizar procesos pero no saben por dónde arrancar. Acá te dejamos una guía simple en 3 pasos:

### 1. Identificá tareas repetitivas
Hacé una lista de todo lo que tu equipo hace más de 3 veces por semana que sea:
- Manual
- Repetitivo
- Propenso a errores humanos

### 2. Medí el tiempo invertido
Antes de automatizar, cuantificá cuánto tiempo se pierde. Si una tarea te lleva 10 horas por semana, automatizarla tiene alto ROI.

### 3. Priorizá por impacto
No intentes automatizar todo de una vez. Elegí el proceso que más tiempo consuma o más errores genere, y empezá por ahí.

> El 80% del beneficio de la automatización viene del 20% de los procesos.

¿Querés ayuda para identificar qué procesos automatizar? [Contactanos]({{< ref "contacto" >}}) y te hacemos un diagnóstico gratuito."""
    },
    {
        "title": "Chatbots con IA: mitos y verdades",
        "tags": ["chatbots", "ia", "atencion-al-cliente"],
        "body": """## Chatbots con IA: lo que escuchamos todos los días

Todavía hay mucha confusión sobre lo que los chatbots con inteligencia artificial pueden y no pueden hacer. Vamos a desmentir algunos mitos.

### ❌ Mito: "Los chatbots son robots fríos que no entienden nada"
**Verdad:** Los chatbots modernos con IA generativa entienden lenguaje natural, contexto y hasta emociones. No son los chatbots con guiones fijos de hace 10 años.

### ❌ Mito: "Implementar un chatbot es carísimo"
**Verdad:** Hoy existen soluciones accesibles para cualquier presupuesto. Además, el retorno de inversión suele verse en los primeros meses.

### ❌ Mito: "Los clientes prefieren hablar con personas siempre"
**Verdad:** Según estudios, el 60% de los usuarios prefiere resolver consultas simples con un chatbot antes que esperar en una línea telefónica.

### ✅ Realidad: La clave está en el balance
Un buen sistema de atención combina chatbot IA para lo rutinario + derivación inteligente a humanos cuando se necesita. No reemplaza, **potencia**.

¿Estás considerando un chatbot para tu negocio? [Escribinos]({{< ref "contacto" >}}) y te contamos cómo funcionaría en tu caso."""
    },
    {
        "title": "IA y productividad: números que importan",
        "tags": ["ia", "productividad", "datos"],
        "body": """## El impacto real de la IA en la productividad

No es futurismo: la inteligencia artificial ya está transformando empresas hoy. Mirá estos números:

### 📊 Lo que dicen los datos

- **40%** de las tareas administrativas se pueden automatizar hoy
- **3x** más rápido procesan documentos los sistemas con IA vs humanos
- **90%** menos errores en tareas de ingreso de datos
- **60%** de los clientes prefieren chatbots IA para consultas simples

### 🏢 Caso real: PyME de logística

Una empresa de logística con la que trabajamos automatizó su proceso de seguimiento de envíos:

```
Antes: 12 horas/semana en tracking manual
Después: 30 minutos/semana (revisión de excepciones)
Ahorro: 95% del tiempo
```

### 💡 La conclusión

Las empresas que adoptan IA no sólo ahorran tiempo: **toman mejores decisiones** porque tienen datos en tiempo real y liberan a su equipo para tareas de mayor valor.

¿Cuánto tiempo pierde tu equipo en tareas repetitivas? [Descubrilo con nosotros]({{< ref "contacto" >}})."""
    },
    {
        "title": "5 procesos contables que deberías automatizar ya",
        "tags": ["contabilidad", "automatizacion", "finanzas"],
        "body": """## Procesos contables: tiempo perdido vs. automatizado

El área contable de cualquier empresa está llena de tareas repetitivas que consumen horas valiosas. Acá los 5 procesos que deberías automatizar YA.

### 1. 📄 Facturación electrónica
Generación, envío y archivo automático de facturas. Sin errores de tipeo, sin facturas olvidadas.

### 2. 💰 Conciliación bancaria
Que un bot cruce tus movimientos bancarios con tu sistema contable. Lo que antes tomaba un día, ahora toma 10 minutos.

### 3. 📬 Gestión de cobranzas
Recordatorios automáticos por email/WhatsApp según el estado de cada cliente. Sin llamadas incómodas.

### 4. 🧾 Procesamiento de comprobantes
Escaneá un PDF o foto de factura → el bot extrae los datos y los carga en tu sistema.

### 5. 📊 Reportes periódicos
Informes de IVA, balance, resultados → generados y enviados automáticamente cada mes.

> El tiempo promedio que una PyME ahorra automatizando estos 5 procesos es de **20 horas semanales**.

¿Tu área contable sigue haciendo todo manual? [Contanos tu caso]({{< ref "contacto" >}}) y te mostramos cómo sería con automatización."""
    },
    {
        "title": "¿Qué es un agente IA y cómo puede ayudar a tu negocio?",
        "tags": ["ia", "agentes", "innovacion"],
        "body": """## Agentes IA: el siguiente nivel de automatización

Seguramente escuchaste hablar de "agentes IA" pero ¿sabés realmente qué son y cómo pueden transformar tu negocio?

### 🤔 ¿Qué es un agente IA?

Un agente IA es un sistema que **no solo ejecuta instrucciones**, sino que **toma decisiones autónomas** basadas en contexto y objetivos. Piensa en él como un empleado digital que:

- Entiende qué se le pide (lenguaje natural)
- Decide cómo hacerlo (planificación)
- Ejecuta acciones (integración con herramientas)
- Aprende de los resultados (mejora continua)

### 💼 Aplicaciones en tu negocio

| Área | Qué hace un agente IA |
|------|----------------------|
| Atención al cliente | Resuelve consultas, deriva casos complejos, hace seguimiento |
| Ventas | Califica leads, programa reuniones, envía propuestas |
| Operaciones | Monitorea procesos, detecta anomalías, genera alertas |
| RRHH | Preselecciona candidatos, programa entrevistas, responde dudas |

### 🏆 ¿Por qué es diferente a un bot común?

Un bot común sigue reglas fijas. Un agente IA **razona, se adapta y mejora**. Es como la diferencia entre un instructivo paso a paso y un colaborador que entiende el objetivo y busca la mejor forma de lograrlo.

¿Querés saber cómo implementar un agente IA en tu negocio? [Hablemos]({{< ref "contacto" >}})."""
    },
    {
        "title": "Automatización vs. desempleo: lo que nadie te cuenta",
        "tags": ["automatizacion", "empleo", "tendencias"],
        "body": """## Automatización: ¿enemiga del empleo?

Es el debate que siempre surge cuando hablamos de automatización e IA. Vamos a poner las cartas sobre la mesa.

### ❌ El miedo: "Los robots nos van a dejar sin trabajo"

Es entendible. Cada vez que hay un salto tecnológico, aparece el mismo miedo. Pasó con la revolución industrial, con Internet, con los smartphones.

### ✅ La realidad: la automatización transforma, no reemplaza

Los datos históricos muestran que la tecnología **crea más empleo del que destruye**, pero cambia la naturaleza del trabajo:

```
Tareas repetitivas → Automatización
Tareas creativas/estratégicas → Potenciación humana
```

### 🔄 Lo que realmente pasa

1. **Desaparecen tareas**, no puestos completos
2. **Aparecen nuevos roles**: gestor de automatización, prompt engineer, analista de datos
3. **Los equipos se vuelven más productivos**: la empresa crece y necesita más gente

### 🎯 Nuestra visión en MR Agentes

No vendemos automatización para reemplazar personas. La vendemos para que **tu equipo deje de hacer tareas que una máquina puede hacer** y se dedique a lo que realmente importa: crear, innovar y construir relaciones.

> El objetivo no es tener menos personas, sino que cada persona aporte más valor.

¿Cómo ves el impacto de la IA en tu rubro? [Contanos tu opinión]({{< ref "contacto" >}})."""
    },
]


def slugify(text):
    """Convertir texto a slug URL-friendly."""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    return text


def create_nota(title, body, tags):
    """Crear archivo de nota en content/notas/."""
    today = datetime.date.today()
    slug = slugify(title)
    filename = f"{today.isoformat()}-{slug}.md"
    filepath = os.path.join(CONTENT_DIR, filename)

    if os.path.exists(filepath):
        print(f"⚠️  Ya existe nota para hoy: {filename}")
        return None

    tags_yaml = "\n".join([f"  - {t}" for t in tags])
    content = f"""---
title: "{title}"
date: {today.isoformat()}
description: "Publicaci&oacute;n diaria de MR Agentes sobre automatizaci&oacute;n e IA."
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
        
        # Git add
        subprocess.run(["git", "add", filepath], check=True, capture_output=True)
        
        # Git commit
        commit_msg = f"📝 Nueva nota: {title}"
        subprocess.run(
            ["git", "commit", "-m", commit_msg],
            check=True, capture_output=True
        )
        
        # Git push
        result = subprocess.run(
            ["git", "push", "origin", "main"],
            check=True, capture_output=True, text=True
        )
        
        print(f"✅ Push exitoso: {commit_msg}")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Error en git: {e.stderr if e.stderr else e}")
        return False


def get_calendar_content():
    """Obtener contenido del calendario basado en el día."""
    today = datetime.date.today()
    # Usar día del mes como índice para rotar contenido
    day_index = (today.day - 1) % len(CONTENT_CALENDAR)
    return CONTENT_CALENDAR[day_index]


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Publicar nota diaria en MR Agentes website")
    parser.add_argument("--title", help="Título de la nota (opcional)")
    parser.add_argument("--content", help="Contenido de la nota en Markdown (opcional)")
    parser.add_argument("--dry-run", action="store_true", help="Solo crear el archivo, sin git push")
    args = parser.parse_args()

    # Si se pasa título y contenido, usarlos
    if args.title and args.content:
        title = args.title
        body = args.content
        tags = ["automatizacion", "ia"]
    else:
        entry = get_calendar_content()
        title = entry["title"]
        body = entry["body"]
        tags = entry["tags"]

    # Crear la nota
    filepath = create_nota(title, body, tags)
    
    if not filepath:
        print("ℹ️  No se creó contenido nuevo (ya existe para hoy)")
        return
    
    if args.dry_run:
        print(f"🏁 Dry run - archivo creado pero sin push: {filepath}")
        return
    
    # Commit y push
    success = git_commit_push(filepath, title)
    
    if success:
        print("🎉 Nota publicada exitosamente!")
    else:
        print("⚠️  Nota creada localmente pero hubo un error al pushear")
        print(f"   Archivo: {filepath}")


if __name__ == "__main__":
    main()
