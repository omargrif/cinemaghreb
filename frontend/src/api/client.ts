import type { MovieDetail, MovieSummary, ScoredMovie } from "./types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  if (!response.ok) {
    // FastAPI puts a human-readable message in `detail` (e.g. "index not built").
    const body = await response.json().catch(() => null);
    throw new Error(typeof body?.detail === "string" ? body.detail : `Erreur ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export const fetchMovies = () => request<MovieSummary[]>("/api/movies");

export const fetchMovie = (id: number) => request<MovieDetail>(`/api/movies/${id}`);

export const fetchSimilar = (id: number, topK = 10) =>
  request<ScoredMovie[]>(`/api/movies/${id}/similar?top_k=${topK}`);

export const vibeSearch = (query: string, topK = 20) =>
  request<ScoredMovie[]>("/api/search/vibe", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, top_k: topK }),
  });
