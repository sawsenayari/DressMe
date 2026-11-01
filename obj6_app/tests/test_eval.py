import json, threading
from http.server import BaseHTTPRequestHandler, HTTPServer

def _mock(monkeypatch, tmp_path):
    class H(BaseHTTPRequestHandler):
        def do_POST(s):
            body_in = json.loads(s.rfile.read(int(s.headers["Content-Length"]))); msgs = body_in["messages"]
            sys_ = msgs[0]["content"] if msgs[0]["role"] == "system" else ""; user = msgs[-1]["content"] if len(msgs) > 1 or not sys_ else ""; ul = user.lower()
            if not sys_:   # ping de check_llm
                msg = {"content": "", "tool_calls": [{"id": "c0", "type": "function", "function": {"name": "get_weather", "arguments": json.dumps({"city": "Tunis"})}}]} if "tools" in body_in else {"content": "<think>je réfléchis {x}</think>{\"ok\": true}"}
                b = json.dumps({"choices": [{"message": msg}]}).encode(); s.send_response(200); s.send_header("Content-Type", "application/json"); s.end_headers(); s.wfile.write(b); return
            if "évaluateur strict" in sys_:
                d = json.loads(user); good = any(a in d["explication"] for a in d["articles"])
                out = dict(pertinence=5, fidelite=5, honnetete=5, clarte=5, commentaire="ok") if good else dict(pertinence=2, fidelite=1, honnetete=2, clarte=5, commentaire="hors contexte")
            elif "groundedness" in sys_: out = {"ungrounded": [], "grounded": True}
            elif "assistant DressMe" in sys_:
                tools = [m for m in msgs if m["role"] == "tool"]; names = [m["name"] for m in tools]
                if not tools: out = None; calls = [("get_weather", {"city": "Tunis"}), ("search_dress_code", {"query": user})]
                elif "recommend_outfits" not in names:
                    occ = "sport" if "foot" in ul else "formal" if "entretien" in ul else "casual"
                    t = json.loads(next(m["content"] for m in tools if m["name"] == "get_weather"))["feels_like"]; out = None; calls = [("recommend_outfits", {"occasion": occ, "feels_like": t, "gender": "Women"})]
                else: out, calls = "Voici des tenues adaptées.", None
            elif "agent de contexte" in sys_:
                occ = "work" if "client" in ul else "sport" if ("foot" in ul or "gym" in ul or "كورة" in ul) else "wedding" if ("mariage" in ul or "فرح" in ul or "wedding" in ul) else "formal" if ("jury" in ul or "entretien" in ul or "interview" in ul) else "casual"
                out = {"occasion": occ, "formality": {"work": 3, "sport": 0, "wedding": 3, "formal": 3, "casual": 1}[occ], "gender": None, "notes": "mock"}
            else:   # styliste
                d = json.loads(user); out = {"explanations": [f"{t['articles'][0]} convient pour {d['contexte']['occasion']}." for t in d["tenues"]]}
            if sys_.find("assistant DressMe") >= 0 and out is None:
                msg = {"content": "", "tool_calls": [{"id": f"c{i}", "type": "function", "function": {"name": n, "arguments": json.dumps(a)}} for i, (n, a) in enumerate(calls)]}
            else: msg = {"content": out if isinstance(out, str) else json.dumps(out, ensure_ascii=False)}
            body = json.dumps({"choices": [{"message": msg}]}).encode(); s.send_response(200); s.send_header("Content-Type", "application/json"); s.end_headers(); s.wfile.write(body)
        def log_message(*a): pass
    srv = HTTPServer(("127.0.0.1", 0), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setenv("LLM_BASE_URL", f"http://127.0.0.1:{srv.server_port}/v1"); monkeypatch.setenv("LLM_MODEL", "m"); monkeypatch.setenv("DRESSME_REPORTS", str(tmp_path))
    return srv

def test_three_evaluations_run_end_to_end(monkeypatch, tmp_path):
    from training import eval_agent, eval_judge, eval_tools
    srv = _mock(monkeypatch, tmp_path)
    ag = eval_agent.main(["--n", "8"])
    assert ag["rag"]["answered_by_llm"] == "8/8" and "occasion_accuracy" in ag["llm"] and ag["rules"]["answered_by_llm"] == "0/8"
    monkeypatch.setenv("LLM_MODEL_JUDGE", "juge-a"); monkeypatch.setenv("LLM_MODEL_JUDGE2", "juge-b")
    ju = eval_judge.main(["--n", "2"])
    assert ju["cases"] == 6 and set(ju["judges"]) == {"juge-a", "juge-b"} and "agreement_between_judges_spearman" in ju
    for v in ju["judges"].values():
        assert v["judge_failures"] == 0 and v["judge_discrimination"] >= .5 and v["mean_scores"]["pertinence"] > v["mean_scores_mismatched_control"]["pertinence"]
    assert (tmp_path / "judge_cases.csv").exists()
    monkeypatch.setattr(eval_tools, "SC", eval_tools.SC[:2]); to = eval_tools.main([]); srv.shutdown()
    assert to["run_errors"] == 0 and to["all_tools"].endswith("(2/2)") and to["order_ok"].endswith("(2/2)") and to["weather_consistent"].endswith("(2/2)")

def test_gold_set_has_no_prompt_leak_and_wilson():
    from app.agent import SYSTEM_PROMPT
    from training.eval_agent import GOLD
    from training.evalkit import wilson
    assert not [g for g in GOLD if g[0] in SYSTEM_PROMPT]
    lo, hi = wilson(18, 36); assert 0.34 < lo < 0.5 < hi < 0.66

def test_check_llm_models_and_json_from(monkeypatch, tmp_path):
    import asyncio
    from app.agent import json_from
    from training import check_llm, eval_models
    assert json_from("<think>{pas du json} réflexion</think> texte {\"a\": {\"b\": 1}} fin") == {"a": {"b": 1}}
    srv = _mock(monkeypatch, tmp_path)
    for k, v in (("LLM_MODEL_AGENDA", "m1"), ("LLM_MODEL_EXPLAIN", "m1"), ("LLM_MODEL_ASSISTANT", "m2"), ("LLM_MODEL_JUDGE", "m3"), ("LLM_MODEL_JUDGE2", "m4")): monkeypatch.setenv(k, v)
    rows = asyncio.run(check_llm.amain())
    assert [r["statut"] for r in rows] == ["OK"] * 5 and rows[2]["appel_d_outils"] == "OK"
    out = eval_models.main(["--models", "x,y", "--n", "6"]); srv.shutdown()
    assert set(out["models"]) == {"x", "y"} and out["recommended_for_agenda"] in ("x", "y")
