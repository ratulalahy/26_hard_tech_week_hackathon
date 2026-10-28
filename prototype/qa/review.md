# Prototype verification and visual review

Scope: standalone Pilot Desk, source snapshot `739f411007a2` (full SHA in `../source-commit.txt`). Only files under `prototype/` are changed. No raw data, model execution, seal entry point, result updates, or new outcome estimates are involved.

## Evidence and offline checks

Commands run from the repository root:

- `python3 prototype/tools/build-data.py`: packages three committed outputs and committed fonts from the pinned revision. Rebuilding produces identical bundle bytes.
- `node --check prototype/app.js`: valid JavaScript.
- `npm --prefix prototype run check`: passes source SHA-256 checks, exact routing estimates and intervals, waiting comparator, storage outcomes, assumptions, and primary equality of completed work.
- Browser checks: all four content states at **1440×900**, **1728×1117**, and **390×844**, using `file://` with networking disabled; exact rendered headline values; no horizontal overflow; guided navigation, restart, arrows, modal and Escape; **zero external requests**, **zero browser errors**, and **zero axe WCAG A/AA violations** in content and modal states.
- Failure paths: missing bundle and a mutated bundle with the required saving field removed both produce the visible error state and hide the result. They do not fall back to a zero saving.
- `git diff --check`: no whitespace errors.

`test-report.json` is the machine summary. Screenshots are generated under this directory and ignored in Git. The tests disable axe's optional stylesheet preloading because axe's XMLHttpRequest preload is not permitted for a `file://` stylesheet; the browser loads the stylesheet normally, and axe inspects the rendered DOM and computed styles. No application errors are filtered out.

## Self-review findings and dispositions

| View / rubric | Severity / confidence | Evidence | Disposition |
|---|---|---|---|
| Routing / annotation layout | Major / high | Initial 94.5% annotation exceeded its 82 px column and touched the text at desktop and phone widths. | Fixed: 112 px desktop column, smaller percent glyph, stacked phone layout. Before screenshots preserved locally. |
| Routing / mark contrast | Minor / high | Initial neutral bars used `#9aa9a2` on near-white. | Fixed: darkened to `#71847a`; selected green, labels and interval marks remain distinct. |
| Storage / context at point of decision | Minor / high | Battery size and efficiency originally appeared only beneath the main panel. | Fixed: repeated beside the objective controls, visibly marked assumed. |
| Storage / hour alignment | Minor / high | Flex-distributed hour ticks were approximate relative to the 24 cells. | Fixed: ticks use the same 24-column grid as schedule cells. |
| Navigation / selector precision | Major / high | First browser run found scene selectors matching both the HTML state marker and the button. | Fixed: button selectors are explicit; all guided actions and arrow navigation tested. |

No open critical or major self-review findings. Bars start at zero; routing uncertainty stays visible; the two storage objectives use the same U baseline and disclose the different coverage window. Color is redundant with text, selected-button state, and charge/discharge symbols. Motion is limited to 250 ms bar changes and disabled with reduced-motion preference. Missing data has a visible error; synchronous local data has no remote loading dependency.

## Scope exceptions and remaining verification

- This is a **self-review**, not an independent review gate. The local review skill requires owner authorization for an additional paid Codex critic. No new paid reviewer was launched; a fresh-context Claude reviewer was not available through this session's agent tools. No independent-review verdict is claimed.
- Browser verification ran on Linux Chromium, not a physical MacBook. The artifact uses ordinary Chrome HTML/CSS/JS, local font files, and no runtime dependencies. A final open-on-the-presenter-laptop check remains advisable.
- Desktop views are fluid documents and may scroll at 900 px height; they are not fixed slides. All controls and qualifications remain reachable. Narrow-screen screenshots verify wrapping rather than a one-screen presentation.
- Review records stay under `prototype/qa/` to honor this task's requested output location instead of the repository-wide `docs/reviews/` convention. No remote PR or publication was created; the requested deliverable is a local branch commit.

Verdict: ready_with_minor_fixes

The verdict is the self-review's assessment; the only remaining check is physical MacBook presentation verification, not a known application defect.
