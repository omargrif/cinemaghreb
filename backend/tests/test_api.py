import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_vibe_index
from app.api.main import app
from app.db.base import Base
from app.db.session import get_db
from app.embeddings.index import VibeIndex
from app.models.movie import Movie
from tests.fakes import FakeEmbedder


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


@pytest.fixture()
def index(tmp_path):
    return VibeIndex(str(tmp_path / "chroma"), embedder=FakeEmbedder())


@pytest.fixture()
def client(db, index):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_vibe_index] = lambda: index
    yield TestClient(app)
    app.dependency_overrides.clear()


def _seed(db, index):
    db.add_all([
        Movie(id=1, title="Le Retour", year=2010, genres=["Drame"], countries=["MA"],
              synopsis="exil nostalgie", umap_x=0.1, umap_y=0.2, ambiance_tags=["nostalgique"]),
        Movie(id=2, title="La Fête", year=2015, genres=["Comédie"], countries=["TN"],
              synopsis="fête mer", umap_x=0.5, umap_y=0.6),
        Movie(id=3, title="Le Désert", year=2019, genres=["Thriller"], countries=["DZ"],
              synopsis="police désert", umap_x=0.9, umap_y=0.1),
        Movie(id=4, title="Sans synopsis", year=2001),
    ])
    db.commit()
    index.rebuild([1, 2, 3], ["exil nostalgie", "fête mer", "police désert"])


def test_list_movies_returns_only_movies_with_map_position(client, db, index):
    _seed(db, index)

    response = client.get("/api/movies")

    assert response.status_code == 200
    assert [m["id"] for m in response.json()] == [1, 2, 3]
    assert response.json()[0]["umap_x"] == 0.1


def test_get_movie_returns_detail_and_404_for_unknown(client, db, index):
    _seed(db, index)

    detail = client.get("/api/movies/1").json()
    assert detail["title"] == "Le Retour"
    assert detail["synopsis"] == "exil nostalgie"
    assert detail["ambiance_tags"] == ["nostalgique"]

    assert client.get("/api/movies/999").status_code == 404


def test_vibe_search_ranks_best_match_first(client, db, index):
    _seed(db, index)

    response = client.post("/api/search/vibe", json={"query": "un film sur l'exil", "top_k": 3})

    assert response.status_code == 200
    results = response.json()
    assert results[0]["movie"]["id"] == 1
    assert results[0]["score"] > results[-1]["score"]


def test_vibe_search_rejects_empty_query(client, db, index):
    assert client.post("/api/search/vibe", json={"query": ""}).status_code == 422


def test_vibe_search_returns_503_when_index_not_built(client):
    response = client.post("/api/search/vibe", json={"query": "exil"})

    assert response.status_code == 503
    assert "build_index" in response.json()["detail"]


def test_vibe_search_skips_hits_missing_from_db(client, db, index):
    _seed(db, index)
    db.delete(db.get(Movie, 1))
    db.commit()

    results = client.post("/api/search/vibe", json={"query": "exil", "top_k": 3}).json()

    assert 1 not in [r["movie"]["id"] for r in results]
    assert len(results) == 2


def test_similar_movies_excludes_itself(client, db, index):
    _seed(db, index)

    response = client.get("/api/movies/1/similar?top_k=2")

    assert response.status_code == 200
    ids = [r["movie"]["id"] for r in response.json()]
    assert 1 not in ids
    assert len(ids) == 2


def test_similar_movies_404_for_unknown_movie(client, db, index):
    _seed(db, index)

    assert client.get("/api/movies/999/similar").status_code == 404


def test_similar_movies_empty_for_movie_not_in_index(client, db, index):
    _seed(db, index)

    assert client.get("/api/movies/4/similar").json() == []
