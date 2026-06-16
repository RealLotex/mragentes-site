// MR Agentes — Push Notifications v2.0
(function () {
  'use strict';

  const VAPID_PUBLIC_KEY = 'BFf7q0…2h8I';
  const TOAST_SEEN_KEY = 'mragentes_push_toast_dismissed';

  function urlBase64ToUint8Array(base64String) {
    const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
    const base64 = (base64String + padding)
      .replace(/-/g, '+')
      .replace(/_/g, '/');
    const rawData = window.atob(base64);
    const outputArray = new Uint8Array(rawData.length);
    for (let i = 0; i < rawData.length; ++i) {
      outputArray[i] = rawData.charCodeAt(i);
    }
    return outputArray;
  }

  async function registerSW() {
    if (!('serviceWorker' in navigator)) {
      console.log('[Push] Service Workers no soportados');
      return null;
    }
    try {
      const registration = await navigator.serviceWorker.register('/sw.js', {
        scope: '/',
      });
      console.log('[Push] SW registrado correctamente');
      return registration;
    } catch (e) {
      console.error('[Push] Error registrando SW:', e);
      return null;
    }
  }

  async function subscribeUser(registration) {
    if (!('PushManager' in window)) {
      console.log('[Push] Push API no soportada');
      return null;
    }

    try {
      let subscription = await registration.pushManager.getSubscription();
      if (subscription) {
        console.log('[Push] Ya suscripto');
        return subscription;
      }

      subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(VAPID_PUBLIC_KEY),
      });

      console.log('[Push] Suscripto exitosamente');

      await fetch('/api/subscribe/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(subscription),
      });

      return subscription;
    } catch (e) {
      console.error('[Push] Error al suscribir:', e);
      return null;
    }
  }

  async function unsubscribeUser(registration) {
    try {
      const subscription = await registration.pushManager.getSubscription();
      if (subscription) {
        await subscription.unsubscribe();
        await fetch('/api/unsubscribe/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ endpoint: subscription.endpoint }),
        });
        console.log('[Push] Desuscripto');
      }
    } catch (e) {
      console.error('[Push] Error al desuscribir:', e);
    }
  }

  async function updateButton(registration) {
    const btn = document.getElementById('push-toggle-btn');
    if (!btn) return;

    const subscription = await registration.pushManager.getSubscription();

    if (subscription) {
      btn.textContent = '🔔 Desactivar notificaciones';
      btn.classList.add('active');
    } else {
      btn.textContent = '🔕 Activar notificaciones';
      btn.classList.remove('active');
    }
  }

  // === TOAST ===
  function showToast(registration) {
    // No mostrar si ya lo vió y lo cerró, o si ya está suscripto
    if (localStorage.getItem(TOAST_SEEN_KEY) === 'true') return;

    const toast = document.createElement('div');
    toast.className = 'push-toast';
    toast.innerHTML = `
      <div class="push-toast-content">
        <p>Tu competencia ya está usando IA. Permití las notificaciones para recuperar terreno.</p>
        <div class="push-toast-actions">
          <button class="push-toast-btn">Activar notificaciones</button>
          <button class="push-toast-close">✕</button>
        </div>
      </div>
    `;

    document.body.appendChild(toast);

    // Trigger animación
    requestAnimationFrame(() => {
      toast.classList.add('visible');
    });

    const toastBtn = toast.querySelector('.push-toast-btn');
    const closeBtn = toast.querySelector('.push-toast-close');

    toastBtn.addEventListener('click', async () => {
      const sub = await subscribeUser(registration);
      if (sub) {
        toast.classList.remove('visible');
        setTimeout(() => toast.remove(), 400);
        localStorage.setItem(TOAST_SEEN_KEY, 'true');
        updateButton(registration);
        // También actualiza botón del footer si existe
      } else {
        // Si el usuario negó permiso en el navegador, mostrar estado
        toastBtn.textContent = 'Permiso denegado — revisá tu navegador';
        toastBtn.disabled = true;
      }
    });

    closeBtn.addEventListener('click', () => {
      localStorage.setItem(TOAST_SEEN_KEY, 'true');
      toast.classList.remove('visible');
      setTimeout(() => toast.remove(), 400);
    });
  }

  // === INIT ===
  document.addEventListener('DOMContentLoaded', async () => {
    const registration = await registerSW();
    if (!registration) return;

    // Actualizar botón del footer si existe
    updateButton(registration);

    // Toggle del botón footer
    const btn = document.getElementById('push-toggle-btn');
    if (btn) {
      btn.addEventListener('click', async () => {
        const sub = await registration.pushManager.getSubscription();
        if (sub) {
          await unsubscribeUser(registration);
          // Si desuscribe, resetea el toast para que pueda verlo si quiere
          localStorage.removeItem(TOAST_SEEN_KEY);
        } else {
          await subscribeUser(registration);
          if (await registration.pushManager.getSubscription()) {
            localStorage.setItem(TOAST_SEEN_KEY, 'true');
          }
        }
        updateButton(registration);
      });
    }

    // Mostrar toast si corresponde
    showToast(registration);
  });

  window.__pushNotifications = {
    subscribe: async () => {
      const reg = await navigator.serviceWorker.ready;
      return subscribeUser(reg);
    },
    unsubscribe: async () => {
      const reg = await navigator.serviceWorker.ready;
      return unsubscribeUser(reg);
    },
  };
})();
