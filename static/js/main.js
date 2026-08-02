/* =========================================
   MR AGENTES — main.js v4 (Renacimiento)
   Reveals suaves con clip-path
   Progressive enhancement: sin JS el contenido siempre es visible.
   ========================================= */

document.addEventListener('DOMContentLoaded', function () {

  /* ---------- Reveal con clip-path ---------- */
  var revealEls = document.querySelectorAll('.section, .card, .feature-item, .stat-item, .nota-card, .nota-card-img, .contact-channel, .cta-section, .diagram-wrap, .marquee');
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
