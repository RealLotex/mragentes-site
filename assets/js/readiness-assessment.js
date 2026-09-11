/* Diagnóstico de punto de partida: una orientación local para elegir un primer
   piloto. No persiste ni transmite respuestas y nunca habilita acciones. */

const choices = {
  frequency: { daily: 3, weekly: 2, occasional: 0 },
  clarity: { clear: 3, partial: 1, unclear: 0 },
  impact: { low: 2, medium: 1, high: -1 },
  exceptions: { few: 1, some: 0, many: 0 },
  owner: { yes: 1, no: 0 },
};

function scoreFor(values, name) {
  return choices[name]?.[values[name]] ?? 0;
}

export function assessReadiness(values = {}) {
  const score = Math.max(
    0,
    Object.keys(choices).reduce((total, name) => total + scoreFor(values, name), 0),
  );
  const sensitive = values.impact === "high";
  const undefinedProcess = values.clarity === "unclear" || values.owner === "no" || values.exceptions === "many";
  const controls = ["Definí una revisión humana para las excepciones."];

  if (values.clarity !== "clear") controls.push("Escribí los pasos, datos de entrada y resultado esperado antes de conectar herramientas.");
  if (values.owner !== "yes") controls.push("Nombrá a una persona responsable de validar el resultado.");
  if (values.frequency === "occasional") controls.push("Medí durante dos semanas si la tarea se repite lo suficiente como para justificar un piloto.");
  if (values.exceptions === "many") controls.push("Elegí una variante simple del proceso; las excepciones quedan fuera de la primera prueba.");
  if (sensitive) controls.push("Agregá aprobación humana antes de cualquier acción sobre dinero, personas o compromisos externos.");

  if (undefinedProcess) {
    return {
      score: 0,
      level: "Ordenar el proceso primero",
      nextStep: "Elegí una tarea repetible y escribí dónde empieza y dónde termina. Después medí tiempo, errores y excepciones durante una semana.",
      controls: ["Elegí una tarea repetible y escribí dónde empieza y dónde termina.", ...controls],
    };
  }

  if (sensitive) {
    return {
      score,
      level: "Preparar antes de automatizar",
      nextStep: "No automatices la decisión sensible. Usá un piloto que prepare información y deje la aprobación final a una persona.",
      controls,
    };
  }

  if (score >= 8) {
    return {
      score,
      level: "Listo para un piloto",
      nextStep: "Elegí un lote pequeño para un piloto, compará el resultado con el método actual y anotá las excepciones antes de ampliar el alcance.",
      controls,
    };
  }

  return {
    score,
    level: "Preparar antes de automatizar",
    nextStep: "Aclarà la entrada, la salida y la excepción más frecuente. Con eso ya podés definir un piloto acotado.",
    controls,
  };
}

export function initReadinessAssessment(root = document) {
  const form = root.querySelector("[data-readiness-assessment]");
  if (!form || form.dataset.initialized === "true") return;
  const result = form.closest(".readiness-assessment")?.querySelector("[data-readiness-result]");
  if (!result) return;
  form.dataset.initialized = "true";

  function render() {
    const values = Object.fromEntries(new FormData(form).entries());
    const assessment = assessReadiness(values);
    result.querySelector("[data-readiness-level]").textContent = assessment.level;
    result.querySelector("[data-readiness-score]").textContent = `${assessment.score} de 10`;
    result.querySelector("[data-readiness-next]").textContent = assessment.nextStep;
    result.querySelector("[data-readiness-controls]").replaceChildren(...assessment.controls.map((control) => {
      const item = document.createElement("li");
      item.textContent = control;
      return item;
    }));
  }

  form.addEventListener("change", render);
  form.addEventListener("reset", () => window.setTimeout(render, 0));
  render();
}

if (typeof document !== "undefined") {
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => initReadinessAssessment(), { once: true });
  } else {
    initReadinessAssessment();
  }
}
