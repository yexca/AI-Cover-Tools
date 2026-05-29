from __future__ import annotations

import numpy as np


def get_rms(
    y: np.ndarray,
    *,
    frame_length: int = 2048,
    hop_length: int = 512,
    pad_mode: str = "constant",
) -> np.ndarray:
    padding = (int(frame_length // 2), int(frame_length // 2))
    y = np.pad(y, padding, mode=pad_mode)

    axis = -1
    out_strides = y.strides + (y.strides[axis],)
    x_shape_trimmed = list(y.shape)
    x_shape_trimmed[axis] -= frame_length - 1
    out_shape = tuple(x_shape_trimmed) + (frame_length,)
    xw = np.lib.stride_tricks.as_strided(y, shape=out_shape, strides=out_strides)
    target_axis = axis - 1 if axis < 0 else axis + 1
    xw = np.moveaxis(xw, -1, target_axis)

    slices = [slice(None)] * xw.ndim
    slices[axis] = slice(0, None, hop_length)
    x = xw[tuple(slices)]
    power = np.mean(np.abs(x) ** 2, axis=-2, keepdims=True)
    return np.sqrt(power)


class Slicer:
    def __init__(
        self,
        sr: int,
        threshold: float = -40.0,
        min_length: int = 5000,
        min_interval: int = 300,
        hop_size: int = 10,
        max_sil_kept: int = 1000,
    ) -> None:
        if not min_length >= min_interval >= hop_size:
            raise ValueError("min_length must be >= min_interval >= hop_size")
        if not max_sil_kept >= hop_size:
            raise ValueError("max_sil_kept must be >= hop_size")

        min_interval_samples = sr * min_interval / 1000
        self.threshold = 10 ** (threshold / 20.0)
        self.hop_size = round(sr * hop_size / 1000)
        self.win_size = min(round(min_interval_samples), 4 * self.hop_size)
        self.min_length = round(sr * min_length / 1000 / self.hop_size)
        self.min_interval = round(min_interval_samples / self.hop_size)
        self.max_sil_kept = round(sr * max_sil_kept / 1000 / self.hop_size)

    def slice_ranges(self, waveform: np.ndarray) -> list[tuple[int, int]]:
        if len(waveform.shape) > 1:
            samples = waveform.mean(axis=0)
            total_samples = waveform.shape[1]
        else:
            samples = waveform
            total_samples = waveform.shape[0]

        if (samples.shape[0] + self.hop_size - 1) // self.hop_size <= self.min_length:
            return [(0, total_samples)]

        rms_list = get_rms(
            y=samples,
            frame_length=self.win_size,
            hop_length=self.hop_size,
        ).squeeze(0)
        return self.slice_ranges_from_rms(rms_list, total_samples)

    def slice_ranges_from_rms(self, rms_list: np.ndarray, total_samples: int) -> list[tuple[int, int]]:
        if rms_list.shape[0] == 0:
            return [(0, total_samples)]

        total_frames = rms_list.shape[0]
        if total_frames <= self.min_length:
            return [(0, total_samples)]

        sil_tags: list[tuple[int, int]] = []
        silence_start = None
        clip_start = 0

        for index, rms in enumerate(rms_list):
            if rms < self.threshold:
                if silence_start is None:
                    silence_start = index
                continue

            if silence_start is None:
                continue

            is_leading_silence = silence_start == 0 and index > self.max_sil_kept
            need_slice_middle = index - silence_start >= self.min_interval and index - clip_start >= self.min_length
            if not is_leading_silence and not need_slice_middle:
                silence_start = None
                continue

            if index - silence_start <= self.max_sil_kept:
                pos = rms_list[silence_start : index + 1].argmin() + silence_start
                if silence_start == 0:
                    sil_tags.append((0, pos))
                else:
                    sil_tags.append((pos, pos))
                clip_start = pos
            elif index - silence_start <= self.max_sil_kept * 2:
                pos = rms_list[index - self.max_sil_kept : silence_start + self.max_sil_kept + 1].argmin()
                pos += index - self.max_sil_kept
                pos_l = rms_list[silence_start : silence_start + self.max_sil_kept + 1].argmin() + silence_start
                pos_r = rms_list[index - self.max_sil_kept : index + 1].argmin() + index - self.max_sil_kept
                if silence_start == 0:
                    sil_tags.append((0, pos_r))
                    clip_start = pos_r
                else:
                    sil_tags.append((min(pos_l, pos), max(pos_r, pos)))
                    clip_start = max(pos_r, pos)
            else:
                pos_l = rms_list[silence_start : silence_start + self.max_sil_kept + 1].argmin() + silence_start
                pos_r = rms_list[index - self.max_sil_kept : index + 1].argmin() + index - self.max_sil_kept
                if silence_start == 0:
                    sil_tags.append((0, pos_r))
                else:
                    sil_tags.append((pos_l, pos_r))
                clip_start = pos_r

            silence_start = None

        if silence_start is not None and total_frames - silence_start >= self.min_interval:
            silence_end = min(total_frames, silence_start + self.max_sil_kept)
            pos = rms_list[silence_start : silence_end + 1].argmin() + silence_start
            sil_tags.append((pos, total_frames + 1))

        if not sil_tags:
            return [(0, total_samples)]

        ranges: list[tuple[int, int]] = []
        if sil_tags[0][0] > 0:
            ranges.append((0, self._frame_to_sample(sil_tags[0][0], total_samples)))
        for index in range(len(sil_tags) - 1):
            ranges.append(
                (
                    self._frame_to_sample(sil_tags[index][1], total_samples),
                    self._frame_to_sample(sil_tags[index + 1][0], total_samples),
                )
            )
        if sil_tags[-1][1] < total_frames:
            ranges.append((self._frame_to_sample(sil_tags[-1][1], total_samples), total_samples))
        return ranges

    def slice(self, waveform: np.ndarray) -> list[np.ndarray]:
        ranges = self.slice_ranges(waveform)
        if len(waveform.shape) > 1:
            return [waveform[:, begin:end] for begin, end in ranges]
        return [waveform[begin:end] for begin, end in ranges]

    def _frame_to_sample(self, frame_index: int, total_samples: int) -> int:
        return min(total_samples, frame_index * self.hop_size)
