# BlindTag Widget Schema

**Status**: Revised — Pass G corrections applied (guidance readability + emoji insertion field + library editor row simplification + dual-input add form)
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
| **Hidden payload** | ✓ | The secret message to embed. Must be printable characters (letters, numbers, punctuation, spaces). Max ~9,000 characters. When you pick an emoji from the selector, its alias (e.g. `:smile:`) is automatically appended here alongside the glyph in the anchor text. |
| **Emoji aliases** | ✓ | Emojis cannot be embedded directly in the hidden payload (they are not printable ASCII). The emoji selector inserts the glyph into your visible anchor text and simultaneously appends the matching alias into the payload — so the receiver decodes the alias and knows which emoji was intended. You can edit the library to add your own. |
| **Obfuscate & Copy** | ✓ | Runs encode and immediately copies the result to your clipboard. The output looks identical to your anchor text — the payload is invisible. |
| **Clip Watch** | ✓ | Monitors your clipboard. When you copy text that contains a hidden payload, BlindTag automatically detects and shows it. No data leaves your machine. |

---

## Surface 2 — Emoji alias selector

### Trigger placement

In `_build_encode_panel()`, the `ANCHOR TEXT` section label row gains an inline emoji trigger button on the right side of the label row:

```
ANCHOR TEXT  ·  visible cover                    ☺
```

The `☺` button (`26×26`, `_btn_ghost_style()`) opens the flyout. It is anchored to the button position so the flyout appears just below the label row, left-aligned with the anchor textbox.

> **Trigger placement rationale**: The glyph is visible content — it belongs in the anchor text field. Placing the `☺` trigger on the ANCHOR TEXT row correctly signals that clicking picks something to embed in the visible text.

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
- Each cell shows **only the emoji glyph** — no alias text in the flyout
- Clicking a cell performs a **dual-field insert**:
  - Appends the emoji **glyph** to `_anchor_input` (anchor text, visible cover)
  - Appends the entry's active **alias** string to `_hidden_input` (hidden payload)
  - Then closes the flyout
- Dual insert rationale: the glyph is what the reader sees; the alias is what the decoder recovers. A single click wires both sides of the round-trip. The user does not need to make two separate field decisions.
- The flyout dismisses on click-outside (mouse press event filter on the parent window) or on `Escape`
- `Edit library` link at the bottom opens the library editor panel

### Grid layout

Entries are laid out in a `QGridLayout`, 6 columns. Each cell is a `QPushButton`:

```
[ 😀 ]  [ 😂 ]  [ ❤️ ]  [ 👍 ]  [ 👎 ]  [ 🔥 ]
```

Button style: `_btn_ghost_style()` with `font-size: 18pt`, `padding: 6px`, fixed `44×44` size. System font renders the glyph; no emoji library dependency required.

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
│ [Encode] [Decode]             □ Clip...  │
├──────────────────────────────────────────┤
│  ←  Emoji Library                        │
│  ─────────────────────────────────────   │
│  😀   smile       [✕]                   │
│  😂   laughing    [✕]                   │
│  ❤️   heart       [✕]                   │
│  ...                                     │
│  ─────────────────────────────────────   │
│  + Add entry                             │
│  😊  label   [________________]  [Add]  │
└──────────────────────────────────────────┘
```

> **Row design rationale**: The code/alias string is internal encoding plumbing — not part of the browse experience. Rows show only what the user cares about: the glyph and the human label. The active alias is exposed as a tooltip on the glyph for users who need to inspect the encoding value; it is not a separate column.

**Per-row columns:**

| Column | Content |
|--------|---------|
| Glyph | Emoji rendered at `18pt`; non-editable. Tooltip on hover shows the active alias (e.g. `:thumbsdown:`) for users who need to inspect the encoding value. |
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
| `alias` | string | The active code — this is what gets appended to `_hidden_input` (payload) on flyout click; must be a member of `codes` |
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
| `TestEmojiFlyout` (in `tests/test_widget.py`) | Flyout cell count matches library length; clicking cell appends glyph to anchor field AND active alias to payload field (dual-field insert) |

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
