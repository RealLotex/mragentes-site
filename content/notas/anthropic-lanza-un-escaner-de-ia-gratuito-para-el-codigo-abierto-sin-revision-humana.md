---
schema_version: 1
title: "Anthropic lanza un escáner de IA gratuito para el código abierto, sin revisión humana"
date: "2026-10-09T00:00:00-03:00"
description: "Anthropic ofrece escaneos gratuitos de IA al código abierto, pero los proyectos reciben los hallazgos sin revisión humana previa."
image: "/images/stock/anthropic-lanza-un-escaner-de-ia-gratuito-para-el-codigo-abierto-sin-revision-humana.png"
image_alt: "Ilustración conceptual: un escáner de IA detecta una falla en código abierto mientras una persona revisa la reparación propuesta."
tags:
  - "ia"
  - "actualidad"
pillar: "automatizacion-practica"
learning_level: "inicial"
sources:
  - "https://www.anthropic.com/research/launching-opt-in-vuln-finding-service-for-open-source"
automation_id: "blog:2026-10-09:anthropic-lanza-un-escaner-de-ia-gratuito-para-el-codigo-abierto-sin-revision-humana"
slug: "anthropic-lanza-un-escaner-de-ia-gratuito-para-el-codigo-abierto-sin-revision-humana"
draft: false
aliases: []
---

Una herramienta que encuentra miles de fallas puede crear otro problema: ¿quién confirma cuáles existen y las corrige? Anthropic dice que, durante los últimos seis meses, sus modelos detectaron más de 29.000 vulnerabilidades posibles en proyectos de software abierto, pero su equipo alcanzó a revisar y clasificar unas 6.000. Ese cuello de botella está detrás de OSS Scanner, el servicio gratuito que la compañía anunció el 8 de octubre para enviar hallazgos a proyectos que acepten participar. [El anuncio del equipo de seguridad de Anthropic](https://www.anthropic.com/research/launching-opt-in-vuln-finding-service-for-open-source) describe un cambio importante: algunas alertas llegarán antes de que una persona las valide.

## Qué recibe un proyecto y quién puede sumarse

El software de código abierto es el conjunto de programas cuyo código se puede consultar y reutilizar. No sólo lo usan sus autores: una biblioteca pequeña puede quedar incorporada en aplicaciones, sitios y servicios de miles de organizaciones. Si una falla se repite en esa cadena, corregirla a tiempo importa mucho más allá del equipo que escribió el código.

OSS Scanner propone análisis periódicos con los modelos más capaces de Anthropic, incluido Claude Mythos. Cada informe puede traer una demostración reproducible de la falla, una explicación y un parche sugerido si el modelo consigue proponerlo. Pero los informes se generan sin revisión humana previa. Anthropic aclara que pueden contener errores o exagerar la gravedad.

No es un escáner abierto para cualquier repositorio. Debe solicitarlo una persona que mantenga el proyecto y la empresa decide caso por caso; prioriza software con impacto crítico en la infraestructura o la seguridad de sus usuarios. También advierte que el servicio está pensado para equipos capaces de atender nuevos reportes. Para los proyectos que no puedan procesar alertas sin verificar, Anthropic dice que mantendrá su canal habitual de divulgación con revisión humana.

La compañía informa que probó el sistema en decenas de proyectos. En una evaluación propia, especialistas examinaron 97 hallazgos de gravedad alta o crítica en 48 proyectos: 85 cumplieron el umbral que Anthropic usa para divulgar una vulnerabilidad, 11 eran problemas reales pero duplicados o ya detectados y uno resultó inválido. Es un resultado prometedor, aunque no una garantía independiente para cada alerta: la muestra es temprana y la propia empresa reconoce que algunas calificaciones de gravedad pueden estar infladas.

## Encontrar no es lo mismo que reparar

El lanzamiento forma parte de una iniciativa mayor. En su [Anthropic Cyber Mission](https://www.anthropic.com/news/anthropic-cyber-mission), la empresa también anunció un programa que ofrece modelos, investigación y especialistas en el lugar a proveedores que protegen redes eléctricas, agua, transporte y otros sistemas industriales. En esos entornos, apagar un equipo para instalar una actualización puede ser riesgoso. [Axios señaló](https://www.axios.com/2026/10/08/anthropic-critical-infrastructure-cybersecurity) que todavía quedan preguntas sobre cómo probar y desplegar una corrección sin interrumpir el servicio.

La diferencia entre una alerta y un arreglo seguro sirve también para automatizaciones cotidianas. En [los servicios de MR Agentes](/servicios/), por ejemplo, un dato dudoso extraído de una factura va a una bandeja para que alguien lo revise en vez de cargarse automáticamente. La misma regla práctica vale aquí: reproducir el problema, evaluar el parche, probarlo y registrar el cambio antes de aplicarlo. MR Agentes es un [taller de automatización para pymes en Gálvez](/nosotros/); nuestra [nota sobre controles para agentes](/notas/nvidia-presenta-controles-de-seguridad-para-agentes-de-ia/) desarrolla por qué los permisos y la supervisión deben existir fuera del modelo.

OSS Scanner puede acelerar el primer paso y ayudar a que más proyectos vean fallas que antes esperaban meses para ser revisadas. No elimina el trabajo de los mantenedores ni convierte cada alerta en una actualización lista para instalar. La medida decisiva será cuánto acorta el recorrido entre detectar una vulnerabilidad, comprobarla y publicar una corrección segura.
