import { Placeholder } from './Placeholder';

export function EmptyState({ text, endpoint }: { text: string; endpoint?: string }) {
  return (
    <div className="empty">
      <div className="empty-art">
        <Placeholder index={0} />
        <Placeholder index={1} />
        <Placeholder index={2} />
      </div>
      <h3>Nothing here yet</h3>
      <p>{text}</p>
      {endpoint && (
        <div>
          <span style={{ fontSize: '0.78rem', color: 'var(--muted)', display: 'block', marginBottom: '4px' }}>
            Endpoint Contract:
          </span>
          <code>{endpoint}</code>
        </div>
      )}
    </div>
  );
}
