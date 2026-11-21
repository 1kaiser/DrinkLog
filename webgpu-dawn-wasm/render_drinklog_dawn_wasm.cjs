#!/usr/bin/env node
/**
 * render_drinklog_dawn_wasm.cjs
 * ------------------------------
 * Pure Node.js + LLVM Clang wasm32 C Kinematics + Native Dawn WebGPU (Vulkan RADV)
 * 3D studio animation renderer for DrinkLog (zero browser / zero Chrome).
 *
 * Uses single-pass batched GPU queue submission + single mapAsync() readback
 * across all 180 frames (15 fps x 12.0 s) and composites WASM-computed 3D renders
 * with crisp HUD overlays into MP4, GIF (< 1.8 MiB), and 2x2 Keyframes PNG.
 */

if (!process.env.VK_ICD_FILENAMES && require("fs").existsSync("/usr/share/vulkan/icd.d/radeon_icd.json")) {
  process.env.VK_ICD_FILENAMES = "/usr/share/vulkan/icd.d/radeon_icd.json";
}

const fs = require("fs");
const path = require("path");
const zlib = require("zlib");
const { spawn, spawnSync } = require("child_process");
const { create, globals } = require("webgpu");

Object.assign(globalThis, globals);

const BASE_DIR = __dirname;
const REPO_ROOT = path.resolve(BASE_DIR, "..");
const OUT_DIR = path.join(REPO_ROOT, "outputs");
const OUT_MP4 = path.join(OUT_DIR, "drinklog_attachment_animation.mp4");
const OUT_GIF = path.join(OUT_DIR, "drinklog_attachment_animation.gif");
const OUT_KF_SHEET = path.join(OUT_DIR, "drinklog_dawn_webgpu_keyframes.png");

const WIDTH = 960;
const HEIGHT = 540;
const FPS = 15;
const DURATION_SEC = 12.0;
const N_FRAMES = Math.round(FPS * DURATION_SEC); // 180 frames
const MAX_DRAWS_PER_FRAME = 28;
const UNIFORM_STRIDE = 256; // WebGPU minUniformBufferOffsetAlignment
const MAX_GIF_BYTES = 1_850_000;

// ---------------------------------------------------------------------------
// Minimal Pure-JS PNG Writer (saves RGBA buffer cleanly for keyframes)
// ---------------------------------------------------------------------------
const CRC_TABLE = (() => {
  const t = new Uint32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    t[n] = c >>> 0;
  }
  return t;
})();
function crc32(buf) {
  let c = 0xffffffff;
  for (let i = 0; i < buf.length; i++) c = CRC_TABLE[(c ^ buf[i]) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}
function makePngChunk(typeStr, dataBuf) {
  const len = Buffer.alloc(4);
  len.writeUInt32BE(dataBuf.length, 0);
  const type = Buffer.from(typeStr, "ascii");
  const crc = Buffer.alloc(4);
  crc.writeUInt32BE(crc32(Buffer.concat([type, dataBuf])), 0);
  return Buffer.concat([len, type, dataBuf, crc]);
}
function writeRgbaPng(outPath, rgbaBuf, w, h) {
  const sig = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(w, 0);
  ihdr.writeUInt32BE(h, 4);
  ihdr[8] = 8; ihdr[9] = 6; ihdr[10] = 0; ihdr[11] = 0; ihdr[12] = 0;
  const raw = Buffer.alloc((w * 4 + 1) * h);
  for (let y = 0; y < h; y++) {
    const rowDst = y * (w * 4 + 1);
    raw[rowDst] = 0;
    rgbaBuf.copy(raw, rowDst + 1, y * w * 4, (y + 1) * w * 4);
  }
  const png = Buffer.concat([
    sig,
    makePngChunk("IHDR", ihdr),
    makePngChunk("IDAT", zlib.deflateSync(raw, { level: 6 })),
    makePngChunk("IEND", Buffer.alloc(0)),
  ]);
  fs.writeFileSync(outPath, png);
}

// ---------------------------------------------------------------------------
// Procedural Indexed 3D Geometry Builders (8 floats/vert: x,y,z, nx,ny,nz, u,v)
// ---------------------------------------------------------------------------
function makeBox(w, h, d) {
  const hw = w * 0.5, hh = h * 0.5, hd = d * 0.5;
  const faces = [
    [[0,0,1],  [-hw,-hh, hd], [ hw,-hh, hd], [ hw, hh, hd], [-hw, hh, hd]],
    [[0,0,-1], [ hw,-hh,-hd], [-hw,-hh,-hd], [-hw, hh,-hd], [ hw, hh,-hd]],
    [[0,1,0],  [-hw, hh, hd], [ hw, hh, hd], [ hw, hh,-hd], [-hw, hh,-hd]],
    [[0,-1,0], [-hw,-hh,-hd], [ hw,-hh,-hd], [ hw,-hh, hd], [-hw,-hh, hd]],
    [[1,0,0],  [ hw,-hh, hd], [ hw,-hh,-hd], [ hw, hh,-hd], [ hw, hh, hd]],
    [[-1,0,0], [-hw,-hh,-hd], [-hw,-hh, hd], [-hw, hh, hd], [-hw, hh,-hd]],
  ];
  const verts = [], idx = [];
  let base = 0;
  for (const [n, a, b, c, d_] of faces) {
    verts.push(...a, ...n, 0, 1,  ...b, ...n, 1, 1,  ...c, ...n, 1, 0,  ...d_, ...n, 0, 0);
    idx.push(base, base + 1, base + 2, base, base + 2, base + 3);
    base += 4;
  }
  return { vertices: new Float32Array(verts), indices: new Uint32Array(idx) };
}

function makeCylinder(rTop, rBot, h, segs = 48, capped = true) {
  const verts = [], idx = [];
  const hh = h * 0.5;
  const slopeY = (rBot - rTop) / Math.max(h, 1e-4);
  for (let i = 0; i <= segs; i++) {
    const u = i / segs;
    const th = u * Math.PI * 2;
    const ct = Math.cos(th), st = Math.sin(th);
    const nLen = Math.hypot(ct, slopeY, st);
    const nx = ct / nLen, ny = slopeY / nLen, nz = st / nLen;
    verts.push(rBot * ct, -hh, rBot * st, nx, ny, nz, u, 1);
    verts.push(rTop * ct,  hh, rTop * st, nx, ny, nz, u, 0);
  }
  for (let i = 0; i < segs; i++) {
    const k = i * 2;
    idx.push(k, k + 2, k + 1, k + 1, k + 2, k + 3);
  }
  if (capped) {
    const topC = verts.length / 8;
    verts.push(0, hh, 0, 0, 1, 0, 0.5, 0.5);
    for (let i = 0; i <= segs; i++) {
      const th = (i / segs) * Math.PI * 2;
      verts.push(rTop * Math.cos(th), hh, rTop * Math.sin(th), 0, 1, 0, 0.5, 0.5);
    }
    for (let i = 0; i < segs; i++) idx.push(topC, topC + 1 + i + 1, topC + 1 + i);

    const botC = verts.length / 8;
    verts.push(0, -hh, 0, 0, -1, 0, 0.5, 0.5);
    for (let i = 0; i <= segs; i++) {
      const th = (i / segs) * Math.PI * 2;
      verts.push(rBot * Math.cos(th), -hh, rBot * Math.sin(th), 0, -1, 0, 0.5, 0.5);
    }
    for (let i = 0; i < segs; i++) idx.push(botC, botC + 1 + i, botC + 1 + i + 1);
  }
  return { vertices: new Float32Array(verts), indices: new Uint32Array(idx) };
}

function makeLathe(pts, segs = 56) {
  const verts = [], idx = [];
  for (let j = 0; j < pts.length; j++) {
    const [r, y] = pts[j];
    const [rPrev, yPrev] = pts[Math.max(0, j - 1)];
    const [rNext, yNext] = pts[Math.min(pts.length - 1, j + 1)];
    const dr = rNext - rPrev, dy = yNext - yPrev;
    const len = Math.hypot(dy, -dr) || 1;
    const nr = dy / len, ny = -dr / len;
    for (let i = 0; i <= segs; i++) {
      const u = i / segs;
      const th = u * Math.PI * 2;
      const ct = Math.cos(th), st = Math.sin(th);
      verts.push(r * ct, y, r * st, nr * ct, ny, nr * st, u, j / (pts.length - 1));
    }
  }
  const stride = segs + 1;
  for (let j = 0; j < pts.length - 1; j++) {
    for (let i = 0; i < segs; i++) {
      const a = j * stride + i, b = a + 1, c = (j + 1) * stride + i, d = c + 1;
      idx.push(a, c, b, b, c, d);
    }
  }
  return { vertices: new Float32Array(verts), indices: new Uint32Array(idx) };
}

function makeTorus(R, rTube, radialSegs = 48, tubeSegs = 14, arc = Math.PI * 2) {
  const verts = [], idx = [];
  for (let i = 0; i <= radialSegs; i++) {
    const u = i / radialSegs;
    const th = u * arc;
    const ct = Math.cos(th), st = Math.sin(th);
    for (let j = 0; j <= tubeSegs; j++) {
      const v = j / tubeSegs;
      const ph = v * Math.PI * 2;
      const cp = Math.cos(ph), sp = Math.sin(ph);
      const px = (R + rTube * cp) * ct;
      const py = (R + rTube * cp) * st;
      const pz = rTube * sp;
      verts.push(px, py, pz, cp * ct, cp * st, sp, u, v);
    }
  }
  const row = tubeSegs + 1;
  for (let i = 0; i < radialSegs; i++) {
    for (let j = 0; j < tubeSegs; j++) {
      const a = i * row + j, b = (i + 1) * row + j, c = (i + 1) * row + j + 1, d = i * row + j + 1;
      idx.push(a, b, d, b, c, d);
    }
  }
  return { vertices: new Float32Array(verts), indices: new Uint32Array(idx) };
}

function makeSphere(r, lat = 14, lon = 20) {
  const verts = [], idx = [];
  for (let i = 0; i <= lat; i++) {
    const th = (i / lat) * Math.PI;
    const st = Math.sin(th), ct = Math.cos(th);
    for (let j = 0; j <= lon; j++) {
      const ph = (j / lon) * Math.PI * 2;
      const nx = st * Math.cos(ph), ny = ct, nz = st * Math.sin(ph);
      verts.push(r * nx, r * ny, r * nz, nx, ny, nz, j / lon, i / lat);
    }
  }
  const row = lon + 1;
  for (let i = 0; i < lat; i++) {
    for (let j = 0; j < lon; j++) {
      const a = i * row + j, b = (i + 1) * row + j, c = b + 1, d = a + 1;
      idx.push(a, b, d, b, c, d);
    }
  }
  return { vertices: new Float32Array(verts), indices: new Uint32Array(idx) };
}

function makeScreenQuad(w, h) {
  const hw = w * 0.5, hh = h * 0.5;
  const verts = new Float32Array([
    -hw, -hh, 0,  0, 0, 1,  0, 1,
     hw, -hh, 0,  0, 0, 1,  1, 1,
     hw,  hh, 0,  0, 0, 1,  1, 0,
    -hw,  hh, 0,  0, 0, 1,  0, 0,
  ]);
  const idx = new Uint32Array([0, 1, 2, 0, 2, 3]);
  return { vertices: verts, indices: idx };
}

// ---------------------------------------------------------------------------
// WGSL Shaders (Studio 3-Point Blinn-Phong + Fresnel Glass + Textured Phone)
// ---------------------------------------------------------------------------
const WGSL_COMMON = /* wgsl */ `
struct Uniforms {
  mvp      : mat4x4<f32>,
  model    : mat4x4<f32>,
  color    : vec4<f32>,
  emissive : vec4<f32>,
  camPos   : vec4<f32>,
  lightDir : vec4<f32>,
};
@group(0) @binding(0) var<uniform> u : Uniforms;

struct VSIn {
  @location(0) pos : vec3<f32>,
  @location(1) nor : vec3<f32>,
  @location(2) uv  : vec2<f32>,
};

struct VSOut {
  @builtin(position) clipPos : vec4<f32>,
  @location(0) worldPos : vec3<f32>,
  @location(1) worldNor : vec3<f32>,
  @location(2) uv       : vec2<f32>,
};

@vertex
fn vs_main(v : VSIn) -> VSOut {
  var o : VSOut;
  let wp = (u.model * vec4<f32>(v.pos, 1.0)).xyz;
  o.clipPos = u.mvp * vec4<f32>(v.pos, 1.0);
  o.worldPos = wp;
  o.worldNor = normalize((u.model * vec4<f32>(v.nor, 0.0)).xyz);
  o.uv = v.uv;
  return o;
}

@fragment
fn fs_lit(in : VSOut) -> @location(0) vec4<f32> {
  let N = normalize(in.worldNor);
  let V = normalize(u.camPos.xyz - in.worldPos);
  let L1 = normalize(u.lightDir.xyz);
  let L2 = normalize(vec3<f32>(-14.0, 12.0, -10.0));

  let diff1 = max(dot(N, L1), 0.0);
  let diff2 = max(dot(N, L2), 0.0) * 0.35;
  let hemi  = 0.34 + 0.16 * N.y;

  let H1 = normalize(L1 + V);
  let spec = pow(max(dot(N, H1), 0.0), 36.0) * 0.42;
  let fresnel = pow(1.0 - max(abs(dot(N, V)), 0.0), 2.2);

  var rgb = u.color.rgb * (hemi + 0.62 * diff1 + diff2) + vec3<f32>(spec);
  rgb += u.emissive.rgb * u.emissive.w;

  var alpha = u.color.a;
  if (u.camPos.w > 0.5) {
    // Translucent glass bottle rim crispness over pure #FFFFFF
    alpha = clamp(u.color.a + 0.32 * fresnel, 0.15, 0.85);
    rgb = mix(rgb, vec3<f32>(0.55, 0.78, 0.94), 0.25 * fresnel);
  }
  return vec4<f32>(clamp(rgb, vec3<f32>(0.0), vec3<f32>(1.0)), alpha);
}
`;

const WGSL_SCREEN = /* wgsl */ `
@group(1) @binding(0) var screenSampler : sampler;
@group(1) @binding(1) var screenTex : texture_2d<f32>;

@fragment
fn fs_screen(in : VSOut) -> @location(0) vec4<f32> {
  return textureSample(screenTex, screenSampler, in.uv);
}
`;

function alphaCompositeInPlace(dstRgba, srcRgba) {
  for (let i = 0; i < dstRgba.length; i += 4) {
    const a = srcRgba[i + 3];
    if (a === 0) continue;
    if (a === 255) {
      dstRgba[i] = srcRgba[i];
      dstRgba[i + 1] = srcRgba[i + 1];
      dstRgba[i + 2] = srcRgba[i + 2];
      dstRgba[i + 3] = 255;
      continue;
    }
    const fa = a / 255.0;
    const inv = 1.0 - fa;
    dstRgba[i] = Math.round(srcRgba[i] * fa + dstRgba[i] * inv);
    dstRgba[i + 1] = Math.round(srcRgba[i + 1] * fa + dstRgba[i + 1] * inv);
    dstRgba[i + 2] = Math.round(srcRgba[i + 2] * fa + dstRgba[i + 2] * inv);
    dstRgba[i + 3] = 255;
  }
}

function encodeGifFromMp4(mp4Path, gifPath, width, fps, maxColors) {
  const pal = "/tmp/drinklog_dawn_palette.png";
  const r1 = spawnSync("ffmpeg", [
    "-y", "-threads", "3", "-i", mp4Path,
    "-vf", `fps=${fps},scale=${width}:-1:flags=lanczos,palettegen=max_colors=${maxColors}:stats_mode=diff`,
    pal,
  ], { encoding: "utf8" });
  if (r1.status !== 0) throw new Error(`ffmpeg palettegen failed: ${r1.stderr}`);

  const r2 = spawnSync("ffmpeg", [
    "-y", "-threads", "3", "-i", mp4Path, "-i", pal,
    "-lavfi", `fps=${fps},scale=${width}:-1:flags=lanczos[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=3`,
    gifPath,
  ], { encoding: "utf8" });
  fs.rmSync(pal, { force: true });
  if (r2.status !== 0) throw new Error(`ffmpeg paletteuse failed: ${r2.stderr}`);
  return fs.statSync(gifPath).size;
}

// ---------------------------------------------------------------------------
// Main Node + Clang WASM + Native Dawn WebGPU Pipeline
// ---------------------------------------------------------------------------
async function main() {
  fs.mkdirSync(OUT_DIR, { recursive: true });

  // 1. Instantiate Clang-compiled wasm32 kinematics kernel
  const wasmPath = path.join(BASE_DIR, "wasm", "drinklog_kinematics.wasm");
  const wasmMemory = new WebAssembly.Memory({ initial: 4 });
  const { instance: wasmInst } = await WebAssembly.instantiate(fs.readFileSync(wasmPath), {
    env: { __linear_memory: wasmMemory },
  });
  const { wasm_eval_stage, wasm_build_mvp, wasm_eval_physics } = wasmInst.exports;

  // Smoke-verify WASM physics kernel parity
  const f32 = new Float32Array(wasmMemory.buffer);
  const PTR_STATE = 1024;
  const PTR_TRS = 2048;
  const PTR_EYE = 2112;
  const PTR_TGT = 2144;
  const PTR_MVP = 2208;
  const PTR_MOD = 2272;
  const PTR_PHYS = 2400;
  wasm_eval_physics(1067.0, 1.10, 1180.0, PTR_PHYS);
  console.log(
    `[wasm32] Kernel loaded | physics test: 1067g @ 1.10g -> ${f32[PTR_PHYS / 4].toFixed(1)} g, ` +
    `delta=${f32[PTR_PHYS / 4 + 1].toFixed(1)} mL`
  );

  // 2. Load pre-rendered transparent HUD overlays & phone screen texture
  const hudLayers = {};
  for (let s = 1; s <= 5; s++) {
    hudLayers[s] = new Uint8Array(zlib.inflateSync(fs.readFileSync(path.join(BASE_DIR, "hud_cache", `hud_stage_${s}.rgba.zlib`))));
  }
  const phoneTexData = new Uint8Array(zlib.inflateSync(fs.readFileSync(path.join(BASE_DIR, "hud_cache", "phone_screen_hc.rgba.zlib"))));

  // 3. Acquire Dawn WebGPU Hardware GPU Device
  const gpu = create([]);
  const adapter = await gpu.requestAdapter({ powerPreference: "high-performance" });
  if (!adapter) throw new Error("Failed to acquire native Dawn WebGPU adapter.");
  const info = adapter.info;
  console.log(`[dawn-webgpu] Adapter: vendor=${info.vendor} arch=${info.architecture} desc="${info.description}"`);

  const device = await adapter.requestDevice({
    requiredLimits: { maxBufferSize: adapter.limits.maxBufferSize },
  });

  // Upload static meshes to GPU
  function uploadMesh(geom) {
    const vbo = device.createBuffer({ size: geom.vertices.byteLength, usage: GPUBufferUsage.VERTEX | GPUBufferUsage.COPY_DST });
    device.queue.writeBuffer(vbo, 0, geom.vertices);
    const ibo = device.createBuffer({ size: geom.indices.byteLength, usage: GPUBufferUsage.INDEX | GPUBufferUsage.COPY_DST });
    device.queue.writeBuffer(ibo, 0, geom.indices);
    return { vbo, ibo, count: geom.indices.length };
  }

  const meshes = {
    shadowDisc: uploadMesh(makeCylinder(3.35, 3.35, 0.04, 48)),
    bottleGlass: uploadMesh(makeLathe([
      [0.01, 0.0], [3.05, 0.0], [3.20, 0.35], [3.20, 9.8], [3.05, 10.6], [1.42, 12.2], [1.42, 13.7],
    ], 56)),
    bottleBase: uploadMesh(makeCylinder(3.05, 3.05, 0.22, 48)),
    waterCyl: uploadMesh(makeCylinder(2.96, 2.96, 1.0, 48)),
    meniscus: uploadMesh(makeTorus(2.92, 0.07, 48, 10)),
    // Standard PET cap (Ø30.5 mm -> R = 1.525 u) & 1.10x DrinkLog (Ø33.6 mm -> R = 1.68 u)
    screwCap: uploadMesh(makeCylinder(1.525, 1.525, 1.35, 48)),
    collar: uploadMesh(makeCylinder(1.68, 1.68, 0.54, 56)),
    silPad: uploadMesh(makeBox(0.14, 0.42, 0.65)),
    hubPlate: uploadMesh(makeCylinder(1.60, 1.60, 0.18, 48)),
    flexRing: uploadMesh(makeTorus(1.44, 0.10, 48, 12)),
    puckShell: uploadMesh(makeCylinder(1.68, 1.68, 0.58, 56)),
    lipo: uploadMesh(makeBox(1.80, 0.32, 1.40)),
    pcb: uploadMesh(makeCylinder(1.40, 1.40, 0.09, 48)),
    lid: uploadMesh(makeCylinder(1.56, 1.66, 0.20, 56)),
    led: uploadMesh(makeSphere(0.12, 12, 16)),
    bail: uploadMesh(makeTorus(1.64, 0.09, 48, 14, Math.PI)),
    usbBezel: uploadMesh(makeBox(0.28, 0.28, 0.88)),
    usbPlug: uploadMesh(makeBox(0.22, 0.30, 0.86)),
    cableHead: uploadMesh(makeBox(1.10, 0.30, 0.80)),
    cableTip: uploadMesh(makeBox(0.45, 0.16, 0.62)),
    cableCord: uploadMesh(makeCylinder(0.11, 0.11, 5.2, 16)),
    bleWave: uploadMesh(makeTorus(0.9, 0.055, 36, 10)),
    phoneBody: uploadMesh(makeBox(4.2, 8.4, 0.40)),
    phoneScreen: uploadMesh(makeScreenQuad(3.78, 7.80)),
  };

  // Phone Screen GPU Texture + Sampler
  const phoneTex = device.createTexture({
    size: { width: 256, height: 512, depthOrArrayLayers: 1 },
    format: "rgba8unorm",
    usage: GPUTextureUsage.TEXTURE_BINDING | GPUTextureUsage.COPY_DST,
  });
  device.queue.writeTexture({ texture: phoneTex }, phoneTexData, { bytesPerRow: 256 * 4 }, { width: 256, height: 512 });
  const sampler = device.createSampler({ magFilter: "linear", minFilter: "linear" });

  // Pipelines
  const bindGroupLayout0 = device.createBindGroupLayout({
    entries: [{
      binding: 0,
      visibility: GPUShaderStage.VERTEX | GPUShaderStage.FRAGMENT,
      buffer: { type: "uniform", hasDynamicOffset: true, minBindingSize: 192 },
    }],
  });
  const bindGroupLayout1 = device.createBindGroupLayout({
    entries: [
      { binding: 0, visibility: GPUShaderStage.FRAGMENT, sampler: { type: "filtering" } },
      { binding: 1, visibility: GPUShaderStage.FRAGMENT, texture: { sampleType: "float" } },
    ],
  });

  const shaderMod = device.createShaderModule({ code: WGSL_COMMON + "\n" + WGSL_SCREEN });
  const vLayout = [{
    arrayStride: 32,
    attributes: [
      { shaderLocation: 0, offset: 0, format: "float32x3" },
      { shaderLocation: 1, offset: 12, format: "float32x3" },
      { shaderLocation: 2, offset: 24, format: "float32x2" },
    ],
  }];

  const opaquePipeline = device.createRenderPipeline({
    layout: device.createPipelineLayout({ bindGroupLayouts: [bindGroupLayout0] }),
    vertex: { module: shaderMod, entryPoint: "vs_main", buffers: vLayout },
    fragment: { module: shaderMod, entryPoint: "fs_lit", targets: [{ format: "rgba8unorm" }] },
    primitive: { topology: "triangle-list", cullMode: "none" },
    depthStencil: { format: "depth24plus", depthWriteEnabled: true, depthCompare: "less" },
  });

  const glassPipeline = device.createRenderPipeline({
    layout: device.createPipelineLayout({ bindGroupLayouts: [bindGroupLayout0] }),
    vertex: { module: shaderMod, entryPoint: "vs_main", buffers: vLayout },
    fragment: {
      module: shaderMod,
      entryPoint: "fs_lit",
      targets: [{
        format: "rgba8unorm",
        blend: {
          color: { srcFactor: "src-alpha", dstFactor: "one-minus-src-alpha", operation: "add" },
          alpha: { srcFactor: "one", dstFactor: "one-minus-src-alpha", operation: "add" },
        },
      }],
    },
    primitive: { topology: "triangle-list", cullMode: "none" },
    depthStencil: { format: "depth24plus", depthWriteEnabled: false, depthCompare: "less" },
  });

  const screenPipeline = device.createRenderPipeline({
    layout: device.createPipelineLayout({ bindGroupLayouts: [bindGroupLayout0, bindGroupLayout1] }),
    vertex: { module: shaderMod, entryPoint: "vs_main", buffers: vLayout },
    fragment: { module: shaderMod, entryPoint: "fs_screen", targets: [{ format: "rgba8unorm" }] },
    primitive: { topology: "triangle-list", cullMode: "none" },
    depthStencil: { format: "depth24plus", depthWriteEnabled: true, depthCompare: "less" },
  });

  // Allocate Uniform Ring Buffer + Render Targets + Single Batched Readback Buffer
  const totalSlots = N_FRAMES * MAX_DRAWS_PER_FRAME;
  const uniformBuf = device.createBuffer({
    size: totalSlots * UNIFORM_STRIDE,
    usage: GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST,
  });
  const uniformCpu = new ArrayBuffer(totalSlots * UNIFORM_STRIDE);
  const uniformF32 = new Float32Array(uniformCpu);

  const bindGroup0 = device.createBindGroup({
    layout: bindGroupLayout0,
    entries: [{ binding: 0, resource: { buffer: uniformBuf, offset: 0, size: 192 } }],
  });
  const bindGroup1 = device.createBindGroup({
    layout: bindGroupLayout1,
    entries: [
      { binding: 0, resource: sampler },
      { binding: 1, resource: phoneTex.createView() },
    ],
  });

  const colorTex = device.createTexture({
    size: { width: WIDTH, height: HEIGHT, depthOrArrayLayers: 1 },
    format: "rgba8unorm",
    usage: GPUTextureUsage.RENDER_ATTACHMENT | GPUTextureUsage.COPY_SRC,
  });
  const depthTex = device.createTexture({
    size: { width: WIDTH, height: HEIGHT, depthOrArrayLayers: 1 },
    format: "depth24plus",
    usage: GPUTextureUsage.RENDER_ATTACHMENT,
  });
  const colorView = colorTex.createView();
  const depthView = depthTex.createView();

  const bytesPerRowUnaligned = WIDTH * 4;
  const bytesPerRow = Math.ceil(bytesPerRowUnaligned / 256) * 256;
  const frameBytes = bytesPerRow * HEIGHT;
  const totalReadbackBytes = frameBytes * N_FRAMES;
  console.log(`[dawn-webgpu] Single-mapAsync batch buffer: ${N_FRAMES} frames x ${WIDTH}x${HEIGHT} = ${(totalReadbackBytes / 1e6).toFixed(1)} MB`);

  const bigReadbackBuf = device.createBuffer({
    size: totalReadbackBytes,
    usage: GPUBufferUsage.COPY_DST | GPUBufferUsage.MAP_READ,
  });

  // -------------------------------------------------------------------------
  // 4. Build All 180 Frames via WASM Kinematics & Record GPU Draw Lists
  // -------------------------------------------------------------------------
  const tWasm0 = Date.now();
  const frameDrawLists = [];
  const frameStages = [];
  const aspect = WIDTH / HEIGHT;
  const fovRad = (36.0 * Math.PI) / 180.0;

  let slotIdx = 0;

  function addDraw(drawList, mesh, pipelineType, trs, rgba, emissive = [0, 0, 0, 0], glassFlag = 0, eye = [0, 0, 0], tgt = [0, 0, 0]) {
    for (let k = 0; k < 9; k++) f32[PTR_TRS / 4 + k] = trs[k];
    for (let k = 0; k < 3; k++) { f32[PTR_EYE / 4 + k] = eye[k]; f32[PTR_TGT / 4 + k] = tgt[k]; }
    wasm_build_mvp(PTR_TRS, PTR_EYE, PTR_TGT, fovRad, aspect, 0.2, 200.0, PTR_MVP, PTR_MOD);

    const baseF = (slotIdx * UNIFORM_STRIDE) / 4;
    for (let k = 0; k < 16; k++) {
      uniformF32[baseF + k] = f32[PTR_MVP / 4 + k];
      uniformF32[baseF + 16 + k] = f32[PTR_MOD / 4 + k];
    }
    uniformF32.set(rgba, baseF + 32);
    uniformF32.set(emissive, baseF + 36);
    uniformF32.set([eye[0], eye[1], eye[2], glassFlag], baseF + 40);
    uniformF32.set([14.0, 28.0, 16.0, 0.0], baseF + 44);

    drawList.push({ mesh, pipelineType, offsetBytes: slotIdx * UNIFORM_STRIDE });
    slotIdx++;
  }

  for (let f = 0; f < N_FRAMES; f++) {
    const tSec = (f / N_FRAMES) * DURATION_SEC;
    wasm_eval_stage(tSec, DURATION_SEC, PTR_STATE);
    const stBase = PTR_STATE / 4;
    const stage = Math.round(f32[stBase + 0]);
    const jawRadius = f32[stBase + 1];
    const scrollRot = f32[stBase + 2];
    const capDropY = f32[stBase + 3];
    const capRotY = f32[stBase + 4];
    const bottleLiftY = f32[stBase + 5];
    const bailAngle = f32[stBase + 6];
    const flexStrain = f32[stBase + 7];
    const waterFrac = f32[stBase + 8];
    const usbPlugZ = f32[stBase + 11];
    const cableProg = f32[stBase + 12];
    const blePhase = f32[stBase + 13];
    const phoneVis = f32[stBase + 14];
    const eye = [f32[stBase + 15], f32[stBase + 16], f32[stBase + 17]];
    const tgt = [f32[stBase + 18], f32[stBase + 19], f32[stBase + 20]];
    const ledRgb = [f32[stBase + 21], f32[stBase + 22], f32[stBase + 23]];

    frameStages.push(stage);
    const opaqueList = [];
    const glassList = [];

    // Ground contact shadow disc (softens as bottle lifts)
    const shScale = 1.0 + 0.06 * bottleLiftY;
    const shAlpha = Math.max(0.05, 0.14 - 0.025 * bottleLiftY);
    addDraw(glassList, meshes.shadowDisc, "glass", [0, 0.02, 0, 0, 0, 0, shScale, 1, shScale], [0.15, 0.22, 0.30, shAlpha], [0,0,0,0], 0, eye, tgt);

    // Bottle Base + Water Column + Meniscus + Screw Cap
    addDraw(opaqueList, meshes.bottleBase, "opaque", [0, bottleLiftY + 0.11, 0, 0, 0, 0, 1, 1, 1], [0.68, 0.84, 0.94, 1.0], [0,0,0,0], 0, eye, tgt);
    const waterH = 9.5 * waterFrac;
    addDraw(glassList, meshes.waterCyl, "glass", [0, bottleLiftY + 0.22 + waterH * 0.5, 0, 0, 0, 0, 1, waterH, 1], [0.18, 0.53, 0.88, 0.72], [0,0,0,0], 0, eye, tgt);
    addDraw(glassList, meshes.meniscus, "glass", [0, bottleLiftY + 0.22 + waterH, 0, Math.PI / 2, 0, 0, 1, 1, 1], [0.55, 0.80, 0.96, 0.88], [0,0,0,0], 0, eye, tgt);

    const capLift = stage === 3 ? capDropY : 0.0;
    addDraw(opaqueList, meshes.screwCap, "opaque", [0, bottleLiftY + 14.32 + capLift, 0, 0, capRotY, 0, 1, 1, 1], [0.28, 0.33, 0.38, 1.0], [0,0,0,0], 0, eye, tgt);

    // Translucent Glass Bottle Shell (rendered in glass pass after inner water)
    addDraw(glassList, meshes.bottleGlass, "glass", [0, bottleLiftY, 0, 0, 0, 0, 1, 1, 1], [0.62, 0.84, 0.97, 0.32], [0,0,0,0], 1, eye, tgt);

    // DrinkLog Assembly base Y
    const capY = bottleLiftY + 14.35 + (stage === 1 ? capDropY : capLift);
    addDraw(opaqueList, meshes.collar, "opaque", [0, capY + 0.27, 0, 0, capRotY + scrollRot, 0, 1, 1, 1], [0.17, 0.24, 0.31, 1.0], [0,0,0,0], 0, eye, tgt);

    // 6 Compliant Split Collet Petals wrapping 1.1x D_cap cleanly
    for (let k = 0; k < 6; k++) {
      const ang = capRotY + (k * 2 * Math.PI) / 6;
      const ca = Math.cos(ang), sa = Math.sin(ang);
      addDraw(opaqueList, meshes.silPad, "opaque", [jawRadius * ca, capY + 0.26, -jawRadius * sa, 0, ang, 0, 1, 1, 1], [0.90, 0.49, 0.13, 1.0], [0,0,0,0], 0, eye, tgt);
    }

    // Hub + Universal Ø30 mm 3-Spoke Stainless Flexure
    addDraw(opaqueList, meshes.hubPlate, "opaque", [0, capY + 0.63, 0, 0, capRotY, 0, 1, 1, 1], [0.36, 0.43, 0.49, 1.0], [0,0,0,0], 0, eye, tgt);
    const flexY = capY + 0.78 - 0.05 * flexStrain;
    const flexGlow = [0.95, 0.61, 0.07, 0.9 * flexStrain];
    addDraw(opaqueList, meshes.flexRing, "opaque", [0, flexY, 0, Math.PI / 2, 0, capRotY, 1, 1, 1], [0.82, 0.85, 0.88, 1.0], flexGlow, 0, eye, tgt);

    // Upper Puck Internals (401520 LiPo + Ø28 mm PCB) + 1.1x Shell + Lid + Status LED
    const puckY = capY + 0.88 + 0.05 * flexStrain;
    addDraw(opaqueList, meshes.lipo, "opaque", [0, puckY + 0.22, 0, 0, capRotY, 0, 1, 1, 1], [0.95, 0.61, 0.07, 1.0], [0,0,0,0], 0, eye, tgt);
    addDraw(opaqueList, meshes.pcb, "opaque", [0, puckY + 0.44, 0, 0, capRotY, 0, 1, 1, 1], [0.05, 0.39, 0.31, 1.0], [0,0,0,0], 0, eye, tgt);
    addDraw(glassList, meshes.puckShell, "glass", [0, puckY + 0.29, 0, 0, capRotY, 0, 1, 1, 1], [0.11, 0.42, 0.66, 0.82], [0,0,0,0], 0, eye, tgt);
    addDraw(opaqueList, meshes.lid, "opaque", [0, puckY + 0.68, 0, 0, capRotY, 0, 1, 1, 1], [0.16, 0.50, 0.73, 1.0], [0,0,0,0], 0, eye, tgt);
    const ledX = 1.05 * Math.cos(capRotY) + 0.55 * Math.sin(capRotY);
    const ledZ = -1.05 * Math.sin(capRotY) + 0.55 * Math.cos(capRotY);
    addDraw(opaqueList, meshes.led, "opaque", [ledX, puckY + 0.80, ledZ, 0, 0, 0, 1, 1, 1], [ledRgb[0], ledRgb[1], ledRgb[2], 1.0], [ledRgb[0], ledRgb[1], ledRgb[2], 0.85], 0, eye, tgt);

    // Pivoting Slim Brushed-Aluminum Finger Bail (R = 1.64 u)
    addDraw(opaqueList, meshes.bail, "opaque", [0, puckY + 0.68, 0, bailAngle - Math.PI / 2, 0, 0, 1, 1, 1], [0.85, 0.88, 0.90, 1.0], [0,0,0,0], 0, eye, tgt);

    // Side IPX8 USB-C Port at -1.68 u + Red TPU Plug + Animated Engaging USB-C Cable
    const bx = -1.66 * Math.cos(capRotY);
    const bz = 1.66 * Math.sin(capRotY);
    addDraw(opaqueList, meshes.usbBezel, "opaque", [bx, puckY + 0.29, bz, 0, capRotY, 0, 1, 1, 1], [0.60, 0.65, 0.68, 1.0], [0,0,0,0], 0, eye, tgt);
    const px = -1.78 * Math.cos(capRotY);
    const pz = 1.78 * Math.sin(capRotY);
    addDraw(opaqueList, meshes.usbPlug, "opaque", [px, puckY + 0.29 + 0.20 * Math.sin(usbPlugZ), pz, 0, capRotY, usbPlugZ, 1, 1, 1], [0.91, 0.30, 0.24, 1.0], [0,0,0,0], 0, eye, tgt);

    if (stage === 5 || cableProg > 0.01) {
      const cxOff = -1.78 - 3.6 * (1.0 - cableProg) - 0.58;
      addDraw(opaqueList, meshes.cableHead, "opaque", [cxOff, puckY + 0.29, 0, 0, 0, 0, 1, 1, 1], [0.17, 0.24, 0.31, 1.0], [0,0,0,0], 0, eye, tgt);
      addDraw(opaqueList, meshes.cableTip, "opaque", [cxOff + 0.72, puckY + 0.29, 0, 0, 0, 0, 1, 1, 1], [0.75, 0.78, 0.80, 1.0], [0,0,0,0], 0, eye, tgt);
      // rz = -1.15 rad: top end (+2.37, +1.06) seats flush inside rear of cableHead at (cxOff - 0.50, puckY + 0.29)
      addDraw(opaqueList, meshes.cableCord, "opaque", [cxOff - 2.87, puckY - 0.77, 0, 0, 0, -1.15, 1, 1, 1], [0.12, 0.15, 0.18, 1.0], [0,0,0,0], 0, eye, tgt);
    }

    // Stage 4: 3D Android Smartphone + Textured Health Connect Screen + Expanding BLE Waves
    if (phoneVis > 0.5) {
      addDraw(opaqueList, meshes.phoneBody, "opaque", [7.6, 6.8, -0.5, 0, -0.38, 0, 1, 1, 1], [0.12, 0.15, 0.18, 1.0], [0,0,0,0], 0, eye, tgt);
      const sx = 7.6 + 0.21 * Math.sin(-0.38);
      const sz = -0.5 + 0.21 * Math.cos(-0.38);
      addDraw(opaqueList, meshes.phoneScreen, "screen", [sx, 6.8, sz, 0, -0.38, 0, 1, 1, 1], [1, 1, 1, 1], [0,0,0,0], 0, eye, tgt);
      if (blePhase >= 0) {
        for (let w = 0; w < 3; w++) {
          const p = (blePhase + w / 3.0) % 1.0;
          const sc = 0.45 + 1.5 * p;
          const al = Math.sin(p * Math.PI) * 0.85;
          addDraw(glassList, meshes.bleWave, "glass", [2.1 + 4.4 * p, 14.0 - 4.2 * p, -0.3 * p, 0, Math.PI / 2 - 0.3, 0, sc, sc, sc], [0.56, 0.27, 0.68, al], [0.56, 0.27, 0.68, 0.4], 0, eye, tgt);
        }
      }
    }

    frameDrawLists.push({ opaqueList, glassList });
  }
  const wasmMs = Date.now() - tWasm0;
  console.log(`[wasm32] Evaluated ${N_FRAMES} frames & ${slotIdx} MVP matrices in ${wasmMs} ms`);

  // 5. Upload All Uniform Slots Once & Submit All 180 Dawn WebGPU Render Passes
  const tGpu0 = Date.now();
  device.queue.writeBuffer(uniformBuf, 0, uniformCpu, 0, slotIdx * UNIFORM_STRIDE);

  for (let f = 0; f < N_FRAMES; f++) {
    const { opaqueList, glassList } = frameDrawLists[f];
    const enc = device.createCommandEncoder();
    const pass = enc.beginRenderPass({
      colorAttachments: [{
        view: colorView,
        clearValue: { r: 1.0, g: 1.0, b: 1.0, a: 1.0 },
        loadOp: "clear",
        storeOp: "store",
      }],
      depthStencilAttachment: {
        view: depthView,
        depthClearValue: 1.0,
        depthLoadOp: "clear",
        depthStoreOp: "store",
      },
    });

    pass.setPipeline(opaquePipeline);
    for (const d of opaqueList) {
      if (d.pipelineType === "screen") {
        pass.setPipeline(screenPipeline);
        pass.setBindGroup(0, bindGroup0, [d.offsetBytes]);
        pass.setBindGroup(1, bindGroup1);
        pass.setVertexBuffer(0, d.mesh.vbo);
        pass.setIndexBuffer(d.mesh.ibo, "uint32");
        pass.drawIndexed(d.mesh.count);
        pass.setPipeline(opaquePipeline);
      } else {
        pass.setBindGroup(0, bindGroup0, [d.offsetBytes]);
        pass.setVertexBuffer(0, d.mesh.vbo);
        pass.setIndexBuffer(d.mesh.ibo, "uint32");
        pass.drawIndexed(d.mesh.count);
      }
    }

    pass.setPipeline(glassPipeline);
    for (const d of glassList) {
      pass.setBindGroup(0, bindGroup0, [d.offsetBytes]);
      pass.setVertexBuffer(0, d.mesh.vbo);
      pass.setIndexBuffer(d.mesh.ibo, "uint32");
      pass.drawIndexed(d.mesh.count);
    }

    pass.end();
    enc.copyTextureToBuffer(
      { texture: colorTex },
      { buffer: bigReadbackBuf, offset: f * frameBytes, bytesPerRow, rowsPerImage: HEIGHT },
      { width: WIDTH, height: HEIGHT, depthOrArrayLayers: 1 }
    );
    device.queue.submit([enc.finish()]);
  }

  // Single batched mapAsync readback across all 180 GPU frames!
  await bigReadbackBuf.mapAsync(GPUMapMode.READ);
  const mappedU8 = new Uint8Array(bigReadbackBuf.getMappedRange());
  const gpuMs = Date.now() - tGpu0;
  console.log(`[dawn-webgpu] GPU rendered & mapped ${N_FRAMES} frames in ${gpuMs} ms (${((N_FRAMES * 1000) / Math.max(1, gpuMs)).toFixed(1)} fps)`);

  // 6. Composite Stage HUDs, Export Keyframes & Stream to FFmpeg (-threads 3)
  const ffProc = spawn("ffmpeg", [
    "-y", "-threads", "3",
    "-f", "rawvideo", "-pixel_format", "rgba",
    "-video_size", `${WIDTH}x${HEIGHT}`, "-framerate", String(FPS),
    "-i", "pipe:0",
    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "medium", "-crf", "20", "-movflags", "+faststart",
    OUT_MP4,
  ], { stdio: ["pipe", "ignore", "pipe"] });
  let ffErr = "";
  ffProc.stderr.on("data", (d) => { ffErr += d.toString(); });
  const writeFrame = (buf) => new Promise((res, rej) => {
    const ok = ffProc.stdin.write(buf, (err) => (err ? rej(err) : res()));
    if (!ok) ffProc.stdin.once("drain", res);
  });

  const frameBuf = Buffer.alloc(WIDTH * HEIGHT * 4);
  // Save 4 keyframe snapshots for 2x2 verification sheet (Stages 1, 2, 4, 5)
  const kfMap = new Map([
    [Math.round(1.1 * FPS), "/tmp/dawn_kf_1.png"],
    [Math.round(3.8 * FPS), "/tmp/dawn_kf_2.png"],
    [Math.round(8.6 * FPS), "/tmp/dawn_kf_3.png"],
    [Math.round(11.6 * FPS), "/tmp/dawn_kf_4.png"],
  ]);

  for (let f = 0; f < N_FRAMES; f++) {
    const fStart = f * frameBytes;
    if (bytesPerRow === bytesPerRowUnaligned) {
      frameBuf.set(mappedU8.subarray(fStart, fStart + bytesPerRowUnaligned * HEIGHT));
    } else {
      for (let y = 0; y < HEIGHT; y++) {
        frameBuf.set(
          mappedU8.subarray(fStart + y * bytesPerRow, fStart + y * bytesPerRow + bytesPerRowUnaligned),
          y * bytesPerRowUnaligned
        );
      }
    }
    alphaCompositeInPlace(frameBuf, hudLayers[frameStages[f]]);
    if (kfMap.has(f)) writeRgbaPng(kfMap.get(f), frameBuf, WIDTH, HEIGHT);
    await writeFrame(frameBuf);
  }
  bigReadbackBuf.unmap();
  ffProc.stdin.end();
  await new Promise((res, rej) => ffProc.on("close", (c) => (c === 0 ? res() : rej(new Error(ffErr)))));

  // Build 2x2 Dawn WebGPU Keyframe Sheet via ffmpeg xstack
  const xs = spawnSync("ffmpeg", [
    "-y", "-threads", "3",
    "-i", "/tmp/dawn_kf_1.png", "-i", "/tmp/dawn_kf_2.png",
    "-i", "/tmp/dawn_kf_3.png", "-i", "/tmp/dawn_kf_4.png",
    "-filter_complex", "[0:v][1:v]hstack=inputs=2[top];[2:v][3:v]hstack=inputs=2[bot];[top][bot]vstack=inputs=2",
    OUT_KF_SHEET,
  ], { encoding: "utf8" });
  for (const p of kfMap.values()) fs.rmSync(p, { force: true });
  if (xs.status !== 0) throw new Error(`ffmpeg keyframe sheet failed: ${xs.stderr}`);

  // Encode GIF strictly < 1.8 MiB
  let gifSize = encodeGifFromMp4(OUT_MP4, OUT_GIF, 720, 12, 128);
  if (gifSize > MAX_GIF_BYTES) gifSize = encodeGifFromMp4(OUT_MP4, OUT_GIF, 640, 10, 96);
  if (gifSize > MAX_GIF_BYTES) gifSize = encodeGifFromMp4(OUT_MP4, OUT_GIF, 600, 10, 80);

  console.log(`[done] MP4 : ${OUT_MP4} (${(fs.statSync(OUT_MP4).size / 1024).toFixed(1)} KiB)`);
  console.log(`[done] GIF : ${OUT_GIF} (${(gifSize / 1024).toFixed(1)} KiB)`);
  console.log(`[done] KF  : ${OUT_KF_SHEET} (${(fs.statSync(OUT_KF_SHEET).size / 1024).toFixed(1)} KiB)`);
}

main().catch((err) => {
  console.error("FATAL:", err);
  process.exit(1);
});
