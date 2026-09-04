/* Calculadora de impacto: todos los cálculos viven en el navegador. No persiste
   ni transmite valores; el resultado es una estimación explícita, no una promesa. */

function nonNegative(value) {
  const parsed = Number(String(value ?? "").trim().replace(",", "."));
  return Number.isFinite(parsed) && parsed > 0 ? parsed : 0;
}

function round(value, digits = 1) {
  const factor = 10 ** digits;
  return Math.round((value + Number.EPSILON) * factor) / factor;
}

export function calculateImpact(values = {}) {
  const weeklyVolume = nonNegative(values.weeklyVolume);
  const manualMinutes = nonNegative(values.manualMinutes);
  const automatedMinutes = nonNegative(values.automatedMinutes);
  const hourlyCost = nonNegative(values.hourlyCost);
  const manualErrorRate = Math.min(100, nonNegative(values.manualErrorRate));
  const errorReduction = Math.min(100, nonNegative(values.errorReduction));
  const costPerError = nonNegative(values.costPerError);
  const monthlyCases = weeklyVolume * 4.33;
  const savedHours = Math.max(0, (manualMinutes - automatedMinutes) * monthlyCases / 60);
  const errorsAvoided = monthlyCases * (manualErrorRate / 100) * (errorReduction / 100);
  const operatingSavings = savedHours * hourlyCost;
  const errorSavings = errorsAvoided * costPerError;

  const controls = ["Registro de cada ejecución, responsable y resultado."];
  if (manualErrorRate > 0) controls.push("Muestra de revisión humana y criterio de excepción.");
  if (monthlyCases >= 200) controls.push("Prueba por lote, alerta de volumen y límite de reintentos.");
  if (costPerError > 0 || errorSavings > 0) controls.push("Criterio de escalamiento, reversión y aviso a una persona.");
  if (operatingSavings + errorSavings > 0) controls.push("Límite de gasto y autorización antes de ampliar el alcance.");
  if (automatedMinutes >= manualMinutes && weeklyVolume > 0) {
    controls.unshift("El flujo aún no reduce tiempo: revisá pasos, datos y aprobaciones antes de ampliarlo.");
  }

  return {
    monthlyCases: round(monthlyCases),
    savedHours: round(savedHours),
    errorsAvoided: round(errorsAvoided),
    operatingSavings: round(operatingSavings, 0),
    errorSavings: round(errorSavings, 0),
    totalPotential: round(operatingSavings + errorSavings, 0),
    controls,
  };
}

export function formatArs(value) {
  return new Intl.NumberFormat("es-AR", {
    style: "currency",
    currency: "ARS",
    maximumFractionDigits: 0,
  }).format(value);
}

export function initImpactCalculator(root = document) {
  const form = root.querySelector("[data-impact-calculator]");
  if (!form || form.dataset.initialized === "true") return;
  form.dataset.initialized = "true";

  const output = form.querySelector("[data-impact-results]");
  const controls = form.querySelector("[data-impact-controls]");
  const field = (name) => form.elements.namedItem(name);

  function values() {
    return {
      weeklyVolume: field("weekly_volume")?.value,
      manualMinutes: field("manual_minutes")?.value,
      automatedMinutes: field("automated_minutes")?.value,
      hourlyCost: field("hourly_cost")?.value,
      manualErrorRate: field("manual_error_rate")?.value,
      errorReduction: field("error_reduction")?.value,
      costPerError: field("cost_per_error")?.value,
    };
  }

  function render() {
    const result = calculateImpact(values());
    output.querySelector("[data-impact-hours]").textContent = result.savedHours.toLocaleString("es-AR", { maximumFractionDigits: 1 }) + " h";
    output.querySelector("[data-impact-operating]").textContent = formatArs(result.operatingSavings);
    output.querySelector("[data-impact-errors]").textContent = result.errorsAvoided.toLocaleString("es-AR", { maximumFractionDigits: 1 });
    output.querySelector("[data-impact-total]").textContent = formatArs(result.totalPotential);
    controls.replaceChildren(...result.controls.map((control) => {
      const item = document.createElement("li");
      item.textContent = control;
      return item;
    }));
  }

  form.addEventListener("input", render);
  form.addEventListener("reset", () => window.setTimeout(render, 0));
  render();
}

if (typeof document !== "undefined") {
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => initImpactCalculator(), { once: true });
  } else {
    initImpactCalculator();
  }
}
