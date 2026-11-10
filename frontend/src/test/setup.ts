// Vitest setup: jsdom lacks matchMedia, which the theme code uses.
if (!window.matchMedia) {
  window.matchMedia = (query: string) => ({ matches: false, media: query, onchange: null, addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {}, dispatchEvent: () => false }) as MediaQueryList
}
