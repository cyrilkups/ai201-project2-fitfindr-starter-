# FitFindr — planning.md

> Complete this document before writing any implementation code.
> Your spec and agent diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Your planning.md will be reviewed as part of your submission.
> Update it before starting any stretch features.

---

## A Complete Interaction

**User query:** "I'm looking for a vintage graphic tee under $30, size M. I mostly wear baggy jeans and chunky sneakers."

**What FitFindr does:**
FitFindr parses the natural language query into structured search parameters, then runs a two-pass search. First it tries the exact request: `description="vintage graphic tee"`, `size="M"`, `max_price=30.0`. If that exact search is empty, it tells the user it is relaxing the filters and retries using only the description. Once it has a non-empty result list, it selects the top item, generates an outfit suggestion using the user's wardrobe, and then generates a short fit-card caption. If both searches are empty, it sets `session["error"]` and stops immediately without calling the styling or caption tools.

**Data flow:**
1. Query → Parse → `search_listings("vintage graphic tee", size="M", max_price=30.0)` → Returns `[]`
2. Retry path → `search_listings("vintage graphic tee", size=None, max_price=None)` → Returns ranked results, top item: `{id: "lst_006", title: "Graphic Tee — 2003 Tour Bootleg Style", price: 24.0, platform: "depop", ...}`
3. Selected item → `suggest_outfit(new_item=lst_006, wardrobe=example_wardrobe)` → Returns a styling paragraph that references the user's baggy jeans, denim jacket, and chunky/black boots
4. Outfit suggestion → `create_fit_card(outfit=suggestion, new_item=lst_006)` → Returns a short caption mentioning the thrift find, price, and vibe

**Error handling:** If the first search is empty, the agent says there was no exact size/price match and broadens the search. If the retry is also empty, it sets `session["error"]` to a specific message like `"No listings found for 'vintage graphic tee' with size M and under $30. Try a broader style keyword or remove a filter."` and terminates before reaching `suggest_outfit` or `create_fit_card`.

---

## Tools

List every tool your agent will use. For each tool, fill in all four fields.
You must have at least 3 tools. The three required tools are listed — add any additional tools below them.

### Tool 1: search_listings

**What it does:**
Searches the mock listings dataset (40 items) for secondhand clothing that matches the user's description, size, and price constraints. Returns the best-matching items ranked by relevance.

**Input parameters:**
- `description` (str): Keywords describing what to search for (for example `"vintage graphic tee"`, `"90s track jacket"`, `"black combat boots"`). Required.
- `size` (str | None): Optional requested size string. Can be an apparel size like `M`, `L`, `S/M`, `XL`, or a numeric/shoe/waist size like `8`, `US 8.5`, or `W30 L30`.
- `max_price` (float | None): Maximum price in dollars. Optional — if None, return all prices.

**What it returns:**
A list of listing dictionaries sorted best-match first. Each dictionary contains:
- `id` (str): Listing ID like `lst_006`
- `title` (str): Human-readable listing title
- `description` (str): Seller/item description
- `category` (str): `tops`, `bottoms`, `outerwear`, `shoes`, or `accessories`
- `style_tags` (list[str]): Style labels like `grunge`, `vintage`, `graphic tee`
- `size` (str): Raw size label from the dataset
- `condition` (str): `excellent`, `good`, or `fair`
- `price` (float): Listing price in USD
- `colors` (list[str]): One or more colors
- `brand` (str | None): Brand name if present
- `platform` (str): Marketplace such as `depop`, `poshmark`, or `thredUp`

**What happens if it fails or returns nothing:**
If no listings pass the filters or no listing has any keyword overlap with the description, the tool returns `[]` instead of raising an exception. The agent handles that result in two stages: retry once with relaxed filters if a size or price filter was present, then terminate with a user-facing error message if the relaxed search is also empty.

---

### Tool 2: suggest_outfit

**What it does:**
Given a new item and the user's existing wardrobe, suggests one or more complete outfit combinations. Uses an LLM to reason about style compatibility, color coordination, and occasion suitability.

**Input parameters:**
- `new_item` (dict): The listing dictionary of the item found by search_listings (contains title, colors, category, style_tags, etc.).
- `wardrobe` (dict): The user's wardrobe object (contains items array with existing pieces, each with category, colors, styles, etc.).

**What it returns:**
A non-empty string with 1 outfit recommendation paragraph. The paragraph must mention the `new_item` by name, reference specific wardrobe pieces when possible, and explain why the colors/styles/silhouettes work together. Example shape: `"Start with the graphic tee, pair it with your baggy dark-wash jeans, layer in the black denim jacket, and finish with chunky sneakers because the dark neutral base keeps the grunge vibe consistent."`

**What happens if it fails or returns nothing:**
If the wardrobe is empty, the tool should return general styling advice built around the new item category instead of named wardrobe pieces. If the LLM is unavailable or returns nothing, the tool should fall back to a deterministic styling paragraph based on the item's category, colors, and style tags. The agent does not stop on this tool; it always proceeds with whatever non-empty suggestion string is returned.

---

### Tool 3: create_fit_card

**What it does:**
Generates a short, shareable Instagram-style caption for a complete outfit. The caption should sound natural and appealing — the kind of thing someone would actually post on social media, not a product description.

**Input parameters:**
- `outfit` (str): The outfit suggestion string from `suggest_outfit` (describes the items and why they work together).
- `new_item` (dict): The listing dictionary of the new item (for title, brand, style context).

**What it returns:**
A non-empty caption string, usually 1-2 sentences. It should mention the thrifted item title, the price, and the resale platform naturally, while reflecting the vibe from the outfit suggestion. Example shape: `"Just found this bootleg-style graphic tee for $24 on Depop, and it completely pulled the grunge outfit together. The dark denim and chunky shoes make it feel effortless."`

**What happens if it fails or returns nothing:**
If `outfit` is empty, return a short fallback sentence about the item instead of raising an error. If the LLM is unavailable or returns nothing, return a deterministic caption that mentions the item, price, platform, and overall vibe. The agent never branches on this tool; it always uses the returned caption.
---

### Additional Tools (if any)

No additional tools are required for the baseline agent. Query parsing happens inside the planning loop, not as a separate tool call.

---

## Planning Loop

**How does your agent decide which tool to call next?**

The planning loop is a fixed sequence with one conditional retry branch:

1. Create a fresh `session` dict with keys for the raw query, parsed filters, search results, selected item, wardrobe, outfit suggestion, fit card, and error.
2. If `query.strip()` is empty, set `session["error"] = "Please enter what you're looking for."` and return immediately.
3. Parse the query with string/regex rules:
   - Extract `max_price` from phrases like `under $30`, `below 40`, or a plain dollar amount.
   - Extract `size` from phrases like `size M`, `in size M`, `size 8`, or `W30 L30`.
   - Remove those filter phrases and filler text like `I'm looking for`, `find me`, and `show me` to produce `description`.
   - Save `{"description": ..., "size": ..., "max_price": ..., "filters_relaxed": False}` to `session["parsed"]`.
4. Call `search_listings(description, size, max_price)` and store the returned list in `session["search_results"]`.
5. If `session["search_results"]` is empty and at least one filter was provided (`size` or `max_price` is not `None`), retry once with `search_listings(description, size=None, max_price=None)`.
   - If the retry returns results, replace `session["search_results"]` with the relaxed results and set `session["parsed"]["filters_relaxed"] = True`.
   - If the retry is still empty, set `session["error"]` to a message that includes the requested description and filters, then return immediately.
6. If the very first search was empty and there were no filters to relax, set `session["error"]` immediately and return.
7. Set `session["selected_item"] = session["search_results"][0]`. The top-ranked result is always the item passed to downstream tools.
8. Call `suggest_outfit(session["selected_item"], session["wardrobe"])` and store the returned string in `session["outfit_suggestion"]`.
9. Call `create_fit_card(session["outfit_suggestion"], session["selected_item"])` and store the returned string in `session["fit_card"]`.
10. Return the completed `session`. At this point `error` is `None`, and the UI can render the listing, outfit suggestion, and fit card.

---

## State Management

**How does information from one tool get passed to the next?**

All state lives in one mutable `session` dictionary created at the top of `run_agent()`. Tools do not read global state; they receive the exact values they need from `session`, and their outputs are written back into `session` for the next step to use.

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

State transitions:
- After parsing, `session["parsed"]` contains the structured search request.
- After `search_listings`, `session["search_results"]` holds the ranked matches.
- After choosing the best match, `session["selected_item"]` becomes the single listing passed into both downstream tools.
- After `suggest_outfit`, `session["outfit_suggestion"]` stores the styling paragraph.
- After `create_fit_card`, `session["fit_card"]` stores the final caption.
- If any early-stop condition happens, only `session["error"]` is set; `selected_item`, `outfit_suggestion`, and `fit_card` stay `None`.

The UI only reads the final session. If `error` is set, it displays that message and ignores the other output panels. If `filters_relaxed` is `True`, the UI prepends a note such as `"No exact size/price match found, so this is the closest style match."`

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | First search returns `[]` | Agent checks whether a size or price filter was present. If yes, it tells the user internally/UI note that no exact filtered match was found and retries once using only the description. |
| search_listings | Relaxed retry also returns `[]` | Agent sets `session["error"]` to a specific message like `"No listings found for 'designer ballgown' with size XXS and under $5. Try a broader style keyword or remove a filter."` and returns immediately without calling any more tools. |
| suggest_outfit | Wardrobe is empty | Tool returns general styling advice like `"Use this tee as the focal point and pair it with relaxed denim and clean sneakers."` Agent still proceeds to `create_fit_card`. |
| suggest_outfit | LLM call fails or returns an empty response | Tool falls back to a deterministic outfit paragraph based on item category, colors, and style tags. Agent does not branch or retry. |
| create_fit_card | `outfit` string is empty or whitespace | Tool returns a safe fallback line about the thrifted item instead of raising. Agent still returns a completed session. |
| create_fit_card | LLM call fails or returns an empty response | Tool returns a deterministic caption that includes the item title, price, platform, and vibe. Agent does not branch or retry. |

---

## Architecture

```mermaid
graph TD
    User["User query"]
    Wardrobe["Wardrobe input"]
    Loop["Planning Loop<br/>run_agent()"]
    Session[("Session state")]
    Search["search_listings(description, size, max_price)"]
    Retry["search_listings(description)<br/>(relaxed retry)"]
    Outfit["suggest_outfit(selected_item, wardrobe)"]
    Card["create_fit_card(outfit_suggestion, selected_item)"]
    Error["session['error'] = helpful message"]
    Success["Return session to UI"]
    Failure["Return error to UI"]

    User --> Loop
    Wardrobe --> Loop
    Loop -->|initialize| Session
    Loop -->|parsed filters| Search
    Search -->|results list| Session
    Search -->|[] and filters present| Retry
    Retry -->|results list| Session
    Retry -->|[] again| Error
    Search -->|[] and no filters to relax| Error
    Session -->|selected_item = search_results[0]| Outfit
    Outfit -->|outfit_suggestion| Session
    Session -->|selected_item + outfit_suggestion| Card
    Card -->|fit_card| Session
    Session --> Success
    Error --> Failure

    style Loop fill:#e1f5ff
    style Session fill:#f3f9ff
    style Search fill:#fff3e0
    style Retry fill:#fff3e0
    style Outfit fill:#f3e5f5
    style Card fill:#e8f5e9
    style Error fill:#ffebee
    style Success fill:#e8f5e9
```

**Flow summary:**
1. User query and wardrobe enter `run_agent()`.
2. `run_agent()` creates `session`, parses the query, and calls `search_listings`.
3. A visible early-stop branch handles empty search results after the relaxed retry.
4. Success path stores `selected_item` in session, then calls `suggest_outfit`.
5. The resulting outfit text is written back to session and passed to `create_fit_card`.
6. The completed session is returned to the UI.

---

## AI Tool Plan

### Milestone 1 — `search_listings`

**AI tool:** GitHub Copilot
**Input I will give it:** The `Tool 1: search_listings` block, the two `search_listings` rows from `## Error Handling`, and the architecture diagram's search/retry branch
**Expected output:** A function that loads the dataset with `load_listings()`, filters by price and size, scores results by description/style overlap, sorts best-match first, and returns `[]` instead of raising when nothing matches
**How I will verify it:** Run at least three direct tests:
- `search_listings("vintage graphic tee", max_price=30)` returns a non-empty ranked list of dicts
- `search_listings("90s track jacket", size="M")` includes the actual track jacket near the top
- `search_listings("designer ballgown", size="XXS", max_price=5)` returns `[]`

### Milestone 2 — `suggest_outfit` and `create_fit_card`

**AI tool:** GitHub Copilot
**Input I will give it:** The `Tool 2` and `Tool 3` blocks, the `suggest_outfit` and `create_fit_card` rows in `## Error Handling`, plus the bottom `## A Complete Interaction (Step by Step)` example
**Expected output:** Two functions that return non-empty strings every time: `suggest_outfit()` should reference either specific wardrobe pieces or fallback basics, and `create_fit_card()` should turn the outfit suggestion into a short caption with a safe deterministic fallback
**How I will verify it:**
- Call `suggest_outfit()` once with `get_example_wardrobe()` and once with `get_empty_wardrobe()`
- Confirm both calls return non-empty strings
- Call `create_fit_card()` with a normal outfit string and with an intentionally empty string
- Confirm the caption mentions the item naturally and never returns `""`

### Milestone 3 — `run_agent` planning loop

**AI tool:** GitHub Copilot
**Input I will give it:** `## Planning Loop`, `## State Management`, `## Error Handling`, and the Mermaid diagram in `## Architecture`
**Expected output:** A `run_agent(query, wardrobe)` function that creates the session dict, parses the query, retries search once without filters when appropriate, stops early on repeated empty search results, and otherwise fills `selected_item`, `outfit_suggestion`, and `fit_card` in order
**How I will verify it:**
- Happy path: `run_agent("vintage graphic tee under $30", get_example_wardrobe())` returns `error=None` and non-empty `selected_item`, `outfit_suggestion`, and `fit_card`
- Relaxed-filter path: `run_agent("black combat boots size 8", get_example_wardrobe())` sets `parsed["filters_relaxed"] = True`
- No-results path: `run_agent("designer ballgown size XXS under $5", get_example_wardrobe())` sets `error` and leaves later outputs empty

### Milestone 4 — UI wiring in `app.py`

**AI tool:** GitHub Copilot
**Input I will give it:** The `## State Management` section, the final-output part of `## A Complete Interaction (Step by Step)`, and the `run_agent()` behavior from `## Planning Loop`
**Expected output:** A `handle_query(user_query, wardrobe_choice)` function that validates empty input, picks the right wardrobe, calls `run_agent()`, formats the selected listing for the first output panel, and shows only the error message when `session["error"]` is set
**How I will verify it:**
- Call `handle_query("", "Example wardrobe")` and confirm it returns an error only in panel 1
- Call `handle_query("vintage graphic tee under $30", "Example wardrobe")` and confirm all three returned strings are populated
- Call `handle_query("designer ballgown size XXS under $5", "Example wardrobe")` and confirm the second and third outputs are empty

---

## A Complete Interaction (Step by Step)

Write out what a full user interaction looks like from start to finish — tool call by tool call. Use a specific example query.

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1:**
Initialize:
- Create `session = {"query": ..., "parsed": {}, "search_results": [], "selected_item": None, "wardrobe": example_wardrobe, "outfit_suggestion": None, "fit_card": None, "error": None}`
- Parse the query into `description="vintage graphic tee"`, `size=None`, `max_price=30.0`, and `filters_relaxed=False`

**Step 2:**
Search:
- Call `search_listings("vintage graphic tee", size=None, max_price=30.0)`
- It returns a ranked list such as:
  - `lst_006 | Graphic Tee — 2003 Tour Bootleg Style | L | $24.00`
  - `lst_033 | Vintage Band Tee — Faded Grey | L | $19.00`
  - `lst_015 | Vintage Graphic Hoodie — Faded Black | L | $26.00`
- Store that list in `session["search_results"]`

**Step 3:**
Selection and styling:
- Set `session["selected_item"] = session["search_results"][0]`, which is `lst_006`
- Call `suggest_outfit(new_item=session["selected_item"], wardrobe=session["wardrobe"])`
- Example returned string: `"Start with Graphic Tee — 2003 Tour Bootleg Style and pair it with your Baggy straight-leg jeans, dark wash, then layer in Vintage black denim jacket and finish with Black combat boots. The mix works because the colors stay close to black and the styling leans into grunge, streetwear, so the outfit feels intentional instead of overdone."`
- Store that string in `session["outfit_suggestion"]`

**Step 4:**
Caption:
- Call `create_fit_card(outfit=session["outfit_suggestion"], new_item=session["selected_item"])`
- Example returned string: `"Just found Graphic Tee — 2003 Tour Bootleg Style for $24.00 on depop, and it instantly gave the whole outfit a graphic tee vibe. Start with Graphic Tee — 2003 Tour Bootleg Style and pair it with your Baggy straight-leg jeans, dark wash, then layer in Vintage black denim jacket and finish with Black combat boots."`
- Store that string in `session["fit_card"]`

**Final output to user:**
The user sees three UI panels:
- **Top listing found:** Title, price, platform, size, condition, colors, style tags, and the item description for `Graphic Tee — 2003 Tour Bootleg Style`
- **Outfit idea:** The styling paragraph naming the jeans, denim jacket, and boots
- **Your fit card:** The short shareable caption

If the first search had failed but the relaxed retry succeeded, the listing panel would also begin with: `"No exact size/price match found, so this is the closest style match:"`
