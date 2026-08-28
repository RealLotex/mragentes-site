/**
 * Wrap Vitest so every runtime failure has a stable trace fingerprint in the
 * error message as well as in the test title/JUnit node name.
 */
export function tracedTest(vitestTest) {
  return (title, callback) => {
    const match = /^\[([A-Z0-9-]+)\]\s+/.exec(title);
    if (!match) throw new Error(`[TRACE-FORMAT-001] test title lacks a leading trace ID: ${title}`);
    const traceId = match[1];
    return vitestTest(title, async (context) => {
      try {
        return await callback(context);
      } catch (error) {
        const prefix = `[${traceId}]`;
        const message = error && typeof error === "object"
          ? String(error.message ?? error)
          : String(error);
        if (message.startsWith(prefix)) throw error;
        // Assertion libraries may expose immutable messages or serialize the
        // original error before a mutation is visible. A fresh Error makes the
        // trace prefix part of the reporter's canonical failure text.
        throw new Error(`${prefix} ${message}`, { cause: error });
      }
    });
  };
}
