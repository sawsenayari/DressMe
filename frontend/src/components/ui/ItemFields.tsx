// Champs d'une fiche ItemCard v1, partagés par l'ajout (AddItemModal) et la modification (ItemDetailModal),
// avec les valeurs du contrat commun (Obj1) et leurs libellés français pour l'affichage.
import type { ClothingItem, Season, Slot, UsageType } from '../../types';
import type { ItemPatch } from '../../services/wardrobe';

export const SLOT_OPTIONS: { id: Slot; label: string }[] = [
  { id: 'top', label: 'Haut' }, { id: 'bottom', label: 'Bas' }, { id: 'onepiece', label: 'Robe / pièce unique' },
  { id: 'outer', label: 'Veste / manteau' }, { id: 'footwear', label: 'Chaussures' }, { id: 'bag', label: 'Sac' },
  { id: 'accessory', label: 'Accessoire' },
];
export const SEASON_OPTIONS: { id: Season; label: string }[] = [
  { id: 'all', label: 'Toutes saisons' }, { id: 'spring', label: 'Printemps' }, { id: 'summer', label: 'Été' },
  { id: 'autumn', label: 'Automne' }, { id: 'winter', label: 'Hiver' },
];
export const USAGE_OPTIONS: { id: UsageType; label: string }[] = [
  { id: 'Casual', label: 'Décontracté' }, { id: 'Smart Casual', label: 'Smart casual' }, { id: 'Formal', label: 'Formel' },
  { id: 'Sports', label: 'Sport' }, { id: 'Ethnic', label: 'Traditionnel' }, { id: 'Party', label: 'Soirée' },
];
// Vocabulaire de couleurs de l'Obj1 (taxonomy.COLOR_MAP) : seules valeurs comprises par les objectifs 3, 5 et 6
export const COLOUR_OPTIONS: { id: string; label: string }[] = [
  { id: 'black', label: 'Noir' }, { id: 'white', label: 'Blanc' }, { id: 'grey', label: 'Gris' }, { id: 'beige', label: 'Beige / crème' },
  { id: 'brown', label: 'Marron' }, { id: 'blue', label: 'Bleu' }, { id: 'red', label: 'Rouge' }, { id: 'pink', label: 'Rose' },
  { id: 'purple', label: 'Violet / lavande' }, { id: 'orange', label: 'Orange' }, { id: 'yellow', label: 'Jaune' },
  { id: 'green', label: 'Vert' }, { id: 'metallic', label: 'Doré / argenté' }, { id: 'multicolor', label: 'Multicolore' },
];
export const FORMALITY_OPTIONS = ['0 · Décontracté / sport', '1 · Quotidien', '2 · Soigné / bureau', '3 · Très habillé'];
export const WARMTH_OPTIONS = ['0 · Très léger (été)', '1 · Léger', '2 · Mi-saison', '3 · Chaud', '4 · Très chaud (hiver)'];
const TYPE_SUGGESTIONS = ['Tshirts', 'Shirts', 'Tops', 'Sweaters', 'Sweatshirts', 'Jeans', 'Trousers', 'Shorts', 'Skirts', 'Track Pants',
  'Dresses', 'Jumpsuit', 'Kaftan', 'Jebba', 'Jackets', 'Blazers', 'Coats', 'Casual Shoes', 'Formal Shoes', 'Sports Shoes', 'Sandals',
  'Heels', 'Flats', 'Boots', 'Handbags', 'Belts', 'Watches', 'Scarves', 'Sunglasses', 'Caps'];

const find = <T extends { id: string; label: string }>(opts: T[], id?: string | null) => opts.find(o => o.id === id)?.label;
// Types du catalogue (anglais, Obj1) -> français pour l'affichage ; un type saisi par l'utilisateur reste tel quel
const TYPE_FR: Record<string, string> = {
  tshirts: 'T-shirt', shirts: 'Chemise', tops: 'Haut', sweaters: 'Pull', sweatshirts: 'Sweat', jeans: 'Jean', trousers: 'Pantalon',
  shorts: 'Short', skirts: 'Jupe', 'track pants': 'Jogging', leggings: 'Legging', dresses: 'Robe', jumpsuit: 'Combinaison',
  kaftan: 'Caftan', jebba: 'Jebba', traditional: 'Tenue traditionnelle', other: 'Autre', jackets: 'Veste', blazers: 'Blazer',
  coats: 'Manteau', 'rain jacket': 'Imperméable', 'casual shoes': 'Baskets', 'formal shoes': 'Chaussures de ville',
  'sports shoes': 'Chaussures de sport', sandals: 'Sandales', heels: 'Talons', flats: 'Ballerines', boots: 'Bottes',
  handbags: 'Sac à main', clutches: 'Pochette', belts: 'Ceinture', watches: 'Montre', scarves: 'Écharpe', sunglasses: 'Lunettes de soleil',
  caps: 'Casquette', socks: 'Chaussettes', ties: 'Cravate',
};
export const typeLabel = (t?: string) => (t ? TYPE_FR[t.toLowerCase()] || t : '');
export const slotLabel = (s?: string) => find(SLOT_OPTIONS, s) || s || '—';
export const seasonLabel = (s?: string) => find(SEASON_OPTIONS, s) || s || '—';
export const usageLabel = (u?: string) => find(USAGE_OPTIONS, u) || u || '—';
export const colourLabel = (c?: string) => find(COLOUR_OPTIONS, c?.toLowerCase()) || c || '—';
export const coloursLabel = (i: Pick<ClothingItem, 'colour' | 'color'>) =>
  (i.colour?.length ? i.colour : [i.color]).filter(Boolean).map(colourLabel).join(' + ');

/** Valeurs du formulaire ; '' = non renseigné (à l'ajout : laissé à la détection de l'Obj1). */
export type ItemForm = {
  name: string; slot: Slot | ''; type: string; colour1: string; colour2: string; season: Season | '';
  usage: UsageType | ''; formality: string; warmth: string; traditional: boolean;
};

export const EMPTY_FORM: ItemForm = {
  name: '', slot: '', type: '', colour1: '', colour2: '', season: '', usage: '', formality: '', warmth: '', traditional: false,
};

export const formFromItem = (i: ClothingItem): ItemForm => ({
  name: i.name || '', slot: i.slot, type: i.type || '', colour1: (i.colour?.[0] || i.color || '').toLowerCase(),
  colour2: (i.colour?.[1] || '').toLowerCase(), season: i.season || 'all', usage: i.usage || '',
  formality: i.formality != null ? String(i.formality) : '', warmth: i.warmth != null ? String(i.warmth) : '',
  traditional: !!i.traditional,
});

/** Patch ItemCard : champs renseignés seulement (ajout) ; full = modification, « traditionnel » toujours envoyé. */
export function patchFromForm(f: ItemForm, full = false): ItemPatch {
  const p: ItemPatch = {};
  if (f.name.trim()) p.name = f.name.trim();
  if (f.slot) p.slot = f.slot;
  if (f.type.trim()) p.type = f.type.trim();
  const colours = [f.colour1, f.colour2].filter(Boolean);
  if (colours.length) p.colour = Array.from(new Set(colours));
  if (f.season) p.season = f.season;
  if (f.usage) p.usage = f.usage;
  if (f.formality !== '') p.formality = Number(f.formality);
  if (f.warmth !== '') p.warmth = Number(f.warmth);
  if (f.traditional || full) p.traditional = f.traditional;
  return p;
}

const lab: React.CSSProperties = { fontSize: '0.72rem', color: 'var(--muted)', textTransform: 'uppercase', display: 'block', marginBottom: '4px' };
const fld: React.CSSProperties = { width: '100%', padding: '8px 10px', borderRadius: '10px', border: '1px solid var(--line)', fontSize: '0.9rem', background: '#FFFFFF' };

interface Props {
  form: ItemForm;
  onChange: (f: ItemForm) => void;
  /** Ajout : chaque champ peut rester « Auto » (détecté par l'Obj1). Modification : valeurs obligatoires. */
  auto?: boolean;
  idPrefix?: string;
}

export function ItemFields({ form, onChange, auto = false, idPrefix = 'f' }: Props) {
  const set = <K extends keyof ItemForm>(k: K, v: ItemForm[K]) => onChange({ ...form, [k]: v });
  const autoOpt = (txt = 'Auto (reconnu sur la photo)') => (auto ? <option value="">{txt}</option> : null);
  const id = (k: string) => `${idPrefix}-${k}`;
  // une valeur existante hors liste (ancienne fiche) reste affichée telle quelle
  const extra = (opts: { id: string }[], v: string) => (v && !opts.some(o => o.id === v) ? <option value={v}>{v}</option> : null);
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
      <div style={{ gridColumn: '1 / -1' }}>
        <label style={lab} htmlFor={id('name')}>Nom{auto ? ' (facultatif)' : ''}</label>
        <input id={id('name')} style={fld} value={form.name} onChange={e => set('name', e.target.value)}
               placeholder={auto ? 'Auto, ex. « Veste en jean bleue »' : 'ex. Veste en jean bleue'} />
      </div>
      <div>
        <label style={lab} htmlFor={id('slot')}>Emplacement</label>
        <select id={id('slot')} style={fld} value={form.slot} onChange={e => set('slot', e.target.value as Slot | '')}>
          {autoOpt()}
          {SLOT_OPTIONS.map(o => <option key={o.id} value={o.id}>{o.label}</option>)}
        </select>
      </div>
      <div>
        <label style={lab} htmlFor={id('type')}>Type</label>
        <input id={id('type')} style={fld} list={id('types')} value={form.type} onChange={e => set('type', e.target.value)}
               placeholder={auto ? 'Auto' : 'ex. Jeans, Blazers'} />
        <datalist id={id('types')}>{TYPE_SUGGESTIONS.map(t => <option key={t} value={t} />)}</datalist>
      </div>
      <div>
        <label style={lab} htmlFor={id('c1')}>Couleur principale</label>
        <select id={id('c1')} style={fld} value={form.colour1} onChange={e => set('colour1', e.target.value)}>
          {auto ? autoOpt() : <option value="" disabled>Choisir…</option>}
          {extra(COLOUR_OPTIONS, form.colour1)}
          {COLOUR_OPTIONS.map(o => <option key={o.id} value={o.id}>{o.label}</option>)}
        </select>
      </div>
      <div>
        <label style={lab} htmlFor={id('c2')}>Couleur secondaire</label>
        <select id={id('c2')} style={fld} value={form.colour2} onChange={e => set('colour2', e.target.value)}>
          <option value="">Aucune</option>
          {extra(COLOUR_OPTIONS, form.colour2)}
          {COLOUR_OPTIONS.map(o => <option key={o.id} value={o.id}>{o.label}</option>)}
        </select>
      </div>
      <div>
        <label style={lab} htmlFor={id('season')}>Saison</label>
        <select id={id('season')} style={fld} value={form.season} onChange={e => set('season', e.target.value as Season | '')}>
          {autoOpt()}
          {SEASON_OPTIONS.map(o => <option key={o.id} value={o.id}>{o.label}</option>)}
        </select>
      </div>
      <div>
        <label style={lab} htmlFor={id('usage')}>Usage</label>
        <select id={id('usage')} style={fld} value={form.usage} onChange={e => set('usage', e.target.value as UsageType | '')}>
          {auto ? autoOpt() : <option value="" disabled>Choisir…</option>}
          {USAGE_OPTIONS.map(o => <option key={o.id} value={o.id}>{o.label}</option>)}
        </select>
      </div>
      <div>
        <label style={lab} htmlFor={id('form')}>Formalité</label>
        <select id={id('form')} style={fld} value={form.formality} onChange={e => set('formality', e.target.value)}>
          {auto ? autoOpt() : <option value="" disabled>Choisir…</option>}
          {FORMALITY_OPTIONS.map((l, n) => <option key={n} value={String(n)}>{l}</option>)}
        </select>
      </div>
      <div>
        <label style={lab} htmlFor={id('warm')}>Chaleur</label>
        <select id={id('warm')} style={fld} value={form.warmth} onChange={e => set('warmth', e.target.value)}>
          {auto ? autoOpt() : <option value="" disabled>Choisir…</option>}
          {WARMTH_OPTIONS.map((l, n) => <option key={n} value={String(n)}>{l}</option>)}
        </select>
      </div>
      <label style={{ gridColumn: '1 / -1', display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.88rem' }}>
        <input type="checkbox" checked={form.traditional} onChange={e => set('traditional', e.target.checked)} />
        🇹🇳 Pièce traditionnelle tunisienne (jebba, kachabia, fouta, kaftan…)
      </label>
    </div>
  );
}
