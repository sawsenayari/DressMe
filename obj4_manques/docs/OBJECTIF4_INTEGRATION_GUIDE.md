# Objectif 4 integration guide

```python
from dressme_gap_agent.wardrobe_loader import load_wardrobe_from_json
from dressme_gap_agent.compatibility_provider import Objective2CompatibilityProvider
from dressme_gap_agent.embedding_inventory import load_items_with_embeddings

inventory = load_wardrobe_from_json(r"C:\path\to\wardrobe.json")
items = load_items_with_embeddings(
    r"C:\path\to\wardrobe_inventory.json",
    r"C:\path\to\fashionclip_embeddings.npz",
)
provider = Objective2CompatibilityProvider("http://127.0.0.1:8002")
```

Call `provider.score_items(items[:2], items[2:4])`. It sends full items to
`POST /pairs`; each item must contain a 512-value FashionCLIP embedding.
Scores are numeric Objective 2 compatibility scores, not outfit gains.

The mock provider is explicitly non-scientific and exists only for tests and
local orchestration. Use `score_to_verdict` only with a team-approved
calibration; the current thresholds are placeholders. A synthetic candidate
cannot be sent to a real provider until Objective 2 documents how that candidate
ID is registered or represented.

Until synthetic-item registration exists, run
`python -m dressme_gap_agent.candidate_prototypes_cli` to create
`candidate_prototypes.json`. This uses a deterministic same-slot existing
wardrobe image as a proxy and records `proxy_item_id`; any ranking produced
from it must be labelled proxy-based, not a direct visual embedding of the
textual archetype.

## Live shopping options

Shopping recommendations are a separate step after gap ranking. They do not
change compatibility scores or outfit counts. Tavily is used because its free
tier is designed for AI-agent search and returns structured results. Create a
free Tavily API key and configure it without putting it in source control:

```powershell
$env:DRESSME_TAVILY_API_KEY = "your-key"
```

Then search the highest-ranked gaps:

```powershell
python -m dressme_gap_agent.shopping `
  --analysis .\wardrobe\.dressme-cache\objective2_gap_analysis.json `
  --output .\wardrobe\.dressme-cache\shopping_recommendations.json `
  --gap-limit 3 `
  --max-results 5 `
  --max-price 100
```

The output contains the original gap, ranked options, source URLs, snippets,
and prices when the search result exposes one. A price filter excludes results
whose price is unknown or above the configured maximum; web results are not
purchase guarantees, so the application should show the source and let the
user verify availability, shipping, size, and final price.

For a browser interface instead of the CLI, run:

```powershell
python -m dressme_gap_agent.web_app
```

Open `http://127.0.0.1:8765`. The API key remains server-side and is never
sent to the browser.
