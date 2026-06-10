"""
agent.py

The FitFindr planning loop. Orchestrates the three tools in response to a
natural language user query, passing state between them via a session dict.

Complete tools.py and test each tool in isolation before implementing this file.

Usage (once implemented):
    from agent import run_agent
    from utils.data_loader import get_example_wardrobe

    result = run_agent(
        query="vintage graphic tee under $30, size M",
        wardrobe=get_example_wardrobe(),
    )
    print(result["fit_card"])
    print(result["error"])   # None on success
"""

import re
from typing import Optional

from tools import search_listings, suggest_outfit, create_fit_card


# ── session state ─────────────────────────────────────────────────────────────

def _new_session(query: str, wardrobe: dict) -> dict:
    """
    Initialize and return a fresh session dict for one user interaction.

    The session dict is the single source of truth for everything that happens
    during a run — it stores the original query, parsed parameters, tool results,
    and any error that caused early termination.

    You may add fields to this dict as needed for your implementation.
    """
    return {
        "query": query,              # original user query
        "parsed": {},                # extracted description / size / max_price
        "search_results": [],        # list of matching listing dicts
        "selected_item": None,       # top result, passed into suggest_outfit
        "wardrobe": wardrobe,        # user's wardrobe dict
        "outfit_suggestion": None,   # string returned by suggest_outfit
        "fit_card": None,            # string returned by create_fit_card
        "error": None,               # set if the interaction ended early
    }


# ── planning loop ─────────────────────────────────────────────────────────────

_PRICE_PATTERN = re.compile(
    r"(?:under|below|less than|max(?:imum)?(?: of)?)\s*\$?(\d+(?:\.\d+)?)",
    re.IGNORECASE,
)
_FALLBACK_PRICE_PATTERN = re.compile(r"\$(\d+(?:\.\d+)?)")
_SIZE_PATTERNS = [
    re.compile(
        r"\bsize\s*((?:xxs|xs|s|m|l|xl|xxl)|(?:us\s*)?\d+(?:\.\d+)?|w\d+(?:\s*l\d+)?)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bin\s+((?:xxs|xs|s|m|l|xl|xxl)|(?:us\s*)?\d+(?:\.\d+)?|w\d+(?:\s*l\d+)?)\s+size\b",
        re.IGNORECASE,
    ),
]
_FILLER_PATTERN = re.compile(
    r"\b(i(?:'| a)?m looking for|looking for|find me|show me|need|want|please|something like)\b",
    re.IGNORECASE,
)


def _normalize_size(size_text: Optional[str]) -> Optional[str]:
    """Normalize extracted size text into the formats used in the dataset."""
    if not size_text:
        return None

    cleaned = " ".join(size_text.strip().upper().split())
    if cleaned in {"XXS", "XS", "S", "M", "L", "XL", "XXL"}:
        return cleaned

    numeric = re.fullmatch(r"(?:US\s*)?(\d+(?:\.\d+)?)", cleaned)
    if numeric:
        return numeric.group(1)

    return cleaned


def _extract_max_price(query: str) -> Optional[float]:
    """Parse a user-provided budget like 'under $30'."""
    match = _PRICE_PATTERN.search(query)
    if not match:
        match = _FALLBACK_PRICE_PATTERN.search(query)
    return float(match.group(1)) if match else None


def _extract_size(query: str) -> Optional[str]:
    """Parse simple apparel and shoe size phrases from the query."""
    for pattern in _SIZE_PATTERNS:
        match = pattern.search(query)
        if match:
            return _normalize_size(match.group(1))
    return None


def _extract_description(query: str) -> str:
    """Remove common filters and filler words to isolate the item request."""
    cleaned = re.split(r"[.!?]", query, maxsplit=1)[0]
    cleaned = _PRICE_PATTERN.sub(" ", cleaned)
    cleaned = _FALLBACK_PRICE_PATTERN.sub(" ", cleaned)
    for pattern in _SIZE_PATTERNS:
        cleaned = pattern.sub(" ", cleaned)

    cleaned = _FILLER_PATTERN.sub(" ", cleaned)
    cleaned = re.sub(r"\b(with|for|in)\b\s*$", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"[\s,;/\-]+", " ", cleaned)
    cleaned = cleaned.strip()
    return cleaned or query.strip()


def _parse_query(query: str) -> dict:
    """Extract the search description and optional filters from the query."""
    return {
        "description": _extract_description(query),
        "size": _extract_size(query),
        "max_price": _extract_max_price(query),
        "filters_relaxed": False,
    }


def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Main agent entry point. Runs the FitFindr planning loop for a single
    user interaction and returns the completed session dict.

    Args:
        query:    Natural language user request
                  (e.g., "vintage graphic tee under $30, size M")
        wardrobe: User's wardrobe dict — use get_example_wardrobe() or
                  get_empty_wardrobe() from utils/data_loader.py

    Returns:
        The session dict after the interaction completes. Check session["error"]
        first — if it is not None, the interaction ended early and the other
        output fields (outfit_suggestion, fit_card) will be None.

    The loop parses the request, searches listings, retries once without filters
    when the filtered search is empty, and only proceeds to styling and caption
    generation after a concrete item has been selected.
    """
    session = _new_session(query, wardrobe)

    if not query or not query.strip():
        session["error"] = "Please enter what you're looking for."
        return session

    parsed = _parse_query(query)
    session["parsed"] = parsed

    results = search_listings(
        parsed["description"],
        size=parsed["size"],
        max_price=parsed["max_price"],
    )

    if not results and (parsed["size"] is not None or parsed["max_price"] is not None):
        results = search_listings(parsed["description"])
        if results:
            parsed["filters_relaxed"] = True

    session["search_results"] = results
    if not results:
        filters = []
        if parsed["size"]:
            filters.append(f"size {parsed['size']}")
        if parsed["max_price"] is not None:
            filters.append(f"under ${parsed['max_price']:.0f}")

        filter_text = f" with {' and '.join(filters)}" if filters else ""
        session["error"] = (
            f"No listings found for '{parsed['description']}'{filter_text}. "
            "Try a broader style keyword or remove a filter."
        )
        return session

    session["selected_item"] = results[0]
    session["outfit_suggestion"] = suggest_outfit(session["selected_item"], wardrobe)
    session["fit_card"] = create_fit_card(
        session["outfit_suggestion"],
        session["selected_item"],
    )
    return session


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

    print("=== Happy path: graphic tee ===\n")
    session = run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    )
    if session["error"]:
        print(f"Error: {session['error']}")
    else:
        print(f"Found: {session['selected_item']['title']}")
        print(f"\nOutfit: {session['outfit_suggestion']}")
        print(f"\nFit card: {session['fit_card']}")

    print("\n\n=== No-results path ===\n")
    session2 = run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    )
    print(f"Error message: {session2['error']}")
