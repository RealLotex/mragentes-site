/* =========================================
   MR AGENTES — model3d.js v19
   Modelos 3D sticky de fondo de sección
   - El modelo queda fijo (sticky) en su posición relativa a la vista mientras
     scrolleás: su centro queda ANCLADO y rota con el progreso de scroll
   - Rotación por scroll reducida al 30% (sutil): horizontal ≈0→-108° (rotY)
     y vertical COMPLETO -45°→+45° (rotX). Se compensa la traslación vertical
     (group.position.y = sin(rotX)). Puntero añade tilt fino.
   - Offset de rotación inicial por modelo (180° para San Pedro y el busto).
   - Fit por ESFERA circunscripta usando el wrapper (que se extiende más allá
     del stage): el modelo fluye fuera de los bordes del elemento sin recorte.
   - Escala 0.95 del frustum, opacidad 50%, degradación automática mobile.

   v17 (fix definitivo "que nunca falle"):
   - Eliminado el HEAD fetch como GATE: el modelo solo se decide por el GET
     real del .glb (si no hay red, Three, WebGL o el .glb da error, se degrada
     limpiamente y se oculta el skeleton SIEMPRE).
   - Todo init() está envuelto en try/catch externo: cualquier excepción
     oculta el skeleton y deja el layout 100% intacto (nunca display:none del
     stage).
   - loader.load() se dispara SIEMPRE que haya Three, sin depender del tamaño
     del stage (que puede estar a 0x0 mientras el layout pinta) — el refit
     corrige el tamaño en cuanto haya espacio.
   - skeleton.style.display se oculta en TODOS los caminos (success y error).
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
        import { DRACOLoader } from 'three/addons/loaders/DRACOLoader.js';
        window.__THREE__ = { THREE: THREE, GLTFLoader: GLTFLoader, DRACOLoader: DRACOLoader };
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
      setTimeout(finish, 12000);
    });
    return threeReady;
  }

  // Oculta el skeleton de un stage de forma segura (no rompe el layout).
  function hideSkeleton(stage) {
    var skeleton = stage && stage.querySelector('.model3d-skeleton');
    if (skeleton) skeleton.style.display = 'none';
  }

  stages.forEach(function (stage) {
    var src = stage.getAttribute('data-model3d');
    var section = stage.closest('.section-3d') || stage.parentElement;
    var skeleton = stage.querySelector('.model3d-skeleton');

    // Regla de oro: el skeleton NUNCA puede quedar visible para siempre.
    // Ponemos un timeout de seguridad que lo oculta si nada termina a tiempo,
    // y el layout se preserva porque ocultar el skeleton no toca el stage.
    var skeletonTimer = setTimeout(function () {
      if (skeleton) skeleton.style.display = 'none';
    }, 9000);

    // --- Flujo NO bloqueado por HEAD ---
    // El HEAD es solo una optimización opcional: no decide si cargamos ni
    // bloquea el resto. El GET del .glb dentro de init() es el que manda.
    var headOk = false;
    try {
      fetch(src, { method: 'HEAD' })
        .then(function (res) { headOk = res.ok ? true : false; })
        .catch(function () { headOk = false; });
    } catch (e) { headOk = false; }

    loadThree()
      .then(function (mod) {
        // Skeleton: si tres demoró, al cargar lo ocultamos y dejamos que el
        // canvas se vea dentro de init().
        clearTimeout(skeletonTimer);
        try {
          init(stage, section, skeleton, src, mod.THREE, mod.GLTFLoader, mod.DRACOLoader);
        } catch (err) {
          console.warn('model3d: init falló', src, err);
          hideSkeleton(stage);
        }
      })
      .catch(function (err) {
        console.warn('model3d: three no cargó', src, err);
        clearTimeout(skeletonTimer);
        hideSkeleton(stage);
      });
  });

  function init(stage, section, skeleton, src, THREE, GLTFLoader, DRACOLoader) {
    // Asegurar que el skeleton se oculte apenas empecemos (sin esperar al GLB).
    hideSkeleton(stage);

    var wrapper = document.createElement('div');
    wrapper.className = 'model3d-stage-canvas';
    stage.appendChild(wrapper);

    // Tamaño: NO asumimos que el stage tiene tamaño real (puede estar 0x0
    // mientras el layout pinta). Siempre caemos a algo >= 1px para que WebGL
    // y el refit no se rompan.
    function stageSize() {
      var w = stage.clientWidth || section.clientWidth || window.innerWidth || 1;
      var h = stage.clientHeight || section.clientHeight || window.innerHeight || 1;
      return { w: Math.max(1, w), h: Math.max(1, h) };
    }
    var size = stageSize();

    var renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: true,
      powerPreference: 'high-performance'
    });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setSize(size.w, size.h, false);
    wrapper.appendChild(renderer.domElement);

    var scene = new THREE.Scene();
    var camera = new THREE.PerspectiveCamera(40, size.w / size.h, 0.1, 200);
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

    // Offset de rotación inicial (Y) por modelo. Lógica pura en model3d-offsets.js
    // (testeada con TDD). San Pedro (home-proyectos) y el busto (home-datos): 180°;
    // el resto: 0° (se ven bien). No hay debug keys ni valores runtime.
    var rotOffsetY = 0;
    if (window.MRModelOffsets) {
      rotOffsetY = window.MRModelOffsets.getModelRotationOffset(src);
    } else if (/home-proyectos|home-datos/.test(src)) {
      rotOffsetY = Math.PI; // 180°
    }

    // Opacidad 50%
    wrapper.style.opacity = '0.5';

    var modelRadius = 1;

    function refit() {
      var s = stageSize();
      camera.aspect = s.w / s.h;
      camera.updateProjectionMatrix();
      renderer.setSize(s.w, s.h, false);

      var dist = camera.position.length();
      var vHalf = Math.tan(THREE.MathUtils.degToRad(camera.fov / 2));
      var fitH = (2 * dist * vHalf * 0.95) / modelRadius;
      var hFov = 2 * Math.atan(vHalf * camera.aspect);
      var fitW = (2 * dist * Math.tan(hFov / 2) * 0.95) / modelRadius;
      group.scale.setScalar(Math.min(fitH, fitW));
    }

    // Cargar el modelo SIEMPRE (es acá donde se dispara el GET del .glb).
    // Prevención de popping: el grupo queda oculto hasta que el modelo esté
    // totalmente listo (radio, refit y rotación inicial aplicados), así el
    // primer frame que se pinta ya tiene el tamaño y orientación finales.
    // El wrapper aparece con un fade-in CSS corto en lugar de un salto seco.
    group.visible = false;
    var loader = new GLTFLoader();
    var draco = new DRACOLoader();
    draco.setDecoderPath('https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/libs/draco/');
    draco.preload();
    loader.setDRACOLoader(draco);

    loader.load(src, function (gltf) {
      var model = gltf.scene;

      // Centrar el MODELO
      model.updateMatrixWorld(true);
      var box = new THREE.Box3().setFromObject(model);
      var center = new THREE.Vector3();
      box.getCenter(center);
      model.position.sub(center);

      group.add(model);
      group.updateMatrixWorld(true);

      box = new THREE.Box3().setFromObject(group);
      var msize = new THREE.Vector3();
      box.getSize(msize);
      modelRadius = Math.max(0.001, msize.length() / 2);

      // Aplicar todo ANTES de mostrar: tamaño + rotación inicial ya resueltos
      refit();
      group.rotation.y = rotOffsetY;
      group.position.y = Math.sin(0); // compensación base con rotX=0
      group.visible = true;

      // Ocultar el skeleton en el success (garantía extra).
      hideSkeleton(stage);
    }, undefined, function (err) {
      console.warn('model3d:', src, err);
      // Error de carga: ocultar skeleton + wrapper, NUNCA ocultar el stage
      // (ocultarlo dispara el CSS :has() y rompe el layout).
      hideSkeleton(stage);
      if (wrapper) wrapper.style.display = 'none';
    });

    // ---------- Progreso de scroll ----------
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

    // ---------- Tilt hacia el puntero ----------
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

      if (IS_MOBILE) {
        frames++;
        acc += 16.67;
        if (acc >= 2000) {
          var fps = frames * 1000 / acc;
          if (!degraded && fps < 24) {
            degraded = true;
            renderer.setPixelRatio(1);
            var s = stageSize();
            renderer.setSize(s.w, s.h, false);
          }
          frames = 0;
          acc = 0;
        }
      }

      currentP += (progress - currentP) * 0.06;
      tiltY += (tiltTargetY - tiltY) * 0.08;
      tiltX += (tiltTargetX - tiltX) * 0.08;

      var rotY = -currentP * Math.PI * 2 * 0.3 + tiltY + rotOffsetY;
      // Giro vertical COMPLETO: -45°→+45° (sin factor de reducción) + tilt fino.
      var rotX = clamp(-(currentP - 0.5) * (Math.PI / 2) + tiltX, -Math.PI / 4, Math.PI / 4);

      group.rotation.y = rotY;
      group.rotation.x = rotX;
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
