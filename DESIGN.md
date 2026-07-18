---
version: alpha
name: Paper-Wiki-design
description: Paper-Wiki is a personal research-paper triage and reading tool — recommend → search/add → skim → review workflow over long-form arXiv summaries (math, code, tables, figures). The design borrows WIRED's editorial discipline (bit.ly/awesome-design-md → design-md/wired) for its color/typography split — warm-paper canvas, serif for anything that IS the paper's content, sans for anything that IS the tool's chrome, hairline elevation, one chromatic accent — but deliberately departs from WIRED on corner geometry: every surface uses a soft rounded radius (never `0px`), chosen for a friendlier, more approachable feel than the original square-corner pass. Coverage spans the app shell (left `SideNav` rail, center content, right `GenerationTray` rail) and its views: 首页 (Home — merges 今日推荐 recommendations + 检索/添加 search into one page with a shared staging tray), 全部论文 (Dashboard + Paper Detail), 待审查 (Review queue, a filtered 全部论文).

colors:
  ink: "#1c1712"
  ink-soft: "#3a3226"
  body: "#6f6656"
  muted: "#9c9484"
  canvas: "#fffefb"
  fog: "#f2efe6"
  line: "#ddd5c2"
  line-strong: "#c4b9a1"
  moss: "#44624a"
  moss-deep: "#324a37"
  moss-soft: "#e3ebe0"
  copper: "#a65f35"
  copper-soft: "#f3e6da"
  error: "#b3261e"
  error-soft: "#fbeae7"
  error-line: "#e7c4bc"
  code-ink: "#201a12"
  on-primary: "#fffefb"

typography:
  font-serif: "'Source Serif 4', Georgia, 'Times New Roman', serif"
  font-sans: "Inter, ui-sans-serif, system-ui, -apple-system, 'Segoe UI', sans-serif"
  font-mono: "ui-monospace, 'JetBrains Mono', 'SFMono-Regular', Menlo, monospace"
  page-title:
    fontFamily: "{typography.font-serif}"
    fontSize: 22px
    fontWeight: 600
    lineHeight: 1.3
  markdown-h1:
    fontFamily: "{typography.font-serif}"
    fontSize: 30px
    fontWeight: 600
    lineHeight: 1.25
  markdown-h2:
    fontFamily: "{typography.font-serif}"
    fontSize: 21px
    fontWeight: 600
    lineHeight: 1.3
  markdown-h3:
    fontFamily: "{typography.font-serif}"
    fontSize: 18px
    fontWeight: 600
    lineHeight: 1.35
  card-title:
    fontFamily: "{typography.font-serif}"
    fontSize: 15px
    fontWeight: 600
    lineHeight: 1.4
  detail-title:
    fontFamily: "{typography.font-serif}"
    fontSize: 26px
    fontWeight: 600
    lineHeight: 1.3
  body-serif:
    fontFamily: "{typography.font-serif}"
    fontSize: 15.5px
    fontWeight: 400
    lineHeight: 1.75
  body-sans:
    fontFamily: "{typography.font-sans}"
    fontSize: 14px
    fontWeight: 400
    lineHeight: 1.5
  byline:
    fontFamily: "{typography.font-sans}"
    fontSize: 12.5px
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: 0.1px
  caption:
    fontFamily: "{typography.font-sans}"
    fontSize: 12px
    fontWeight: 500
    lineHeight: 1.4
  button:
    fontFamily: "{typography.font-sans}"
    fontSize: 14px
    fontWeight: 500
    lineHeight: 1.2
  mono:
    fontFamily: "{typography.font-mono}"
    fontSize: 13.5px
    fontWeight: 400
    lineHeight: 1.6

rounded:
  none: 0px
  md: 6px
  lg: 8px
  xl: 12px
  full: 9999px

spacing:
  xs: 4px
  sm: 8px
  md: 12px
  lg: 16px
  xl: 20px
  2xl: 24px
  3xl: 32px
  4xl: 48px

components:
  page-header:
    backgroundColor: "{colors.canvas}"
    borderColor: "{colors.line}"
    typography: "{typography.page-title}"
  nav-button:
    textColor: "{colors.body}"
    activeBorder: "{colors.line}"
    activeBackground: "{colors.fog}"
    typography: "{typography.body-sans}"
  action-button:
    backgroundColor: "{colors.canvas}"
    borderColor: "{colors.line}"
    hoverBorder: "{colors.moss}"
    typography: "{typography.button}"
    rounded: "{rounded.lg}"
  button-primary:
    backgroundColor: "{colors.moss}"
    textColor: "{colors.canvas}"
    hoverBackground: "{colors.moss-deep}"
    typography: "{typography.button}"
    rounded: "{rounded.lg}"
  paper-card:
    backgroundColor: "{colors.canvas}"
    borderColor: "{colors.line}"
    activeBorder: "{colors.moss}"
    titleTypography: "{typography.card-title}"
    metaTypography: "{typography.byline}"
    bodyTypography: "{typography.body-sans}"
    rounded: "{rounded.xl}"
  badge:
    backgroundColor: "{colors.fog}"
    borderColor: "{colors.line}"
    typography: "{typography.caption}"
  badge-pattern:
    backgroundColor: "{colors.copper-soft}"
    textColor: "{colors.copper}"
    borderColor: "{colors.copper}"
  side-panel:
    backgroundColor: "{colors.canvas}"
    borderColor: "{colors.line}"
    titleTypography: "{typography.caption}"
    rounded: "{rounded.xl}"
  editor:
    backgroundColor: "{colors.canvas}"
    borderColor: "{colors.line}"
    focusBorder: "{colors.moss}"
    typography: "{typography.mono}"
    rounded: "{rounded.lg}"
  markdown-body:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    h1: "{typography.markdown-h1}"
    h2: "{typography.markdown-h2}"
    h3: "{typography.markdown-h3}"
    body: "{typography.body-serif}"
    linkColor: "{colors.moss}"
    blockquoteBorder: "{colors.moss}"
    blockquoteBackground: "{colors.fog}"
    codeBackground: "{colors.code-ink}"
    rounded: "{rounded.xl}"
  side-nav:
    backgroundColor: "{colors.fog}"
    borderColor: "{colors.line}"
    activeIndicator: "{colors.moss}"
    itemRounded: "{rounded.lg}"
  generation-tray:
    backgroundColor: "{colors.fog}"
    borderColor: "{colors.line}"
    itemBackground: "{colors.canvas}"
    itemRounded: "{rounded.lg}"
  review-badge:
    reviewedColor: "{colors.moss}"
    pendingColor: "{colors.muted}"
    typography: "{typography.byline}"
  toast-band:
    backgroundColor: "{colors.canvas}"
    borderColor: "{colors.line}"
    elevation: "shadow-lg (only floating/sticky surfaces)"

---

## Overview

Paper-Wiki is a working tool, not a marketing site — a researcher opens it to triage new arXiv drops, skim a generated summary, and review/correct the structured metadata (pattern, prior works) before it enters their library. That's a fundamentally different job than WIRED's, but the same editorial instinct applies almost unchanged: **the paper is the story, the app is the newsroom around it.** Everything that is the paper's own content — titles, headings, abstracts, prose, blockquoted findings — is set in a serif built for sustained reading. Everything that is the tool's own chrome — nav, filters, buttons, badges, metadata rows, tables — stays in a small, quiet sans. There is no gradient, no illustration, no soft drop shadow; hairline borders on a warm paper-toned canvas carry all the structure.

The app kept WIRED's color/type discipline — hairline borders instead of shadows, a single green accent (`moss`) — but the first pass's square corners read as cold and "boxed-in" once the app grew a left nav rail and a right staging rail. This revision keeps the serif/sans split and warm palette, and softens the geometry: every surface (buttons, inputs, cards, panels) now carries a rounded radius sized to its role, instead of `{rounded.none}` everywhere.

**Key characteristics:**
- Warm paper canvas (`{colors.canvas}` / `{colors.fog}`) — never stark white, never cool gray.
- **Chrome vs. content by surface tone**: the app shell's structural rails (`SideNav`, `GenerationTray`) sit on `{colors.fog}` — the same tone as the page background — so they read as recessed chrome. Actual content (cards, panels, the search bar) sits on `{colors.canvas}`, which pops against the fog. Never give a nav rail the same surface color as a content card; that's what made earlier passes feel like "a box stuck on the side."
- Two-face typographic split: `Source Serif 4` for paper titles, markdown headings, and long-form body copy; `Inter` for every piece of app chrome (nav, buttons, badges, forms, tables, metadata lines).
- One chromatic accent, `{colors.moss}` — links, active states, "reviewed"/"done" signals, and the fill color for primary actions (`.button-primary`). `{colors.copper}` is a second, deliberately narrow accent reserved for pattern-classification tags and "why recommended" annotations only.
- Rounded geometry on every surface, sized by role (see Shapes) — `{rounded.lg}` for buttons/inputs/list rows, `{rounded.xl}` for cards/panels/the search bar, `{rounded.full}` only for circular icon affordances.
- Flat elevation: hairline borders (`{colors.line}`) do the work everywhere except floating/sticky overlays (the image lightbox), which may use a soft shadow because they visually detach from the page.
- Selection/active state is a border-weight and border-color change (2px `{colors.moss}`), never a drop shadow on the card itself.
- Primary vs. secondary buttons: a page's *one* highest-emphasis action (search submit, batch-generate) uses `.button-primary` (solid `{colors.moss}` fill, `{colors.canvas}` text) so it doesn't read as "just another bordered button" next to everything else. Every other action stays the outlined `.action-button`.

## Colors

### Canvas & Surface
- **Canvas** (`{colors.canvas}` — `#fffefb`): card and panel surfaces. Warm off-white, not pure `#ffffff` — avoids the cold, sterile look of a generic dev-tool white.
- **Fog** (`{colors.fog}` — `#f2efe6`): the page background wash behind panels, and tinted surfaces (badge fill, blockquote fill, active nav-button fill). A warm parchment tone.
- **Line** (`{colors.line}` — `#ddd5c2`): the default 1px hairline — panel borders, card borders, table cell borders, input borders.
- **Line Strong** (`{colors.line-strong}` — `#c4b9a1`): reserved for dividers that need more separation than the default hairline (e.g. a section break inside a long summary).

### Text
- **Ink** (`{colors.ink}` — `#1c1712`): headings and primary body text. Warm near-black, not the cool `#172026` the app used before.
- **Ink Soft** (`{colors.ink-soft}` — `#3a3226`): de-emphasized headings (e.g. empty-state titles).
- **Body** (`{colors.body}` — `#6f6656`): secondary text — authors/venue/byline rows, abstract previews, helper copy. Replaces ad-hoc `slate-500`/`slate-600`.
- **Muted** (`{colors.muted}` — `#9c9484`): tertiary/disabled text — placeholders, "no data yet" states, unreviewed status icons. Replaces ad-hoc `slate-400`.

### Accent
- **Moss** (`{colors.moss}` — `#44624a`, unchanged from the current brand): the app's only interactive accent. Links inside markdown, active nav/segmented-control state, active card border, focus rings, "reviewed"/"succeeded" signals, checkbox accent.
- **Moss Deep** (`{colors.moss-deep}` — `#324a37`): hover/pressed state for moss-accented interactive elements.
- **Moss Soft** (`{colors.moss-soft}` — `#e3ebe0`): rare tint fill, e.g. a "succeeded" row background.
- **Copper** (`{colors.copper}` — `#a65f35`, unchanged): the second, deliberately narrow accent. Used **only** for: the SCI-pattern badge/tag, the "why recommended" reason line on a candidate card, and the degraded-mode warning icon. Never used for primary actions or navigation.
- **Copper Soft** (`{colors.copper-soft}` — `#f3e6da`): tint fill behind the pattern badge.

### Semantic
- **Error** (`{colors.error}` — `#b3261e`) / **Error Soft** (`{colors.error-soft}` — `#fbeae7`) / **Error Line** (`{colors.error-line}` — `#e7c4bc`): formalizes the ad-hoc `red-600`/`red-50`/`red-200` currently sprinkled across error banners and the failed-candidate card state.
- **Code Ink** (`{colors.code-ink}` — `#201a12`): the dark background for fenced code blocks inside markdown — warmed to match the ink hue instead of a cold near-black.

## Typography

### Font Family
Two faces carry the entire system, exactly mirroring WIRED's "serif for narrative, sans for structure" rule:

1. **Source Serif 4** (`{typography.font-serif}`) — every piece of *paper content*: paper titles on cards and in the detail view, markdown h1/h2/h3, markdown body paragraphs and blockquotes, prior-work titles. This is the one addition that gives the app an academic-reading identity instead of a generic dashboard identity. Falls back to Georgia / Times New Roman.
2. **Inter** (`{typography.font-sans}`, unchanged) — every piece of *app chrome*: nav, buttons, segmented controls, badges, form inputs, table headers/cells, panel titles, byline/metadata rows, status text. Never used for a paper's own title or body.

`{typography.font-mono}` (unchanged mono stack) stays reserved for the raw-markdown editor textarea and rendered code blocks.

### Hierarchy

| Token | Size | Weight | Face | Use |
|---|---|---|---|---|
| `{typography.detail-title}` | 26px | 600 | serif | Paper Detail view's `<h1>` (the open paper's title). |
| `{typography.markdown-h1}` | 30px | 600 | serif | `##`-equivalent top heading inside a rendered summary. |
| `{typography.page-title}` | 22px | 600 | serif | Section headers: "My Papers", "今日推荐", "检索 / 添加论文". Previously sans — this is the visible brand signature at the top of every view. |
| `{typography.markdown-h2}` | 21px | 600 | serif | Second-level markdown heading. |
| `{typography.markdown-h3}` | 18px | 600 | serif | Third-level markdown heading. |
| `{typography.card-title}` | 15px | 600 | serif | Paper-card / candidate-card / prior-card title — these ARE paper titles, so they take the serif, matching WIRED's story-card headline treatment. |
| `{typography.body-serif}` | 15.5px | 400 | serif | Markdown body paragraphs, blockquotes, abstract preview text on a paper card. Line-height 1.75 for sustained reading. |
| `{typography.body-sans}` | 14px | 400 | sans | Default UI body: filters, helper text, table cells, form labels. |
| `{typography.byline}` | 12.5px | 400 | sans | Authors · venue · year line under a serif title — the app's "byline row," identical in spirit to WIRED's article byline. |
| `{typography.caption}` | 12px | 500 | sans | Badges, panel-title eyebrows (`PATTERN`, `PRIOR WORKS`, `PUBLISH`), status labels. |
| `{typography.button}` | 14px | 500 | sans | All button and segmented-control labels. |
| `{typography.mono}` | 13.5px | 400 | mono | Editor textarea, rendered `<code>`/`<pre>`. |

### Principles
- **Serif for the paper, sans for the tool.** If the text came from (or describes) the paper's own content — title, heading, abstract, prose, blockquote — it's serif. If it's the app talking to the user — a button, a filter, a status pill, a table header — it's sans. Never mix these roles.
- **Byline rhythm.** The authors/venue/year line always sits directly under a serif title, in `{typography.byline}`, colored `{colors.body}` — this pairing (serif headline + small sans byline) is the single most-repeated pattern in the app (paper cards, candidate cards, the detail header) and is exactly what should read as "the brand."
- **No display weight above 600.** Keep serif headings at 600, not 700+ — bold serif at small UI sizes gets heavy and clashes with the sans chrome around it.

### Font Loading Note
`Source Serif 4` is a free variable Google Font (weights 400/600 are sufficient) — self-host or load via a `<link>`/`@font-face` in `index.html`; do not depend on Google's CDN if the app must work offline. No proprietary-font substitution problem exists here (unlike WIRED's `WiredDisplay`/`BreveText`).

## Layout

The app shell is a three-region flex row on desktop (`≥lg`): a fixed-width left `SideNav` rail (nav icons only below `lg`, icon+label at `lg` and up), a flexible center column, and a fixed-width right `GenerationTray` rail (hidden below `lg`). The center column holds either the 首页 (Home) view — a search bar pinned to the top followed by the 检索结果/今日推荐 card feeds — or the 全部论文 view, which keeps its own resizable two-pane workbench (paper list ⟷ paper detail) above `lg`, stacking to a single column below it. `GenerationTray` and its underlying state (`useBatchGeneration`) live at the app-shell level, not inside either view, so staged papers and generation progress persist when switching between 首页 and 全部论文. Tailwind's default 4px spacing scale is unchanged.

## Elevation & Depth

| Level | Treatment | Use |
|---|---|---|
| Level 0 — Flat | No shadow, no border. | Page background (`{colors.fog}`). |
| Level 1 — Hairline | 1px solid `{colors.line}`. | Default state for every card, panel, input, table cell — almost everything. |
| Level 2 — Accent Border | 2px solid `{colors.moss}`. | Selected/active card (`paper-card-active`, `candidate-card-selected`) — **replaces the current `shadow-sm`**. Selection is communicated by color+weight, never elevation. |
| Level 3 — Floating Shadow | `{colors.line}` hairline + soft drop shadow. | The only exception: overlays that visually detach from page flow — the sticky batch-action bar, the image lightbox backdrop. These already float above content, so a shadow is honest, not decorative. |

## Shapes

| Token | Value | Use |
|---|---|---|
| `{rounded.md}` | 6px | Small chips: `.badge`, `.badge-pattern`, `.role-badge`, inline `<code>`. |
| `{rounded.lg}` | 8px | Buttons (`.action-button`, `.button-primary`, `.icon-button`), form inputs/selects, `.editor`, `.segmented-control` (with `overflow-hidden` so child buttons clip to the rounded bounds), `.side-nav-button`, `GenerationTray` list rows, `.prior-card`, fenced code blocks, markdown images. |
| `{rounded.xl}` | 12px | Larger surfaces: `.paper-card`, `.candidate-card`, `.side-panel`, `.markdown-body`/`.markdown-empty`, the home-page search bar container. |
| `{rounded.full}` | 9999px | Circular icon-only affordances only (none currently in use, but reserved for one). |
| `{rounded.none}` | 0px | No longer used anywhere in the live UI — kept in the token table only so a stray future component doesn't reintroduce it by omission. |

Pick radius by the element's role, not by habit: small inline chip → `md`; anything clickable at normal control height → `lg`; a card/panel/container that holds other content → `xl`. Don't mix an `xl` radius onto a small badge or a `md` radius onto a full card — the scale only reads as a system if it's applied consistently by size class.

## Components

Mapped to the existing Tailwind component classes in `web/frontend/src/styles.css` — this is a token/value update, not a restructuring:

- **`SideNav`** — the left rail. Surface `{colors.fog}` (not canvas — see "chrome vs. content" above), `{rounded.lg}` on each nav row, current-view indicated by a 3px `{colors.moss}` left accent bar + `{colors.canvas}` background on that row, never a border. Collapses to icon-only below `lg`; keep `title=` tooltips on the icon buttons when labels are hidden.
- **`GenerationTray`** — the right rail. Surface `{colors.fog}`, header uses the same `.panel-title` treatment as `PaperDetail`'s aside panels (so it reads as "one more side panel," not a bolted-on widget). Staged items render as `{colors.canvas}` rows at `{rounded.lg}` inside the fog rail — the tone contrast is what makes them read as cards. Never render this as a bottom-fixed drawer; it's a persistent rail mounted at the app-shell level regardless of `{view}`, so staged/generating state survives navigation.
- **`.icon-button` / `.action-button`** — `{rounded.lg}`, hairline border, hover→moss border/text. **`.button-primary`** — same `{rounded.lg}`, solid `{colors.moss}` fill + `{colors.canvas}` text, hover `{colors.moss-deep}`; reserve for the one primary action per context (search submit, batch-generate).
- **`.paper-card` / `.candidate-card`** — surface `{colors.canvas}`, border `{colors.line}`, `{rounded.xl}`; title (`h2`/`h3` inside) moves to `{typography.card-title}` (serif); author/venue line moves to `{typography.byline}`; abstract preview moves to `{typography.body-serif}` at a slightly smaller size (14–15px) so it still reads as "reading," not "UI copy." Active/selected state: no shadow, a 2px `{colors.moss}` border instead.
- **`.badge`** — fill `{colors.fog}`, text `{colors.body}`, `{typography.caption}`, `{rounded.md}`. **`.badge-pattern`** — fill `{colors.copper-soft}`, text/border `{colors.copper}` — the pattern tag stays the one place copper appears prominently.
- **`.side-panel` / `.panel-title`** — `{rounded.xl}` on the panel; panel-title eyebrows (`Pattern`, `Prior Works`, `Publish`) stay sans/uppercase/`{colors.body}`.
- **`.editor`** — `{rounded.lg}`, mono, hairline border, moss focus ring.
- **The home search bar** — a single `{rounded.xl}` bordered container housing icon + input + `.button-primary` submit, not three separately-bordered fields in a row (that reads as an unstyled form, not a search product). Secondary filters (year range, "add by arXiv ID" toggle) sit in a smaller, de-emphasized row below the bar, not crammed inline with it.
- **Native `<select>`** — never the bare browser default. Wrap in a `relative` container, `appearance-none` on the `<select>`, and an absolutely-positioned `ChevronDown` icon on the right (see `Dashboard`'s reviewed-filter for the reference implementation) — same `{rounded.lg}`/border/focus treatment as every other input.
- **`.markdown-body`** — `{rounded.xl}`. `h1`/`h2`/`h3` → `{typography.markdown-h1/h2/h3}` (serif, 600). `p`/`li` → `{typography.body-serif}`. `blockquote` keeps the moss left-rule + `{colors.fog}` fill, text in serif italic-capable body. `code`/`pre` stay mono at `{rounded.md}`/`{rounded.lg}`; `pre` background is `{colors.code-ink}`. `a` stays `{colors.moss}` underline — the one inline link color, exactly WIRED's link-blue role.
- **`ReviewBadge`** — unchanged logic; reviewed state `{colors.moss}`, pending state `{colors.muted}` (not `slate-400`).
- **`PriorWorksView` (`.prior-card`, `.role-badge`, `.prior-meta`, `.prior-relationship`, `.prior-synthesis`)** — prior-work titles move to serif (`{typography.card-title}` scale, slightly smaller e.g. 14px), everything else (role badge, meta line, relationship sentence) stays sans/`body-sans`; `.prior-card` at `{rounded.lg}`.
- **Image lightbox** — the one place a soft shadow is allowed (Level 3 elevation above); the zoomed image itself keeps `{rounded.lg}`.

## Do's and Don'ts

### Do
- Set every paper title, markdown heading, and long-form paragraph in `{typography.font-serif}`. This is the app's one big differentiator — protect it.
- Round every surface by the Shapes scale (`md`/`lg`/`xl` by role) — don't add a new button, input, card, or panel at `{rounded.none}`.
- Give structural chrome (`SideNav`, `GenerationTray`) the `{colors.fog}` surface, not `{colors.canvas}` — that tone difference is what stops a rail from looking like a stuck-on box.
- Communicate "selected"/"active" with a 2px `{colors.moss}` border, never a shadow, on cards.
- Use `.button-primary` for exactly one action per view/context (the thing you most want the user to click); everything else stays `.action-button`.
- Keep `{colors.copper}` narrow — pattern tags and "why recommended" annotations only. If you reach for copper anywhere else, use moss instead.
- Warm every neutral: canvas, fog, line, ink, body, muted are all warm-toned, not cool gray/slate. Don't reintroduce Tailwind's default `slate-*` grays.
- Pair a serif title with a sans byline line directly beneath it — this rhythm should repeat everywhere a paper is named (list card, candidate card, detail header).
- Style native form controls (`<select>`, spin-buttons) explicitly — never ship a bare browser-default control.

### Don't
- Don't set nav labels, button text, badges, table headers, or form inputs in the serif face — chrome is sans, always.
- Don't let markdown body copy fall back to the sans face — it must stay serif for reading comfort.
- Don't add a third chromatic accent. Moss (primary) and copper (narrow/tag) are the only two.
- Don't add drop shadows to any card or panel in normal document flow; reserve shadow for the lightbox only.
- Don't put a nav rail or a side panel on the same surface tone (`{colors.canvas}`) as the content it frames — that flattens the visual hierarchy and is exactly what made earlier passes feel disjointed.
- Don't turn every button into `.button-primary` — a screen with three green buttons has no hierarchy, which defeats the point.
- Don't mix radius sizes off-scale (no `xl` badges, no `md` cards) — consistency is what makes rounding read as a system.
