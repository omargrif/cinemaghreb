import { useEffect, useMemo, useState } from "react";
import { fetchMovie, fetchMovies, fetchSimilar, vibeSearch } from "./api/client";
import { hasPosition } from "./api/types";
import type { MovieDetail as MovieDetailData, PositionedMovie, ScoredMovie } from "./api/types";
import { MovieDetail } from "./components/MovieDetail";
import { ResultsList } from "./components/ResultsList";
import { COLOR_BY_LABELS, SemanticMap } from "./components/SemanticMap";
import type { ColorBy } from "./components/SemanticMap";
import { VibeSearchBar } from "./components/VibeSearchBar";

const message = (error: unknown) => (error instanceof Error ? error.message : String(error));

export default function App() {
  const [movies, setMovies] = useState<PositionedMovie[]>([]);
  const [loadState, setLoadState] = useState<"loading" | "ready" | "error">("loading");
  const [loadError, setLoadError] = useState<string | null>(null);
  const [colorBy, setColorBy] = useState<ColorBy>("genre");

  const [results, setResults] = useState<ScoredMovie[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);

  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<MovieDetailData | null>(null);
  const [similar, setSimilar] = useState<ScoredMovie[]>([]);

  useEffect(() => {
    fetchMovies()
      .then((list) => {
        setMovies(list.filter(hasPosition));
        setLoadState("ready");
      })
      .catch((error) => {
        setLoadError(message(error));
        setLoadState("error");
      });
  }, []);

  useEffect(() => {
    setDetail(null);
    setSimilar([]);
    if (selectedId === null) return;
    let cancelled = false;
    Promise.all([fetchMovie(selectedId), fetchSimilar(selectedId)])
      .then(([movie, neighbours]) => {
        if (cancelled) return;
        setDetail(movie);
        setSimilar(neighbours);
      })
      .catch((error) => {
        if (!cancelled) setSearchError(message(error));
      });
    return () => {
      cancelled = true;
    };
  }, [selectedId]);

  const runSearch = async (query: string) => {
    setSearching(true);
    setSearchError(null);
    setSelectedId(null);
    try {
      setResults(await vibeSearch(query));
    } catch (error) {
      setResults(null);
      setSearchError(message(error));
    } finally {
      setSearching(false);
    }
  };

  const clearSearch = () => {
    setResults(null);
    setSelectedId(null);
    setSearchError(null);
  };

  // On the map: neighbours of the open movie, else the current search results.
  const highlighted = useMemo(() => {
    const source = selectedId !== null ? similar : (results ?? []);
    return new Map(source.map(({ movie, score }) => [movie.id, score]));
  }, [selectedId, similar, results]);

  return (
    <div className="app">
      <header>
        <div className="brand">
          <h1>CineMaghreb</h1>
          <p>Découvrir le cinéma maghrébin par ambiance</p>
        </div>
        <VibeSearchBar loading={searching} hasResults={results !== null} onSearch={runSearch} onClear={clearSearch} />
      </header>

      <main>
        <section className="map-panel" aria-label="Carte sémantique">
          <div className="toolbar">
            <span>{loadState === "ready" ? `${movies.length} films sur la carte` : ""}</span>
            <label>
              Couleur par
              <select value={colorBy} onChange={(event) => setColorBy(event.target.value as ColorBy)}>
                {(Object.keys(COLOR_BY_LABELS) as ColorBy[]).map((key) => (
                  <option key={key} value={key}>
                    {COLOR_BY_LABELS[key]}
                  </option>
                ))}
              </select>
            </label>
          </div>

          {loadState === "loading" && <p className="state">Chargement de la carte…</p>}
          {loadState === "error" && (
            <p className="state error">Impossible de charger les films : {loadError}</p>
          )}
          {loadState === "ready" && movies.length === 0 && (
            <p className="state">
              Aucun film n'est encore placé sur la carte. Lancez la collecte puis
              <code> python -m app.embeddings.build_index </code> côté backend.
            </p>
          )}
          {loadState === "ready" && movies.length > 0 && (
            <SemanticMap
              movies={movies}
              colorBy={colorBy}
              highlighted={highlighted}
              selectedId={selectedId}
              onSelect={setSelectedId}
            />
          )}
        </section>

        <aside className="side-panel">
          {searchError && <p className="state error">{searchError}</p>}
          {selectedId !== null ? (
            <MovieDetail
              detail={detail?.id === selectedId ? detail : null}
              similar={similar}
              onBack={() => setSelectedId(null)}
              onSelect={setSelectedId}
            />
          ) : results !== null ? (
            <ResultsList title={`${results.length} films proches de cette ambiance`} results={results} onSelect={setSelectedId} />
          ) : (
            <p className="hint">
              Décrivez une ambiance ou choisissez une suggestion pour éclairer les films correspondants sur la carte.
              Cliquez sur un point pour ouvrir un film et voir ses voisins.
            </p>
          )}
        </aside>
      </main>
    </div>
  );
}
