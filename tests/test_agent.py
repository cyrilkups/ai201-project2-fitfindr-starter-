from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import agent
from app import handle_query
from utils.data_loader import get_example_wardrobe


def test_run_agent_happy_path_populates_session():
    session = agent.run_agent("vintage graphic tee under $30", get_example_wardrobe())

    assert session["error"] is None
    assert session["selected_item"] is not None
    assert session["outfit_suggestion"]
    assert session["fit_card"]
    assert session["search_results"]
    assert session["search_results"][0] == session["selected_item"]


def test_run_agent_passes_same_state_between_tools(monkeypatch):
    seen = {}
    original_suggest = agent.suggest_outfit
    original_card = agent.create_fit_card

    def traced_suggest(new_item, wardrobe):
        seen["selected_item_id_in_suggest"] = id(new_item)
        seen["selected_item_title_in_suggest"] = new_item["title"]
        result = original_suggest(new_item, wardrobe)
        seen["outfit_from_suggest"] = result
        return result

    def traced_card(outfit, new_item):
        seen["selected_item_id_in_card"] = id(new_item)
        seen["outfit_into_card"] = outfit
        return original_card(outfit, new_item)

    monkeypatch.setattr(agent, "suggest_outfit", traced_suggest)
    monkeypatch.setattr(agent, "create_fit_card", traced_card)

    session = agent.run_agent("vintage graphic tee under $30", get_example_wardrobe())

    assert id(session["selected_item"]) == seen["selected_item_id_in_suggest"]
    assert id(session["selected_item"]) == seen["selected_item_id_in_card"]
    assert session["outfit_suggestion"] == seen["outfit_from_suggest"]
    assert session["outfit_suggestion"] == seen["outfit_into_card"]


def test_run_agent_no_results_stops_before_downstream_tools(monkeypatch):
    called = {"suggest": False, "card": False}

    def fail_if_called_suggest(new_item, wardrobe):
        called["suggest"] = True
        raise AssertionError("suggest_outfit should not be called on empty search results")

    def fail_if_called_card(outfit, new_item):
        called["card"] = True
        raise AssertionError("create_fit_card should not be called on empty search results")

    monkeypatch.setattr(agent, "suggest_outfit", fail_if_called_suggest)
    monkeypatch.setattr(agent, "create_fit_card", fail_if_called_card)

    session = agent.run_agent("designer ballgown size XXS under $5", get_example_wardrobe())

    assert session["error"]
    assert session["selected_item"] is None
    assert session["outfit_suggestion"] is None
    assert session["fit_card"] is None
    assert called == {"suggest": False, "card": False}


def test_run_agent_relaxes_filters_when_exact_match_fails():
    session = agent.run_agent("black combat boots size 8", get_example_wardrobe())

    assert session["error"] is None
    assert session["parsed"]["filters_relaxed"] is True
    assert session["selected_item"] is not None


def test_handle_query_returns_error_only_for_empty_query():
    listing_text, outfit_text, fit_card = handle_query("", "Example wardrobe")

    assert listing_text == "Please enter a search query first."
    assert outfit_text == ""
    assert fit_card == ""


def test_handle_query_formats_success_response():
    listing_text, outfit_text, fit_card = handle_query(
        "vintage graphic tee under $30",
        "Example wardrobe",
    )

    assert "Graphic Tee" in listing_text
    assert "Price:" in listing_text
    assert outfit_text
    assert fit_card
