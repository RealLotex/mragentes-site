// MR Agentes — Push Notifications v1.0
(function () {
  'use strict';

  const VAPID_PUBLIC_KEY = 'BFf7q0ihgaxZdhpjSvDIRtfCIKmgnldo_L0ZvwLYhN_ya9yKEYs0WzJRmylqYPL038GG-IdxbMnKgK0AQIc2h8I';

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
      // Verificar si ya está suscripto
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

      // Enviar suscripción a nuestro endpoint
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
        // Notificar al servidor
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

  async function updateSubscriptionStatus(registration) {
    const statusEl = document.getElementById('push-status');
    const btn = document.getElementById('push-toggle-btn');
    if (!btn || !statusEl) return;

    const subscription = await registration.pushManager.getSubscription();
    if (subscription) {
      btn.textContent = '🔔 Desactivar notificaciones';
      btn.classList.add('active');
      statusEl.textContent = 'Notificaciones activadas';
      statusEl.className = 'push-status active';
    } else {
      btn.textContent = '🔕 Activar notificaciones';
      btn.classList.remove('active');
      statusEl.textContent = 'Notificaciones desactivadas';
      statusEl.className = 'push-status';
    }
  }

  // Inicialización
  document.addEventListener('DOMContentLoaded', async () => {
    const btn = document.getElementById('push-toggle-btn');
    if (!btn) return; // No hay botón en esta página

    const registration = await registerSW();
    if (!registration) {
      btn.style.display = 'none';
      return;
    }

    await updateSubscriptionStatus(registration);

    btn.addEventListener('click', async () => {
      const subscription = await registration.pushManager.getSubscription();
      if (subscription) {
        await unsubscribeUser(registration);
      } else {
        await subscribeUser(registration);
      }
      await updateSubscriptionStatus(registration);
    });
  });

  // Exportar funciones para uso desde la consola
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
