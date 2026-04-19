import "@testing-library/jest-dom";

// jsdom 29 does not implement matchMedia; several components
// (e.g. ThemeProvider) call it during mount, which would throw.
// Polyfill once here so every test inherits a safe default.
if (typeof window !== "undefined" && typeof window.matchMedia !== "function") {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: (query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }),
  });
}
