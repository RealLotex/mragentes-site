---
title: Colofón
key: Cómo está hecho
description: Con qué está construido este sitio, qué tipografías usa y por qué,
  qué datos recoge (ninguno) y qué decisiones de diseño se tomaron a propósito.
lede: La costumbre de cerrar un libro declarando con qué se compuso es vieja y
  sigue sirviendo. Un negocio que automatiza procesos ajenos debería poder mostrar
  cómo hizo el propio.
image: /faviconhand512.png
no_closer: true
---

## Tipografía

Las tres familias del sitio están dibujadas en Argentina. No es un gesto decorativo:
entre varias opciones técnicamente equivalentes, ésta agrega algo que las otras no.

- **[Archivo](https://fonts.google.com/specimen/Archivo)**, de Omnibus-Type (Buenos
  Aires), en títulos, texto principal e interfaz. Su eje de ancho variable
  permite ajustar los títulos a cada formato.
- **[Alegreya](https://fonts.google.com/specimen/Alegreya)**, de Huerta Tipográfica
  (Buenos Aires), diseñada por Juan Pablo del Peral, en citas.
- **[Chivo Mono](https://fonts.google.com/specimen/Chivo+Mono)**, también de
  Omnibus-Type, en fechas, claves y datos. La monoespaciada alinea las cifras en
  columna, que es exactamente para lo que se la usa acá.

Las tres se sirven desde este mismo dominio, en formato WOFF2 y sólo con el subconjunto
latino: 204 kB en total, sin una sola petición a servidores de terceros. Un sitio que
llama a `fonts.googleapis.com` bloquea su propio dibujado contra un dominio ajeno y
envía la IP de cada visitante a un tercero sin avisarle.

## Color y forma

El fondo claro acompaña la lectura. Los botones redondeados y los bordes finos
se repiten en la navegación y en los formularios. El verde petróleo identifica
los bloques de contacto, y el ocre marca la sección activa.

## La mano

La marca es una mano grabada que toma el gesto de *La creación de Adán*.
La escena de Miguel Ángel ocurre en el espacio entre dos dedos:
una mano le transfiere a la otra la capacidad de actuar. Eso es delegar una tarea, y es
literalmente lo que hace un agente. El fresco es de 1512 y es de dominio público.

No hay fotos de banco de imágenes en el sitio ni imágenes generadas por IA.

## Movimiento

Ninguno automático. No hay elementos que aparezcan al hacer scroll, ni palabras que se
escriban solas, ni contadores que suban. Lo único que se mueve responde a una acción:
el foco del teclado, la presión de un botón, la apertura del menú. Y todo eso se apaga
si el sistema operativo pide menos movimiento.

## Construcción

Sitio estático hecho con [Hugo](https://gohugo.io), alojado en GitHub Pages y publicado
por GitHub Actions en cada cambio. Los estilos y el JavaScript se minifican y llevan
huella digital en el nombre del archivo, así que el navegador puede cachearlos para
siempre y aun así recibir la versión nueva el día que cambian.

Todo el JavaScript del sitio son unas 200 líneas y hace tres cosas: abrir el menú en
pantallas angostas, filtrar el índice de notas y manejar el botón de avisos. Sin
JavaScript el sitio funciona completo.

## Qué datos recoge

No hay Google Analytics, píxel de Facebook, mapas de calor ni cookies propias o de terceros. Por eso no hay cartel de cookies: no hay nada que consentir.

Para saber si el contenido sirve, registramos de forma agregada dos acciones: clics de compartir desde una nota y entradas desde los enlaces de Facebook o Instagram. El registro conserva sólo la acción, la ruta pública, la red y la hora; descarta IP, navegador, parámetros de consulta, texto y cualquier identificador de persona. No crea perfiles y respeta la señal «No rastrear» del navegador.

Dos excepciones, ambas voluntarias y explícitas: el **formulario de contacto**, que se
procesa con Formspree y manda el mensaje a la casilla de MR Agentes, y los **avisos de
nota nueva**, que sólo existen si apretás el botón del pie y guardan únicamente el
identificador que genera tu navegador. Se dan de baja desde el mismo botón.

## Accesibilidad

Contraste verificado sobre el fondo hueso, foco visible en todo lo que se pueda enfocar
con el teclado, blancos de al menos 44 px en los controles táctiles, estructura de
encabezados en orden y enlace para saltar al contenido. Las notas están hechas para
imprimirse: hay una hoja de estilo de impresión que saca la navegación y expande los
enlaces a su dirección completa.

Si encontrás algo que no se entiende, que no se lee o que no funciona con teclado,
[escribime](/contacto/) y lo corrijo.
