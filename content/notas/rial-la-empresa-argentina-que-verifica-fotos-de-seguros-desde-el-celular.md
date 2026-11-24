---
schema_version: 1
title: "Rial, la empresa argentina que verifica fotos de seguros desde el celular"
date: "2026-11-24T00:00:00-03:00"
description: "Una aseguradora puede pedir una foto por enlace y recibirla con una firma digital. Rial también permite que un agente de IA gestione el pedido."
image: "/images/stock/rial-la-empresa-argentina-que-verifica-fotos-de-seguros-desde-el-celular.png"
image_alt: "Ilustración generada con IA de una persona que fotografía con el celular el golpe en el guardabarros de un auto"
tags:
  - "ia"
  - "argentina"
  - "automatizacion"
  - "seguros"
  - "mcp"
pillar: "automatizacion-practica"
learning_level: "inicial"
sources:
  - "https://www.itsitio.com/ar/inteligencia-artificial/real-o-sintetica-la-argentina-que-creo-una-tecnologia-para-verificar-imagenes-en-la-era-de-la-ia-y-desembarco-en-silicon-valley/"
  - "https://www.rial.io/"
  - "https://www.rial.io/guides/photo-verification-api"
  - "https://spec.c2pa.org/specifications/specifications/2.4/explainer/Explainer.html"
  - "https://www.camarainsurtech.com.ar/novedades/insurtech-meetday-2026"
  - "https://www.drapercygnus.vc/startups/rial"
automation_id: "blog:2026-11-24:rial-la-empresa-argentina-que-verifica-fotos-de-seguros-desde-el-celular"
slug: "rial-la-empresa-argentina-que-verifica-fotos-de-seguros-desde-el-celular"
draft: false
aliases: []
news: true
---

Un auto tiene un golpe en el guardabarros y la aseguradora pide una foto. Si recibe un archivo adjunto, le queda por averiguar cuándo se tomó y si fue retocado. Rial, una empresa tecnológica argentina fundada por la física Daphne Estrada, cambia ese paso del reclamo. La aseguradora puede enviar un enlace para que el cliente abra la cámara del celular y saque la foto en ese momento. La imagen llega con una firma digital que permite comprobar si el archivo fue modificado después de la captura. [Rial](https://www.rial.io/)

Estrada estudió en la Universidad de Buenos Aires y trabajó en prevención de fraude antes de fundar Rial a fines de 2025. El 19 de noviembre contó a ITSitio que la empresa ya trabajaba con compañías de Argentina, Brasil y Estados Unidos. La posibilidad de agregar daños a una foto con herramientas de inteligencia artificial generativa fue parte del problema que quiso resolver. En junio, la Cámara Insurtech Argentina, que reúne a empresas de tecnología para seguros, premió el proyecto en un encuentro del sector en Rosario. [ITSitio](https://www.itsitio.com/ar/inteligencia-artificial/real-o-sintetica-la-argentina-que-creo-una-tecnologia-para-verificar-imagenes-en-la-era-de-la-ia-y-desembarco-en-silicon-valley/) · [Cámara Insurtech Argentina](https://www.camarainsurtech.com.ar/novedades/insurtech-meetday-2026)

## Qué queda registrado en la foto

El enlace abre un flujo de captura en el navegador del teléfono. El sistema registra datos de la toma, como la hora y la ubicación, y los vincula al archivo con una credencial que sigue el estándar abierto C2PA. Funciona como un precinto digital. Si alguien altera los píxeles del archivo firmado, al verificarlo ya no coincide con el que salió de la captura. Por separado, Rial dice que analiza señales como la posibilidad de que el usuario haya fotografiado una pantalla. En una prueba que la empresa publicó, el sistema identificó el objeto pedido, un aire acondicionado, y también señaló que se había fotografiado desde una pantalla. [Documentación de Rial](https://www.rial.io/guides/photo-verification-api) · [Explicación del estándar C2PA](https://spec.c2pa.org/specifications/specifications/2.4/explainer/Explainer.html)

Una firma válida ayuda a establecer de dónde salió el archivo y qué ocurrió con él. Para determinar si el golpe ocurrió en el accidente declarado, la aseguradora sigue necesitando el resto de la evidencia. Una foto recién tomada puede mostrar un daño anterior. [Explicación del estándar C2PA](https://spec.c2pa.org/specifications/specifications/2.4/explainer/Explainer.html)

## Qué puede hacer un agente en el reclamo

Rial documenta una integración mediante MCP, un protocolo que permite conectar un asistente de IA con herramientas externas. Con acceso a la cuenta, un agente puede preparar el pedido de fotos, enviar el enlace y consultar el resultado. La documentación también contempla la compra de créditos para fotos con un tope mensual. En un circuito de reclamos, esos permisos importan porque pedir evidencia, gastar dinero y tomar una decisión sobre el pago son acciones distintas. [Documentación de Rial](https://www.rial.io/guides/photo-verification-api) · [Cómo separar datos, costos y permisos en un agente](/notas/agentes-de-ia-con-freno-y-mapa-costos-datos-y-permisos/)

El cambio para quien revisa el siniestro está en qué recibe al abrir el expediente. Además de ver el daño, puede comprobar el origen del archivo y decidir si la imagen alcanza para evaluar el caso o si hace falta pedir otra prueba.
