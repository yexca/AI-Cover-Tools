# Tools

`app/tools` contains standalone audio utilities used by the GUI Tools page.

The GUI page has:

- a top function selector
- one input card
- one output card
- background workers so the GUI stays responsive

## Shared Audio Scan

Tools scan these suffixes:

- `.wav`
- `.flac`
- `.ogg`
- `.mp3`
- `.m4a`
- `.aac`
- `.wma`

## Audio Quality

Purpose: render a spectrogram image similar to Spek.

Input:

- audio file path
- drag-and-drop audio file area

Behavior:

- reads audio with `soundfile`
- downmixes to mono
- splits long audio into 10 minute segments
- renders PNG spectrograms with `scipy.signal` and `Pillow`
- writes to `outputs/audio_quality/<source-stem>/`

Output:

- image preview
- segment metadata
- previous and next segment buttons
- click-to-open image preview dialog

## Total Duration

Purpose: total duration of all audio files in a folder.

Input:

- folder path, default `inputs`
- drag-and-drop folder area

Behavior:

- recursively scans supported audio files
- reads duration with `soundfile`
- falls back to `ffprobe` when `soundfile` cannot read a file

Output:

```text
%Hours% h %Minutes% m %Seconds% s
```

The output card also shows scanned file count, failed file count, and folder path.

## Pitch Report

Purpose: dataset-wide pitch range and distribution report.

Input:

- folder path, default `inputs`
- drag-and-drop folder area
- pitch algorithm selector

Algorithms:

- `Praat`: uses `praat-parselmouth`
- `RMVPE`: uses `rmvpe-onnx` with ONNX Runtime

Praat behavior:

- loads each file with Praat
- calls `Sound.to_pitch()`
- keeps voiced frames where frequency is greater than 0

RMVPE behavior:

- loads audio with `soundfile`
- calls `rmvpe_onnx.RMVPE().predict(audio, sample_rate)`
- keeps frames above the confidence threshold
- downloads `rmvpe.onnx` automatically on first use if not already cached

Report fields:

- algorithm
- files scanned
- failed files
- voiced frame count
- absolute raw range
- primary pitch concentration
- effective RVC target range after trimming 1 percent outliers
- per-file pitch ranges

Output image:

- `outputs/pitch/dataset_pitch_distribution.png`
- click-to-open image preview dialog

## Normalize

Purpose: peak-normalize all audio files in a folder.

Input card rows:

1. input folder, default `inputs`
2. drag-and-drop input folder area
3. output folder, default `outputs`
4. drag-and-drop output folder area
5. target peak in dB, default `-3.0`, and run button

Behavior:

- recursively scans supported audio files
- runs `ffmpeg-normalize` with peak normalization
- preserves relative folder structure in the output folder
- uses the original file extension for output
- exposes `normalize_audio_file` for callers such as the WebUI that already own a concrete artifact list

Equivalent command shape:

```bat
ffmpeg-normalize input.wav -nt peak -t -3 -ext wav -o output.wav -f
```

Output:

- success count
- failed count
- output folder

## Dependencies

Tools use:

- `soundfile`
- `numpy`
- `scipy`
- `Pillow`
- `praat-parselmouth`
- `rmvpe-onnx`
- `ffmpeg-normalize`
- `ffmpeg` / `ffprobe`

`run-install.bat` installs these into the project-local `env`.
