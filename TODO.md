# Todo

- [ ] Add server-side pagination to the game catalog.
  - Show 20 games per page using a `page` query parameter.
  - Count matching games and fetch the current page with SQL `LIMIT` and `OFFSET`.
  - Preserve search, filters, and sorting in pagination links; reset to page 1 when these change.
  - Show the result range, total count, current page, and Previous/Next controls.
  - Handle invalid page numbers, out-of-range pages, and empty results.
  - Keep the existing Flask templates, full-page navigation, and game card popups.
