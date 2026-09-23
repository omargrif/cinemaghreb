import type { MovieDetail as MovieDetailData, ScoredMovie } from "../api/types";
import { ResultsList } from "./ResultsList";

const regionNames = new Intl.DisplayNames(["fr"], { type: "region" });

interface Props {
  detail: MovieDetailData | null;
  similar: ScoredMovie[];
  onBack: () => void;
  onSelect: (id: number) => void;
}

export function MovieDetail({ detail, similar, onBack, onSelect }: Props) {
  if (!detail) {
    return <p className="hint">Chargement…</p>;
  }

  const countries = detail.countries.map((code) => regionNames.of(code) ?? code).join(", ");

  return (
    <article className="detail">
      <button type="button" className="back" onClick={onBack}>
        ← Retour
      </button>

      <div className="detail-head">
        {detail.poster_url && <img src={detail.poster_url} alt={`Affiche de ${detail.title}`} />}
        <div>
          <h2>
            {detail.title} {detail.year && <span className="year">({detail.year})</span>}
          </h2>
          {detail.original_title && detail.original_title !== detail.title && (
            <p className="meta">{detail.original_title}</p>
          )}
          {detail.director && <p className="meta">De {detail.director}</p>}
          {countries && <p className="meta">{countries}</p>}
          {detail.vote_average ? <p className="meta">Note TMDB : {detail.vote_average.toFixed(1)} / 10</p> : null}
        </div>
      </div>

      {detail.ambiance_tags.length > 0 && (
        <div className="tags">
          {detail.ambiance_tags.map((tag) => (
            <span key={tag} className="tag">
              {tag}
            </span>
          ))}
        </div>
      )}
      {detail.mood_summary && <p className="mood">{detail.mood_summary}</p>}
      {detail.synopsis && <p>{detail.synopsis}</p>}
      {detail.cast.length > 0 && <p className="meta">Avec {detail.cast.slice(0, 6).join(", ")}</p>}

      <ResultsList title="Films à l'ambiance proche" results={similar} onSelect={onSelect} />
    </article>
  );
}
