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

export const BASE_OPTION: EChartsOption = {
  backgroundColor: "transparent",
  textStyle: { fontFamily: "Inter, sans-serif", color: CHART_COLORS.muted },
  grid: { left: 48, right: 16, top: 32, bottom: 28 },
  tooltip: {
    trigger: "axis",
    backgroundColor: CHART_COLORS.tooltip,
    borderColor: "rgba(255,255,255,0.07)",
    textStyle: { color: CHART_COLORS.text, fontSize: 12 },
  },
  legend: { top: 0, textStyle: { color: CHART_COLORS.muted, fontSize: 12 } },
};

const AXIS_STYLE = {
  axisLabel: { color: CHART_COLORS.muted, fontSize: 11 },
  axisLine: { lineStyle: { color: CHART_COLORS.grid } },
  splitLine: { lineStyle: { color: CHART_COLORS.grid, type: "dashed" as const } },
};

/** Applique le style commun à un axe ; `const T` conserve les littéraux (type: "value"…). */
export function styledAxis<const T extends Record<string, unknown>>(axis: T) {
  return { ...AXIS_STYLE, ...axis, axisLabel: { ...AXIS_STYLE.axisLabel, ...(axis.axisLabel as object | undefined) } };
}
