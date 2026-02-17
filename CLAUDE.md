# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Lexora Console is a lightweight single-page application built with vanilla JavaScript (ES6 modules), Tailwind CSS (CDN), and no build tooling. It serves as a dashboard with pluggable modules.

## Development

**Start the dev server:**
```
./run.sh
# or directly: python3 -m http.server 9009
```
Serves static files at `http://localhost:9009`. No build step required.

**External services** (must be running separately):
- Lexora Feed service: `http://localhost:9001`
- Lexora Mind service: `http://localhost:9002`

There are no tests, linting, or build tools configured.

## Architecture

**Module system:** The app dynamically loads modules defined in the `MODULES` array in `index.html`. Each module is an ES6 file in `modules/` that exports an `init(container, apiBase)` function. The container is a DOM element to render into; apiBase is the module's backend URL.

**Current modules:**
- `modules/feed.js` — Lexora Feed: RSS feed reader. Fetches from `GET {apiBase}/rss?range=...`, filters by date range and feed name. State is component-scoped (closure variables).
- `modules/mind.js` — Lexora Mind: Knowledge base chat. Posts questions to `POST {apiBase}/api/v1/query`, displays answers with source links. Maintains message history in memory.

**Navigation:** Sidebar buttons switch between modules. No URL routing or history API — active module is tracked in a local variable in `index.html`.

**Styling:** Tailwind CSS via CDN plus `styles/app.css` for custom styles. HTMX is loaded but currently unused.
