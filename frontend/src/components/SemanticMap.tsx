import * as d3 from "d3";
import { useEffect, useMemo, useRef, useState } from "react";
import type { PositionedMovie } from "../api/types";

export type ColorBy = "genre" | "country" | "decade";

export const COLOR_BY_LABELS: Record<ColorBy, string> = {
  genre: "Genre",
  country: "Pays",
  decade: "Décennie",
};

interface Props {
  movies: PositionedMovie[];
  colorBy: ColorBy;
  /** movie id -> similarity score; when non-empty, everything else fades back. */
  highlighted: Map<number, number>;
  selectedId: number | null;
  onSelect: (id: number) => void;
}

const PADDING = 36;
const MAX_LEGEND_ENTRIES = 9;
const OTHER_LABEL = "Autres";

/** Inks chosen to sit on the cream page and stay apart from each other. */
const INK_PALETTE = [
  "#2b3a6b",
  "#a8492a",
  "#436b5f",
  "#b08315",
  "#6d3560",
  "#1f6f77",
  "#8a5524",
  "#55603a",
  "#93304a",
];
const OTHER_COLOR = "#8b8471";

const SELECTED_STROKE = "#1c1a15";
const HIGHLIGHT_STROKE = "rgba(28, 26, 21, 0.7)";

const regionNames = new Intl.DisplayNames(["fr"], { type: "region" });

function categoryOf(movie: PositionedMovie, colorBy: ColorBy): string {
  switch (colorBy) {
    case "genre":
      return movie.genres[0] ?? OTHER_LABEL;
    case "country": {
      const code = movie.countries[0];
      return code ? (regionNames.of(code) ?? code) : OTHER_LABEL;
    }
    case "decade":
      return movie.year ? `${Math.floor(movie.year / 10) * 10}s` : OTHER_LABEL;
  }
}

/** Most frequent categories get their own color; the long tail shares one gray. */
function buildPalette(movies: PositionedMovie[], colorBy: ColorBy) {
  const counts = new Map<string, number>();
  for (const movie of movies) {
    const category = categoryOf(movie, colorBy);
    counts.set(category, (counts.get(category) ?? 0) + 1);
  }
  const top = [...counts.entries()]
    .filter(([category]) => category !== OTHER_LABEL)
    .sort((a, b) => b[1] - a[1])
    .slice(0, MAX_LEGEND_ENTRIES)
    .map(([category]) => category);
  if (top.length < counts.size) top.push(OTHER_LABEL);

  const colorOf = new Map(
    top.map((category, i) => [category, category === OTHER_LABEL ? OTHER_COLOR : INK_PALETTE[i % INK_PALETTE.length]]),
  );
  return {
    legend: top.map((category) => ({ category, color: colorOf.get(category) ?? OTHER_COLOR })),
    colorFor: (movie: PositionedMovie) => colorOf.get(categoryOf(movie, colorBy)) ?? OTHER_COLOR,
  };
}

function useElementSize<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [size, setSize] = useState({ width: 0, height: 0 });
  useEffect(() => {
    const element = ref.current;
    if (!element) return;
    const observer = new ResizeObserver(([entry]) =>
      setSize({ width: entry.contentRect.width, height: entry.contentRect.height }),
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  return [ref, size] as const;
}

export function SemanticMap({ movies, colorBy, highlighted, selectedId, onSelect }: Props) {
  const [containerRef, { width, height }] = useElementSize<HTMLDivElement>();
  const svgRef = useRef<SVGSVGElement>(null);
  const zoomRef = useRef<d3.ZoomBehavior<SVGSVGElement, unknown> | null>(null);
  const [transform, setTransform] = useState<d3.ZoomTransform>(d3.zoomIdentity);
  const [hovered, setHovered] = useState<PositionedMovie | null>(null);

  useEffect(() => {
    const svg = svgRef.current;
    if (!svg) return;
    const zoom = d3
      .zoom<SVGSVGElement, unknown>()
      .scaleExtent([1, 30])
      .on("zoom", (event) => setTransform(event.transform));
    zoomRef.current = zoom;
    d3.select(svg).call(zoom);
    return () => {
      d3.select(svg).on(".zoom", null);
    };
  }, []);

  const xScale = useMemo(() => {
    const [min, max] = d3.extent(movies, (m) => m.umap_x);
    return d3.scaleLinear().domain([min ?? 0, max ?? 1]).range([PADDING, Math.max(width - PADDING, PADDING + 1)]);
  }, [movies, width]);

  const yScale = useMemo(() => {
    const [min, max] = d3.extent(movies, (m) => m.umap_y);
    return d3.scaleLinear().domain([min ?? 0, max ?? 1]).range([Math.max(height - PADDING, PADDING + 1), PADDING]);
  }, [movies, height]);

  const palette = useMemo(() => buildPalette(movies, colorBy), [movies, colorBy]);

  // Draw order: faded points first, highlighted next, selected on top.
  const drawOrder = useMemo(() => {
    const weight = (m: PositionedMovie) => (m.id === selectedId ? 2 : highlighted.has(m.id) ? 1 : 0);
    return [...movies].sort((a, b) => weight(a) - weight(b));
  }, [movies, highlighted, selectedId]);

  const hasHighlight = highlighted.size > 0;
  const radiusScale = Math.min(1 + (transform.k - 1) * 0.25, 2.5);

  const resetZoom = () => {
    if (svgRef.current && zoomRef.current) {
      d3.select(svgRef.current).transition().duration(400).call(zoomRef.current.transform, d3.zoomIdentity);
    }
  };

  const screenX = (m: PositionedMovie) => transform.applyX(xScale(m.umap_x));
  const screenY = (m: PositionedMovie) => transform.applyY(yScale(m.umap_y));

  return (
    <div className="map" ref={containerRef}>
      <svg
        ref={svgRef}
        width={width}
        height={height}
        role="img"
        aria-label="Carte sémantique des films : les films proches par l'ambiance sont proches sur la carte"
      >
        {drawOrder.map((movie) => {
          const isSelected = movie.id === selectedId;
          const isHighlighted = highlighted.has(movie.id);
          const dimmed = hasHighlight && !isHighlighted && !isSelected;
          const radius = (isSelected ? 9 : isHighlighted ? 7 : 4.5) * radiusScale;
          return (
            <circle
              key={movie.id}
              cx={screenX(movie)}
              cy={screenY(movie)}
              r={radius}
              fill={palette.colorFor(movie)}
              fillOpacity={dimmed ? 0.18 : 0.85}
              stroke={isSelected ? SELECTED_STROKE : isHighlighted ? HIGHLIGHT_STROKE : "none"}
              strokeWidth={isSelected ? 2.5 : 1.5}
              className="map-point"
              onMouseEnter={() => setHovered(movie)}
              onMouseLeave={() => setHovered((current) => (current?.id === movie.id ? null : current))}
              onClick={() => onSelect(movie.id)}
            />
          );
        })}
      </svg>

      {hovered && (
        <div
          className="map-tooltip"
          style={{
            left: Math.min(screenX(hovered) + 14, Math.max(width - 230, 0)),
            top: Math.max(screenY(hovered) - 44, 4),
          }}
        >
          <strong>{hovered.title}</strong>
          <span>{[hovered.year, hovered.genres[0]].filter(Boolean).join(" · ")}</span>
        </div>
      )}

      <ul className="map-legend" aria-label={`Couleurs par ${COLOR_BY_LABELS[colorBy].toLowerCase()}`}>
        {palette.legend.map(({ category, color }) => (
          <li key={category}>
            <span className="swatch" style={{ background: color }} />
            {category}
          </li>
        ))}
      </ul>

      <button type="button" className="map-reset" onClick={resetZoom}>
        Recentrer
      </button>
    </div>
  );
}
