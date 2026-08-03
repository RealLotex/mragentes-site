/* =========================================
   MR AGENTES — model3d.js
   Viewer 3D con Three.js (GLB/GLTF)
   - Turntable infinito
   - Rotación sutil siguiendo el puntero (indica interactividad)
   - Skeleton loader mientras descarga
   - Resolución adaptativa: baja en mobile / bajo rendimiento
   - Si el modelo no existe (404), el panel se oculta
   ========================================= */

(function () {
  'use strict';

  var panels = document.querySelectorAll('[data-model3d]');
  if (!panels.length) return;

  // ---------- Detección de rendimiento ----------
  var IS_MOBILE = window.matchMedia('(pointer: coarse)').matches
    || window.innerWidth < 768
    || (navigator.maxTouchPoints && navigator.maxTouchPoints > 1 && window.innerWidth < 1024);
  var LOW_CORES = (navigator.hardwareConcurrency || 8) <= 4;
  var LOW_QUALITY = IS_MOBILE || LOW_CORES;

  var REDUCED_MOTION = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // ---------- Cargar Three.js dinámico ----------
  var threeReady = null;
  function loadThree() {
    if (threeReady) return threeReady;
    threeReady = new Promise(function (resolve, reject) {
      // Import map + módulo three desde CDN (jsdelivr, versión fija)
      var script = document.createElement('script');
      script.type = 'importmap';
      script.textContent = JSON.stringify({
        imports: {
          'three': 'https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js',
          'three/addons/': 'https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/'
        }
      });
      document.head.appendChild(script);

      var loader = document.createElement('script');
      loader.type = 'module';
      loader.textContent = `
        import * as THREE from 'three';
        import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
        window.__THREE__ = { THREE: THREE, GLTFLoader: GLTFLoader };
        window.dispatchEvent(new CustomEvent('three-ready'));
      `;
      document.head.appendChild(loader);

      var done = false;
      var finish = function () {
        if (done) return;
        done = true;
        if (window.__THREE__) resolve(window.__THREE__);
        else reject(new Error('three no cargó'));
      };
      window.addEventListener('three-ready', finish);
      setTimeout(finish, 15000);
    });
    return threeReady;
  }

  // ---------- Por panel ----------
  panels.forEach(function (panel) {
    var src = panel.getAttribute('data-model3d');
    var label = panel.getAttribute('data-label') || 'Modelo 3D';
    var skeleton = panel.querySelector('.model3d-skeleton');

    // Verificar que el modelo exista; si no, ocultar el panel (sin romper nada)
    fetch(src, { method: 'HEAD' })
      .then(function (res) {
        if (!res.ok) {
          panel.style.display = 'none';
          return null;
        }
        return loadThree();
      })
      .then(function (THREEmod) {
        if (!THREEmod) return;
        initScene(panel, skeleton, src, label, THREEmod.THREE, THREEmod.GLTFLoader);
      })
      .catch(function () {
        panel.style.display = 'none';
      });
  });

  function initScene(panel, skeleton, src, label, THREE, GLTFLoader) {
    // Canvas propio para no pisar el skeleton
    var wrapper = document.createElement('div');
    wrapper.className = 'model3d-canvas';
    panel.appendChild(wrapper);

    var rect = panel.getBoundingClientRect();
    var w = rect.width || 400;
    var h = rect.height || 400;

    var renderer;
    try {
      renderer = new THREE.WebGLRenderer({
        antialias: !LOW_QUALITY,
        alpha: true,
        powerPreference: LOW_QUALITY ? 'low-power' : 'high-performance'
      });
    } catch (e) {
      // Sin WebGL (navegador viejo / GPU bloqueada): ocultar panel, no dejar skeleton infinito
      panel.style.display = 'none';
      return;
    }
    renderer.setPixelRatio(LOW_QUALITY ? 1 : Math.min(window.devicePixelRatio, 2));
    renderer.setSize(w, h);
    wrapper.appendChild(renderer.domElement);

    var scene = new THREE.Scene();
    var camera = new THREE.PerspectiveCamera(40, w / h, 0.1, 100);
    camera.position.set(0, 0.55, 3.2);
    camera.lookAt(0, 0, 0);

    // Luces
    var ambient = new THREE.AmbientLight(0xfff2dd, 1.6);
    scene.add(ambient);
    var key = new THREE.DirectionalLight(0xfff0d8, 2.2);
    key.position.set(2.5, 4, 3);
    scene.add(key);
    var fill = new THREE.DirectionalLight(0xffd9a0, 0.9);
    fill.position.set(-3, 1, -2);
    scene.add(fill);

    var group = new THREE.Group();
    scene.add(group);

    var loader = new GLTFLoader();
    loader.load(src, function (gltf) {
      var model = gltf.scene;

      // Centrar el modelo en su origen ANTES de escalar
      var box = new THREE.Box3().setFromObject(model);
      var center = new THREE.Vector3();
      box.getCenter(center);
      model.position.sub(center);

      // Escala basada en el frustum de la cámara: el modelo ocupa ~75% del alto
      // del panel sin importar las unidades del GLB (Sketchfab usa cm/mm).
      var size = new THREE.Vector3();
      box.getSize(size);
      var maxDim = Math.max(size.x, size.y, size.z);
      var dist = camera.position.distanceTo(new THREE.Vector3(0, 0, 0));
      var fovHeight = 2 * dist * Math.tan(THREE.MathUtils.degToRad(camera.fov / 2));
      var fill = LOW_QUALITY ? 0.7 : 0.78;
      var scale = (fovHeight * fill) / maxDim;
      model.scale.setScalar(scale);

      group.add(model);
      group.position.y = -0.1;

      // Quitar skeleton
      if (skeleton) skeleton.style.display = 'none';
    }, undefined, function (err) {
      console.warn('model3d:', src, err);
      panel.style.display = 'none';
    });

    // ---------- Turntable infinito + pointer-follow ----------
    var rotationSpeed = REDUCED_MOTION ? 0 : 0.004;
    var targetRotY = 0;
    var targetRotX = 0;
    var currentRotY = 0;
    var currentRotX = 0;
    // Pointer follow (solo con puntero fino o en desktop)
    if (!IS_MOBILE && !REDUCED_MOTION) {
      panel.addEventListener('mousemove', function (e) {
        var r = panel.getBoundingClientRect();
        var nx = (e.clientX - r.left) / r.width - 0.5;   // -0.5..0.5
        var ny = (e.clientY - r.top) / r.height - 0.5;
        targetRotY = nx * 0.6;
        targetRotX = -ny * 0.4;
      });
      panel.addEventListener('mouseleave', function () {
        targetRotY = 0;
        targetRotX = 0;
      });
    }

    // ---------- Render loop con pausa fuera de viewport ----------
    var visible = true;
    var ro = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        visible = entry.isIntersecting;
      });
    }, { threshold: 0.05 });
    ro.observe(panel);

    var running = true;
    var fpsFrames = 0;
    var fpsTime = 0;
    var degraded = LOW_QUALITY;

    function loop() {
      if (!running) return;
      requestAnimationFrame(loop);

      if (!visible) return;

      // FPS monitoring para degradar resolución automáticamente
      fpsFrames++;
      fpsTime += 16.67;
      if (fpsTime >= 2000) {
        var fps = fpsFrames * 1000 / fpsTime;
        if (!degraded && fps < 28) {
          degraded = true;
          renderer.setPixelRatio(1);
          renderer.setSize(w, h, false);
        }
        fpsFrames = 0;
        fpsTime = 0;
      }

      // Turntable: rotación continua + easing hacia el puntero
      currentRotY += rotationSpeed;
      currentRotX += (targetRotX - currentRotX) * 0.08;
      group.rotation.y = currentRotY + targetRotY;
      group.rotation.x = targetRotX * 0.5;

      renderer.render(scene, camera);
    }
    loop();

    // Resize
    var onResize = function () {
      var r = panel.getBoundingClientRect();
      if (r.width > 0 && r.height > 0) {
        w = r.width;
        h = r.height;
        camera.aspect = w / h;
        camera.updateProjectionMatrix();
        renderer.setSize(w, h, false);
      }
    };
    window.addEventListener('resize', onResize);
  }
})();
