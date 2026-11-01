"""Assistant conversationnel = agent à outils. Le LLM décide quels outils appeler (function calling), en local ou via MCP."""
import json, os, sys
from pathlib import Path
from .agent import _post
from .tools import DISPATCH, TOOL_SPECS

PROMPT = """Tu es l'assistant DressMe (mode, Tunisie). Réponds en français, de façon concise.
Méthode : 1) get_weather pour la ville (Tunis si non précisée) ; 2) search_dress_code pour le contexte culturel ou l'occasion ;
3) recommend_outfits avec l'occasion et la météo obtenues. Ne propose QUE des vêtements renvoyés par recommend_outfits, et signale les alertes.
Genre de l'utilisateur : {gender}."""

async def _loop(question, gender, specs, call, max_steps=6, keep_raw=False):
    msgs = [{"role": "system", "content": PROMPT.format(gender=gender)}, {"role": "user", "content": question}]; trace = []
    for _ in range(max_steps):
        msg = (await _post(msgs, "assistant", specs))["choices"][0]["message"]; calls = msg.get("tool_calls")
        if not calls: return {"answer": msg.get("content") or "", "trace": trace}
        msgs.append({"role": "assistant", "content": msg.get("content") or "", "tool_calls": calls})
        for c in calls:
            name, args = c["function"]["name"], json.loads(c["function"]["arguments"] or "{}")
            try: out = await call(name, args)
            except Exception as e: out = {"error": repr(e)}
            out = out if isinstance(out, str) else json.dumps(out, ensure_ascii=False)
            trace.append({"tool": name, "args": args, "result": out[:300], **({"raw": out} if keep_raw else {})})   # raw : sortie complète (évaluation)
            msgs.append({"role": "tool", "tool_call_id": c["id"], "name": name, "content": out})
    return {"answer": "(nombre maximal d'étapes atteint)", "trace": trace}

async def run_assistant(question, gender="Women", uid="anon", wardrobe=None, use_mcp=False, keep_raw=False):
    if not use_mcp:
        async def local(name, args):
            if name == "recommend_outfits": args = {**args, "gender": args.get("gender", gender), "wardrobe": wardrobe, "uid": uid}
            return await DISPATCH[name](**args)
        return {**await _loop(question, gender, TOOL_SPECS, local, keep_raw=keep_raw), "mcp": False}
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    params = StdioServerParameters(command=sys.executable, args=["-m", "app.mcp_server"], cwd=str(Path(__file__).parent.parent), env=dict(os.environ))
    async with stdio_client(params) as (r, w), ClientSession(r, w) as s:
        await s.initialize()
        specs = [{"type": "function", "function": {"name": t.name, "description": t.description or "", "parameters": t.inputSchema}} for t in (await s.list_tools()).tools]  # découverte dynamique
        async def remote(name, args): return "".join(getattr(c, "text", "") for c in (await s.call_tool(name, args)).content)
        return {**await _loop(question, gender, specs, remote, keep_raw=keep_raw), "mcp": True}
