# Design reference

The rules behind Kuber's dark finance UI. Read the two SVGs in `reference/`
alongside this — they show the actual layout these rules produce.

## Rules worth keeping

- Colour only ever encodes meaning. Teal is money in, coral is money out, red only
  appears when a budget is breached. Don't use color for anything else (no rainbow
  category palettes beyond what `tokens.json` already defines).
- Two font weights, 400 and 500. Nothing heavier — no bold headings.
- Cents are dimmed rather than dropped, and all currency uses tabular figures so
  columns/digits align vertically.
- Budget bars stop at 100% and change colour (teal/blue → red) instead of overflowing
  the card edge.

## The money-flow (Sankey) pattern specifically

Reference: [`reference/money-flow-reference.svg`](reference/money-flow-reference.svg).

- Reads left to right: income streams → one centre node for cash that's actually
  withdrawable → where it lands.
- One vertical scale drives both sides, so ribbon thickness is directly comparable
  across the whole chart.
- Income ribbons are shades of blue so they read as one family; destination ribbons
  carry the semantic colours (coral spend, teal savings, purple investment, grey
  unallocated remainder).
- The centre bar is the only white element in the whole widget — it's the pinch point,
  so it gets the strongest value.
- The right column always sums to the left column. Anything not assigned becomes the
  unallocated buffer rather than disappearing.

## Budgets/goals pattern

Reference: [`reference/budgets-goals-reference.svg`](reference/budgets-goals-reference.svg).

- One row per budget: category name + icon, a capped progress bar, amount spent vs.
  limit with cents dimmed.
- Savings goals: same bar pattern, but teal throughout (there's no "over" state for a
  goal — it just reaches 100% and stops).

## Tokens

Use [`tokens.json`](tokens.json) (or [`tokens.css`](tokens.css) custom properties) rather
than hand-picking colors — every value a widget needs (surfaces, text, flow/category/source
colors, tint backgrounds, type scale, radius, spacing) is already defined there.

## In-chat widget adaptation

When rendering via `show_widget` (inline in the Claude chat), the widget runs inside the
host's light/dark theme. Use the Ledger dark tokens for **chart elements** (bar fills,
Sankey ribbons, category dots) but let the host CSS variables (`--surface-1`,
`--text-primary`, `--text-secondary`, `--bg-accent`, etc.) handle surfaces and text so
the widget integrates with the chat theme. Keep backgrounds transparent at the top level.
