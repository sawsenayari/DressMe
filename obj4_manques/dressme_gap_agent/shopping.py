"""Find live shopping options for ranked wardrobe gaps with Tavily."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
from typing import Any
from html.parser import HTMLParser
from urllib.request import Request, urlopen


class ShoppingSearchError(RuntimeError):
    """Raised when a configured shopping search cannot be completed."""


class _OpenGraphImageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.image_url: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() != "meta" or self.image_url:
            return
        attributes = {key.casefold(): value for key, value in attrs}
        property_name = (attributes.get("property") or attributes.get("name") or "").casefold()
        content = attributes.get("content")
        if property_name in {"og:image", "twitter:image"} and content:
            self.image_url = content


@dataclass(frozen=True)
class ShoppingSearchConfig:
    api_key: str
    endpoint: str = "https://api.tavily.com/search"
    timeout_seconds: float = 20.0

    @classmethod
    def from_env(cls) -> "ShoppingSearchConfig":
        api_key = os.getenv("DRESSME_TAVILY_API_KEY", "").strip()
        if not api_key:
            raise ShoppingSearchError(
                "Set DRESSME_TAVILY_API_KEY to use live shopping search."
            )
        endpoint = os.getenv(
            "DRESSME_TAVILY_ENDPOINT",
            "https://api.tavily.com/search",
        ).strip()
        if not endpoint.startswith("https://"):
            raise ShoppingSearchError("DRESSME_SEARCH_ENDPOINT must use HTTPS.")
        return cls(api_key=api_key, endpoint=endpoint)


_PRICE_PATTERN = re.compile(
    r"(?P<symbol>[$€£])\s?(?P<amount>\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?|\d+(?:[.,]\d{1,2})?)"
    r"|(?P<amount_before>\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?|\d+(?:[.,]\d{1,2})?)\s?(?P<code>USD|EUR|GBP)",
    re.IGNORECASE,
)


def _extract_price(text: str) -> tuple[float | None, str | None]:
    matches = list(_PRICE_PATTERN.finditer(text))
    if not matches:
        return None, None
    prices = []
    for match in matches:
        raw_amount = match.group("amount") or match.group("amount_before")
        if "," in raw_amount and len(raw_amount.rsplit(",", 1)[1]) == 3:
            raw_amount = raw_amount.replace(",", "")
        else:
            raw_amount = raw_amount.replace(",", ".")
        prices.append((
            float(raw_amount),
            (match.group("symbol") or match.group("code")).upper(),
        ))
    return min(prices, key=lambda item: item[0])


def _search_query(gap: dict[str, Any]) -> str:
    description = gap.get("description")
    if not isinstance(description, str) or not description.strip():
        raise ShoppingSearchError("Every gap must contain a non-empty description.")
    return f"{description.strip()} buy online"


def _read_json(request: Request, timeout_seconds: float) -> dict[str, Any]:
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            if response.status < 200 or response.status >= 300:
                raise ShoppingSearchError(f"Shopping search returned HTTP {response.status}.")
            payload = json.loads(response.read().decode("utf-8"))
    except ShoppingSearchError:
        raise
    except Exception as exc:
        raise ShoppingSearchError("Shopping search request failed.") from exc
    if not isinstance(payload, dict):
        raise ShoppingSearchError("Shopping search returned an invalid response.")
    return payload


def _find_page_image(url: str) -> str | None:
    request = Request(url, headers={"User-Agent": "DressMe-gap-detector/1.0"})
    try:
        with urlopen(request, timeout=5) as response:
            content_type = response.headers.get("Content-Type", "")
            if "text/html" not in content_type.casefold():
                return None
            parser = _OpenGraphImageParser()
            parser.feed(response.read(256_000).decode("utf-8", errors="ignore"))
            return parser.image_url if parser.image_url and parser.image_url.startswith("https://") else None
    except Exception:
        return None


def search_gap(
    gap: dict[str, Any],
    config: ShoppingSearchConfig,
    *,
    max_results: int = 5,
    max_price: float | None = None,
) -> list[dict[str, Any]]:
    if not 1 <= max_results <= 20:
        raise ValueError("max_results must be between 1 and 20.")
    if max_price is not None and max_price < 0:
        raise ValueError("max_price must be non-negative.")
    query = _search_query(gap)
    body = json.dumps({
        "query": query,
        "search_depth": "basic",
        "topic": "general",
        "max_results": max_results,
        "include_answer": False,
        "include_raw_content": False,
        "include_images": True,
        "exclude_domains": ["youtube.com", "youtu.be"],
    }).encode("utf-8")
    request = Request(
        config.endpoint,
        data=body,
        method="POST",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config.api_key}",
            "User-Agent": "DressMe-gap-detector/1.0",
        },
    )
    payload = _read_json(request, config.timeout_seconds)
    raw_results = payload.get("results", [])
    top_level_images = payload.get("images", [])
    if not isinstance(raw_results, list):
        raise ShoppingSearchError("Shopping search returned malformed web results.")
    if not isinstance(top_level_images, list):
        top_level_images = []
    options = []
    for result_index, raw in enumerate(raw_results):
        if not isinstance(raw, dict):
            continue
        title = raw.get("title")
        url = raw.get("url")
        snippet = raw.get("content", "")
        if not isinstance(title, str) or not isinstance(url, str) or not url.startswith("https://"):
            continue
        if any(domain in url.casefold() for domain in ("youtube.com/", "youtu.be/")):
            continue
        if not isinstance(snippet, str):
            snippet = ""
        price, currency = _extract_price(f"{title} {snippet}")
        if max_price is not None and (price is None or price > max_price):
            continue
        image_url = raw.get("image_url")
        result_images = raw.get("images", [])
        if not image_url and isinstance(result_images, list):
            for image in result_images:
                candidate_url = image.get("url") if isinstance(image, dict) else image
                if isinstance(candidate_url, str) and candidate_url.startswith("https://"):
                    image_url = candidate_url
                    break
        if not image_url:
            if result_index < len(top_level_images):
                image = top_level_images[result_index]
                candidate_url = image.get("url") if isinstance(image, dict) else image
                if isinstance(candidate_url, str) and candidate_url.startswith("https://"):
                    image_url = candidate_url
        if not isinstance(image_url, str) or not image_url.startswith("https://"):
            image_url = _find_page_image(url)
        option = {
            "title": title,
            "url": url,
            "snippet": snippet,
            "price": price,
            "currency": currency,
            "source": "tavily_search",
        }
        if image_url:
            option["image_url"] = image_url
        options.append(option)
    return options


def recommend_products(
    analysis_path: str | Path,
    output_path: str | Path,
    *,
    config: ShoppingSearchConfig | None = None,
    gap_limit: int = 3,
    max_results: int = 5,
    max_price: float | None = None,
) -> dict[str, Any]:
    if not 1 <= gap_limit <= 8:
        raise ValueError("gap_limit must be between 1 and 8.")
    payload = json.loads(Path(analysis_path).read_text(encoding="utf-8"))
    gaps = payload.get("gaps") if isinstance(payload, dict) else None
    if not isinstance(gaps, list):
        raise ShoppingSearchError("Gap analysis must contain a gaps array.")
    search_config = config or ShoppingSearchConfig.from_env()
    recommendations = []
    for gap in gaps[:gap_limit]:
        if not isinstance(gap, dict):
            raise ShoppingSearchError("Gap analysis contains a malformed gap.")
        recommendations.append({
            "gap": gap.get("description"),
            "slot": gap.get("slot"),
            "rank": gap.get("rank"),
            "options": search_gap(
                gap,
                search_config,
                max_results=max_results,
                max_price=max_price,
            ),
        })
    result = {
        "pipeline_version": "shopping-recommendations-v1",
        "status": "complete",
        "source": "tavily_live_web_search",
        "price_filter": max_price,
        "gap_count": len(recommendations),
        "recommendations": recommendations,
    }
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(destination)
    return result


def main() -> int:
    import argparse
    import sys

    from dotenv import load_dotenv

    load_dotenv()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis", default="wardrobe/.dressme-cache/objective2_gap_analysis.json")
    parser.add_argument("--output", default="wardrobe/.dressme-cache/shopping_recommendations.json")
    parser.add_argument("--gap-limit", type=int, default=3)
    parser.add_argument("--max-results", type=int, default=5)
    parser.add_argument("--max-price", type=float, default=None)
    args = parser.parse_args()
    result = recommend_products(
        args.analysis,
        args.output,
        gap_limit=args.gap_limit,
        max_results=args.max_results,
        max_price=args.max_price,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
