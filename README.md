# FitFindr

FitFindr is a small agent for secondhand fashion discovery. You give it a plain-English shopping request like "vintage graphic tee under $30," and it does three things in sequence: it searches a resale listings dataset, figures out how that item could work with your wardrobe, and then writes a short fit-card caption that sounds like a real thrift post instead of a product blurb.

What makes the project interesting is not just the three tools by themselves, but the decision-making between them. The agent does not blindly call every tool every time. It searches first, checks whether the search succeeded, optionally relaxes the filters once, and only then moves on to styling and caption generation.

## Quick Start

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

### Run the app

On this machine, the default Gradio port range was already busy, so I verified the app on port `8080`:

```bash
GRADIO_SERVER_PORT=8080 python app.py
```

Then open:

`http://127.0.0.1:8080`

### Run the tests

```bash
python -m pytest tests/ -q
```

## What a Successful Run Looks Like

A typical successful interaction goes like this:

1. The user asks for something in natural language.
2. The agent parses that request into a search description plus optional filters like size and max price.
3. `search_listings()` returns ranked matches from the dataset.
4. The top result becomes `session["selected_item"]`.
5. `suggest_outfit()` uses that exact item plus the wardrobe data to produce styling advice.
6. `create_fit_card()` turns that exact outfit suggestion into a short caption.
7. The UI shows all three outputs together: listing, outfit idea, and fit card.

If search fails, the sequence changes. The agent tries one relaxed search when the original request included filters. If that still comes back empty, the run stops there with a helpful error instead of pretending it found something.

## Tool Inventory

### `search_listings(description: str, size: Optional[str], max_price: Optional[float]) -> list[dict]`

This tool is the retrieval step. Its job is to take a user request and turn it into actual candidate items from the dataset.

Inputs:
- `description: str` — the core search phrase, such as `"vintage graphic tee"` or `"90s track jacket"`.
- `size: Optional[str]` — an optional size filter such as `"M"`, `"8"`, or `"W30 L30"`.
- `max_price: Optional[float]` — an optional maximum budget in dollars.

Output:
- a ranked `list[dict]` of listings, where each listing contains `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, and `platform`.

What it contributes:
- it gives the rest of the agent something concrete to reason over
- it determines whether the run continues normally, retries with relaxed filters, or exits early

Failure handling:
- when nothing matches, it returns `[]`
- it does not throw a normal "no results" case as an exception

### `suggest_outfit(new_item: dict, wardrobe: dict) -> str`

This is the styling step. It takes the chosen item and tries to make it feel wearable in the context of the user's wardrobe instead of treating it like a standalone product.

Inputs:
- `new_item: dict` — the selected listing chosen from search results
- `wardrobe: dict` — wardrobe data with an `items` list loaded from `utils/data_loader.py`

Output:
- a non-empty string with outfit advice

What it contributes:
- turns a search result into something personal
- references actual wardrobe pieces when possible
- falls back to general styling guidance when the wardrobe is empty

Failure handling:
- if the wardrobe is empty, it still returns usable advice
- if the Groq call fails, it falls back to deterministic styling text

### `create_fit_card(outfit: str, new_item: dict) -> str`

This is the finishing step. It takes the item plus the styling recommendation and turns them into a short caption that feels like something a person would actually post.

Inputs:
- `outfit: str` — the outfit text returned by `suggest_outfit`
- `new_item: dict` — the same selected listing used in the previous step

Output:
- a non-empty caption string that mentions the item, price, platform, and overall vibe

What it contributes:
- makes the final output feel complete and presentable
- gives the interface a third panel that reads differently from the outfit advice

Failure handling:
- if the outfit string is missing, it returns a descriptive fallback message
- if the Groq call fails, it falls back to a deterministic caption

## How the Planning Loop Actually Works

The planning loop lives in [agent.py](/Users/cyrilkups/Desktop/ai201-project2-fitfindr-starter-/agent.py) inside `run_agent()`. The key idea is that it branches on the search result instead of treating the system like a fixed pipeline.

The logic is:

1. Start a fresh `session` dictionary.
2. Reject empty user input immediately.
3. Parse the raw query into:
   - `description`
   - `size`
   - `max_price`
   - `filters_relaxed`
4. Call `search_listings(description, size, max_price)`.
5. If search succeeds:
   - store the results
   - choose `results[0]` as `selected_item`
   - pass that exact object into `suggest_outfit`
   - pass the exact resulting outfit string into `create_fit_card`
6. If search fails and the query had filters:
   - retry once using only the description
   - mark `filters_relaxed = True` if that retry succeeds
7. If search still fails:
   - set `session["error"]`
   - return early
   - do not call the styling tool
   - do not call the caption tool

That early-stop behavior is important. It is what makes the agent feel deliberate instead of scripted.

## State Management

Everything flows through a single session object. That makes the interaction easy to inspect and easy to test.

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

Why this works well:
- the selected listing is stored once and reused downstream
- the outfit text is stored once and reused downstream
- the UI only reads the final state instead of recomputing anything
- failure is explicit because `error` is part of the same object

I also tested this directly. The same `selected_item` object reaches both downstream tools, and the exact `outfit_suggestion` stored in session is the string that becomes the input to `create_fit_card`.

## Error Handling

### Search failure

Concrete example:
- query: `"designer ballgown size XXS under $5"`

Direct tool result:
- `search_listings(...)` returns `[]`

Agent response:
- `"No listings found for 'designer ballgown' with size XXS and under $5. Try a broader style keyword or remove a filter."`

State at the end:
- `selected_item = None`
- `outfit_suggestion = None`
- `fit_card = None`

The important part is what does not happen: the agent does not continue into styling or caption generation.

### Empty wardrobe

Concrete example:
- call `suggest_outfit(listing, get_empty_wardrobe())`

Response shape:
- general styling guidance such as pairing the item with relaxed denim, neutral bottoms, or simple shoes

Why that matters:
- the agent still returns something useful even when it cannot reference named wardrobe pieces

### Empty outfit string

Concrete example:
- call `create_fit_card("", listing)`

Response:
- `"I couldn't generate a full fit card because the outfit details were missing..."`

Why that matters:
- the UI receives a readable fallback instead of a traceback or silent empty output

I saved the deliberate failure-mode transcript in [milestone5_failure_checks.txt](/Users/cyrilkups/Desktop/ai201-project2-fitfindr-starter-/milestone5_failure_checks.txt).

## AI Usage

I used AI as a drafting and acceleration tool, but not as something I trusted blindly.

### Example 1: Tool implementation

What I gave the AI:
- the `Tool 1`, `Tool 2`, and `Tool 3` sections from `planning.md`
- the intended failure behaviors
- the existing function signatures from `tools.py`

What it gave back:
- first-pass implementations for retrieval, styling, and caption generation

What I changed before keeping it:
- made imports safe when `groq` or `dotenv` were missing
- added deterministic fallbacks for both LLM-backed tools
- corrected SDK assumptions so the Groq client calls matched the real client
- refined ranking and size-matching logic to better fit this dataset

### Example 2: Planning loop and state flow

What I gave the AI:
- the `Planning Loop`, `State Management`, and `Architecture` sections from `planning.md`
- the Mermaid diagram showing the retry branch and early-stop branch

What it gave back:
- a draft `run_agent()` structure

What I changed before keeping it:
- made retry conditional only when size or price filters were present
- ensured the no-results path returns before any downstream tool calls
- added tests that verify actual state passing, not just surface-level output

## Spec Reflection

The implementation stayed pretty close to the original plan, which was a good sign that the spec was specific enough. The biggest surprises were environmental rather than architectural.

What changed in practice:
- the original Gradio requirement was too new for the Python 3.9 venv in this repo
- Gradio also needed a compatible `huggingface_hub` version to import cleanly
- local port conflicts meant I verified the interface on `http://127.0.0.1:8080` instead of assuming `7860`

What stayed true to the plan:
- one real decision point after search
- one relaxed retry path
- one explicit early-stop path on repeated search failure
- session-based state flow across every step

If I kept going, I would improve the query parsing and make the "closest match" ranking a little more nuanced so that the fallback search could distinguish style similarity from size similarity more gracefully.

## End-to-End Verification

Verified locally:
- `handle_query("vintage graphic tee under $30", "Example wardrobe")` fills all three output panels
- `handle_query("designer ballgown size XXS under $5", "Example wardrobe")` returns an error only in the first panel
- `build_interface()` succeeds
- the app launches successfully with `GRADIO_SERVER_PORT=8080 python app.py`
- `http://127.0.0.1:8080` responds with HTTP 200
- `python -m pytest tests/ -q` passes

## Demo Notes

If you want to demo the project smoothly, the cleanest path is:

1. Start the app.
2. Run a happy-path query like `"vintage graphic tee under $30"`.
3. Explain that the selected listing becomes shared state for the next two steps.
4. Run a failure query like `"designer ballgown size XXS under $5"`.
5. Point out that the agent stops early instead of fabricating a recommendation.

There is also a ready-to-use recording outline in [demo_script.md](/Users/cyrilkups/Desktop/ai201-project2-fitfindr-starter-/demo_script.md).
