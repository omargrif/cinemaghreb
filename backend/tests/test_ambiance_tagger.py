import json
from types import SimpleNamespace

import pytest

from app.enrichment.ambiance_tagger import (
    AMBIANCE_RESPONSE_SCHEMA,
    tag_movie,
    tag_movies,
)
from app.models.movie import Movie


def _movie(**overrides) -> Movie:
    defaults = {
        "id": 1,
        "title": "Much Loved",
        "year": 2015,
        "director": "Nabil Ayouch",
        "genres": ["Drama"],
        "synopsis": "Trois amies traversent Marrakech de nuit.",
    }
    defaults.update(overrides)
    return Movie(**defaults)


class _FakeModels:
    def __init__(self, texts):
        self._texts = list(texts)
        self.calls: list[SimpleNamespace] = []

    def generate_content(self, model, contents, config):
        self.calls.append(SimpleNamespace(model=model, contents=contents, config=config))
        return SimpleNamespace(text=self._texts.pop(0))


class _FakeClient:
    def __init__(self, texts):
        if isinstance(texts, str):
            texts = [texts]
        self.models = _FakeModels(texts)


def test_tag_movie_sends_synopsis_and_metadata_and_constrains_tags():
    payload = json.dumps({"tags": ["nostalgique", "social"], "mood_summary": "Une nuit d'errance et de liberté."})
    client = _FakeClient(payload)

    result = tag_movie(client, _movie())

    assert result.tags == ["nostalgique", "social"]
    assert result.mood_summary == "Une nuit d'errance et de liberté."
    call = client.models.calls[0]
    assert call.model == "gemini-2.5-flash-lite"
    assert "Much Loved" in call.contents
    assert "Nabil Ayouch" in call.contents
    assert "Marrakech" in call.contents
    assert call.config.response_schema == AMBIANCE_RESPONSE_SCHEMA


def test_tag_movie_rejects_movie_without_synopsis():
    with pytest.raises(ValueError):
        tag_movie(_FakeClient([]), _movie(synopsis=None))


def test_tag_movie_filters_tags_outside_the_controlled_vocabulary():
    payload = json.dumps({"tags": ["nostalgique", "invente", "social"], "mood_summary": "Ambiance."})
    client = _FakeClient(payload)

    result = tag_movie(client, _movie())

    assert result.tags == ["nostalgique", "social"]


def test_tag_movie_returns_none_when_below_minimum_tags():
    payload = json.dumps({"tags": ["invente"], "mood_summary": "Ambiance."})
    client = _FakeClient(payload)

    assert tag_movie(client, _movie()) is None


def test_tag_movie_returns_none_on_invalid_json():
    client = _FakeClient("not valid json")

    assert tag_movie(client, _movie()) is None


def test_tag_movies_paces_calls_and_skips_unparseable_results():
    payloads = [
        json.dumps({"tags": ["nostalgique", "social"], "mood_summary": "A"}),
        "not valid json",
    ]
    client = _FakeClient(payloads)
    movies = [_movie(id=1), _movie(id=2, title="Second")]
    sleeps = []

    results = dict(tag_movies(client, movies, delay_seconds=2.0, sleep_fn=sleeps.append))

    assert [m.id for m in results] == [1]
    assert sleeps == [2.0]


def test_tag_movies_stops_after_consecutive_errors_instead_of_burning_the_list():
    class _AlwaysFailingModels(_FakeModels):
        def generate_content(self, model, contents, config):
            self.calls.append(None)
            raise RuntimeError("quota exceeded")

    client = _FakeClient([])
    client.models = _AlwaysFailingModels([])
    movies = [_movie(id=i) for i in range(1, 51)]

    results = list(tag_movies(client, movies, delay_seconds=0, sleep_fn=lambda _: None, max_consecutive_errors=3))

    assert results == []
    assert len(client.models.calls) == 3


def test_tag_movies_continues_past_a_raising_call():
    class _RaisingModels(_FakeModels):
        def generate_content(self, model, contents, config):
            if len(self.calls) == 0:
                self.calls.append(None)
                raise RuntimeError("quota exceeded")
            return super().generate_content(model, contents, config)

    client = _FakeClient([])
    client.models = _RaisingModels([json.dumps({"tags": ["tendu", "sombre"], "mood_summary": "B"})])
    movies = [_movie(id=1), _movie(id=2, title="Second")]

    results = dict(tag_movies(client, movies, delay_seconds=0, sleep_fn=lambda _: None))

    assert [m.id for m in results] == [2]
