#!/usr/bin/env node
/**
 * Headless Chrome + Three.js studio renderer for DrinkLog.
 * Captures --keyframes-only (5 stage PNGs in /tmp/) or full 240-frame 3D
 * animation into outputs/drinklog_attachment_animation.mp4 and
 * outputs/drinklog_attachment_animation.gif (< 1.8 MiB).
 */

import { spawnSync } from 'node:child_process';
import { createRequire } from 'node:module';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { startDrinkLogServer } from './serve.mjs';

const require = createRequire(import.meta.url);
let playwrightCorePath;
for (const cand of [
  path.join(path.dirname(fileURLToPath(import.meta.url)), 'node_modules/playwright-core'),
  '/home/kaiser/projects/hong-kong-winter-threejs/node_modules/playwright-core',
]) {
  if (fs.existsSync(cand)) {
    playwrightCorePath = cand;
    break;
  }
}
if (!playwrightCorePath) {
  throw new Error('Could not find playwright-core locally.');
}
const { chromium } = require(playwrightCorePath);

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, '..');
const OUT_DIR = path.join(REPO_ROOT, 'outputs');
const OUT_MP4 = path.join(OUT_DIR, 'drinklog_attachment_animation.mp4');
const OUT_GIF = path.join(OUT_DIR, 'drinklog_attachment_animation.gif');
const CHROME_PATH = '/usr/bin/google-chrome';

const WIDTH = 960;
const HEIGHT = 540;
const FPS = 20;
const DURATION_SEC = 12.0;
const TOTAL_FRAMES = Math.round(FPS * DURATION_SEC);
const MAX_GIF_BYTES = 1_850_000;

async function launchChromeWithWebGL(baseUrl) {
  const configs = [
    {
      name: 'ANGLE-Vulkan',
      args: [
        '--no-sandbox', '--headless=new', '--use-angle=vulkan',
        '--enable-features=Vulkan', '--disable-vulkan-surface',
        '--disable-dev-shm-usage', '--disable-extensions',
        '--disable-component-update', '--disable-background-networking', '--disable-sync',
      ],
    },
    {
      name: 'ANGLE-GL-EGL',
      args: [
        '--no-sandbox', '--headless=new', '--use-gl=angle',
        '--use-angle=gl-egl', '--enable-webgl', '--ignore-gpu-blocklist',
        '--disable-dev-shm-usage', '--disable-extensions',
        '--disable-component-update', '--disable-background-networking', '--disable-sync',
      ],
    },
    {
      name: 'ANGLE-SwiftShader',
      args: [
        '--no-sandbox', '--headless=new', '--use-gl=angle',
        '--use-angle=swiftshader', '--enable-unsafe-swiftshader',
        '--enable-webgl', '--ignore-gpu-blocklist', '--disable-dev-shm-usage',
      ],
    },
  ];

  let lastErr = null;
  for (const cfg of configs) {
    console.log(`[chrome] Trying ${cfg.name}...`);
    const browser = await chromium.launch({
      executablePath: CHROME_PATH,
      headless: true,
      args: cfg.args,
    });
    const page = await browser.newPage({ viewport: { width: WIDTH, height: HEIGHT } });
    page.on('pageerror', (e) => console.error('[pageerror]', e.message));
    page.on('console', (m) => {
      if (m.type() === 'error') console.error('[console.error]', m.text());
    });

    try {
      await page.goto(`${baseUrl}/?headless=1`, { waitUntil: 'load', timeout: 30000 });
      await page.waitForFunction(() => window.__sceneReady === true, undefined, { timeout: 30000 });
      const info = await page.evaluate(() => window.__rendererInfo());
      // Verify actual rendered canvas pixels (skip backends that silently draw empty framebuffers)
      const canvasStats = await page.evaluate(() => {
        window.__seekAndRender(8.6);
        const c = document.getElementById('viewport');
        const ctx = document.createElement('canvas').getContext('2d');
        ctx.canvas.width = 160;
        ctx.canvas.height = 90;
        ctx.drawImage(c, 0, 0, 160, 90);
        const px = ctx.getImageData(0, 0, 160, 90).data;
        let nonZeroA = 0;
        for (let i = 0; i < px.length; i += 4) {
          if (px[i + 3] > 0) nonZeroA++;
        }
        return { nonZeroA };
      });
      if (canvasStats.nonZeroA < 200) {
        throw new Error(`WebGL framebuffer rendered blank (${canvasStats.nonZeroA} non-transparent sample pixels)`);
      }
      console.log(`[chrome:${cfg.name}] Ready:`, JSON.stringify(info), `pixels=${canvasStats.nonZeroA}`);
      return { browser, page };
    } catch (err) {
      console.warn(`[chrome:${cfg.name}] Skipped: ${err.message}`);
      lastErr = err;
      await browser.close();
    }
  }
  throw lastErr;
}

function encodeGifFromMp4(mp4Path, gifPath, width, fps, maxColors) {
  const palettePath = '/tmp/drinklog_threejs_palette.png';
  const vfPal = `fps=${fps},scale=${width}:-1:flags=lanczos,palettegen=max_colors=${maxColors}:stats_mode=diff`;
  const r1 = spawnSync('ffmpeg', ['-y', '-i', mp4Path, '-vf', vfPal, palettePath], { encoding: 'utf8' });
  if (r1.status !== 0) throw new Error(`ffmpeg palettegen failed: ${r1.stderr}`);

  const vfUse = `fps=${fps},scale=${width}:-1:flags=lanczos[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=3`;
  const r2 = spawnSync('ffmpeg', ['-y', '-i', mp4Path, '-i', palettePath, '-lavfi', vfUse, gifPath], { encoding: 'utf8' });
  fs.rmSync(palettePath, { force: true });
  if (r2.status !== 0) throw new Error(`ffmpeg paletteuse failed: ${r2.stderr}`);
  return fs.statSync(gifPath).size;
}

async function main() {
  const keyframesOnly = process.argv.includes('--keyframes-only');
  fs.mkdirSync(OUT_DIR, { recursive: true });

  const { server, url } = await startDrinkLogServer(0);
  let browser = null;

  try {
    const launched = await launchChromeWithWebGL(url);
    browser = launched.browser;
    const page = launched.page;

    if (keyframesOnly) {
      const kfTimes = [1.1, 3.8, 6.2, 8.6, 11.6];
      for (let i = 0; i < kfTimes.length; i++) {
        await page.evaluate((t) => window.__seekAndRender(t), kfTimes[i]);
        const outPng = `/tmp/drinklog_threejs_kf_${i + 1}.png`;
        await page.screenshot({ path: outPng, type: 'png' });
        console.log(`[keyframe] Saved t=${kfTimes[i]}s -> ${outPng}`);
      }
      return;
    }

    const tmpFramesDir = '/tmp/drinklog_threejs_frames';
    fs.rmSync(tmpFramesDir, { recursive: true, force: true });
    fs.mkdirSync(tmpFramesDir, { recursive: true });

    console.log(`[render] Capturing ${TOTAL_FRAMES} Three.js studio frames (${WIDTH}x${HEIGHT} @ ${FPS} fps)...`);
    for (let f = 0; f < TOTAL_FRAMES; f++) {
      const tSec = (f / TOTAL_FRAMES) * DURATION_SEC;
      await page.evaluate((t) => window.__seekAndRender(t), tSec);
      const framePath = path.join(tmpFramesDir, `frame_${String(f).padStart(4, '0')}.png`);
      await page.screenshot({ path: framePath, type: 'png' });
      if ((f + 1) % 60 === 0) {
        console.log(`[render] ${f + 1}/${TOTAL_FRAMES} frames captured`);
      }
    }

    const mp4Res = spawnSync('ffmpeg', [
      '-y', '-framerate', String(FPS),
      '-i', path.join(tmpFramesDir, 'frame_%04d.png'),
      '-an', '-vcodec', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '20',
      OUT_MP4,
    ], { encoding: 'utf8' });
    fs.rmSync(tmpFramesDir, { recursive: true, force: true });
    if (mp4Res.status !== 0) throw new Error(`ffmpeg mp4 encode failed: ${mp4Res.stderr}`);

    // Encode high-quality palette-optimized GIF strictly under 1.8 MiB
    let gifSize = encodeGifFromMp4(OUT_MP4, OUT_GIF, 720, 12, 128);
    if (gifSize > MAX_GIF_BYTES) {
      console.log(`[gif] ${gifSize} bytes > ${MAX_GIF_BYTES}, retrying compact 640px/10fps/96 colors...`);
      gifSize = encodeGifFromMp4(OUT_MP4, OUT_GIF, 640, 10, 96);
    }
    if (gifSize > MAX_GIF_BYTES) {
      console.log(`[gif] ${gifSize} bytes > ${MAX_GIF_BYTES}, retrying 600px/10fps/80 colors...`);
      gifSize = encodeGifFromMp4(OUT_MP4, OUT_GIF, 600, 10, 80);
    }

    const mp4Size = fs.statSync(OUT_MP4).size;
    console.log(`[done] MP4: ${OUT_MP4} (${(mp4Size / 1024).toFixed(1)} KiB)`);
    console.log(`[done] GIF: ${OUT_GIF} (${(gifSize / 1024).toFixed(1)} KiB)`);
  } finally {
    if (browser) await browser.close();
    server.close();
  }
}

await main();
