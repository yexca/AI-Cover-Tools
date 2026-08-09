# AI Cover Tools Design System

This file is the design contract for the PySide6 desktop application and the browser WebUI. It describes the current product language and the rules agents must follow when changing user-facing layout, styling, interaction, or copy.

Implementation sources remain authoritative for resolved values:

| Surface | Primary implementation sources |
| --- | --- |
| Desktop theme | `app/gui/style.py`, `app/gui/appearance.py`, `app/gui/widgets/` |
| Desktop page composition | `app/gui/views/`, `app/gui/main_window.py` |
| WebUI theme and layout | `app/web/static/styles.css`, `app/web/static/index.html` |
| WebUI interaction | `app/web/static/app.js` |
| Desktop translations | `app/gui/i18n/translations.py` |
| WebUI translations | `app/web/static/i18n/` |

If implementation and this document diverge, do not create a third pattern. Decide which behavior is intentional and update the contract and implementation together.

## 1. Product Experience

AI Cover Tools is a local audio-production utility. The interface should feel like a focused workstation: calm at rest, clear under load, and trustworthy around long-running or destructive operations.

Core principles:

- **Audio first:** controls and chrome support the workflow; source paths, model names, node connections, progress, and results remain easy to scan.
- **Local and trustworthy:** distinguish local scans from network synchronization and make file destinations explicit before work starts.
- **Truthful state:** show queued, running, cancelling, completed, failed, and unavailable states accurately. Color never substitutes for state text where the distinction matters.
- **Progressive detail:** expose common actions first and keep model metadata or advanced parameters available without dominating the primary flow.
- **Calm density:** prefer compact, aligned controls and restrained surfaces over decorative panels, oversized headings, or excessive animation.
- **Consistency before novelty:** reuse an existing control, spacing rhythm, semantic color, and interaction pattern before inventing a new one.
- **International by construction:** English, Simplified Chinese, and Japanese are first-class layouts, not follow-up translations.

The two frontends intentionally have related but distinct visual identities:

- The desktop GUI uses a dark, wallpaper-backed glass treatment with a blue action accent.
- The WebUI uses a dark, opaque workstation layout with a purple graph/action accent and node-type colors.

Share hierarchy and semantics between them, not literal styling. Do not paste desktop translucency into the WebUI or WebUI node styling into Qt without an explicit redesign.

## 2. Shared Semantic Rules

### Action Hierarchy

Every view should make these levels visually distinct:

1. **Primary action:** the single action that advances the current workflow, such as Run or Save when saving is the page goal.
2. **Secondary action:** browse, refresh, add, export, or other supporting actions.
3. **Quiet action:** icon controls, collapse/expand, navigation, or row-level utilities.
4. **Destructive/cancelling action:** stop, delete, reset, or cancellation that may discard work.

Do not place multiple equally emphasized primary buttons in one local action group. A destructive color is reserved for destructive or failure-adjacent actions, never decoration.

### Feedback Semantics

| Meaning | Required treatment |
| --- | --- |
| Selected/current | Accent border or surface plus a structural indicator |
| Running/queued | Accent state, progress where measurable, and text/status ownership |
| Success | Green semantic feedback and a terminal success message |
| Warning/confirmation needed | Amber/orange semantic feedback with an explanation or next step |
| Error/invalid | Red semantic feedback located near the affected control, node, or connection |
| Disabled/unavailable | Reduced emphasis and disabled interaction; explain why when it is not obvious |
| Cancelled | A terminal cancelled state, not success and not an endless running state |

Do not rely on hue alone. Use text, icons, borders, shape, or placement so state remains understandable with reduced color perception.

### Depth and Surfaces

- Separate persistent zones with surface color and borders.
- Use shadows for floating overlays, menus, dialogs, selected graph nodes, or active feedback—not as decoration on every static card.
- Keep borders subtle at rest and stronger for focus, selection, validation, or active resizing.
- Blur belongs to the desktop wallpaper treatment and WebUI modal scrim. It is not a universal card effect.
- Maintain sufficient dark tint behind desktop text when a user chooses a bright background image.

### Shape

- Small controls use approximately 5–7 px radii.
- Desktop shell panels and cards use 8 px radii.
- WebUI nodes, menus, dialogs, and toasts use approximately 7–9 px radii.
- Pills are reserved for compact statuses, connection hints, and count-like metadata.
- Circular shapes are reserved for ports, status dots, badges, and truly circular icon controls.

## 3. Desktop GUI

### Visual Theme

The desktop GUI is a dark glass workspace over an optional background image. The tint and translucent panels must keep the application readable without hiding the image completely.

Default appearance roles:

| Role | Current value or range | Use |
| --- | --- | --- |
| Base text | `#f7f9fc` | Primary labels and content; user-adjustable through appearance preview |
| Wallpaper tint | `#04070c`, alpha `155/255` | Default contrast layer over the background image |
| Shell glass | `rgba(10, 14, 22, 0.38–0.44)` | Title bar, navigation, and content shell |
| Card glass | `rgba(10, 14, 22, 0.36)` | Functional page sections |
| Quiet fill | `rgba(255, 255, 255, 0.032–0.055)` | Inputs, steps, and subtle control surfaces |
| Standard border | `rgba(255, 255, 255, 0.15–0.18)` | Cards, panels, and controls |
| Focus border | `rgba(255, 255, 255, 0.34)` | Keyboard/input focus |
| Muted text | white at approximately `55–78%` | Descriptions, status details, unavailable steps |
| Primary accent | `rgba(74, 132, 255, 0.34)` | Primary buttons and selected segmented controls |
| Primary hover | `rgba(74, 132, 255, 0.62)` | Hover on primary actions |
| Danger | `rgba(210, 65, 82, 0.30)` | Stop/destructive controls |
| Danger hover | `rgba(210, 65, 82, 0.62)` | Hover on destructive controls |

These values live in `app/gui/style.py` and `app/gui/appearance.py`. Repeated new roles belong in the central QSS; do not scatter equivalent RGBA values across page modules.

### Typography

Font stack:

```text
"Segoe UI", "Microsoft YaHei UI", "Yu Gothic UI", sans-serif
```

| Role | Size | Weight |
| --- | --- | --- |
| Base controls/body | 14 px | Regular |
| Page body emphasis | 15 px | Regular |
| Card title | 16 px | Bold |
| Section title | 18 px | Bold |
| App/navigation title | 20 px | Bold |
| Result metric | 28 px | Bold |
| Page title | 30 px | Bold |
| Window title | 13 px | Bold |

Rules:

- Use the existing object-name roles (`PageTitle`, `PageBody`, `SectionTitle`, `CardTitle`, `MutedText`, and `ResultText`) instead of page-local font declarations.
- Use bold for hierarchy, not for every label.
- Allow translated labels and long paths to wrap or elide deliberately. Never truncate the underlying stored value.
- Technical reports may use a text area, but the general interface remains in the UI font stack.

### Window and Shell Geometry

- Default window: `1180 × 760`.
- Minimum window: `900 × 560`.
- Frameless title bar: 44 px high.
- Root inset and shell gaps: 8 px; navigation-to-content gap: 12 px.
- Navigation rail: 84 px collapsed, 220 px expanded.
- Main content must remain usable at the minimum size; use page scrolling instead of shrinking controls below readable dimensions.

The title bar, navigation rail, and content panel are stable shell zones. A feature page should not bypass or restyle them.

### Page Recipe

New implemented pages should follow this composition:

```text
Page QWidget (transparent)
└─ root layout, zero margins
   └─ TransparentScrollArea
      └─ transparent content QWidget
         └─ vertical layout, margins 28/26/28/26, spacing 16
            ├─ PageTitle
            ├─ GlassCard(s)
            └─ stretch
```

Card internals normally use horizontal margins of 18 px, vertical margins of 16 px, and 10–12 px spacing. Deviate only when the content geometry requires it, such as an image preview or a compact inline toolbar.

When pages share a `QStackedWidget`, do not let one page's tall content stretch another page's cards. Use fixed vertical size policy for content-sized cards and place a stretch after them. Avoid hard-coded card heights when translation or results can grow.

### Components

#### Glass Cards

- A card groups one coherent task, settings family, or result.
- Use `GlassCard`; do not nest several glass cards solely for decoration.
- Put the title first, then inputs/actions, then explanatory or result text.
- Separate input and result cards when processing produces a large report, image, or metric.

#### Buttons

- `PrimaryButton`: start or confirm the main operation.
- `GlassButton`: secondary actions such as Browse, Add, Save preset, or navigation.
- `DangerButton`: stop or destructive actions only.
- `IconButton`/`IconTextButton`: compact shell or row actions with translated accessible text/tooltips.
- `SegmentButton`: mutually exclusive tool selection; the checked state must be visible.

Buttons use a minimum height of about 34 px, 6 px radius, and 8 × 12 px internal padding. Preserve disabled states while work is running and prevent duplicate starts.

#### Inputs

- Line edits, spin boxes, combo boxes, and text edits share quiet translucent fills, standard borders, and a stronger focus border.
- Pair path inputs with a clearly labeled Browse action.
- Preserve exact filesystem values. Display normalization must never rewrite a user's path silently.
- Use wheel-disabled numeric controls where accidental scroll changes would be harmful.
- Explain units in labels or suffixes (`dB`, `ms`, `Hz`, sample rate) rather than relying on documentation alone.

#### Results and Status

- A task reports start, completion, cancellation, and error through the page and shared status bar as appropriate.
- Do not show a success message until output is finalized.
- Large metrics use `ResultText`; detailed diagnostics use `MutedText` or a report text area.
- Image previews require an empty/loading/error state and must not force unrelated cards beyond the window width.

### Desktop Interaction

- Keep all long work off the GUI thread.
- Disable or change controls while an operation is active so the same task cannot start twice.
- Stop/cancel should request cancellation and report “cancelling” when shutdown is not immediate.
- Worker completion must restore controls for success, failure, and cancellation.
- Live language changes call every page's `retranslate()` and update shell/title/status content without restarting.
- Appearance controls are currently previews; do not imply persistence until it exists end to end.

## 4. Browser WebUI

### Visual Theme

The WebUI is a dark node-workflow workstation. Opaque surfaces and fine borders keep a graph with many nodes readable. Purple identifies the main graph/action accent; node-type colors distinguish workflow roles.

Public CSS roles are defined in `:root` in `app/web/static/styles.css`:

| Token | Value | Role |
| --- | --- | --- |
| `--bg` | `#0c0e13` | App and graph background |
| `--panel` | `#12151c` | Persistent side panels |
| `--panel-2` | `#171b24` | Raised controls and nested surfaces |
| `--panel-3` | `#1d222d` | Stronger nested/floating surface |
| `--line` | `#272d3a` | Standard divider and border |
| `--line-bright` | `#363e4e` | Strong/floating border |
| `--text` | `#e8ebf1` | Primary text |
| `--muted` | `#8b93a3` | Readable secondary text |
| `--dim` | `#5d6573` | Low-priority metadata and icons |
| `--accent` | `#8b5cf6` | Primary graph/action accent |
| `--accent-2` | `#a879ff` | Focus, active, and running accent |
| `--cyan` | `#47c8e8` | Audio/progress accent |
| `--green` | `#42d392` | Success/output state |
| `--orange` | `#f59e5b` | Warning/queued/dirty state |
| `--red` | `#ee6a72` | Error/cancel/destructive state |
| `--shadow` | `0 18px 60px rgba(0,0,0,.35)` | Floating menus and hints |

Use these variables when a role already exists. When a new semantic value is reused across components, promote it to `:root` and document it; one-off geometry may remain component-local. Do not add a second purple, green, or border system for a page-local variation.

Node type colors are categorical identifiers, not generic feedback colors:

| Node type | Color |
| --- | --- |
| File/folder input | `#4fc3df` |
| Separator/model | `#9a6cf2` |
| Slicer | `#f3a45f` |
| Peak normalizer | `#e66f8f` |
| Output folder | `#54d69a` |

Keep a node's type color stable across the library item, node header/icon, ports where applicable, minimap, and running highlight. Validation red overrides categorical emphasis when an error must be addressed.

### Typography

Font stack:

```text
Inter, "Segoe UI", "Microsoft YaHei UI", system-ui, sans-serif
```

- Root size is 16 px.
- Standard controls and node titles are 13–15 px.
- Secondary metadata is 10–12 px.
- Panel headings are 18 px and semibold.
- Use uppercase eyebrow labels only for stable section identifiers such as NODE LIBRARY, PROPERTIES, WORKFLOWS, and RUNS.
- Use semibold for node names and structural labels; keep descriptions regular.
- Long workflow names, model names, stems, and paths must elide or wrap without expanding fixed toolbars or sidebars.

### Shell Geometry

- Top bar: 62 px.
- Workflow tabs: 36 px.
- Combined `--header-height`: 98 px.
- Default node library width: 320 px; allowed range 220–520 px.
- Default inspector width: 360 px; allowed range 260–520 px.
- Desktop canvas column keeps at least 420 px in the widest layout and 300 px below 1050 px.
- Sidebars are user-resizable on wide layouts. The separator must expose keyboard and ARIA state as well as pointer resizing.

The graph canvas is the primary work surface. Sidebars support it and should collapse or become drawers before the canvas becomes unusable.

### Graph Components

#### Library Items

- Group nodes by workflow role; separator subgroups represent function, while architecture remains a filter.
- Installed state and “outputs need confirmation” are status, not taxonomy.
- Show summary information in the row and provide metadata on demand. Do not make every row permanently tall.
- Unavailable nodes explain why they cannot be added.
- Drag and double-click addition should remain equivalent paths to the same node creation behavior.

#### Nodes

- Default node width: 224 px; header height: 40 px; radius: 9 px.
- The complete non-interactive node surface is the drag target. Ports, buttons, links, form controls, and the resize handle retain their own pointer behavior.
- A visible lower-right handle resizes node width and height. Resizing must follow canvas zoom, update connections and the minimap continuously, support keyboard arrow adjustments, and participate in workflow history and persistence.
- Header color identifies type. Body content stays on the neutral panel surface.
- Selection uses the node color plus a stronger border/shadow.
- Running uses the node color as an active glow; validation errors use semantic red.
- Titles and port labels elide visually but exact model filenames and stem handles remain in data.
- File and folder summaries may show a compact basename for scanning. Preserve complete folder paths in data; browser-uploaded audio preserves its original display name and opaque upload ID.
- Selection exposes one compact floating node toolbar positioned inside the canvas viewport. Duplicate is neutral; Delete uses semantic red and requires an anchored confirmation. Cancel, Escape, and clicking outside dismiss the confirmation without deleting.
- New nodes need a stable type, icon, title key, category, input/output contract, inspector editor, validation, execution support, and tests. A library-only card is not a completed node.

#### Ports and Connections

- Ports remain visible outside the node edge with a minimum visual target and a larger effective pointer target where practical.
- Hover, pending, compatible, and drop-target states must be distinct.
- A connection can start from either an input or output port; compatibility rules are direction-independent.
- Ordinary inputs accept one edge. Smart classification output is the deliberate exception and communicates that its audio input accepts multiple separator-derived edges.
- Edge selection, active flow, and validation errors must remain visually distinguishable.
- Raw port handles are backend contracts and are never localized or normalized. Only labels are presentation.

#### Inspector

- Empty state explains how to select a node.
- Group fields into coherent sections: model information, paths, parameters, ports, and validation as applicable.
- Single audio uses the browser-native file input and reports upload state at the field. Server-local folder paths retain the native folder picker.
- Common parameters appear before advanced model-specific options.
- Changes update the active editor only, participate in undo/draft behavior, and visibly mark the workflow dirty.

### Web Controls and Overlays

- The gradient purple Run button is the primary action.
- Neutral text/icon buttons handle management, refresh, save, and canvas tools.
- Cancel uses red styling and appears only when cancellation is available.
- Controls are approximately 30–37 px high; icon-only controls retain labels through `title`/ARIA and visible focus.
- Dialogs use a dark scrim, one strong floating surface, clear title/subtitle hierarchy, and an explicit close action.
- Toasts are transient feedback. Persistent or actionable failures also appear at the affected node, connection, validation banner, run record, or activity log.
- Menus and previews stay inside the viewport and do not obscure the initiating control unnecessarily.
- Floating node toolbars follow node movement, resizing, canvas pan/zoom, sidebar layout changes, and viewport resizing without changing graph geometry.

### Web Interaction Contract

- Canvas panning begins only on the canvas background, never from nodes, ports, floating toolbars, form controls, or links.
- Node movement uses world coordinates adjusted for zoom and commits history only after a real move.
- Pointer capture is released on normal completion and cancellation. `pointercancel`, lost capture, window blur, workflow replacement, and node deletion must leave no stuck interaction state.
- Escape closes the topmost manager or cancels a pending connection before invoking broader shortcuts.
- `Ctrl/Cmd+S` saves; `Ctrl/Cmd+Z` and `Ctrl/Cmd+Shift+Z` navigate the active workflow's history.
- Each open workflow owns its own graph, transform, selection, history, draft, dirty state, and run association.
- Server workflow revision conflicts are visible and recoverable; never overwrite the server silently.
- The browser reconciles run state from the server snapshot and global event stream. Switching tabs never transfers run ownership.
- Cancellation is a request until the server reports a terminal state.

### Responsive Behavior

Preserve the existing transition points:

| Width | Behavior |
| --- | --- |
| Above 1050 px | Full resizable library, canvas, and inspector layout |
| 801–1050 px | Narrower sidebars and canvas; workflow-name field is hidden |
| 651–800 px | Inspector becomes a right drawer; resizers disappear; actions compact |
| 481–650 px | Library also becomes a left drawer; canvas becomes the only grid column |
| 480 px and below | Language selector hides and canvas toolbar becomes more compact |

Rules:

- Drawer visibility is derived from viewport state, not persisted as if it were a wide-layout preference.
- Preserve at least 48 px of context beside a mobile drawer.
- Dialogs fit inside the viewport with internal scrolling.
- Toolbars may hide text labels before hiding the action itself.
- Test immediately above and below affected breakpoints; resizing across a breakpoint must cancel or reconcile active pointer interactions cleanly.

## 5. Internationalization and Content

Supported locales:

```text
English (en) · Simplified Chinese (zh_CN / zh-CN) · Japanese (ja)
```

- No new user-visible string may exist in only one locale.
- Desktop strings use `Translator` keys and participate in `retranslate()`.
- Static WebUI strings use `data-i18n`, `data-i18n-title`, `data-i18n-placeholder`, or `data-i18n-aria-label`; dynamic strings use `t()`/`plural()`.
- Keep locale key sets identical and preserve script load order before `app.js`.
- Do not translate file paths, model filenames, node IDs, stem handles, workflow IDs, error codes, or serialized keys.
- Use product terms consistently within each locale. Avoid two labels for the same operation unless they express different actions.
- Copy should say what happened and what the user can do next. Avoid unexplained technical tracebacks in primary UI messages.
- Do not claim Train or Inference functionality while those pages remain placeholders.

Plan layouts for expansion:

- Buttons should tolerate longer Japanese and English labels.
- Chinese text may be visually compact but must not be used to justify a fixed width that clips other locales.
- Model names and Windows paths may contain long unbroken segments; use elision, wrapping, and title/detail views deliberately.

## 6. Accessibility and Input

- Preserve semantic HTML landmarks, dialog roles, tab lists, labels, and ARIA state in the WebUI.
- Icon-only actions need a translated accessible name and a visible focus state.
- Keyboard focus must not be removed merely for visual cleanliness.
- Pointer-only behavior needs a keyboard or click fallback when the action is essential. Port connections retain click-to-connect alongside dragging.
- Desktop controls need labels or translated tooltips; do not rely on a symbol whose meaning changes by locale or platform.
- Use disabled state only for genuinely unavailable actions. Do not disable a control to hide an unexplained error.
- Animations should be short and functional. Avoid continuous decorative motion; running pulses and flow indicators stop at terminal state.
- Do not encode instructions as text baked into images.

## 7. Do and Don't

### Do

- Reuse central QSS object names and WebUI root variables.
- Keep one obvious primary action per local task area.
- Use node-type colors consistently and semantic feedback colors truthfully.
- Design all relevant idle, hover, focus, selected, disabled, running, cancelling, success, warning, and error states.
- Keep local scan, online catalog sync, model download, and workflow execution visibly separate.
- Preserve exact paths and backend handles while formatting only their display labels.
- Check the minimum desktop window, WebUI breakpoints, and long translated strings.
- Update this file when adding a reusable token, component, or interaction pattern.

### Don't

- Do not add page-local colors or fonts when an existing semantic role fits.
- Do not use glass, blur, gradients, glow, or shadows merely to make a new feature look more prominent.
- Do not make warning, success, danger, or node-type colors decorative.
- Do not hide errors only in a transient toast or console.
- Do not block the Qt event loop or make the WebUI appear finished before the server reaches a terminal state.
- Do not introduce a frontend framework, icon library, token system, or build pipeline as part of an unrelated feature.
- Do not guess unknown model outputs or display a guessed label as an execution handle.
- Do not solve one viewport by breaking another supported breakpoint.

## 8. Agent UI Checklist

Before implementing a UI change:

1. Read this file and inspect the nearest existing component on the same surface.
2. Identify the owning style/component file and all interaction states.
3. Decide whether the change is local composition or a reusable pattern.
4. List every user-visible string and add all three locales in the same change.
5. Trace any new value through schema, validation, persistence, and execution—not only the view.

Before handing off:

1. Check desktop at `1180 × 760` and `900 × 560`, or the WebUI around every affected breakpoint.
2. Check long English/Japanese labels, long Windows paths, and long model/stem names.
3. Check keyboard focus, disabled behavior, cancellation, failure, and empty state.
4. Run the verification required by `AGENTS.md` and the affected developer document.
5. Review the diff for one-off styles, hard-coded user-visible strings, and accidental changes to raw handles.
