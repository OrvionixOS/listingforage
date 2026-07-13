// Shared types for the AI listing engine output.

export interface ScoreSet {
  seo: number;
  keywordOpportunity: number;
  competitiveAdvantage: number;
  thumbnail: number;
  visualQuality: number;
  conversion: number;
  brandAlignment: number;
  buyerConfidence: number;
  offerStrength: number;
  overall: number;
}

export interface ListingImage {
  n: number;
  title: string;
  purpose: string;
  psychology: string;
  layout: string;
  copyOverlay: string;
  designDirection: string;
  mockup: string;
  cta: string;
}

export interface ListingResult {
  productAnalysis: {
    summary: string;
    idealBuyer: string;
    buyingMotivation: string;
    emotionalAppeal: string;
    complexity: string;
    useCases: string[];
    niches: string[];
    seasonalOpportunities: string[];
    giftPotential: string;
    premiumPositioning: string;
  };
  marketResearch: {
    overview: string;
    competitorPatterns: string[];
    customerLanguage: string[];
    objections: string[];
  };
  marketGap: {
    competitorsDoWell: string[];
    customersRespondTo: string[];
    competitorWeaknesses: string[];
    differentiation: string[];
    strongerOffer: string;
  };
  beatBestSellers: {
    positioning: string;
    keywordStrategy: string;
    visualStrategy: string;
    valueProps: string[];
    whyChooseThis: string;
  };
  brand: {
    positioningStatement: string;
    idealCustomer: string;
    personality: string[];
    colors: { hex: string; name: string }[];
    typography: string[];
    collectionIdeas: string[];
    expansionIdeas: string[];
    consistencyGuidelines: string[];
  };
  titles: {
    best: string;
    alternatives: string[];
    reasoning: string;
  };
  description: {
    hook: string;
    problem: string;
    transformation: string;
    included: string[];
    features: string[];
    fileDetails: string;
    instructions: string;
    printing: string;
    compatibility: string;
    faq: { q: string; a: string }[];
    trust: string;
    cta: string;
    fullText: string;
  };
  tags: string[];
  keywords: {
    primary: string[];
    secondary: string[];
    longTail: string[];
  };
  attributes: {
    materials: string[];
    colors: string[];
    occasions: string[];
    themes: string[];
    categories: string[];
    styles: string[];
  };
  pricing: {
    recommended: number;
    min: number;
    max: number;
    strategy: string;
  };
  images: ListingImage[];
  scores: ScoreSet;
  recommendations: string[];
}

export interface ProductFile {
  path: string;
  name: string;
  size: number;
  type: string;
  url?: string;
}

export const SCORE_LABELS: { key: keyof ScoreSet; label: string }[] = [
  { key: "seo", label: "SEO Strength" },
  { key: "keywordOpportunity", label: "Keyword Opportunity" },
  { key: "competitiveAdvantage", label: "Competitive Advantage" },
  { key: "thumbnail", label: "Thumbnail Strength" },
  { key: "visualQuality", label: "Visual Quality" },
  { key: "conversion", label: "Conversion Potential" },
  { key: "brandAlignment", label: "Brand Alignment" },
  { key: "buyerConfidence", label: "Buyer Confidence" },
  { key: "offerStrength", label: "Offer Strength" },
  { key: "overall", label: "Overall Sales Potential" },
];