/* =========================================
   MR AGENTES — Scroll Animations
   Estilo Inconcert: fade-in + translateY
   ========================================= */

document.addEventListener('DOMContentLoaded', function() {
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('scroll-visible');
        observer.unobserve(entry.target);
      }
    });
  }, {
    threshold: 0.15,
    rootMargin: '0px 0px -50px 0px'
  });

  // Observar secciones, cards, features, stat-items y más
  const targets = document.querySelectorAll(
    '.section, .card, .feature-item, .stat-item, .nota-card, .contact-channel, .cta-section'
  );
  targets.forEach(el => {
    el.classList.add('scroll-hidden');
    observer.observe(el);
  });
});
