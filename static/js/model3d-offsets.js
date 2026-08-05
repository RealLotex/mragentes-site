/*
 * model3d-offsets.js — Lógica pura de offsets de rotación inicial (Y) por modelo.
 *
 * Funciona en browser (se expone como window.MRModelOffsets) y en Node
 * (module.exports) para poder testearla con TDD en Node.
 *
 * Requisito (2026-08-05):
 *   - home-proyectos (San Pedro) => rotOffsetY = Math.PI  (180°)
 *   - home-datos (el busto)      => rotOffsetY = Math.PI  (180°)
 *   - cualquier otro modelo      => rotOffsetY = 0  (se ven bien)
 *
 * No hay debug keys ni configuración runtime: los valores son fijos y deterministas.
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.MRModelOffsets = factory();
  }
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  /**
   * Devuelve el offset de rotación inicial en el eje Y (radianes) para un
   * modelo dado por su ruta/src.
   *
   * @param {string|null|undefined} src  ruta del .glb (p.ej. "/models/home-proyectos.glb")
   * @returns {number} rotación en radianes (Math.PI => 180°)
   */
  function getModelRotationOffset(src) {
    if (typeof src !== 'string') return 0;
    // San Pedro y el busto: ambos requieren 180°.
    if (/home-proyectos|home-datos/.test(src)) {
      return Math.PI; // 180°
    }
    return 0;
  }

  return {
    getModelRotationOffset: getModelRotationOffset,
  };
});
