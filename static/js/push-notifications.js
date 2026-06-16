// MR Agentes — Push Notifications v2.1
(function () {
  'use strict';

  const _VK = (function(){
    var m = document.querySelector('meta[name="vapid-key"]');
    if(m) return m.content;
    return atob('QkZmN3EwaWhnYXhaZGhwalN2RElSdGZDSUttZ25sZG9fTDBadndMWWhOX3lhOXlLRVlzMFd6SlJteWxxWVBMMDM4R0ctSWR4Yk1uS2dLMEFRSWMyaDhJ');
  })();

  function urlBase64ToUint8Array(b64) {
    const pad = '='.repeat((4 - (b64.length % 4)) % 4);
    const raw = window.atob((b64 + pad).replace(/-/g, '+').replace(/_/g, '/'));
    return Uint8Array.from(raw, (c) => c.charCodeAt(0));
  }

  async function registerSW() {
    if (!('serviceWorker' in navigator)) return null;
    try {
      return await navigator.serviceWorker.register('/sw.js', { scope: '/' });
    } catch (e) {
      console.error('[Push] SW error:', e);
      return null;
    }
  }

  async function subscribeUser(registration) {
    if (!('PushManager' in window)) return null;
    // Si el permiso ya fue denegado, ni intentamos
    if (Notification.permission === 'denied') return 'denied';

    try {
      let sub = await registration.pushManager.getSubscription();
      if (sub) return sub;

      sub = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(_VK),
      });

      // Fire and forget — no crítico si el servidor push no responde
      fetch('/api/subscribe/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(sub),
      }).catch(() => {});

      return sub;
    } catch (e) {
      console.error('[Push] Subscribe error:', e);
      // Si el error es porque el permiso está denegado
      if (Notification.permission === 'denied') return 'denied';
      return null;
    }
  }

  async function unsubscribeUser(registration) {
    try {
      const sub = await registration.pushManager.getSubscription();
      if (sub) {
        await sub.unsubscribe();
        fetch('/api/unsubscribe/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ endpoint: sub.endpoint }),
        }).catch(() => {});
      }
    } catch (e) {
      console.error('[Push] Unsubscribe error:', e);
    }
  }

  function getPermissionStatus() {
    // 'default' | 'granted' | 'denied'
    if (!('Notification' in window)) return 'unsupported';
    return Notification.permission;
  }

  function getBrowserLabel() {
    const ua = navigator.userAgent;
    if (ua.includes('Firefox')) return 'Firefox';
    if (ua.includes('Chrome')) return 'Chrome';
    if (ua.includes('Safari') && !ua.includes('Chrome')) return 'Safari';
    if (ua.includes('Edg')) return 'Edge';
    return 'tu navegador';
  }

  function getPermissionInstructions() {
    const browser = getBrowserLabel();
    const isMobile = /Mobi|Android/i.test(navigator.userAgent);

    if (isMobile) {
      if (browser === 'Chrome' || browser === 'Firefox') {
        return (
          'Presioná el ícono 🔒 o ℹ️ en la barra de direcciones, ' +
          'buscá "Notificaciones" y cambiá a "Permitir". Luego recargá la página.'
        );
      }
      return 'Andá a Configuración > Notificaciones > MR Agentes y activá los permisos.';
    }

    if (browser === 'Firefox') {
      return (
        'Hacé clic en el ícono 🔒 en la barra de direcciones, ' +
        'click en "Permisos" > "Notificaciones" y seleccioná "Permitir".'
      );
    }
    if (browser === 'Chrome') {
      return (
        'Hacé clic en el ícono 🔒 en la barra de direcciones, ' +
        'buscá "Notificaciones" y cambiá a "Permitir". Luego recargá la página.'
      );
    }
    if (browser === 'Edge') {
      return (
        'Andá a Configuración > Cookies y permisos del sitio > Notificaciones, ' +
        'buscá mragentes.com.ar y activalo.'
      );
    }
    return 'Revisá la configuración de notificaciones de tu navegador para mragentes.com.ar y activalas.';
  }

  async function updateButton(registration) {
    const btn = document.getElementById('push-toggle-btn');
    if (!btn) return;

    const permission = getPermissionStatus();

    if (permission === 'denied') {
      btn.textContent = '🔕 Notificaciones bloqueadas';
      btn.classList.remove('active');
      btn.title = 'Permiso denegado — activalo desde la configuración del navegador';
      return;
    }

    if (permission === 'unsupported') {
      btn.style.display = 'none';
      return;
    }

    const sub = await registration.pushManager.getSubscription();
    if (sub) {
      btn.textContent = '🔔 Desactivar notificaciones';
      btn.classList.add('active');
    } else {
      btn.textContent = '🔕 Activar notificaciones';
      btn.classList.remove('active');
    }
  }

  // === TOAST ===
  function showToast(registration) {
    if (localStorage.getItem('TOAST_DISMISSED') === 'true') return;

    const permission = getPermissionStatus();
    const isDenied = permission === 'denied';

    const toast = document.createElement('div');
    toast.className = 'push-toast';

    if (isDenied) {
      toast.innerHTML = `
        <div class="push-toast-content">
          <p>Tu competencia ya está usando IA.<br>Permití las notificaciones para recuperar terreno.</p>
          <div class="push-toast-actions" style="flex-direction:column;align-items:stretch;gap:0.5rem;">
            <button class="push-toast-btn">Ver cómo activarlas</button>
            <button class="push-toast-close" style="align-self:center;">✕ Cerrar</button>
          </div>
        </div>
      `;
    } else {
      toast.innerHTML = `
        <div class="push-toast-content">
          <p>Tu competencia ya está usando IA.<br>Permití las notificaciones para recuperar terreno.</p>
          <div class="push-toast-actions">
            <button class="push-toast-btn">Activar notificaciones</button>
            <button class="push-toast-close">✕</button>
          </div>
        </div>
      `;
    }

    document.body.appendChild(toast);
    requestAnimationFrame(() => toast.classList.add('visible'));

    const btn = toast.querySelector('.push-toast-btn');
    const close = toast.querySelector('.push-toast-close');

    close.addEventListener('click', () => {
      localStorage.setItem('TOAST_DISMISSED', 'true');
      toast.classList.remove('visible');
      setTimeout(() => toast.remove(), 400);
    });

    btn.addEventListener('click', async () => {
      if (isDenied) {
        // Mostrar instrucciones en el mismo toast
        toast.innerHTML = `
          <div class="push-toast-content">
            <p style="font-size:0.85rem;">
              <strong>Notificaciones bloqueadas en ${getBrowserLabel()}.</strong>
            </p>
            <p style="font-size:0.8rem;color:var(--gray-600);">
              ${getPermissionInstructions()}
            </p>
            <div class="push-toast-actions" style="flex-direction:column;align-items:stretch;gap:0.5rem;margin-top:0.75rem;">
              <button class="push-toast-btn" onclick="location.reload()">Ya lo activé — recargar</button>
              <button class="push-toast-close" style="align-self:center;">✕ Entendido</button>
            </div>
          </div>
        `;
        toast.querySelector('.push-toast-close').addEventListener('click', () => {
          localStorage.setItem('TOAST_DISMISSED', 'true');
          toast.classList.remove('visible');
          setTimeout(() => toast.remove(), 400);
        });
        return;
      }

      const result = await subscribeUser(registration);
      if (result === 'denied') {
        // Recargar toast con instrucciones
        location.reload(); // simple: recarga y muestra el toast de denied
        return;
      }
      if (result) {
        toast.classList.remove('visible');
        setTimeout(() => toast.remove(), 400);
        localStorage.setItem('TOAST_DISMISSED', 'true');
        updateButton(registration);
      } else {
        // Error genérico
        btn.textContent = 'Error — intentá de nuevo';
        btn.disabled = true;
        setTimeout(() => {
          btn.textContent = 'Activar notificaciones';
          btn.disabled = false;
        }, 2000);
      }
    });
  }

  // === INIT ===
  document.addEventListener('DOMContentLoaded', async () => {
    const isUnsupported = !('serviceWorker' in navigator) || !('PushManager' in window) || !('Notification' in window);
    if (isUnsupported) {
      const btn = document.getElementById('push-toggle-btn');
      if (btn) btn.style.display = 'none';
      return;
    }

    const registration = await registerSW();
    if (!registration) {
      const btn = document.getElementById('push-toggle-btn');
      if (btn) btn.style.display = 'none';
      return;
    }

    updateButton(registration);

    const btn = document.getElementById('push-toggle-btn');
    if (btn) {
      btn.addEventListener('click', async () => {
        // Si está bloqueado, no hacer nada (el toast se encarga)
        if (Notification.permission === 'denied') {
          localStorage.removeItem('TOAST_DISMISSED');
          location.reload();
          return;
        }

        const sub = await registration.pushManager.getSubscription();
        if (sub) {
          await unsubscribeUser(registration);
          localStorage.removeItem('TOAST_DISMISSED');
          updateButton(registration);
          // Mostrar el toast de vuelta
          showToast(registration);
        } else {
          const result = await subscribeUser(registration);
          if (result && result !== 'denied') {
            localStorage.setItem('TOAST_DISMISSED', 'true');
          }
          if (result === 'denied') location.reload();
          updateButton(registration);
        }
      });
    }

    // Mostrar toast si no está suscripto
    const sub = await registration.pushManager.getSubscription();
    if (!sub) {
      showToast(registration);
    }
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
