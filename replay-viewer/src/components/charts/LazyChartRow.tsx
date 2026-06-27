import { useEffect, useRef, useState, type ReactNode } from "react";

/** Mount children only when row scrolls into view (chart virtualization). */
export function LazyChartRow({
  children,
  minHeight = 100,
}: {
  children: ReactNode;
  minHeight?: number;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) setVisible(true);
      },
      { rootMargin: "120px 0px" },
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  return (
    <div ref={ref} style={{ minHeight }} className="lazy-chart-row">
      {visible ? children : null}
    </div>
  );
}
