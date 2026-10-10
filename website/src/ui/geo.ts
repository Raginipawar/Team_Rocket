// Calibrates the demo's abstract 0-800 schematic plane onto real Pune / Pimpri
// Chinchwad geography, so the animated routes sit on an actual street map instead
// of a drawn grid. Control points: real-world locality coordinates matched against
// the abstract (x, y) position the old schematic map used for the same locality.
type Pt = [number, number];

const CONTROL: { xy: Pt; lnglat: Pt }[] = [
  { xy: [40, 80], lnglat: [73.7503, 18.6698] }, // Dehu Road
  { xy: [160, 115], lnglat: [73.7638, 18.6529] }, // Nigdi
  { xy: [250, 265], lnglat: [73.7698, 18.6468] }, // Akurdi
  { xy: [470, 215], lnglat: [73.7997, 18.6298] }, // Chinchwad
  { xy: [590, 350], lnglat: [73.8009, 18.6279] }, // Pimpri
  { xy: [690, 145], lnglat: [73.842, 18.6228] }, // Bhosari
  { xy: [110, 365], lnglat: [73.7466, 18.645] }, // Ravet
  { xy: [400, 580], lnglat: [73.7651, 18.5986] }, // Wakad
];

// Least squares fit of [lng, lat] = a*x + b*y + c (solved independently per axis
// via the normal equations, 3x3 Gaussian elimination).
function fitAxis(target: number[]): [number, number, number] {
  // columns: x, y, 1
  const rows = CONTROL.map(({ xy: [x, y] }) => [x, y, 1]);
  const n = rows.length;
  // A^T A (3x3) and A^T b (3x1)
  const AtA = [
    [0, 0, 0],
    [0, 0, 0],
    [0, 0, 0],
  ];
  const Atb = [0, 0, 0];
  for (let i = 0; i < n; i++) {
    const r = rows[i];
    for (let a = 0; a < 3; a++) {
      Atb[a] += r[a] * target[i];
      for (let b = 0; b < 3; b++) AtA[a][b] += r[a] * r[b];
    }
  }
  // Gaussian elimination on [AtA | Atb]
  const m = AtA.map((row, i) => [...row, Atb[i]]);
  for (let col = 0; col < 3; col++) {
    let piv = col;
    for (let r = col + 1; r < 3; r++) if (Math.abs(m[r][col]) > Math.abs(m[piv][col])) piv = r;
    [m[col], m[piv]] = [m[piv], m[col]];
    for (let r = 0; r < 3; r++) {
      if (r === col) continue;
      const f = m[r][col] / m[col][col];
      for (let c = col; c < 4; c++) m[r][c] -= f * m[col][c];
    }
  }
  return [m[0][3] / m[0][0], m[1][3] / m[1][1], m[2][3] / m[2][2]];
}

const [a, b, c] = fitAxis(CONTROL.map((p) => p.lnglat[0]));
const [d, e, f] = fitAxis(CONTROL.map((p) => p.lnglat[1]));

/** Converts an abstract demo-plane (x, y) position to a real [lng, lat]. */
export function toLngLat([x, y]: Pt): Pt {
  return [a * x + b * y + c, d * x + e * y + f];
}

export function routeToLngLat(route: Pt[]): Pt[] {
  return route.map(toLngLat);
}

// The real-world bounding box the demo plane covers, for the initial camera fit.
export const DEMO_BOUNDS: [Pt, Pt] = [
  [73.735, 18.59],
  [73.855, 18.68],
];
