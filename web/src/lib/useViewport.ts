import { useEffect, useState } from 'react';

export interface Viewport { w: number; h: number }
export function useViewport(): Viewport {
  const [v, setV] = useState({ w: innerWidth, h: innerHeight });
  useEffect(() => {
    const f = () => setV({ w: innerWidth, h: innerHeight });
    addEventListener('resize', f);
    return () => removeEventListener('resize', f);
  }, []);
  return v;
}
