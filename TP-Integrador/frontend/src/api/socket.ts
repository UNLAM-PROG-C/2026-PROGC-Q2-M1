// Suscripción a los eventos del backend por WebSocket (patrón Observer,
// design D6 y D13). Al conectar, el backend manda un evento `state` con el
// snapshot completo, así que una reconexión (o una recarga de la página)
// recupera el trabajo en curso sin pedir nada más.
// Si la conexión se cae, se reintenta con espera exponencial acotada.

import {SOCKET_URL} from './config';
import type {ServerEvent} from './types';

const RECONNECT_BASE_MS = 500;
const RECONNECT_MAX_MS = 5000;
const BACKOFF_FACTOR = 2;

export type ServerEventListener = (event: ServerEvent) => void;
export type ConnectionListener = (connected: boolean) => void;

export interface EventSocket
{
  close(): void;
}

/** Espera antes del intento número `attempt` (empezando en 0). */
export function reconnectDelayMs(attempt: number): number
{
  return Math.min(RECONNECT_MAX_MS, RECONNECT_BASE_MS * BACKOFF_FACTOR ** attempt);
}

function parseEvent(raw: unknown): ServerEvent | null
{
  try
  {
    const event = JSON.parse(String(raw)) as ServerEvent;
    return typeof event?.type === 'string' ? event : null;
  }
  catch
  {
    return null;
  }
}

/** WebSocket que se reconecta solo hasta que se llama a `close()`. */
class ReconnectingSocket implements EventSocket
{
  private socket: WebSocket | null = null;
  private attempt = 0;
  private closed = false;
  private timer: ReturnType<typeof setTimeout> | undefined;

  constructor(private readonly url: string, private readonly onEvent: ServerEventListener, private readonly onConnection: ConnectionListener)
  {
    this.open();
  }

  close(): void
  {
    this.closed = true;
    clearTimeout(this.timer);
    this.socket?.close();
  }

  private open(): void
  {
    const socket = new WebSocket(this.url);
    socket.onopen = () => this.handleOpen();
    socket.onmessage = (message) => this.handleMessage(message.data);
    socket.onclose = () => this.scheduleReconnect();
    this.socket = socket;
  }

  private handleOpen(): void
  {
    this.attempt = 0;
    this.onConnection(true);
  }

  private handleMessage(data: unknown): void
  {
    const event = parseEvent(data);
    if (event)
    {
      this.onEvent(event);
    }
  }

  private scheduleReconnect(): void
  {
    this.onConnection(false);
    if (!this.closed)
    {
      this.timer = setTimeout(() => this.open(), reconnectDelayMs(this.attempt++));
    }
  }
}

/** Abre el WebSocket de eventos y lo mantiene conectado. */
export function connectEvents(onEvent: ServerEventListener, onConnection: ConnectionListener, url: string = SOCKET_URL): EventSocket
{
  return new ReconnectingSocket(url, onEvent, onConnection);
}
