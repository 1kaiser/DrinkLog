import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';

export const DURATION_SEC = 12.0;

const urlParams = new URLSearchParams(window.location.search);
const IS_HEADLESS = urlParams.get('headless') === '1';
if (IS_HEADLESS) {
  document.body.classList.add('headless');
}

const canvas = document.getElementById('viewport');
const renderer = new THREE.WebGLRenderer({
  canvas,
  antialias: true,
  alpha: true,
  preserveDrawingBuffer: true,
});
renderer.setPixelRatio(IS_HEADLESS ? 1 : Math.min(window.devicePixelRatio, 2));
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setClearColor(0xffffff, 0.0); // Transparent over #FFFFFF CSS studio background
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.08;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;

const scene = new THREE.Scene();
const pmrem = new THREE.PMREMGenerator(renderer);
scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;

const camera = new THREE.PerspectiveCamera(36, window.innerWidth / window.innerHeight, 0.2, 200);
camera.position.set(16.5, 19.5, 22.0);

const controls = new OrbitControls(camera, canvas);
controls.enableDamping = true;
controls.dampingFactor = 0.07;
controls.target.set(0.8, 8.8, 0.0);

// Studio 3-point lighting + subtle soft floor shadow catcher
const keyLight = new THREE.DirectionalLight(0xfff9f0, 2.2);
keyLight.position.set(14, 28, 16);
keyLight.castShadow = true;
keyLight.shadow.mapSize.set(1024, 1024);
keyLight.shadow.camera.near = 4;
keyLight.shadow.camera.far = 65;
keyLight.shadow.camera.left = -16;
keyLight.shadow.camera.right = 16;
keyLight.shadow.camera.top = 24;
keyLight.shadow.camera.bottom = -12;
keyLight.shadow.bias = -0.0005;
scene.add(keyLight);

const fillLight = new THREE.DirectionalLight(0xdbeeff, 0.9);
fillLight.position.set(-18, 14, -10);
scene.add(fillLight);

const rimLight = new THREE.DirectionalLight(0xffffff, 0.8);
rimLight.position.set(0, 18, -22);
scene.add(rimLight);

const floor = new THREE.Mesh(
  new THREE.CircleGeometry(30, 64),
  new THREE.ShadowMaterial({ opacity: 0.14 })
);
floor.rotation.x = -Math.PI / 2;
floor.receiveShadow = true;
scene.add(floor);

// ---------------------------------------------------------------------------
// Materials
// ---------------------------------------------------------------------------
const matBottleGlass = new THREE.MeshPhysicalMaterial({
  color: 0x99d1f4,
  roughness: 0.10,
  metalness: 0.08,
  transparent: true,
  opacity: 0.44,
  depthWrite: false,
  clearcoat: 1.0,
  clearcoatRoughness: 0.08,
});
const matWater = new THREE.MeshPhysicalMaterial({
  color: 0x2e86de,
  roughness: 0.12,
  metalness: 0.02,
  transparent: true,
  opacity: 0.72,
  clearcoat: 0.8,
});
const matCollar = new THREE.MeshStandardMaterial({ color: 0x2c3e50, roughness: 0.45, metalness: 0.25 });
const matJaw = new THREE.MeshStandardMaterial({ color: 0x1e272e, roughness: 0.42, metalness: 0.30 });
const matSilicone = new THREE.MeshStandardMaterial({ color: 0xe67e22, roughness: 0.78, metalness: 0.02 });
const matHub = new THREE.MeshStandardMaterial({ color: 0x5d6d7e, roughness: 0.40, metalness: 0.35 });
const matFlexure = new THREE.MeshStandardMaterial({
  color: 0xd0d7de,
  roughness: 0.22,
  metalness: 0.88,
  emissive: new THREE.Color(0xf39c12),
  emissiveIntensity: 0.0,
});
const matGold = new THREE.MeshStandardMaterial({ color: 0xf1c40f, roughness: 0.25, metalness: 0.90 });
const matPuckShell = new THREE.MeshStandardMaterial({
  color: 0x1b6ca8,
  roughness: 0.30,
  metalness: 0.20,
  transparent: true,
  opacity: 0.86,
});
const matLid = new THREE.MeshStandardMaterial({ color: 0x2980b9, roughness: 0.28, metalness: 0.18 });
const matBail = new THREE.MeshStandardMaterial({ color: 0xd5dbdb, roughness: 0.22, metalness: 0.92 });
const matPcb = new THREE.MeshStandardMaterial({ color: 0x0e6251, roughness: 0.45, metalness: 0.15 });
const matLipo = new THREE.MeshStandardMaterial({ color: 0xf39c12, roughness: 0.35, metalness: 0.40 });
const matRedTpu = new THREE.MeshStandardMaterial({ color: 0xe74c3c, roughness: 0.65, metalness: 0.05 });
const matUsbMetal = new THREE.MeshStandardMaterial({ color: 0x95a5a6, roughness: 0.25, metalness: 0.92 });
const matLed = new THREE.MeshStandardMaterial({
  color: 0x27ae60,
  emissive: new THREE.Color(0x27ae60),
  emissiveIntensity: 1.5,
  roughness: 0.2,
});

// ---------------------------------------------------------------------------
// 1. Bottle + Animated Water Column + Screw Cap (1 unit = 10 mm)
// ---------------------------------------------------------------------------
const bottleGroup = new THREE.Group();
scene.add(bottleGroup);

// Lathe bottle profile (Ø64 mm body -> shoulder -> Ø29 mm neck)
const bottlePts = [
  new THREE.Vector2(0.01, 0.0),
  new THREE.Vector2(3.05, 0.0),
  new THREE.Vector2(3.20, 0.35),
  new THREE.Vector2(3.20, 9.8),
  new THREE.Vector2(3.05, 10.6),
  new THREE.Vector2(1.48, 12.2),
  new THREE.Vector2(1.48, 13.7),
];
const bottleMesh = new THREE.Mesh(new THREE.LatheGeometry(bottlePts, 56), matBottleGlass);
bottleMesh.castShadow = true;
bottleGroup.add(bottleMesh);

// Solid base plinth shadow disc inside bottle bottom
const bottleBase = new THREE.Mesh(
  new THREE.CylinderGeometry(3.05, 3.05, 0.22, 48),
  new THREE.MeshStandardMaterial({ color: 0xb0d4ee, roughness: 0.2, transparent: true, opacity: 0.65 })
);
bottleBase.position.y = 0.11;
bottleBase.castShadow = true;
bottleGroup.add(bottleBase);

// Animated Water Cylinder + Meniscus
const waterHeightMax = 9.5;
const waterCyl = new THREE.Mesh(new THREE.CylinderGeometry(2.98, 2.98, 1.0, 48), matWater);
bottleGroup.add(waterCyl);

const waterMeniscus = new THREE.Mesh(
  new THREE.TorusGeometry(2.95, 0.07, 12, 48),
  new THREE.MeshPhysicalMaterial({ color: 0x85c1e9, roughness: 0.1, transparent: true, opacity: 0.85 })
);
waterMeniscus.rotation.x = Math.PI / 2;
bottleGroup.add(waterMeniscus);

// Bottle Screw Cap Group (separates in Stage 3 unscrew) — standard 30.5 mm PET cap
const screwCapGroup = new THREE.Group();
screwCapGroup.position.y = 13.65;
bottleGroup.add(screwCapGroup);

const capCyl = new THREE.Mesh(
  new THREE.CylinderGeometry(1.525, 1.525, 1.35, 48),
  new THREE.MeshStandardMaterial({ color: 0x485460, roughness: 0.45, metalness: 0.2 })
);
capCyl.position.y = 0.675;
capCyl.castShadow = true;
screwCapGroup.add(capCyl);

// ---------------------------------------------------------------------------
// 2. DrinkLog 1.1x D_cap Proportioned Puck Assembly (33.6 mm on 30.5 mm cap)
// ---------------------------------------------------------------------------
const drinkLogGroup = new THREE.Group();
scene.add(drinkLogGroup);

const scrollCollarGroup = new THREE.Group();
drinkLogGroup.add(scrollCollarGroup);

const collarRing = new THREE.Mesh(new THREE.CylinderGeometry(1.68, 1.68, 0.54, 64, 1, true), matCollar);
collarRing.position.y = 0.27;
collarRing.castShadow = true;
scrollCollarGroup.add(collarRing);

const collarInnerWall = new THREE.Mesh(new THREE.CylinderGeometry(1.55, 1.55, 0.54, 64, 1, true), matCollar);
collarInnerWall.material = matCollar.clone();
collarInnerWall.material.side = THREE.BackSide;
collarInnerWall.position.y = 0.27;
scrollCollarGroup.add(collarInnerWall);

const collarTopRing = new THREE.Mesh(new THREE.RingGeometry(1.55, 1.68, 64), matCollar);
collarTopRing.rotation.x = -Math.PI / 2;
collarTopRing.position.y = 0.54;
scrollCollarGroup.add(collarTopRing);

for (let i = 0; i < 36; i++) {
  const ang = (i / 36) * Math.PI * 2;
  const rib = new THREE.Mesh(new THREE.BoxGeometry(0.06, 0.46, 0.12), matCollar);
  rib.position.set(1.68 * Math.cos(ang), 0.27, 1.68 * Math.sin(ang));
  rib.rotation.y = -ang;
  scrollCollarGroup.add(rib);
}

// 6 Compliant Split Collet Petals (Orange TPU / Shore 50A)
const jawPivots = [];
for (let k = 0; k < 6; k++) {
  const arm = new THREE.Group();
  arm.rotation.y = (k * 2 * Math.PI) / 6;
  const slider = new THREE.Group();
  const silPad = new THREE.Mesh(new THREE.BoxGeometry(0.14, 0.42, 0.65), matSilicone);
  silPad.position.set(0.0, 0.27, 0);
  slider.add(silPad);
  arm.add(slider);
  drinkLogGroup.add(arm);
  jawPivots.push(slider);
}

const hubPlate = new THREE.Mesh(new THREE.CylinderGeometry(1.60, 1.60, 0.18, 64), matHub);
hubPlate.position.y = 0.63;
hubPlate.castShadow = true;
drinkLogGroup.add(hubPlate);

// Universal Ø30.0 mm x 0.8 mm 3-Spoke Stainless Flexure + Gold Strain Gauges
const flexureGroup = new THREE.Group();
flexureGroup.position.y = 0.78;
drinkLogGroup.add(flexureGroup);

const flexOuter = new THREE.Mesh(new THREE.TorusGeometry(1.44, 0.10, 12, 64), matFlexure);
flexOuter.rotation.x = Math.PI / 2;
flexureGroup.add(flexOuter);

const flexInner = new THREE.Mesh(new THREE.CylinderGeometry(0.55, 0.55, 0.09, 48), matFlexure);
flexureGroup.add(flexInner);

for (let k = 0; k < 3; k++) {
  const spokeG = new THREE.Group();
  spokeG.rotation.y = (k * 2 * Math.PI) / 3;
  const spoke = new THREE.Mesh(new THREE.BoxGeometry(0.85, 0.09, 0.42), matFlexure);
  spoke.position.x = 0.92;
  spokeG.add(spoke);
  if (k < 2) {
    const sg = new THREE.Mesh(new THREE.BoxGeometry(0.42, 0.11, 0.28), matGold);
    sg.position.x = 0.92;
    spokeG.add(sg);
  }
  flexureGroup.add(spokeG);
}

// Upper Electronics Puck Group (1.1x D_cap outer shell around Ø28.0 mm PCB Core)
const upperPuckGroup = new THREE.Group();
upperPuckGroup.position.y = 0.88;
drinkLogGroup.add(upperPuckGroup);

const puckShell = new THREE.Mesh(new THREE.CylinderGeometry(1.68, 1.68, 0.58, 64), matPuckShell);
puckShell.position.y = 0.29;
puckShell.castShadow = true;
upperPuckGroup.add(puckShell);

const lipoMesh = new THREE.Mesh(new THREE.BoxGeometry(1.8, 0.32, 1.4), matLipo);
lipoMesh.position.y = 0.22;
upperPuckGroup.add(lipoMesh);

const pcbMesh = new THREE.Mesh(new THREE.CylinderGeometry(1.40, 1.40, 0.09, 48), matPcb);
pcbMesh.position.y = 0.44;
upperPuckGroup.add(pcbMesh);

const mcuShield = new THREE.Mesh(
  new THREE.BoxGeometry(0.95, 0.12, 1.25),
  new THREE.MeshStandardMaterial({ color: 0xbdc3c7, roughness: 0.25, metalness: 0.9 })
);
mcuShield.position.set(0.0, 0.53, -0.15);
upperPuckGroup.add(mcuShield);

const topLidGroup = new THREE.Group();
topLidGroup.position.y = 0.58;
upperPuckGroup.add(topLidGroup);

const lidDisc = new THREE.Mesh(new THREE.CylinderGeometry(1.56, 1.66, 0.20, 64), matLid);
lidDisc.position.y = 0.10;
lidDisc.castShadow = true;
topLidGroup.add(lidDisc);

const statusLed = new THREE.Mesh(new THREE.SphereGeometry(0.11, 16, 12), matLed);
statusLed.position.set(1.05, 0.22, 0.55);
topLidGroup.add(statusLed);

const bailPivot = new THREE.Group();
bailPivot.position.set(0, 0.68, 0);
upperPuckGroup.add(bailPivot);

const bailArc = new THREE.Mesh(new THREE.TorusGeometry(1.64, 0.09, 14, 56, Math.PI), matBail);
bailArc.rotation.x = -Math.PI / 2;
bailArc.castShadow = true;
bailPivot.add(bailArc);

// Side IPX8 USB-C Port Bezel (-X side at x = -1.66), Captive Red TPU Plug, & Cable
const usbBezel = new THREE.Mesh(new THREE.BoxGeometry(0.28, 0.28, 0.88), matUsbMetal);
usbBezel.position.set(-1.66, 0.29, 0.0);
upperPuckGroup.add(usbBezel);

const usbVoid = new THREE.Mesh(
  new THREE.BoxGeometry(0.30, 0.18, 0.68),
  new THREE.MeshBasicMaterial({ color: 0x111111 })
);
usbVoid.position.set(-1.68, 0.29, 0.0);
upperPuckGroup.add(usbVoid);

const usbPlugPivot = new THREE.Group();
usbPlugPivot.position.set(-1.78, 0.12, 0.0);
upperPuckGroup.add(usbPlugPivot);

const usbPlugMesh = new THREE.Mesh(new THREE.BoxGeometry(0.22, 0.30, 0.86), matRedTpu);
usbPlugMesh.position.set(0.0, 0.17, 0.0);
usbPlugPivot.add(usbPlugMesh);

// Animated USB-C Cable Assembly (world space relative to cap side in Stage 5)
const usbCableGroup = new THREE.Group();
scene.add(usbCableGroup);

const cablePlugHead = new THREE.Mesh(
  new THREE.BoxGeometry(1.15, 0.32, 0.88),
  new THREE.MeshStandardMaterial({ color: 0x2c3e50, roughness: 0.4, metalness: 0.25 })
);
cablePlugHead.castShadow = true;
usbCableGroup.add(cablePlugHead);

const cableUsbTip = new THREE.Mesh(new THREE.BoxGeometry(0.55, 0.18, 0.68), matUsbMetal);
cableUsbTip.position.x = 0.82;
usbCableGroup.add(cableUsbTip);

const cableCurve = new THREE.CatmullRomCurve3([
  new THREE.Vector3(-0.55, 0, 0),
  new THREE.Vector3(-2.6, -0.35, 0.3),
  new THREE.Vector3(-5.5, -2.0, 0.8),
  new THREE.Vector3(-9.0, -5.2, 1.4),
]);
const cableCord = new THREE.Mesh(
  new THREE.TubeGeometry(cableCurve, 24, 0.13, 12, false),
  new THREE.MeshStandardMaterial({ color: 0x1e272e, roughness: 0.6 })
);
usbCableGroup.add(cableCord);

// ---------------------------------------------------------------------------
// 3. Animated BLE Waves + 3D Android Smartphone w/ Live Health Connect Texture
// ---------------------------------------------------------------------------
const phoneGroup = new THREE.Group();
phoneGroup.position.set(8.2, 7.2, -0.6);
phoneGroup.rotation.y = -0.38;
scene.add(phoneGroup);

const phoneBody = new THREE.Mesh(
  new THREE.BoxGeometry(4.4, 8.8, 0.42),
  new THREE.MeshStandardMaterial({ color: 0x1e272e, roughness: 0.25, metalness: 0.8 })
);
phoneBody.castShadow = true;
phoneGroup.add(phoneBody);

const phoneCanvas = document.createElement('canvas');
phoneCanvas.width = 256;
phoneCanvas.height = 512;
const phoneCtx = phoneCanvas.getContext('2d');
const phoneTex = new THREE.CanvasTexture(phoneCanvas);
phoneTex.colorSpace = THREE.SRGBColorSpace;

const phoneScreen = new THREE.Mesh(
  new THREE.PlaneGeometry(3.96, 8.20),
  new THREE.MeshBasicMaterial({ map: phoneTex })
);
phoneScreen.position.z = 0.22;
phoneGroup.add(phoneScreen);

let lastScreenState = '';
function drawPhoneScreen(loggedMl, synced) {
  const key = `${loggedMl}_${synced}`;
  if (key === lastScreenState) return;
  lastScreenState = key;

  const ctx = phoneCtx;
  ctx.fillStyle = '#f8f9fa';
  ctx.fillRect(0, 0, 256, 512);

  // Header bar
  ctx.fillStyle = '#1b4f72';
  ctx.fillRect(0, 0, 256, 84);
  ctx.fillStyle = '#ffffff';
  ctx.font = 'bold 20px sans-serif';
  ctx.textAlign = 'center';
  ctx.fillText('Health Connect', 128, 38);
  ctx.font = '13px sans-serif';
  ctx.fillStyle = '#aed6f1';
  ctx.fillText('HydrationRecord Sync', 128, 62);

  // Main Hydration Ring Card
  ctx.fillStyle = '#ffffff';
  ctx.strokeStyle = synced ? '#27ae60' : '#d0d7de';
  ctx.lineWidth = 4;
  ctx.beginPath();
  ctx.roundRect(22, 114, 212, 220, 18);
  ctx.fill();
  ctx.stroke();

  ctx.fillStyle = synced ? '#1e8449' : '#2c3e50';
  ctx.font = 'bold 46px sans-serif';
  ctx.fillText(`+${loggedMl} mL`, 128, 206);

  ctx.font = 'bold 16px sans-serif';
  ctx.fillStyle = synced ? '#27ae60' : '#7f8c8d';
  ctx.fillText(synced ? 'ACK Verified ✓' : 'Waiting for BLE...', 128, 252);

  ctx.font = '13px monospace';
  ctx.fillStyle = '#566573';
  ctx.fillText('1180 g -> 970 g', 128, 294);

  // Footer badge
  ctx.fillStyle = '#ebf5fb';
  ctx.fillRect(22, 368, 212, 92);
  ctx.fillStyle = '#154360';
  ctx.font = 'bold 14px sans-serif';
  ctx.fillText('DrinkLog GATT 0002', 128, 405);
  ctx.font = '12px sans-serif';
  ctx.fillStyle = '#2980b9';
  ctx.fillText('Idempotent Seq #002', 128, 430);

  phoneTex.needsUpdate = true;
}

// BLE Signal Rings
const bleWaves = [];
for (let i = 0; i < 3; i++) {
  const wave = new THREE.Mesh(
    new THREE.TorusGeometry(1.0, 0.06, 10, 40),
    new THREE.MeshBasicMaterial({ color: 0x8e44ad, transparent: true, opacity: 0.0 })
  );
  scene.add(wave);
  bleWaves.push(wave);
}

// ---------------------------------------------------------------------------
// Analytical Timeline Engine (Deterministic & Scrubbable)
// ---------------------------------------------------------------------------
function ease(x) {
  const t = Math.max(0, Math.min(1, x));
  return t * t * (3 - 2 * t);
}

const elStageBadge = document.getElementById('stage-badge');
const elStageHeading = document.getElementById('stage-heading');
const elStageDesc = document.getElementById('stage-desc');
const elValMass = document.getElementById('val-mass');
const elValHc = document.getElementById('val-hc');
const elPowerPill = document.getElementById('power-pill');
const elScrubTime = document.getElementById('scrub-time');
const elChkExplode = document.getElementById('chk-explode');
const elSelTier = document.getElementById('sel-tier');

const TIER_SCALE_FACTORS = {
  pet_30: 1.00,   // 30.5 -> 33.6 mm
  sport_40: 1.34, // 41.0 -> 45.1 mm
  flask_48: 1.57, // 48.0 -> 52.8 mm
  wide_63: 2.06,  // 63.0 -> 69.3 mm
};

let currentTime = 0.0;
let playing = !IS_HEADLESS;
let userExplode = false;
let tierScale = 1.00;
let userControllingCamera = false;

controls.addEventListener('start', () => { userControllingCamera = true; });

function applyState(tSec) {
  const t = ((tSec % DURATION_SEC) + DURATION_SEC) % DURATION_SEC;

  let stage = 1;
  let jawDiaMm = 30.5;
  let capDropY = 0;
  let capRotY = 0;
  let bottleLiftY = 0;
  let bailAngle = 0;
  let flexStrain = 0;
  let waterFrac = 0.85;
  let massG = 0;
  let hcMl = 0;
  let synced = false;
  let powerText = 'POWER: SLEEP 6.4 uA';
  let powerColor = '#16a085';
  let ledColor = 0x2ecc71;
  let ledInt = 0.4;
  let usbPlugAngle = 0;
  let cableOffset = 0;
  let blePhase = -1;
  let phoneAlpha = 0.0;
  let camPos = new THREE.Vector3(12.8, 19.0, 24.5);
  let camTarget = new THREE.Vector3(0.0, 10.6, 0.0);
  let stageHead = '';
  let stageSub = '';

  if (t < 2.6) {
    stage = 1;
    const u = ease(t / 2.6);
    jawDiaMm = 34.0 - 3.5 * u;
    capDropY = 3.2 * (1.0 - u);
    capRotY = 0.85 * (1.0 - u);
    stageHead = '1.1x Cap Gripper (33.6 mm Shell)';
    stageSub = 'Compliant split collet locks onto 30.5 mm PET cap around universal Ø28 mm PCB core.';
    camPos.set(12.8 - 0.8 * u, 18.5 + 0.8 * u, 24.0);
    camTarget.set(0.0, 11.0, 0.0);
    ledColor = 0x3498db;
    ledInt = 0.5;
  } else if (t < 5.2) {
    stage = 2;
    const u = ease((t - 2.6) / 2.6);
    bailAngle = (Math.PI / 2) * Math.min(1, u * 1.9);
    const liftBell = Math.sin(Math.min(1, Math.max(0, (u - 0.22) / 0.78)) * Math.PI);
    bottleLiftY = 2.4 * liftBell;
    flexStrain = liftBell;
    massG = liftBell > 0.15 ? 1180 : (u > 0.6 ? 1180 : 0);
    powerText = liftBell > 0.15 ? 'POWER: WEIGH 4.0 mA' : 'POWER: SLEEP 6.4 uA';
    powerColor = liftBell > 0.15 ? '#d4ac0d' : '#16a085';
    ledColor = 0x27ae60;
    ledInt = liftBell > 0.2 ? 2.2 : 0.6;
    stageHead = 'Bail-Lift Baseline Weighing';
    stageSub = 'Slim folding bail routes 100% weight via Ø30 mm 3-spoke flexure (m = Fz / az).';
    camPos.set(13.5, 19.5, 26.5);
    camTarget.set(0.0, 10.8, 0.0);
  } else if (t < 7.4) {
    stage = 3;
    const u = ease((t - 5.2) / 2.2);
    const unscrewArc = Math.sin(u * Math.PI);
    capDropY = 2.8 * unscrewArc;
    capRotY = Math.PI * 2.0 * u;
    waterFrac = 0.85 - 0.24 * Math.min(1, Math.max(0, (u - 0.22) / 0.55));
    massG = 0;
    powerText = 'POWER: AUTO-TARE 0 g';
    powerColor = '#2980b9';
    ledColor = 0x00bcd4;
    ledInt = 1.6;
    stageHead = 'Cap-Off Auto-Tare & Sip (-210 mL)';
    stageSub = 'Unscrewed cap updates zero-offset EMA (0.8 old + 0.2 raw), cancelling thermal drift.';
    camPos.set(13.0, 19.0, 24.5);
    camTarget.set(0.0, 10.2, 0.0);
  } else if (t < 9.8) {
    stage = 4;
    const u = ease((t - 7.4) / 2.4);
    bailAngle = Math.PI / 2;
    const liftBell = Math.sin(Math.min(1, u * 1.1) * Math.PI);
    bottleLiftY = 2.2 * liftBell;
    flexStrain = 0.82 * liftBell;
    waterFrac = 0.61;
    massG = 970;
    synced = u > 0.35;
    hcMl = synced ? 210 : 0;
    blePhase = (u * 2.0) % 1.0;
    phoneAlpha = 1.0;
    powerText = 'POWER: BLE SYNC 8 mA';
    powerColor = '#8e44ad';
    ledColor = 0x27ae60;
    ledInt = 2.0;
    stageHead = 'BLE Sync to Google Health Connect';
    stageSub = '1180 g -> 970 g (+210 mL) pushed via GATT 0002; ring clears only after Health Connect ACK.';
    camPos.set(12.5, 18.8, 29.0);
    camTarget.set(2.2, 10.2, 0.0);
  } else {
    stage = 5;
    const u = ease((t - 9.8) / 2.2);
    waterFrac = 0.61;
    massG = 970;
    hcMl = 210;
    synced = true;
    usbPlugAngle = -2.0 * Math.min(1, u * 2.0);
    cableOffset = Math.max(0, (u - 0.25) / 0.75);
    powerText = 'POWER: USB-C 5V + DEBUG';
    powerColor = '#c0392b';
    ledColor = cableOffset > 0.6 ? 0xe74c3c : 0x27ae60;
    ledInt = 2.2;
    stageHead = 'IP67 USB-C Charge & Native Debug';
    stageSub = 'Captive TPU plug opens to reveal IPX8 USB-C (BQ25180 5V + nRF52840 CDC/DFU CLI).';
    camPos.set(-10.5, 17.5, 11.5);
    camTarget.set(-1.1, 14.8, 0.0);
  }

  // Apply bottle & cap transforms
  bottleGroup.position.y = bottleLiftY;
  const hWater = waterHeightMax * waterFrac;
  waterCyl.scale.y = hWater;
  waterCyl.position.y = 0.22 + hWater / 2.0;
  waterMeniscus.position.y = 0.22 + hWater;

  // Unscrewed cap lifts screwCapGroup + DrinkLog together in Stage 3
  const capLiftOffset = stage === 3 ? capDropY : 0.0;
  screwCapGroup.position.y = 13.65 + capLiftOffset;
  screwCapGroup.rotation.y = capRotY;
  screwCapGroup.scale.set(tierScale, 1.0, tierScale);

  const capY = bottleLiftY + 14.35 + (stage === 1 ? capDropY : capLiftOffset);
  drinkLogGroup.position.y = capY;
  drinkLogGroup.rotation.y = capRotY;

  // Scale outer shell cleanly to selected 1.1x tier while keeping universal Ø28/Ø30 mm core fixed
  scrollCollarGroup.scale.set(tierScale, 1.0, tierScale);
  puckShell.scale.set(tierScale, 1.0, tierScale);
  topLidGroup.scale.set(tierScale, 1.0, tierScale);
  scrollCollarGroup.rotation.y = (jawDiaMm - 30.5) * 0.10;
  const jawRadius = ((jawDiaMm / 10.0) * 0.5) * tierScale;
  for (const s of jawPivots) {
    s.position.x = jawRadius;
  }

  const exp = userExplode ? 2.4 : 0.0;
  hubPlate.position.y = 0.63 + 0.4 * exp;
  flexureGroup.position.y = 0.78 + 1.0 * exp - 0.05 * flexStrain;
  matFlexure.emissiveIntensity = 0.9 * flexStrain;
  upperPuckGroup.position.y = 0.88 + 2.0 * exp + 0.05 * flexStrain;
  topLidGroup.position.y = 0.58 + 0.9 * exp;
  bailPivot.rotation.x = bailAngle;

  matLed.color.setHex(ledColor);
  matLed.emissive.setHex(ledColor);
  matLed.emissiveIntensity = ledInt;

  usbPlugPivot.rotation.z = usbPlugAngle;
  const portWorldX = -1.78 * tierScale;
  const portWorldY = capY + upperPuckGroup.position.y + 0.29;
  usbCableGroup.visible = stage === 5 || cableOffset > 0.01;
  usbCableGroup.position.set(portWorldX - 3.6 * (1.0 - cableOffset) - 0.58, portWorldY, 0.0);

  // Android Phone + BLE Waves (Stage 4)
  phoneGroup.visible = phoneAlpha > 0.05;
  drawPhoneScreen(hcMl, synced);
  for (let i = 0; i < bleWaves.length; i++) {
    const w = bleWaves[i];
    if (blePhase >= 0) {
      const p = (blePhase + i / bleWaves.length) % 1.0;
      w.visible = true;
      w.position.set(3.2 + 4.0 * p, 14.0 - 4.0 * p, -0.3 * p);
      w.rotation.y = Math.PI / 2 - 0.3;
      w.scale.setScalar(0.5 + 1.8 * p);
      w.material.opacity = Math.sin(p * Math.PI) * 0.85;
    } else {
      w.visible = false;
    }
  }

  // Camera framing (automatic during headless/playback unless user grabbed OrbitControls)
  if (!userControllingCamera || IS_HEADLESS) {
    camera.position.copy(camPos);
    controls.target.copy(camTarget);
    controls.update();
  }

  // Update DOM HUD
  elStageBadge.textContent = `Stage ${stage}/5`;
  elStageHeading.textContent = stageHead;
  elStageDesc.textContent = stageSub;
  elValMass.textContent = `${massG} g`;
  elValHc.textContent = `+${hcMl} mL`;
  elPowerPill.textContent = powerText;
  elPowerPill.style.background = powerColor;
  if (!IS_HEADLESS) elScrubTime.value = t.toFixed(2);
}

window.__DURATION_SEC = DURATION_SEC;
window.__seekAndRender = (tSec) => {
  currentTime = tSec;
  applyState(tSec);
  renderer.render(scene, camera);
};
window.__rendererInfo = () => {
  const gl = renderer.getContext();
  const dbg = gl.getExtension('WEBGL_debug_renderer_info');
  return {
    vendor: dbg ? gl.getParameter(dbg.UNMASKED_VENDOR_WEBGL) : 'unknown',
    renderer: dbg ? gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL) : 'unknown',
    triangles: renderer.info.render.triangles,
  };
};

// Interactive UI bindings
document.getElementById('btn-play')?.addEventListener('click', (e) => {
  playing = !playing;
  e.target.textContent = playing ? 'Pause' : 'Play';
  e.target.classList.toggle('active', playing);
});
document.querySelectorAll('.btn-stage').forEach((btn) => {
  btn.addEventListener('click', () => {
    userControllingCamera = false;
    currentTime = Number(btn.dataset.t);
    applyState(currentTime);
  });
});
elScrubTime?.addEventListener('input', () => {
  playing = false;
  document.getElementById('btn-play').textContent = 'Play';
  document.getElementById('btn-play').classList.remove('active');
  currentTime = Number(elScrubTime.value);
  applyState(currentTime);
});
elChkExplode?.addEventListener('change', () => {
  userExplode = elChkExplode.checked;
  applyState(currentTime);
});
elSelTier?.addEventListener('change', () => {
  tierScale = TIER_SCALE_FACTORS[elSelTier.value] || 1.0;
  applyState(currentTime);
});

window.addEventListener('resize', () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.render(scene, camera);
});

// Initial render + Ready flag
applyState(0.0);
renderer.render(scene, camera);
window.__sceneReady = true;

if (!IS_HEADLESS) {
  let lastMs = performance.now();
  function animate(nowMs) {
    const dt = Math.min(0.05, (nowMs - lastMs) / 1000.0);
    lastMs = nowMs;
    if (playing) {
      currentTime = (currentTime + dt) % DURATION_SEC;
      applyState(currentTime);
    } else {
      controls.update();
    }
    renderer.render(scene, camera);
    requestAnimationFrame(animate);
  }
  requestAnimationFrame(animate);
}
