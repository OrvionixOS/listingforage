export const PRODUCT_CATEGORIES = [
  "Printable Artwork",
  "Digital Planner",
  "Template",
  "Invitation",
  "SVG File",
  "Cricut File",
  "Font",
  "Branding Kit",
  "Social Media Template",
  "Business Template",
  "Wedding Product",
  "Educational Product",
  "Digital Download",
  "Pattern",
  "Worksheet",
  "Mockup",
  "Design Bundle",
] as const;

export const STYLE_OPTIONS = [
  "Auto-detect",
  "Minimal",
  "Boho",
  "Modern",
  "Vintage",
  "Elegant",
  "Playful",
  "Luxury",
  "Rustic",
  "Watercolor",
  "Scandinavian",
  "Y2K / Trendy",
] as const;

export const IMPROVE_ACTIONS = [
  { key: "regenerate", label: "Regenerate title" },
  { key: "seo", label: "Improve SEO" },
  { key: "conversion", label: "Improve conversion" },
  { key: "premium", label: "Make it more premium" },
  { key: "trendy", label: "Make it more trendy" },
  { key: "gift", label: "Make it more gift-focused" },
  { key: "audience", label: "New target audience" },
  { key: "compete", label: "Re-analyze competitors" },
] as const;

export type ImproveAction = (typeof IMPROVE_ACTIONS)[number]["key"];