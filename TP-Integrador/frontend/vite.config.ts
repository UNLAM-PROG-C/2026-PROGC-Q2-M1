/// <reference types="vitest/config" />
// Configuración de Vite y Vitest. El servidor de desarrollo escucha solo en
// 127.0.0.1 (spec "Acceso solo local") y toma el puerto de FRONTEND_PORT.
import react from '@vitejs/plugin-react';
import {defineConfig, loadEnv} from 'vite';

const LOCAL_HOST = '127.0.0.1';
const DEFAULT_FRONTEND_PORT = 5173;

function resolvePort(rawPort: string | undefined): number
{
  const port = Number(rawPort);
  return Number.isInteger(port) && port > 0 ? port : DEFAULT_FRONTEND_PORT;
}

export default defineConfig(({mode}) =>
{
  const env = loadEnv(mode, process.cwd(), '');
  const server = {host: LOCAL_HOST, port: resolvePort(env.FRONTEND_PORT), strictPort: true};
  return {
    plugins: [react()],
    server,
    preview: server,
    test: {
      environment: 'jsdom',
      globals: true,
      setupFiles: ['./src/testSetup.ts'],
      css: false,
    },
  };
});
