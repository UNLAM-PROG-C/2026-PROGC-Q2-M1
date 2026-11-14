// Configuración común de Vitest: matchers de jest-dom y limpieza del DOM.
import '@testing-library/jest-dom/vitest';
import {cleanup} from '@testing-library/react';
import {afterEach} from 'vitest';

afterEach(() => cleanup());
