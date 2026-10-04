import { useEffect, useState } from 'react';
import { loadAnim } from '../theme';

/** Плавний лічильник до `target` за ~600мс. При min/off — одразу фінал. */
export function useCountUp(target: number, duration = 600): number {
  const [v, setV] = useState(target);
  useEffect(() => {
    if (loadAnim() !== 'all' || !Number.isFinite(target)) {
      setV(target);
      return;
    }
    let raf = 0;
    const t0 = performance.now();
    const tick = (now: number) => {
      const p = Math.min(1, (now - t0) / duration);
      const eased = 1 - Math.pow(1 - p, 3);
      setV(target * eased);
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, duration]);
  return v;
}
