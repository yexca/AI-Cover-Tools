# AI Cover Tools Agent Instructions

This file is the canonical repository contract for coding agents. It applies to the entire repository unless a more specific `AGENTS.md` exists below the directory being edited. User and platform instructions take precedence over this file.

`CLAUDE.md` is only a compatibility entry point. Keep substantive instructions here so all agents work from one maintained source.

## Guiding Principles (MUST FOLLOW)

### Think Before Editing

- Turn the request into a concrete, verifiable outcome before changing files.
- Inspect the current implementation, tests, documentation, and `git status` before deciding on a solution.
- State assumptions that affect behavior, data, dependencies, or architecture. Ask before proceeding only when a wrong assumption would be destructive or would materially change the requested result.
- Prefer evidence from this repository over guesses about libraries, model metadata, audio formats, or UI behavior.
- Fix a limitation at the layer that owns it. Do not hide an upstream contract problem with a downstream special case.

### Keep Changes Small and Intentional

- Implement only the requested behavior. Do not add speculative configuration, abstractions, compatibility layers, or unrelated cleanup.
- Every changed line must be explainable by the task.
- Match the surrounding style. Do not reformat or reorganize unrelated code.
- Remove code made unused by the current change, but leave pre-existing dead code alone unless its removal is requested.
- Reuse an existing helper or framework feature when it already expresses the required behavior clearly. Add a shared abstraction only when multiple real call sites need the same contract.

### Preserve Truthful Behavior

- Do not silently guess model outputs, path ownership, workflow compatibility, or successful processing.
- Keep validation, execution, persistence, and UI state consistent. A UI-only simulation of backend behavior is not a completed feature.
- Fail with actionable context at system boundaries. Do not swallow exceptions or convert failures into success states.
- Keep local-only and networked operations visibly distinct. A local model refresh must not start a download or catalog synchronization.

## Required Reading

Before editing, read:

1. This file in full.
2. [`documents/README.md`](documents/README.md) and the document for the subsystem being changed.
3. [`DESIGN.md`](DESIGN.md) for any user-facing desktop or WebUI work.
4. The nearest tests and entry points for the behavior being changed.

Useful subsystem references:

| Area | Required reference |
| --- | --- |
| Architecture or package ownership | [`documents/architecture.md`](documents/architecture.md) |
| Environment or dependencies | [`documents/environment.md`](documents/environment.md) |
| Configuration or persistent paths | [`documents/configuration.md`](documents/configuration.md) |
| Desktop GUI | [`documents/gui.md`](documents/gui.md) and [`DESIGN.md`](DESIGN.md) |
| Browser WebUI | [`documents/webui.md`](documents/webui.md) and [`DESIGN.md`](DESIGN.md) |
| Separation | [`documents/separate.md`](documents/separate.md) |
| Slicing | [`documents/slicer.md`](documents/slicer.md) |
| Audio utilities | [`documents/tools.md`](documents/tools.md) |
| Development and verification | [`documents/development.md`](documents/development.md) |

Developer documents describe the intended current behavior. Tests, schemas, and executable code show what is enforced. If they disagree, do not silently choose one: determine the intended contract, then update implementation and documentation together or report the discrepancy.

## Project Boundaries

AI Cover Tools is a Windows-first, local audio workflow application using Python 3.12. It has three user-facing entry surfaces:

- `main.py`: command-line separation workflow.
- `app/gui`: PySide6 desktop application.
- `app/web`: FastAPI service and plain HTML/CSS/JavaScript graph editor.

Code ownership is:

| Path | Owns | Must not own |
| --- | --- | --- |
| `app/gui` | Qt shell, pages, widgets, translations, worker wiring | Audio algorithms or WebUI contracts |
| `app/web` | HTTP/SSE API, graph schemas, validation, persistence, run orchestration, browser UI | Desktop widgets or guessed model metadata |
| `app/separate` | Separation preprocessing, models, runner, pipeline, archive handling | GUI presentation |
| `app/slicer` | Silence analysis and clip-writing workflow | GUI presentation |
| `app/tools` | Audio inspection and preparation utilities | GUI presentation |
| `app/train`, `app/inference` | Reserved workflow boundaries | Pretending placeholder features are implemented |
| `app/utils` | Small, deliberately shared primitives | Feature-specific orchestration or a generic dumping ground |
| `app/config` | Stable application defaults | User-generated state |
| `documents` | Current developer-facing behavior and architecture | Generated runtime records |

Dependency direction:

```text
CLI / desktop GUI -> workflow modules -> app.utils
WebUI API/executor -> WebUI contracts + selected workflow helpers/libraries
workflow modules -X-> GUI or WebUI presentation
```

Rules:

- Put new behavior in the existing owning package. A new top-level package or sideways dependency requires a clear architectural reason and an update to `documents/architecture.md`.
- Workflow APIs must remain importable and testable without starting Qt or FastAPI.
- Use `pathlib.Path` for concrete filesystem paths, dataclasses for in-process workflow results, Pydantic models for WebUI wire contracts, and JSON only for intentional persistent boundaries.
- Keep stage-specific third-party imports close to the stage that needs them, especially heavy or optional audio/model dependencies.
- Do not edit `sample/` as part of application work unless the task explicitly targets the vendored/reference project.

## Runtime Data and Destructive Operations

The following directories contain environments, user inputs, downloaded models, generated outputs, or persistent application state:

```text
env/  inputs/  models/  outputs/  archives/  user_data/  sample/
```

- Treat their existing contents as user-owned. Do not delete, rename, normalize, rewrite, or commit them unless the user explicitly requests that exact operation.
- Separation may clear `outputs/` before a real run. Agents must not run a non-dry-run pipeline against repository runtime paths merely as a smoke test.
- Use `tempfile.TemporaryDirectory`, injected roots/stores, fixture registries, and tiny generated audio fixtures for tests.
- Never use real user media or load full model checkpoints when a stub, metadata fixture, or short synthetic file verifies the contract.
- Preserve source audio. Derived files go to an explicit output or temporary directory.
- When adding or modifying persistent JSON writes that can be interrupted, make them atomic: write a sibling temporary file, flush/close it, then replace the target.
- Do not weaken workflow revision checks, immutable run snapshots, archive ownership, or loopback restrictions on the native path picker.
- Network access, model downloads, dependency installation, and online catalog synchronization must be explicit. Do not add them to import time or normal local refresh/startup paths.

## Implementation Conventions

### Python

- Target Python 3.12 and begin new modules with `from __future__ import annotations`.
- Type public functions, structured state, and non-obvious return values. Prefer built-in generics such as `list[str]` and unions such as `Path | None`.
- Prefer `Path` methods to ad-hoc string path manipulation. Preserve Unicode names and Windows path semantics.
- Use dataclasses for structured workflow results instead of tuples or presentation strings.
- Keep business logic independent of GUI labels. Presentation layers translate structured results into user-facing text.
- Use `logging` for workflow/service diagnostics; reserve `print` for CLI/launcher-facing output that is intentionally part of the command experience.
- Catch exceptions only where the layer can add context, clean up, translate them into a stable API response, or update UI state. Preserve the original exception as the cause when wrapping it.
- Invoke subprocesses with argument lists and controlled environments. Do not build shell command strings from user paths.
- Follow existing naming: `snake_case` modules/functions/variables, `PascalCase` classes, and leading underscores for private helpers.
- This repository currently has no mandatory formatter or linter configuration. Do not introduce one, or reformat the repository, as a side effect of another task.

### Configuration and Dependencies

- `app/config/defaults.py` defines defaults; root `config.py` is the user-facing CLI overlay.
- `user_data/gui_separate_config.py` is generated. Never edit or commit it by hand.
- Keep configuration keys backward compatible unless the task explicitly changes the contract. Update the loader, all callers, examples, and `documents/configuration.md` together.
- Use the project-local `env` interpreter. Do not install into system Python.
- A dependency change must account for every applicable installation surface: `requirements.txt`, `environment.yml`, `run-install.bat`, runtime availability checks, and documentation. Update only the surfaces that actually own that dependency and explain intentional differences.
- Avoid importing optional heavy dependencies at application startup when only one workflow stage needs them.

### Desktop GUI (PySide6)

- Call `configure_windows_dll_paths()` before importing PySide6 in modules that can be entry boundaries, following the existing bootstrap pattern.
- Keep the Qt event loop responsive. Audio processing, model work, filesystem scans, and subprocess waits belong in `QThread`, worker objects, or `QProcess` with clear completion, failure, and cancellation handling.
- A page inside the stack should use the established transparent `QScrollArea` + content widget + `GlassCard` pattern unless the design task intentionally changes that pattern.
- Put reusable controls in `app/gui/widgets`; keep page-specific composition in `app/gui/views`.
- Reuse object names and central QSS in `app/gui/style.py`. Do not accumulate page-local styles for an existing semantic component.
- Every user-visible string must be translated through `Translator`. Add the same key to `en`, `zh_CN`, and `ja`, and implement or update `retranslate()` for live language changes.
- Long-running pages must emit truthful status changes for start, success, cancellation, and failure.
- Avoid fixed heights for content that can grow with translation or results. When stacked pages influence one another, use the existing fixed-card size-policy pattern and a trailing stretch.
- Preserve frameless-window behavior, title-bar controls, minimum window size, and appearance preview wiring when changing the shell.

### WebUI (FastAPI + Plain JavaScript)

- Keep `app/web/schemas.py`, API payloads, validation, executor behavior, persisted workflow shape, frontend serialization, and tests synchronized.
- Raw model stem values are execution handles. Preserve exact case, whitespace, and spelling from registry through ports, edges, validation, and execution. Labels may be localized; handles may not.
- Model function, architecture, installation state, and output-confirmation state are independent dimensions. Do not encode one as another or guess unknown outputs.
- Saved workflow revisions are optimistic-concurrency contracts. Stale writes must continue to fail instead of overwriting newer state.
- `RunManager` is authoritative for queue, cancellation, history, and terminal state. The browser may render or reconcile that state but must not invent it.
- A run owns an immutable workflow snapshot and node-specific intermediate files. Execution must not switch to a newly edited browser graph mid-run.
- The native path-picker endpoint stays loopback-only and must retain stable cancel, busy, and error shapes.
- Escape untrusted strings before inserting HTML. Prefer `textContent`; use the existing `escapeHtml` path when building trusted templates.
- Preserve pointer interaction cleanup for `pointerup`, `pointercancel`, lost capture, window blur, workflow replacement, and node deletion. Test both directions of port connection when changing graph gestures.
- Maintain sidebar drawer behavior and all existing responsive modes. Do not fix desktop layout by breaking widths below 1050, 800, 650, or 480 pixels.
- The frontend intentionally has no bundler or framework. Do not introduce a framework, package manager, or build step without an explicit project-level decision.
- Dynamic user-visible strings use the WebUI i18n runtime. Keep `en.js`, `zh-CN.js`, and `ja.js` key sets identical, including ARIA labels, titles, empty states, validation, and status text.

## Design Contract

[`DESIGN.md`](DESIGN.md) is normative for user-facing styling and interaction.

- Reuse the existing component, token, spacing, and state vocabulary before adding a new one.
- Desktop and WebUI are related products but different surfaces; do not copy Qt glass styles into the graph editor or WebUI purple node styles into the desktop shell without an intentional redesign.
- Semantic colors communicate action or state. Do not use danger, warning, success, or node-type colors decoratively.
- A new shared visual token or reusable component pattern must be implemented at its owner and documented in `DESIGN.md` in the same change.
- Visual changes require checking focus, disabled, hover, selected, loading/running, error, long-text, and translated states as applicable.

## Testing and Verification

Choose checks in proportion to the change. Start with focused tests, then run all affected suites. Use the project-local interpreter:

```powershell
.\env\python.exe -m compileall -q app main.py
.\env\python.exe -m unittest discover -s app\web\tests -v
.\env\python.exe -m unittest discover -s tests -v
node --check .\app\web\static\app.js
git diff --check
```

Additional requirements:

- Bug fixes should add or update a regression test that fails for the old behavior when practical.
- WebUI contract changes require both WebUI unit tests and the integration suite.
- WebUI i18n or frontend changes require the i18n tests and `node --check`.
- Desktop page or shell changes require an offscreen initialization smoke test:

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
.\env\python.exe -c "from PySide6.QtWidgets import QApplication; from app.gui.i18n.translator import Translator; from app.gui.main_window import MainWindow; app=QApplication([]); window=MainWindow(Translator('zh_CN')); print(window.windowTitle())"
```

- Audio workflow changes require a targeted run with a tiny temporary audio fixture and temporary output roots. Never use repository `inputs/` or `outputs/` for an automated smoke test.
- Native path-picker changes require automated mocked coverage plus one real Windows select/cancel smoke test when the environment permits interaction.
- Documentation-only changes require at least link/path review and `git diff --check`; do not run expensive model or audio checks without a reason.
- If a required check cannot run, report the exact command and reason. Do not imply verification that did not happen.

## Documentation Rules

- Update the relevant developer document whenever a change alters architecture, ownership, configuration, persistence, an API, a workflow contract, or verification commands.
- Update all three root READMEs when user-facing capabilities, setup, or limitations change. Keep English, Simplified Chinese, and Japanese meaningfully aligned.
- Document current behavior, not planned behavior. Mark `train` and `inference` as placeholders until implemented end to end.
- Prefer links to the owning document over duplicating long rules. Keep `AGENTS.md` focused on how agents work and `DESIGN.md` focused on user-facing design.
- Examples must use safe placeholder paths and must not suggest deleting user data as a normal troubleshooting step.

## Git Hygiene

- Preserve unrelated user changes in a dirty worktree. Do not revert, overwrite, reformat, stage, or commit them.
- Do not stage, commit, push, change branches, or rewrite history unless the user asks.
- When a commit is requested, keep it focused and follow the repository's prevailing Conventional Commit style, for example `feat(webui): ...`, `fix(slicer): ...`, or `docs: ...`.
- Do not commit caches, environments, downloaded models, media, generated output, runtime state, or temporary smoke-test artifacts.
- Review `git diff --check`, the scoped diff, and `git status --short` before declaring completion.

## Definition of Done

A change is complete only when:

- the requested behavior is implemented at the owning layer;
- affected contracts remain consistent across callers and persistence boundaries;
- focused and affected verification passes, or limitations are reported exactly;
- relevant documentation and translations are current;
- runtime/user data and unrelated work remain untouched; and
- the final handoff lists changed files, verification performed, and any real remaining risk.
