// Controlador de zoom compartible (patrón Observer, design D5 del cambio 4).
// Guarda la vista (zoom y desplazamiento) y avisa a quienes se suscribieron.
// Un visor solo tiene su propio controlador; los dos mosaicos de una
// comparación comparten uno, así acercar uno mueve el otro a la misma zona.
// La interfaz `subscribe`/`getView` es la que pide `useSyncExternalStore`.

import {FIT_VIEW, type ZoomView} from './zoom';

type Listener = () => void;

export class ZoomController
{
  private view: ZoomView = FIT_VIEW;
  private readonly listeners = new Set<Listener>();

  getView = (): ZoomView => this.view;

  /** Devuelve la función para desuscribirse. */
  subscribe = (listener: Listener): (() => void) =>
  {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  };

  /** Aplica un cambio a la vista y avisa a todos los suscriptores si cambió. */
  update = (change: (view: ZoomView) => ZoomView): void =>
  {
    const next = change(this.view);
    if (next === this.view)
    {
      return;
    }
    this.view = next;
    this.listeners.forEach((listener) => listener());
  };
}
