# WebUI

The WebUI is a local ComfyUI-style editor for audio processing graphs. It uses a static browser frontend, a FastAPI backend, and a single-worker executor for `python-audio-separator` jobs.

## Run

```bat
run-webui.bat
```

Open:

```text
http://127.0.0.1:8188/
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
| `input_file` | none | `audio` | `path` |
| `input_folder` | none | `audio` | `path`, `recursive`, `extensions` |
| `separator` | `audio` | model stems | `model_filename`, `options` |
| `output_folder` | `audio` | none | `path`, `naming_template`, `format`, `conflict` |

Model stem names are execution handles. Preserve the exact registry value, including spaces and capitalization. Translate or format visible labels only; never normalize a handle independently in the frontend.

Edges store:

- `source` and `target` node IDs
- `source_handle` and `target_handle`
- a stable edge `id` used by structured validation

Legacy editor node names such as `file_input`, `folder_input`, `model`, and `output` are normalized by `app/web/schemas.py`.

## Editor Behavior

- Drag a library item to the canvas or double-click it to add a node.
- Click a node to open its properties.
- On narrow viewports, properties use a right-side drawer instead of disappearing.
- Text and number fields commit on blur or Enter. An active field is flushed before the inspector is rebuilt or the graph is replaced.
- Path values are trimmed. An explicitly empty path remains empty and does not fall back to stale loaded data.
- Connect ports by dragging in either direction. Dragging from an occupied input reconnects it.
- Clicking two compatible ports is retained as a fallback.
- Pointer state is cleared on pointer up, cancellation, lost capture, window blur, node deletion, workflow load, new workflow, undo, and redo.
- Canvas panning disables browser text selection and uses pointer capture.
- Validation errors are mapped back to node and edge IDs and highlighted on the graph.
- The Workflows dialog lists server-saved workflows and supports open, delete, save as, JSON import, and JSON export.
- Save writes the current workflow to the local service. Export is a separate action and does not change saved state.
- On mobile-width viewports, the node library becomes a left drawer so the canvas keeps the full viewport width.

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

Models without confirmed output stems remain visible as needing confirmation but cannot pass run validation. The current UI does not yet provide a metadata-confirmation editor.

## Native Path Picker

The frontend calls:

```http
POST /api/dialog/pick
```

Kinds:

- `audio_file`
- `input_directory`
- `output_directory`

The endpoint is restricted to loopback clients. On Windows it launches `app.web.dialog_worker` with the existing PySide6 environment so the Qt dialog owns its GUI main thread. Dialog requests are globally serialized; a second concurrent request receives `409 dialog_busy`.

The request includes the active WebUI locale, so dialog titles support Simplified Chinese, Japanese, and English. Audio selection is limited to extensions in `app/web/formats.py`.

The path picker is intentionally unavailable to remote clients. Remote deployments must enter server-local paths manually or provide a different path-browsing service.

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
- required paths and basic local path type
- supported input audio extensions
- installed and known separator models
- confirmed separator output handles
- input/output port contracts
- forbidden incoming or outgoing edges
- required separator and output inputs
- graph cycles

Runs are submitted to a `RunManager` with one worker. This prevents concurrent model jobs from competing for the GPU. Events are exposed through server-sent events at `/api/runs/{run_id}/events`.

Execution stages:

1. Read a single audio file or recursively scan an input folder.
2. Execute separator nodes through `python-audio-separator`.
3. Route artifacts by exact output stem handle.
4. Copy or convert files into output folders.

Output templates may use:

- `{relative_dir}`
- `{basename}`
- `{stem}`
- `{ext}`
- `{model}`
- `{node}`

Conflict modes are `rename`, `overwrite`, and `skip`. Output paths are checked so naming templates cannot escape the selected output root.

Cancellation is cooperative. It is checked between files and nodes; an active model call may need to finish before cancellation takes effect.
The frontend keeps the run in a cancelling state until the server reports a terminal cancellation event.

The Runs dialog shows the current single-worker queue and completed runs from the current server session. Active run IDs are retained in browser storage, allowing a page reload to reconnect to the run event stream. Any active run can also be selected from the run list for tracking or cancellation.

## Persistence

Browser-local state:

- `audioflow:autosave`: current workflow payload
- `audioflow:autosave-dirty`: whether the browser draft differs from its last server save
- `audioflow:model-cache`: last visible model list
- `audioflow:locale`: locale preference
- `audioflow:active-run-id`: run to reconnect after a page reload

Server-local state:

- `user_data/model_registry.json`: model metadata cache
- `user_data/web_workflows.json`: saved workflows
- `user_data/web_runs/<run-id>/`: intermediate run output

The Workflows dialog uses the server CRUD API for normal persistence. JSON import and export remain available as explicit portability actions. The browser autosave stores only the active draft; it does not replace the server workflow list.

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
| `POST` | `/api/dialog/pick` | local native path picker |
| `GET/POST` | `/api/workflows` | list or create workflows |
| `GET/PUT/DELETE` | `/api/workflows/{id}` | workflow CRUD |
| `POST` | `/api/workflows/validate` | structured pre-run validation |
| `POST` | `/api/runs` | queue a workflow |
| `GET` | `/api/runs` | list current-session runs and queue positions |
| `GET/DELETE` | `/api/runs/{id}` | inspect or cancel a run |
| `GET` | `/api/runs/{id}/events` | SSE run events |

## Current Limitations

- Models with uncertain function or outputs need an explicit metadata editor.
- The executor visits every node in topological order; it does not yet prune nodes that cannot reach an output.
- Run history survives browser reloads but remains in memory and is not restored after a server restart.
- Advanced separator parameters are present in the backend but only a small subset is exposed in the inspector.
- Multi-select, copy/paste, groups, comments, and reusable subgraphs are not implemented.

## Verification

```bat
env\python.exe -m unittest discover -s app\web\tests -v
env\python.exe -m unittest discover -s tests -v
node --check app\web\static\app.js
git diff --check
```

For a Windows picker smoke test, start the WebUI from the project environment, click Browse, select or cancel a local file/folder, and confirm that the UI leaves the button enabled and reports the result.
