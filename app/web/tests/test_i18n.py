from __future__ import annotations

import re
import unittest
from pathlib import Path


STATIC_DIR = Path(__file__).resolve().parents[1] / "static"
LOCALES_DIR = STATIC_DIR / "i18n" / "locales"


def locale_keys(name: str) -> set[str]:
    source = (LOCALES_DIR / name).read_text(encoding="utf-8")
    return set(re.findall(r"^\s*'([^']+)'\s*:", source, flags=re.MULTILINE))


class I18nTests(unittest.TestCase):
    def test_locale_dictionaries_have_identical_keys(self) -> None:
        english = locale_keys("en.js")
        self.assertGreater(len(english), 200)
        self.assertEqual(locale_keys("zh-CN.js"), english)
        self.assertEqual(locale_keys("ja.js"), english)

    def test_static_literal_references_exist_in_every_locale(self) -> None:
        english = locale_keys("en.js")
        app_source = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
        index_source = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
        call_keys = set(re.findall(r"\b(?:t|plural)\(\s*'([^']+)'", app_source))
        attribute_keys = set(
            re.findall(r'data-i18n(?:-placeholder|-title|-aria-label)?="([^"]+)"', index_source)
        )
        referenced = call_keys | attribute_keys
        missing = sorted(key for key in referenced if key not in english and f"{key}.other" not in english)
        self.assertEqual(missing, [])

    def test_language_scripts_load_before_the_application(self) -> None:
        source = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
        positions = [
            source.index('/i18n/locales/en.js'),
            source.index('/i18n/locales/zh-CN.js'),
            source.index('/i18n/locales/ja.js'),
            source.index('/i18n/core.js'),
            source.index('/app.js'),
        ]
        self.assertEqual(positions, sorted(positions))

    def test_frontend_preserves_raw_model_stems_as_port_handles(self) -> None:
        source = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
        self.assertIn("return { id: item, label: item }", source)
        self.assertNotIn("id: item.toLowerCase().replace", source)

    def test_frontend_exposes_audio_preparation_nodes(self) -> None:
        source = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
        self.assertIn("{ type: 'slicer'", source)
        self.assertIn("{ type: 'peak_normalize'", source)
        self.assertIn("node.type === 'slicer'", source)
        self.assertIn("node.type === 'peak_normalize'", source)

    def test_model_taxonomy_keeps_confirmation_as_status(self) -> None:
        source = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
        self.assertIn("unknown: 'other'", source)
        self.assertIn("const functionSections", source)
        self.assertIn("needsConfirmation", source)
        self.assertIn("aria-disabled=\"${unavailable}\"", source)
        self.assertNotIn("unknown: 'needsConfirmation'", source)

    def test_model_library_has_on_demand_details(self) -> None:
        source = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
        index = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
        self.assertIn("function modelPreviewHtml", source)
        self.assertIn("function scheduleModelPreview", source)
        self.assertIn('id="modelPreview"', index)

    def test_node_cards_expose_resize_summaries_and_selected_node_toolbar(self) -> None:
        source = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
        styles = (STATIC_DIR / "styles.css").read_text(encoding="utf-8")
        index = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
        self.assertIn("function startNodeResize", source)
        self.assertIn("function resizeNodeWithKeyboard", source)
        self.assertIn("node.data.width", source)
        self.assertIn("node.data.height", source)
        self.assertIn('data-node-summary="source"', source)
        self.assertIn('data-node-summary="output-folder"', source)
        self.assertIn("function pathLeaf", source)
        self.assertIn("element.addEventListener('pointerdown'", source)
        self.assertIn("function renderNodeToolbar", source)
        self.assertIn("function duplicateSelectedNode", source)
        self.assertIn("const duplicate = deepClone(source)", source)
        self.assertIn('id="nodeToolbar"', index)
        self.assertIn('id="duplicateNodeAction"', index)
        self.assertIn(".node-toolbar", styles)
        self.assertIn("confirmation-align-left", source)
        self.assertIn("confirmation-above", source)
        self.assertIn(".node-toolbar.confirmation-align-left", styles)
        self.assertIn(".node-toolbar.confirmation-above", styles)
        self.assertNotIn("node-delete-popover", source)
        self.assertNotIn("node-menu", source)
        self.assertIn(".node-resize-handle", styles)
        self.assertNotIn("inspector.field.x", source)
        self.assertNotIn("inspector.field.y", source)

    def test_single_audio_uses_browser_upload(self) -> None:
        source = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
        self.assertIn("if (node.type === 'input_file') fields = audioUploadField(c)", source)
        self.assertIn('class="audio-upload-input" type="file"', source)
        self.assertIn("/api/uploads/audio?filename=", source)
        self.assertIn("node.data.config.upload_id = result.id", source)
        self.assertIn("node.data.upload_id", source)

    def test_smart_output_allows_multiple_frontend_connections(self) -> None:
        source = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
        self.assertIn("function inputAllowsMultiple", source)
        self.assertIn("node.data.config?.mode === 'smart_classification'", source)
        self.assertIn("if (!inputAllowsMultiple(inputNode, input.portId))", source)
        self.assertIn("inspector.option.smartClassification", source)
        self.assertIn("node.data.mode = config.mode", source)

    def test_frontend_exposes_workflow_and_run_management(self) -> None:
        source = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
        index = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="workflowManager"', index)
        self.assertIn('id="workflowTabs"', index)
        self.assertIn('id="runManager"', index)
        self.assertIn("async function fetchWorkflows", source)
        self.assertIn("async function fetchRuns", source)
        self.assertIn("async function recoverActiveRun", source)
        self.assertIn("audioflow:draft-v2:", source)
        self.assertIn("openIds:drafts.map(item => item.id)", source)
        self.assertIn("audioflow:workflow-tabs-v2", source)
        self.assertIn("new EventSource('/api/events/runs')", source)
        self.assertIn("loadWorkflowData(run.workflow, { dirty:false, notify:false })", source)
        self.assertNotIn("audioflow:active-run-id", source)
        self.assertNotIn("/api/runs/${encodeURIComponent(id)}/events", source)
        self.assertIn("state.cancelling = lifecycleStatus === 'cancelling'", source)


if __name__ == "__main__":
    unittest.main()
