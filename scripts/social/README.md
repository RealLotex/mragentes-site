# Publicación social

Este paquete renderiza el anuncio de cada nota y entrega exactamente la misma pieza a Facebook
e Instagram. No genera una publicación diaria independiente.

## Comandos soportados

```bash
python -m scripts.social render-note-announcement --slug <slug>
python -m scripts.social deliver-note --slug <slug> --deploy-sha <sha> --ledger <ruta>
python -m scripts.social.meta_preflight
```

El render se ejecuta en el worktree editorial. La entrega remota sólo la ejecuta el job
`publish_meta` de `.github/workflows/deploy.yml`, dentro del environment `meta-testing` y después
del health gate público.

`deliver-note` valida la nota y el hash del anuncio, comprueba que la imagen ya sea pública,
reconcilia publicaciones recientes y conserva checkpoints separados para Facebook e Instagram.
Una plataforma confirmada nunca se repite; un resultado incierto requiere revisión manual.

## Imagen y copy

El fondo puede ser una fotografía de stock o una imagen generada sin texto ni logotipos. El
archivo publicado siempre es el JPG vertical producido por la plantilla `nota`, con marca,
título legible y CTA. Los captions se derivan de la nota desplegada y enlazan su URL canónica.

## Configuración

Los secretos `META_ACCESS_TOKEN`, `FB_PAGE_ID` e `IG_USER_ID` existen sólo en `meta-testing`.
El workflow fija `META_GRAPH_VERSION=v26.0`, `META_ENVIRONMENT=testing`, `SOCIAL_ENABLED=1` y
`SOCIAL_DRY_RUN=0`. Ningún secreto se versiona ni llega a la automatización editorial.

Las plantillas y utilidades históricas se mantienen para previsualización local, pero no son una
autoridad de publicación.
