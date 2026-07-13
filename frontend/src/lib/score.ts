export function scoreColor(v: number): string {
  if (v >= 80) return "oklch(0.72 0.18 150)";
  if (v >= 60) return "oklch(0.78 0.15 85)";
  if (v >= 40) return "oklch(0.75 0.18 55)";
  return "oklch(0.66 0.2 25)";
}

export function scoreLabel(v: number): string {
  if (v >= 80) return "Excellent";
  if (v >= 60) return "Strong";
  if (v >= 40) return "Needs work";
  return "Weak";
}