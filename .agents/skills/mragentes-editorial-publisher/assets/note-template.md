# Formato de entrada al publicador

Guardá un JSON fuera del repositorio. Los valores siguientes indican el formato, no son hechos
ni enlaces aptos para publicación:

```json
{
  "title": "Título con sujeto y hecho concreto",
  "summary": "Una oración de hasta 160 caracteres con el dato principal.",
  "body": "Primer párrafo con quién, qué y cuándo. [Fuente original](https://FUENTE_REAL).\\n\\n## Un subtítulo útil\\n\\nDatos y límites con citas junto a cada afirmación.",
  "image_alt": "Descripción literal de la fotografía",
  "source_url": "https://FUENTE_REAL",
  "source_name": "Nombre de la fuente",
  "source_date": "YYYY-MM-DD",
  "related_sources": [],
  "tags": ["ia", "actualidad"],
  "image_credit": {
    "source_url": "https://PAGINA_REAL_DE_LA_FOTO",
    "creator": "Autor real",
    "license_url": "https://LICENCIA_REAL"
  }
}
```

La imagen se entrega como un archivo JPG o PNG separado. El comando construye los metadatos
Hugo y todos los artefactos derivados.
