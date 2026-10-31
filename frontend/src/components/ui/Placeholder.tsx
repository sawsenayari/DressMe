const SHAPES = ['arch', 'blob', 'pebble'] as const;
const TONES = ['lilac', 'butter', 'mint', 'sky'] as const;
const FASHION_EMOJIS = ['🧶', '👗', '🧥', '👟', '👜', '✨'];

/** Artistic stand-in for a garment image. Pass index to vary shape and tone. */
export function Placeholder({ index = 0, label }: { index?: number; label?: string }) {
  return (
    <div
      className={`ph ph-${SHAPES[index % 3]} tone-${TONES[index % 4]}`}
      role="img"
      aria-label={label ?? 'Image placeholder'}
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontSize: '2rem',
        opacity: 0.85,
        boxShadow: 'var(--shadow-subtle)',
      }}
    >
      <span>{FASHION_EMOJIS[index % FASHION_EMOJIS.length]}</span>
    </div>
  );
}
