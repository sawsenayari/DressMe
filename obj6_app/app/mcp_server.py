"""Serveur MCP DressMe : expose les outils à tout client MCP (Claude Desktop, agents…). Lancement : python -m app.mcp_server"""
from mcp.server.fastmcp import FastMCP
from . import tools

mcp = FastMCP("dressme")

@mcp.tool()
async def get_weather(city: str = "Tunis") -> dict:
    """Météo du jour (température ressentie, pluie, vent) pour une ville tunisienne."""
    return await tools.get_weather(city)

@mcp.tool()
async def search_dress_code(query: str) -> list:
    """Cherche des usages vestimentaires tunisiens (mariage, aïd, soutenance, chaleur, pluie…)."""
    return await tools.search_dress_code(query)

@mcp.tool()
async def recommend_outfits(occasion: str, feels_like: float, gender: str = "Women", rain_prob: float = 0.0, k: int = 3) -> dict:
    """Propose des tenues complètes (accessoires et alertes) pour une occasion (casual, work, formal, sport, wedding, religious, party)."""
    return await tools.recommend_outfits(occasion, feels_like, gender, rain_prob, k)

if __name__ == "__main__": mcp.run()
