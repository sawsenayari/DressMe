import { useRef } from 'react';

/** Opens the camera on mobile, file chooser on desktop. */
export function PhotoPicker({
  label,
  onPick,
  busy,
  className = 'btn',
}: {
  label: string;
  onPick: (f: File) => void;
  busy?: boolean;
  className?: string;
}) {
  const ref = useRef<HTMLInputElement>(null);
  return (
    <>
      <input
        ref={ref}
        type="file"
        accept="image/*"
        capture="environment"
        hidden
        onChange={e => {
          const f = e.target.files?.[0];
          if (f) onPick(f);
          e.target.value = '';
        }}
      />
      <button className={className} disabled={busy} onClick={() => ref.current?.click()}>
        <span style={{ fontSize: '1.1rem' }}>📸</span>
        <span>{busy ? 'Analyse…' : label}</span>
      </button>
    </>
  );
}
