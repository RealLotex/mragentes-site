/* =========================================
   MR AGENTES — model3d.js v9
   Modelos 3D sticky de fondo de sección
   - El modelo queda fijo (sticky) centrado verticalmente mientras scrolleás
     el texto de la sección; solo rota con el progreso de scroll
   - Horizontal 0→360°, vertical -45°→+45° (por scroll, sin turntable)
   - Origen centrado en el MODELO (no en el group): rota sobre el centro real
   - Escala: modelo completo visible, opacidad 50%, máxima resolución
   - Mobile: banda 320px, degradación automática si FPS < 24
   ========================================= */

(function () {
  'use strict';

  var stages = document.querySelectorAll('[data-model3d]');
  if (!stages.length) return;

  var IS_MOBILE = window.matchMedia('(pointer: coarse)').matches
    || window.innerWidth < 768
    || (navigator.maxTouchPoints && navigator.maxTouchPoints > 1 && window.innerWidth < 1024);
  var REDUCED_MOTION = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // ---------- Cargar Three.js dinámico ----------
  var threeReady = null;
  function loadThree() {
    if (threeReady) return threeReady;
    threeReady = new Promise(function (resolve, reject) {
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

  stages.forEach(function (stage) {
    var src = stage.getAttribute('data-model3d');
    var section = stage.closest('.section-3d') || stage.parentElement;
    var skeleton = stage.querySelector('.model3d-skeleton');

    fetch(src, { method: 'HEAD' })
      .then(function (res) {
        if (!res.ok) {
          stage.style.display = 'none';
          return null;
        }
        return loadThree();
      })
      .then(function (mod) {
        if (mod) init(stage, section, skeleton, src, mod.THREE, mod.GLTFLoader);
      })
      .catch(function () {
        stage.style.display = 'none';
      });
  });

  function init(stage, section, skeleton, src, THREE, GLTFLoader) {
    var wrapper = document.createElement('div');
    wrapper.className = 'model3d-stage-canvas';
    stage.appendChild(wrapper);

    var w = stage.clientWidth || 600;
    var h = stage.clientHeight || 600;

    var renderer;
    try {
      renderer = new THREE.WebGLRenderer({
        antialias: true,
        alpha: true,
        powerPreference: 'high-performance'
      });
    } catch (e) {
      stage.style.display = 'none';
      return;
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setSize(w, h);
    wrapper.appendChild(renderer.domElement);

    var scene = new THREE.Scene();
    var camera = new THREE.PerspectiveCamera(40, w / h, 0.1, 200);
    camera.position.set(0, 0.4, 3.4);
    camera.lookAt(0, 0, 0);

    // Luces cálidas (pergamino)
    var ambient = new THREE.AmbientLight(0xfff2dd, 1.8);
    scene.add(ambient);
    var key = new THREE.DirectionalLight(0xfff0d8, 2.4);
    key.position.set(2.5, 4, 3);
    scene.add(key);
    var fill = new THREE.DirectionalLight(0xffd9a0, 1.0);
    fill.position.set(-3, 1, -2);
    scene.add(fill);

    var group = new THREE.Group();
    scene.add(group);

    var loader = new GLTFLoader();
    loader.load(src, function (gltf) {
      var model = gltf.scene;

      // --- FIX ORIGEN: centrar el MODELO, no el group ---
      // (aplicar posición y luego escalar el group multiplicaba el offset
      //  por el scale y los modelos con origen desplazado quedaban fuera)
      model.updateMatrixWorld(true);
      var box = new THREE.Box3().setFromObject(model);
      var center = new THREE.Vector3();
      box.getCenter(center);
      model.position.sub(center);

      group.add(model);
      group.updateMatrixWorld(true);

      // Escala fit: modelo completo visible (90% del alto del stage)
      box = new THREE.Box3().setFromObject(group);
      var size = new THREE.Vector3();
      box.getSize(size);
      var maxDim = Math.max(size.x, size.y, size.z) || 1;
      var dist = camera.position.length();
      var vHalf = Math.tan(THREE.MathUtils.degToRad(camera.fov / 2));
      var fitH = (2 * dist * vHalf * 0.9) / maxDim;
      var hFov = 2 * Math.atan(vHalf * camera.aspect);
      var fitW = (2 * dist * Math.tan(hFov / 2) * 0.9) / maxDim;
      group.scale.setScalar(Math.min(fitH, fitW));

      if (skeleton) skeleton.style.display = 'none';
    }, undefined, function (err) {
      console.warn('model3d:', src, err);
      stage.style.display = 'none';
    });

    // Opacidad 50%
    wrapper.style.opacity = '0.5';

    // ---------- Progreso de scroll (basado en la SECCIÓN, no en el stage) ----------
    // Con sticky el stage queda fijo; el progreso se calcula sobre el recorrido
    // completo de la sección: 0 al entrar, 1 al salir.
    var progress = 0;
    var currentP = 0;
    function updateScroll() {
      var r = section.getBoundingClientRect();
      var vh = window.innerHeight;
      var total = r.height + vh;
      var done = vh - r.top;
      progress = Math.max(0, Math.min(1, done / total));
    }
    updateScroll();
    window.addEventListener('scroll', updateScroll, { passive: true });
    window.addEventListener('resize', updateScroll);

    // ---------- Tilt hacia el puntero (sutil) ----------
    var tiltY = 0, tiltX = 0, tiltTargetY = 0, tiltTargetX = 0;
    if (!IS_MOBILE && !REDUCED_MOTION) {
      section.addEventListener('mousemove', function (e) {
        var r = section.getBoundingClientRect();
        var nx = (e.clientX - r.left) / r.width - 0.5;
        var ny = (e.clientY - r.top) / r.height - 0.5;
        tiltTargetY = nx * 0.25;
        tiltTargetX = ny * 0.12;
      });
      section.addEventListener('mouseleave', function () {
        tiltTargetY = 0;
        tiltTargetX = 0;
      });
    }

    function clamp(v, min, max) {
      return Math.max(min, Math.min(max, v));
    }

    // ---------- Pausa fuera de viewport ----------
    var visible = true;
    var ro = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        visible = entry.isIntersecting;
      });
    }, { threshold: 0.02 });
    ro.observe(section);

    // ---------- Loop ----------
    var frames = 0, acc = 0, degraded = false;
    function loop() {
      requestAnimationFrame(loop);
      if (!visible) return;

      // Degradación automática SOLO en mobile si va mal
      if (IS_MOBILE) {
        frames++;
        acc += 16.67;
        if (acc >= 2000) {
          var fps = frames * 1000 / acc;
          if (!degraded && fps < 24) {
            degraded = true;
            renderer.setPixelRatio(1);
            renderer.setSize(w, h, false);
          }
          frames = 0;
          acc = 0;
        }
      }

      // Easing del scroll
      currentP += (progress - currentP) * 0.06;
      tiltY += (tiltTargetY - tiltY) * 0.08;
      tiltX += (tiltTargetX - tiltX) * 0.08;

      // Rotación INVERTIDA (sentido contrario al scroll):
      // horizontal: 0→-360° a lo largo de la sección. Vertical: -45°→+45° invertido.
      var rotY = -currentP * Math.PI * 2 + tiltY;
      var rotX = clamp(-(currentP - 0.5) * (Math.PI / 2) + tiltX, -Math.PI / 4, Math.PI / 4);

      group.rotation.y = rotY;
      group.rotation.x = rotX;

      renderer.render(scene, camera);
    }
    loop();

    function onResize() {
      var rw = stage.clientWidth;
      var rh = stage.clientHeight;
      if (rw > 0 && rh > 0) {
        w = rw;
        h = rh;
        camera.aspect = w / h;
        camera.updateProjectionMatrix();
        renderer.setSize(w, h, false);
      }
    }
    window.addEventListener('resize', onResize);
  }
})();
