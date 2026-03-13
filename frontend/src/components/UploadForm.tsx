import { useRef, useState } from "react";
import { presignUpload, uploadFile } from "../api/client";
import type { PresignResponse } from "../types/job";

interface Props {
  onPresigned: (presign: PresignResponse, file: File) => void;
}

const ACCEPTED = ".fastq,.fastq.gz,.bam,.fq,.fq.gz";

export function UploadForm({ onPresigned }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleFile(file: File) {
    setError(null);
    setUploading(true);
    try {
      const presign = await presignUpload(file.name, file.size);
      await uploadFile(presign.upload_url, file);
      onPresigned(presign, file);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Upload failed.";
      setError(msg);
    } finally {
      setUploading(false);
    }
  }

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
  }

  function handleDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    const file = e.dataTransfer.files?.[0];
    if (file) handleFile(file);
  }

  return (
    <div style={styles.wrapper}>
      <h2 style={styles.title}>Bioinformatics Pipeline</h2>
      <p style={styles.subtitle}>Upload a FASTQ or BAM file to get started.</p>

      <div
        style={styles.dropzone}
        onDragOver={(e) => e.preventDefault()}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => e.key === "Enter" && inputRef.current?.click()}
      >
        {uploading ? (
          <span style={styles.hint}>Uploading…</span>
        ) : (
          <>
            <span style={styles.icon}>📂</span>
            <span style={styles.hint}>Drag & drop or click to select</span>
            <span style={styles.accepted}>{ACCEPTED}</span>
          </>
        )}
      </div>

      <input
        ref={inputRef}
        type="file"
        accept={ACCEPTED}
        style={{ display: "none" }}
        onChange={handleChange}
      />

      {error && <p style={styles.error}>{error}</p>}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  wrapper: { maxWidth: 480, margin: "0 auto", textAlign: "center" },
  title: { fontSize: 24, fontWeight: 700, marginBottom: 4 },
  subtitle: { color: "#666", marginBottom: 24 },
  dropzone: {
    border: "2px dashed #3b82f6",
    borderRadius: 12,
    padding: "48px 24px",
    cursor: "pointer",
    background: "#eff6ff",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: 8,
    transition: "background 0.15s",
  },
  icon: { fontSize: 40 },
  hint: { fontSize: 16, color: "#1d4ed8", fontWeight: 500 },
  accepted: { fontSize: 12, color: "#6b7280" },
  error: { color: "#dc2626", marginTop: 12 },
};
