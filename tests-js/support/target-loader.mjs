import assert from "node:assert/strict";
import { readFile, stat } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

export const REPO_ROOT = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../..",
);

export function traceAssert(condition, traceId, message) {
  assert.ok(condition, `[${traceId}] ${message}`);
}

export async function fileExists(relativePath) {
  try {
    await stat(path.join(REPO_ROOT, relativePath));
    return true;
  } catch (error) {
    if (error && error.code === "ENOENT") return false;
    throw error;
  }
}

export async function readProjectFile(relativePath, traceId) {
  const absolutePath = path.join(REPO_ROOT, relativePath);
  try {
    return await readFile(absolutePath, "utf8");
  } catch (error) {
    traceAssert(false, traceId, `no se pudo leer ${relativePath}: ${error.message}`);
  }
}

async function importFresh(absolutePath) {
  const url = pathToFileURL(absolutePath);
  url.searchParams.set("contract", `${Date.now()}-${Math.random()}`);
  return import(url.href);
}

async function loadInstrumentedLegacyWorker(traceId) {
  const relativePath = "cf_worker.js";
  let source = await readProjectFile(relativePath, traceId);
  const defaultMarker = /export\s+default\s+\{/;
  traceAssert(defaultMarker.test(source), traceId, `${relativePath} no expone un Worker default instrumentable`);
  source = source.replace(defaultMarker, "const __workerDefault = {");
  source = source.replace(
    /export\s*\{\s*webPushEncrypt\s*,\s*generateVapidHeaders\s*,\s*buildNotificationPayload\s*\}\s*;?/g,
    "",
  );
  source += `
export default __workerDefault;
export {
  tokenOk,
  forbidden,
  publicPostImage,
  buildNotificationPayload,
  handleSubscribe,
  sendWelcomePush,
  handleUnsubscribe,
  handleSendOne,
  handleSend,
  handleDebugStatus,
  handleClearAll,
  limitedConcurrency,
  generateVapidHeaders,
  webPushEncrypt,
  hkdf,
  buildPkcs8PrivateKey,
  derSequence,
  derInteger,
  derOctetString,
  derBitString,
  derTagged,
  derLength,
  concatBytes,
  base64UrlDecode,
  base64UrlEncode,
};
//# sourceURL=mragentes-legacy-worker.instrumented.mjs
`;
  const encoded = Buffer.from(source, "utf8").toString("base64");
  try {
    return {
      module: await import(`data:text/javascript;base64,${encoded}#${Date.now()}-${Math.random()}`),
      relativePath,
      legacy: true,
    };
  } catch (error) {
    traceAssert(false, traceId, `falló la carga instrumentada de ${relativePath}: ${error.message}`);
  }
}

/**
 * Prefer the planned Worker entry point. Until it exists, instrument the copied
 * legacy Worker so characterization tests still exercise real production code.
 * This function is only called from test bodies, therefore a missing target is
 * reported as an AssertionError carrying the caller's trace ID.
 */
export async function loadWorkerTarget(traceId) {
  const candidates = [
    "workers/push/src/index.ts",
    "workers/push/src/index.js",
    "workers/push/src/worker.ts",
    "workers/push/src/worker.js",
  ];
  for (const relativePath of candidates) {
    if (!(await fileExists(relativePath))) continue;
    try {
      return {
        module: await importFresh(path.join(REPO_ROOT, relativePath)),
        relativePath,
        legacy: false,
      };
    } catch (error) {
      traceAssert(false, traceId, `el target ${relativePath} existe pero no carga: ${error.message}`);
    }
  }
  return loadInstrumentedLegacyWorker(traceId);
}

export function requireExport(target, exportName, traceId) {
  const value = target.module[exportName]
    ?? target.module.default?.[exportName]
    ?? target.module.__test?.[exportName];
  traceAssert(
    value !== undefined,
    traceId,
    `${target.relativePath} debe exportar ${exportName} para su contrato de pruebas`,
  );
  return value;
}

export function requireFunction(target, exportName, traceId) {
  const value = requireExport(target, exportName, traceId);
  traceAssert(typeof value === "function", traceId, `${exportName} debe ser una función`);
  return value;
}

export function workerHandler(target, traceId) {
  const handler = target.module.default ?? target.module.worker ?? target.module;
  traceAssert(handler && typeof handler.fetch === "function", traceId, "el Worker debe exponer fetch(request, env, ctx)");
  return handler;
}

export async function importPlannedModule(candidates, traceId) {
  for (const relativePath of candidates) {
    if (!(await fileExists(relativePath))) continue;
    try {
      return {
        module: await importFresh(path.join(REPO_ROOT, relativePath)),
        relativePath,
      };
    } catch (error) {
      traceAssert(false, traceId, `el módulo ${relativePath} existe pero no carga: ${error.message}`);
    }
  }
  traceAssert(false, traceId, `falta el módulo planificado (${candidates.join(" | ")})`);
}
