import csv
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.data_collection.load_to_db import CSV_FIELDS, load_csv
from app.db.base import Base
from app.models.movie import Movie


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    yield db
    db.close()


def _write_csv(path: Path, rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _row(**overrides) -> dict:
    base = dict.fromkeys(CSV_FIELDS, "")
    base.update(overrides)
    return base


def test_load_csv_creates_movies(tmp_path, session):
    csv_path = tmp_path / "movies.csv"
    _write_csv(csv_path, [
        _row(tmdb_id="1", title="Much Loved", year="2015", countries="MA", genres="Drama|Social", source="tmdb"),
    ])

    created, updated = load_csv(csv_path, session=session)

    assert (created, updated) == (1, 0)
    movie = session.query(Movie).one()
    assert movie.title == "Much Loved"
    assert movie.year == 2015
    assert movie.countries == ["MA"]
    assert movie.genres == ["Drama", "Social"]


def test_load_csv_upserts_by_tmdb_id(tmp_path, session):
    csv_path = tmp_path / "movies.csv"
    _write_csv(csv_path, [_row(tmdb_id="1", title="Original Title", source="tmdb")])
    load_csv(csv_path, session=session)

    _write_csv(csv_path, [_row(tmdb_id="1", title="Updated Title", source="tmdb")])
    created, updated = load_csv(csv_path, session=session)

    assert (created, updated) == (0, 1)
    assert session.query(Movie).count() == 1
    assert session.query(Movie).one().title == "Updated Title"


def test_load_csv_falls_back_to_imdb_id_when_no_tmdb_id(tmp_path, session):
    csv_path = tmp_path / "movies.csv"
    _write_csv(csv_path, [_row(imdb_id="tt123", title="First Pass", source="imdb_dataset")])
    load_csv(csv_path, session=session)

    _write_csv(csv_path, [_row(imdb_id="tt123", title="Second Pass", source="imdb_dataset")])
    created, updated = load_csv(csv_path, session=session)

    assert (created, updated) == (0, 1)
    assert session.query(Movie).one().title == "Second Pass"
