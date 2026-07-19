from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any
from urllib.request import Request, urlopen
from urllib.parse import urlparse

import yaml

from .paths import MODELS_DIR, REGISTRY_PATH, SEPARATOR_DATA_DIR


CATALOG_URL = "https://raw.githubusercontent.com/TRvlvr/application_data/main/filelists/download_checks.json"
MODEL_EXTENSIONS = {".ckpt", ".onnx", ".pth", ".pt", ".th", ".safetensors"}
CATALOG_GROUPS = {
    "vr_download_list": ("VR", "VR"),
    "vr_download_vip_list": ("VR", "VR"),
    "mdx_download_list": ("MDX", "MDX"),
    "mdx_download_vip_list": ("MDX", "MDX"),
    "mdx23_download_list": ("MDXC", "MDXC"),
    "mdx23c_download_list": ("MDXC", "MDXC"),
    "mdx23c_download_vip_list": ("MDXC", "MDXC"),
    "roformer_download_list": ("RoFormer", "MDXC"),
    "demucs_download_list": ("Demucs", "Demucs"),
    "other_network_list": ("RoFormer", "MDXC"),
    "other_network_list_new": ("RoFormer", "MDXC"),
}


class _YamlLoader(yaml.SafeLoader):
    pass


_YamlLoader.add_constructor(
    "tag:yaml.org,2002:python/tuple",
    lambda loader, node: tuple(loader.construct_sequence(node)),
)


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return default


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name, suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _tokens(value: str) -> set[str]:
    ignored = {"model", "config", "band", "roformer", "mel", "mono"}
    return {part for part in re.split(r"[^a-z0-9]+", value.lower()) if len(part) > 1 and part not in ignored}


def _architecture_from(group: str, filename: str, label: str) -> tuple[str, str]:
    if group in CATALOG_GROUPS:
        return CATALOG_GROUPS[group]
    text = f"{filename} {label}".lower()
    if "roformer" in text:
        return "RoFormer", "MDXC"
    if "demucs" in text or filename.lower().endswith(".th"):
        return "Demucs", "Demucs"
    if filename.lower().endswith(".onnx") or "mdx-net" in text:
        return "MDX", "MDX"
    if "mdx" in text or filename.lower().endswith(".ckpt"):
        return "MDXC", "MDXC"
    if filename.lower().endswith(".pth"):
        return "VR", "VR"
    return "Unknown", "Unknown"


def _function_from(stems: list[str], text: str) -> str:
    stem_set = {stem.lower().replace("-", "_") for stem in stems}
    lowered = text.lower()
    # Explicit task names are stronger evidence than generic stems such as "dry".
    if any(token in lowered for token in ("denoise", "de-noise", "noise removal", "noise-removal")):
        return "denoise"
    if any(token in lowered for token in ("dereverb", "de-reverb", "deecho", "de-echo")):
        return "dereverb"
    if any(token in lowered for token in ("debleed", "de-bleed")):
        return "debleed"
    if stem_set & {"noise", "no_noise", "denoised"}:
        return "denoise"
    if stem_set & {"noreverb", "dry", "reverb", "wet"}:
        return "dereverb"
    instruments = {"drums", "bass", "guitar", "piano", "other", "vocals"}
    if len(stem_set & instruments) >= 3:
        return "multistem_separation"
    if stem_set & {"vocals", "vocal", "instrumental", "accompaniment", "other"} or "karaoke" in lowered:
        return "vocal_separation"
    return "other"


class ModelRegistry:
    """Fast local model discovery with an optional, explicit catalog sync."""

    def __init__(self, models_dir: Path = MODELS_DIR, cache_path: Path = REGISTRY_PATH) -> None:
        self.models_dir = models_dir
        self.cache_path = cache_path
        self._lock = RLock()
        self._data: dict[str, Any] = _read_json(cache_path, {})

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            if not self._data:
                return {
                    "version": 1,
                    "refreshed_at": None,
                    "models_dir": str(self.models_dir.resolve()),
                    "models": [],
                    "summary": {"total": 0, "installed": 0, "needs_confirmation": 0, "by_function": {}},
                    "scanning": True,
                }
            return json.loads(json.dumps(self._data))

    def refresh(self, scope: str = "local", force: bool = False) -> dict[str, Any]:
        if scope not in {"local", "catalog", "all"}:
            raise ValueError(f"Unsupported refresh scope: {scope}")
        if scope in {"catalog", "all"}:
            self._sync_catalog(force=force)
        data = self._scan()
        with self._lock:
            self._data = data
            _atomic_json(self.cache_path, data)
        return self.snapshot()

    def find(self, filename: str) -> dict[str, Any] | None:
        for model in self.snapshot().get("models", []):
            if model["filename"].lower() == filename.lower():
                return model
        return None

    def _sync_catalog(self, force: bool) -> None:
        target = self.models_dir / "download_checks.json"
        if target.exists() and not force:
            return
        request = Request(CATALOG_URL, headers={"User-Agent": "AI-cover-tools-webui"})
        with urlopen(request, timeout=20) as response:  # noqa: S310 - fixed trusted URL
            payload = response.read()
        parsed = json.loads(payload.decode("utf-8"))
        if not isinstance(parsed, dict):
            raise ValueError("Online model catalog has an invalid format")
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=target.name, suffix=".tmp", dir=target.parent)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(payload)
            os.replace(temporary, target)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def _catalog_sources(self) -> list[tuple[str, dict[str, Any]]]:
        sources: list[tuple[str, dict[str, Any]]] = []
        cached = _read_json(self.models_dir / "download_checks.json", {})
        bundled = _read_json(SEPARATOR_DATA_DIR / "models.json", {})
        if isinstance(cached, dict):
            sources.append(("audio-separator-cache", cached))
        if isinstance(bundled, dict):
            sources.append(("audio-separator-bundled", bundled))
        return sources

    def _flatten_catalog(self) -> dict[str, dict[str, Any]]:
        flattened: dict[str, dict[str, Any]] = {}
        for source_name, source in self._catalog_sources():
            for group, entries in source.items():
                if not isinstance(entries, dict) or "download" not in group:
                    continue
                for label, value in entries.items():
                    files: list[str]
                    if isinstance(value, str):
                        files = [value]
                    elif isinstance(value, dict):
                        files = [*value.keys(), *(item for item in value.values() if isinstance(item, str))]
                    else:
                        continue
                    names = [Path(urlparse(item).path).name for item in files]
                    names = list(dict.fromkeys(name for name in names if name))
                    yaml_names = [name for name in names if name.lower().endswith((".yaml", ".yml"))]
                    candidates = [name for name in names if Path(name).suffix.lower() in MODEL_EXTENSIONS]
                    # Demucs loads its YAML entry point; other architectures load the weight.
                    filename = (yaml_names[0] if group.startswith("demucs") and yaml_names else None) or (candidates[0] if candidates else None)
                    if not filename:
                        continue
                    architecture, backend = _architecture_from(group, filename, str(label))
                    flattened[filename.lower()] = {
                        "filename": filename,
                        "display_name": str(label),
                        "architecture": architecture,
                        "backend": backend,
                        "config_filename": yaml_names[0] if yaml_names else None,
                        "download_files": names,
                        "catalog_source": source_name,
                    }
        return flattened

    def _yaml_metadata(self, path: Path) -> dict[str, Any]:
        try:
            value = yaml.load(path.read_text(encoding="utf-8"), Loader=_YamlLoader)
        except (OSError, yaml.YAMLError, UnicodeError):
            return {}
        if not isinstance(value, dict):
            return {}
        training = value.get("training") or {}
        stems = training.get("instruments") if isinstance(training, dict) else None
        target = training.get("target_instrument") if isinstance(training, dict) else None
        return {
            "outputs": [str(stem) for stem in stems] if isinstance(stems, (list, tuple)) else [],
            "target_stem": str(target) if target else None,
        }

    def _best_yaml(self, model: Path, preferred: str | None, yamls: list[Path]) -> Path | None:
        if preferred:
            preferred_path = self.models_dir / preferred
            if preferred_path.exists():
                return preferred_path
        direct = [model.with_suffix(".yaml"), model.with_suffix(".yml")]
        for path in direct:
            if path.exists():
                return path
        model_tokens = _tokens(model.stem)
        ranked = sorted(
            ((len(model_tokens & _tokens(path.stem)), path) for path in yamls),
            key=lambda item: item[0],
            reverse=True,
        )
        return ranked[0][1] if ranked and ranked[0][0] >= 2 else None

    def _score_metadata(self, filename: str) -> dict[str, Any]:
        scores = _read_json(SEPARATOR_DATA_DIR / "models-scores.json", {})
        record = scores.get(filename) if isinstance(scores, dict) else None
        if isinstance(record, dict) and isinstance(record.get("stems"), list):
            return {
                "outputs": [str(stem) for stem in record["stems"]],
                "target_stem": str(record["target_stem"]) if record.get("target_stem") else None,
            }
        tracks = record.get("track_scores") if isinstance(record, dict) else None
        if not isinstance(tracks, list):
            return {"outputs": [], "target_stem": None}
        for track in tracks:
            stems = track.get("scores") if isinstance(track, dict) else None
            if isinstance(stems, dict):
                return {"outputs": [str(stem) for stem in stems], "target_stem": None}
        return {"outputs": [], "target_stem": None}

    def _scan(self) -> dict[str, Any]:
        self.models_dir.mkdir(parents=True, exist_ok=True)
        catalog = self._flatten_catalog()
        yaml_files = sorted([*self.models_dir.glob("*.yaml"), *self.models_dir.glob("*.yml")])
        local_files = [path for path in self.models_dir.iterdir() if path.is_file() and path.suffix.lower() in MODEL_EXTENSIONS]
        # Demucs models use a YAML file as the model entry point. Other YAML files
        # are only sidecar configs and must not appear as standalone models.
        local_files.extend(
            path
            for entry in catalog.values()
            if entry.get("backend") == "Demucs"
            for path in [self.models_dir / str(entry["filename"])]
            if path.is_file() and path.suffix.lower() in {".yaml", ".yml"}
        )
        local_files = sorted(set(local_files))
        models: dict[str, dict[str, Any]] = {}

        for key, entry in catalog.items():
            score_metadata = self._score_metadata(entry["filename"])
            outputs = score_metadata["outputs"]
            models[key] = {
                **entry,
                "id": entry["filename"],
                "installed": False,
                "path": None,
                "size": None,
                "modified_at": None,
                "outputs": outputs,
                "target_stem": score_metadata["target_stem"],
                "function": _function_from(outputs, f"{entry['filename']} {entry['display_name']}"),
                "metadata_source": "scores" if outputs else "catalog",
                "confidence": "medium" if outputs else "low",
                "needs_confirmation": not bool(outputs),
            }

        for path in local_files:
            key = path.name.lower()
            catalog_entry = catalog.get(key, {})
            architecture, backend = _architecture_from("", path.name, str(catalog_entry.get("display_name", "")))
            if catalog_entry:
                architecture = catalog_entry["architecture"]
                backend = catalog_entry["backend"]
            config_path = path if path.suffix.lower() in {".yaml", ".yml"} else self._best_yaml(path, catalog_entry.get("config_filename"), yaml_files)
            yaml_metadata = self._yaml_metadata(config_path) if config_path else {}
            score_metadata = self._score_metadata(path.name)
            outputs = yaml_metadata.get("outputs") or score_metadata["outputs"]
            target = yaml_metadata.get("target_stem") or score_metadata["target_stem"]
            display_name = catalog_entry.get("display_name") or path.stem.replace("_", " ")
            source = "yaml" if yaml_metadata.get("outputs") else ("scores" if outputs else "filename")
            models[key] = {
                **catalog_entry,
                "id": path.name,
                "filename": path.name,
                "display_name": display_name,
                "installed": True,
                "path": str(path.resolve()),
                "size": path.stat().st_size,
                "modified_at": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
                "architecture": architecture,
                "backend": backend,
                "config_filename": config_path.name if config_path else catalog_entry.get("config_filename"),
                "outputs": outputs,
                "target_stem": target,
                "function": _function_from(outputs, f"{path.name} {display_name}"),
                "metadata_source": source,
                "confidence": "high" if source == "yaml" else ("medium" if source == "scores" else "low"),
                "needs_confirmation": not bool(outputs),
            }

        ordered = sorted(models.values(), key=lambda model: (not model["installed"], model["function"], model["display_name"].lower()))
        counts: dict[str, int] = {}
        for model in ordered:
            counts[model["function"]] = counts.get(model["function"], 0) + 1
        return {
            "version": 1,
            "refreshed_at": datetime.now(timezone.utc).isoformat(),
            "models_dir": str(self.models_dir.resolve()),
            "models": ordered,
            "summary": {
                "total": len(ordered),
                "installed": sum(1 for model in ordered if model["installed"]),
                "needs_confirmation": sum(1 for model in ordered if model["needs_confirmation"]),
                "by_function": counts,
            },
        }
