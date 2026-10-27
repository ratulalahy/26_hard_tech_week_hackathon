import '@fontsource/funnel-sans/400.css';
import '@fontsource/funnel-sans/500.css';
import '@fontsource/funnel-sans/600.css';
import '@fontsource/funnel-display/400.css';
import '@fontsource/funnel-display/500.css';
import '@fontsource/funnel-display/600.css';
import './styles.css';
import { createRoot } from 'react-dom/client';
import { App } from './App';

createRoot(document.getElementById('root')!).render(<App />);
