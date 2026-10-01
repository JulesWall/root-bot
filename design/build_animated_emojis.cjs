// Animated adaptations of the existing Lucide icons; no bot or game changes.
const fs = require('node:fs/promises');
const path = require('node:path');
const { createRequire } = require('node:module');
const { createHash } = require('node:crypto');
const runtimeRequire = process.argv[2]
  ? createRequire(path.resolve(process.argv[2], 'package.json')) : require;
const sharp = runtimeRequire('sharp');
const OUT = path.join(__dirname, 'root-os-emojis-animes');
const SIZE = 128;
const FRAMES = 24;
const DELAY = 80;
const WHITE = '#EEF1F5';
const icons = [
  { name: 'root_alerte', color: '#FFC15A', label: 'Alerte pulsante', draw(t) {
    const s = 0.90 + 0.10 * (1 - Math.cos(t * Math.PI * 2)) / 2;
    return `<g transform="translate(12 12) scale(${s}) translate(-12 -12)"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4"/><path d="M12 17h.01"/></g>`;
  } },
  { name: 'root_terminal', color: '#54E2D1', label: 'Curseur clignotant', draw(t) {
    return `<polyline points="4 17 10 11 4 5"/>${t < 0.625 ? '<line x1="12" x2="20" y1="19" y2="19"/>' : ''}`;
  } },
  { name: 'root_recolter', color: WHITE, label: 'Fleche descendante', draw(t) {
    const y = -1.4 * Math.cos(t * Math.PI * 2);
    return `<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><g transform="translate(0 ${y})"><polyline points="7 10 12 15 17 10"/><line x1="12" x2="12" y1="15" y2="3"/></g>`;
  } },
  { name: 'root_scan', color: WHITE, label: 'Balayage du scan', draw(t) {
    const x = 11 + Math.cos(t * Math.PI * 2) * 5.2;
    return `<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/><defs><clipPath id="lens"><circle cx="11" cy="11" r="5.7"/></clipPath></defs><path d="M${x} 4v14" stroke="#54E2D1" stroke-width="1.8" clip-path="url(#lens)"/>`;
  } },
  { name: 'root_retour', color: WHITE, label: 'Mouvement de retour', draw(t) {
    const x = -1.6 * (1 - Math.cos(t * Math.PI * 2)) / 2;
    return `<g transform="translate(${x} 0)"><polyline points="9 14 4 9 9 4"/><path d="M20 20v-7a4 4 0 0 0-4-4H4"/></g>`;
  } },
];

function svg(icon, t) {
  return Buffer.from(`<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128" viewBox="0 0 24 24" fill="none" stroke="${icon.color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${icon.draw(t)}</svg>`);
}

async function encode(frames, width, height) {
  return sharp(Buffer.concat(frames), {
    raw: { width, height: height * frames.length, channels: 4, pageHeight: height },
  }).gif({ loop: 0, delay: frames.map(() => DELAY), colours: 64, dither: 0, effort: 7,
    interFrameMaxError: 0, interPaletteMaxError: 0, keepDuplicateFrames: true }).toBuffer();
}

async function verify(gif, name) {
  const meta = await sharp(gif, { animated: true }).metadata();
  if (meta.width !== SIZE || meta.pageHeight !== SIZE || meta.pages !== FRAMES ||
      !meta.hasAlpha || meta.loop !== 0 || gif.length >= 256 * 1024 ||
      meta.delay.some(delay => delay !== DELAY)) throw new Error(`Invalid GIF: ${name} ${JSON.stringify(meta)}`);
  const raw = await sharp(gif, { animated: true }).ensureAlpha().raw().toBuffer();
  const hashes = new Set();
  for (let f = 0; f < FRAMES; f++) {
    const frame = raw.subarray(f * SIZE * SIZE * 4, (f + 1) * SIZE * SIZE * 4);
    let visible = 0;
    for (let y = 0; y < SIZE; y++) for (let x = 0; x < SIZE; x++) {
      const alpha = frame[(y * SIZE + x) * 4 + 3];
      if (alpha) visible++;
      if (alpha && (x === 0 || y === 0 || x === SIZE - 1 || y === SIZE - 1)) {
        throw new Error(`Clipped frame: ${name}/${f}`);
      }
    }
    if (visible < 200 || visible > SIZE * SIZE * 0.6) throw new Error(`Bad alpha: ${name}/${f}`);
    hashes.add(createHash('sha256').update(frame).digest('hex'));
  }
  if (hashes.size < 2) throw new Error(`Not animated: ${name}`);
  return { name, bytes: gif.length, width: SIZE, height: SIZE, frames: meta.pages,
    durationMs: FRAMES * DELAY, uniqueFrames: hashes.size, transparent: true };
}

async function main() {
  await fs.mkdir(OUT, { recursive: true });
  const previews = Array.from({ length: FRAMES }, () => []);
  const manifest = [];
  for (const [i, icon] of icons.entries()) {
    const frames = [];
    for (let f = 0; f < FRAMES; f++) {
      frames.push(await sharp(svg(icon, f / FRAMES)).ensureAlpha().raw().toBuffer());
    }
    const gif = await encode(frames, SIZE, SIZE);
    manifest.push(await verify(gif, icon.name));
    await fs.writeFile(path.join(OUT, `${icon.name}.gif`), gif);
    // Preview the decoded GIF, including its actual indexed transparency.
    for (let f = 0; f < FRAMES; f++) {
      const png = await sharp(gif, { page: f, pages: 1 }).png().toBuffer();
      const url = `data:image/png;base64,${png.toString('base64')}`;
      previews[f].push(`<image x="${i * 180 + 34}" y="65" width="88" height="88" href="${url}"/><image x="${i * 180 + 132}" y="96" width="32" height="32" href="${url}"/><text x="${i * 180 + 90}" y="180" text-anchor="middle" fill="#EEF1F5" font-size="14">${icon.name}</text>`);
    }
  }
  const previewFrames = [];
  for (const tiles of previews) {
    const frame = Buffer.from(`<svg xmlns="http://www.w3.org/2000/svg" width="900" height="218"><rect width="900" height="218" fill="#232428"/><g font-family="Segoe UI,Arial,sans-serif"><text x="25" y="34" fill="#EEF1F5" font-size="20" font-weight="600">ROOT OS / EMOJIS ANIMES</text>${tiles.join('')}<text x="25" y="205" fill="#A4A8B0" font-size="12">Apercu des GIF exportes / grand format et 32 px / Lucide</text></g></svg>`);
    previewFrames.push(await sharp(frame).ensureAlpha().raw().toBuffer());
  }
  await fs.writeFile(path.join(OUT, 'apercu.gif'), await encode(previewFrames, 900, 218));
  await sharp(previewFrames[6], { raw: { width: 900, height: 218, channels: 4 } })
    .png().toFile(path.join(OUT, 'apercu.png'));
  await fs.copyFile(path.join(__dirname, 'root-os-emojis', 'LICENSE-LUCIDE.txt'), path.join(OUT, 'LICENSE-LUCIDE.txt'));
  await fs.writeFile(path.join(OUT, 'manifest.json'), JSON.stringify(manifest, null, 2) + '\n');
  console.log(JSON.stringify(manifest, null, 2));
}

main().catch(error => { console.error(error); process.exitCode = 1; });
