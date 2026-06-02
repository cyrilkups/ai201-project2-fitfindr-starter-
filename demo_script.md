# Demo Script

## 1. Intro

"This is FitFindr, a secondhand styling agent. It takes a natural-language shopping query, searches a listings dataset, suggests an outfit using the user's wardrobe, and then creates a short social-style fit card caption."

## 2. Happy Path

Run:

```bash
GRADIO_SERVER_PORT=8080 python app.py
```

Open `http://127.0.0.1:8080`.

Use this query:

`vintage graphic tee under $30`

Narration:
- "First, the agent parses the query into a description and optional filters."
- "Then it calls `search_listings` and ranks the matching items."
- "The top result becomes `session['selected_item']`."
- "That exact selected item is passed into `suggest_outfit` along with the wardrobe."
- "The returned outfit text is stored in `session['outfit_suggestion']`."
- "Then that exact string is passed into `create_fit_card` to generate the final caption."

Point out:
- panel 1: selected listing
- panel 2: outfit suggestion
- panel 3: fit card

## 3. State Passing

Suggested narration:

"The important part here is that the agent is not hardcoding the next step. The selected listing from search is reused downstream, and the outfit suggestion string created in step two becomes the input for the caption tool in step three."

If you want a terminal proof while recording:

```bash
python -c "from agent import run_agent; from utils.data_loader import get_example_wardrobe; s = run_agent('vintage graphic tee under $30', get_example_wardrobe()); print(s['selected_item']); print(); print(s['outfit_suggestion']); print(); print(s['fit_card'])"
```

## 4. Failure Path

Use this query:

`designer ballgown size XXS under $5`

Narration:
- "This deliberately triggers a search failure."
- "The search tool returns an empty list."
- "The agent detects that and exits early with an informative error message."
- "It does not call the outfit or fit-card tools, so those panels remain empty."

Optional terminal proof:

```bash
python -c "from agent import run_agent; from utils.data_loader import get_example_wardrobe; s = run_agent('designer ballgown size XXS under \$5', get_example_wardrobe()); print(s)"
```

## 5. Close

"So the main agent behavior is: search first, branch on results, pass state forward when successful, and stop gracefully when the search cannot recover."
