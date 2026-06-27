/** Keep narrative sections that mention the selected corner (by id or display name). */
export function filterNarrativeByCorner(
  narrative: string,
  cornerId?: string | null,
  cornerDisplay?: string | null,
  structuredSections?: { corner_id?: string; heading: string; body: string }[],
): string {
  if (!cornerId && !cornerDisplay) return narrative;

  if (structuredSections?.length) {
    const matched = structuredSections.filter(
      (s) =>
        s.corner_id === cornerId ||
        (cornerDisplay && s.heading.toLowerCase().includes(cornerDisplay.toLowerCase())),
    );
    if (matched.length) {
      return matched.map((s) => `### ${s.heading}\n${s.body}`).join("\n\n");
    }
  }

  const needles = [cornerId, cornerDisplay].filter(Boolean) as string[];
  const chunks = narrative.split(/(?=^### )/m);
  if (chunks.length <= 1) {
    const lower = narrative.toLowerCase();
    if (needles.some((n) => lower.includes(n.toLowerCase()))) return narrative;
    return "";
  }

  const header = chunks[0];
  const sections = chunks.slice(1);
  const matched = sections.filter((sec) => {
    const lower = sec.toLowerCase();
    return needles.some((n) => lower.includes(n.toLowerCase()));
  });

  if (!matched.length) return header.trim() ? header : "";
  return [header, ...matched].join("");
}
