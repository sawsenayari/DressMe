import type { ClothingItem } from '../../types';
import { Placeholder } from './Placeholder';
import { coloursLabel, seasonLabel, slotLabel, typeLabel } from './ItemFields';

interface Props {
  item?: ClothingItem;
  index?: number;
  onClick?: (item: ClothingItem) => void;
  /** Chargement immédiat (quelques pièces visibles tout de suite, ex. tenue du jour). */
  eager?: boolean;
}

export function ItemTile({ item, index = 0, onClick, eager = false }: Props) {
  const slotVal = item?.slot || item?.category;
  const categoryTagClass = slotVal === 'top' 
    ? 'chip-tag-pink' 
    : slotVal === 'bottom' 
    ? 'chip-tag-lavender' 
    : slotVal === 'outer' 
    ? 'chip-tag-mint' 
    : slotVal === 'footwear'
    ? 'chip-tag-butter'
    : slotVal === 'bag'
    ? 'chip-tag-peach'
    : 'chip-tag-sky';

  return (
    <figure
      className="tile"
      onClick={() => item && onClick?.(item)}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
    >
      <div className="tile-img-box">
        {item ? (
          <img
            src={item.imageUrl}
            alt={item.name || `${slotLabel(item.slot)} ${coloursLabel(item)}`}
            loading={eager ? 'eager' : 'lazy'}
            onError={e => {
              // fallback if image fails to load
              (e.target as HTMLElement).style.display = 'none';
            }}
          />
        ) : (
          <Placeholder index={index} />
        )}

        {item?.wearCount !== undefined && (
          <span className="tile-badge" title={`Worn ${item.wearCount} times`}>
            ✨ porté {item.wearCount} fois
          </span>
        )}
      </div>

      {item && (
        <figcaption>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '4px', gap: '6px' }}>
            <span className="tile-category">{slotLabel(slotVal)}</span>
            <span className={`chip-tag ${categoryTagClass}`}>{seasonLabel(item.season)}</span>
          </div>
          {item.name && (
            <div style={{ fontWeight: 600, fontSize: '0.88rem', color: 'var(--ink)', marginTop: '2px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={item.name}>
              {item.name}
            </div>
          )}
          <div className="tile-details">
            <span>{coloursLabel(item)}</span>
            {(item.type || item.style) && (
              <>
                <span>•</span>
                <span>{typeLabel(item.type) || item.style}</span>
              </>
            )}
            {item.source === 'user_corrected' && <span title="Caractéristiques confirmées par vous">✓</span>}
          </div>
        </figcaption>
      )}
    </figure>
  );
}
