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
  Aires), en títulos e interfaz. Tiene eje de ancho variable, y los títulos van
  ligeramente expandidos —112 %— para que se lean como una placa grabada y no como
  una tipografía de sistema.
- **[Alegreya](https://fonts.google.com/specimen/Alegreya)**, de Huerta Tipográfica
  (Buenos Aires), diseñada por Juan Pablo del Peral, en todo el texto largo. Es una
  serif pensada para literatura: tiene ritmo y aguanta párrafos enteros sin cansar.
- **[Chivo Mono](https://fonts.google.com/specimen/Chivo+Mono)**, también de
  Omnibus-Type, en fechas, claves y datos. La monoespaciada alinea las cifras en
  columna, que es exactamente para lo que se la usa acá.

Las tres se sirven desde este mismo dominio, en formato WOFF2 y sólo con el subconjunto
latino: 204 kB en total, sin una sola petición a servidores de terceros. Un sitio que
llama a `fonts.googleapis.com` bloquea su propio dibujado contra un dominio ajeno y
envía la IP de cada visitante a un tercero sin avisarle.

## Color y forma

El fondo es hueso, no blanco puro, y la tinta es un negro cálido, no `#000`. El negro
puro sobre blanco puro vibra en pantalla y cansa a los pocos párrafos.

El único acento es el naranja del **minio**, la pintura antióxido con la que se pintan
las estructuras de hierro y buena parte de la maquinaria agrícola de esta zona. Se usa
para una cosa por página, no para decorar.

No hay tarjetas. Lo que en una plantilla sería una grilla de recuadros con sombra, acá
son filas separadas por filetes de un pixel, numeradas al margen como una lámina
anatómica. Los botones son rectángulos con 2 px de radio y una sombra dura que se hunde
al presionarlos, como una tecla.

## La mano

La marca es una mano grabada, y el detalle de *La creación de Adán* que abre la portada
es el mismo gesto. Toda esa escena de Miguel Ángel ocurre en el espacio entre dos dedos:
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

Ninguno. No hay Google Analytics, ni píxel de Facebook, ni mapas de calor, ni cookies
propias ni de terceros. Por eso tampoco hay cartel de cookies: no hay nada que
consentir.

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
