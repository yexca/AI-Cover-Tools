# Slicer Module

`app/slicer` contains the audio slicing workflow for preparing training clips after separation.

Files:

- `engine.py`: local copy of the `audio-slicer` RMS silence-detection algorithm.
- `workflow.py`: folder scanning, streaming RMS analysis, slice writing, and result dataclasses.

The GUI Slicer page is organized as two glass cards:

- Input and output: input folder, output folder, output format, and start button.
- Slicing settings: threshold, minimum clip length, minimum silence interval, hop size, and maximum kept silence length.

Defaults:

| Setting | Default |
| --- | --- |
| Input folder | `inputs` |
| Output folder | `outputs` |
| Output format | `wav` |
| Threshold (dB) | `-40` |
| Minimum Length (ms) | `5000` |
| Minimum Interval (ms) | `300` |
| Hop Size (ms) | `10` |
| Maximum Size Length (ms) | `1000` |

Processing behavior:

1. Recursively scan the input folder for supported audio files.
2. Analyze each file with the `audio-slicer` RMS algorithm.
3. Write clips under `outputs/<source-name>/`.
4. Keep the GUI responsive by running slicing in a background thread.

Supported output formats are `wav`, `flac`, and `mp3`. Actual MP3 read/write support depends on the installed `libsndfile` backend used by `soundfile`.
