from __future__ import annotations

import json
import logging
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from types import ModuleType

from .naming import numbered_audio_id, safe_name
from .preprocess import preprocess_group_inputs
from .separator_runner import AudioItem, AudioSeparatorRunner


@dataclass(frozen=True)
class PipelineResult:
    final_output_dir: Path
    groups_processed: int
    files_processed: int


def run_pipeline(config: ModuleType, dry_run: bool = False) -> PipelineResult:
    started_at = datetime.now()
    root = Path(config.ROOT_DIR)
    inputs_dir = Path(config.INPUTS_DIR)
    work_dir = Path(config.WORK_OUTPUTS_DIR)
    archive_dir = Path(getattr(config, "ARCHIVE_DIR", root / "archive"))
    final_dir = archive_dir / f"{config.FINAL_OUTPUT_PREFIX}-{started_at.strftime(config.FINAL_OUTPUT_TIME_FORMAT)}"

    _reset_work_dir(config, work_dir, dry_run)
    _setup_logging(config, work_dir, started_at)
    logger = logging.getLogger("ai_cover.workflow")

    groups = _prepare_groups(config, inputs_dir, dry_run)
    if not groups:
        return PipelineResult(final_output_dir=final_dir, groups_processed=0, files_processed=0)

    if dry_run:
        print(f"Input groups: {len(groups)}")
        for group_name, items in groups.items():
            print(f"- {group_name}: {len(items)} audio file(s)")
        print("Model steps:")
        for index, step in enumerate(config.MODEL_PIPELINE, start=1):
            print(f"- {index}. {step['label']}: {step['model_filename']} -> {step['keep_stem']}")
        return PipelineResult(final_output_dir=final_dir, groups_processed=len(groups), files_processed=sum(len(v) for v in groups.values()))

    work_dir.mkdir(parents=True, exist_ok=True)
    final_dir.mkdir(parents=True, exist_ok=True)
    log_path = _current_log_path()

    runner = AudioSeparatorRunner(config)
    manifest = {
        "started_at": started_at.isoformat(timespec="seconds"),
        "final_output_dir": str(final_dir),
        "groups": {},
    }

    total_files = 0
    for group_name, start_items in groups.items():
        logger.info("Starting group: %s", group_name)
        current_items = preprocess_group_inputs(config, group_name, start_items)
        group_manifest = {
            "input_files": [str(item.current_path) for item in start_items],
            "preprocessed_files": [str(item.current_path) for item in current_items],
            "steps": [],
            "final_files": [],
        }

        for step_index, step in enumerate(config.MODEL_PIPELINE, start=1):
            try:
                result = runner.run_step(group_name, step_index, step, current_items)
            except Exception:
                logger.exception("Step failed: group=%s step=%s", group_name, step.get("label"))
                if bool(getattr(config, "STOP_ON_ERROR", True)):
                    raise
                break

            group_manifest["steps"].append(
                {
                    "index": step_index,
                    "label": step["label"],
                    "model_filename": step["model_filename"],
                    "produced_files": [str(path) for path in result.produced_files],
                    "kept_files": [str(path) for path in result.kept_files],
                }
            )
            current_items = result.next_items

        final_group_dir = final_dir / group_name if bool(getattr(config, "FINAL_OUTPUT_GROUP_SUBDIRS", True)) else final_dir
        final_group_dir.mkdir(parents=True, exist_ok=True)
        for item in current_items:
            destination = final_group_dir / item.current_path.name
            shutil.copy2(item.current_path, destination)
            group_manifest["final_files"].append(str(destination))
            total_files += 1

        manifest["groups"][group_name] = group_manifest
        logger.info("Finished group: %s", group_name)

    manifest["finished_at"] = datetime.now().isoformat(timespec="seconds")
    (final_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    if log_path and log_path.exists():
        shutil.copy2(log_path, final_dir / log_path.name)

    if bool(getattr(config, "CLEAN_WORK_OUTPUTS_AFTER_SUCCESS", False)) and work_dir.exists():
        shutil.rmtree(work_dir)

    return PipelineResult(final_output_dir=final_dir, groups_processed=len(groups), files_processed=total_files)


def preprocess_only(config: ModuleType, dry_run: bool = False) -> PipelineResult:
    started_at = datetime.now()
    inputs_dir = Path(config.INPUTS_DIR)
    work_dir = Path(config.WORK_OUTPUTS_DIR)

    _reset_work_dir(config, work_dir, dry_run)
    _setup_logging(config, work_dir, started_at)
    groups = _prepare_groups(config, inputs_dir, dry_run)
    if not groups:
        return PipelineResult(final_output_dir=work_dir, groups_processed=0, files_processed=0)

    total_files = 0
    for group_name, items in groups.items():
        if dry_run:
            print(f"- {group_name}: {len(items)} file(s) -> {work_dir / f'{group_name}-inputs1'}")
            total_files += len(items)
            continue
        converted = preprocess_group_inputs(config, group_name, items)
        total_files += len(converted)

    return PipelineResult(final_output_dir=work_dir, groups_processed=len(groups), files_processed=total_files)


def _reset_work_dir(config: ModuleType, work_dir: Path, dry_run: bool) -> None:
    if dry_run:
        return
    if bool(getattr(config, "CLEAN_WORK_OUTPUTS_BEFORE_RUN", True)) and work_dir.exists():
        shutil.rmtree(work_dir)


def _prepare_groups(config: ModuleType, inputs_dir: Path, dry_run: bool) -> dict[str, list[AudioItem]]:
    if not inputs_dir.exists():
        inputs_dir.mkdir(parents=True, exist_ok=True)
        if dry_run:
            print(f"Input directory created: {inputs_dir}")
            print("Add subfolders with audio files, then run again.")
            return {}
        raise FileNotFoundError(f"Input directory was created but is empty: {inputs_dir}")

    groups = _discover_groups(config)
    if not groups and dry_run:
        print(f"No input folders with audio files were found under: {inputs_dir}")
        print("Add audio files under folders such as inputs/kano or inputs/warma.")
        return {}

    if not groups:
        raise RuntimeError(f"No input folders with audio files were found under: {inputs_dir}")

    return groups


def _discover_groups(config: ModuleType) -> dict[str, list[AudioItem]]:
    inputs_dir = Path(config.INPUTS_DIR)
    extensions = {ext.lower() for ext in getattr(config, "AUDIO_EXTENSIONS", set())}
    recursive = bool(getattr(config, "RECURSIVE_INPUT_SCAN", True))
    groups: dict[str, list[AudioItem]] = {}

    for folder in sorted(path for path in inputs_dir.iterdir() if path.is_dir()):
        pattern = "**/*" if recursive else "*"
        files = sorted(path for path in folder.glob(pattern) if path.is_file() and path.suffix.lower() in extensions)
        if not files:
            continue
        group_name = safe_name(folder.name)
        groups[group_name] = [AudioItem(original_id=numbered_audio_id(index), current_path=path) for index, path in enumerate(files, start=1)]

    return groups


def _setup_logging(config: ModuleType, work_dir: Path, started_at: datetime) -> None:
    work_dir.mkdir(parents=True, exist_ok=True)
    level = getattr(logging, str(getattr(config, "LOG_LEVEL", "INFO")).upper(), logging.INFO)
    log_path = work_dir / f"run-{started_at.strftime('%Y%m%d-%H%M%S')}.log"

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)
    root_logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    stream_handler.setLevel(level)
    root_logger.addHandler(stream_handler)


def _current_log_path() -> Path | None:
    for handler in logging.getLogger().handlers:
        if isinstance(handler, logging.FileHandler):
            return Path(handler.baseFilename)
    return None
