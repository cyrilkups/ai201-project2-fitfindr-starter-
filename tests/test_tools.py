from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.data_loader import get_empty_wardrobe, get_example_wardrobe

import tools
from tools import create_fit_card, search_listings, suggest_outfit


def _sample_listing():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert results, "expected at least one graphic tee listing for tests"
    return results[0]


def test_search_returns_results():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0
    assert all(isinstance(item, dict) for item in results)


def test_search_empty_results():
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []


def test_search_price_filter():
    results = search_listings("jacket", size=None, max_price=10)
    assert all(item["price"] <= 10 for item in results)


def test_search_size_filter():
    results = search_listings("track jacket", size="M", max_price=None)
    assert results
    assert any(item["size"] == "M" for item in results)


def test_suggest_outfit_returns_groq_response(monkeypatch):
    listing = _sample_listing()
    wardrobe = get_example_wardrobe()

    monkeypatch.setattr(
        tools,
        "_generate_with_groq",
        lambda prompt, *, max_tokens, temperature: "Mocked outfit idea",
    )

    suggestion = suggest_outfit(listing, wardrobe)
    assert suggestion == "Mocked outfit idea"


def test_suggest_outfit_empty_wardrobe_fallback(monkeypatch):
    listing = _sample_listing()
    empty_wardrobe = get_empty_wardrobe()

    monkeypatch.setattr(
        tools,
        "_generate_with_groq",
        lambda prompt, *, max_tokens, temperature: None,
    )

    suggestion = suggest_outfit(listing, empty_wardrobe)
    assert isinstance(suggestion, str)
    assert suggestion
    assert listing["title"] in suggestion


def test_create_fit_card_returns_groq_response(monkeypatch):
    listing = _sample_listing()
    captured = {}

    def fake_generate(prompt, *, max_tokens, temperature):
        captured["prompt"] = prompt
        captured["max_tokens"] = max_tokens
        captured["temperature"] = temperature
        return "Mocked fit card"

    monkeypatch.setattr(tools, "_generate_with_groq", fake_generate)

    caption = create_fit_card("Layer the tee with dark denim and boots.", listing)
    assert caption == "Mocked fit card"
    assert captured["max_tokens"] == 200
    assert captured["temperature"] == 0.9
    assert listing["title"] in captured["prompt"]


def test_create_fit_card_empty_outfit_returns_informative_message():
    listing = _sample_listing()

    caption = create_fit_card("", listing)
    assert isinstance(caption, str)
    assert caption
    assert listing["title"] in caption


def test_create_fit_card_fallback_when_groq_unavailable(monkeypatch):
    listing = _sample_listing()

    monkeypatch.setattr(
        tools,
        "_generate_with_groq",
        lambda prompt, *, max_tokens, temperature: None,
    )

    caption = create_fit_card("Pair it with baggy jeans and a denim jacket.", listing)
    assert isinstance(caption, str)
    assert caption
    assert listing["title"] in caption
    assert listing["platform"] in caption
