from __future__ import annotations

import re
from pathlib import Path


def normalize_token(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def safe_name(value: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", value).strip(" .")
    cleaned = re.sub(r"\s+", "_", cleaned)
    return cleaned or "audio"


def original_id_for_file(file_path: Path, root: Path) -> str:
    relative = file_path.relative_to(root)
    parts = list(relative.with_suffix("").parts)
    return safe_name("__".join(parts))


def numbered_audio_id(index: int) -> str:
    return f"{index:02d}"


def stem_aliases(keep_stem: str, aliases: list[str] | None = None) -> list[str]:
    seen = set()
    values = [keep_stem, keep_stem.title(), keep_stem.upper(), keep_stem.replace("_", " ")]
    values.extend(aliases or [])
    result = []
    for value in values:
        key = normalize_token(value)
        if key and key not in seen:
            result.append(value)
            seen.add(key)
    return result


def output_extension(output_format: str | None) -> str:
    if not output_format:
        return ".wav"
    return "." + output_format.lower().lstrip(".")


def parsed_stem_from_separator_name(path: Path) -> str | None:
    match = re.search(r"_\(([^)]+)\)", path.stem)
    if match:
        return match.group(1)
    return None
