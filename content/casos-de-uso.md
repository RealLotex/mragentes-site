---
title: "Casos de uso de automatización para pymes"
key: "Casos de uso"
description: "Cuatro casos tipo de automatización para pymes: qué se automatiza, qué controla una persona y cómo verificar si el piloto aporta valor."
lede: "No son promesas ni resultados atribuidos a clientes: son casos tipo para diseñar un piloto pequeño, medible y con una persona responsable."
image: /faviconhand512.png
no_closer: false
---

Un caso de uso útil no empieza por una herramienta ni por la palabra “agente”. Empieza por una tarea repetida, una decisión que debe seguir siendo humana y una señal que permite comprobar si el cambio ayudó.

Los cuatro casos de esta página describen un diseño posible. No anuncian resultados de clientes ni reemplazan un relevamiento: sirven para decidir si conviene hacer una prueba acotada. Antes de automatizar, conviene registrar una semana de operación actual. Ese dato será la línea de base para evaluar el piloto.

## 1. Consultas comerciales que necesitan derivación

**Situación.** Una persona recibe consultas repetidas por WhatsApp, correo o formulario: horario, disponibilidad, cobertura, documentación necesaria. El problema no es responder una pregunta aislada; es no perder el caso que necesita una cotización, una excepción o información que el sistema no conoce.

**Diseño del piloto.** El sistema clasifica la consulta, propone una respuesta a preguntas verificadas y prepara una derivación cuando detecta una condición fuera de catálogo. La persona responsable revisa las derivaciones y conserva el control sobre precios, promesas comerciales y datos personales.

| Elemento | Definición verificable |
|---|---|
| Entrada | Consulta recibida en un canal definido |
| Regla | Responder solo con una base de conocimiento aprobada |
| Límite | No cotizar, negociar ni modificar pedidos |
| Salida | Respuesta aprobada o derivación con contexto |
| Evidencia | Categoría, fuente consultada, estado de la derivación |
| Métrica de piloto | Tiempo hasta primera respuesta y proporción de derivaciones correctas |

El piloto no se considera exitoso por responder mucho. Se considera útil si reduce esperas sin aumentar respuestas incorrectas o casos perdidos.

## 2. Facturas y remitos que hoy se transcriben

**Situación.** Llegan documentos con distintos formatos. Una persona lee proveedor, fecha, importe, número y otros campos para cargar la información en una planilla o sistema de gestión. El riesgo no es sólo la demora: un importe o número mal transcripto puede trasladarse al proceso siguiente.

**Diseño del piloto.** El sistema extrae un conjunto pequeño de campos, compara reglas simples —por ejemplo, que el importe sea positivo y que el número no esté duplicado— y envía a revisión los documentos con baja confianza o inconsistencias. No carga automáticamente lo que no puede justificar.

| Elemento | Definición verificable |
|---|---|
| Entrada | PDF o imagen de proveedor autorizado |
| Regla | Extraer únicamente los campos definidos para ese documento |
| Límite | No aprobar pagos ni alterar el documento original |
| Salida | Registro preparado o bandeja de revisión |
| Evidencia | Documento de origen, campo extraído, regla aplicada y revisión |
| Métrica de piloto | Minutos por documento, tasa de revisión y errores detectados |

Una prueba honesta incluye documentos difíciles: fotos torcidas, sellos, formatos nuevos y datos incompletos. Medir sólo documentos prolijos produce una estimación engañosa.

## 3. Alertas de operación antes de que el problema escale

**Situación.** El equipo tiene planillas, sistema de ventas o inventario, pero los problemas se detectan tarde: un artículo cae debajo del mínimo, una cuenta queda vencida o una venta se desvía del rango esperado.

**Diseño del piloto.** El sistema consulta fuentes acordadas en un horario conocido y compara los datos contra una regla explícita. La alerta informa qué valor cambió, contra qué umbral se evaluó y a quién corresponde revisarla. Una alerta no ejecuta compras, pagos ni cambios de precio.

| Elemento | Definición verificable |
|---|---|
| Entrada | Fuente de datos identificada y horario de actualización |
| Regla | Umbral, período de comparación y responsable definidos |
| Límite | Alertar; no ejecutar una decisión financiera |
| Salida | Aviso con dato, regla y enlace a la fuente |
| Evidencia | Valor observado, umbral aplicado y fecha de revisión |
| Métrica de piloto | Alertas útiles, falsos avisos y tiempo hasta revisión |

La señal correcta no es “más alertas”. Es una alerta que llega a la persona indicada con información suficiente para decidir.

## 4. Seguimiento de tareas administrativas repetitivas

**Situación.** Una tarea se repite cada semana: reunir archivos, detectar faltantes, pedir un dato y armar un resumen de pendientes. La información suele existir, pero queda distribuida entre correo, planillas y carpetas.

**Diseño del piloto.** El sistema prepara una lista de control basada en fuentes delimitadas y marca lo que falta. La persona confirma los casos ambiguos y define qué pendiente se cierra. El envío externo y los cambios en registros sensibles quedan sujetos a una aprobación explícita.

| Elemento | Definición verificable |
|---|---|
| Entrada | Fuentes y responsables documentados |
| Regla | Lista de requisitos y fecha de corte aprobadas |
| Límite | No borrar archivos ni cerrar tareas sin aprobación |
| Salida | Resumen de pendientes priorizados |
| Evidencia | Fuente por pendiente, fecha de consulta y decisión final |
| Métrica de piloto | Tiempo de preparación, pendientes detectados y retrabajo evitado |

## Cómo elegir el primer piloto

Elegí una tarea con cuatro propiedades:

1. Ocurre con frecuencia suficiente para observarla en pocas semanas.
2. Tiene una entrada reconocible: un mensaje, un documento, un cambio de dato o un horario.
3. Permite separar lo que el sistema prepara de lo que debe aprobar una persona.
4. Tiene una métrica de negocio simple: tiempo, error, demora, pendiente o retrabajo.

Si el proceso cambia todo el tiempo, nadie puede explicar la regla o no existe una persona responsable, todavía no es un buen candidato. Primero se aclara el proceso; después se automatiza.

Para estimar el tiempo que hoy consume una tarea, se puede usar la [calculadora de impacto](/calculadora-impacto/). Para revisar un circuito concreto, [escribinos](/contacto/): el primer objetivo no es automatizar más, sino demostrar control y valor en un tramo pequeño del proceso.
