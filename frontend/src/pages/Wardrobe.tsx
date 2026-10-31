import { useState, useMemo } from 'react';
import { useAsync } from '../hooks/useAsync';
import { addItem, listItems } from '../services/wardrobe';
import type { Slot, Season, ClothingItem } from '../types';
import { ItemTile } from '../components/ui/ItemTile';
import { ItemDetailModal } from '../components/ui/ItemDetailModal';
import { AddItemModal } from '../components/ui/AddItemModal';
import { EmptyState } from '../components/ui/EmptyState';
import { useApp } from '../context/AppContext';

// 7 official slots defined in ItemCard v1 contract
const SLOTS: { id: Slot | 'all'; label: string; icon: string }[] = [
  { id: 'all', label: 'Toutes les pièces', icon: '✨' },
  { id: 'top', label: 'Hauts (Top)', icon: '👚' },
  { id: 'bottom', label: 'Bas (Bottom)', icon: '👖' },
  { id: 'onepiece', label: 'Robe / Combinaison', icon: '👗' },
  { id: 'outer', label: 'Vestes & Manteaux', icon: '🧥' },
  { id: 'footwear', label: 'Chaussures', icon: '👠' },
  { id: 'bag', label: 'Sacs', icon: '👜' },
  { id: 'accessory', label: 'Accessoires', icon: '🧣' },
];

const SEASONS: { id: Season | 'all'; label: string }[] = [
  { id: 'all', label: 'Toutes Saisons' },
  { id: 'spring', label: 'Printemps' },
  { id: 'summer', label: 'Été' },
  { id: 'autumn', label: 'Automne' },
  { id: 'winter', label: 'Hiver' },
];

export default function Wardrobe() {
  const { useDemoData, wardrobe: demoWardrobe, addWardrobeItem, searchQuery } = useApp();
  const [version, setVersion] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [activeSlot, setActiveSlot] = useState<Slot | 'all'>('all');
  const [activeSeason, setActiveSeason] = useState<Season | 'all'>('all');
  const [onlyTraditional, setOnlyTraditional] = useState(false);
  const [sortBy, setSortBy] = useState<'recent' | 'most-worn' | 'least-worn' | 'confidence'>('recent');
  const [selectedItem, setSelectedItem] = useState<ClothingItem | null>(null);
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);

  // Live model backend query
  const apiState = useAsync(listItems, [version]);

  async function handleAdd(file: File, meta?: Partial<ClothingItem>) {
    setBusy(true);
    setError('');
    try {
      if (useDemoData) {
        const newItem: ClothingItem = {
          id: `it_${Date.now()}`,
          name: meta?.name || 'Nouvelle Pièce',
          imageUrl: URL.createObjectURL(file),
          imageCrop: URL.createObjectURL(file),
          slot: meta?.slot || 'top',
          category: meta?.slot || 'top',
          colour: [meta?.color || 'cream'],
          color: meta?.color || 'cream',
          season: meta?.season || 'spring',
          style: meta?.style || 'style standard',
          traditional: meta?.traditional || false,
          confidence: { slot: 0.95, colour: 0.90, type: 0.88 },
          source: 'user_corrected',
          wearCount: 0,
        };
        addWardrobeItem(newItem);
      } else {
        await addItem(file);
        setVersion(v => v + 1);
      }
    } catch {
      setError('Impossible d\'analyser la photo. Vérifiez le service de segmentation & classification.');
      throw new Error('Upload failed');
    } finally {
      setBusy(false);
    }
  }

  const rawItems: ClothingItem[] = useDemoData
    ? demoWardrobe
    : (apiState.data || []);

  const filteredItems = useMemo(() => {
    let items = [...rawItems];

    if (activeSlot !== 'all') {
      items = items.filter(i => (i.slot || i.category) === activeSlot);
    }

    if (activeSeason !== 'all') {
      items = items.filter(i => i.season === activeSeason || i.season === 'all');
    }

    if (onlyTraditional) {
      items = items.filter(i => i.traditional);
    }

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      items = items.filter(
        i =>
          (i.name && i.name.toLowerCase().includes(q)) ||
          i.slot.toLowerCase().includes(q) ||
          i.color.toLowerCase().includes(q) ||
          (i.style && i.style.toLowerCase().includes(q))
      );
    }

    if (sortBy === 'most-worn') {
      items.sort((a, b) => (b.wearCount || 0) - (a.wearCount || 0));
    } else if (sortBy === 'least-worn') {
      items.sort((a, b) => (a.wearCount || 0) - (b.wearCount || 0));
    } else if (sortBy === 'confidence') {
      items.sort((a, b) => (b.confidence?.slot || 0) - (a.confidence?.slot || 0));
    }

    return items;
  }, [rawItems, activeSlot, activeSeason, onlyTraditional, searchQuery, sortBy]);

  return (
    <>
      <header className="page-head">
        <div>
          <h1 style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            Dressing Numérique <span style={{ fontSize: '1.6rem' }}>🧺</span>
          </h1>
          <p className="page-subtitle">
            Conforme au contrat ItemCard v1 (7 emplacements, découpe SegFormer/rembg et traçabilité de classification).
          </p>
        </div>

        <button className="btn" onClick={() => setIsAddModalOpen(true)} disabled={busy}>
          <span style={{ fontSize: '1.1rem' }}>+</span>
          <span>Ajouter une pièce</span>
        </button>
      </header>

      {error && (
        <div
          role="alert"
          style={{
            background: 'var(--danger-bg)',
            color: 'var(--danger)',
            padding: '12px 18px',
            borderRadius: '16px',
            marginBottom: '20px',
            fontSize: '0.9rem',
          }}
        >
          {error}
        </div>
      )}

      {/* 7 Slots Category Pills (ItemCard v1) */}
      <section style={{ marginBottom: '16px' }}>
        <div className="chips" role="group" aria-label="Filtres emplacements">
          {SLOTS.map(c => {
            const count = c.id === 'all'
              ? rawItems.length
              : rawItems.filter(i => (i.slot || i.category) === c.id).length;

            return (
              <button
                key={c.id}
                className="chip"
                aria-pressed={activeSlot === c.id}
                onClick={() => setActiveSlot(c.id)}
                style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}
              >
                <span>{c.icon}</span>
                <span>{c.label}</span>
                <span
                  style={{
                    fontSize: '0.74rem',
                    background: activeSlot === c.id ? 'rgba(0,0,0,0.1)' : 'var(--paper)',
                    padding: '2px 8px',
                    borderRadius: '999px',
                    fontWeight: 600,
                  }}
                >
                  {count}
                </span>
              </button>
            );
          })}
        </div>
      </section>

      {/* Secondary Season, Traditional, and Sorting Bar */}
      <section
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '12px',
          marginBottom: '24px',
          paddingBottom: '16px',
          borderBottom: '1px solid var(--line)',
        }}
      >
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center' }}>
          {SEASONS.map(s => (
            <button
              key={s.id}
              onClick={() => setActiveSeason(s.id)}
              style={{
                fontSize: '0.82rem',
                padding: '6px 14px',
                borderRadius: '999px',
                border: '1px solid',
                borderColor: activeSeason === s.id ? 'var(--pastel-pink-deep)' : 'var(--line)',
                background: activeSeason === s.id ? 'var(--pastel-pink-soft)' : 'var(--surface)',
                color: activeSeason === s.id ? 'var(--pastel-pink-deep)' : 'var(--muted)',
                fontWeight: activeSeason === s.id ? 600 : 500,
              }}
            >
              {s.label}
            </button>
          ))}

          {/* Traditional Garments Filter (tunisian pieces: jebba, fouta) */}
          <button
            onClick={() => setOnlyTraditional(prev => !prev)}
            style={{
              fontSize: '0.82rem',
              padding: '6px 14px',
              borderRadius: '999px',
              border: '1px solid',
              borderColor: onlyTraditional ? 'var(--pastel-butter-deep)' : 'var(--line)',
              background: onlyTraditional ? 'var(--pastel-butter-soft)' : 'var(--surface)',
              color: onlyTraditional ? 'var(--pastel-butter-deep)' : 'var(--muted)',
              fontWeight: onlyTraditional ? 700 : 500,
            }}
          >
            🇹🇳 Traditionnel ({rawItems.filter(i => i.traditional).length})
          </button>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span style={{ fontSize: '0.82rem', color: 'var(--muted)' }}>Trier par :</span>
          <select
            value={sortBy}
            onChange={e => setSortBy(e.target.value as any)}
            className="form-select"
            style={{ padding: '6px 12px', fontSize: '0.84rem', width: 'auto', borderRadius: '12px' }}
          >
            <option value="recent">Récemment Ajouté</option>
            <option value="most-worn">Plus Porté</option>
            <option value="least-worn">Moins Porté</option>
            <option value="confidence">Confiance Détection (Obj1)</option>
          </select>
        </div>
      </section>

      {/* Grid of Items */}
      {filteredItems.length > 0 ? (
        <div className="grid">
          {filteredItems.map((item, idx) => (
            <ItemTile
              key={item.id}
              item={item}
              index={idx}
              onClick={it => setSelectedItem(it)}
            />
          ))}
        </div>
      ) : (
        <EmptyState
          text="Aucune pièce ne correspond aux filtres appliqués."
          endpoint="GET /wardrobe/items"
        />
      )}

      {/* Item Detail Modal */}
      <ItemDetailModal
        item={selectedItem}
        onClose={() => setSelectedItem(null)}
      />

      {/* Add Item Modal */}
      <AddItemModal
        isOpen={isAddModalOpen}
        onClose={() => setIsAddModalOpen(false)}
        onAdd={handleAdd}
        busy={busy}
      />
    </>
  );
}
