# Recuperación segura

Clasificá el estado por plataforma:

- `complete`: existe un único ID remoto confirmado; omitir;
- `missing`: el fallo ocurrió antes de crear contenido remoto; se puede reintentar sólo esa plataforma;
- `uncertain`: el efecto pudo ocurrir; reconciliar antes de reintentar;
- `needs_review`: hay cero, varias o conflictivas coincidencias remotas; detener.

La reconciliación compara la ventana temporal, el hash normalizado, el recurso y el permalink. Sólo una coincidencia inequívoca permite reconstruir el checkpoint. Nunca uses `force`, nunca borres un éxito confirmado y nunca generes una segunda pieza para resolver un fallo de entrega.

## Recuperación programada

Usá el conector de GitHub para leer la ejecución de `social-daily.yml` o
`social-note.yml` correspondiente a la fecha local:

- si está `in_progress`, no interfieras y devolvé `skipped`;
- si terminó correctamente, devolvé `skipped`;
- si falló antes de un efecto remoto y el error es `retryable`, reintentá sólo
  los jobs fallidos de esa misma ejecución;
- si el resultado es `uncertain` o `needs_review`, detenete y reportá la
  evidencia sin reintentar.

El reintento siempre vuelve a entrar por el workflow guardado en GitHub. No
llames a Meta desde la tarea de Codex, no despaches otro draft y no accedas a
cuentas o procesos retirados.
