from app.data_collection.omdb_collector import _split_list, parse_omdb_record


def test_split_list_handles_na_and_empty():
    assert _split_list("N/A") == []
    assert _split_list(None) == []
    assert _split_list("Anna, Karim, Youssef") == ["Anna", "Karim", "Youssef"]


def test_parse_omdb_record_maps_fields():
    data = {
        "imdbID": "tt1234567",
        "Title": "Test Movie",
        "Year": "2015–2016",
        "Country": "Morocco, France",
        "Director": "N/A",
        "Actors": "A, B",
        "Plot": "A great plot.",
        "Genre": "Drama",
        "Poster": "N/A",
    }

    movie = parse_omdb_record(data)

    assert movie.imdb_id == "tt1234567"
    assert movie.year == 2015
    assert movie.countries == ["Morocco", "France"]
    assert movie.director is None
    assert movie.cast == ["A", "B"]
    assert movie.synopsis == "A great plot."
    assert movie.synopsis_language == "en"
    assert movie.poster_url is None
    assert movie.source == "omdb"


def test_parse_omdb_record_handles_missing_plot():
    data = {"imdbID": "tt1", "Title": "X", "Year": "2020", "Plot": "N/A"}
    movie = parse_omdb_record(data)
    assert movie.synopsis is None
