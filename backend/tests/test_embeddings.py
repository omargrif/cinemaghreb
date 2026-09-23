import numpy as np
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.embeddings.build_index import build_index
from app.embeddings.index import VibeIndex
from app.embeddings.projection import _n_neighbors, project_2d
from app.embeddings.text_builder import build_embedding_text, is_embeddable
from app.models.movie import Movie
from tests.fakes import FakeEmbedder


@pytest.fixture()
def index(tmp_path):
    return VibeIndex(str(tmp_path / "chroma"), embedder=FakeEmbedder())


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    yield db
    db.close()


def test_build_embedding_text_puts_mood_before_synopsis():
    movie = Movie(
        title="X", synopsis="Un plot.", mood_summary="Une ambiance.",
        ambiance_tags=["nostalgique", "social"], genres=["Drame"],
    )

    text = build_embedding_text(movie)

    assert text.index("Une ambiance.") < text.index("Un plot.")
    assert "nostalgique, social" in text
    assert "Drame" in text


def test_is_embeddable_requires_synopsis_or_mood_summary():
    assert not is_embeddable(Movie(title="Only a title"))
    assert is_embeddable(Movie(title="A", synopsis="text"))
    assert is_embeddable(Movie(title="B", mood_summary="text"))


def test_search_ranks_matching_text_first(index):
    index.rebuild([1, 2, 3], ["exil et nostalgie", "fête sur la mer", "police dans le désert"])

    hits = index.search("un film sur l'exil", top_k=3)

    assert hits[0].movie_id == 1
    assert hits[0].score > hits[-1].score


def test_similar_to_excludes_the_movie_itself(index):
    index.rebuild([1, 2, 3], ["exil nostalgie", "exil nostalgie fête", "police désert"])

    hits = index.similar_to(1, top_k=2)

    assert hits[0].movie_id == 2
    assert 1 not in [h.movie_id for h in hits]


def test_similar_to_unknown_movie_returns_empty(index):
    index.rebuild([1], ["exil"])

    assert index.similar_to(999) == []


def test_rebuild_replaces_previous_collection(index):
    index.rebuild([1, 2], ["exil", "mer"])
    index.rebuild([3], ["désert"])

    hits = index.search("exil", top_k=10)

    assert [h.movie_id for h in hits] == [3]


def test_n_neighbors_scales_with_corpus_size_within_bounds():
    assert _n_neighbors(3) == 2  # can never exceed n - 1
    assert _n_neighbors(36) == 6
    assert _n_neighbors(10_000) == 15


def test_project_2d_handles_tiny_and_normal_corpora():
    assert project_2d(np.ones((2, 4))).shape == (2, 2)
    rng = np.random.default_rng(0)
    assert project_2d(rng.normal(size=(30, 8))).shape == (30, 2)


def test_build_index_writes_coordinates_only_for_embeddable_movies(session, index):
    session.add_all([
        Movie(title="A", synopsis="exil nostalgie"),
        Movie(title="B", synopsis="fête mer"),
        Movie(title="C", synopsis="police désert"),
        Movie(title="No text at all"),
    ])
    session.commit()

    indexed = build_index(session, index)

    assert indexed == 3
    by_title = {m.title: m for m in session.query(Movie).all()}
    assert by_title["A"].umap_x is not None and by_title["A"].umap_y is not None
    assert by_title["No text at all"].umap_x is None
