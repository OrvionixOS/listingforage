// Digital product taxonomy: 13 groups, each with its subcategories.
// Selected values are stored as "Group / Subcategory".
export const CATEGORY_GROUPS = [
  {
    label: "Art & Collectibles",
    items: ["Digital wall art", "Printable art", "Digital illustrations", "Digital paintings", "Photography prints"],
  },
  {
    label: "Craft Supplies & Tools",
    items: ["Digital papers", "Scrapbook papers", "SVG files", "Cricut files", "Sewing patterns", "Embroidery patterns", "Laser cut files", "Craft templates"],
  },
  {
    label: "Paper & Party Supplies",
    items: ["Invitations", "Party printables", "Wedding templates", "Cards", "Labels", "Signs", "Printable decorations"],
  },
  {
    label: "Templates & Design Resources",
    items: ["Canva templates", "Resume templates", "Social media templates", "Business templates", "Branding kits", "Presentation templates"],
  },
  {
    label: "Planners & Organization",
    items: ["Digital planners", "Printable planners", "Calendars", "Trackers", "Checklists", "Notion templates"],
  },
  {
    label: "Journals, Books & Educational",
    items: ["Ebooks", "Workbooks", "Guided journals", "Coloring books", "Worksheets", "Learning resources"],
  },
  {
    label: "Graphics & Digital Assets",
    items: ["Clip art", "Digital stickers", "Backgrounds", "Textures", "Patterns", "Fonts", "Brushes", "Icons"],
  },
  {
    label: "Photography & Creative Tools",
    items: ["Lightroom presets", "Photoshop actions", "Photo overlays", "Mockups", "Editing resources"],
  },
  {
    label: "Business & Professional Resources",
    items: ["Client forms", "Contracts", "Spreadsheets", "Calculators", "SOP templates", "Marketing materials"],
  },
  {
    label: "AI & Digital Tools",
    items: ["AI prompt packs", "AI workflow templates", "ChatGPT resources", "Midjourney resources", "Automation templates"],
  },
  {
    label: "Wellness & Spirituality",
    items: ["Manifestation journals", "Tarot resources", "Astrology resources", "Meditation guides", "Affirmation cards", "Spiritual workbooks"],
  },
  {
    label: "3D & Technical Files",
    items: ["3D models", "STL files", "CAD files", "Digital manufacturing files"],
  },
  {
    label: "Audio & Video Assets",
    items: ["Music files", "Sound effects", "Video templates", "Motion graphics", "LUTs"],
  },
] as const;

export const PRODUCT_CATEGORIES: string[] = CATEGORY_GROUPS.flatMap((g) =>
  g.items.map((i) => `${g.label} / ${i}`),
);

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
