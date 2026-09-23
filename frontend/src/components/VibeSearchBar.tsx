import { useState } from "react";

// Full sentences rather than single words: the search embeds the query the same
// way it embeds synopses, and a descriptive phrase matches better than one adjective.
const PRESETS: { label: string; query: string }[] = [
  { label: "Nostalgique", query: "un film nostalgique sur le souvenir et le temps qui passe" },
  { label: "Onirique", query: "un film onirique, entre rêve et réalité" },
  { label: "Tendu", query: "un film tendu, oppressant, qui ne laisse pas respirer" },
  { label: "Chaleureux", query: "un film chaleureux sur la famille et la vie de quartier" },
  { label: "Politique", query: "un film politique sur le pouvoir et la révolte" },
  { label: "Poétique", query: "un film poétique et contemplatif" },
  { label: "Exil", query: "un film sur l'exil et la migration" },
  { label: "Festif", query: "un film festif, plein de musique et d'énergie" },
];

interface Props {
  loading: boolean;
  hasResults: boolean;
  onSearch: (query: string) => void;
  onClear: () => void;
}

export function VibeSearchBar({ loading, hasResults, onSearch, onClear }: Props) {
  const [text, setText] = useState("");

  const submit = (query: string) => {
    const trimmed = query.trim();
    if (trimmed) onSearch(trimmed);
  };

  return (
    <div className="search">
      <form
        onSubmit={(event) => {
          event.preventDefault();
          submit(text);
        }}
      >
        <input
          type="search"
          value={text}
          onChange={(event) => setText(event.target.value)}
          placeholder="Décrivez une ambiance… « un film mélancolique sur l'exil »"
          aria-label="Décrire une ambiance"
        />
        <button type="submit" disabled={loading || !text.trim()}>
          {loading ? "Recherche…" : "Chercher"}
        </button>
        {hasResults && (
          <button
            type="button"
            className="secondary"
            onClick={() => {
              setText("");
              onClear();
            }}
          >
            Effacer
          </button>
        )}
      </form>
      <div className="chips" aria-label="Ambiances suggérées">
        {PRESETS.map((preset) => (
          <button
            key={preset.label}
            type="button"
            className="chip"
            disabled={loading}
            onClick={() => {
              setText(preset.query);
              submit(preset.query);
            }}
          >
            {preset.label}
          </button>
        ))}
      </div>
    </div>
  );
}
