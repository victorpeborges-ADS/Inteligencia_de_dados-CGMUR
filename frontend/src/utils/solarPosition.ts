/**
 * Posição solar (algoritmo NOAA simplificado) — espelha shadow_insolation_service.py.
 * Usado na iluminação do gêmeo 3D (17f.1).
 */

export type SolarPosition = {
  elevacaoGraus: number;
  azimuteGraus: number;
  zeniteGraus: number;
};

export type WeatherPresetId = 'dia' | 'entardecer' | 'noite' | 'chuva';

export type SceneLighting = {
  sunAzimuth: number;
  sunPolar: number;
  sunIntensity: number;
  lightIntensity: number;
  lightColor: string;
  lightPosition: [number, number, number];
  hillshadeExaggeration: number;
  basemapBrightness: number;
  label: string;
  elevacaoGraus: number;
};

export function solarPosition(latDeg: number, lonDeg: number, when: Date): SolarPosition {
  const start = Date.UTC(when.getUTCFullYear(), 0, 0);
  const n = Math.floor((when.getTime() - start) / 86_400_000);
  const hour = when.getUTCHours() + when.getUTCMinutes() / 60 + when.getUTCSeconds() / 3600;

  const gamma = ((2 * Math.PI) / 365) * (n - 1 + (hour - 12) / 24);
  const decl =
    0.006918 -
    0.399912 * Math.cos(gamma) +
    0.070257 * Math.sin(gamma) -
    0.006758 * Math.cos(2 * gamma) +
    0.000907 * Math.sin(2 * gamma);

  const eqtime =
    229.18 *
    (0.000075 +
      0.001868 * Math.cos(gamma) -
      0.032077 * Math.sin(gamma) -
      0.014615 * Math.cos(2 * gamma) -
      0.040849 * Math.sin(2 * gamma));

  const timeOffset = eqtime + 4 * lonDeg;
  const tst = hour * 60 + timeOffset;
  const ha = ((tst / 4) - 180) * (Math.PI / 180);
  const lat = latDeg * (Math.PI / 180);

  let cosZen = Math.sin(lat) * Math.sin(decl) + Math.cos(lat) * Math.cos(decl) * Math.cos(ha);
  cosZen = Math.max(-1, Math.min(1, cosZen));
  const zenith = Math.acos(cosZen);
  const elev = 90 - (zenith * 180) / Math.PI;

  const sinAz = (-Math.sin(ha) * Math.cos(decl)) / Math.max(1e-6, Math.sin(zenith));
  const cosAz =
    (Math.sin(decl) - Math.sin(lat) * Math.cos(zenith)) /
    (Math.cos(lat) * Math.max(1e-6, Math.sin(zenith)));
  let az = (Math.atan2(sinAz, cosAz) * 180) / Math.PI;
  az = ((az % 360) + 360) % 360;

  return {
    elevacaoGraus: Math.round(elev * 100) / 100,
    azimuteGraus: Math.round(az * 100) / 100,
    zeniteGraus: Math.round(((zenith * 180) / Math.PI) * 100) / 100,
  };
}

/** Constrói Date UTC a partir de data local + hora do dia (0–24). */
export function dateAtLocalHour(base: Date, hourOfDay: number, lonDeg: number): Date {
  const utcOffsetHours = lonDeg / 15;
  const localHour = Math.max(0, Math.min(23.99, hourOfDay));
  const y = base.getFullYear();
  const m = base.getMonth();
  const d = base.getDate();
  // aproximação: local solar ≈ UTC + lon/15
  const utcHour = localHour - utcOffsetHours;
  const ms = Date.UTC(y, m, d, Math.floor(utcHour), Math.round((utcHour % 1) * 60), 0);
  return new Date(ms);
}

export function presetDefaultHour(preset: WeatherPresetId): number {
  switch (preset) {
    case 'entardecer':
      return 17.5;
    case 'noite':
      return 21;
    case 'chuva':
      return 14;
    case 'dia':
    default:
      return 12;
  }
}

export function computeSceneLighting(
  lat: number,
  lon: number,
  hourOfDay: number,
  preset: WeatherPresetId,
  baseDate: Date = new Date(),
): SceneLighting {
  const when = dateAtLocalHour(baseDate, hourOfDay, lon);
  const sun = solarPosition(lat, lon, when);
  const elev = sun.elevacaoGraus;
  const az = sun.azimuteGraus;
  // polar: 0 = zênite, 90 = horizonte (MapLibre sky / light)
  const polar = Math.max(0, Math.min(180, 90 - elev));

  let sunIntensity = elev > 0 ? 8 + (elev / 90) * 12 : 1.5;
  let lightIntensity = elev > 0 ? 0.35 + (elev / 90) * 0.45 : 0.12;
  let lightColor = '#ffffff';
  let hillshade = 0.25;
  let brightness = 1;
  let label = `Sol ${Math.round(elev)}° · az ${Math.round(az)}°`;

  if (elev > 0 && elev < 12) {
    lightColor = '#ffb070';
    sunIntensity = 14;
    lightIntensity = 0.55;
    label = `Aurora/crepúsculo · ${Math.round(elev)}°`;
  } else if (elev <= 0) {
    lightColor = '#6b8cae';
    sunIntensity = 1.2;
    lightIntensity = 0.1;
    hillshade = 0.12;
    brightness = 0.55;
    label = 'Noite';
  }

  if (preset === 'entardecer') {
    lightColor = '#ff9a5c';
    sunIntensity = Math.max(sunIntensity, 16);
    lightIntensity = Math.max(lightIntensity, 0.5);
    brightness = 0.85;
    label = `Entardecer · sol ${Math.round(elev)}°`;
  } else if (preset === 'noite') {
    lightColor = '#7aa0c4';
    sunIntensity = 1;
    lightIntensity = 0.08;
    hillshade = 0.1;
    brightness = 0.45;
    label = 'Noite';
  } else if (preset === 'chuva') {
    lightColor = '#c5d0d8';
    sunIntensity = Math.min(sunIntensity, 4);
    lightIntensity = Math.min(lightIntensity, 0.28);
    hillshade = 0.18;
    brightness = 0.7;
    label = `Chuva · luz difusa · sol ${Math.round(elev)}°`;
  } else if (preset === 'dia' && elev > 12) {
    label = `Dia claro · sol ${Math.round(elev)}°`;
  }

  return {
    sunAzimuth: az,
    sunPolar: polar,
    sunIntensity,
    lightIntensity,
    lightColor,
    lightPosition: [1.35, az, polar],
    hillshadeExaggeration: hillshade,
    basemapBrightness: brightness,
    label,
    elevacaoGraus: elev,
  };
}
