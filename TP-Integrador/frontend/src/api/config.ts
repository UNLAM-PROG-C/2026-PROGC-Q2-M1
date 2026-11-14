// URL del backend, tomada de VITE_BACKEND_URL (ver env.example).

const DEFAULT_BACKEND_URL = 'http://127.0.0.1:8000';
const TRAILING_SLASHES = /\/+$/;
const HTTP_SCHEME = /^http/;

/** URL base HTTP del backend, sin barra final. */
export const BACKEND_URL: string = (import.meta.env.VITE_BACKEND_URL || DEFAULT_BACKEND_URL).replace(TRAILING_SLASHES, '');

/** URL del WebSocket de eventos: mismo host que la API con esquema ws/wss. */
export const SOCKET_URL: string = `${BACKEND_URL.replace(HTTP_SCHEME, 'ws')}/ws`;
