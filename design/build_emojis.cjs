// Build Discord emoji PNGs from the official Lucide vector assets.
const fs = require('node:fs/promises');
const path = require('node:path');
const { createRequire } = require('node:module');
const runtimeRequire = process.argv[2]
  ? createRequire(path.resolve(process.argv[2], 'package.json'))
  : require;
const sharp = runtimeRequire('sharp');

const VERSION = '0.468.0';
const BASE = `https://raw.githubusercontent.com/lucide-icons/lucide/${VERSION}`;
const OUT = path.join(__dirname, 'root-os-emojis');
const TEAL = '#54E2D1';
const WHITE = '#EEF1F5';
const AMBER = '#FFC15A';
const icons = [
  ['root_terminal', 'terminal', 'Terminal', TEAL],
  ['root_firewall', 'shield-half', 'Firewall', TEAL],
  ['root_ferme', 'server', 'Ferme de minage', TEAL],
  ['root_puissance', 'cpu', 'Puissance', TEAL],
  ['root_production', 'chart-column-increasing', 'Production', TEAL],
  ['root_memoire', 'database', 'Memoire et RTM', TEAL],
  ['root_temps', 'clock', 'Duree et developpement', TEAL],
  ['root_recolter', 'download', 'Recolter', WHITE],
  ['root_materiel', 'settings', 'Materiel', WHITE],
  ['root_logiciels', 'monitor', 'Logiciels', WHITE],
  ['root_operations', 'list', 'Operations', WHITE],
  ['root_journal', 'file-text', 'Journal', WHITE],
  ['root_alerte', 'triangle-alert', 'Anomalie et alerte', AMBER],
  ['root_scan', 'search', 'Diagnostiquer', WHITE],
  ['root_connexions', 'network', 'Connexions', WHITE],
  ['root_retour', 'corner-up-left', 'Retour', WHITE],
  ['root_bilan', 'chart-no-axes-column-increasing', 'Bilan', WHITE],
];

async function download(url) {
  const response = await fetch(url, { signal: AbortSignal.timeout(30000) });
  if (!response.ok) throw new Error(`${response.status}: ${url}`);
  return response.text();
}

async function main() {
  const responses = await Promise.allSettled([
    ...icons.map(([, source]) => download(`${BASE}/icons/${source}.svg`)),
    download(`${BASE}/LICENSE`),
  ]);
  const failures = responses.filter(item => item.status === 'rejected');
  if (failures.length) throw new Error(failures.map(item => item.reason.message).join('\n'));

  await fs.mkdir(path.join(OUT, 'png'), { recursive: true });
  await fs.mkdir(path.join(OUT, 'sources-svg'), { recursive: true });
  const manifest = [];
  const tiles = [];
  for (const [i, [name, source, label, color]] of icons.entries()) {
    const svg = responses[i].value;
    if (!svg.includes('<svg')) throw new Error(`Invalid SVG: ${source}`);
    await fs.writeFile(path.join(OUT, 'sources-svg', `${name}.svg`), svg);

    // Preserve Lucide's geometry and antialiasing; recolor through its alpha mask.
    const alpha = await sharp(Buffer.from(svg), { density: 384 })
      .resize(128, 128).ensureAlpha().extractChannel('alpha').toBuffer();
    const png = await sharp({ create: { width: 128, height: 128, channels: 3, background: color } })
      .joinChannel(alpha).png({ compressionLevel: 9 }).toBuffer();
    const file = path.join(OUT, 'png', `${name}.png`);
    await fs.writeFile(file, png);
    const metadata = await sharp(png).metadata();
    const { data } = await sharp(png).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
    let opaque = 0;
    for (let offset = 3; offset < data.length; offset += 4) if (data[offset] > 0) opaque++;
    if (metadata.width !== 128 || metadata.height !== 128 || !metadata.hasAlpha || png.length >= 256 * 1024
        || opaque < 200 || opaque > 128 * 128 * 0.8 || data[3] !== 0) {
      throw new Error(`Invalid emoji export: ${name}`);
    }
    manifest.push({ name, usage: label, color, file: `png/${name}.png`, bytes: png.length,
      source: `${BASE}/icons/${source}.svg`, size: 128 });
    const small = await sharp(png).resize(32, 32).png().toBuffer();
    const x = (i % 6) * 180;
    const y = 108 + Math.floor(i / 6) * 160;
    tiles.push(`<image x="${x + 40}" y="${y}" width="72" height="72" href="data:image/png;base64,${png.toString('base64')}"/>`);
    tiles.push(`<image x="${x + 130}" y="${y + 24}" width="32" height="32" href="data:image/png;base64,${small.toString('base64')}"/>`);
    tiles.push(`<text x="${x + 90}" y="${y + 100}" text-anchor="middle" fill="#F2F3F5" font-size="14">${name}</text>`);
    tiles.push(`<text x="${x + 90}" y="${y + 120}" text-anchor="middle" fill="#A4A8B0" font-size="12">${label}</text>`);
  }
  const preview = `<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="610">
    <rect width="1080" height="610" fill="#232428"/>
    <g font-family="Segoe UI,Arial,sans-serif">
      <text x="32" y="44" fill="#F2F3F5" font-size="25" font-weight="600">ROOT OS / EMOJIS</text>
      <text x="32" y="72" fill="#A4A8B0" font-size="15">17 PNG transparents · 128 x 128 · grand aperçu et taille 32 px</text>
      ${tiles.join('\n')}
      <text x="32" y="592" fill="#A4A8B0" font-size="12">Pictogrammes Lucide · palette Root OS · apercu sur fond sombre</text>
    </g>
  </svg>`;
  await sharp(Buffer.from(preview)).png().toFile(path.join(OUT, 'apercu.png'));
  await fs.writeFile(path.join(OUT, 'manifest.json'), JSON.stringify(manifest, null, 2) + '\n');
  await fs.writeFile(path.join(OUT, 'LICENSE-LUCIDE.txt'), responses.at(-1).value);
  console.log(JSON.stringify({ count: manifest.length, maxBytes: Math.max(...manifest.map(i => i.bytes)),
    output: OUT, transparent: true, size: '128x128' }, null, 2));
}

main().catch(error => { console.error(error.message); process.exitCode = 1; });
