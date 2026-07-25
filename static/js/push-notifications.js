// MR Agentes — Push Notifications v2.2
// Mejoras: diagnóstico completo, soporte iOS, status visible, debug mode (?push-debug)
(function () {
  'use strict';

  const DEBUG = window.location.search.includes('push-debug');
  function log(...args) { console.log('[Push]', ...args); }
  function warn(...args) { console.warn('[Push]', ...args); }
  function err(...args) { console.error('[Push]', ...args); }

  // URL del Worker de Cloudflare
  const PUSH_API_URL = (function(){
    var m = document.querySelector('meta[name="push-api-url"]');
    return m ? m.content : '';
  })();

  // VAPID public key
  const _VK = (function(){
    var m = document.querySelector('meta[name="vapid-key"]');
    if(m) return m.content;
    // Legacy fallback (old key — shouldn't be used)
    return atob('QkNhbm1xNjh3TXN2VnVEVy1EVlFPMzQ5VWoxSHZQN0Q2cWRIYzlvQzhMODlDUThKRWRkV2Y2T24xcFdqa01ZdUhxTUtfamNrZHA2VTg4QzZoOXM0VmJr');
  })();

  function urlBase64ToUint8Array(b64) {
    const pad = '='.repeat((4 - (b64.length % 4)) % 4);
    const raw = window.atob((b64 + pad).replace(/-/g, '+').replace(/_/g, '/'));
    return Uint8Array.from(raw, (c) => c.charCodeAt(0));
  }

  // ─── Device detection ────────────────────────────────────────────────────
  function getDeviceInfo() {
    const ua = navigator.userAgent;
    const isMobile = /Mobi|Android/i.test(ua);
    const isIOS = /iPhone|iPad|iPod/i.test(ua);
    const isSafari = /Safari/i.test(ua) && !/Chrome|Chromium|Edg/i.test(ua);
    const isFirefox = /Firefox/i.test(ua);
    const isChrome = /Chrome|Chromium/i.test(ua) && !/Edg/i.test(ua);
    const isPWA = window.matchMedia('(display-mode: standalone)').matches;

    let browser = 'desconocido';
    if (isFirefox) browser = 'Firefox';
    else if (isSafari) browser = 'Safari';
    else if (isChrome) browser = 'Chrome';
    else if (/Edg/i.test(ua)) browser = 'Edge';

    return { isMobile, isIOS, isSafari, isFirefox, isChrome, isPWA, browser };
  }

  async function registerSW() {
    if (!('serviceWorker' in navigator)) {
      warn('Service Worker no soportado en este navegador');
      return null;
    }
    try {
      const reg = await navigator.serviceWorker.register('/sw.js', { scope: '/' });
      log('SW registrado:', reg.scope);
      return reg;
    } catch (e) {
      err('Error al registrar SW:', e.message);
      return null;
    }
  }

  async function subscribeUser(registration) {
    if (!('PushManager' in window)) {
      warn('PushManager no soportado');
      return null;
    }

    const perm = Notification.permission;
    log('Permiso actual:', perm);

    if (perm === 'denied') {
      warn('Permiso denegado — imposible suscribir');
      return 'denied';
    }

    try {
      let sub = await registration.pushManager.getSubscription();
      if (sub) {
        log('Ya suscripto. Endpoint:', sub.endpoint.slice(0, 60) + '…');
        return sub;
      }

      log('Solicitando suscripción push con VAPID key…');
      sub = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(_VK),
      });

      log('✅ Suscripción creada. Endpoint:', sub.endpoint.slice(0, 60) + '…');

      // Enviar suscripción al worker
      if (PUSH_API_URL) {
        try {
          const res = await fetch(PUSH_API_URL + '/api/subscribe/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(sub),
          });
          const data = await res.json();
          log('Worker respondió a subscribe:', data);
        } catch (fetchErr) {
          warn('No se pudo guardar suscripción en el worker:', fetchErr.message);
          // La suscripción local es válida aunque el worker falle
        }
      } else {
        warn('PUSH_API_URL no configurada — suscripción local solamente');
      }

      return sub;
    } catch (e) {
      err('Error al suscribir:', e.message, e.name);
      if (Notification.permission === 'denied') return 'denied';
      return null;
    }
  }

  async function unsubscribeUser(registration) {
    try {
      const sub = await registration.pushManager.getSubscription();
      if (sub) {
        log('Cancelando suscripción:', sub.endpoint.slice(0, 60) + '…');
        await sub.unsubscribe();
        log('✅ Suscripción cancelada localmente');

        if (PUSH_API_URL) {
          fetch(PUSH_API_URL + '/api/unsubscribe/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ endpoint: sub.endpoint }),
          }).then(r => r.json()).then(d => log('Worker unsubscribe:', d)).catch(() => {});
        }
      }
    } catch (e) {
      err('Error al desuscribir:', e);
    }
  }

  function getPermissionStatus() {
    if (!('Notification' in window)) return 'unsupported';
    return Notification.permission;
  }

  // ─── Instrucciones contextuales ─────────────────────────────────────────
  function getPermissionInstructions() {
    const { browser, isMobile, isIOS, isSafari, isPWA } = getDeviceInfo();

    // iOS Safari solo soporta push en PWA agregada a Home Screen
    if (isIOS && isSafari && !isPWA) {
      return (
        '⚠️ En iPhone/iPad, las notificaciones push solo funcionan si agregás ' +
        'el sitio a la pantalla de inicio (botón Compartir → "Agregar a inicio"). ' +
        'Después de agregarlo, abrilo desde el ícono y aceptá las notificaciones.'
      );
    }

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
        'clic en "Permisos" > "Notificaciones" y seleccioná "Permitir".'
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

  // ─── Status Badge (modo debug) ──────────────────────────────────────────
  function showDebugPanel(registration, sub) {
    if (!DEBUG) return;

    const { browser, isMobile, isIOS, isSafari, isPWA } = getDeviceInfo();
    const panel = document.createElement('div');
    panel.id = 'push-debug-panel';
    panel.style.cssText = 'position:fixed;bottom:16px;right:16px;background:#1a1a1a;color:#fff;padding:12px 16px;border-radius:8px;font-size:12px;font-family:monospace;z-index:99999;max-width:320px;box-shadow:0 4px 12px rgba(0,0,0,.3);';
    panel.innerHTML = [
      '<strong>🔔 Push Debug</strong>',
      'Browser: ' + browser + (isMobile ? ' 📱' : ' 🖥️'),
      'iOS: ' + isIOS + ' | Safari: ' + isSafari + ' | PWA: ' + isPWA,
      'Permission: ' + Notification.permission,
      'SW: ' + (registration ? '✅ ' + registration.scope : '❌'),
      'Subscribed: ' + (sub ? '✅ ' + sub.endpoint.slice(0, 50) + '…' : '❌'),
      'Worker URL: ' + (PUSH_API_URL || '❌ no configurada'),
      '<button id="push-debug-test" style="margin-top:8px;padding:4px 8px;background:#2596be;color:#fff;border:none;border-radius:4px;cursor:pointer;">🧪 Enviar test push</button>',
      '<button id="push-debug-close" style="margin-left:4px;padding:4px 8px;background:#555;color:#fff;border:none;border-radius:4px;cursor:pointer;">✕</button>',
    ].join('<br>');
    document.body.appendChild(panel);

    document.getElementById('push-debug-close').addEventListener('click', () => panel.remove());
    document.getElementById('push-debug-test').addEventListener('click', async () => {
      if (!sub) {
        alert('No estás suscripto. Suscribite primero.');
        return;
      }
      try {
        const res = await fetch(PUSH_API_URL + '/api/send/one/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            subscription: sub,
            title: '🧪 Test de notificación',
            body: 'Si ves esto, las push notifications funcionan correctamente.',
            url: 'https://mragentes.com.ar/',
          }),
        });
        const data = await res.json();
        alert('Test enviado: ' + JSON.stringify(data, null, 2));
      } catch (e) {
        alert('Error: ' + e.message);
      }
    });
  }

  // ─── Button ─────────────────────────────────────────────────────────────
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
      log('Botón: activado (suscripto)');
    } else {
      btn.textContent = '🔕 Activar notificaciones';
      btn.classList.remove('active');
      log('Botón: desactivado (no suscripto)');
    }
  }

  // ─── Toast ──────────────────────────────────────────────────────────────
  function showToast(registration) {
    if (localStorage.getItem('TOAST_DISMISSED') === 'true') return;

    const permission = getPermissionStatus();
    const isDenied = permission === 'denied';
    const { isIOS, isSafari, isPWA } = getDeviceInfo();

    const toast = document.createElement('div');
    toast.className = 'push-toast';

    // Mensaje adaptado a iOS
    let msg = 'Tu competencia ya usa IA. <br> Permití las notificaciones y no te quedes atrás.';
    if (isIOS && isSafari && !isPWA) {
      msg = '📱 En iPhone agregá esta página a tu inicio para recibir notificaciones.<br>Tu competencia ya usa IA, no te quedes atrás.';
    }

    if (isDenied) {
      toast.innerHTML = `
        <div class="push-toast-content">
          <p>${msg}</p>
          <div class="push-toast-actions" style="flex-direction:column;align-items:stretch;gap:0.5rem;">
            <button class="push-toast-btn">Ver cómo activarlas</button>
            <button class="push-toast-close" style="align-self:center;">✕ Cerrar</button>
          </div>
        </div>
      `;
    } else {
      toast.innerHTML = `
        <div class="push-toast-content">
          <p>${msg}</p>
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
        toast.innerHTML = `
          <div class="push-toast-content">
            <p style="font-size:0.85rem;">
              <strong>Notificaciones bloqueadas en ${getDeviceInfo().browser}.</strong>
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
        location.reload();
        return;
      }
      if (result) {
        toast.classList.remove('visible');
        setTimeout(() => toast.remove(), 400);
        localStorage.setItem('TOAST_DISMISSED', 'true');
        updateButton(registration);
        log('✅ Suscripción exitosa desde toast');
      } else {
        btn.textContent = 'Error — intentá de nuevo';
        btn.disabled = true;
        setTimeout(() => {
          btn.textContent = 'Activar notificaciones';
          btn.disabled = false;
        }, 2000);
      }
    });
  }

  // ─── INIT ───────────────────────────────────────────────────────────────
  document.addEventListener('DOMContentLoaded', async () => {
    log('Inicializando push notifications v2.2…');

    const isUnsupported = !('serviceWorker' in navigator) || !('PushManager' in window) || !('Notification' in window);
    if (isUnsupported) {
      warn('API de Push no disponible en este navegador');
      const btn = document.getElementById('push-toggle-btn');
      if (btn) btn.style.display = 'none';
      return;
    }

    const registration = await registerSW();
    if (!registration) {
      warn('No se pudo registrar el Service Worker');
      const btn = document.getElementById('push-toggle-btn');
      if (btn) btn.style.display = 'none';
      return;
    }

    // Esperar a que el SW esté activo
    await navigator.serviceWorker.ready;
    log('SW listo');

    const sub = await registration.pushManager.getSubscription();
    log('Estado inicial:', sub ? 'Suscripto' : 'No suscripto');

    updateButton(registration);

    // Debug panel si ?push-debug
    showDebugPanel(registration, sub);

    const btn = document.getElementById('push-toggle-btn');
    if (btn) {
      btn.addEventListener('click', async () => {
        if (Notification.permission === 'denied') {
          localStorage.removeItem('TOAST_DISMISSED');
          location.reload();
          return;
        }

        const currentSub = await registration.pushManager.getSubscription();
        if (currentSub) {
          await unsubscribeUser(registration);
          localStorage.removeItem('TOAST_DISMISSED');
          updateButton(registration);
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
    if (!sub) {
      log('No suscripto — mostrando toast');
      showToast(registration);
    }

    // Escuchar mensajes del SW
    navigator.serviceWorker.addEventListener('message', (event) => {
      log('Mensaje del SW:', event.data);
      if (event.data && event.data.type === 'NEW_NOTA') {
        const nota = event.data.payload;
        log('Nueva nota detectada por SW:', nota.title);
        if (sub) {
          registration.showNotification(nota.title || 'Nueva nota de MR Agentes', {
            body: 'Acabamos de publicar una nueva nota.',
            icon: '/images/favicon.png',
            badge: '/images/favicon.png',
            data: { url: nota.url || '/' },
            actions: [
              { action: 'open', title: 'Leer nota' },
              { action: 'close', title: 'Cerrar' },
            ],
            tag: 'new-nota',
            renotify: true,
          });
        }
      }
    });

    log('✅ Push notifications inicializado');
  });

  // ─── API pública ────────────────────────────────────────────────────────
  window.__pushNotifications = {
    subscribe: async () => {
      const reg = await navigator.serviceWorker.ready;
      return subscribeUser(reg);
    },
    unsubscribe: async () => {
      const reg = await navigator.serviceWorker.ready;
      return unsubscribeUser(reg);
    },
    status: async () => {
      if (!('serviceWorker' in navigator)) return { supported: false };
      const reg = await navigator.serviceWorker.ready;
      const sub = await reg.pushManager.getSubscription();
      return {
        supported: true,
        permission: Notification.permission,
        subscribed: !!sub,
        endpoint: sub ? sub.endpoint : null,
        device: getDeviceInfo(),
      };
    },
  };
})();
