---
schema_version: 1
title: "El ataque con agentes de IA que alcanzó al menos 15 entidades de salud en Argentina"
date: "2026-10-27T00:00:00-03:00"
description: "CrowdStrike describe una campaña entre mayo y agosto: hubo robo de credenciales e historias clínicas en al menos una entidad, pero no identificó a las víctimas."
image: "/images/stock/el-ataque-con-agentes-de-ia-que-alcanzo-al-menos-15-entidades-de-salud-en-argentina.png"
image_alt: "Ilustración conceptual de dos agentes de IA conectados con registros médicos y una red de salud sobre un mapa estilizado de Argentina; no representa un incidente real."
tags:
  - "ia"
  - "ciberseguridad"
  - "salud"
  - "argentina"
  - "agentes"
pillar: "automatizacion-practica"
learning_level: "inicial"
sources:
  - "https://www.crowdstrike.com/en-us/blog/crowdstrike-uncovers-new-agentic-ai-campaigns/"
  - "https://www.clarin.com/tecnologia/crecen-ciberataque-agentes-ia-argentina-vulneraron-15-entidades-salud-robaron-historias-clinicas_0_E48IKoPlfw.html"
automation_id: "blog:2026-10-27:el-ataque-con-agentes-de-ia-que-alcanzo-al-menos-15-entidades-de-salud-en-argentina"
slug: "el-ataque-con-agentes-de-ia-que-alcanzo-al-menos-15-entidades-de-salud-en-argentina"
draft: false
aliases: []
---

Al menos 15 entidades de salud de Argentina fueron comprometidas en una campaña que usó agentes de inteligencia artificial; en al menos una, el atacante robó credenciales e historias clínicas. Así lo sostiene CrowdStrike, que publicó el hallazgo el 21 de octubre sobre actividad registrada entre mayo y agosto de 2026. La empresa no identificó a las víctimas ni dijo que se hubieran robado historias clínicas de las 15. [El informe original](https://www.crowdstrike.com/en-us/blog/crowdstrike-uncovers-new-agentic-ai-campaigns/) y [la reconstrucción de Clarín](https://www.clarin.com/tecnologia/crecen-ciberataque-agentes-ia-argentina-vulneraron-15-entidades-salud-robaron-historias-clinicas_0_E48IKoPlfw.html) permiten separar lo documentado de lo que todavía se desconoce.

La pista apareció, según CrowdStrike, porque los propios atacantes dejaron abiertos en internet directorios con las herramientas de la operación. Los investigadores pudieron reconstruir parte de las instrucciones que recibió la IA, sus respuestas y las acciones que siguieron. Clarín entrevistó a Marcos Ferreira, vicepresidente de ingeniería de ventas para América Latina de la firma. Ferreira no precisó si las organizaciones afectadas eran públicas o privadas ni cuáles habían recibido una notificación.

## Qué hacían los dos agentes

Un agente de IA puede recibir un objetivo, elegir una acción disponible y continuar según el resultado, en vez de limitarse a responder una pregunta. En esta campaña, CrowdStrike describe un esquema de dos agentes construido alrededor de Claude Code, la herramienta de programación de Anthropic: uno, llamado supervisor, elegía la próxima tarea dentro de una secuencia; el otro la ejecutaba. El operador había adaptado un marco de pruebas de seguridad de código abierto. Un pentest suele ser una intrusión simulada y autorizada para descubrir fallas; aquí se usó contra organizaciones reales sin permiso.

La diferencia importa: el informe no describe una máquina que salió a buscar hospitales por su cuenta. El atacante eligió los objetivos y preparó las herramientas; después delegó parte de las decisiones y la ejecución. La IA participó en una operación humana, pero hizo más que redactar un mensaje o sugerir código.

En uno de los episodios reconstruidos, el atacante ya tenía un punto de entrada. Cuando el primer intento quedó bloqueado, el agente cambió de estrategia en menos de un minuto. Según el relato de Clarín, unos 20 minutos después de la instrucción inicial había llegado a Active Directory, un sistema central que administra cuentas y accesos, y había obtenido credenciales. Ese tiempo corresponde a un caso observado, no a un promedio de toda la campaña.

Clarín también contó otro episodio argentino: el agente encontró que el acceso disponible en una entidad de salud podía servir para explorar otra organización que el atacante ya había vulnerado. Identificó esa posibilidad en doce minutos y medio, aunque la instrucción inicial no le había pedido ese salto. En términos sencillos, el sistema halló por su cuenta una conexión entre dos redes a las que el operador ya había logrado entrar.

## Lo que el número no permite afirmar

El informe de CrowdStrike reúne cuatro actores que usaron agentes en campañas entre mayo y agosto; sólo uno es el que la compañía vincula con entidades de salud argentinas. Para ese operador, la firma afirma al menos 15 compromisos y extracción de datos en por lo menos una víctima. No publicó los nombres, la cantidad de pacientes afectados ni evidencia pública que permita identificar a las instituciones. Por eso, el dato debe leerse como un hallazgo de inteligencia de amenazas de una empresa privada, no como un registro oficial o una lista de hospitales confirmada por sus responsables.

La exposición de datos médicos tiene antecedentes en el país. Clarín recuerda intrusiones y filtraciones que afectaron a OSDE y al Hospital Garrahan en 2022, a PAMI en 2023, y un ataque de ransomware que interrumpió sistemas del Grupo Rossi, Stamboulian e Hidalgo en 2024. Son episodios distintos: no hay un vínculo demostrado entre ellos y la campaña que CrowdStrike describe ahora.

## La lección práctica para quienes conectan agentes

El caso no equivale a una automatización comercial ni a un agente de atención al cliente. Sí muestra por qué importa el alcance de las herramientas que una IA puede usar. Si un sistema sólo necesita consultar documentos, no necesita permiso para modificar el sistema de gestión; las acciones de escritura y las decisiones sensibles pueden quedar detrás de una aprobación humana, con registros que permitan reconstruir qué pasó.

Ese criterio también sirve en una pyme que conecta correo, planillas o facturas: permisos mínimos, separación entre lectura y modificación y una persona que revise excepciones. Es parte del diseño de los [agentes y automatizaciones que desarrolla MR Agentes](/servicios/), y de los [controles operativos para agentes de IA](/notas/agentes-con-control-operativo-evidencia-y-supervision-humana/).

La siguiente pieza que falta es saber qué organizaciones fueron afectadas y cuáles recibieron aviso. CrowdStrike dijo a Clarín que intentó notificar a las entidades responsables, pero no identificó a quiénes contactó ni si obtuvo respuesta. Hasta que esa información aparezca, la conclusión más firme es concreta: un atacante pudo dejar que agentes tomaran decisiones tácticas dentro de redes de salud argentinas, y el alcance de los datos expuestos sigue sin poder verificarse públicamente.
