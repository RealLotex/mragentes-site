/* =========================================
   MR AGENTES — main.js v5
   Rotador de palabra en h1 · reveals con clip-path
   Progressive enhancement: sin JS el contenido siempre es visible.
   ========================================= */

document.addEventListener('DOMContentLoaded', function () {

  /* ---------- Rotador de palabra (h1) ---------- */
  var rotator = document.getElementById('rotate-word');
  if (rotator) {
    var words = ['solo', '24/7', 'en automático', 'sin supervisión', 'en segundo plano'];
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
          setTimeout(tick, 1700);
          return;
        }
        setTimeout(tick, 60);
      } else {
        charIdx--;
        rotator.textContent = word.slice(0, charIdx);
        if (charIdx === 0) {
          deleting = false;
          wordIdx = (wordIdx + 1) % words.length;
          setTimeout(tick, 350);
          return;
        }
        setTimeout(tick, 26);
      }
    }
    tick();
  }

  /* ---------- Reveal con clip-path ---------- */
  var revealEls = document.querySelectorAll('.section, .card, .feature-item, .fact-item, .stat-item, .nota-card, .nota-card-img, .contact-channel, .cta-section, .folio');
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

    // Fallback: revelar todo a los 2.5s si algo quedó sin observarse
    setTimeout(function () {
      revealEls.forEach(function (el) {
        el.classList.add('reveal-in');
      });
    }, 2500);
  }

  /* ---------- Menu mobile ---------- */
  var toggle = document.querySelector('.menu-toggle');
  var nav = document.querySelector('.nav-links');
  if (toggle && nav) {
    toggle.addEventListener('click', function () {
      nav.classList.toggle('open');
    });
  }
});
