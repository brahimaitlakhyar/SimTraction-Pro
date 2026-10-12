import type { EChartsOption } from "echarts";

// Thème commun aux graphiques, aligné sur les tokens de index.css
export const CHART_COLORS = {
  primary: "#3b82f6",
  accent:  "#10b981",
  warn:    "#f59e0b",
  danger:  "#ef4444",
  violet:  "#8b5cf6",
  muted:   "#64748b",
  grid:    "rgba(255,255,255,0.04)",
  tooltip: "#1a2235",
  text:    "#f1f5f9",
};

// Nombres à la française (espace des milliers, virgule décimale) : ECharts formate en anglais par défaut
const nfFr = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 3 });
export const fmtNombre = (v: unknown) => (typeof v === "number" ? nfFr.format(v) : String(v ?? ""));

export const BASE_OPTION: EChartsOption = {
  backgroundColor: "transparent",
  textStyle: { fontFamily: "Inter, sans-serif", color: CHART_COLORS.muted },
  grid: { left: 48, right: 16, top: 32, bottom: 28 },
  tooltip: {
    trigger: "axis",
    backgroundColor: CHART_COLORS.tooltip,
    borderColor: "rgba(255,255,255,0.07)",
    textStyle: { color: CHART_COLORS.text, fontSize: 12 },
    valueFormatter: v => (Array.isArray(v) ? v.map(fmtNombre).join(" ; ") : fmtNombre(v)),
  },
  legend: { top: 0, textStyle: { color: CHART_COLORS.muted, fontSize: 12 } },
};

// Clés d'objet fusionnées avec BASE_OPTION au lieu d'être remplacées
const CLES_FUSIONNEES = ["textStyle", "grid", "tooltip", "legend"] as const;

/** Fusionne les options d'un graphique avec le thème (fusion d'un niveau pour tooltip, legend…). */
export function avecTheme(option: EChartsOption): EChartsOption {
  const out: Record<string, unknown> = { ...BASE_OPTION, ...option };
  for (const k of CLES_FUSIONNEES) {
    const base = BASE_OPTION[k], propre = option[k];
    if (propre && typeof propre === "object" && !Array.isArray(propre)) out[k] = { ...(base as object), ...propre };
  }
  return out as EChartsOption;
}

/** Zoom à la molette avec Ctrl seulement : la molette seule fait défiler la page. */
export const ZOOM_INTERIEUR = { type: "inside" as const, zoomOnMouseWheel: "ctrl" as const, moveOnMouseWheel: false };

const AXIS_STYLE = {
  axisLabel: { color: CHART_COLORS.muted, fontSize: 11 },
  axisLine: { lineStyle: { color: CHART_COLORS.grid } },
  splitLine: { lineStyle: { color: CHART_COLORS.grid, type: "dashed" as const } },
};

/**
 * Applique le style commun à un axe ; `const T` conserve les littéraux (type: "value"…).
 * Les axes numériques sans formateur propre affichent les nombres à la française.
 */
export function styledAxis<const T extends Record<string, unknown>>(axis: T) {
  const label = (axis.axisLabel ?? {}) as Record<string, unknown>;
  const numerique = axis.type === "value" && label.formatter === undefined;
  return {
    ...AXIS_STYLE,
    ...axis,
    axisLabel: { ...AXIS_STYLE.axisLabel, ...(numerique ? { formatter: fmtNombre } : {}), ...label },
  };
}
