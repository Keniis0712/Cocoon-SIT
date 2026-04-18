import { useEffect, useRef } from "react";
import * as echarts from "echarts";

interface EChartProps {
  option: unknown;
  height?: number;
}

export default function EChart({ option, height = 320 }: EChartProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    if (!chartRef.current) {
      chartRef.current = echarts.init(containerRef.current, undefined, { renderer: "canvas" });
    }
    chartRef.current.setOption(option as echarts.EChartsOption, true);
    const observer = new ResizeObserver(() => {
      chartRef.current?.resize();
    });
    observer.observe(containerRef.current);
    return () => {
      observer.disconnect();
    };
  }, [option]);

  useEffect(() => {
    return () => {
      chartRef.current?.dispose();
      chartRef.current = null;
    };
  }, []);

  return <div ref={containerRef} style={{ height }} className="w-full" />;
}
