# PLAN — MR Agentes Website con Hugo + GitHub Pages

## Objetivo
Sitio web estático MR Agentes con Hugo, deploy automático a GitHub Pages,
publicación diaria de contenido sincronizado con Instagram.

## Stack
- **SSG:** Hugo (última versión estable)
- **Theme:** Minimalista, customizado con brand MR Agentes
- **Hosting:** GitHub Pages (con dominio propio o user.github.io)
- **CI/CD:** GitHub Actions (deploy automático en push a main)
- **Automation:** Cron de OpenClaw → daily post → commit → push → deploy

## Estructura del sitio
```
/
├── content/
│   ├── _index.md          → Página de inicio (hero, servicios, CTA, últimas notas)
│   ├── nosotros.md        → Quiénes somos, valores, equipo
│   ├── servicios.md       → Servicios ofrecidos, precios/paquetes
│   ├── contacto.md        → Formulario de contacto, WhatsApp, redes
│   └── notas/             → Blog/notas (publicación diaria)
│       ├── nota-1.md
│       └── ...
├── assets/
│   ├── images/
│   │   └── mragentes.png  → Logo oficial
│   └── css/
│       └── brand.css      → Estilos custom (overrides del theme)
├── layouts/
│   └── ...                → Overrides de templates si es necesario
├── config.toml
└── static/
    └── ...                → Archivos estáticos extras
```

## Brand MR Agentes (desde INSTAGRAM-BRAND.md)
- **Primary color:** #2596be (azul)
- **Secondary:** #8b5cf6 (índigo)
- **Dark text:** #1a1a1a
- **Font:** Inter (400-900), desde Google Fonts
- **Logo:** mragentes.png
- **Tono:** institucional-profesional, voseo rioplatense

## Páginas

### Inicio (`_index.md`)
- Hero section con tagline y CTA
- Grid de servicios (3-4 cards)
- Últimas 3 notas del blog
- CTA final de contacto/WhatsApp

### Nosotros
- Quiénes somos
- Valores / Misión / Visión
- Diferenciadores
- Link a Instagram y redes

### Servicios
- Cards de servicios con descripción
- Paquetes o pricing (si aplica)
- CTA a contacto

### Notas (blog)
- Listado cronológico inverso
- Cada nota: título, fecha, extracto, link
- Página individual de nota

### Contacto
- Formulario (Netlify Forms o Formspree)
- WhatsApp directo (link wa.me)
- Instagram, Facebook, email
- Mapa/horarios (si aplica)

## Flujo de publicación diaria
1. Cron de OpenClaw (12:00) ejecuta script `publish_daily.py`
2. Script:
   a. Toma contenido del calendario o genera nota nueva
   b. Crea `/content/notas/YYYY-MM-DD-titulo.md`
   c. Commit + push a `main`
   d. GitHub Actions hace deploy automático a Pages
3. Opcional: generar y subir imágenes del post como ilustración

## Setup inicial (necesito del usuario)
1. Token de GitHub con repo + actions scope
2. Usuario de GitHub
3. Nombre de repo preferido (ej: mragentes-site)
4. Dominio personalizado (opcional)
5. Preferencia de theme Hugo (o elegir uno)

## Skill + TOOLS.md update
Una vez operativo, crear skill `hugo-publisher` y actualizar TOOLS.md
para que el cron use el pipeline completo.

## Milestones
1. ✅ PLAN.md creado
2. ⬜ Usuario provee credenciales GitHub
3. ⬜ Hugo instalado + sitio creado
4. ⬜ Brand aplicado + páginas maquetadas
5. ⬜ Repo creado + GitHub Actions configurado
6. ⬜ Primer deploy exitoso
7. ⬜ Skill creado + cron configurado
8. ⬜ Publicación diaria automática OK
