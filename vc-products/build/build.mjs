#!/usr/bin/env node
// Builds vc-products/index.html: an encrypted list of Vital City data products.
// Inputs live in vc-products/private/ (gitignored, never published):
//   items.json  — one record per product (name, title, url, screenshotUrl, description, topic,
//                  lastUpdated, lastUpdatedWhat, refresh, dataThrough, methodFlag, methodNotes, vcStatus)
//   shots/<name>.jpg — screenshot for each product
//   password.txt — the page password (one line)
// Everything, screenshots included, goes inside the AES-GCM payload, so the
// public file shows nothing without the password.
// Run: node vc-products/build/build.mjs
import { readFileSync, writeFileSync, existsSync } from 'fs';
import { pbkdf2Sync, createCipheriv, randomBytes } from 'crypto';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const DIR = join(dirname(fileURLToPath(import.meta.url)), '..');
const PRIV = join(DIR, 'private');
const password = readFileSync(join(PRIV, 'password.txt'), 'utf8').trim();
const items = JSON.parse(readFileSync(join(PRIV, 'items.json'), 'utf8'));

let withShot = 0;
for (const p of items) {
  const f = join(PRIV, 'shots', `${p.name}.jpg`);
  if (existsSync(f)) { p.img = 'data:image/jpeg;base64,' + readFileSync(f).toString('base64'); withShot++; }
}

const now = new Date();
const builtDate = now.toLocaleDateString('en-CA', { timeZone: 'America/New_York' });
const plaintext = Buffer.from(JSON.stringify({ builtAt: now.getTime(), builtDate, items }), 'utf8');
const salt = randomBytes(16), iv = randomBytes(12), iterations = 250000;
const key = pbkdf2Sync(password, salt, iterations, 32, 'sha256');
const cipher = createCipheriv('aes-256-gcm', key, iv);
const ct = Buffer.concat([cipher.update(plaintext), cipher.final(), cipher.getAuthTag()]);
const payload = { iterations, salt: salt.toString('base64'), iv: iv.toString('base64'), ciphertext: ct.toString('base64') };

const html = readFileSync(join(DIR, 'build', 'template.html'), 'utf8').replace('__PAYLOAD__', JSON.stringify(payload));
writeFileSync(join(DIR, 'index.html'), html);
console.log(`index.html: ${items.length} products, ${withShot} screenshots, ${(html.length / 1e6).toFixed(1)} MB`);
