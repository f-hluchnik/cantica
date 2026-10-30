# Archived design: "M5 minimal" (30. 10. 2026)

The first M5 UI: mobile first, system fonts, thin colour stripe, plain lists with tier symbols,
uppercase part labels. Replaced by the label-based design (review after M5).

- `templates/` — copies of `web/templates/web/*.html` at that time
- `styles.css`, `app.js` — copies of `web/static/web/`
- `preview/` — static renders (CSS inlined) to open in a browser

To restore: copy `templates/*` to `web/templates/web/` and `styles.css` / `app.js` to `web/static/web/css|js/`.
The engine and views did not change with the redesign, so the templates fit as they are.
