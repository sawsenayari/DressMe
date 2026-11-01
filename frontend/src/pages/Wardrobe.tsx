import { useState, useMemo } from 'react';
import { useAsync } from '../hooks/useAsync';
import { addItem, deleteItem, listItems, updateItem, type ItemPatch } from '../services/wardrobe';
import type { Slot, Season, ClothingItem } from '../types';
import { ItemTile } from '../components/ui/ItemTile';
import { ItemDetailModal } from '../components/ui/ItemDetailModal';
import { AddItemModal } from '../components/ui/AddItemModal';
import { EmptyState } from '../components/ui/EmptyState';
import { useApp } from '../context/AppContext';

// 7 official slots defined in ItemCard v1 contract
const SLOTS: { id: Slot | 'all'; label: string; icon: string }[] = [
  { id: 'all', label: 'Toutes les pièces', icon: '✨' },
  { id: 'top', label: 'Hauts', icon: '👚' },
  { id: 'bottom', label: 'Bas', icon: '👖' },
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
  const { useDemoData, wardrobe: demoWardrobe, addWardrobeItem, updateWardrobeItem, removeWardrobeItem, searchQuery, setSearchQuery } = useApp();
  const [version, setVersion] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [activeSlot, setActiveSlot] = useState<Slot | 'all'>('all');
  const [activeSeason, setActiveSeason] = useState<Season | 'all'>('all');
  const [onlyTraditional, setOnlyTraditional] = useState(false);
  const [sortBy, setSortBy] = useState<'recent' | 'name' | 'most-worn' | 'least-worn' | 'confidence'>('recent');
  const [selectedItem, setSelectedItem] = useState<ClothingItem | null>(null);
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);

  // Live model backend query
  const apiState = useAsync(listItems, [version]);

  // Ajout : l'Obj1 reconnaît la photo, puis les caractéristiques saisies (champs non « Auto ») remplacent sa détection
  async function handleAdd(file: File, patch: ItemPatch) {
    setBusy(true);
    setError('');
    try {
      if (useDemoData) {
        const colour = patch.colour?.length ? patch.colour : ['beige'];
        const slot = patch.slot || 'top';
        addWardrobeItem({
          id: `it_${Date.now()}`, name: patch.name || 'Nouvelle pièce', type: patch.type, slot, category: slot,
          colour, color: colour[0], season: patch.season || 'all', usage: patch.usage || 'Casual',
          formality: patch.formality ?? 1, warmth: patch.warmth ?? 1, traditional: !!patch.traditional,
          imageUrl: URL.createObjectURL(file), imageCrop: URL.createObjectURL(file),
          source: 'user_corrected', confidence: { slot: 1, colour: 1, type: 1 },
        });
      } else {
        const created = await addItem(file);
        if (Object.keys(patch).length) await updateItem(created.id, patch);
        setVersion(v => v + 1);
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(`Impossible d'ajouter la pièce : ${msg}`);
      throw e instanceof Error ? e : new Error(msg);
    } finally {
      setBusy(false);
    }
  }

  // Modifier / supprimer : passerelle (PUT / DELETE /wardrobe/items/{id}) en mode API, état local en mode démo
  async function handleSave(id: string, patch: ItemPatch): Promise<ClothingItem | void> {
    if (useDemoData) {
      updateWardrobeItem(id, { ...patch, ...(patch.colour ? { color: patch.colour[0] } : {}), ...(patch.slot ? { category: patch.slot } : {}) });
      const it = demoWardrobe.find(i => i.id === id);
      return it ? { ...it, ...patch, source: 'user_corrected' } : undefined;
    }
    const updated = await updateItem(id, patch);
    setVersion(v => v + 1);
    return updated;
  }

  async function handleDelete(id: string) {
    if (useDemoData) { removeWardrobeItem(id); return; }
    await deleteItem(id);
    setVersion(v => v + 1);
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
      // chaque mot doit apparaître dans au moins un champ : nom, emplacement, type, couleurs, usage, saison, style, id
      const words = searchQuery.toLowerCase().split(/\s+/).filter(Boolean);
      items = items.filter(i => {
        const text = [i.name, i.slot, i.type, i.color, ...(i.colour || []), i.usage, i.season, i.style, i.id,
                      i.traditional ? 'traditionnel traditional' : ''].filter(Boolean).join(' ').toLowerCase();
        return words.every(w => text.includes(w));
      });
    }

    if (sortBy === 'recent') {
      items.sort((a, b) => b.id.localeCompare(a.id, undefined, { numeric: true }));   // identifiants croissants à l'ajout
    } else if (sortBy === 'name') {
      items.sort((a, b) => (a.name || '').localeCompare(b.name || '', 'fr'));
    } else if (sortBy === 'most-worn') {
      items.sort((a, b) => (b.wearCount || 0) - (a.wearCount || 0));
    } else if (sortBy === 'least-worn') {
      items.sort((a, b) => (a.wearCount || 0) - (b.wearCount || 0));
    } else if (sortBy === 'confidence') {
      items.sort((a, b) => (a.source === 'user_corrected' ? 2 : a.confidence?.slot ?? 1) - (b.source === 'user_corrected' ? 2 : b.confidence?.slot ?? 1));
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
            Toutes vos pièces au même endroit : ajoutez une photo, nous reconnaissons le vêtement pour vous.
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
            <option value="recent">Récemment ajouté</option>
            <option value="name">Nom (A → Z)</option>
            {useDemoData && <option value="most-worn">Plus porté</option>}
            {useDemoData && <option value="least-worn">Moins porté</option>}
            <option value="confidence">À vérifier en premier</option>
          </select>
        </div>
      </section>

      {/* Grid of Items */}
      {searchQuery.trim() && (
        <p style={{ fontSize: '0.86rem', color: 'var(--muted)', margin: '0 0 12px' }}>
          {filteredItems.length} résultat(s) pour « {searchQuery} » ·{' '}
          <button className="btn-sm btn-secondary" style={{ borderRadius: '999px', fontSize: '0.76rem' }} onClick={() => setSearchQuery('')}>
            Effacer la recherche
          </button>
        </p>
      )}

      {!useDemoData && apiState.error ? (
        <EmptyState text={`Garde-robe indisponible : ${apiState.error.message}`} endpoint="GET /wardrobe/items" />
      ) : filteredItems.length > 0 ? (
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
        onSave={handleSave}
        onDelete={handleDelete}
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
