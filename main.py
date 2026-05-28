from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ai_cover.config_loader import load_config
from ai_cover.dependencies import ensure_audio_separator_available
from ai_cover.models import ensure_models
from ai_cover.workflow import preprocess_only
from ai_cover.workflow import run_pipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch AI cover training-data preprocessing pipeline.")
    parser.add_argument("--config", default="config.py", help="Path to the pipeline config file.")
    parser.add_argument("--download-models-only", action="store_true", help="Only download/check configured models, then exit.")
    parser.add_argument("--preprocess-only", action="store_true", help="Only convert/copy input audio into clean WAV files, then exit.")
    parser.add_argument("--skip-model-download", action="store_true", help="Skip model pre-download/check before processing.")
    parser.add_argument("--dry-run", action="store_true", help="Print the planned input groups and model steps without processing audio.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_config(Path(args.config))

    needs_audio_separator = (not args.dry_run and not args.preprocess_only) or args.download_models_only
    if needs_audio_separator:
        ensure_audio_separator_available(config)

    if not args.dry_run and not args.preprocess_only and not args.skip_model_download:
        ensure_models(config)

    if args.download_models_only:
        print("Model check/download completed.")
        return 0

    if args.preprocess_only:
        result = preprocess_only(config, dry_run=args.dry_run)
        if not args.dry_run:
            print(f"Preprocess completed. WAV inputs: {result.final_output_dir}")
        return 0

    result = run_pipeline(config, dry_run=args.dry_run)
    if args.dry_run:
        return 0

    print(f"Done. Final outputs: {result.final_output_dir}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("Interrupted by user.")
        raise SystemExit(130)
    except Exception as exc:
        print(f"Pipeline failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
