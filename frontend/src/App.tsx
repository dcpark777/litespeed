// Placeholder shell. Real UI (three-region layout, SPEC §7) is Phase 2 work —
// deliberately unstyled until then so no throwaway design accrues.
import React, { useEffect, useState } from "react";

export default function App() {
  const [health, setHealth] = useState<string>("checking…");
  useEffect(() => {
    fetch("/api/health")
      .then((r) => r.json())
      .then((d) => setHealth(d.ok ? "backend connected" : "backend unhealthy"))
      .catch(() => setHealth("backend unreachable"));
  }, []);
  return (
    <main style={{ fontFamily: "monospace", padding: "2rem" }}>
      <h1>nova</h1>
      <p>{health}</p>
      <p>Phase 2 builds the real UI. See SPEC.md §7.</p>
    </main>
  );
}
