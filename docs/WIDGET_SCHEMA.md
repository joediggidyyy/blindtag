# BlindTag Widget Schema

**Status**: Revised — Pass H design targets applied (format selector, anchor-only emoji insert, encode resolution pipeline)
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
| **Emoji format** | ✓ | The format selector (in the panel header) controls how a picked emoji is represented in the anchor text: `Glyph` inserts the raw emoji character (🗑️), `Unicode` inserts the codepoint notation (`U+1F5D1`), `Alias` inserts the short code (`:trash:`). All three produce valid anchor cover text. At encode time the widget resolves any format tokens to actual glyph characters before embedding the payload. |
| **Obfuscate & Copy** | ✓ | Runs encode and immediately copies the result to your clipboard. The output looks identical to your anchor text — the payload is invisible. |
| **Clip Watch** | ✓ | Monitors your clipboard. When you copy text that contains a hidden payload, BlindTag automatically detects and shows it. No data leaves your machine. |

---

## Surface 2 — Emoji selector + format selector

### Format selector

A compact format selector is added to the **toggle strip** on the right side, adjacent to the `Clip Watch` checkbox:

```
[Encode] [Decode]                  [Glyph ▾]  □ Clip Watch
```

The selector is a minimal `QPushButton` that cycles through three modes on click (or exposes a small popup). It is always visible when the encode panel is active.

| Mode | Label | Inserts into anchor | Example |
|------|-------|--------------------|---------|
| `Glyph` | `Glyph` | Raw emoji character | `🗑️` |
| `Unicode` | `Unicode` | Codepoint notation | `U+1F5D1` (multi-codepoint: `U+1F5D1 U+FE0F`) |
| `Alias` | `Alias` | Active alias from library | `:trash:` |

**Canonical Unicode format rule**: uppercase `U+XXXX`, minimum 4 hex digits, no padding beyond natural length (e.g. `U+1F5D1`, not `U+0001F5D1`). Separate codepoints with a single space.

**Default**: `Glyph`. State is ephemeral (in-memory per-session); resets to `Glyph` on restart.

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
- Clicking a cell performs a **single-field insert** into `_anchor_input` only:
  - `Glyph` mode → appends raw emoji character
  - `Unicode` mode → appends `U+XXXX` notation string
  - `Alias` mode → appends active alias string (e.g. `:trash:`)
  - **Nothing is written to `_hidden_input`** — the hidden payload field is untouched
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
│ [Encode] [Decode]    [Glyph ▾]  □ Clip  │
├──────────────────────────────────────────┤
│  ←  Emoji Library                        │
│  ─────────────────────────────────────   │
│  😀  🔵 U+1F600    smile       [✕]      │
│  😂  🔵 U+1F602    laughing    [✕]      │
│  ❤️  🔵 U+2764…    heart       [✕]      │
│  ...                                     │
│  ─────────────────────────────────────   │
│  + Add entry                             │
│  😊  label   [________________]  [Add]  │
└──────────────────────────────────────────┘
```

> **Row design**: Each row shows the glyph, a format-value column (dynamic — updates when the format selector changes), and the human label. The format-value column shows exactly what will be inserted into ANCHOR TEXT if the user picks that emoji from the flyout. This makes the library editor double as a format preview surface.

> **Format column header**: matches the active format selector label (`Unicode` / `Alias` / `Glyph`).

**Per-row columns:**

| Column | Content |
|--------|---------|
| Glyph | Emoji rendered at `18pt`; non-editable. |
| Format value | The representation that would be inserted into ANCHOR TEXT if this emoji is picked. Derives from the active format selector — updates live when the selector changes. `Glyph` mode shows the raw glyph (same as the first column), `Unicode` shows `U+XXXX` notation, `Alias` shows `:alias:`. Uses `C_MUTED` at `9pt`. |
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
| `alias` | string | The active code — used as the `Alias` format value when inserting into ANCHOR TEXT; must be a member of `codes` |
| `codes` | string[] | Full pick list of available codes for this emoji; each must match `^[ -~]+$` (printable ASCII) |
| `label` | string | Human-readable name; shown in editor only, never encoded |

### Load behavior

At `BlindTagWindow.__init__`, load `assets/emoji_library_default.json`. If the JSON is malformed, log a warning to the status bar and continue with an empty library (do not crash).

### Validation rule

On Add entry / Add code: every code must match `^[ -~]+$` (printable ASCII 0x20–0x7E). Reject with red border; no modal or dialog.

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
| `TestEmojiFlyout` (in `tests/test_widget.py`) | Flyout cell count matches library length; clicking cell inserts format-value into anchor field only (single-field insert); hidden payload field is not modified; Unicode mode inserts `U+XXXX` notation; Alias mode inserts alias string; Glyph mode inserts raw glyph |

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
