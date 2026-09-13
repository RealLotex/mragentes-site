---
schema_version: 1
title: "Agentes sin IA en la sombra: cómo escalar con control"
date: "2026-09-13T12:00:00-03:00"
description: "Un método simple para adoptar agentes de IA con herramientas aprobadas, permisos mínimos, evidencia y responsables claros."
image: "/images/stock/pexels-5324856.jpg"
image_alt: "Equipo de profesionales trabajando con computadoras portátiles en una oficina"
tags:
  - ia
  - agentes
  - automatizacion
  - seguridad
  - gobernanza
  - pymes
pillar: "control-y-gobernanza"
learning_level: "intermedio"
sources:
  - "https://news.microsoft.com/source/asia/features/how-microsoft-ai-is-helping-cognizant-scale-delivery-excellence-across-10000-projects/"
  - "https://www.ncsc.gov.uk/blogs/the-hidden-risks-of-shadow-ai"
  - "https://www.gov.uk/government/publications/ai-risk-management-toolkit"
automation_id: "blog:2026-09-13:agentes-sin-ia-en-la-sombra-como-escalar-con-control"
slug: "agentes-sin-ia-en-la-sombra-como-escalar-con-control"
draft: false
aliases: []
---

Una empresa puede adoptar inteligencia artificial de dos maneras muy distintas. En la primera, cada persona prueba servicios por su cuenta, copia información de trabajo y acumula automatizaciones que nadie registra. En la segunda, el equipo elige una necesidad concreta, autoriza una herramienta, limita los datos y conserva evidencia de cada decisión. Las dos vías pueden producir resultados rápidos, pero sólo una permite crecer sin perder control.

Tres publicaciones oficiales recientes permiten observar esta diferencia. Microsoft describió cómo Cognizant incorporó agentes en una operación que supera los 10.000 proyectos. El National Cyber Security Centre (NCSC) del Reino Unido explicó los riesgos de la “IA en la sombra”, es decir, el uso de tecnología que queda fuera de los sistemas y procesos aprobados. El gobierno británico, además, publicó un toolkit para comprender, evaluar y tratar riesgos durante el diseño, la compra o la operación de soluciones de IA.

El aprendizaje no consiste en copiar la escala de una empresa con 350.000 colaboradores. Para una pyme, la evidencia apunta a una arquitectura mucho más sencilla: una lista corta de herramientas aprobadas, permisos mínimos, una persona responsable de cada proceso y un registro suficiente para reconstruir qué ocurrió. Este enfoque reduce puntos de falla y evita que la gobernanza se convierta en una capa burocrática separada del trabajo cotidiano.

## Escalar agentes no significa entregarles toda la operación

Según el [caso publicado por Microsoft](https://news.microsoft.com/source/asia/features/how-microsoft-ai-is-helping-cognizant-scale-delivery-excellence-across-10000-projects/), Cognizant usa Microsoft AI Foundry, servicios de Azure AI y Microsoft 365 Copilot para asistir a líderes de Delivery Excellence. Los sistemas centrales continúan en funcionamiento; la IA lee documentos, reconcilia datos, identifica riesgos y prepara borradores para revisión. Las experiencias se integran en aplicaciones conocidas como Teams, Outlook, Word y Excel.

Esta separación es relevante. El agente no reemplaza el sistema donde reside la información oficial ni se convierte en autoridad final. Reduce el trabajo de buscar, reunir y ordenar señales distribuidas. Después presenta una salida para que una persona la evalúe. Microsoft informa que la plataforma pasó de 6.700 usuarios durante el despliegue inicial a más de 8.000 en junio de 2026, pero también señala que las decisiones finales continúan bajo responsabilidad humana.

El dato más útil para diseñar controles es la tasa de aceptación de recomendaciones de uno de los agentes: 42 %. En el artículo, Cognizant interpreta ese resultado como evidencia de que la revisión funciona. Un agente que propone no necesita acertar de forma automática en todos los casos para aportar valor. Necesita mostrar su propuesta, permitir el rechazo y conservar una frontera clara entre asistencia y decisión.

La arquitectura descrita incluye acceso de confianza cero, permisos detallados y auditoría dentro de un entorno controlado. Para una organización pequeña, esos términos pueden traducirse sin desplegar una plataforma compleja: cada automatización accede sólo a los archivos o aplicaciones que necesita; redactar no concede permiso para publicar; consultar clientes no concede permiso para modificar sus datos; y una ejecución deja un identificador, sus fuentes y su resultado.

## La IA en la sombra es una señal operativa, no sólo un problema de conducta

El [NCSC define la IA en la sombra](https://www.ncsc.gov.uk/blogs/the-hidden-risks-of-shadow-ai) como tecnología de IA que no aparece en los sistemas y procesos aprobados de una organización. El riesgo no surge únicamente de que una persona ignore una política. También puede indicar que la política no ofrece una herramienta capaz de resolver una necesidad real.

Cuando un servicio no aprobado recibe datos de la empresa o de sus clientes, la organización puede perder visibilidad sobre dónde se almacenan, cuánto tiempo se conservan o cómo se utilizan. Si se trata de un agente con acceso a herramientas, una vulnerabilidad o una configuración incorrecta puede exponer los mismos privilegios que el agente posee legítimamente. El impacto aumenta con cada permiso innecesario.

Por eso, prohibir de forma general no resuelve el problema. El NCSC recomienda entender por qué las personas recurren a estas herramientas, ofrecer alternativas seguras e integrar la IA de manera controlada. También advierte que el uso no aprobado probablemente no desaparecerá por completo. La meta razonable es reducir el riesgo y mejorar la visibilidad.

Una pyme puede comenzar con un inventario de una sola página. Debe registrar la herramienta, el proceso donde se usa, la persona responsable, las categorías de datos permitidas, las acciones habilitadas y la fecha de revisión. Si una prueba no puede incorporarse a ese inventario, no debería recibir información sensible ni permisos externos. Esta regla simple convierte una conversación abstracta sobre seguridad en una decisión observable.

## Un registro de riesgos pequeño puede ordenar decisiones grandes

El [AI Risk Management Toolkit](https://www.gov.uk/government/publications/ai-risk-management-toolkit) del Department for Science, Innovation and Technology está dirigido a quienes diseñan, operan, compran o entregan productos con IA. La guía incluye un libro de trabajo y propone un punto de partida para equipos multidisciplinarios: datos, ingeniería, tecnología, gestión de proyectos, cambio y comunicaciones.

La idea central es que un riesgo debe comprenderse y justificarse junto con su tratamiento. No basta con anotar “la IA puede equivocarse”. Es necesario identificar qué error importa, a quién afecta, qué control reduce su probabilidad o impacto y quién decide si el riesgo residual es aceptable. Ese análisis permite comparar alternativas antes de invertir más tiempo o ampliar permisos.

Para una automatización de contenidos, por ejemplo, los riesgos principales no son idénticos en todas las etapas:

| Etapa | Riesgo concreto | Control mínimo | Responsable |
| --- | --- | --- | --- |
| Investigación | Usar una afirmación sin respaldo | Fuente primaria y enlace conservado | Responsable editorial |
| Redacción | Presentar una inferencia como un hecho | Revisión de citas y lenguaje | Editor de la nota |
| Publicación web | Duplicar o romper una página | Pruebas, identificador único y despliegue verificable | Responsable técnico |
| Redes sociales | Publicar dos veces tras un error incierto | Clave de deduplicación y consulta del estado remoto | Responsable del canal |

Este registro no requiere una aplicación nueva. Puede vivir junto al proceso que controla, con campos obligatorios y un historial de cambios. La simplicidad tiene una ventaja adicional: si una persona no puede explicar el control, probablemente tampoco podrá verificarlo cuando ocurra una falla.

## Un piloto de cinco controles para una pyme

El primer paso es elegir un proceso pequeño, frecuente y reversible. Clasificar consultas, preparar un resumen o redactar una respuesta son mejores candidatos iniciales que aprobar pagos, eliminar información o enviar mensajes sin revisión. El objetivo debe expresarse como un resultado medible, no como una expectativa general de “usar IA”.

El segundo paso es nombrar a una persona responsable. Esa persona no necesita ejecutar cada tarea, pero sí debe decidir qué datos se permiten, qué resultado se considera correcto y cuándo detener el piloto. Si nadie puede asumir esa función, el proceso todavía no está definido con suficiente claridad.

El tercer paso es aprobar una herramienta y una fuente de datos. Una lista corta facilita capacitación, soporte y auditoría. Los datos sensibles deben excluirse por defecto hasta comprobar que el proveedor, la configuración y el contrato ofrecen el tratamiento necesario. Las cuentas personales no deberían formar parte de un proceso empresarial.

El cuarto paso es separar preparación y efecto externo. El agente puede investigar, clasificar o redactar; otra condición verificable autoriza publicar, enviar o modificar. Esta frontera permite probar el trabajo interno muchas veces sin multiplicar consecuencias. Cuando la publicación automática sea necesaria, debe incorporar una identidad estable para que un reintento reconozca el resultado anterior.

El quinto paso es medir utilidad y control durante un período breve. Conviene registrar tiempo ahorrado, porcentaje de propuestas aceptadas, correcciones necesarias, incidentes y casos derivados a una persona. Una tasa de aceptación inferior al 100 % no implica fracaso: puede demostrar que la revisión detecta propuestas que no deben avanzar. La decisión de ampliar el piloto debe apoyarse en esos datos y no sólo en una demostración llamativa.

## Qué cambia cuando el sistema crece

Al aumentar el volumen, la tentación habitual es agregar herramientas, agentes y caminos de recuperación. Cada componente nuevo también agrega estados posibles y dependencias. Antes de ampliar la arquitectura, conviene comprobar si el problema puede resolverse con el mismo flujo, más capacidad y mejores límites.

El caso de Cognizant muestra una red de agentes para entrega, auditoría y conocimiento, pero mantiene sistemas centrales, permisos detallados y decisiones humanas. La recomendación no es comenzar con una red equivalente. Es conservar esas fronteras desde el primer piloto. Una pyme puede operar un único flujo lineal: entrada validada, preparación, controles, publicación y registro. Sólo debería separar componentes cuando exista una necesidad demostrable de escala, aislamiento o responsabilidad.

También debe existir una regla para la incertidumbre. Si el sistema no puede confirmar si una acción externa ocurrió, no debe repetirla automáticamente. Debe conservar el intento y derivarlo a revisión. Esta decisión puede parecer más lenta en un caso aislado, pero evita duplicados y daños difíciles de corregir.

La adopción controlada no busca eliminar todos los riesgos. Busca que los riesgos importantes sean visibles, tengan tratamiento y permanezcan dentro de límites aceptados. Las fuentes analizadas coinciden en un punto práctico: la utilidad de la IA aumenta cuando se integra al trabajo real, y esa integración necesita herramientas aprobadas, permisos acotados y responsabilidad explícita.

## Preguntas frecuentes

### ¿Qué diferencia hay entre usar IA y tener IA en la sombra?

La diferencia es la visibilidad y la aprobación. Una herramienta autorizada forma parte de un proceso conocido, con reglas sobre datos, permisos y responsables. La IA en la sombra se utiliza fuera de esos controles, aunque la intención de quien la usa sea mejorar su trabajo.

### ¿Una pyme necesita un comité para comenzar?

No necesariamente. Un piloto pequeño puede tener una persona responsable, un inventario simple, datos permitidos por escrito y una revisión definida. Deben participar más áreas cuando el proceso afecta información sensible, clientes, obligaciones legales o decisiones de alto impacto.

### ¿Qué permisos debería recibir un agente?

Sólo los indispensables para su etapa. Un agente de investigación puede consultar fuentes aprobadas; uno de redacción puede preparar archivos; ninguno necesita credenciales de publicación si esa acción corresponde a una etapa posterior. Los permisos deben revisarse cuando cambia el objetivo.

### ¿Cómo se evalúa si el piloto funciona?

Se combinan métricas de utilidad y control: tiempo ahorrado, calidad aceptada, cantidad de correcciones, derivaciones humanas, fallas y duplicados. El piloto funciona cuando mejora un resultado concreto sin volver opaca la responsabilidad ni ampliar el riesgo más allá de lo acordado.

## Fuentes y metodología

El análisis utiliza el caso de Microsoft sobre la adopción de agentes en Cognizant: https://news.microsoft.com/source/asia/features/how-microsoft-ai-is-helping-cognizant-scale-delivery-excellence-across-10000-projects/. Para riesgos de herramientas no autorizadas se consultó la guía del National Cyber Security Centre: https://www.ncsc.gov.uk/blogs/the-hidden-risks-of-shadow-ai. El marco práctico de evaluación proviene del AI Risk Management Toolkit del gobierno británico: https://www.gov.uk/government/publications/ai-risk-management-toolkit.

Las cifras y capacidades empresariales se atribuyen a las organizaciones que las publicaron. Las recomendaciones para pymes son una inferencia metodológica: reducen esos principios a un piloto lineal y verificable, sin asumir que una organización pequeña posee la infraestructura o la escala de los casos citados.
