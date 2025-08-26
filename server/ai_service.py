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
DEFAULT_MODEL = os.environ.get("AI_MODEL", "gemini-2.0-flash")


def ai_enabled() -> bool:
    return bool(os.environ.get("GOOGLE_GENAI_API_KEY"))


class ChatMessage(TypedDict):
    role: str
    content: str


def _call_genai(messages: List[ChatMessage]) -> str:
    key = os.environ.get("GOOGLE_GENAI_API_KEY")
    if not key:
        raise RuntimeError("missing API key")
    url = GENAI_ENDPOINT_TMPL.format(model=DEFAULT_MODEL)
    # Gemini expects 'contents' with parts. We'll map each message to a content entry.
    contents: List[Dict[str, Any]] = []
    for m in messages[-10:]:  # limit token usage
        role = 'user' if m['role'] == 'user' else 'model'
        contents.append({"role": role, "parts": [{"text": m['content']}]})
    payload: Dict[str, Any] = {"contents": contents}
    try:
        r = requests.post(
            url,
            json=payload,
            timeout=25,
            headers={
                'Content-Type': 'application/json',
                'X-Goog-Api-Key': key,
            }
        )
        r.raise_for_status()
    except Exception as e:
        log.warning("AI call failed: %s", e)
        raise
    data = r.json()
    # Navigate typical structure
    try:
        return data['candidates'][0]['content']['parts'][0]['text'].strip()
    except Exception:
        return "(AI response parsing error)"


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
