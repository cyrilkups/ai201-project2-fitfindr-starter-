"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Complete and test each tool before moving to agent.py.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import os
import re
from typing import Optional

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - depends on local environment
    def load_dotenv():
        return False

try:
    from groq import Groq
except ImportError:  # pragma: no cover - depends on local environment
    Groq = None

from utils.data_loader import load_listings

load_dotenv()


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """
    Initialize and return a Groq client using GROQ_API_KEY from .env.

    Returns None if the Groq SDK is unavailable or no API key is configured.
    """
    if Groq is None:
        return None

    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return None
    return Groq(api_key=api_key)


def _tokenize(text: str) -> set[str]:
    """Lowercase tokenization that keeps alphanumeric words."""
    return set(re.findall(r"[a-z0-9]+", (text or "").lower()))


def _format_price(value) -> str:
    """Format a numeric price consistently for captions and UI."""
    if isinstance(value, (int, float)):
        return f"${value:.2f}"
    return "a great price"


def _infer_categories(keywords: set[str]) -> set[str]:
    """Infer likely listing categories from product words in the query."""
    category_hints = {
        "tops": {
            "tee", "shirt", "hoodie", "sweater", "tank", "blouse",
            "cardigan", "cami", "top", "flannel",
        },
        "bottoms": {
            "jeans", "pants", "trousers", "shorts", "skirt", "bottoms",
            "denim",
        },
        "outerwear": {
            "jacket", "coat", "windbreaker", "blazer", "bomber",
            "outerwear",
        },
        "shoes": {
            "boots", "boot", "sneakers", "sneaker", "loafers", "loafer",
            "heels", "heel", "mary", "janes", "mules", "shoe", "shoes",
        },
        "accessories": {
            "bag", "belt", "hat", "scarf", "beanie", "accessory",
            "accessories",
        },
    }

    return {
        category
        for category, hints in category_hints.items()
        if keywords & hints
    }


def _matches_size(listing_size: str, requested_size: Optional[str]) -> bool:
    """Match common apparel and shoe size formats without false positives."""
    if not requested_size:
        return True

    requested = requested_size.strip().upper()
    listing = (listing_size or "").strip().upper()
    if not listing:
        return False

    tokens = {
        token
        for token in re.split(r"[^A-Z0-9.]+", listing)
        if token
    }

    if requested in {"XXS", "XS", "S", "M", "L", "XL", "XXL"}:
        return requested in tokens

    requested_numeric = re.fullmatch(
        r"(?:US\s*)?(\d+(?:\.\d+)?)",
        requested,
    )
    if requested_numeric:
        listing_numbers = {
            match.group(0)
            for match in re.finditer(r"\d+(?:\.\d+)?", listing)
        }
        return requested_numeric.group(1) in listing_numbers

    if requested in tokens:
        return True

    return requested in listing


def _generate_with_groq(
    prompt: str,
    *,
    max_tokens: int,
    temperature: float,
) -> Optional[str]:
    """Call Groq if available; otherwise return None for fallback handling."""
    client = _get_groq_client()
    if client is None:
        return None

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception:
        return None

    if not response.choices:
        return None

    content = response.choices[0].message.content
    return content.strip() if content else None


def _compatibility_score(new_item: dict, wardrobe_item: dict) -> int:
    """Simple heuristic for ranking wardrobe pieces against the new listing."""
    new_tags = {tag.lower() for tag in new_item.get("style_tags", [])}
    wardrobe_tags = {tag.lower() for tag in wardrobe_item.get("style_tags", [])}
    new_colors = {color.lower() for color in new_item.get("colors", [])}
    wardrobe_colors = {color.lower() for color in wardrobe_item.get("colors", [])}

    score = 0
    score += len(new_tags & wardrobe_tags) * 3
    score += len(new_colors & wardrobe_colors) * 2

    if wardrobe_item.get("category") != new_item.get("category"):
        score += 1

    return score


def _pick_best_item(
    wardrobe_items: list[dict],
    new_item: dict,
    allowed_categories: set[str],
    used_ids: set[str],
) -> Optional[dict]:
    """Choose the strongest wardrobe match from the requested categories."""
    candidates = [
        item for item in wardrobe_items
        if item.get("category") in allowed_categories
        and item.get("id") not in used_ids
    ]
    if not candidates:
        return None

    return max(
        candidates,
        key=lambda item: (
            _compatibility_score(new_item, item),
            item.get("name", ""),
        ),
    )


def _fallback_outfit(new_item: dict, wardrobe: dict) -> str:
    """Deterministic styling advice for offline or missing-key scenarios."""
    wardrobe_items = wardrobe.get("items", [])
    title = new_item.get("title", "this piece")
    category = new_item.get("category", "item")
    colors = ", ".join(new_item.get("colors", [])) or "neutral tones"
    vibes = ", ".join(new_item.get("style_tags", [])[:2]) or "easygoing"

    if not wardrobe_items:
        if category == "tops":
            return (
                f"Use {title} as the focal point and ground it with relaxed denim "
                f"or straight-leg trousers in a neutral wash. Add clean sneakers "
                f"or chunky boots so the {colors} palette still feels balanced "
                f"and {vibes}."
            )
        if category == "bottoms":
            return (
                f"Build around {title} with a fitted baby tee, ribbed tank, or "
                f"soft knit in cream, black, or white. Finish with sneakers or "
                f"loafers and a cropped jacket to keep the silhouette intentional."
            )
        if category == "shoes":
            return (
                f"Let {title} lead the outfit with relaxed jeans or a midi skirt "
                f"plus a simple tee or knit on top. Keep the rest of the palette "
                f"pared back so the footwear still feels like the statement."
            )
        return (
            f"Style {title} with simple staples in black, white, denim, or other "
            f"muted neutrals so the {vibes} details stand out. A clean base and "
            f"one textured layer will make the outfit feel finished."
        )

    preferred_categories = {
        "tops": [{"bottoms"}, {"outerwear"}, {"shoes", "accessories"}],
        "bottoms": [{"tops"}, {"outerwear"}, {"shoes", "accessories"}],
        "outerwear": [{"tops"}, {"bottoms"}, {"shoes", "accessories"}],
        "shoes": [{"tops"}, {"bottoms"}, {"outerwear"}],
        "accessories": [{"tops"}, {"bottoms"}, {"outerwear"}],
    }

    used_ids: set[str] = set()
    chosen_items: list[dict] = []
    for category_group in preferred_categories.get(category, [{"tops"}, {"bottoms"}]):
        match = _pick_best_item(wardrobe_items, new_item, category_group, used_ids)
        if match:
            chosen_items.append(match)
            used_ids.add(match.get("id"))

    if not chosen_items:
        return (
            f"Start with {title} and pair it with the most versatile basics in "
            f"your wardrobe so the {vibes} styling still feels cohesive."
        )

    names = [item.get("name", "a favorite piece") for item in chosen_items]
    lead = f"Start with {title} and pair it with your {names[0]}"
    if len(names) >= 2:
        lead += f", then layer in {names[1]}"
    if len(names) >= 3:
        lead += f" and finish with {names[2]}"
    lead += "."

    shared_tags = sorted(
        {
            tag.lower()
            for item in chosen_items
            for tag in item.get("style_tags", [])
            if tag.lower() in {style.lower() for style in new_item.get("style_tags", [])}
        }
    )
    style_reason = ", ".join(shared_tags[:2]) or vibes

    return (
        f"{lead} The mix works because the colors stay close to {colors} and the "
        f"styling leans into {style_reason}, so the outfit feels intentional "
        f"instead of overdone."
    )


def _fallback_fit_card(outfit: str, new_item: dict) -> str:
    """Create a short caption when Groq is unavailable."""
    title = new_item.get("title", "this find")
    price = _format_price(new_item.get("price"))
    platform = new_item.get("platform", "a resale app")
    vibe = new_item.get("style_tags", ["secondhand"])
    mood = vibe[0] if vibe else "secondhand"
    return (
        f"Just found {title} for {price} on {platform}, and it instantly gave the "
        f"whole outfit a {mood} vibe. {outfit}"
    )


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: Optional[str] = None,
    max_price: Optional[float] = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for
                     (e.g., "vintage graphic tee").
        size:        Size string to filter by, or None to skip size filtering.
                     Matching is case-insensitive (e.g., "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts, sorted by relevance (best match first).
        Returns an empty list if nothing matches — does NOT raise an exception.

    Each listing dict has the following fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand, platform

    TODO:
        1. Load all listings with load_listings().
        2. Filter by max_price and size (if provided).
        3. Score each remaining listing by keyword overlap with `description`.
        4. Drop any listings with a score of 0 (no relevant matches).
        5. Sort by score, highest first, and return the listing dicts.

    Before writing code, fill in the Tool 1 section of planning.md.
    """
    if not description or not description.strip():
        return []

    listings = load_listings()
    keywords = _tokenize(description)
    query_text = description.lower()
    desired_categories = _infer_categories(keywords)

    scored_listings = []
    for listing in listings:
        if max_price is not None and listing["price"] > max_price:
            continue

        if not _matches_size(listing.get("size", ""), size):
            continue

        score = 0
        matched_keywords = set()

        title_lower = listing["title"].lower()
        for keyword in keywords:
            if keyword in title_lower:
                score += 5
                matched_keywords.add(keyword)

        desc_lower = listing["description"].lower()
        for keyword in keywords:
            if keyword in desc_lower:
                score += 2
                matched_keywords.add(keyword)

        for tag in listing["style_tags"]:
            if tag.lower() in keywords or any(kw in tag.lower() for kw in keywords):
                score += 3
                matched_keywords.update(kw for kw in keywords if kw in tag.lower())

        for color in listing.get("colors", []):
            if color.lower() in keywords:
                score += 1
                matched_keywords.add(color.lower())

        if desired_categories and listing.get("category") in desired_categories:
            score += 4

        if query_text and query_text in title_lower:
            score += 6

        if matched_keywords:
            scored_listings.append((score, listing))

    scored_listings.sort(key=lambda x: (-x[0], x[1]["price"]))
    return [listing for _, listing in scored_listings]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key containing a list of
                  wardrobe item dicts. May be empty — handle this gracefully.

    Returns:
        A non-empty string with outfit suggestions.
        If the wardrobe is empty, offer general styling advice for the item
        rather than raising an exception or returning an empty string.

    TODO:
        1. Check whether wardrobe['items'] is empty.
        2. If empty: call the LLM with a prompt for general styling ideas
           (what kinds of items pair well, what vibe it suits, etc.).
        3. If not empty: format the wardrobe items into a prompt and ask
           the LLM to suggest specific outfit combinations using the new item
           and named pieces from the wardrobe.
        4. Return the LLM's response as a string.

    Before writing code, fill in the Tool 2 section of planning.md.
    """
    wardrobe_items = wardrobe.get("items", [])

    if not wardrobe_items:
        prompt = f"""A user is considering buying this thrifted item:

Title: {new_item.get('title')}
Colors: {', '.join(new_item.get('colors', []))}
Style tags: {', '.join(new_item.get('style_tags', []))}
Category: {new_item.get('category')}

The user has an empty wardrobe and is just starting out. Suggest what types of basic items would pair well with this piece to create a complete outfit. Be specific about silhouettes, colors, and occasions. Keep it to 3–4 sentences."""
    else:
        wardrobe_text = "\n".join(
            f"- {item.get('name')} ({item.get('category')}) — colors: {', '.join(item.get('colors', []))}; styles: {', '.join(item.get('style_tags', []))}"
            for item in wardrobe_items
        )
        prompt = f"""A user is considering buying this thrifted item:

Title: {new_item.get('title')}
Colors: {', '.join(new_item.get('colors', []))}
Style tags: {', '.join(new_item.get('style_tags', []))}
Category: {new_item.get('category')}
Description: {new_item.get('description')}

Their existing wardrobe contains:
{wardrobe_text}

Suggest 1–2 specific outfit combinations using this new item with pieces from their wardrobe. Name the actual pieces from their wardrobe and explain why the colors, styles, and silhouettes work together. Keep it to 3–5 sentences and sound like a friendly styling expert."""

    suggestion = _generate_with_groq(
        prompt,
        max_tokens=300,
        temperature=0.4,
    )
    return suggestion if suggestion else _fallback_outfit(new_item, wardrobe)


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 2–4 sentence string usable as an Instagram/TikTok caption.
        If outfit is empty or missing, return a descriptive error message
        string — do NOT raise an exception.

    The caption should:
    - Feel casual and authentic (like a real OOTD post, not a product description)
    - Mention the item name, price, and platform naturally (once each)
    - Capture the outfit vibe in specific terms
    - Sound different each time for different inputs (use higher LLM temperature)

    TODO:
        1. Guard against an empty or whitespace-only outfit string.
        2. Build a prompt that gives the LLM the item details and the outfit,
           and asks for a caption matching the style guidelines above.
        3. Call the LLM and return the response.

    Before writing code, fill in the Tool 3 section of planning.md.
    """
    if not outfit or not outfit.strip():
        title = new_item.get("title", "New find")
        return (
            f"I couldn't generate a full fit card because the outfit details were "
            f"missing. {title} is still a strong secondhand pickup on its own."
        )

    prompt = f"""Write a short, authentic Instagram/TikTok caption (2–4 sentences) for this outfit. Sound like a real person posting their OOTD, not a robot or brand account.

Thrifted item: {new_item.get('title')}
Price: ${new_item.get('price')}
Platform: {new_item.get('platform')}
Colors: {', '.join(new_item.get('colors', []))}
Style vibes: {', '.join(new_item.get('style_tags', []))}

Outfit details: {outfit}

Mention the item name, price, and where it's from naturally. Capture the outfit's vibe (e.g., grunge, cottagecore, minimal, y2k). You can use 1–2 emojis if it feels right. Keep it casual and genuine — like you're excited to share this thrift find."""

    caption = _generate_with_groq(
        prompt,
        max_tokens=200,
        temperature=0.9,
    )
    return caption if caption else _fallback_fit_card(outfit, new_item)
