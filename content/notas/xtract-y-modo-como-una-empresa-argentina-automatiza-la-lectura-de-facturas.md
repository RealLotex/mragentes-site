---
schema_version: 1
title: "Xtract y MODO: cómo una empresa argentina automatiza la lectura de facturas"
date: "2026-11-04T00:00:00-03:00"
description: "Xtract procesa facturas para MODO y otras empresas: qué automatiza, qué resultados informa y por qué importa controlar los errores."
image: "/images/stock/xtract-y-modo-como-una-empresa-argentina-automatiza-la-lectura-de-facturas.png"
image_alt: "Ilustración de facturas que pasan de un escritorio a un sistema digital, con una persona revisando un comprobante"
tags:
  - "inteligencia-artificial"
  - "automatizacion"
  - "pymes"
  - "argentina"
pillar: "automatizacion-practica"
learning_level: "inicial"
sources:
  - "https://www.itsitio.com/ar/inteligencia-artificial/en-contabilidad-casi-bien-es-mal-xtract-la-startup-argentina-que-le-enseno-a-leer-facturas-a-arcos-dorados-y-modo-sin-depender-de-openai-o-antropic/"
  - "https://xtract.app/es-ES/resources/case-studies/modo/"
  - "https://www.cronista.com/negocios/de-la-corpo-a-armar-una-startup-que-automatiza-facturas-para-ypf-arcos-dorados-y-nike-van-por-us-75-millones/"
automation_id: "blog:2026-11-04:xtract-y-modo-como-una-empresa-argentina-automatiza-la-lectura-de-facturas"
slug: "xtract-y-modo-como-una-empresa-argentina-automatiza-la-lectura-de-facturas"
draft: false
aliases: []
---

Una factura de proveedor puede parecer un trámite menor hasta que hay cientos: alguien debe leerla, comprobar sus datos y cargarla en el sistema contable. La fintech argentina MODO incorporó software de Xtract para reducir ese trabajo. Según un [caso publicado por la propia proveedora](https://xtract.app/es-ES/resources/case-studies/modo/), procesó más de 9.300 facturas desde mayo de 2023 y ahorró el equivalente a más de 1.240 horas de carga manual. Son estimaciones de Xtract para ese cliente, no una medición independiente.

La historia volvió a circular el 2 de noviembre en [ITSitio](https://www.itsitio.com/ar/inteligencia-artificial/en-contabilidad-casi-bien-es-mal-xtract-la-startup-argentina-que-le-enseno-a-leer-facturas-a-arcos-dorados-y-modo-sin-depender-de-openai-o-antropic/), pero la herramienta y la implementación de MODO son anteriores. La pregunta útil para cualquier negocio es cómo se pasa de leer un comprobante a incorporarlo en la contabilidad sin convertir un error de lectura en un error de gestión.

## De la factura al sistema contable

Xtract fue fundada en 2020 por Tomás Marconi, Alejandro Bezdjian y Jesús De Gruttola. Según relató Marconi a [El Cronista](https://www.cronista.com/negocios/de-la-corpo-a-armar-una-startup-que-automatiza-facturas-para-ypf-arcos-dorados-y-nike-van-por-us-75-millones/), las conversaciones con equipos financieros revelaron una tarea repetida: personas dedicadas durante horas a cargar comprobantes. Arcos Dorados figuró entre sus primeros clientes corporativos.

La plataforma toma la información del comprobante, aplica reglas de validación y la integra con un ERP, el sistema que una empresa usa para administrar procesos y registros. En el caso de MODO, Xtract identifica a SAP como destino. La empresa también ofrece circuitos de aprobación de facturas: leer un documento y autorizar su pago son pasos distintos.

Por ejemplo, una factura puede llegar por correo, convertirse en campos como proveedor, fecha e importe y pasar al sistema de gestión. La dificultad no termina al extraer números: hay que comprobar que correspondan al documento y a las reglas del negocio, evitar duplicados y resolver excepciones.

## El mismo resultado no garantiza que sea correcto

Xtract describe su tecnología como determinística: para una misma factura y las mismas condiciones, dice, produce el mismo resultado. Eso aporta consistencia, pero un resultado repetible también puede ser incorrecto. ITSitio recoge una exactitud del 98% atribuida a la solución, sin precisar allí la muestra ni el método de medición; no alcanza para prometer ese resultado en cualquier empresa.

La diferencia con un asistente conversacional también importa. Un modelo generativo puede ayudar a interpretar texto y documentos, pero la contabilización necesita reglas, integración y controles sobre los datos que se guardan. No hace falta elegir una sola técnica para todos los problemas: la decisión depende del documento y del riesgo de equivocarse.

## Qué puede aprender una pyme

El caso de MODO es de una empresa con volumen y SAP; no demuestra que toda pyme necesite la misma plataforma ni que ahorre la misma cantidad de horas. Antes de automatizar conviene contar cuántos comprobantes llegan, de qué proveedores y formatos, cuánto tiempo lleva cargarlos y qué pasa cuando falta un dato o aparece un duplicado.

En [MR Agentes](/servicios/), el trabajo de lectura de documentos parte de definir campos, conectar el sistema de destino y enviar los casos dudosos a revisión. Es una manera práctica de aplicar la lección del caso: la ganancia no está solamente en leer más rápido, sino en que la información llegue al lugar correcto y alguien pueda intervenir cuando el circuito no resuelve una excepción.
