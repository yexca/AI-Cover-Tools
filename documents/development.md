# Development

This project is growing page by page. Keep changes scoped to the module that owns the behavior.

## General Rules

- GUI code lives under `app/gui`.
- Audio processing lives under workflow modules.
- Shared small helpers live under `app/utils`.
- Do not put long-running work on the GUI thread.
- Use dataclasses for workflow results when the GUI needs structured output.
- Keep user data under `user_data`, not in source folders.

## GUI Page Pattern

Use this pattern for new implemented pages:

1. Create a page under `app/gui/views`.
2. Use a transparent `QScrollArea`.
3. Use `GlassCard` for functional card sections.
4. Put reusable controls under `app/gui/widgets`.
5. Implement `retranslate(translator)`.
6. Emit `status_changed` when long tasks start, finish, or fail.
7. Run long tasks with `QThread` or `QProcess`.
8. Keep the workflow function importable and testable without Qt.

When a page is inside `QStackedWidget`, fixed-height cards may need:

```python
card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
layout.addStretch(1)
```

This prevents one page's tall output from stretching another page's input card.

## Workflow Pattern

Workflow modules should expose small APIs:

```python
result = run_workflow(input_path, output_path, settings)
```

Return dataclasses instead of GUI strings.

The GUI should translate result dataclasses into visible messages.

## Verification Checklist

After code changes:

```bat
env\python.exe -m compileall app
```

For GUI page initialization:

```bat
set QT_QPA_PLATFORM=offscreen
env\python.exe -c "from PySide6.QtWidgets import QApplication; from app.gui.i18n.translator import Translator; from app.gui.main_window import MainWindow; app=QApplication([]); window=MainWindow(Translator('zh_CN')); print(window.windowTitle())"
```

For workflow changes, create a short temporary audio file and run the workflow directly through `env/python.exe`.

Clean temporary output after smoke tests.

## Git Hygiene

The repository may contain user or in-progress changes.

- Do not revert unrelated user changes.
- Stage only files related to the task.
- Use partial staging when a file contains unrelated user work.
- Do not commit generated outputs unless they are intentionally part of the project.
