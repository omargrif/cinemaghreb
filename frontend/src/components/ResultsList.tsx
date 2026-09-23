import type { ScoredMovie } from "../api/types";

interface Props {
  title: string;
  results: ScoredMovie[];
  onSelect: (id: number) => void;
}

export function ResultsList({ title, results, onSelect }: Props) {
  return (
    <section>
      <h2>{title}</h2>
      {results.length === 0 ? (
        <p className="hint">Aucun film trouvé.</p>
      ) : (
        <ol className="results">
          {results.map(({ movie, score }) => (
            <li key={movie.id}>
              <button type="button" onClick={() => onSelect(movie.id)}>
                {movie.poster_url ? (
                  <img src={movie.poster_url} alt="" loading="lazy" />
                ) : (
                  <span className="poster-placeholder" aria-hidden="true" />
                )}
                <span className="result-text">
                  <strong>{movie.title}</strong>
                  <span className="meta">{[movie.year, movie.genres[0]].filter(Boolean).join(" · ")}</span>
                  {movie.ambiance_tags.length > 0 && (
                    <span className="meta">{movie.ambiance_tags.slice(0, 3).join(", ")}</span>
                  )}
                </span>
                <span className="score" title="Proximité avec la recherche">
                  {Math.round(score * 100)} %
                </span>
              </button>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
