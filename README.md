# FitFindr

FitFindr is a small styling agent for secondhand fashion. A user describes what they want in natural language, FitFindr searches a mock listings dataset, chooses the best match, suggests how to style it with the user's wardrobe, and then generates a short social-ready fit card caption.

## Run

### Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file in the project root:

```bash
GROQ_API_KEY=your_key_here
```

### Launch the app

Default Gradio ports may already be busy on some machines. In my local verification, the interface was confirmed at `http://127.0.0.1:8080`.

```bash
GRADIO_SERVER_PORT=8080 python app.py
```

### Run tests

```bash
python -m pytest tests/ -q
```

## Tool Inventory

### `search_listings(description: str, size: Optional[str], max_price: Optional[float]) -> list[dict]`

Purpose:
Find secondhand listings that match the user's request and rank them by relevance.

Inputs:
- `description: str` — the search phrase, such as `"vintage graphic tee"` or `"90s track jacket"`.
- `size: Optional[str]` — optional apparel, shoe, or waist size such as `"M"`, `"8"`, or `"W30 L30"`.
- `max_price: Optional[float]` — optional maximum price in USD.

Output:
- `list[dict]` of ranked listing objects. Each listing includes `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, and `platform`.

Failure behavior:
- Returns `[]` if nothing matches. It does not raise an exception for normal no-results cases.

### `suggest_outfit(new_item: dict, wardrobe: dict) -> str`

Purpose:
Suggest an outfit that uses the chosen listing and the user's current wardrobe.

Inputs:
- `new_item: dict` — the selected listing returned from `search_listings`.
- `wardrobe: dict` — wardrobe data with an `items` list from `utils/data_loader.py`.

Output:
- `str` containing outfit advice. In the happy path, it references named wardrobe pieces. In the fallback path, it gives general styling guidance.

Failure behavior:
- If the wardrobe is empty, it returns general styling advice instead of crashing.
- If the Groq call fails, it falls back to deterministic styling text.

### `create_fit_card(outfit: str, new_item: dict) -> str`

Purpose:
Turn the outfit suggestion into a short caption that sounds like a real thrift or outfit post.

Inputs:
- `outfit: str` — the outfit suggestion returned by `suggest_outfit`.
- `new_item: dict` — the selected listing.

Output:
- `str` caption that mentions the item, price, platform, and vibe.

Failure behavior:
- If `outfit` is empty, it returns a descriptive fallback string.
- If the Groq call fails, it falls back to a deterministic caption.

## Planning Loop

The planning loop lives in [agent.py](/Users/cyrilkups/Desktop/ai201-project2-fitfindr-starter-/agent.py) inside `run_agent()`. It is not just a fixed “call every tool” pipeline; it makes one important branching decision based on the search result.

Step-by-step behavior:
1. Create a fresh `session` dict for this user interaction.
2. Reject empty queries early with `session["error"] = "Please enter what you're looking for."`.
3. Parse the raw query into:
   - `description`
   - `size`
   - `max_price`
   - `filters_relaxed`
4. Call `search_listings(description, size, max_price)`.
5. If search returns results:
   - store them in `session["search_results"]`
   - set `session["selected_item"] = results[0]`
   - call `suggest_outfit(selected_item, wardrobe)`
   - store the result in `session["outfit_suggestion"]`
   - call `create_fit_card(outfit_suggestion, selected_item)`
   - store the result in `session["fit_card"]`
6. If search returns `[]` and the query included a size or price filter:
   - retry once with relaxed filters by calling `search_listings(description)` only
   - if retry succeeds, set `filters_relaxed = True` and continue through the normal success path
7. If search still returns `[]` after the retry:
   - set `session["error"]`
   - return immediately
   - do not call `suggest_outfit`
   - do not call `create_fit_card`

This branching behavior is covered by tests in [tests/test_agent.py](/Users/cyrilkups/Desktop/ai201-project2-fitfindr-starter-/tests/test_agent.py).

## State Management

The state object is a single session dictionary passed through the whole interaction:

```python
session = {
    "query": str,
    "parsed": {
        "description": str,
        "size": str | None,
        "max_price": float | None,
        "filters_relaxed": bool,
    },
    "search_results": list[dict],
    "selected_item": dict | None,
    "wardrobe": dict,
    "outfit_suggestion": str | None,
    "fit_card": str | None,
    "error": str | None,
}
```

Why this matters:
- `selected_item` is the exact listing dict passed into both downstream tools.
- `outfit_suggestion` is the exact string passed into `create_fit_card`.
- the UI only reads the final session; it does not recompute any intermediate values.

I verified this directly and then encoded it in tests that assert:
- the same `selected_item` object reaches both `suggest_outfit` and `create_fit_card`
- the exact `outfit_suggestion` stored in session is the same string passed into `create_fit_card`

## Error Handling

### `search_listings`

Concrete failure:
- Query: `"designer ballgown size XXS under $5"`

Direct tool result:
- `[]`

Agent behavior:
- returns `"No listings found for 'designer ballgown' with size XXS and under $5. Try a broader style keyword or remove a filter."`
- leaves `selected_item = None`
- leaves `fit_card = None`
- never calls downstream tools

### `suggest_outfit`

Concrete failure:
- same listing as happy path, but with `get_empty_wardrobe()`

Behavior:
- returns general advice such as using relaxed denim or straight-leg trousers and simple shoes
- does not raise an exception
- still gives the agent something usable for the next step

### `create_fit_card`

Concrete failure:
- `create_fit_card("", listing)`

Behavior:
- returns: `"I couldn't generate a full fit card because the outfit details were missing. ..."`
- does not raise an exception
- gives the UI a specific fallback message

I saved a transcript of these deliberate failure checks in [milestone5_failure_checks.txt](/Users/cyrilkups/Desktop/ai201-project2-fitfindr-starter-/milestone5_failure_checks.txt).

## AI Usage

### Instance 1: Tool implementation

Input I gave the AI:
- the `Tool 1`, `Tool 2`, and `Tool 3` spec blocks from `planning.md`
- expected failure behaviors
- the exact function signatures already present in `tools.py`

What the AI produced:
- first-pass implementations for search, styling, and caption generation

What I changed before keeping it:
- made imports resilient when `groq` or `dotenv` were missing
- added deterministic fallbacks for `suggest_outfit` and `create_fit_card`
- corrected compatibility issues with the actual Groq Python client shape
- refined size parsing and ranking logic to better fit the mock dataset

### Instance 2: Planning loop and state flow

Input I gave the AI:
- the `Planning Loop`, `State Management`, and `Architecture` sections from `planning.md`
- the Mermaid diagram showing the retry branch and early-stop error path

What the AI produced:
- a draft `run_agent()` flow

What I changed before keeping it:
- made the retry logic conditional only on filtered searches
- ensured the no-results branch returns before `suggest_outfit` and `create_fit_card`
- added tests that verify object identity and state passing rather than only checking string outputs

## Spec Reflection

The biggest thing that changed from the original plan was environment handling. The tool and planning logic matched the design closely, but the runtime environment needed extra work:
- `gradio>=6.9.0` was not compatible with the repo’s Python 3.9 venv
- Gradio 4.44.1 worked, but it also needed a compatible `huggingface_hub` pin
- default Gradio ports were busy locally, so I verified the app at `http://127.0.0.1:8080`

The planning loop itself stayed close to the spec:
- one real decision point after search
- one retry path
- early termination when search cannot recover

If I extended this project, I would improve query parsing so that terms like `"a vintage graphic tee"` normalize a little more cleanly and I would separate “closest style match” from “closest size match” more explicitly in the ranking.

## End-to-End Verification

Verified locally:
- `handle_query("vintage graphic tee under $30", "Example wardrobe")` populates all three output panels
- `handle_query("designer ballgown size XXS under $5", "Example wardrobe")` returns an error only in the first output panel
- `python app.py` launches successfully when run with `GRADIO_SERVER_PORT=8080`
- local server responds with HTTP 200 at `http://127.0.0.1:8080`
- `python -m pytest tests/ -q` passes

## Demo Notes

Suggested happy-path demo:
1. Query: `"vintage graphic tee under $30"`
2. Narrate that the agent parses the query, searches listings, chooses one top result, styles it with wardrobe state, then writes the fit card.
3. Point out that the listing in panel 1 is the same item being used for the outfit and caption.

Suggested failure-path demo:
1. Query: `"designer ballgown size XXS under $5"`
2. Narrate that search fails, the agent stops early, and the styling/caption steps are intentionally skipped.

Suggested state-passing narration:
- “This selected item dict is stored in `session['selected_item']`, then the same object is passed to `suggest_outfit`, and the exact returned outfit string becomes the input to `create_fit_card`.”
