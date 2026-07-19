from __future__ import annotations

import unittest

from app.web.schemas import RunRequest, Workflow
from app.web.workflows import topological_order, validate_workflow


class _Registry:
    def find(self, filename: str):
        if filename == "test.ckpt":
            return {"installed": True, "outputs": ["vocals", "other"]}
        return None


class WorkflowTests(unittest.TestCase):
    def test_editor_payload_is_normalized_and_validated(self) -> None:
        raw = {
            "id": "workflow-1",
            "name": "Vocal split",
            "nodes": [
                {"id": "input", "type": "file_input", "data": {"config": {"path": "song.wav"}}},
                {"id": "split", "type": "separator", "data": {"model_filename": "test.ckpt", "config": {"output_format": "wav"}}},
                {"id": "output", "type": "output", "data": {"config": {"path": "outputs", "naming": "{basename}_{stem}.{ext}"}}},
            ],
            "edges": [
                {"source": "input", "source_handle": "audio", "target": "split", "target_handle": "audio"},
                {"source": "split", "source_handle": "vocals", "target": "output", "target_handle": "audio"},
            ],
        }
        workflow = Workflow.model_validate(raw)
        self.assertEqual([node.type for node in workflow.nodes], ["input_file", "separator", "output_folder"])
        self.assertEqual(workflow.nodes[0].data["path"], "song.wav")
        self.assertEqual(workflow.nodes[2].data["naming_template"], "{basename}_{stem}.{ext}")
        self.assertEqual(validate_workflow(workflow, _Registry()), [])
        self.assertEqual(topological_order(workflow), ["input", "split", "output"])
        self.assertEqual(RunRequest.model_validate(raw).workflow.id, "workflow-1")

    def test_unknown_separator_stem_is_reported(self) -> None:
        workflow = Workflow.model_validate(
            {
                "nodes": [
                    {"id": "input", "type": "input_file", "data": {"path": "song.wav"}},
                    {"id": "split", "type": "separator", "data": {"model_filename": "test.ckpt"}},
                    {"id": "output", "type": "output_folder", "data": {"path": "outputs"}},
                ],
                "edges": [
                    {"source": "input", "target": "split"},
                    {"source": "split", "source_handle": "drums", "target": "output"},
                ],
            }
        )
        errors = validate_workflow(workflow, _Registry())
        self.assertTrue(any("no output stem: drums" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
