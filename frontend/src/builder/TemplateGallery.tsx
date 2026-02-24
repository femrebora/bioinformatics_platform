import { useState } from "react";
import { PIPELINE_TEMPLATES, type PipelineTemplate } from "./templates";

interface TemplateGalleryProps {
  onClose:  () => void;
  onSelect: (template: PipelineTemplate) => void;
}

export function TemplateGallery({ onClose, onSelect }: TemplateGalleryProps) {
  return (
    <div style={s.backdrop} onClick={onClose}>
      <div style={s.modal} onClick={(e) => e.stopPropagation()}>

        {/* Header */}
        <div style={s.header}>
          <div>
            <h2 style={s.title}>Pipeline Templates</h2>
            <p style={s.subtitle}>
              Start from a pre-built layout — customise it after applying.
            </p>
          </div>
          <button onClick={onClose} style={s.closeBtn}>✕</button>
        </div>

        {/* Grid */}
        <div style={s.grid}>
          {PIPELINE_TEMPLATES.map((tpl) => (
            <TemplateCard
              key={tpl.id}
              template={tpl}
              onSelect={() => { onSelect(tpl); onClose(); }}
            />
          ))}
        </div>

      </div>
    </div>
  );
}

// ── Template Card ─────────────────────────────────────────────────────────

function TemplateCard({
  template,
  onSelect,
}: {
  template: PipelineTemplate;
  onSelect: () => void;
}) {
  const [hovered, setHovered] = useState(false);

  return (
    <div
      style={{ ...s.card, ...(hovered ? s.cardHover : {}) }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onClick={onSelect}
    >
      <div style={s.cardIcon}>{template.icon}</div>
      <div style={s.cardName}>{template.name}</div>
      <div style={s.cardDesc}>{template.description}</div>

      <div style={s.cardTags}>
        {template.tags.map((t) => (
          <span key={t} style={s.tag}>{t}</span>
        ))}
      </div>

      {hovered && (
        <div style={s.useOverlay}>
          <span style={s.useBtn}>Use Template →</span>
        </div>
      )}
    </div>
  );
}

// ── Styles ────────────────────────────────────────────────────────────────

const s: Record<string, React.CSSProperties> = {
  backdrop: {
    position: "fixed", inset: 0,
    background: "rgba(0,0,0,0.45)",
    display: "flex", alignItems: "center", justifyContent: "center",
    zIndex: 190,
    backdropFilter: "blur(2px)",
  },
  modal: {
    width: "min(900px, 96vw)",
    maxHeight: "88vh",
    background: "#fff",
    borderRadius: 14,
    boxShadow: "0 24px 64px rgba(0,0,0,0.22)",
    display: "flex", flexDirection: "column",
    overflow: "hidden",
  },
  header: {
    display: "flex", alignItems: "flex-start", justifyContent: "space-between",
    padding: "24px 28px 20px",
    borderBottom: "1px solid #e5e7eb",
    flexShrink: 0,
  },
  title: {
    margin: 0, fontSize: 20, fontWeight: 700, color: "#111827",
  },
  subtitle: {
    margin: "4px 0 0", fontSize: 13, color: "#6b7280",
  },
  closeBtn: {
    border: "none", background: "none", cursor: "pointer",
    color: "#9ca3af", fontSize: 18, padding: "4px 6px",
    borderRadius: 6, lineHeight: 1,
  },
  grid: {
    flex: 1, overflowY: "auto",
    display: "grid",
    gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))",
    gap: 16,
    padding: "24px 28px",
  },
  card: {
    position: "relative",
    border: "1px solid #e5e7eb",
    borderRadius: 10,
    padding: "20px 18px",
    cursor: "pointer",
    background: "#fafafa",
    transition: "border-color 0.15s, box-shadow 0.15s, transform 0.12s",
    display: "flex", flexDirection: "column", gap: 8,
    overflow: "hidden",
  },
  cardHover: {
    borderColor: "#2563eb",
    boxShadow: "0 4px 16px rgba(37,99,235,0.12)",
    transform: "translateY(-2px)",
    background: "#fff",
  },
  cardIcon: {
    fontSize: 32, lineHeight: 1,
  },
  cardName: {
    fontSize: 14, fontWeight: 700, color: "#111827",
  },
  cardDesc: {
    fontSize: 12, color: "#6b7280", lineHeight: 1.5,
    flex: 1,
  },
  cardTags: {
    display: "flex", flexWrap: "wrap", gap: 4, marginTop: 4,
  },
  tag: {
    fontSize: 10, fontWeight: 500,
    background: "#eff6ff", color: "#1d4ed8",
    border: "1px solid #bfdbfe",
    padding: "1px 7px", borderRadius: 10,
  },
  useOverlay: {
    position: "absolute", inset: 0,
    background: "linear-gradient(to bottom, transparent 40%, rgba(37,99,235,0.08) 100%)",
    display: "flex", alignItems: "flex-end", justifyContent: "flex-end",
    padding: "12px 14px",
    pointerEvents: "none",
  },
  useBtn: {
    fontSize: 12, fontWeight: 700,
    color: "#2563eb",
    background: "#fff",
    padding: "4px 12px",
    borderRadius: 6,
    boxShadow: "0 1px 4px rgba(0,0,0,0.12)",
  },
};
