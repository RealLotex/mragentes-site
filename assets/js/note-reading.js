function initReaction(note, slug, tell) {
  const button = note.querySelector("[data-note-reaction]");
  const score = button.querySelector("[data-note-score]");
  const base = Number(button.dataset.reactionBase);
  const storageKey = `mragentes:reaction:${slug}`;
  const endpoint = `/api/metrics/v1/reactions/${slug}`;
  let liked = false;
  let storedVisitor = "";
  let canReact = Boolean(window.crypto?.randomUUID);

  try { storedVisitor = localStorage.getItem(storageKey) || ""; }
  catch { canReact = false; }

  function getVisitor() {
    const visitor = localStorage.getItem(storageKey) || crypto.randomUUID();
    localStorage.setItem(storageKey, visitor);
    return visitor;
  }

  async function update(method, visitor) {
    const response = await fetch(endpoint, {
      method,
      headers: visitor ? { "X-Note-Visitor": visitor } : {},
      credentials: "omit",
      signal: window.AbortSignal?.timeout?.(6000),
    });
    if (!response.ok) throw new Error("No se pudo actualizar el puntaje");
    const result = await response.json();
    if (!Number.isSafeInteger(result.likes) || result.likes < 0) throw new Error("Puntaje inválido");
    liked = result.liked === true;
    const action = liked ? "Quitar Me gusta" : "Dar Me gusta";
    score.textContent = base + result.likes;
    button.setAttribute("aria-pressed", String(liked));
    button.setAttribute("aria-label", `${action}. Puntaje de la nota ${score.textContent}.`);
    button.title = action + " · Puntaje de la nota";
  }

  button.addEventListener("click", async () => {
    if (button.disabled) return;
    button.disabled = true;
    try {
      const visitor = navigator.locks?.request
        ? await navigator.locks.request(storageKey, getVisitor)
        : getVisitor();
      await update(liked ? "DELETE" : "PUT", visitor);
      tell(liked ? "Reacción guardada." : "Reacción quitada.");
    } catch {
      tell("No se pudo confirmar tu reacción. Volvé a intentarlo.");
    } finally {
      button.disabled = false;
    }
  });

  update("GET", storedVisitor).then(() => {
    button.disabled = !canReact;
  }).catch(() => {
    button.title = "El puntaje está temporalmente fuera de línea.";
    button.disabled = !canReact;
  });
}

function initBookmark(note, slug, tell) {
  const button = note.querySelector("[data-note-save]");
  const label = button.querySelector("[data-note-save-label]");
  const key = `mragentes:saved:${slug}`;
  let saved;
  try { saved = localStorage.getItem(key) === "1"; }
  catch { return; }

  function render() {
    button.setAttribute("aria-pressed", String(saved));
    label.textContent = saved ? "Guardada" : "Guardar";
  }
  render();
  button.hidden = false;
  button.addEventListener("click", () => {
    try {
      if (saved) localStorage.removeItem(key);
      else localStorage.setItem(key, "1");
      saved = !saved;
      render();
      tell(saved ? "Nota guardada en este navegador." : "La nota se quitó de guardadas.");
    } catch {
      tell("El navegador no pudo guardar la nota.");
    }
  });
}

export function speechParts(text) {
  const parts = [];
  for (const sentence of text.replace(/([.!?])\s+/g, "$1\n").split(/\n+/)) {
    // Las frases cortas evitan el corte que hacen algunos motores en un bloque largo.
    for (const part of sentence.trim().match(/.{1,240}(?:\s|$)|\S{1,240}/g) || []) {
      if (part.trim()) parts.push(part.trim());
    }
  }
  return parts;
}

export function initReadAloud(note, tell, browser = window) {
  const synth = browser.speechSynthesis;
  const Utterance = browser.SpeechSynthesisUtterance;
  if (!synth || !Utterance) return;
  const button = note.querySelector("[data-note-audio]");
  const duration = button.querySelector("[data-audio-duration]").textContent;
  let playback = null;
  synth.getVoices();

  function reset() {
    playback = null;
    button.setAttribute("aria-pressed", "false");
    button.setAttribute("aria-label", `Escuchar la nota, duración estimada ${duration}`);
    button.title = "Escuchar la nota";
  }

  button.hidden = false;
  button.addEventListener("click", () => {
    if (playback) {
      reset();
      synth.cancel();
      tell("Lectura detenida.");
      return;
    }
    const localVoices = synth.getVoices().filter((voice) => voice.localService);
    const voice = localVoices.find((item) => /^es[-_]ar$/i.test(item.lang))
      || localVoices.find((item) => /^es(?:[-_]|$)/i.test(item.lang));
    if (!voice) {
      tell("Para escuchar, activá una voz en español en la configuración de tu dispositivo.");
      return;
    }
    const content = note.querySelector("[data-note-text]");
    const parts = speechParts(`${note.querySelector("h1").textContent}.\n${content.innerText || content.textContent}`);
    if (parts.length === 0) return;

    const current = { index: 0, utterance: null };
    playback = current;
    button.setAttribute("aria-pressed", "true");
    button.setAttribute("aria-label", "Detener la lectura");
    button.title = "Detener la lectura";
    tell("Leyendo la nota.");

    function next() {
      if (playback !== current) return;
      if (current.index === parts.length) {
        reset();
        tell("Lectura finalizada.");
        return;
      }
      const utterance = new Utterance(parts[current.index]);
      current.index += 1;
      current.utterance = utterance;
      utterance.voice = voice;
      utterance.lang = voice.lang;
      utterance.onend = next;
      utterance.onerror = () => {
        if (playback !== current) return;
        reset();
        tell("La lectura se interrumpió. Podés volver a iniciarla.");
      };
      synth.speak(utterance);
    }
    next();
  });

  browser.addEventListener("pagehide", () => {
    if (!playback) return;
    reset();
    synth.cancel();
  });
}

const note = typeof document !== "undefined" && document.querySelector("[data-note-reading]");
if (note) {
  const url = new URL(note.querySelector("[data-share-url]").dataset.shareUrl);
  const slug = url.pathname.split("/").filter(Boolean).pop();
  const status = note.querySelector("[data-note-status]");
  const tell = (message) => { status.textContent = message; };
  initReaction(note, slug, tell);
  initBookmark(note, slug, tell);
  initReadAloud(note, tell);
}
