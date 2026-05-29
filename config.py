MODEL_BATCH_SIZE = 16
MODEL_OVERLAP = 2
MODEL_SEGMENT_SIZE = 256
MODEL_OVERRIDE_SEGMENT_SIZE = False

# Edit this list to change the order of processing. keep_stem is the target
# product to pass to the next model and to keep in the final output.
MODEL_PIPELINE = [
    {
        "label": "vocals",
        "model_filename": "mel_band_roformer_kim_ft3_unwa.ckpt",
        "keep_stem": "vocals",
        "stem_aliases": ["Vocals", "vocal"],
        "pitch_shift": 0,
    },
]
