// Zona para soltar archivos (`store-utility-card`): acepta arrastrar y soltar
// o elegir con el selector del sistema. No sube nada: entrega los archivos.

import {useRef, useState, type ChangeEvent, type DragEvent, type ReactNode} from 'react';

interface FileDropZoneProps
{
  title: string;
  hint: string;
  accept: string;
  multiple: boolean;
  disabled?: boolean;
  onFiles: (files: File[]) => void;
  children?: ReactNode;
}

interface FileDrop
{
  dragging: boolean;
  dropHandlers: {onDrop: (event: DragEvent) => void; onDragOver: (event: DragEvent) => void; onDragEnter: () => void; onDragLeave: () => void};
  onChange: (event: ChangeEvent<HTMLInputElement>) => void;
}

function useFileDrop(onFiles: (files: File[]) => void, disabled: boolean): FileDrop
{
  const [dragging, setDragging] = useState(false);
  const deliver = (files: FileList | null): void =>
  {
    if (files && files.length > 0 && !disabled)
    {
      onFiles(Array.from(files));
    }
  };
  const onDrop = (event: DragEvent): void =>
  {
    event.preventDefault();
    setDragging(false);
    deliver(event.dataTransfer.files);
  };
  const onDragOver = (event: DragEvent): void => event.preventDefault();
  const onChange = (event: ChangeEvent<HTMLInputElement>): void =>
  {
    deliver(event.target.files);
    event.target.value = '';
  };
  return {dragging, onChange, dropHandlers: {onDrop, onDragOver, onDragEnter: () => setDragging(true), onDragLeave: () => setDragging(false)}};
}

export function FileDropZone({title, hint, accept, multiple, disabled = false, onFiles, children}: FileDropZoneProps): JSX.Element
{
  const input = useRef<HTMLInputElement>(null);
  const {dragging, dropHandlers, onChange} = useFileDrop(onFiles, disabled);
  return (
    <div className={dragging ? 'drop-zone drop-zone--dragging' : 'drop-zone'} {...dropHandlers}>
      <h2 className="drop-zone__title">{title}</h2>
      <p className="drop-zone__hint">{hint}</p>
      <button type="button" className="drop-zone__choose" disabled={disabled} onClick={() => input.current?.click()}>Elegir archivos…</button>
      <input ref={input} type="file" accept={accept} multiple={multiple} hidden onChange={onChange} aria-label={title} />
      {children}
    </div>
  );
}
