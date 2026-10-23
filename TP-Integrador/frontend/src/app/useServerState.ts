// Hook que mantiene el estado del backend: snapshot inicial por HTTP y
// actualizaciones por WebSocket (Observer). Cada reconexión trae un snapshot
// nuevo, así que al recargar la página se recupera el trabajo en curso.

import {useEffect, useReducer, useState} from 'react';
import {getState} from '../api/client';
import {connectEvents} from '../api/socket';
import type {AppState, ServerEvent} from '../api/types';
import {applyServerEvent} from './serverState';

export interface ServerConnection
{
  server: AppState | null;
  connected: boolean;
}

export function useServerState(): ServerConnection
{
  const [server, dispatch] = useReducer(applyServerEvent, null);
  const [connected, setConnected] = useState(false);

  useEffect(() =>
  {
    const onEvent = (event: ServerEvent): void => dispatch(event);
    getState().then((state) => onEvent({type: 'state', state})).catch(() => setConnected(false));
    const socket = connectEvents(onEvent, setConnected);
    return () => socket.close();
  }, []);

  return {server, connected};
}
