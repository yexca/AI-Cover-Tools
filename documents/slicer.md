# Slicer

`app/slicer` prepares training clips from audio files.

## Files

- `engine.py`: local copy of the RMS silence-detection slicer.
- `workflow.py`: recursive scanning, streaming RMS analysis, clip writing, and result dataclasses.

## Workflow API

```python
from app.slicer import SlicerSettings, run_slicer

result = run_slicer(
    input_dir="inputs",
    output_dir="outputs",
    output_format="wav",
    settings=SlicerSettings(),
)
```

`run_slicer` returns `SlicerRunResult`.

`run_slicing_task` processes one concrete audio file and is reused by the WebUI slicer node. The graph executor owns the per-run intermediate directory and preserves artifact metadata while expanding one input artifact into multiple clip artifacts.

## GUI Page

Cards:

- Input and output
- Slicing settings

Input and output card:

- input folder
- output folder
- output format
- start button

Settings card:

| Setting | Default |
| --- | --- |
| Threshold | `-40.0 dB` |
| Minimum Length | `5000 ms` |
| Minimum Interval | `300 ms` |
| Hop Size | `10 ms` |
| Maximum Size Length | `1000 ms` |

The GUI validates:

- minimum length >= minimum interval
- minimum interval >= hop size
- maximum kept silence >= hop size

The task runs in a `QThread`.

## Processing Behavior

1. Recursively scan the input folder for supported audio files.
2. Analyze each file with the RMS slicer.
3. Write clips under `output_dir/<source-stem>/`.
4. Return per-file success, generated paths, and errors.

Supported input suffixes:

- `.wav`
- `.flac`
- `.mp3`
- `.m4a`
- `.aac`
- `.ogg`
- `.opus`
- `.wma`
- `.aiff`
- `.aif`

Supported output formats:

- `wav`
- `flac`
- `mp3`

MP3 support depends on the installed `libsndfile` backend used by `soundfile`.
