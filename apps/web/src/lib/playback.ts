import { useCallback, useEffect, useRef, useState } from "react";

/** Play/pause/scrub clock over [0, duration]. */
export function usePlayback(duration: number) {
  const [t, setT] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const last = useRef<number | null>(null);

  useEffect(() => {
    if (!playing) {
      last.current = null;
      return;
    }
    let raf = 0;
    const tick = (now: number) => {
      const prev = last.current ?? now;
      last.current = now;
      const dt = ((now - prev) / 1000) * speed;
      setT((cur) => {
        const next = cur + dt;
        if (next >= duration) {
          setPlaying(false);
          return duration;
        }
        return next;
      });
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [playing, speed, duration]);

  const toggle = useCallback(() => {
    setT((cur) => (cur >= duration ? 0 : cur));
    setPlaying((p) => !p);
  }, [duration]);
  const seek = useCallback((v: number) => setT(Math.min(Math.max(v, 0), duration)), [duration]);
  const reset = useCallback(() => {
    setPlaying(false);
    setT(0);
  }, []);
  return { t, playing, speed, setSpeed, toggle, seek, reset };
}
