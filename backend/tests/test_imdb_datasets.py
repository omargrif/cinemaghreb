from app.data_collection.imdb_datasets import (
    attach_countries,
    attach_crew,
    build_movies_from_basics,
    collect_cast_ids,
    collect_director_ids,
    find_candidate_regions,
    resolve_names,
)


def test_find_candidate_regions_filters_to_target_countries():
    akas_rows = [
        {"titleId": "tt1", "region": "MA"},
        {"titleId": "tt1", "region": "US"},
        {"titleId": "tt2", "region": "FR"},
        {"titleId": "tt3", "region": "DZ"},
    ]

    regions = find_candidate_regions(akas_rows, {"MA", "DZ"})

    assert regions == {"tt1": {"MA"}, "tt3": {"DZ"}}


def test_build_movies_from_basics_excludes_non_movie_types_and_non_candidates():
    basics_rows = [
        {"tconst": "tt1", "titleType": "movie", "primaryTitle": "A", "originalTitle": "A", "startYear": "2005", "genres": "Drama,War"},
        {"tconst": "tt2", "titleType": "tvSeries", "primaryTitle": "B", "originalTitle": "B", "startYear": "2010", "genres": "\\N"},
        {"tconst": "tt3", "titleType": "movie", "primaryTitle": "C", "originalTitle": "C", "startYear": "\\N", "genres": "\\N"},
    ]

    movies = build_movies_from_basics(basics_rows, candidate_tconsts={"tt1", "tt2", "tt3"})

    assert set(movies) == {"tt1", "tt3"}
    assert movies["tt1"].year == 2005
    assert movies["tt1"].genres == ["Drama", "War"]
    assert movies["tt3"].year is None
    assert movies["tt1"].source == "imdb_dataset"


def test_collect_director_ids_skips_null_marker():
    crew_rows = [
        {"tconst": "tt1", "directors": "nm1,nm2"},
        {"tconst": "tt2", "directors": "\\N"},
    ]

    directors = collect_director_ids(crew_rows, candidate_tconsts={"tt1", "tt2"})

    assert directors == {"tt1": ["nm1", "nm2"]}


def test_collect_cast_ids_orders_and_caps_at_ten():
    principals_rows = [
        {"tconst": "tt1", "category": "actor", "ordering": str(i), "nconst": f"nm{i}"} for i in range(12)
    ]
    principals_rows.append({"tconst": "tt1", "category": "writer", "ordering": "99", "nconst": "nmWriter"})

    cast = collect_cast_ids(principals_rows, candidate_tconsts={"tt1"})

    assert cast["tt1"] == [f"nm{i}" for i in range(10)]
    assert "nmWriter" not in cast["tt1"]


def test_resolve_names_only_keeps_needed_ids():
    name_rows = [
        {"nconst": "nm1", "primaryName": "Alice"},
        {"nconst": "nm2", "primaryName": "Bob"},
    ]

    names = resolve_names(name_rows, needed_nconsts={"nm1"})

    assert names == {"nm1": "Alice"}


def test_attach_crew_resolves_names_and_falls_back_to_id():
    movies = build_movies_from_basics(
        [{"tconst": "tt1", "titleType": "movie", "primaryTitle": "A", "originalTitle": "A", "startYear": "2020", "genres": "\\N"}],
        candidate_tconsts={"tt1"},
    )

    attach_crew(
        movies,
        director_ids={"tt1": ["nm1"]},
        cast_ids={"tt1": ["nm2", "nm3"]},
        names={"nm1": "Jane Director", "nm2": "Actor Two"},
    )

    assert movies["tt1"].director == "Jane Director"
    assert movies["tt1"].cast == ["Actor Two", "nm3"]  # nm3 has no resolved name, falls back to id


def test_attach_countries_sets_sorted_region_list():
    movies = build_movies_from_basics(
        [{"tconst": "tt1", "titleType": "movie", "primaryTitle": "A", "originalTitle": "A", "startYear": "2020", "genres": "\\N"}],
        candidate_tconsts={"tt1"},
    )

    attach_countries(movies, {"tt1": {"DZ", "MA"}})

    assert movies["tt1"].countries == ["DZ", "MA"]
