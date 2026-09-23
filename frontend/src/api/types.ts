export interface MovieSummary {
  id: number;
  title: string;
  year: number | null;
  countries: string[];
  genres: string[];
  ambiance_tags: string[];
  poster_url: string | null;
  umap_x: number | null;
  umap_y: number | null;
}

export interface MovieDetail extends MovieSummary {
  original_title: string;
  director: string | null;
  cast: string[];
  synopsis: string | null;
  mood_summary: string | null;
  vote_average: number | null;
}

export interface ScoredMovie {
  movie: MovieSummary;
  score: number;
}

/** A movie the API has placed on the map (the list endpoint only returns these). */
export type PositionedMovie = MovieSummary & { umap_x: number; umap_y: number };

export function hasPosition(movie: MovieSummary): movie is PositionedMovie {
  return movie.umap_x !== null && movie.umap_y !== null;
}
