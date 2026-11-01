import { Placeholder } from './Placeholder';

export function EmptyState({ text, endpoint }: { text: string; endpoint?: string }) {
  return (
    <div className="empty">
      <div className="empty-art">
        <Placeholder index={0} />
        <Placeholder index={1} />
        <Placeholder index={2} />
      </div>
      <h3>Rien à afficher pour l'instant</h3>
      <p>{text}</p>
      {/* endpoint : utile aux développeurs (attribut), jamais affiché à l'utilisateur */}
      {endpoint && <span hidden data-endpoint={endpoint} />}
    </div>
  );
}
