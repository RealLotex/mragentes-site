/* =========================================
   MR AGENTES — model3d.js v12
   Modelos 3D sticky de fondo de sección
   - El modelo queda fijo (sticky) en su posición relativa a la vista mientras
     scrolleás: su centro queda ANCLADO y rota con el progreso de scroll
   - Rotación por scroll reducida al 30% (sutil): horizontal ≈0→-108° (rotY)
     y vertical -13.5°→+13.5° (rotX). Se compensa la traslación vertical
     (group.position.y = sin(rotX)). Puntero añade tilt fino.
   - Offset de rotación inicial por modelo (180° para San Pedro y el busto).
   - Fit por ESFERA circunscripta usando el wrapper (que se extiende más allá
     del stage): el modelo fluye fuera de los bordes del elemento sin recorte.
   - Escala 0.95 del frustum, opacidad 50%, degradación automática mobile.
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

    // Offset de rotación inicial (Y) por modelo: algunos modelos llegan
    // orientados de frente/espaldas y hay que girarlos 180° para mostrarlos
    // bien. San Pedro (home-proyectos) y el busto (home-datos).
    var rotOffsetY = 0;
    if (/proyectos|datos|home-proyectos|home-datos/.test(src)) {
      rotOffsetY = Math.PI; // 180°
    }


    // Opacidad 50%
    wrapper.style.opacity = '0.5';

    var modelLoaded = false;

    // Radio de la ESFERA circunscripta del modelo (sin escala). Acá guardamos
    // el radio real, no la dimensión máxima del box: la esfera garantiza que el
    // modelo NUNCA se recorte sin importar cómo rote (el box alineado a ejes
    // crece al girar y causaba crop).
    var modelRadius = 1;

    // --- Reescala del canvas según el espacio real (no el del init) ---
    // El modelo usa TODO el espacio disponible: el wrapper se extiende más allá
    // del stage (inset negativo en CSS), así que se mide el wrapper, no el
    // stage, para que el modelo fluya fuera de los bordes del elemento.
    function refit() {
      if (!modelLoaded) return;
      var el = wrapper && wrapper.clientWidth ? wrapper : stage;
      var cw = el.clientWidth || w;
      var ch = el.clientHeight || h;
      if (cw > 0) w = cw;
      if (ch > 0) h = ch;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h, false);

      // Escala la esfera del modelo para que quepa en el cono de visión, con un
      // factor generoso (0.95) para usar casi todo el espacio sin recortar.
      var dist = camera.position.length();
      var vHalf = Math.tan(THREE.MathUtils.degToRad(camera.fov / 2));
      var fitH = (2 * dist * vHalf * 0.95) / modelRadius;
      var hFov = 2 * Math.atan(vHalf * camera.aspect);
      var fitW = (2 * dist * Math.tan(hFov / 2) * 0.95) / modelRadius;
      group.scale.setScalar(Math.min(fitH, fitW));
    }

    var loader = new GLTFLoader();
    loader.load(src, function (gltf) {
      var model = gltf.scene;

      // --- FIX ORIGEN: centrar el MODELO, no el group ---
      model.updateMatrixWorld(true);
      var box = new THREE.Box3().setFromObject(model);
      var center = new THREE.Vector3();
      box.getCenter(center);
      model.position.sub(center);

      group.add(model);
      group.updateMatrixWorld(true);

      // Guardar el radio de la esfera circunscripta (usado por refit).
      box = new THREE.Box3().setFromObject(group);
      var size = new THREE.Vector3();
      box.getSize(size);
      var half = size.length() / 2; // media diagonal => radio de la esfera
      modelRadius = Math.max(0.001, half);

      modelLoaded = true;
      refit();

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

    // ---------- Pausa fuera de viewport ----------
    function clamp(v, min, max) {
      return Math.max(min, Math.min(max, v));
    }

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
      // - horizontal: 0→-360° (rotY) a lo largo de la sección
      // - vertical: -45°→+45° (rotX)
      // Para que el modelo PAREZCA quieto en su lugar (sticky) mientras rota
      // en dos ejes, compensamos la traslación vertical: rotar en X desplaza
      // el centro aparente del modelo hacia arriba/abajo dentro del canvas.
      // Movemos el group en Y con la señal contraria según el radio real del
      // modelo (modelRadius * escala), de modo que el centro visual quede
      // anclado aunque rote y no parece "subir o bajar" con el texto.
      var rotY = -currentP * Math.PI * 2 * 0.3 + tiltY + rotOffsetY;
      var rotX = clamp(-(currentP - 0.5) * (Math.PI / 2) * 0.3 + tiltX, -Math.PI / 4, Math.PI / 4);

      group.rotation.y = rotY;
      group.rotation.x = rotX;
      // Compensación vertical: contrarrresta el corrimiento de la rotación en X
      // para mantener el centro del modelo fijo respecto al viewport.
      group.position.y = Math.sin(rotX);

      renderer.render(scene, camera);
    }
    loop();

    function onResize() {
      refit();
    }
    window.addEventListener('resize', onResize);
  }
})();
