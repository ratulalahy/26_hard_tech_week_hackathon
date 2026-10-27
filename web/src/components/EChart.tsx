import { HeatmapChart, LineChart, ScatterChart } from 'echarts/charts';
import { GridComponent, MarkAreaComponent, MarkLineComponent, MarkPointComponent, TooltipComponent, VisualMapComponent } from 'echarts/components';
import * as echarts from 'echarts/core';
import type { EChartsCoreOption } from 'echarts/core';
import { SVGRenderer } from 'echarts/renderers';
import { useEffect, useRef } from 'react';
import { C } from '../lib/color';

echarts.use([LineChart, HeatmapChart, ScatterChart, GridComponent, TooltipComponent, MarkAreaComponent, MarkLineComponent, MarkPointComponent, VisualMapComponent, SVGRenderer]);

// A custom theme built from the tokens: hairline grids, muted axes, no chart junk.
const axis = {
  axisLine: { show: true, lineStyle: { color: 'rgba(110,62,30,.22)', width: 1 } },
  axisTick: { show: false },
  axisLabel: { color: C.ink3, fontSize: 12, fontFamily: 'Funnel Sans', margin: 8 },
  splitLine: { show: true, lineStyle: { color: 'rgba(110,62,30,.08)', width: 1 } },
  nameTextStyle: { color: C.ink3, fontSize: 11, fontFamily: 'Funnel Sans' },
};
echarts.registerTheme('gridpilot', {
  color: [C.ink, C.route, C.ink3],
  backgroundColor: 'transparent',
  textStyle: { fontFamily: 'Funnel Sans', color: C.ink2, fontSize: 12 },
  categoryAxis: { ...axis, splitLine: { show: false } },
  valueAxis: { ...axis, axisLine: { show: false } },
  timeAxis: { ...axis, splitLine: { show: false } },
  line: { symbol: 'none', smooth: false, lineStyle: { width: 1.75 } },
  tooltip: {
    backgroundColor: '#fff', borderWidth: 0, padding: [8, 12], extraCssText: 'border-radius:8px;box-shadow:0 0 0 1px rgba(110,62,30,.14),0 8px 24px -12px rgba(124,64,28,.25);',
    textStyle: { color: C.ink, fontSize: 12, fontFamily: 'Funnel Sans' },
    axisPointer: { lineStyle: { color: 'rgba(45,29,20,.35)', width: 1 }, crossStyle: { color: 'rgba(45,29,20,.35)' } },
  },
});

const withMotion = (o: EChartsCoreOption): EChartsCoreOption => {
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  return { animation: !reduce, animationDuration: 200, animationDurationUpdate: 160, ...o };
};

export function EChart({ option, className, testId, label }: { option: EChartsCoreOption; className?: string; testId?: string; label: string }) {
  const el = useRef<HTMLDivElement>(null);
  const chart = useRef<echarts.ECharts | null>(null);
  const optRef = useRef(option);
  optRef.current = option;
  useEffect(() => {
    if (!el.current) return;
    const c = echarts.init(el.current, 'gridpilot', { renderer: 'svg' });
    chart.current = c;
    c.setOption(withMotion(optRef.current), { notMerge: true });
    const ro = new ResizeObserver(() => c.resize());
    ro.observe(el.current);
    return () => { ro.disconnect(); c.dispose(); chart.current = null; };
  }, []);
  useEffect(() => { chart.current?.setOption(withMotion(option), { notMerge: true }); }, [option]);
  return <div ref={el} className={className} data-testid={testId} role="img" aria-label={label} />;
}
