import { useState } from "react";

export default function SourcesPanel({ sources }) {
  const [open, setOpen] = useState(false);

  if (!sources || sources.length === 0) return null;

  return (
    <div style={{ marginTop: "8px" }}>
      <button
        onClick={() => setOpen(!open)}
        style={{
          background: "none",
          border: "none",
          color: "#6b7cff",
          cursor: "pointer",
          padding: 0,
          fontSize: "13px"
        }}
      >
        {open ? "Hide sources ▲" : `Sources (${sources.length}) ▼`}
      </button>

      {open && (
        <div style={{ marginTop: "6px" }}>
          {sources.map((s, i) => (
            <div
              key={i}
              style={{
                border: "1px solid #e5e7eb",
                borderRadius: "6px",
                padding: "8px",
                marginBottom: "6px",
                fontSize: "13px"
              }}
            >
              <div style={{ fontWeight: 600 }}>{s.title}</div>
              <div style={{ color: "#555", margin: "4px 0" }}>
                {s.snippet}
              </div>
              <a
                href={s.url}
                target="_blank"
                rel="noopener noreferrer"
                style={{ color: "#2563eb" }}
              >
                {new URL(s.url).hostname}
              </a>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
