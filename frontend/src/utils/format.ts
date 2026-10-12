// Formatage des grandeurs selon le système (V en continu, kV en alternatif), à la française.

const nf = (d: number) => new Intl.NumberFormat("fr-FR", { minimumFractionDigits: d, maximumFractionDigits: d });

export function fmt(v: number | null | undefined, decimales = 0): string {
  return v == null || !isFinite(v) ? "–" : nf(decimales).format(v);
}

/** Tension : « 1 950 V » en 3 kV, « 24,72 kV » en 25 kV. */
export function fmtU(v: number | null | undefined, ac: boolean): string {
  if (v == null || !isFinite(v)) return "–";
  return ac ? `${fmt(v / 1000, 2)} kV` : `${fmt(v)} V`;
}

export function fmtHms(t: number): string {
  const s = Math.round(t);
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), x = s % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(x).padStart(2, "0")}`;
}

/** Énergie : kWh sous 1 MWh, MWh au-delà. */
export function fmtE(kwh: number | null | undefined): string {
  if (kwh == null || !isFinite(kwh)) return "–";
  return Math.abs(kwh) < 1000 ? `${fmt(kwh)} kWh` : `${fmt(kwh / 1000, 2)} MWh`;
}
