# Recuperación segura

Clasificá el estado por plataforma:

- `complete`: existe un único ID remoto confirmado; omitir;
- `missing`: el fallo ocurrió antes de crear contenido remoto; se puede reintentar sólo esa plataforma;
- `uncertain`: el efecto pudo ocurrir; reconciliar antes de reintentar;
- `needs_review`: hay cero, varias o conflictivas coincidencias remotas; detener.

La reconciliación compara la ventana temporal, el hash normalizado, el recurso y el permalink. Sólo una coincidencia inequívoca permite reconstruir el checkpoint. Nunca uses `force`, nunca borres un éxito confirmado y nunca generes una segunda pieza para resolver un fallo de entrega.
