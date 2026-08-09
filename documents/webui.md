# WebUI

The WebUI is a local ComfyUI-style editor for audio processing graphs. It uses a static browser frontend, a FastAPI backend, and a single-worker executor for separation, slicing, peak-normalization, and output jobs.

## Run

```bat
run-webui.bat
```

Open:

```text
http://127.0.0.1:7657/
```

`run-webui.bat` always uses `env/python.exe`. Additional Uvicorn arguments are forwarded, for example:

```bat
run-webui.bat --port 8000
```

## Structure

```text
app/web/
  __main__.py          Uvicorn launcher
  main.py              FastAPI routes and static frontend
  schemas.py           Pydantic workflow contracts
  model_registry.py    model scan, classification, and cached metadata
  workflows.py         workflow persistence and validation
  executor.py          queued graph execution
  uploads.py           content-addressed browser audio uploads
  dialogs.py           loopback-only path-picker service
  dialog_worker.py     Windows Qt file/folder picker subprocess
  formats.py           supported audio extensions
  static/
    index.html         WebUI shell
    app.js             graph editor and API client
    styles.css         layout and graph styling
    i18n/              locale runtime and dictionaries
  tests/               WebUI unit tests
```

The frontend is deliberately dependency-free JavaScript. It is served directly by FastAPI; there is no frontend build step.

## Node Contract

Supported node types:

| Type | Input handles | Output handles | Important data |
| --- | --- | --- | --- |
| `input_file` | none | `audio` | `upload_id`, `upload_name`, or legacy `path` |
| `input_folder` | none | `audio` | `path`, `recursive`, `extensions` |
| `separator` | `audio` | model stems | `model_filename`, `options` |
| `slicer` | `audio` | `audio` | `threshold`, `min_length`, `min_interval`, `hop_size`, `max_sil_kept`, `output_format` |
| `peak_normalize` | `audio` | `audio` | `target_peak_db` |
| `output_folder` | `audio` | none | `path`, `mode`, `naming_template`, `format`, `conflict` |

Model stem names are execution handles. Preserve the exact registry value, including spaces and capitalization. Translate or format visible labels only; never normalize a handle independently in the frontend.

Edges store:

- `source` and `target` node IDs
- `source_handle` and `target_handle`
- a stable edge `id` used by structured validation

Legacy editor node names such as `file_input`, `folder_input`, `model`, and `output` are normalized by `app/web/schemas.py`.

## Editor Behavior

- Drag a library item to the canvas, double-click it, or focus it and press Enter/Space to add a node.
- Drag any non-interactive part of a node to move it. Click without moving to select it and open its properties.
- The node library uses compact two-line rows. Primary labels are 14 px, secondary metadata is 11 px, and drag affordances appear on hover or keyboard focus.
- Library sections are `Input`, `Audio preparation`, `Separation`, `Cleanup`, `Other`, and `Output`. Separator models have a second level for vocal/instrumental separation, multi-stem separation, denoise, dereverb/de-echo, vocal cleanup, or unclassified models.
- Architecture is a filter and metadata value, not a task category. Model installation and output-confirmation state are also independent of the category tree.
- Hover or focus a model row to see its complete display name, filename, function, architecture, output stems, metadata source, and confidence. The selected model node repeats durable model details in the properties panel.
- Canvas model nodes keep only their title, function, and ports. Filename, architecture, and metadata are intentionally deferred to the model preview and properties panel.
- The node-library title, search and architecture filter, and model-count footer stay fixed within the sidebar. Only the grouped node list scrolls when its contents exceed the viewport height.
- The node library and properties panel use mirrored controls at the left and right canvas edges. Collapsing a panel keeps its control attached to the corresponding edge so it can be reopened in place.
- On desktop viewports, both sidebars can be resized by dragging their separators. Focused separators also accept the arrow keys in 10 px steps, Shift+arrow in 30 px steps, and Home/End for the allowed minimum/maximum width.
- The preferred sidebar widths are 320 px for the node library and 360 px for properties. Widths are clamped to preserve a usable canvas and restored from browser-local storage; the node library allows 220-520 px and properties allows 260-520 px before viewport constraints are applied.
- At 800 px or narrower, properties becomes a right-side overlay drawer and starts collapsed. At 650 px or narrower, the node library also becomes a left-side overlay drawer and starts collapsed, leaving the full-width canvas behind both drawers.
- Drawer panel headers retain their own collapse controls because an open drawer covers the corresponding canvas-edge control. Sidebar visibility itself is derived from the current viewport when the page loads and is not persisted.
- Text and number fields commit on blur or Enter. An active field is flushed before the inspector is rebuilt or the graph is replaced.
- Path values are trimmed. An explicitly empty path remains empty and does not fall back to stale loaded data.
- Connect ports by dragging in either direction. Dragging from an occupied input reconnects it.
- Clicking two compatible ports is retained as a fallback.
- Ordinary input ports accept one connection. An Output folder in `smart_classification` mode accepts multiple connections on its `audio` input.
- Drag the visible handle at a node's lower-right corner to resize its width and height. A focused handle accepts the arrow keys in 10 px steps and Shift+arrow in 30 px steps.
- Single-file nodes show the selected filename in their Source summary. Output nodes show both their format and destination folder; the complete path remains available in Properties and as hover text.
- Selecting a node shows a compact viewport-positioned toolbar above or below it. Duplicate copies settings and size to a new offset node without copying edges. Delete opens an anchored confirmation; Cancel, Escape, or clicking elsewhere dismisses it.
- Properties exposes the display name and workflow parameters, but not raw X/Y coordinates; node position remains controlled by canvas dragging.
- Pointer state is cleared on pointer up, cancellation, lost capture, window blur, node deletion, workflow load, new workflow, undo, and redo.
- Canvas panning disables browser text selection and uses pointer capture.
- Validation errors are mapped back to node and edge IDs and highlighted on the graph.
- Open workflows use a tab bar. Each tab retains its own graph, undo history, dirty state, and canvas transform while another tab is active.
- Unsaved and modified tabs keep independent browser drafts. Reload restores the session tab order; without a tab session, all retained drafts are reopened with the most recent active. The previous single-workflow autosave is imported once when no newer draft can be restored.
- The Workflows dialog lists server-saved workflows and supports open, delete, save as, JSON import, and JSON export.
- Save writes the current workflow to the local service. Export is a separate action and does not change saved state.
- Server saves use a revision number. Updating a stale revision returns `409`; reopen the server copy or use Save as to keep both versions.

## Model Registry and Refresh

The model registry is stored at:

```text
user_data/model_registry.json
```

Startup behavior:

1. Return the saved registry immediately so first paint is not blocked.
2. Start a local-only model scan in a background thread.
3. Do not download or load checkpoints into GPU memory during the scan.

The refresh menu exposes:

- local scan: reads installed model files and local metadata
- catalog sync: manually updates the downloadable model catalog over the network

Metadata sources include the bundled `python-audio-separator` catalog and scores, cached catalog data, model filenames, and compatible YAML files. Registry entries include architecture, backend, function, outputs, confidence, metadata source, installation state, and `needs_confirmation`.

`function` and `needs_confirmation` describe different dimensions:

- `function` controls task grouping. A model with confirmed outputs but no recognized task stays usable under `Other` / `Unclassified`.
- `needs_confirmation` means the registry has no confirmed output stems. The model remains visible with a warning, but the library disables drag, double-click, and keyboard insertion because such a node cannot pass workflow validation.

The current UI does not yet provide a metadata-confirmation editor. Confirmation must come from compatible YAML or catalog/score metadata discovered during a registry refresh.

## Browser Audio Upload and Native Folder Picker

Single audio nodes use the browser's file input. The selected bytes are sent as the raw request body to:

```http
POST /api/uploads/audio?filename=<browser-filename>
```

`AudioUploadStore` validates the extension, hashes the content with SHA-256, writes atomically, and reuses an existing object with the same hash and extension. Files live under `user_data/web_uploads`; workflows store the opaque `upload_id` plus the original `upload_name`. Validation and execution resolve only IDs owned by that store. Existing workflows with a server-local `path` remain supported, but the current Single audio inspector does not expose a server filesystem picker.

Input and output folder fields call `POST /api/dialog/pick` with `input_directory` or `output_directory`. The endpoint is restricted to loopback clients. On Windows it launches `app.web.dialog_worker` with the existing PySide6 environment so the Qt dialog owns its GUI main thread. Dialog requests are globally serialized; a second concurrent request receives `409 dialog_busy`. The request carries the active locale so dialog titles support Simplified Chinese, Japanese, and English.

The dialog contract still accepts `audio_file` for compatibility with existing API callers, but the browser frontend no longer uses it. Native path picking is unavailable to remote clients; browser audio upload remains available wherever the WebUI itself is reachable.

## Validation and Execution

`POST /api/workflows/validate` returns:

```json
{
  "valid": false,
  "errors": [],
  "global_errors": [],
  "node_errors": {},
  "edge_errors": {}
}
```

Validation checks:

- unique node and edge IDs
- required input and output nodes
- required paths or owned upload references and basic local path type
- supported input audio extensions
- installed and known separator models
- confirmed separator output handles
- input/output port contracts
- one incoming edge per ordinary input port; multiple edges only for Smart classification output
- forbidden incoming or outgoing edges
- required separator and output inputs
- separator-derived provenance for Smart classification inputs
- valid slicer timing relationships and output format
- peak-normalization targets between `-60` and `0 dB`
- graph cycles

Runs are submitted to a `RunManager` with one worker. This prevents concurrent model jobs from competing for the GPU. Before execution, the manager keeps only nodes that can reach an Output folder; disconnected model branches are not loaded or run. The frontend keeps one global server-sent event connection at `/api/events/runs`; `/api/runs/{run_id}/events` remains available for a single-run consumer. Both streams support `Last-Event-ID` resume semantics.

Execution stages:

1. Resolve an uploaded or legacy local single audio file, or recursively scan an input folder.
2. Execute separator nodes through `python-audio-separator`.
3. Slice audio nodes into one or more clips under the run's intermediate directory.
4. Peak-normalize audio nodes with `ffmpeg-normalize` while preserving artifact metadata.
5. Route artifacts by exact output stem handle.
6. Copy or convert files into output folders.

Output templates may use:

- `{relative_dir}`
- `{basename}`
- `{stem}`
- `{ext}`
- `{model}`
- `{node}`

Conflict modes are `rename`, `overwrite`, and `skip`. Output paths are checked so naming templates cannot escape the selected output root.

An Output folder with `mode: smart_classification` ignores the naming template and accepts multiple separator-derived inputs. It writes each artifact to `<safe-model>_<safe-stem>/<original-relative-directory>/<basename>.<ext>`. The exact separator stem is preserved as metadata until filesystem-invalid characters and spaces are made path-safe. The selected conflict mode still controls same-name files.

Cancellation is cooperative. It is checked between files and nodes; an active model, slicing, or normalization operation may need to finish before cancellation takes effect.
The frontend keeps the run in a cancelling state until the server reports a terminal cancellation event.

The Runs dialog shows the current single-worker queue and persisted run history. Each submitted run retains an immutable workflow snapshot. On reload, the frontend reconciles the active workflow tab with the server run snapshot and keeps receiving global run events; it does not depend on a browser-stored active run ID. Background workflow tabs show their run state, and any active run can be selected from the run list for tracking or cancellation.

## Persistence

Browser-local state:

- `audioflow:draft-v2:<workflow-id>`: one recoverable draft per unsaved or modified workflow
- `audioflow:draft-index-v2`: draft recency index, capped at 20 entries
- `audioflow:workflow-tabs-v2` in session storage: open tab order and active tab
- `audioflow:sidebar-layout-v1`: last user-adjusted widths for the node library and properties panel; expanded/collapsed state is not stored
- `audioflow:model-cache`: last visible model list
- `audioflow:locale`: locale preference

The legacy `audioflow:autosave` and `audioflow:autosave-dirty` values are read only for one-time migration.

Server-local state:

- `user_data/model_registry.json`: model metadata cache
- `user_data/web_uploads/<sha256>.<ext>`: content-addressed browser audio uploads
- `user_data/workflows/<workflow-hash>.json`: one revisioned file per saved workflow
- `user_data/web_runs/<run-id>/run.json`: persisted run status and event history
- `user_data/web_runs/<run-id>/workflow.json`: immutable submitted workflow snapshot
- `user_data/web_runs/<run-id>/<node-id>/`: intermediate separator output

Optional node `data.width` and `data.height` values persist user-resized cards through drafts, JSON import/export, and server saves. Older workflows without these values keep the default 224 px width and content-driven height.

Existing `user_data/web_workflows.json` data is migrated into the workflow directory once. The legacy file is retained, and `user_data/workflows/.legacy-migrated` prevents deleted workflows from being imported again.

The Workflows dialog uses the server CRUD API for normal persistence. JSON import and export remain explicit portability actions. Browser drafts recover editor state but do not replace server workflow storage.

## Internationalization

Supported locales:

- `zh-CN`
- `ja`
- `en`

The default preference follows `navigator.languages`. A top-bar selector can override it and stores the preference locally. Locale changes re-render static text, the node library, graph cards, inspector, validation UI, and run controls.

Do not translate user workflow names, custom node titles, filesystem paths, model names, architecture names, or stem handles.

## API Summary

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/health` | service health |
| `GET` | `/api/models` | model snapshot and filters |
| `POST` | `/api/models/refresh` | local scan or catalog refresh |
| `POST` | `/api/uploads/audio` | store a browser-selected audio file |
| `POST` | `/api/dialog/pick` | local native path picker |
| `GET/POST` | `/api/workflows` | list or create workflows |
| `GET/PUT/DELETE` | `/api/workflows/{id}` | workflow CRUD |
| `POST` | `/api/workflows/validate` | structured pre-run validation |
| `POST` | `/api/runs` | queue a workflow |
| `GET` | `/api/runs` | list persisted runs plus active/history snapshots |
| `GET/DELETE` | `/api/runs/{id}` | inspect or cancel a run |
| `GET` | `/api/runs/{id}/events` | SSE run events |
| `GET` | `/api/events/runs` | global SSE events for all runs |

## Current Limitations

- Models with an uncertain function remain in `Other` / `Unclassified`; models without confirmed output stems still need an explicit metadata editor.
- Advanced separator parameters are present in the backend but only a small subset is exposed in the inspector.
- Multi-select, clipboard copy/paste, groups, comments, and reusable subgraphs are not implemented. Selected-node duplication is available from the floating toolbar.

## Verification

```bat
env\python.exe -m unittest discover -s app\web\tests -v
env\python.exe -m unittest discover -s tests -v
node --check app\web\static\app.js
git diff --check
```

For an input smoke test, start the WebUI from the project environment, choose and upload a tiny temporary audio file in Single audio, then select or cancel an input/output folder with Browse. Confirm that each control returns to an enabled state and reports the result.
