# SLAI Pet Demo Design System

## 0. Research Log

- Embedded refs: shortlisted `notion.md`, `claude.md`, and `airbnb.md`; picked Notion-inspired warm minimalism because this is a calm, owner-facing desktop companion panel.
- UI UX DB: searched `pet companion calm desktop dashboard` on the `html-tailwind` stack; retained the mobile-first responsive rule.
- Lazyweb: skipped because the requested asset is an internal MVP panel, not a clone of a named product; no external screen is treated as a visual contract.
- Imagen drafts: skipped because this page uses existing Live2D/API assets and does not need a new hero bitmap.

## 1. Atmosphere & Identity

The demo is a small observatory for a living companion: warm paper surfaces, one clear status signal, and a soft dusk accent that makes state changes feel meaningful. The signature is a “pet orbit” visual: a luminous circular companion card beside a compact, readable state ledger.

## 2. Color

| Role | Token | Value | Usage |
|---|---|---|---|
| Canvas | `--color-canvas` | `#f4f1ec` | Page background |
| Surface | `--color-surface` | `#fffdf9` | Cards and panels |
| Surface muted | `--color-surface-muted` | `#ebe5dc` | Secondary panel |
| Text primary | `--color-ink` | `#282522` | Headings and body |
| Text secondary | `--color-ink-muted` | `#756d65` | Labels and hints |
| Line | `--color-line` | `#ded6cc` | Quiet dividers |
| Accent | `--color-accent` | `#c26a4a` | Primary action and focus |
| Accent deep | `--color-accent-deep` | `#8f4430` | Pressed and strong states |
| Mint | `--color-mint` | `#6aa995` | Healthy/connected status |
| Sky | `--color-sky` | `#87aeca` | Energy and information |
| Gold | `--color-gold` | `#d59a4b` | Experience and growth |
| Danger | `--color-danger` | `#b44f4f` | Error only |
| Accent soft | `--color-accent-soft` | `#f9e8df` | Persona pill |
| Pet gold | `--color-pet-gold` | `#f9c177` | Pet illustration |
| Pet coral | `--color-pet-coral` | `#edb07e` | Pet illustration |
| Pet lilac | `--color-pet-lilac` | `#e5d6dd` | Orbit surface |
| Pet cloud | `--color-pet-cloud` | `#d5dbe3` | Orbit surface |
| Pet peach | `--color-pet-peach` | `#f9dfc9` | Orbit surface |
| Pet cream | `--color-pet-cream` | `#fff2d7` | Orbit surface |
| Surface warm | `--color-surface-warm` | `#fff7ef` | Hover surface |
| Mint soft | `--color-mint-soft` | `#c2e0ca` | Study icon |
| Sky soft | `--color-sky-soft` | `#d8eff4` | Bath icon |
| Purple soft | `--color-purple-soft` | `#bb8cb6` | Adventure icon |

Accent is reserved for interaction and the pet orbit glow. Surfaces use a tonal shift plus a restrained multi-layer shadow.

## 3. Typography

- Primary: `ui-rounded`, `-apple-system`, `BlinkMacSystemFont`, `"Segoe UI"`, sans-serif.
- Mono: `ui-monospace`, `SFMono-Regular`, Menlo, monospace.
- Display: 40px/1.1/700; H2: 24px/1.25/700; H3: 18px/1.35/700; body: 16px/1.6/400; small: 14px/1.5/500; label: 12px/1.35/700.
- CJK body never falls below 14px and long labels wrap naturally.

## 4. Spacing & Layout

Base unit is 4px. Tokens: `--space-1:4px`, `--space-2:8px`, `--space-3:12px`, `--space-4:16px`, `--space-5:20px`, `--space-6:24px`, `--space-8:32px`, `--space-10:40px`, `--space-12:48px`.

The page uses a centered max-width of 1180px, a 12-column desktop grid, and one-column mobile flow. Breakpoints: 640px and 960px. Cards own their content; the page is the scroll owner.

## 5. Components

### Pet Orbit Card

- Structure: heading, status badge, gradient orbit, SVG pet mark, current persona metadata.
- States: connected, loading, error, and reduced-motion.
- Accessibility: status is text, SVG is decorative, focusable actions use visible rings.
- Motion: only `transform` and `opacity`; orbit pulse communicates connection and pauses under reduced motion.

### State Ledger

- Structure: repeated label/value/progress rows for hunger, energy, health, mood, intimacy, and growth.
- Variants: healthy, warning, and low based on server values.
- Accessibility: each progress bar has an accessible label and numeric value.

### Action Button

- Structure: native button with text label and optional inline SVG icon.
- States: default, hover, active, focus, disabled, loading.
- Motion: 140ms color/transform feedback only.

### Artifact Card

- Structure: skill label, title, short explanation, native button, result link.
- States: idle, generating, success, error.
- Accessibility: result link receives focus after generation.

## 6. Motion & Interaction

- Micro: 140ms ease-out for button press and status changes.
- Standard: 240ms ease-in-out for panel reveal.
- No decorative infinite loops except the orbit pulse, which conveys live connection and is disabled by `prefers-reduced-motion`.
- Camera buttons describe privacy-preserving presence events; no frame is uploaded by this demo.

## 7. Depth & Surface

Strategy: mixed. Cards use a whisper line plus a low-opacity layered shadow; the hero pet orbit uses tonal gradients to create depth. No hard black shadows.

## 8. Accessibility Constraints & Accepted Debt

- WCAG 2.2 AA target; keyboard reachability, visible focus, 4.5:1 body contrast, semantic landmarks, and reduced motion are required.
- Accepted debt: Live2D rendering remains in the upstream compiled app, so this independent page uses a small inline SVG pet mark until the frontend source submodule is available. Owner: frontend member; exit: integrate the event protocol into `Open-LLM-VTuber-Web`.

## 9. Pet World Main-Stage Redesign

The demo is now a scene first, control surface second. The original Open-LLM-VTuber page is reused as the focal Live2D world inside a same-origin stage frame, preserving the project's actual model, room background, idle motion, and existing tap interactions. Our pet state, action, and skill controls sit in a compact bottom dock; secondary controls live in a right-side drawer and are hidden until requested.

### 9.1 Scene grammar

- Viewport: one full-height world shell with a quiet top status bar and a large stage taking the remaining space.
- Stage: original Live2D page at `/`, cropped to the character/world region on desktop and shown full width on mobile.
- Dock: four high-frequency action affordances (`摸摸`, `喂食`, `玩耍`, `聊天`) plus a compact chat entry. The dock is a control rail, not a dashboard card.
- Drawer: state ledger, all world actions, skills, persona summary, and presence simulation. It opens from the dock and closes with Escape or the close button.
- Feedback: actions produce a short scene pulse, a compact action toast, and refreshed state chips; no decorative animation runs without a state change.

### 9.2 New tokens

| Role | Token | Value |
|---|---|---|
| World canvas | `--world-ink` | `#f7f0e8` |
| World glass | `--world-glass` | `rgba(20, 24, 38, .82)` |
| World line | `--world-line` | `rgba(255, 255, 255, .16)` |
| World accent | `--world-accent` | `#f0b36a` |
| Dock height | `--dock-height` | `76px` |
| Drawer width | `--drawer-width` | `min(420px, 92vw)` |

### 9.3 Motion contract

- Action feedback uses a 420ms `transform`/`opacity` scene pulse and a 180ms toast enter; it is tied to a server result.
- Drawer uses a 220ms translate/opacity transition and supports Escape, close button, and reduced-motion fallback.
- `prefers-reduced-motion: reduce` disables the scene pulse and drawer transition while preserving state changes and text feedback.

### 9.4 Accepted debt

- The outer Demo now calls the compiled bundle's public `window.getLAppAdapter()` bridge to map `摸摸`、`喂食`、`玩耍` and `聊天` to real motion/expression indices. The remaining debt is architectural: this bridge belongs to the compiled upstream page, so a future frontend-submodule integration should move the mapping into a typed event protocol instead of relying on iframe access. The iframe is delayed briefly during first load so upstream permission toasts do not cover the hero copy, and a top crop keeps upstream utility chrome out of the world stage.
