#!/usr/bin/env node
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const source = await readFile(new URL('../assets/js/push.js', import.meta.url), 'utf8');

assert.match(source, /function keyMatches\(sub\)/);
assert.match(source, /applicationServerKey: b64ToBytes\(VAPID\)/);
assert.match(source, /function revalidate\(reg\)/);
assert.match(source, /if \(!sub \|\| keyMatches\(sub\)\)/);
assert.match(source, /if \(!response\.ok\) throw new Error/);
assert.match(source, /sub\.unsubscribe\(\)\.catch/);

console.log('push client tests: ok');
