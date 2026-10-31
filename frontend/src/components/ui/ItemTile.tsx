import type { ClothingItem } from '../../types';
import { Placeholder } from './Placeholder';

interface Props {
  item?: ClothingItem;
  index?: number;
  onClick?: (item: ClothingItem) => void;
}

export function ItemTile({ item, index = 0, onClick }: Props) {
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
            alt={`${item.color} ${item.category}`}
            loading="lazy"
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
            ✨ {item.wearCount} wears
          </span>
        )}
      </div>

      {item && (
        <figcaption>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '4px' }}>
            <span className="tile-category">{item.category}</span>
            <span className={`chip-tag ${categoryTagClass}`}>{item.season}</span>
          </div>
          <div className="tile-details">
            <span>{item.color}</span>
            {item.style && (
              <>
                <span>•</span>
                <span>{item.style}</span>
              </>
            )}
          </div>
        </figcaption>
      )}
    </figure>
  );
}
