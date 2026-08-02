/* =========================================
   MR AGENTES — main.js v3
   Rotador de palabras · tilt 3D · reveals con clip-path
   Progressive enhancement: sin JS el contenido siempre es visible.
   ========================================= */

document.addEventListener('DOMContentLoaded', function () {

  /* ---------- Rotador de palabras (hero) ---------- */
  var rotator = document.getElementById('rotate-word');
  if (rotator) {
    var words = ['solo', '24/7', 'en piloto automático', 'más rápido', 'sin errores'];
    var wordIdx = 0;
    var charIdx = 0;
    var deleting = false;

    function tick() {
      var word = words[wordIdx];
      if (!deleting) {
        charIdx++;
        rotator.textContent = word.slice(0, charIdx);
        if (charIdx === word.length) {
          deleting = true;
          setTimeout(tick, 1800);
          return;
        }
        setTimeout(tick, 65);
      } else {
        charIdx--;
        rotator.textContent = word.slice(0, charIdx);
        if (charIdx === 0) {
          deleting = false;
          wordIdx = (wordIdx + 1) % words.length;
          setTimeout(tick, 350);
          return;
        }
        setTimeout(tick, 28);
      }
    }
    tick();
  }

  /* ---------- Tilt 3D en cards (estilo spline) ---------- */
  var tiltables = document.querySelectorAll('.card, .terminal-wrap, .cta-section');
  tiltables.forEach(function (el) {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    el.addEventListener('mousemove', function (e) {
      var rect = el.getBoundingClientRect();
      var x = (e.clientX - rect.left) / rect.width - 0.5;
      var y = (e.clientY - rect.top) / rect.height - 0.5;
      el.style.transform = 'perspective(900px) rotateY(' + (x * 4) + 'deg) rotateX(' + (-y * 4) + 'deg) translateY(-3px)';
    });
    el.addEventListener('mouseleave', function () {
      el.style.transform = '';
    });
  });

  /* ---------- Reveal con clip-path ----------
     La clase .reveal solo se aplica DESDE JS (progressive enhancement).
     Sin JS el contenido queda visible; con JS se anima al entrar. */
  var revealEls = document.querySelectorAll('.section, .card, .feature-item, .stat-item, .nota-card, .nota-card-img, .contact-channel, .cta-section, .terminal-wrap, .marquee');
  if ('IntersectionObserver' in window) {
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add('reveal-in');
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -40px 0px' });

    revealEls.forEach(function (el) {
      el.classList.add('reveal');
      observer.observe(el);
    });

    // Fallback: si algo quedó sin observarse por layout shifts, revelar todo a los 2.5s
    setTimeout(function () {
      revealEls.forEach(function (el) {
        el.classList.add('reveal-in');
      });
    }, 2500);
  }
});
