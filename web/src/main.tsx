import '@fontsource/funnel-sans/400.css';
import '@fontsource/funnel-sans/500.css';
import '@fontsource/funnel-sans/600.css';
import '@fontsource/funnel-display/400.css';
import '@fontsource/funnel-display/500.css';
import '@fontsource/funnel-display/600.css';
import './styles.css';
import { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { App } from './App';
import { Regions } from './pages/Regions';

// Temporary page switch (T18) until the shared nav (T21) mounts pages: #regions renders the standalone
// ten-region overview; every other hash renders the App shell unchanged.
const isRegions = () => location.hash.startsWith('#regions');
function Root() {
  const [regions, setRegions] = useState(isRegions);
  useEffect(() => {
    const on = () => setRegions(isRegions());
    window.addEventListener('hashchange', on);
    return () => window.removeEventListener('hashchange', on);
  }, []);
  return regions ? <Regions /> : <App />;
}

createRoot(document.getElementById('root')!).render(<Root />);
