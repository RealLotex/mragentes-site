# mragentes.com.ar

Sitio de MR Agentes — automatización de procesos y agentes de IA para pymes.
Gálvez, provincia de Santa Fe.

Hugo (extended) → GitHub Pages, publicado por GitHub Actions en cada push a `main`.

---

## Arrancar en local

```bash
hugo server -D          # http://localhost:1313
hugo                    # compila a public/
```

Requiere Hugo **extended** 0.128 o superior (la versión que usa el workflow está
fijada en `.github/workflows/deploy.yml`; conviene que la local coincida).

---

## Cómo está organizado

```
assets/          CSS y JS que pasan por Hugo Pipes (se minifican y llevan huella)
  css/main.css   hoja única, ordenada por secciones numeradas
  js/site.js     menú angosto + filtro del índice de notas
  js/push.js     avisos de nota nueva (Web Push)
content/         markdown de las páginas y las notas
layouts/         plantillas
  _default/      baseof, single (páginas sueltas), thanks
  notas/         list (índice) y single (artículo)
  tags/          list (todos los temas) y term (un tema)
  partials/      masthead, colophon, closer, schema
  shortcodes/    ficha (tabla de especificación), contacto (formulario + canales)
static/          se copia tal cual: fuentes, imágenes, sw.js, manifest, robots
scripts/         publicación automática de notas (Python, fuera del build)
```

### Decisiones que conviene no deshacer sin pensarlo

**Las hojas y los scripts viven en `assets/`, no en `static/`.** Ahí Hugo los
minifica y les agrega una huella digital al nombre
(`main.min.<hash>.css`), con su `integrity` correspondiente. Es lo que permite
cachearlos para siempre sin que nadie quede con una versión vieja. Si se mueven a
`static/` vuelve el `?v=21` a mano, que es justo lo que esto reemplazó.

**Las fuentes son autoalojadas** (`static/fonts/`, subconjunto latino, WOFF2).
No hay `@import` a `fonts.googleapis.com`: bloqueaba el dibujado contra un dominio
ajeno y mandaba la IP de cada visitante a un tercero. Las dos que pintan la primera
pantalla van con `<link rel="preload">` en `baseof.html`.

**`public/` no se versiona.** Lo genera el workflow. Estuvo commiteado un tiempo;
se sacó del índice con `git rm -r --cached public/`.

**El front matter de las notas no cambió.** `scripts/publish_daily.py` sigue
escribiendo `title`, `date`, `description`, `image`, `image_alt` y `tags` igual que
antes. El campo `image` ya no se pinta arriba del artículo, pero se sigue usando
para las tarjetas de Facebook, WhatsApp y Twitter al compartir — no lo saques.

**El service worker precarga sólo rutas estables.** Los nombres con huella cambian
en cada publicación, así que no se pueden precargar por nombre; el resto se guarda
en el cache a medida que se pide (`static/sw.js`).

---

## El sistema visual, en corto

Está documentado para quien lo lea en **[/colofon/](https://mragentes.com.ar/colofon/)**
(`content/colofon.md`) y comentado en `assets/css/main.css`. Lo mínimo:

- **Referencia:** lámina anatómica y hoja de especificación técnica. Papel hueso,
  tinta negra cálida, filetes de 1 px, columna de claves al margen, figuras
  numeradas.
- **Tipografías:** Archivo y Chivo Mono (Omnibus-Type) y Alegreya (Huerta
  Tipográfica) — las tres dibujadas en Argentina.
- **Un solo acento:** `--minio` (#a8391b), el naranja del antióxido.
- **Sin tarjetas.** Lo que sería una grilla de recuadros con sombra es una lista
  reglada (`.ledger`, `.index`, `.spec`, `.channels`).
- **Sin animaciones de entrada.** Sólo se mueve lo que responde a una acción.
- **Sin analítica ni cookies**, y por eso sin cartel de cookies.

La grilla `.sheet` tiene tres columnas nombradas: `key` (claves al margen), `text`
(medida de lectura) y `aside` (marginalia). Por debajo de 62rem colapsa a una.
Ojo con eso: los hijos colocados por nombre de línea necesitan volver a
`grid-column: auto` en la consulta de medios, y con selectores de igual o mayor
especificidad — una consulta de medios no agrega especificidad por sí sola.

---

## Publicación

`git push` a `main` dispara `.github/workflows/deploy.yml`.

Las notas diarias las escribe `scripts/publish_daily.py`, que crea el archivo en
`content/notas/`, commitea y pushea. El deploy es el mismo.

---

## Antes de dar por cerrada una tanda de cambios

```bash
hugo --quiet --destination /tmp/build   # tiene que salir sin advertencias
```

Y revisar a ojo, como mínimo: portada, `/servicios/`, `/notas/`, una nota, y
`/contacto/` — cada una a 390 px y a 1440 px. El desborde horizontal en pantallas
angostas es el error que más fácil se cuela.
