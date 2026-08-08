---
title: Servicios
key: Fichas
description: Automatización de procesos, agentes de atención por WhatsApp, lectura
  de documentos y tableros de control para pymes de Santa Fe. Presupuesto cerrado
  por proyecto y las cuentas a tu nombre.
lede: Cuatro tipos de trabajo. Cada uno con lo que incluye, con qué se construye,
  qué necesito de tu lado, cuánto tarda y en qué casos conviene no hacerlo.
image: /images/mragentes.png
---

Casi ningún proyecto es uno solo de estos cuatro: lo habitual es que una parte sea
automatización, otra parte atención y otra parte tablero. Se cotizan juntos, como un
proyecto, no como una suma de módulos.

## Automatización de procesos

La tarea que alguien hace todos los días, siempre igual, abriendo tres pestañas.
Se define el circuito una vez y pasa a ejecutarse solo: cuando llega un mail, cuando
se cierra una venta, cuando son las 8 de la mañana del lunes.

Los casos más frecuentes son emisión y envío de comprobantes, sincronización entre
una planilla y el sistema de gestión, alta de clientes en varios sistemas a la vez, y
el reporte periódico que alguien arma a mano.

{{< ficha
    titulo="Ficha 01 — automatización de procesos"
    incluye="Relevamiento del circuito actual, construcción del flujo, conexión con los sistemas que ya usás, manejo de errores (qué pasa cuando un servicio no responde) y documentación escrita de cómo funciona."
    herramientas="n8n como motor principal. Make o Zapier cuando el cliente ya los tiene pagos. Conexión por API con lo que haya: sistema de gestión, facturador, planillas, correo."
    aporta="Un acceso a los sistemas involucrados y una persona del equipo que conozca la tarea de verdad — normalmente quien la hace, no quien la supervisa."
    plazo="De una a tres semanas para un circuito. Los proyectos con varios circuitos encadenados se entregan por partes."
    nosirve="Si el proceso cambia todos los meses o todavía no está definido. Automatizar algo que se está discutiendo sale caro dos veces: primero se construye y después se tira." >}}

## Agentes de atención

Un agente que atiende por WhatsApp o desde el sitio, con la información real del
negocio cargada: horarios, precios, condiciones, estado del pedido.

La diferencia con un chatbot de árbol de opciones es que entiende la pregunta escrita
como la escribe un cliente, con errores de tipeo y sin elegir del menú. La diferencia
con dejar un modelo suelto es que está acotado a lo que sabe, y cuando no sabe lo dice
y pasa la conversación a una persona con todo el historial adelante.

Desde agosto de 2026 el Reglamento europeo de IA exige que un sistema conversacional
avise que es un sistema. Todos los agentes se entregan identificándose, acá y allá —
en la práctica, además, [genera más confianza que disimularlo](/notas/).

{{< ficha
    titulo="Ficha 02 — agentes de atención"
    incluye="Carga de la base de conocimiento con la información del negocio, definición de qué puede y qué no puede responder, derivación a una persona con el historial de la charla, y un registro de las consultas que no supo contestar para ir corrigiéndolo."
    herramientas="API oficial de WhatsApp Business, modelos de lenguaje de OpenAI, n8n para la orquestación. Widget para el sitio cuando hace falta."
    aporta="La información que hoy tenés dispersa (lista de precios, horarios, preguntas frecuentes reales) y una persona que reciba las derivaciones."
    plazo="De dos a cuatro semanas, más una o dos de ajuste con conversaciones reales. Un agente no queda fino el primer día: queda fino después de leer lo que la gente le pregunta."
    nosirve="Si el volumen de consultas es bajo y variado. Cuando son diez mensajes por día y cada uno es distinto, el agente resuelve poco y conviene invertir en otra cosa." >}}

## Lectura de documentos

Remitos, facturas de proveedor y órdenes de compra que hoy alguien transcribe a mano.
Entran como PDF o como foto sacada con el teléfono, se extraen los campos y salen
cargados en el sistema.

El punto importante es qué pasa con lo dudoso: cuando la extracción no tiene
confianza suficiente, el documento no se carga con datos inventados. Va a una bandeja
de revisión. Es menos vistoso en una demo y es la única forma de que sirva en
producción.

{{< ficha
    titulo="Ficha 03 — lectura de documentos"
    incluye="Definición de los campos a extraer, procesamiento de PDF e imágenes, umbral de confianza y bandeja de revisión manual, carga al sistema destino y control de duplicados."
    herramientas="Modelos de extracción de documentos, n8n para el circuito, conexión al sistema de gestión."
    aporta="Entre veinte y cincuenta documentos de muestra, incluidos los feos: escaneados torcidos, con sello encima, de proveedores que usan un formato propio."
    plazo="De dos a cuatro semanas. La mayor parte del tiempo se va en los formatos raros, no en los prolijos."
    nosirve="Si son menos de veinte o treinta documentos por mes. Por debajo de ese volumen, el tiempo de revisar lo que el sistema marca como dudoso se parece bastante al de cargarlos a mano." >}}

## Tableros y alertas

Menos vistoso que lo anterior y, en varios negocios, lo que más cambia el día a día.

Un tablero con los números que se miran de verdad, actualizado solo. Y sobre todo
alertas: avisos que llegan cuando un número se sale del rango en vez de esperar a que
alguien entre a mirar. Stock por debajo del mínimo, una factura vencida hace más de
treinta días, ventas de la semana por debajo de la anterior.

{{< ficha
    titulo="Ficha 04 — tableros y alertas"
    incluye="Unificación de las fuentes de datos, limpieza, tablero actualizado automáticamente y reglas de alerta con su canal de envío (WhatsApp o correo)."
    herramientas="Planillas conectadas, bases de datos, n8n. Tablero en la herramienta que ya uses; si no usás ninguna, se define en el relevamiento."
    aporta="Acceso a las fuentes y una definición clara de qué números importan. Ésta suele ser la parte difícil, y la charlamos juntos."
    plazo="De una a dos semanas para un tablero con sus alertas."
    nosirve="Si los datos de origen están mal cargados. Un tablero no corrige datos malos: los muestra más rápido y con mejor tipografía." >}}

## Cómo se cobra

**Presupuesto cerrado por proyecto.** No trabajo por hora: el número que figura en el
presupuesto es el que se factura. Si me lleva más tiempo del que calculé, es problema
mío, no tuyo.

**Las cuentas de las plataformas van a tu nombre.** n8n, la API de WhatsApp, OpenAI y
cualquier otro servicio los contratás y los pagás vos, al precio de lista, con tu
tarjeta. No revendo licencias ni cobro comisión sobre eso. Lo que cobro es el trabajo
de construir e integrar.

**El mantenimiento se decide al final, no al principio.** Cuando el sistema está
andando y ya sabés cuánto lo usás, elegís entre un acuerdo mensual o llamarme sólo
cuando haga falta.

No publico una lista de precios porque no la tengo: dos proyectos que se describen con
la misma frase pueden tener cuatro veces de diferencia según cuántos sistemas haya que
tocar. El presupuesto sale entre tres y siete días después de la primera charla, es
por escrito, y no se cobra.
