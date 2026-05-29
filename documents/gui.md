# GUI

The GUI uses PySide6 and lives under `app/gui`.

Current structure:

```text
app/gui/
  __main__.py
  application.py
  bootstrap.py
  icons.py
  main_window.py
  paths.py
  style.py
  assets/
    icons/
  i18n/
  views/
  widgets/
```

Design direction:

- WinUI-like shell with a left navigation rail and a right content area.
- Navigation items include Home, Separate, Slicer, Train, Inference, Settings, and About.
- The navigation rail supports expanded `icon + text` mode and collapsed `icon only` mode.
- Navigation icons are local SVG assets under `app/gui/assets/icons`.
- Navigation icons use a small rotation animation on hover and selection.
- The visual style uses a blurred full-window background layer over `sample/76371065_p0.png`.
- The background is dark-tinted before the card panels are drawn so text remains readable.
- Navigation, content, language controls, and settings controls are translucent dark glass panels.
- The Settings page currently supports changing the background image, blur radius, and text color for live preview.
- The Separate page uses card-based modules. Presets appear first, common model settings second, and pipeline model cards below.
- Separate model cards can be reordered; card order is the execution order.
- The Slicer page is implemented as two glass cards: input/output controls and slicing settings.
- Slicing runs in a background thread so the GUI stays responsive while audio files are processed.
- The Tools page uses a top function selector and switches the cards below it between audio quality, total duration, and pitch analysis.
- Tools workflows run outside the GUI layer under `app/tools`; long-running work uses background threads.
- The Settings page uses glass cards grouped by background effects and color/tint controls.
- The first GUI version is growing page by page; Train and Inference remain placeholders.

Internationalization:

- Language is resolved from the system locale.
- Supported languages are Simplified Chinese, English, and Japanese.
- If locale detection fails or the language is unsupported, English is used.
- Translation strings are currently plain Python dictionaries in `app/gui/i18n/translations.py`.
- A language selector lives at the lower-left of the navigation rail and updates visible text immediately.

Run the GUI:

```bat
run-gui.bat
```

Or directly:

```bat
env\python.exe -m app.gui
```

Environment setup:

- `run-install.bat` only manages the project-local `env`.
- If `env/python.exe` exists, the installer reuses it.
- If `env/python.exe` is missing, the installer downloads Miniconda into `env/conda` and creates `env`.
- The installer checks whether PySide6 is usable inside the local `env`.
- If PySide6 is missing or Qt cannot import, the installer tries conda-forge first.
- If conda installation fails, it falls back to pip.
- PySide6 is pinned to `6.8.1`, matching the sample project under `sample/pyside6-getting-started`.

Recommended growth path:

- Keep each page under `app/gui/views`.
- Keep reusable controls under `app/gui/widgets`.
- Use background worker classes for long tasks so separation, slicing, training, and inference do not freeze the UI.
- Keep actual audio processing in the workflow modules.
