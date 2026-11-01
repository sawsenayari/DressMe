# DressMe — frontend

React + TypeScript + Vite. Responsive (phone and laptop), no mock data: every screen shows a placeholder until the model backend answers.

## Run
```bash
npm install
cp .env.example .env     # set VITE_API_URL to the model backend
npm run dev
```

## Structure
```
src/
  types/        domain types = contract with the modeling team
  services/     one file per model (DSO); the only place that talks to the backend
  hooks/        useAsync (loading / error / data)
  components/
    layout/     AppShell (sidebar on laptop, tab bar on mobile)
    ui/         Placeholder, EmptyState, DataState, ItemTile, PhotoPicker
  pages/        Today, Wardrobe, DoesItMatch, Gaps, Profile
  styles/       tokens.css (colors, fonts), global.css
```

## Integration points
| Screen | DSO | Request | Response type |
|---|---|---|---|
| Wardrobe | DSO1 | `GET /wardrobe/items`, `POST /wardrobe/items` (multipart `image`) | `ClothingItem[]`, `ClothingItem` |
| Does it match? | DSO2 | `POST /compatibility/score` (multipart `image`) | `CompatibilityResult` |
| Today | DSO3, DSO6 | `GET /outfits/today?occasion=&budget=` | `Outfit` |
| Outfit Studio | DSO3, DSO2 | `POST /outfits/judge` (JSON `item_ids`, `occasion`, `temperatureC?`, `rain?`) | `OutfitJuryResult` |
| Gaps | DSO4 | `GET /gaps` | `GapSuggestion[]` |
| Profile | DSO5 | `GET/PUT /profile` | `StyleProfile` |

Dev requests to `/api/*` are proxied to `VITE_API_URL` (prefix stripped). To change a field name or shape, edit `src/types/index.ts` and the matching service.
