// Punto de entrada: tipografía Inter local (sin Google Fonts, para funcionar
// sin internet), estilos globales y montaje de la aplicación.

import '@fontsource/inter/300.css';
import '@fontsource/inter/400.css';
import '@fontsource/inter/600.css';
import './styles/tokens.css';
import './styles/base.css';
import './styles/layout.css';
import './styles/controls.css';
import './styles/result.css';
import {StrictMode} from 'react';
import {createRoot} from 'react-dom/client';
import {App} from './App';

const rootElement = document.getElementById('root');
if (rootElement)
{
  createRoot(rootElement).render(
    <StrictMode>
      <App />
    </StrictMode>,
  );
}
