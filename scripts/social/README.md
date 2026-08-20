# Social manager

Compone y publica las piezas de Instagram y Facebook con **el mismo sistema
visual que el sitio**: papel hueso, tinta cálida, minio como único acento, las
tres tipografías argentinas autoalojadas y la mano grabada como firma.

Los logos anteriores quedaron fuera. La marca es la misma que el masthead: la
mano de `static/faviconhand512.png` con «MR» en
negrita y «Agentes» en regular más claro, exactamente como lo pinta
`.signature-name` en `assets/css/main.css`.

---

## Arrancar

```bash
pip install -r scripts/requirements.txt
cp .env.example .env          # y completar las tres claves de Meta
python3 -m scripts.social doctor
```

`doctor` dice qué falta: credenciales, dependencias, tipografías, y si por
error quedó un `.env` versionado.

---

## Comandos

```bash
python3 -m scripts.social templates            # las 15 plantillas
python3 -m scripts.social library              # los 15 posteos listos
python3 -m scripts.social gallery              # muestrario completo (45 piezas)

python3 -m scripts.social render --from diagnostico --surface all
python3 -m scripts.social render --template dato --stat "40%" --lead "…" --surface story

python3 -m scripts.social nota --latest        # piezas de la última nota, sin publicar
python3 -m scripts.social publish-nota --latest --dry-run
python3 -m scripts.social publish-nota --latest
python3 -m scripts.social publish-library --key diagnostico --story
```

Sin credenciales nada falla: compone, muestra el texto que iría a cada red y
avisa qué falta. Con `SOCIAL_DRY_RUN=1` tampoco toca la red.

---

## Aviso automático de nota nueva

Cada nota que llega a `main` se anuncia sola. El circuito:

```
content/notas/2026-08-08-….md          ← publish_daily.py / publish_blog.py
        │  push a main
        ▼
.github/workflows/social.yml           ← se dispara con el push
        │  compone 4 láminas 4:5 + 1 historia 9:16
        ▼
static/social/<slug>/                  ← commit + push (las piezas quedan servidas)
        │
        ├── Facebook   → foto por multipart, con el enlace a la nota
        └── Instagram  → carrusel (por URL) + historia
        │
        ▼
scripts/social/state.json              ← queda registrado: no se repite
```

**Por qué se commitean las imágenes.** Facebook acepta el archivo directo;
Instagram no: crea el posteo a partir de una URL pública que Meta descarga
desde sus servidores. Al commitearlas quedan servidas por
`raw.githubusercontent.com` apenas se pushea — sin esperar el deploy de Pages —
y por el sitio cuando el deploy termina. Se prueban las dos, en ese orden.

Para que el repositorio no engorde, sólo se conservan las piezas de las
**últimas 10 notas**: pasada esa ventana Meta ya descargó todo y no las mira
nadie más.

### Configurar los secretos

En GitHub: *Settings → Secrets and variables → Actions → New repository secret*

| Secreto             | De dónde sale                                                            |
|---------------------|--------------------------------------------------------------------------|
| `META_ACCESS_TOKEN` | Token de página de larga duración                                        |
| `FB_PAGE_ID`        | ID numérico de la página de Facebook                                     |
| `IG_USER_ID`        | `GET /v21.0/<FB_PAGE_ID>?fields=instagram_business_account`               |

Permisos que necesita el token: `pages_manage_posts`, `pages_read_engagement`,
`instagram_basic`, `instagram_content_publish`. La cuenta de Instagram tiene
que ser profesional y estar vinculada a esa página de Facebook.

Para apagar la publicación sin borrar nada: variable de repositorio
`SOCIAL_ENABLED = 0`.

### Publicar desde tu máquina en vez de desde Actions

Poné `SOCIAL_LOCAL_PUBLISH=1` en el `.env` **y** `SOCIAL_ENABLED=0` como
variable del repositorio. Si dejás los dos activos, la nota puede salir dos
veces: `state.json` frena la repetición sólo si alcanzó a viajar entre una
publicación y la otra.

---

## Las plantillas

Quince composiciones, cada una resuelta nativamente para 1:1, 4:5 y 9:16. La
historia no es el cuadrado estirado — se compone aparte, con más cuerpo
tipográfico y respetando las zonas que tapa la interfaz de Instagram.

| Clave         | Para qué sirve                                        |
|---------------|-------------------------------------------------------|
| `nota`        | Aviso de nota nueva, con su imagen de portada         |
| `titular`     | Una idea sola, a toda página                          |
| `dato`        | Un número grande con su fuente                        |
| `cita`        | Frase textual en bastardilla, con atribución          |
| `lista`       | Tres a cinco puntos numerados                         |
| `mito`        | Mito y verdad, en dos paños                           |
| `comparativa` | Antes y después del mismo proceso                     |
| `ficha`       | Hoja de especificación de un servicio                 |
| `pasos`       | Proceso encadenado                                     |
| `pregunta`    | Pregunta directa, para que respondan                  |
| `glosario`    | Un término del rubro, explicado sin humo              |
| `caso`        | Problema, solución y resultado                        |
| `anuncio`     | Aviso con los canales de contacto                     |
| `agenda`      | Tres o cuatro entradas fechadas                       |
| `punto`       | Una idea por lámina, para carruseles                  |

Cada una compone sobre cuatro fondos —papel, papel reglado, tinta y minio— y
el fondo rota solo. Por eso quince plantillas alcanzan para que no se repita
la estampa: la variedad sale de la combinación, no de tener treinta archivos.

### Los quince posteos listos

`library.json` es texto plano: la plantilla que usa cada posteo, lo que va en
la lámina y el texto para cada red. Se amplía copiando una entrada y
cambiándole la clave — no hay que tocar código.

---

## Por qué las piezas viejas fallaban, y qué lo impide ahora

**Texto desbordado.** El apilador reparte el alto de arriba hacia abajo: cada
bloque mide contra lo que le queda de presupuesto y no puede devolver más que
eso. `fit_text()` busca el cuerpo más grande que entra y, si ni el mínimo
entra, corta con puntos suspensivos. No es que el desborde esté controlado: no
puede ocurrir.

**Historias estiradas.** Ninguna foto se escala a la fuerza. Todo pasa por
`cover()`, que respeta la proporción y recorta lo que sobra. Las historias se
componen nativas a 1080×1920, no se reencuadra el cuadrado.

**Cuadraditos vacíos.** Las fuentes del sitio son subconjuntos latinos: tienen
todo el castellano y no tienen flechas ni palomitas. Antes de dibujar, cada
texto pasa por `sanitize()`, que cambia `→` por `»` y descarta lo que la fuente
no sabe dibujar.

**Todos los posteos iguales.** Rotan la plantilla, el fondo, el gancho, el
cierre y el juego de etiquetas, con una semilla derivada del slug de la nota:
distinto en cada nota, siempre igual para la misma nota.

**Posteos pobres.** De cada nota se extraen materiales reales —un número del
texto, una cita, los subtítulos— y con eso se arma un carrusel de cuatro
láminas más la historia, en vez de una sola placa con el título.

---

## Los archivos

```
brand.py       tokens del CSS, carga de las fuentes del sitio, la mano, paletas
canvas.py      superficies, papel, filetes, ajuste de texto, recorte de fotos
blocks.py      bloques de composición y el apilador con presupuesto de alto
templates.py   las quince plantillas
library.json   los quince posteos listos (texto plano, editable)
library.py     lector de la biblioteca
notas.py       lectura del front matter y del cuerpo de las notas de Hugo
copy.py        ganchos, cierres, etiquetas y las piezas derivadas de una nota
flow.py        el circuito completo: componer, commitear, publicar, registrar
publisher.py   cliente de la Graph API (Facebook, Instagram, historias)
hook.py        enganche para publish_daily.py y publish_blog.py
cli.py         línea de comandos
state.py       qué se publicó y qué plantilla salió última
config.py      lectura del .env y de las variables de entorno
```
