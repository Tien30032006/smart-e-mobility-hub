# UI / UX & Internationalization Guidelines

The frontend is plain HTML/CSS/JS (no build step). It ships with a small design system and
a bilingual (**English / Vietnamese**) layer shared by every page. Follow these rules so all
screens look and behave consistently.

## 1. Bilingual UI (EN / VI)

* The language switcher (EN | VI) is in the top navigation. The choice is stored in `localStorage`
  (`hub_lang`); the first visit follows the browser language (Vietnamese browsers get VI, everything else EN).
* All strings live in **`src/shared/i18n.js`**, in two dictionaries (`en`, `vi`). Add every new key to **both**.
* Never hard-code visible text in HTML or JS.

```html
<h1 data-i18n="page.findHub.title"></h1>                       <!-- text -->
<input data-i18n-attr="placeholder:common.search,aria-label:common.search">   <!-- attributes -->
```
```js
Hub.t('hub.spaces')                      // JS string
Hub.t('trip.minutes', { n: 15 })         // "{n}" placeholders
I18n.hubName(hub)                        // localized Hub name (by hub_id, falls back to API name)
```
* Build dynamic DOM **inside the `draw` callback** of `Hub.render(el, promise, draw)`. The framework
  re-runs `draw` automatically on a language change, so your page updates without a reload.
* Key naming: `page.<page>.<thing>`, `common.*`, `menu.*`, `hub.*`, `role.*`, `<module>.*` (e.g. `charging.queue`).
* Data that comes from the database/JSON (vehicle models, user names) is **not** translated.
  Backend error messages (`detail`) are English; show them as-is or map known codes to i18n keys.
* Format dates/numbers with `toLocaleString(I18n.lang)`.

## 2. Design system (`assets/css/style.css`)

* Use the semantic tokens (`--brand`, `--surface`, `--ink`, `--muted`, `--line`, `--warn-soft`, `--danger-soft`…).
  **No raw hex colors in pages.** Tokens switch automatically for dark mode (`html[data-theme="dark"]`).
* Ready-made components: `.card` (`.lift` for hover), `.grid`, `.badge` (`.warn`, `.bad`), `.bar` (progress, add `.hot`),
  `.chip`, `.todo`, `.error`, `.skeleton`, `button` / `button.secondary`, `.icon-btn`, `.seg` (segmented control), `table`.
* Icons: `Hub.icon('bike' | 'plug' | 'parking' | 'shield' | 'alert' | …)` returns an inline SVG. **Do not use emoji as icons.**
  Add new icons to the `ICONS` map in `main.js`.

## 3. UX checklist (apply to every page you build)

| Area | Rule |
|---|---|
| Accessibility | Text contrast >= 4.5:1; every input has a visible `<label>`; icon-only buttons have `aria-label`; keep the focus ring; use `role="alert"` for errors |
| Touch | Targets >= 44x44 px, >= 8 px apart |
| Feedback | Show the skeleton while loading (`Hub.render` does it); disable a button while its request runs; show errors next to the field |
| Status | Never rely on color alone: pair colors with text/icon (e.g. "Nearly full" badge, not just a red bar) |
| Layout | Mobile-first; no horizontal scroll at 375 px; wide tables go inside `overflow-x:auto` |
| Motion | 150-300 ms, transform/opacity only; honors `prefers-reduced-motion` automatically |
| Both themes | Check every new screen in light **and** dark mode, in EN **and** VI (Vietnamese strings are often longer) |

## 4. Page skeleton

```html
<head> ... <script src="/shared/i18n.js"></script> <link rel="stylesheet" href="/app/assets/css/style.css"> </head>
<body data-role="student">
  <nav id="nav"></nav>
  <main>
    <header class="page-head"><h1 data-i18n="page.xxx.title"></h1></header>
    <div id="app" class="card"></div>
  </main>
  <script src="/shared/api-client.js"></script>
  <script src="/app/assets/js/main.js"></script>
  <script> Hub.init(); Hub.render(document.getElementById('app'), API.get('/api/...'), data => { /* build DOM */ }); </script>
</body>
```
