# GUI

The GUI uses PySide6 and lives under `app/gui`.

## Structure

```text
app/gui/
  application.py        QApplication and MainWindow startup
  bootstrap.py          Windows DLL path setup for local env
  icons.py              SVG icon loading helpers
  main_window.py        shell, navigation, stacked pages, background
  paths.py              project and asset paths
  style.py              global Qt stylesheet
  appearance.py         live appearance settings dataclass
  assets/icons/         navigation and window chrome SVGs
  i18n/                 translator and dictionaries
  storage/              GUI persistence helpers
  views/                page widgets
  widgets/              reusable controls and shell widgets
```

## Shell

The main window is a WinUI-like desktop shell:

- background image layer
- blur layer
- tint layer
- custom title bar when frameless window chrome is enabled
- left navigation rail
- right content panel with a `QStackedWidget`
- status bar for current task messages

The navigation rail includes:

- Home
- Separate
- Slicer
- Train
- Inference
- Tools
- Settings
- About

Home, Train, Inference, and About are currently placeholder pages.

## Implemented Pages

### Separate

Card layout:

- Presets
- Common settings
- Ordered model module cards

The page runs the CLI separation workflow with a generated config file under `user_data/gui_separate_config.py`. It uses `QProcess` so output can stream into the GUI and the run can be stopped.

### Slicer

Card layout:

- Input and output
- Slicing settings

The page runs `app.slicer.run_slicer` in a background `QThread`.

### Tools

Card layout:

- top function selector
- input card
- output card

Implemented tools:

- Audio quality spectrogram
- Total duration
- Pitch report
- Peak normalize

The page runs tool workflows in a background `QThread`.

### Settings

Card layout:

- Background
- Color and tint

The page emits live appearance signals for:

- background image
- blur radius
- text color
- tint color
- tint opacity

These settings are live preview only in the current implementation.

## Internationalization

Translations are plain dictionaries in `app/gui/i18n/translations.py`.

Supported locales:

- `en`
- `zh_CN`
- `ja`

Locale resolution:

1. Use the explicit locale if supplied.
2. Otherwise detect the system locale.
3. Fall back to English when unsupported.

Every page implements `retranslate(translator)` and receives language changes from `MainWindow`.

## Styling

Global styling is in `app/gui/style.py`.

Common object names:

- `GlassCard`
- `PrimaryButton`
- `DangerButton`
- `GlassButton`
- `SegmentButton`
- `DropArea`
- `SpectrogramImage`
- `ReportText`

When adding new pages:

- Use a transparent `QScrollArea`.
- Use `GlassCard` for cards.
- Keep long tasks off the GUI thread.
- Give cards fixed vertical size policies when a stacked page could otherwise stretch them.
- Put processing code in a workflow module, not in `app/gui/views`.

## Run

```bat
run-gui.bat
```

Directly:

```bat
env\python.exe -m app.gui
```
