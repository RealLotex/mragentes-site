# AGENTS.md — contrato del repositorio

Este archivo rige todo el árbol. El proyecto se opera con Codex, tareas programadas de
ChatGPT y GitHub; no agregues otra autoridad de ejecución.

## Flujo obligatorio

1. Leé el pedido, los contratos existentes y los archivos que vayas a tocar.
2. Definí alcance, arquitectura, riesgos, archivos y criterio de aceptación.
3. Escribí primero un test que falle por la ausencia del cambio y conservá la evidencia RED.
4. Implementá el cambio mínimo con `apply_patch`.
5. Ejecutá el test focalizado hasta GREEN y luego la suite proporcional al riesgo.
6. Para cambios visuales, renderizá y verificá escritorio y móvil.
7. Informá archivos cambiados, pruebas ejecutadas y cualquier efecto externo pendiente.

TDD es obligatorio para código, contratos, configuración y documentación operativa. Una
prueba que ya pasaba antes del cambio no demuestra RED.

## Límites de trabajo

- Preservá cambios ajenos y evitá reescrituras destructivas.
- Buscá con `rg`; editá con `apply_patch`; prepará en Git sólo rutas revisadas y explícitas.
- No uses comandos destructivos, force push ni atajos que incorporen todo el árbol.
- No publiques, despliegues ni cambies tareas programadas salvo que el pedido lo autorice.
- Los cambios automáticos entran por ramas `automation/**`, pull request, CI y merge protegido.
- GitHub Pages es la única publicación web; GitHub Actions ejecuta los efectos posteriores.
- Meta permanece en el entorno `meta-testing` hasta una decisión explícita del propietario.
- La entrega de Cloudflare se administra con el conector; no agregues credenciales ni CLI de
  despliegue al runtime del repositorio.

## Seguridad e independencia

- Este repositorio es público. Nunca leas, muestres, registres ni versiones secretos.
- Los secretos viven en entornos protegidos de GitHub o en el proveedor correspondiente.
- Toda llamada externa debe ser autenticada, acotada, observable e idempotente.
- Ante resultado remoto incierto, detené la repetición y marcá revisión manual.
- Ningún flujo puede depender de cuentas, procesos, rutas personales o servicios retirados.

## Definición de terminado

El cambio está terminado sólo si sus contratos están GREEN, el build relevante pasa, no hay
secretos ni dependencias retiradas, y la documentación coincide con el comportamiento real.
Consultá `ARCHITECTURE.md`, `OPERATIONS.md` y `SECURITY.md` para los contratos del sistema.
