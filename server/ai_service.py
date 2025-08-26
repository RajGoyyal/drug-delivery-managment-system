"""AI helper service for Friendly Med Pal.

Currently integrates (optionally) with Google AI Studio (Gemini) via the
generativelanguage REST API. If no API key is configured, functions return
deterministic heuristic placeholders so the frontend can still render.

Environment variables:
  GOOGLE_GENAI_API_KEY   -> required for real calls
  AI_MODEL               -> defaults to gemini-1.5-flash

Public functions:
  ai_enabled() -> bool
  summarize(context: dict) -> str
  chat_reply(history: list[dict]) -> str

History item format expected by chat_reply:
  {"role": "user"|"assistant", "content": "..."}
"""
from __future__ import annotations

import os, json, logging, textwrap
from typing import List, Dict, Any, TypedDict

import requests

# Exposed for diagnostics (/api/ai/status)
LAST_AI_ERROR: str | None = None

# Lightweight .env loader (avoids extra dependency). Loads before reading defaults so AI_MODEL & key apply.
def _load_env_file():
    filename = os.environ.get("ENV_FILE", ".env")
    candidates = []
    cwd = os.getcwd()
    # Walk up max 3 levels to find .env so running from nested folder still works
    for _ in range(4):
        candidates.append(os.path.join(cwd, filename))
        parent = os.path.dirname(cwd)
        if parent == cwd:
            break
        cwd = parent
    for path in candidates:
        if not os.path.isfile(path):
            continue
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k = k.strip(); v = v.strip()
                    if (k not in os.environ) or (os.environ[k] in ("", "YOUR_KEY_HERE")):
                        os.environ[k] = v
            break  # stop after first successful load
        except Exception:
            continue

_load_env_file()

log = logging.getLogger(__name__)

# IMPORTANT: Never embed static API keys in source. Key is supplied at runtime via env var and HTTP header.
GENAI_ENDPOINT_TMPL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
# Primary + fallbacks (first element may be overridden by AI_MODEL env)
PRIMARY_MODEL = os.environ.get("AI_MODEL", "gemini-2.5-pro")
FALLBACK_MODELS = [m for m in {PRIMARY_MODEL, "gemini-2.5-pro", "gemini-2.0-flash"}]  # set->list dedups


def ai_enabled() -> bool:
    return bool(os.environ.get("GOOGLE_GENAI_API_KEY"))


class ChatMessage(TypedDict):
    role: str
    content: str


def _extract_text(data: Dict[str, Any]) -> str:
    # Try standard structure
    try:
        parts = data['candidates'][0]['content']['parts']
        texts = [p.get('text','') for p in parts if isinstance(p, dict)]
        combined = "\n".join(t for t in texts if t).strip()
        if combined:
            return combined
    except Exception:
        pass
    # Fallback paths
    for path in [
        ['candidates',0,'output'],
        ['candidates',0,'content','parts',0,'text'],
        ['text'],
    ]:
        cur: Any = data
        ok = True
        for key in path:
            if isinstance(key,int):
                if isinstance(cur,list) and len(cur)>key:
                    cur = cur[key]
                else:
                    ok=False; break
            else:
                if isinstance(cur,dict) and key in cur:
                    cur = cur[key]
                else:
                    ok=False; break
        if ok and isinstance(cur,str) and cur.strip():
            return cur.strip()
    return ""


def _call_genai(messages: List[ChatMessage]) -> str:
    key = os.environ.get("GOOGLE_GENAI_API_KEY")
    if not key:
        raise RuntimeError("missing API key")
    # Prepare payload
    contents: List[Dict[str, Any]] = []
    for m in messages[-10:]:  # trim history
        role = 'user' if m['role'] == 'user' else 'model'
        contents.append({"role": role, "parts": [{"text": m['content']}]})
    payload: Dict[str, Any] = {"contents": contents}
    global LAST_AI_ERROR
    last_error: str | None = None
    for model in FALLBACK_MODELS:
        url = GENAI_ENDPOINT_TMPL.format(model=model)
        try:
            r = requests.post(
                url,
                json=payload,
                timeout=30,
                headers={
                    'Content-Type': 'application/json',
                    'X-Goog-Api-Key': key,
                }
            )
            # Server error -> try next
            if r.status_code >= 500:
                last_error = f"{model} server {r.status_code}"
                continue
            data = r.json()
            if 'error' in data:
                msg = data['error'].get('message') if isinstance(data['error'], dict) else data['error']
                last_error = f"{model} error: {msg}"
                continue
            text = _extract_text(data)
            if text:
                if model != FALLBACK_MODELS[0]:
                    log.info("Used fallback model: %s", model)
                LAST_AI_ERROR = None
                return text
            last_error = f"{model} empty response"
        except Exception as e:
            last_error = f"{model} exception: {e}"
            continue
    debug = bool(os.environ.get('DEBUG_AI'))
    LAST_AI_ERROR = last_error
    return f"(AI response parsing error){' '+last_error if last_error else ''}{' – set DEBUG_AI=1 for details' if not debug else ''}"


def summarize(context: Dict[str, Any]) -> str:
    """Produce a natural language operational summary.

    Context keys: stats, insights (optional)
    """
    stats = context.get('stats', {})
    insights = context.get('insights', {})
    base_text = textwrap.dedent(f"""
    Operational snapshot:
      Patients: {stats.get('patients', 'n/a')}
      Drugs: {stats.get('drugs', 'n/a')}
      Deliveries: {stats.get('deliveries', 'n/a')}
      Low stock drugs: {stats.get('low_stock_drugs', 'n/a')}
    """)
    if ai_enabled():
        prompt = (
            "You are an operations assistant. Summarize current medication delivery system status concisely. "
            "Highlight risks, adherence and inventory concerns. Keep under 130 words.\n\n" + base_text +
            "\nInsights JSON: " + json.dumps(insights) + "\nSummary:" )
        try:
            return _call_genai([{"role": "user", "content": prompt}])
        except Exception:
            pass
    # Fallback heuristic summary
    adherence = insights.get('adherence', {}).get('overall_percent')
    recs = insights.get('recommendations', [])
    parts: List[str] = [p for p in [
        base_text.strip(),
        f"Estimated adherence: {adherence}%" if adherence is not None else None,
        ("Top recommendation: " + recs[0]) if recs else None,
        "(AI key not configured – showing heuristic summary)" if not ai_enabled() else None,
    ] if p]
    return "\n".join(parts)


def chat_reply(history: List[ChatMessage]) -> str:
    if ai_enabled():
        try:
            return _call_genai(history)
        except Exception as e:
            log.warning("Falling back to heuristic reply: %s", e)
    # Simple heuristic fallback referencing last user message
    last_user = next((m['content'] for m in reversed(history) if m['role']=='user'), '')
    return (
        "(Heuristic assistant) You asked: " + last_user[:180] + ". "
        "Real AI responses will appear once a Google AI Studio key is configured." )


def answer_with_context(question: str, context: Dict[str, Any]) -> str:
    """RAG-style answer: we build a structured prompt including supplied context.

    Context keys (suggested): stats, patients, drugs, deliveries, inventory_issues, recommendations, risk_patients.
    """
    if ai_enabled():
        prompt = (
            "You are an AI assistant acting as: (1) Operations Analyst, (2) Inventory Manager, (3) Adherence Coach.\n"
            "Use ONLY the provided JSON context to answer the user question. If data is missing, say so and suggest what is needed.\n"
            "Provide answer sections: SUMMARY, DETAILS, RISKS, NEXT_ACTIONS.\n"
            "Be concise (<=220 words). Avoid hallucination.\n"
            f"User question: {question}\n"\
            f"Context JSON: {json.dumps(context, ensure_ascii=False)[:12000]}\n"  # truncate to avoid excessive tokens
            "Answer:"
        )
        try:
            return _call_genai([{"role": "user", "content": prompt}])
        except Exception as e:
            global LAST_AI_ERROR
            LAST_AI_ERROR = f"RAG: {e}"
            log.warning("RAG AI failed: %s", e)
    # Heuristic fallback
    return (
        "(Heuristic RAG) Unable to use live AI. Question: '" + question[:160] + "'. "
        "Key context keys: " + ", ".join(sorted(context.keys())) + "." )
