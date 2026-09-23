from app.data_collection.merge import (
    compute_completeness_report,
    group_by_identity,
    merge_all_sources,
    normalize_title,
)
from app.data_collection.schema import RawMovie


def test_normalize_title_strips_accents_punctuation_and_case():
    assert normalize_title("L'Été, à Casablanca!") == "l ete a casablanca"


def test_group_by_identity_groups_on_shared_imdb_id():
    a = RawMovie(imdb_id="tt1", title="Film A", source="tmdb")
    b = RawMovie(imdb_id="tt1", title="Film A", source="imdb_dataset")
    c = RawMovie(imdb_id="tt2", title="Other Film", source="tmdb")

    groups = group_by_identity([a, b, c])

    group_sizes = sorted(len(g) for g in groups)
    assert group_sizes == [1, 2]


def test_group_by_identity_fuzzy_matches_same_year_titles_without_imdb_id():
    a = RawMovie(title="Casablanca Beats", year=2021, source="imdb_dataset")
    b = RawMovie(title="Casablanca Beats!", year=2021, source="imdb_dataset")
    c = RawMovie(title="Completely Different Movie", year=2021, source="imdb_dataset")

    groups = group_by_identity([a, b, c])

    sizes = sorted(len(g) for g in groups)
    assert sizes == [1, 2]


def test_group_by_identity_does_not_match_across_different_years():
    a = RawMovie(title="Same Title", year=2000, source="imdb_dataset")
    b = RawMovie(title="Same Title", year=2010, source="imdb_dataset")

    groups = group_by_identity([a, b])

    assert len(groups) == 2


def test_merge_group_prefers_tmdb_synopsis_but_falls_back_to_imdb_director():
    tmdb_movie = RawMovie(
        tmdb_id=1, imdb_id="tt1", title="Film", year=2020,
        countries=["MA"], synopsis="TMDB synopsis", synopsis_language="fr",
        source="tmdb",
    )
    imdb_movie = RawMovie(
        imdb_id="tt1", title="Film", year=2020,
        countries=["MA", "FR"], director="Jane Director", cast=["A", "B"],
        source="imdb_dataset",
    )

    merged = merge_all_sources([tmdb_movie, imdb_movie])

    assert len(merged) == 1
    result = merged[0]
    assert result.synopsis == "TMDB synopsis"
    assert result.director == "Jane Director"
    assert result.countries == ["FR", "MA"]
    assert result.source == "imdb_dataset+tmdb"


def test_compute_completeness_report_counts_missing_fields_overall_and_per_country():
    movies = [
        RawMovie(title="A", countries=["MA"], synopsis="has one", director="D", cast=["X"], source="tmdb"),
        RawMovie(title="B", countries=["MA"], source="imdb_dataset"),
        RawMovie(title="C", countries=["DZ"], synopsis="s", source="tmdb"),
    ]

    report = compute_completeness_report(movies, {"MA": "Morocco", "DZ": "Algeria"})

    assert report["total_movies"] == 3
    assert report["with_synopsis"] == 2
    assert report["pct_missing_synopsis"] == round(100 / 3, 1)
    assert report["per_country"]["MA"]["total"] == 2
    assert report["per_country"]["MA"]["pct_missing_synopsis"] == 50.0
    assert report["per_country"]["DZ"]["pct_missing_synopsis"] == 0.0
