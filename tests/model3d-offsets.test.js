/*
 * Test para la lógica de offsets de rotación de los modelos 3D.
 *
 * Requisito (TDD):
 *  - San Pedro (home-proyectos) debe devolver rotOffsetY = Math.PI (180°)
 *  - El busto (home-datos)    debe devolver rotOffsetY = Math.PI (180°)
 *  - Cualquier otro modelo (home-servicios, contacto, nosotros, servicios)
 *    debe devolver rotOffsetY = 0 (sin offset, se ve bien).
 *
 * Run: node tests/model3d-offsets.test.js
 */
const assert = require('assert');
const path = require('path');
const getModelRotationOffset = require(
  path.join(__dirname, '..', 'static', 'js', 'model3d-offsets.js')
).getModelRotationOffset;

const TAU = 2 * Math.PI;
function approx(a, b, eps) {
  return Math.abs(a - b) < (eps || 1e-9);
}

let failures = 0;
function test(name, fn) {
  try {
    fn();
    console.log('  \u2713 ' + name);
  } catch (e) {
    failures++;
    console.error('  \u2717 ' + name);
    console.error('      ' + e.message);
  }
}

console.log('Modelo home-proyectos (San Pedro) => 180° (Math.PI)');
test('home-proyectos.glb devuelve Math.PI', () => {
  assert.strictEqual(
    getModelRotationOffset('/models/home-proyectos.glb'),
    Math.PI, // San Pedro: 180°
  );
});

console.log('Modelo home-datos (el busto) => 180° (Math.PI)');
test('home-datos.glb devuelve Math.PI', () => {
  assert.strictEqual(
    getModelRotationOffset('/models/home-datos.glb'),
    Math.PI, // el busto: 180°
  );
});

console.log('Otros modelos => sin offset (0)');
test('home-servicios.glb devuelve 0', () => {
  assert.strictEqual(getModelRotationOffset('/models/home-servicios.glb'), Math.PI * 0); // ok 0
});
test('contacto.glb devuelve 0', () => {
  assert.strictEqual(getModelRotationOffset('/models/contacto.glb'), Math.PI * 0);
});
test('nosotros.glb devuelve 0', () => {
  assert.strictEqual(getModelRotationOffset('/models/nosotros.glb'), Math.PI * 0);
});
test('servicios.glb devuelve 0', () => {
  assert.strictEqual(getModelRotationOffset('/models/servicios.glb'), Math.PI * 0);
});
test('string vacío devuelve 0', () => {
  assert.strictEqual(getModelRotationOffset(''), Math.PI * 0);
});
test('undefined devuelve 0', () => {
  assert.strictEqual(getModelRotationOffset(undefined), Math.PI * 0);
});

console.log('Sanidad: 180° es Math.PI radianes');
test('Math.PI equivale a 180°', () => {
  assert.ok(approx(getModelRotationOffset('/models/home-proyectos.glb'), Math.PI));
});

if (failures > 0) {
  console.error('\n  ✗ ' + failures + ' test(s) fallaron.');
  process.exit(1);
}
console.log('\n  ✓ Todos los tests pasaron.');
process.exit(0);
