---
schema_version: 1
title: "Cómo usa Buenos Aires la IA para controlar si se vacían los contenedores"
date: "2026-11-22T00:00:00-03:00"
description: "La Ciudad cruza cámaras, GPS y señales de los camiones recolectores. Así puede revisar qué pasó en una parada y avisar a la empresa de limpieza."
image: "/images/stock/como-usa-buenos-aires-la-ia-para-controlar-si-se-vacian-los-contenedores.png"
image_alt: "Ilustración generada con IA de un camión recolector y un contenedor de residuos en una calle de Buenos Aires."
tags:
  - "ia"
  - "argentina"
  - "vision-computacional"
  - "automatizacion"
  - "residuos"
pillar: "automatizacion-practica"
learning_level: "inicial"
sources:
  - "https://noticiasargentinas.com/sociedad/la-ciudad-implemento-una-plataforma-con-ia-para-controlar-la-recoleccion-de-residuos_a6afde3da4f169fd00c3e84e6"
  - "https://static.buenosaires.gob.ar/sites/default/files/2026-10/VT%20HIGIENE%20URBANA.pdf"
  - "https://documentosboletinoficial.buenosaires.gob.ar/publico/ck_PE-DEC-AJG-AJG-97-26-7320.pdf"
  - "https://buenosaires.gob.ar/gcaba_historico/barrido-y-limpieza/monitoreo-de-higiene"
  - "https://www.iswa.org/event/2026-iswa-world-congress/"
  - "https://radiomitre.cienradios.com/sociedad/presentaron-en-londres-una-ia-argentina-que-audita-la-recoleccion-de-basura-en-tiempo-real/"
automation_id: "blog:2026-11-22:como-usa-buenos-aires-la-ia-para-controlar-si-se-vacian-los-contenedores"
slug: "como-usa-buenos-aires-la-ia-para-controlar-si-se-vacian-los-contenedores"
draft: false
aliases: []
news: true
---

Un camión recolector pasó por la cuadra. Horas después, el contenedor sigue lleno. ¿Lo vació y se volvió a llenar, o el brazo que lo levanta nunca llegó a accionarse? La ubicación del vehículo, por sí sola, deja abiertas las dos posibilidades. El Gobierno de la Ciudad de Buenos Aires usa cámaras y análisis de imágenes para reconstruir qué pasó alrededor de cada parada. Las empresas argentinas BS Lab y Exanet, que desarrollaron la plataforma de control, llevaron el caso al Congreso Mundial de la Asociación Internacional de Residuos Sólidos, celebrado del 9 al 11 de noviembre en Londres. El servicio ya usaba esta tecnología antes de la presentación. [Noticias Argentinas](https://noticiasargentinas.com/sociedad/la-ciudad-implemento-una-plataforma-con-ia-para-controlar-la-recoleccion-de-residuos_a6afde3da4f169fd00c3e84e6) · [Congreso de la ISWA](https://www.iswa.org/event/2026-iswa-world-congress/)

## Qué agrega una cámara al GPS

La Ciudad ya tenía dos formas de seguir el recorrido. El GPS registraba por dónde había pasado cada camión. Un sensor en el contenedor registraba si la unidad lo había operado. Las cámaras, cuya incorporación el Gobierno porteño documentó en marzo, permiten ver también la maniobra y el estado de la vereda. La plataforma junta la ubicación, las imágenes y las señales de accionamiento del brazo mecánico, el que levanta el contenedor para descargarlo en el camión. [Centro de Monitoreo de Higiene](https://buenosaires.gob.ar/gcaba_historico/barrido-y-limpieza/monitoreo-de-higiene) · [Decreto porteño de marzo](https://documentosboletinoficial.buenosaires.gob.ar/publico/ck_PE-DEC-AJG-AJG-97-26-7320.pdf)

La IA entra en el análisis del video. Esa tarea se conoce como visión computacional. El programa busca patrones en las imágenes para distinguir, por ejemplo, bolsas que quedaron junto al contenedor de un residuo grande o de un montón de ramas. Cuando el sistema genera una incidencia, guarda una imagen, la hora y la ubicación. El centro de monitoreo puede consultar ese registro y avisar a la empresa que tiene a cargo el servicio en la zona. [Audiencia pública de higiene urbana del 5 de octubre](https://static.buenosaires.gob.ar/sites/default/files/2026-10/VT%20HIGIENE%20URBANA.pdf)

## De una alerta a una cuadra limpia

En esa audiencia, el Gobierno porteño informó que el sistema procesaba más de 2.000 hallazgos por día y generaba unas 250 incidencias diarias en promedio. Los hallazgos son detecciones del programa y las incidencias son registros de situaciones que requieren seguimiento. Esas cifras cuentan lo que el sistema detectó y registró. Para saber cuánto mejoró el servicio habría que medir cuánto tardó cada empresa en resolver los avisos y qué pasó en las cuadras donde volvió a aparecer el problema. La Ciudad mantiene inspectores en la calle para verificar cómo se prestó el servicio. [Versión taquigráfica de la audiencia](https://static.buenosaires.gob.ar/sites/default/files/2026-10/VT%20HIGIENE%20URBANA.pdf)

En Londres, el equipo presentó la certificación automática de las tareas como un paso futuro. Por ahora, el cambio está en lo que un operador puede reconstruir con el registro de una parada. Ante un contenedor lleno, puede revisar si el camión se detuvo, si lo levantó y qué quedó alrededor. Es una diferencia que vale para cualquier tarea fuera de la oficina. El registro del recorrido dice dónde estuvo el equipo. Las señales de la maniobra y las imágenes ayudan a verificar qué trabajo hizo ahí. [Radio Mitre](https://radiomitre.cienradios.com/sociedad/presentaron-en-londres-una-ia-argentina-que-audita-la-recoleccion-de-basura-en-tiempo-real/) · [Automatización de procesos en MR Agentes](/servicios/#automatización-de-procesos)
