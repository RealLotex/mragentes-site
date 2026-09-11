import { describe, expect, test } from "vitest";

import { importPlannedModule } from "./support/target-loader.mjs";

const TRACE = "READINESS-ASSESSMENT";

async function assessment() {
  const target = await importPlannedModule(["assets/js/readiness-assessment.js"], TRACE);
  return target.module;
}

describe("diagnóstico de punto de partida", () => {
  test("[READINESS-ASSESSMENT-001] prioriza un piloto repetible con datos claros y riesgo bajo", async () => {
    const { assessReadiness } = await assessment();
    const result = assessReadiness({
      frequency: "daily",
      clarity: "clear",
      impact: "low",
      exceptions: "few",
      owner: "yes",
    });

    expect(result.level).toBe("Listo para un piloto");
    expect(result.score).toBe(10);
    expect(result.nextStep).toMatch(/piloto/i);
    expect(result.controls).toContain("Definí una revisión humana para las excepciones.");
  });

  test("[READINESS-ASSESSMENT-002] frena acciones sensibles aunque el proceso sea frecuente", async () => {
    const { assessReadiness } = await assessment();
    const result = assessReadiness({
      frequency: "daily",
      clarity: "clear",
      impact: "high",
      exceptions: "few",
      owner: "yes",
    });

    expect(result.level).toBe("Preparar antes de automatizar");
    expect(result.score).toBe(7);
    expect(result.nextStep).toMatch(/no automatices la decisión/i);
    expect(result.controls).toContain("Agregá aprobación humana antes de cualquier acción sobre dinero, personas o compromisos externos.");
  });

  test("[READINESS-ASSESSMENT-003] identifica qué ordenar cuando todavía no hay una tarea definida", async () => {
    const { assessReadiness } = await assessment();
    const result = assessReadiness({
      frequency: "occasional",
      clarity: "unclear",
      impact: "medium",
      exceptions: "many",
      owner: "no",
    });

    expect(result.level).toBe("Ordenar el proceso primero");
    expect(result.score).toBe(0);
    expect(result.controls).toEqual(expect.arrayContaining([
      "Elegí una tarea repetible y escribí dónde empieza y dónde termina.",
      "Nombrá a una persona responsable de validar el resultado.",
    ]));
  });
});
