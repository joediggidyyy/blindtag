# BlindTag Widget Schema

**Status**: Revised — Pass H design targets applied (anchor-only emoji insert, encode resolution pipeline); input validation schema added; format selector removed from banner (box1 is format-agnostic)
**Precondition**: Pass C complete (`e134dab`); all 25 CLI tests passing; calamum go/pass
**Execution authority**: This document is the design contract. An implementation checklist will be created before Pass D begins.
**Scope**: Three surfaces — in-product guidance panel, emoji alias selector flyout, and emoji library editor

---

## Design principles (widget-specific)

These extend the core Polymath visual precedents already established in `widget.py`:

1. **Locked baseline** — the existing title bar / toggle strip / panel stack / status bar layout is immutable. New surfaces extend it; they do not restructure it.
2. **Left-side slide-out for guidance** — the `?` help trigger opens a slide-out from the left edge, keeping the right-side encode/decode panel fully visible.
3. **Collapsed cards, in-card caret** — help cards are collapsed by default; only entries with meaningful deeper content expose an expand caret. Expanding happens vertically in place.
4. **No control-bar intrusions** — the emoji selector is a floating `QFrame` flyout anchored to a small inline trigger; it is not a dialog, modal, dropdown bar, or boxed control cluster.
5. **Alias transparency** — the payload constraint (printable ASCII only) means emojis must be represented as ASCII alias strings. The selection flyout shows only the emoji glyph (fast scan, no text noise). The edit panel reveals the active alias and the full `codes` pick list, keeping complexity out of the selection flow.
6. **Library ships with the application** — `assets/emoji_library_default.json` is a tracked, versioned file committed to the repo. It is the working library at runtime; there is no separate user-local copy or seed step. Users edit it via the in-app editor; those edits persist to the same file.

---

## Surface 1 — Guidance panel

### Trigger

A `?` button is added to `_TitleBar`, positioned to the right of the title text `BlindTag`, left of the spacer (so it does not crowd the minimize/close buttons):

```
│ ⬡ BlindTag  ?                              ─   ✕  │
```

The button uses `_btn_ghost_style()` with a fixed size of `26×26`. It toggles the guidance panel open/closed. The panel is not a separate window — it is a `QWidget` overlaid on the left edge of the main `QWidget`, same stacking level as the panels in `_stack`.

### Panel layout

```
┌──────────────────────────────────────────┐
│ ⬡ BlindTag  ?                    ─   ✕  │
├──────────────────────────────────────────┤
│ ┌──────────────┐                         │
│ │ HELP         │  [Encode] [Decode] □    │
│ │              ├─────────────────────────┤
│ │  ▶ Anchor    │                         │
│ │    text      │  [main panel content]   │
│ │  ▶ Hidden    │                         │
│ │    payload   │                         │
│ │  ▶ Emoji     │                         │
│ │    aliases   │                         │
│ │  ▶ Obfuscate │                         │
│ │    & Copy    │                         │
│ │  ▶ Clip Watch│                         │
│ └──────────────┘                         │
├──────────────────────────────────────────┤
│ Status message                        ●  │
└──────────────────────────────────────────┘
```

- Width: `200px`, fixed
- Background: `C_SECONDARY` (`#1E1E1E`)
- Border-right: `1px solid #303030`
- The guidance panel overlays (not pushes) the encode/decode panel; main panel content is still scrollable behind it
- The toggle strip and status bar are always fully visible regardless of panel state

### Card structure

Each card is a `QWidget` with:
- Header row: `▶ / ▼` caret label + bold topic label, full-width clickable
- Expanded body: a `QLabel` with `wordWrap=True`, `C_TEXT` color (not `C_MUTED` — body guidance prose must be readable, not dimmed), `10pt` font, `4px` left-indent from the caret column

> **Readability rule**: `C_MUTED` is reserved for section labels and hints. Guidance card body text uses `C_TEXT` (`#E0E0E0` or equivalent) at ≥10pt.

### Card content

| Card | Caret | Expanded guidance |
|------|-------|-------------------|
| **Anchor text** | ✓ | The visible text your payload will be hidden inside. Any readable string works. The receiver sees only this text unless they decode it. |
| **Hidden payload** | ✓ | Your secret message — plain text only (letters, numbers, punctuation, spaces). Max ~9,000 characters. Nothing from the emoji selector goes here; this field is exclusively for the message you want to hide. |
| **Emoji format** | ✓ | The anchor text field accepts any emoji representation — raw glyph (🗑️), Unicode notation (`U+1F5D1`), or alias code (`:trash:`). All are valid cover text. At encode time the widget resolves any tokens to actual glyph characters before embedding the payload. No input is rejected. |
| **Obfuscate & Copy** | ✓ | Runs encode and immediately copies the result to your clipboard. The output looks identical to your anchor text — the payload is invisible. |
| **Clip Watch** | ✓ | Monitors your clipboard. When you copy text that contains a hidden payload, BlindTag automatically detects and shows it. No data leaves your machine. |

---

## Surface 2 — Emoji selector

### Format selector — REMOVED FROM BANNER

The format selector button (`[Glyph ▾]`) is **not present** in the toggle strip. The toggle strip is:

```
[Encode] [Decode]                             □ Clip Watch
```

**Rationale**: Box1 (ANCHOR TEXT) is format-agnostic — it accepts raw glyphs, `U+XXXX` notation, and `:alias:` codes interchangeably. The encoder resolves all token forms at encode time (see encode resolution pipeline below). Because the anchor field auto-detects any input format, a sender-side format toggle is redundant.

**Output format**: the encoded output (box3) is always the raw Unicode string with Plane 14 payload characters. There is no meaningful output format choice — the receiver's decoder extracts Plane 14 tags regardless of visible anchor content. If a user wants to inspect what was embedded, they use the Decode panel.

**Flyout insert behaviour**: since the format selector is removed, the emoji flyout always inserts the raw emoji glyph character into the anchor field. This is the most natural flyout action and produces valid input under the format-agnostic box1 schema.

### Trigger placement

In `_build_encode_panel()`, the `ANCHOR TEXT` section label row gains an inline emoji trigger button on the right side of the label row:

```
ANCHOR TEXT  ·  visible cover                    ☺
```

The `☺` button (`26×26`, `_btn_ghost_style()`) opens the flyout. It is anchored to the button position so the flyout appears just below the label row.

### Flyout layout

```
┌────────────────────────────────┐
│  😀   😂   ❤️   👍   👎   🔥  │
│  ⭐   ✅   ❌   ⚠️   🔒   🔓  │
│  📎   📋   🗑️   💬   📌   🏷️  │
│  🔑   👁️                       │
│  ──────────────────────────    │
│  Edit library              ⚙  │
└────────────────────────────────┘
```

- The flyout is a `QFrame` with `StyledPanel` shape, not a separate window
- Width: `240px`, height auto-expands to fit grid (max `220px`, scrollable)
- Background: `C_SURFACE` (`#252525`), border `1px solid #303030`
- Each cell shows **only the emoji glyph** — no format text in the flyout cells
- Clicking a cell performs a **single-field insert** into `_anchor_input` only — appends the raw emoji glyph character
  - **Nothing is written to `_hidden_input`** — the hidden payload field is always untouched
- The flyout dismisses on click-outside or `Escape`
- `Edit library` link at the bottom opens the library editor panel

### Encode resolution pipeline

Before calling `core.encode(anchor, payload)`, the widget resolves format tokens in `_anchor_input`:

1. **Unicode tokens**: scan for `U+[0-9A-Fa-f]{4,6}( U+[0-9A-Fa-f]{4,6})*` → resolve to the corresponding Unicode character(s)
2. **Alias tokens**: scan for `:[a-z0-9_]+:` or bare uppercase keywords — look up in library → resolve to the emoji glyph
3. **Glyph / plain text**: no transformation needed; passed through as-is
4. Unresolvable tokens (no match in library, invalid codepoint) pass through unchanged — they are valid visible cover text

The resolved string is passed to `encode()`. The OUTPUT field displays the result (the glyph with invisible Plane 14 payload).

> **Pipeline rationale**: Decoupling format from encoding means the decoder requires no format knowledge — it extracts Plane 14 tags regardless of what the anchor looks like. The format is a sender-side UX choice only.

### Grid layout

Entries are laid out in a `QGridLayout`, 6 columns. Each cell is a `QPushButton`:

```
[ 😀 ]  [ 😂 ]  [ ❤️ ]  [ 👍 ]  [ 👎 ]  [ 🔥 ]
```

Button style: `_btn_ghost_style()` with `font-size: 18pt`, `padding: 6px`, fixed `44×44` size.

---

## Surface 3 — Library editor

### Access

Accessible only from the `Edit library` link in the emoji flyout. Not exposed from the title bar or toggle strip — it is a secondary surface.

### Implementation

A fourth panel added to `_stack` (after encode, decode). The toggle strip `[Encode] [Decode]` never shows a `[Library]` tab — the editor is entered via the flyout and exited via a `← Back` ghost button at the top of the editor panel.

### Editor layout

```
┌──────────────────────────────────────────┐
│ ⬡ BlindTag  ?                    ─   ✕  │
├──────────────────────────────────────────┤
│ [Encode] [Decode]               □ Clip  │
├──────────────────────────────────────────┤
│  ←  Emoji Library                        │
│  ─────────────────────────────────────   │
│  😀  :smile:        smile       [✕]      │
│  😂  :lol:          laughing    [✕]      │
│  ❤️  :heart:        heart       [✕]      │
│  ...                                     │
│  ─────────────────────────────────────   │
│  + Add entry                             │
│  😊  label   [________________]  [Add]  │
└──────────────────────────────────────────┘
```

> **Row design**: Each row shows the glyph, the active alias (tooltip shows the full `codes` list), and the human label. The alias is shown in `C_MUTED` at `9pt` as a reference; users never need to type it into the anchor — they can just type a glyph directly or let the flyout insert it.

**Per-row columns:**

| Column | Content |
|--------|--------|
| Glyph | Emoji rendered at `18pt`; non-editable. |
| Active alias | The `alias` value for this entry (e.g. `:trash:`). Shown in `C_MUTED` at `9pt`. Tooltip shows full `codes` list. |
| Label | `C_MUTED` display label |
| Delete `✕` | Removes the entire entry; no confirmation dialog |

**Add entry form** (bottom, inline — emoji picker icon · label field · Add button):

- **Dual-input emoji field**: accepts either a rendered emoji glyph (paste `👎`) or a code string (type `:thumbsdown:` or `NO`). Detection:
  - 1–2 chars with codepoint outside printable ASCII → treat as glyph directly; alias auto-set to `:label:` normalized from the label field
  - Matches `^[ -~]+$` (printable ASCII, code-like) → use as active alias; a resolvable code sets the glyph if found in the existing library, otherwise the user must also paste the glyph
- `Label` field: plain text; required
- `Add` button: disabled until both emoji (or resolvable code) and label are non-empty
- Validation: code string must match `^[ -~]+$`; red border on invalid input, no modal
- On add: new entry appended with `alias = resolved_code`, `codes = [resolved_code]`, `emoji = resolved_glyph`

**Write-through:** All changes (add, delete) write immediately to `assets/emoji_library_default.json`. No Save button.

---

## Persistence — `assets/emoji_library_default.json`

### Authority

`assets/emoji_library_default.json` is a **tracked, versioned file committed to the repository**. It is the single working library — there is no separate user-local copy or seed step. The in-app editor writes directly to this file. It ships pre-populated with the default 20-entry library including per-emoji `codes` arrays.

### Format

```json
[
  { "emoji": "😀", "alias": ":smile:",      "codes": [":smile:", ":smiley:", ":grinning:", "SMILE"],  "label": "smile"       },
  { "emoji": "😂", "alias": ":lol:",        "codes": [":lol:", ":joy:", "LOL"],                       "label": "laughing"    },
  { "emoji": "❤️", "alias": ":heart:",      "codes": [":heart:", ":love:", "HEART"],                  "label": "heart"       },
  { "emoji": "👍", "alias": ":thumbsup:",   "codes": [":thumbsup:", ":+1:", "OK"],                   "label": "thumbs up"   },
  { "emoji": "👎", "alias": ":thumbsdown:", "codes": [":thumbsdown:", ":-1:", "NO"],                  "label": "thumbs down" },
  { "emoji": "🔥", "alias": ":fire:",       "codes": [":fire:", "HOT"],                              "label": "fire"        },
  { "emoji": "⭐", "alias": ":star:",       "codes": [":star:", "STAR"],                             "label": "star"        },
  { "emoji": "✅", "alias": ":check:",      "codes": [":check:", ":ok:", "YES"],                     "label": "check"       },
  { "emoji": "❌", "alias": ":x:",          "codes": [":x:", ":no:", "NO"],                          "label": "x"           },
  { "emoji": "⚠️", "alias": ":warn:",       "codes": [":warn:", ":alert:", "WARN"],                  "label": "warning"     },
  { "emoji": "🔒", "alias": ":lock:",       "codes": [":lock:", "LOCKED"],                           "label": "lock"        },
  { "emoji": "🔓", "alias": ":unlock:",     "codes": [":unlock:", "OPEN"],                           "label": "unlock"      },
  { "emoji": "📎", "alias": ":clip:",       "codes": [":clip:", ":attach:"],                         "label": "clip"        },
  { "emoji": "📋", "alias": ":paste:",      "codes": [":paste:", ":clipboard:"],                     "label": "paste"       },
  { "emoji": "🗑️", "alias": ":trash:",      "codes": [":trash:", ":delete:", "DEL"],                 "label": "trash"       },
  { "emoji": "💬", "alias": ":msg:",        "codes": [":msg:", ":chat:", "MSG"],                     "label": "message"     },
  { "emoji": "📌", "alias": ":pin:",        "codes": [":pin:", "PIN"],                               "label": "pin"         },
  { "emoji": "🏷️", "alias": ":tag:",        "codes": [":tag:", "TAG"],                               "label": "tag"         },
  { "emoji": "🔑", "alias": ":key:",        "codes": [":key:", "KEY"],                               "label": "key"         },
  { "emoji": "👁️", "alias": ":eye:",        "codes": [":eye:", ":watch:", "EYE"],                    "label": "eye"         }
]
```

### Schema fields

| Field | Type | Description |
|-------|------|-------------|
| `emoji` | string | Unicode emoji glyph; display only |
| `alias` | string | The active alias code for this emoji (e.g. `:trash:`); must be a member of `codes` |
| `codes` | string[] | Full pick list of available codes for this emoji; each must match `^[ -~]+$` (printable ASCII) |
| `label` | string | Human-readable name; shown in editor only, never encoded |

### Load behavior

At `BlindTagWindow.__init__`, load `assets/emoji_library_default.json`. If the JSON is malformed, log a warning to the status bar and continue with an empty library (do not crash).

### Validation rule

On Add entry / Add code: every code must match `^[ -~]+$` (printable ASCII 0x20–0x7E). Reject with red border; no modal or dialog.

---

## Input validation schema

Blindtag uses a declarative field-spec pattern for input handling, consistent with the `_DSWizardFieldSpec` convention in the observer project (`observerctl.py`, line ~10068). Each field is described by a frozen dataclass spec rather than ad-hoc conditional checks.

### Box1 — ANCHOR TEXT (`_anchor_input`)

| Attribute | Value |
|-----------|-------|
| `key` | `anchor_text` |
| `value_kind` | `cover-text` |
| `required` | No — empty anchor is valid cover text |
| `max_length` | None — no cap enforced |
| `choices` | None — any input is accepted |
| `reject_policy` | `never` — no input string is rejected |
| `description` | Visible cover text. Accepts raw glyphs, `U+XXXX` codepoint notation, `:alias:` codes, or plain text. All forms resolve at encode time. |

**Auto-detection order** (applied by the encode resolution pipeline, not at input time):

1. Scan for `U+[0-9A-Fa-f]{4,6}( U+[0-9A-Fa-f]{4,6})*` → resolve to Unicode character(s)
2. Scan for `:[a-z0-9_]+:` or bare uppercase keywords → look up in emoji library → resolve to glyph
3. Remaining characters (raw glyphs, plain text) → pass through unchanged
4. Unresolvable tokens (no library match, invalid codepoint) → pass through unchanged as visible cover text

No validation error is raised for box1 input. At encode time, if the anchor contains only Plane 14 characters (which would make the output invisible), the status bar may warn — but this is an encode-time advisory, not input rejection.

### Box2 — HIDDEN PAYLOAD (`_hidden_input`)

**No input validation.** The field accepts any text without filtering, length warnings, or character checks at input time.

At encode time, `core.encode()` raises `InvalidPayloadError` for characters outside printable ASCII (0x20–0x7E). This error is surfaced in the status bar as an encode-time failure — it is not pre-validated in the widget.

### Emoji editor — Add entry form

The editor add form writes structured data to `emoji_library_default.json` and requires field-level validation:

| Field | `value_kind` | Constraint | Reject on |
|-------|-------------|------------|----------|
| `emoji` (glyph input) | `glyph` | At least one codepoint outside printable ASCII range (U+0020–U+007E); 1–2 grapheme clusters | Input contains only printable ASCII → glyph detection fails; red border shown |
| `label` | `text` | Non-empty; max 60 chars | Empty → Add button remains disabled |
| `alias` / `code` | `ascii-code` | Matches `^[ -~]+$` (printable ASCII 0x20–0x7E); max 30 chars | Non-matching chars → red border; no modal |

Validation is synchronous and inline — red border on the failing field, no dialog or modal. The `Add` button is disabled until `emoji` (or resolvable code) and `label` are both non-empty and valid.

The `emoji` field also accepts a code string (`:alias:` or bare keyword) as a secondary input path: if the code resolves to a known library entry, the glyph is auto-filled. If the code does not resolve, the user must also paste the glyph directly.

---

## Title bar change summary

Before:
```
│ ⬡ BlindTag                               ─   ✕  │
```

After:
```
│ ⬡ BlindTag  ?                            ─   ✕  │
```

The `?` button is inserted after the title label, before `addStretch()`. It is `26×26`, `_btn_ghost_style()`, toggles the guidance panel.

---

## New module / file inventory

| Artifact | Type | Notes |
|----------|------|-------|
| `assets/emoji_library_default.json` | Data | Tracked, versioned. Ships pre-populated with 20 entries including `codes` arrays. Single working library — in-app edits write directly to this file. |
| `blindtag/widget.py` | Modified | `_GuidancePanel`, `_EmojiCard`, `_EmojiFlyout`, `_LibraryEditorPanel` classes; `?` button in `_TitleBar`; emoji trigger in `_build_encode_panel()` |

No new Python modules. All new UI classes live in `widget.py`.

---

## Calamum / test surface

| Test class | Scope |
|------------|-------|
| `TestEmojiLibrary` (in `tests/test_widget.py`) | Load `emoji_library_default.json`; verify schema (all entries have `emoji`, `alias`, `codes`, `label`); `alias` is member of `codes`; all codes pass ASCII validation; add/remove entry; add/remove code; set active alias |
| `TestGuidancePanel` (in `tests/test_widget.py`) | Panel opens/closes, card count matches schema, card text not empty |
| `TestEmojiFlyout` (in `tests/test_widget.py`) | Flyout cell count matches library length; clicking a cell inserts the raw emoji glyph into `_anchor_input` only (single-field insert); `_hidden_input` is not modified |

These are part of the `tests/test_widget.py` work already in Planned. The emoji/guidance implementation should ship as part of the same pass that delivers `test_widget.py`.

---

## Implementation notes (added during planning pass)

These notes resolve gaps identified during plan review. They do not change any design decision in this schema — they specify implementation details that are required for correct, testable, Polymath-aligned code.

### Library file path resolution

`assets/emoji_library_default.json` must be resolved relative to the package, not the working directory:

```python
_DEFAULT_LIBRARY_PATH = Path(__file__).resolve().parent.parent / "assets" / "emoji_library_default.json"
```

This resolves correctly when the package is installed in editable mode (`pip install -e .`) or run from any working directory.

### `EmojiLibrary` helper class (headless)

Library load/save/validate logic must be extracted into a standalone `EmojiLibrary` class that accepts an explicit `path` parameter. This is required for:
- Unit testing add/remove/alias operations without mutating `assets/emoji_library_default.json`
- Clear separation between library logic (no Qt) and UI classes

`BlindTagWindow.__init__` instantiates `EmojiLibrary(_DEFAULT_LIBRARY_PATH)`. Test classes instantiate `EmojiLibrary(tmp_path / "emoji_library_default.json")` using pytest's `tmp_path` fixture with a copy of the real file.

### PySide6 test architecture

`TestEmojiLibrary` is headless — no Qt dependency, no `QApplication` needed.

`TestGuidancePanel` and `TestEmojiFlyout` require a `QApplication` instance. A session-scoped `qapp` fixture in `tests/conftest.py` provides this without adding any new runtime dependency (PySide6 is already a project dependency).

No `pytest-qt` package is required.

### Write-through test isolation

Tests that call `EmojiLibrary.add_entry`, `EmojiLibrary.remove_entry`, or `EmojiLibrary.set_active_alias` must operate on a temporary copy of the library file. They must never write to `assets/emoji_library_default.json` during a test run. Use `shutil.copy` in the test setup to create a `tmp_path` copy.
