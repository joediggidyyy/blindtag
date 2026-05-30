# BlindTag Widget Schema

**Status**: Proposed — locked for implementation (Pass D)
**Precondition**: Pass C complete (`e134dab`); all 25 CLI tests passing; calamum go/pass
**Execution authority**: This document is the design contract. An implementation checklist will be created before Pass D begins.
**Scope**: Two surfaces — in-product guidance panel and emoji alias selector (with library editor)

---

## Design principles (widget-specific)

These extend the core Polymath visual precedents already established in `widget.py`:

1. **Locked baseline** — the existing title bar / toggle strip / panel stack / status bar layout is immutable. New surfaces extend it; they do not restructure it.
2. **Left-side slide-out for guidance** — the `?` help trigger opens a slide-out from the left edge, keeping the right-side encode/decode panel fully visible.
3. **Collapsed cards, in-card caret** — help cards are collapsed by default; only entries with meaningful deeper content expose an expand caret. Expanding happens vertically in place.
4. **No control-bar intrusions** — the emoji selector is a floating `QFrame` flyout anchored to a small inline trigger; it is not a dialog, modal, dropdown bar, or boxed control cluster.
5. **Alias transparency** — the payload constraint (printable ASCII only) means emojis must be represented as ASCII alias strings. The UI makes this visible to the user without jargon: the flyout shows the emoji and the alias it will insert.
6. **Library persistence is local** — `assets/emoji_library.json` is a user-local file, `.gitignore`d from default commits, seeded from a shipped default if absent.

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
- Expanded body: a `QLabel` with `wordWrap=True`, `C_MUTED` color, `9pt` font

Cards with shallow content (one or two words of explanation) do **not** have a caret — they display inline as static label rows. Cards with meaningful guidance (3+ sentences or actionable steps) use the expand caret.

### Card content

| Card | Caret | Expanded guidance |
|------|-------|-------------------|
| **Anchor text** | ✓ | The visible text your payload will be hidden inside. Any readable string works. The receiver sees only this text unless they decode it. |
| **Hidden payload** | ✓ | The secret message to embed. Must be printable characters (letters, numbers, punctuation, spaces). Max ~9,000 characters. Emojis must be inserted as aliases — use the emoji button next to this field. |
| **Emoji aliases** | ✓ | Emojis cannot be embedded directly (they are not printable ASCII). The emoji selector inserts a short alias like `:smile:` instead. The receiver decodes and sees the alias text. You can edit the library to add your own. |
| **Obfuscate & Copy** | ✓ | Runs encode and immediately copies the result to your clipboard. The output looks identical to your anchor text — the payload is invisible. |
| **Clip Watch** | ✓ | Monitors your clipboard. When you copy text that contains a hidden payload, BlindTag automatically detects and shows it. No data leaves your machine. |

---

## Surface 2 — Emoji alias selector

### Trigger placement

In `_build_encode_panel()`, the `HIDDEN PAYLOAD` section label row gains an inline emoji trigger button on the right side of the label row:

```
HIDDEN PAYLOAD  ·  printable ASCII only          ☺
```

The `☺` button (`26×26`, `_btn_ghost_style()`) opens the flyout. It is anchored to the button position so the flyout appears just below the label row, left-aligned with the payload textbox.

### Flyout layout

```
┌─────────────────────────────────────────┐
│  😀  :smile:    😂  :lol:    ❤️  :heart:  │
│  👍  :thumbsup: 👎  :thumbsdown: 🔥 :fire:│
│  ...                                    │
│  ─────────────────────────────────────  │
│  Edit library                       ⚙  │
└─────────────────────────────────────────┘
```

- The flyout is a `QFrame` with `StyledPanel` shape, not a separate window
- Width: `300px`, height auto-expands to fit library contents (max `220px`, scrollable)
- Background: `C_SURFACE` (`#252525`), border `1px solid #303030`
- Each entry shows the emoji glyph + alias string side by side
- Clicking an entry **appends** the alias string to `_hidden_input` and closes the flyout
- The flyout dismisses on click-outside (mouse press event filter on the parent window) or on `Escape`
- `Edit library` link at the bottom opens the library editor panel

### Grid layout

Entries are laid out in a `QGridLayout`, 3 columns. Each cell is a `QPushButton` with transparent background:

```
[emoji  alias ]  [emoji  alias ]  [emoji  alias ]
```

Button style: `_btn_ghost_style()` with `font-size: 10pt`, `text-align: left`, `padding: 4px 8px`.

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
│  😀  :smile:        thumbs up    [✕]     │
│  😂  :lol:          laughing     [✕]     │
│  ❤️  :heart:        heart        [✕]     │
│  ...                                     │
│  ─────────────────────────────────────   │
│  + Add entry                             │
│    Emoji: [____]  Alias: [_________]     │
│    Label: [________________]   [Add]     │
└──────────────────────────────────────────┘
```

- `← Back` ghost button navigates to the previously active encode/decode panel
- Each row: emoji display (non-editable label), alias string, label text, delete `✕` button
- Delete requires no confirmation dialog — it takes immediate effect and updates the JSON file
- **Add entry form** at the bottom: three fields + `Add` button. Inline validation: alias must be non-empty printable ASCII only; shows red border if invalid. No modal.
- All changes write through to `assets/emoji_library.json` immediately on each action (not on a Save button)

---

## Persistence — `assets/emoji_library.json`

### Format

```json
[
  { "emoji": "😀", "alias": ":smile:",      "label": "smile"       },
  { "emoji": "😂", "alias": ":lol:",        "label": "laughing"    },
  { "emoji": "❤️", "alias": ":heart:",      "label": "heart"       },
  { "emoji": "👍", "alias": ":thumbsup:",   "label": "thumbs up"   },
  { "emoji": "👎", "alias": ":thumbsdown:", "label": "thumbs down" },
  { "emoji": "🔥", "alias": ":fire:",       "label": "fire"        },
  { "emoji": "⭐", "alias": ":star:",       "label": "star"        },
  { "emoji": "✅", "alias": ":check:",      "label": "check"       },
  { "emoji": "❌", "alias": ":x:",          "label": "x"           },
  { "emoji": "⚠️", "alias": ":warn:",       "label": "warning"     },
  { "emoji": "🔒", "alias": ":lock:",       "label": "lock"        },
  { "emoji": "🔓", "alias": ":unlock:",     "label": "unlock"      },
  { "emoji": "📎", "alias": ":clip:",       "label": "clip"        },
  { "emoji": "📋", "alias": ":paste:",      "label": "paste"       },
  { "emoji": "🗑️", "alias": ":trash:",      "label": "trash"       },
  { "emoji": "💬", "alias": ":msg:",        "label": "message"     },
  { "emoji": "📌", "alias": ":pin:",        "label": "pin"         },
  { "emoji": "🏷️", "alias": ":tag:",        "label": "tag"         },
  { "emoji": "🔑", "alias": ":key:",        "label": "key"         },
  { "emoji": "👁️", "alias": ":eye:",        "label": "eye"         }
]
```

### Load behavior

At `BlindTagWindow.__init__`, load `assets/emoji_library.json`. If the file is absent, seed from a shipped read-only default (`assets/emoji_library_default.json`) by copying it into place. If the JSON is malformed, fall back to the default and log a warning to the status bar.

### Validation rule

On Add entry: `alias` must match `^[ -~]+$` (printable ASCII 0x20–0x7E). Reject silently with a red border; no modal or dialog.

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
| `assets/emoji_library_default.json` | Data | Shipped default 20-entry library; read-only reference |
| `assets/emoji_library.json` | Data | User-local working library; `.gitignore`d |
| `blindtag/widget.py` | Modified | `_GuidancePanel`, `_EmojiCard`, `_EmojiFlyout`, `_LibraryEditorPanel` classes; `?` button in `_TitleBar`; emoji trigger in `_build_encode_panel()` |

No new Python modules. All new UI classes live in `widget.py`.

---

## Calamum / test surface

| Test class | Scope |
|------------|-------|
| `TestEmojiLibrary` (in `tests/test_widget.py`) | Load default, add/remove/validate entry, alias ASCII constraint |
| `TestGuidancePanel` (in `tests/test_widget.py`) | Panel opens/closes, card count matches schema, card text not empty |

These are part of the `tests/test_widget.py` work already in Planned. The emoji/guidance implementation should ship as part of the same pass that delivers `test_widget.py`.
