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

function formatTime(seconds) {
  return [Math.floor(seconds / 60), seconds % 60].map((value) => String(value).padStart(2, "0")).join(":");
}

export function initReadAloud(note, browser = window) {
  const synth = browser.speechSynthesis;
  const Utterance = browser.SpeechSynthesisUtterance;
  if (!synth || !Utterance) return;
  const button = note.querySelector("[data-note-audio]");
  const player = note.querySelector("[data-note-player]");
  const toggle = player.querySelector("[data-audio-toggle]");
  const play = toggle.querySelector("[data-audio-play]");
  const pause = toggle.querySelector("[data-audio-pause]");
  const progress = player.querySelector("[data-audio-progress]");
  const elapsed = player.querySelector("[data-audio-current]");
  const error = player.querySelector("[data-audio-error]");
  const total = Number(progress.max);
  const duration = button.querySelector("[data-audio-duration]").textContent;
  let parts;
  let secondsPerWord;
  let voice;
  let position = 0;
  let seeking = false;
  let current = null;
  let timer;
  synth.getVoices();

  function renderTime(value) {
    const time = formatTime(value);
    elapsed.textContent = time;
    progress.value = value;
    progress.setAttribute("aria-valuetext", `${time} de ${duration}`);
  }

  function renderPlayback() {
    play.hidden = Boolean(current);
    pause.hidden = !current;
    toggle.setAttribute("aria-label", current ? "Pausar lectura" : "Reproducir lectura");
  }

  function stop() {
    const wasPlaying = Boolean(current);
    current = null;
    browser.clearInterval(timer);
    if (wasPlaying) synth.cancel();
    renderPlayback();
  }

  function prepare() {
    const localVoices = synth.getVoices().filter((voice) => voice.localService);
    voice = localVoices.find((item) => /^es[-_]ar$/i.test(item.lang))
      || localVoices.find((item) => /^es(?:[-_]|$)/i.test(item.lang));
    if (!voice) {
      error.textContent = "Para escuchar, activá una voz en español en la configuración de tu dispositivo.";
      return false;
    }
    if (!parts) {
      const content = note.querySelector("[data-note-text]");
      const text = `${note.querySelector("h1").textContent}.\n${content.innerText || content.textContent}`;
      let wordCount = 0;
      parts = speechParts(text).map((part) => {
        const words = Array.from(part.matchAll(/\S+/g), (word) => word.index);
        const start = wordCount;
        wordCount += words.length;
        return { text: part, words, start, end: wordCount };
      });
      secondsPerWord = total / wordCount;
    }
    error.textContent = "";
    return true;
  }

  function speakFrom(word) {
    const part = parts.find((item) => word < item.end);
    if (!part) {
      current = null;
      position = total;
      if (!seeking) renderTime(total);
      renderPlayback();
      return;
    }
    const offset = part.words[word - part.start];
    const utterance = new Utterance(part.text.slice(offset));
    utterance.voice = voice;
    utterance.lang = voice.lang.replace("_", "-");
    current = utterance;
    renderPlayback();

    let anchorPosition = position;
    let anchorTime;
    // Los eventos de palabra ajustan el reloj cuando el motor de voz los emite.
    utterance.onstart = () => {
      if (current !== utterance) return;
      anchorTime = browser.performance.now();
      timer = browser.setInterval(() => {
        const estimate = anchorPosition + (browser.performance.now() - anchorTime) / 1000;
        position = Math.max(position, Math.min(total, part.end * secondsPerWord, estimate));
        if (!seeking) renderTime(Math.floor(position));
      }, 200);
    };
    utterance.onboundary = (event) => {
      if (current !== utterance || event.name !== "word") return;
      const nextWord = part.words.findIndex((index) => index > offset + event.charIndex);
      anchorPosition = ((nextWord === -1 ? part.end : part.start + nextWord) - 1) * secondsPerWord;
      anchorTime = browser.performance.now();
    };
    utterance.onend = () => {
      if (current !== utterance) return;
      browser.clearInterval(timer);
      position = Math.min(total, part.end * secondsPerWord);
      if (!seeking) renderTime(Math.floor(position));
      speakFrom(part.end);
    };
    utterance.onerror = () => {
      if (current !== utterance) return;
      stop();
      error.textContent = "La lectura se interrumpió. Podés reanudarla desde el reproductor.";
    };
    synth.speak(utterance);
  }

  function start() {
    if (!prepare()) return;
    if (position >= total) position = 0;
    renderTime(Math.floor(position));
    speakFrom(Math.floor(position / secondsPerWord + 1e-8));
  }

  function seek(value) {
    const resume = Boolean(current);
    if (resume) stop();
    position = Math.max(0, Math.min(total, Math.floor(value)));
    seeking = false;
    renderTime(position);
    if (resume && position < total) start();
  }

  button.hidden = false;
  button.addEventListener("click", () => {
    const opening = player.hidden;
    player.hidden = !opening;
    button.setAttribute("aria-expanded", String(opening));
    button.setAttribute("aria-label", opening ? "Cerrar el reproductor" : `Escuchar la nota, duración estimada ${duration}`);
    button.title = opening ? "Cerrar el reproductor" : "Escuchar la nota";
    if (opening) {
      start();
      toggle.focus();
    } else {
      stop();
    }
  });
  toggle.addEventListener("click", () => {
    if (current) stop();
    else start();
  });
  player.querySelectorAll("[data-audio-skip]").forEach((skip) => {
    skip.addEventListener("click", () => seek(position + Number(skip.dataset.audioSkip)));
  });
  progress.addEventListener("input", () => {
    seeking = true;
    renderTime(Number(progress.value));
  });
  progress.addEventListener("change", () => seek(Number(progress.value)));
  progress.addEventListener("blur", () => {
    if (seeking) seek(Number(progress.value));
  });
  browser.addEventListener("pagehide", stop);
}

const note = typeof document !== "undefined" && document.querySelector("[data-note-reading]");
if (note) {
  const url = new URL(note.querySelector("[data-share-url]").dataset.shareUrl);
  const slug = url.pathname.split("/").filter(Boolean).pop();
  const status = note.querySelector("[data-note-status]");
  const tell = (message) => { status.textContent = message; };
  initReaction(note, slug, tell);
  initBookmark(note, slug, tell);
  initReadAloud(note);
}
