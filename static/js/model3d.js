/* =========================================
   MR AGENTES — model3d.js v7
   Modelos 3D de fondo (no paneles)
   - Ocupan 2/3 del ancho, 3x más grandes, opacidad 50%
   - Rotación guiada por scroll + turntable infinito + tilt hacia el puntero
   - Máxima resolución (pixelRatio hasta 2, antialias)
   - En mobile: banda superior y degradación automática si FPS < 24
   - Skeleton loader mientras descarga; sin WebGL/404 se oculta el stage
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
    var h = stage.clientHeight || 480;

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
    // Máxima resolución
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setSize(w, h);
    wrapper.appendChild(renderer.domElement);

    var scene = new THREE.Scene();
    var camera = new THREE.PerspectiveCamera(40, w / h, 0.1, 200);
    camera.position.set(0, 0.5, 3.2);
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

      // Centrar en origen antes de escalar
      var box = new THREE.Box3().setFromObject(model);
      var center = new THREE.Vector3();
      box.getCenter(center);
      model.position.sub(center);

      // Escala frustum-based × 3 (fondo grande, se sale del encuadre a propósito)
      var size = new THREE.Vector3();
      box.getSize(size);
      var maxDim = Math.max(size.x, size.y, size.z) || 1;
      var dist = camera.position.distanceTo(new THREE.Vector3(0, 0, 0));
      var fovHeight = 2 * dist * Math.tan(THREE.MathUtils.degToRad(camera.fov / 2));
      var scale = (fovHeight * 2.3) / maxDim;
      model.scale.setScalar(scale);

      group.add(model);

      // Skeleton fuera
      if (skeleton) skeleton.style.display = 'none';
    }, undefined, function (err) {
      console.warn('model3d:', src, err);
      stage.style.display = 'none';
    });

    // Opacidad 50%
    wrapper.style.opacity = '0.5';

    // ---------- Rotación por scroll ----------
    var scrollAngle = 0;
    var scrollTarget = 0;
    function updateScroll() {
      var r = stage.getBoundingClientRect();
      var center = r.top + r.height / 2;
      var vp = window.innerHeight / 2;
      scrollTarget = (vp - center) * 0.004;
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
        tiltTargetY = nx * 0.5;
        tiltTargetX = -ny * 0.3;
      });
      section.addEventListener('mouseleave', function () {
        tiltTargetY = 0;
        tiltTargetX = 0;
      });
    }

    var turntable = REDUCED_MOTION ? 0 : 0.002;

    // ---------- Pausa fuera de viewport ----------
    var visible = true;
    var ro = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        visible = entry.isIntersecting;
      });
    }, { threshold: 0.02 });
    ro.observe(stage);

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

      // Scroll (easing) + turntable + puntero
      scrollAngle += (scrollTarget - scrollAngle) * 0.06;
      turntable += 0.002;
      tiltY += (tiltTargetY - tiltY) * 0.08;
      tiltX += (tiltTargetX - tiltX) * 0.08;

      group.rotation.y = scrollAngle + turntable + tiltY;
      group.rotation.x = tiltX * 0.5;

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
