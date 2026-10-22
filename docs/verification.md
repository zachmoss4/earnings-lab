# Verification

Test environment: Apple Silicon macOS, Python 3.14.4, Node.js 26.8.1, NumPy 2.5.4, pandas 3.0.6, yfinance 1.7.0, React 19.3.1, and Vite 8.3.5. The pinned dependency set requires Python 3.12+.

Sixteen unit tests cover numerical parity against the reference function, interpolation and units, all classification combinations, invalid expirations/quotes/history, event coverage, contract units, optional metadata, currency validation, local persistence, caching, provider failures, input validation, and loopback origin/host checks.

`npm run build` runs TypeScript checking and creates the production interface. Browser verification covers live ticker entry, chart/data views, snapshot reopening, quantity changes, and calculation-note dialogs.

The release includes the prebuilt UI. A clean-folder launch without Node/npm verifies that the launcher can create its Python environment and serve the UI and offline-example API. This is a same-computer packaging check, not cross-platform certification.

Screenshots use the explicitly labeled offline example. Tests verify application behavior and calculations; they do not establish trading performance.
