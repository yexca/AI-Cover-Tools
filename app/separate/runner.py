from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

from ..utils.audio import AudioItem
from ..utils.naming import normalize_token, parsed_stem_from_separator_name, safe_name, stem_aliases


@dataclass(frozen=True)
class StepResult:
    next_items: list[AudioItem]
    produced_files: list[Path]
    kept_files: list[Path]


class AudioSeparatorRunner:
    def __init__(self, config: ModuleType) -> None:
        self.config = config
        self.logger = logging.getLogger("ai_cover.separator")

    def run_step(self, group_name: str, step_index: int, step: dict, items: list[AudioItem]) -> StepResult:
        from audio_separator.separator import Separator

        label = safe_name(step["label"])
        stage_output_dir = Path(self.config.WORK_OUTPUTS_DIR) / f"{group_name}-outputs{step_index}-{label}"
        next_input_dir = Path(self.config.WORK_OUTPUTS_DIR) / f"{group_name}-inputs{step_index + 1}"
        stage_output_dir.mkdir(parents=True, exist_ok=True)
        next_input_dir.mkdir(parents=True, exist_ok=True)

        separator = Separator(
            log_level=getattr(logging, str(getattr(self.config, "LOG_LEVEL", "INFO")).upper(), logging.INFO),
            model_file_dir=str(Path(self.config.MODELS_DIR)),
            output_dir=str(stage_output_dir),
            mdx_params=self._mdx_params(step),
            vr_params=self._vr_params(step),
            demucs_params=self._demucs_params(step),
            mdxc_params=self._mdxc_params(step),
            **self._common_options(step),
        )
        self._log_acceleration_state()
        separator.load_model(model_filename=step["model_filename"])

        next_items: list[AudioItem] = []
        produced_files: list[Path] = []
        kept_files: list[Path] = []

        for item in items:
            clean_base = f"{item.original_id}-{label}"
            custom_names = self._custom_output_names(step, clean_base)
            self.logger.info("Processing %s with %s", item.current_path, step["model_filename"])
            output_paths = separator.separate(str(item.current_path), custom_output_names=custom_names)
            outputs = [self._resolve_output_path(path, stage_output_dir) for path in output_paths]
            produced_files.extend(outputs)

            target = self._select_target_file(outputs, step, clean_base)
            clean_target = next_input_dir / f"{clean_base}.wav"
            shutil.move(str(target), str(clean_target))
            kept_files.append(clean_target)
            next_items.append(AudioItem(original_id=item.original_id, current_path=clean_target))

        return StepResult(next_items=next_items, produced_files=produced_files, kept_files=kept_files)

    def _common_options(self, step: dict) -> dict:
        options = dict(getattr(self.config, "COMMON_SEPARATOR_OPTIONS", {}))
        options.update(step.get("separator_options", {}))
        if not options.get("output_single_stem"):
            options["output_single_stem"] = None
        else:
            options["output_single_stem"] = step["keep_stem"]
        return options

    def _mdx_params(self, step: dict) -> dict:
        params = dict(getattr(self.config, "DEFAULT_MDX_PARAMS", {}))
        for key in ("segment_size", "overlap", "batch_size"):
            if key in step:
                params[key] = step[key]
        params.update(step.get("mdx_params", {}))
        return params

    def _vr_params(self, step: dict) -> dict:
        params = dict(getattr(self.config, "DEFAULT_VR_PARAMS", {}))
        if "batch_size" in step:
            params["batch_size"] = step["batch_size"]
        params.update(step.get("vr_params", {}))
        return params

    def _demucs_params(self, step: dict) -> dict:
        params = dict(getattr(self.config, "DEFAULT_DEMUCS_PARAMS", {}))
        if "segment_size" in step:
            params["segment_size"] = step["segment_size"]
        if "overlap" in step:
            params["overlap"] = step["overlap"]
        params.update(step.get("demucs_params", {}))
        return params

    def _mdxc_params(self, step: dict) -> dict:
        params = dict(getattr(self.config, "DEFAULT_MDXC_PARAMS", {}))
        for key in ("segment_size", "override_model_segment_size", "overlap", "batch_size", "pitch_shift"):
            if key in step:
                params[key] = step[key]
        params.update(step.get("mdxc_params", {}))
        return params

    def _custom_output_names(self, step: dict, clean_base: str) -> dict[str, str]:
        aliases = stem_aliases(step["keep_stem"], step.get("stem_aliases"))
        return {alias: clean_base for alias in aliases}

    def _resolve_output_path(self, output_path: str | Path, output_dir: Path) -> Path:
        path = Path(output_path)
        if path.is_absolute():
            return path
        return output_dir / path

    def _select_target_file(self, outputs: list[Path], step: dict, clean_base: str) -> Path:
        if not outputs:
            raise RuntimeError(f"No output files produced by model: {step['model_filename']}")

        aliases = {normalize_token(value) for value in stem_aliases(step["keep_stem"], step.get("stem_aliases"))}
        for path in outputs:
            if normalize_token(path.stem) == normalize_token(clean_base):
                return path

        for path in outputs:
            parsed_stem = parsed_stem_from_separator_name(path)
            if parsed_stem and normalize_token(parsed_stem) in aliases:
                return path

        for path in outputs:
            path_stem_key = normalize_token(path.stem)
            if any(alias and alias in path_stem_key for alias in aliases):
                return path

        if len(outputs) == 1:
            self.logger.warning("Only one output found; using it as target: %s", outputs[0])
            return outputs[0]

        names = ", ".join(path.name for path in outputs)
        raise RuntimeError(f"Could not find target stem '{step['keep_stem']}' in outputs: {names}")

    def _log_acceleration_state(self) -> None:
        try:
            import torch

            if torch.cuda.is_available():
                self.logger.info("Torch CUDA available: %s (%s)", torch.version.cuda, torch.cuda.get_device_name(0))
            else:
                self.logger.warning("Torch CUDA is not available; Torch models will use CPU.")
        except Exception as exc:
            self.logger.warning("Unable to inspect Torch CUDA state: %s", exc)

        try:
            import onnxruntime as ort

            providers = ort.get_available_providers()
            if "CUDAExecutionProvider" in providers:
                self.logger.info("ONNX Runtime CUDAExecutionProvider available.")
            else:
                self.logger.warning("ONNX Runtime CUDAExecutionProvider is not available. Providers: %s", providers)
        except Exception as exc:
            self.logger.warning("Unable to inspect ONNX Runtime providers: %s", exc)
