import responses

from app.data_collection.tmdb_collector import (
    TMDBClient,
    _pick_synopsis,
    discover_country_ids,
    fetch_movie_details,
    parse_movie_details,
)


def make_client() -> TMDBClient:
    return TMDBClient(api_key="test-key", request_delay_seconds=0)


@responses.activate
def test_discover_country_ids_paginates_until_total_pages():
    responses.add(
        responses.GET,
        "https://api.themoviedb.org/3/discover/movie",
        json={"results": [{"id": 1}, {"id": 2}], "total_pages": 2, "page": 1},
        match=[responses.matchers.query_param_matcher({"with_origin_country": "MA", "page": "1", "sort_by": "popularity.desc", "include_adult": "false", "api_key": "test-key"})],
    )
    responses.add(
        responses.GET,
        "https://api.themoviedb.org/3/discover/movie",
        json={"results": [{"id": 3}], "total_pages": 2, "page": 2},
        match=[responses.matchers.query_param_matcher({"with_origin_country": "MA", "page": "2", "sort_by": "popularity.desc", "include_adult": "false", "api_key": "test-key"})],
    )

    ids = discover_country_ids(make_client(), "MA")

    assert ids == {1, 2, 3}


@responses.activate
def test_discover_country_ids_respects_max_pages():
    responses.add(
        responses.GET,
        "https://api.themoviedb.org/3/discover/movie",
        json={"results": [{"id": 1}], "total_pages": 10, "page": 1},
    )

    ids = discover_country_ids(make_client(), "MA", max_pages=1)

    assert ids == {1}
    assert len(responses.calls) == 1


def test_pick_synopsis_prefers_arabic_then_french_then_english():
    translations = [
        {"iso_639_1": "en", "data": {"overview": "English plot"}},
        {"iso_639_1": "fr", "data": {"overview": "Intrigue en francais"}},
    ]
    text, lang = _pick_synopsis(translations, fallback_overview="fallback", fallback_language="en")
    assert (text, lang) == ("Intrigue en francais", "fr")


def test_pick_synopsis_falls_back_to_default_overview_when_no_translation_matches():
    text, lang = _pick_synopsis([], fallback_overview="Only this one", fallback_language="en")
    assert (text, lang) == ("Only this one", "en")


def test_pick_synopsis_returns_none_when_nothing_available():
    assert _pick_synopsis([], fallback_overview="", fallback_language="en") == (None, None)


def test_parse_movie_details_extracts_director_cast_and_countries():
    details = {
        "id": 42,
        "imdb_id": "tt0000042",
        "title": "Test Film",
        "original_title": "Film Test",
        "release_date": "2019-05-01",
        "production_countries": [{"iso_3166_1": "MA", "name": "Morocco"}],
        "original_language": "ar",
        "genres": [{"id": 1, "name": "Drama"}],
        "poster_path": "/poster.jpg",
        "vote_average": 7.2,
        "popularity": 12.3,
        "overview": "Default overview",
        "credits": {
            "crew": [{"name": "Jane Director", "job": "Director"}, {"name": "Other", "job": "Producer"}],
            "cast": [{"name": f"Actor {i}"} for i in range(15)],
        },
        "translations": {"translations": []},
        "external_ids": {},
    }

    movie = parse_movie_details(details)

    assert movie.tmdb_id == 42
    assert movie.imdb_id == "tt0000042"
    assert movie.year == 2019
    assert movie.countries == ["MA"]
    assert movie.director == "Jane Director"
    assert len(movie.cast) == 10  # capped
    assert movie.poster_url == "https://image.tmdb.org/t/p/w500/poster.jpg"
    assert movie.source == "tmdb"


@responses.activate
def test_fetch_movie_details_returns_none_on_http_error():
    responses.add(responses.GET, "https://api.themoviedb.org/3/movie/999", status=404)

    result = fetch_movie_details(make_client(), 999)

    assert result is None
