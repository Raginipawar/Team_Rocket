// Google polyline algorithm at precision 6 (what OSRM returns with geometries=polyline6).
// Coordinates are [lat, lng] pairs.

export function decodePolyline6(str: string | null | undefined): [number, number][] {
  if (!str) return [];
  const coords: [number, number][] = [];
  let index = 0;
  let lat = 0;
  let lng = 0;
  const factor = 1e6;
  while (index < str.length) {
    for (const which of [0, 1]) {
      let result = 0;
      let shift = 0;
      let byte: number;
      do {
        byte = str.charCodeAt(index++) - 63;
        result |= (byte & 0x1f) << shift;
        shift += 5;
      } while (byte >= 0x20 && index < str.length);
      const delta = result & 1 ? ~(result >> 1) : result >> 1;
      if (which === 0) lat += delta;
      else lng += delta;
    }
    coords.push([lat / factor, lng / factor]);
  }
  return coords;
}

export function encodePolyline6(coords: [number, number][]): string {
  const factor = 1e6;
  let out = "";
  let prevLat = 0;
  let prevLng = 0;
  const enc = (v: number) => {
    let s = v < 0 ? ~(v << 1) : v << 1;
    let chunk = "";
    while (s >= 0x20) {
      chunk += String.fromCharCode((0x20 | (s & 0x1f)) + 63);
      s >>= 5;
    }
    return chunk + String.fromCharCode(s + 63);
  };
  for (const [la, ln] of coords) {
    const lat = Math.round(la * factor);
    const lng = Math.round(ln * factor);
    out += enc(lat - prevLat) + enc(lng - prevLng);
    prevLat = lat;
    prevLng = lng;
  }
  return out;
}
