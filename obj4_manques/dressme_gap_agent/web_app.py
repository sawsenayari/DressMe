"""Run a local browser UI for testing wardrobe-gap shopping recommendations."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from .shopping import ShoppingSearchError, recommend_products


HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>DressMe gap shopping</title>
  <style>
    :root { color-scheme: light; font-family: system-ui, sans-serif; }
    body { background: #f5f1ed; color: #2b2522; margin: 0; }
    main { max-width: 900px; margin: 0 auto; padding: 32px 18px; }
    h1 { margin-bottom: 6px; }
    .subtle { color: #6f625c; }
    form, .card { background: white; border-radius: 14px; padding: 20px;
      box-shadow: 0 3px 14px #00000012; margin: 18px 0; }
    form { display: grid; grid-template-columns: repeat(3, 1fr) auto;
      gap: 12px; align-items: end; }
    label { display: grid; gap: 6px; font-size: .9rem; }
    input, button { border: 1px solid #cfc3bc; border-radius: 8px; padding: 10px; font: inherit; }
    button { background: #563d35; color: white; cursor: pointer; }
    button:disabled { opacity: .6; cursor: wait; }
    .option { border-top: 1px solid #eee6e1; padding: 14px 0; }
    .product-image { width: 140px; height: 170px; object-fit: cover;
      border-radius: 8px; float: left; margin: 0 14px 8px 0; background: #eee6e1; }
    .option::after { content: ""; display: block; clear: both; }
    .option:first-child { border-top: 0; }
    a { color: #754d3d; font-weight: 650; }
    .price { font-weight: 700; margin: 6px 0; }
    .error { color: #a52e2e; white-space: pre-wrap; }
    @media (max-width: 700px) { form { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
<main>
  <h1>DressMe shopping suggestions</h1>
  <p class="subtle">Search products for the highest-value wardrobe gaps.</p>
  <form id="search-form">
    <label>Gaps to search
      <input id="gap-limit" type="number" min="1" max="8" value="3">
    </label>
    <label>Results per gap
      <input id="max-results" type="number" min="1" max="20" value="5">
    </label>
    <label>Maximum price
      <input id="max-price" type="number" min="0" step="0.01" value="100">
    </label>
    <button id="submit" type="submit">Find options</button>
  </form>
  <p id="status" class="subtle"></p>
  <section id="results"></section>
</main>
<script>
const form = document.querySelector("#search-form");
const button = document.querySelector("#submit");
const status = document.querySelector("#status");
const results = document.querySelector("#results");

function text(value) {
  return document.createTextNode(value ?? "");
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  button.disabled = true;
  status.textContent = "Searching...";
  results.replaceChildren();
  const body = {
    gap_limit: Number(document.querySelector("#gap-limit").value),
    max_results: Number(document.querySelector("#max-results").value),
    max_price: Number(document.querySelector("#max-price").value)
  };
  try {
    const response = await fetch("/api/recommendations", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(body)
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || "Search failed.");
    status.textContent = `${payload.gap_count} gap(s) searched. Verify prices and availability on the retailer page.`;
    for (const recommendation of payload.recommendations) {
      const card = document.createElement("article");
      card.className = "card";
      const heading = document.createElement("h2");
      heading.append(text(`#${recommendation.rank} ${recommendation.gap}`));
      card.append(heading);
      if (!recommendation.options.length) {
        card.append(text("No matching options found under this budget."));
      }
      for (const option of recommendation.options) {
        const item = document.createElement("div");
        item.className = "option";
        const link = document.createElement("a");
        link.href = option.url;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.append(text(option.title));
        item.append(link);
        if (option.image_url) {
          const image = document.createElement("img");
          image.className = "product-image";
          image.src = option.image_url;
          image.alt = option.title;
          image.loading = "lazy";
          image.referrerPolicy = "no-referrer";
          image.onerror = () => image.remove();
          item.append(image);
        }
        const price = document.createElement("div");
        price.className = "price";
        price.append(text(option.price == null ? "Price not detected" :
          `${option.currency} ${option.price}`));
        item.append(price);
        const snippet = document.createElement("div");
        snippet.className = "subtle";
        snippet.append(text(option.snippet));
        item.append(snippet);
        card.append(item);
      }
      results.append(card);
    }
  } catch (error) {
    status.textContent = "";
    const message = document.createElement("p");
    message.className = "error";
    message.append(text(error.message));
    results.append(message);
  } finally {
    button.disabled = false;
  }
});
</script>
</body>
</html>"""


class _Handler(BaseHTTPRequestHandler):
    analysis_path = Path("wardrobe/.dressme-cache/objective2_gap_analysis.json")
    output_path = Path("wardrobe/.dressme-cache/shopping_recommendations.json")

    def _send(self, status: int, payload: str, content_type: str) -> None:
        encoded = payload.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self) -> None:
        if self.path == "/" or self.path == "/index.html":
            self._send(200, HTML, "text/html")
        else:
            self._send(404, json.dumps({"error": "Not found."}), "application/json")

    def do_POST(self) -> None:
        if self.path != "/api/recommendations":
            self._send(404, json.dumps({"error": "Not found."}), "application/json")
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            request = json.loads(self.rfile.read(length))
            result = recommend_products(
                self.analysis_path,
                self.output_path,
                gap_limit=int(request.get("gap_limit", 3)),
                max_results=int(request.get("max_results", 5)),
                max_price=float(request["max_price"]) if request.get("max_price") is not None else None,
            )
            self._send(200, json.dumps(result, ensure_ascii=False), "application/json")
        except (ValueError, KeyError, json.JSONDecodeError, ShoppingSearchError) as exc:
            self._send(400, json.dumps({"error": str(exc)}), "application/json")

    def log_message(self, format: str, *args: Any) -> None:
        return


def main() -> int:
    from dotenv import load_dotenv

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--analysis", default="wardrobe/.dressme-cache/objective2_gap_analysis.json")
    args = parser.parse_args()
    load_dotenv()
    _Handler.analysis_path = Path(args.analysis)
    server = ThreadingHTTPServer((args.host, args.port), _Handler)
    print(f"DressMe UI: http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
