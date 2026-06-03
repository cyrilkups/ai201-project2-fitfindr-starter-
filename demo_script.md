# Demo Script

This version is written to sound natural out loud. You do not need to read it word-for-word, but it should give you a smooth rhythm for a 3–5 minute demo.

## Opening

"This is FitFindr. The idea is simple: you describe what you're looking for in everyday language, and the agent does three jobs for you. It searches secondhand listings, figures out how that piece could work with your wardrobe, and then writes a short fit-card caption that feels like a real post instead of a product listing."

## Show the Interface

Run:

```bash
GRADIO_SERVER_PORT=8080 python app.py
```

Open:

`http://127.0.0.1:8080`

Suggested transition:

"The interface has one input for the shopping query, one wardrobe selector, and three output panels. Those panels map directly to the three stages of the agent: search, styling, and caption generation."

## Happy Path Walkthrough

Use this query:

`vintage graphic tee under $30`

Suggested narration:

"I’m starting with a happy-path example. The user wants a vintage graphic tee under thirty dollars."

"First, the agent parses the request. It pulls out the description, notices the budget, and stores that in the session state."

"Then it calls the search tool, which ranks the matching listings and picks the top result."

"That selected listing becomes shared state. The same listing object is passed into the outfit tool, so now the agent can reason about how it fits into the user’s wardrobe."

"Once the outfit suggestion comes back, that exact string becomes the input to the fit-card tool. So the final caption is not generated from scratch; it is grounded in the search result and the styling recommendation that came right before it."

What to point at on screen:
- panel 1: the selected listing
- panel 2: the outfit idea
- panel 3: the fit card

Good closing line for this part:

"So this is the main success path: search first, style second, caption third, with state flowing forward through each step."

## Make State Passing Visible

If you want a short terminal proof while recording, run:

```bash
python -c "from agent import run_agent; from utils.data_loader import get_example_wardrobe; s = run_agent('vintage graphic tee under $30', get_example_wardrobe()); print(s['selected_item']); print(); print(s['outfit_suggestion']); print(); print(s['fit_card'])"
```

Suggested narration:

"Here you can see the actual session contents. The selected item is stored once, then reused downstream. The outfit suggestion is also stored once, and that exact text becomes the input to the caption step. The agent is not re-prompting from scratch between steps and it is not using hardcoded placeholders."

## Failure Path

Use this query:

`designer ballgown size XXS under $5`

Suggested narration:

"Now I’m triggering a deliberate failure case. This query is unrealistic for the dataset, so the search tool returns no results."

"At that point, the important thing is that the agent does not keep going. It returns a clear error message, and the styling and caption panels stay empty."

"That tells us the planning loop is actually branching. It’s not just calling all three tools every time no matter what happened upstream."

If you want a matching terminal check:

```bash
python -c "from agent import run_agent; from utils.data_loader import get_example_wardrobe; s = run_agent('designer ballgown size XXS under \$5', get_example_wardrobe()); print(s)"
```

## Optional Empty-Wardrobe Note

If you want one extra quick example, switch to the empty wardrobe option and reuse a normal fashion query.

Suggested narration:

"With an empty wardrobe, the outfit tool still returns something useful. Instead of naming existing pieces, it falls back to general styling advice. So even the degraded path stays readable and helpful."

## Closing

"That’s FitFindr. The project is small, but the core agent behavior is there: it makes one real decision after search, it carries state forward instead of recomputing everything, and it fails gracefully when the search step can’t recover."
