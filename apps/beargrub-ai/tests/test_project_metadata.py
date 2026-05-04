from __future__ import annotations

import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PROJECT_ROOT.parents[1]


class ProjectMetadataTests(unittest.TestCase):
    def test_requirements_include_phase_1_runtime_dependencies(self):
        requirements = {
            line.strip()
            for line in (PROJECT_ROOT / "requirements.txt").read_text().splitlines()
            if line.strip() and not line.startswith("#")
        }

        self.assertGreaterEqual(
            requirements,
            {
                "chainlit",
                "langchain",
                "langchain-openai",
                "langchain-community",
                "chromadb",
                "openai",
                "requests",
                "python-dotenv",
                "posthog",
            },
        )
        self.assertNotIn("boto3", requirements)

    def test_env_example_declares_only_expected_keys_without_secret_values(self):
        env_text = (PROJECT_ROOT / ".env.example").read_text()

        self.assertIn("OPENAI_API_KEY=", env_text)
        self.assertIn("POSTHOG_API_KEY=", env_text)
        self.assertIn("BEARGRUB_AUTO_INIT=1", env_text)
        self.assertNotIn("sk-", env_text)
        self.assertNotIn("phc_", env_text)

    def test_vulnerability_log_tracks_open_items_and_deferred_work(self):
        log_text = (PROJECT_ROOT / "VULNERABILITY_LOG.md").read_text()

        self.assertIn("External menu availability", log_text)
        self.assertIn("Telemetry privacy", log_text)
        self.assertIn("Deferred To Phase 2 Or Later", log_text)

    def test_phase_2_ci_workflow_runs_required_local_gates(self):
        workflow_text = (REPO_ROOT / ".github" / "workflows" / "beargrub-ai-ci.yml").read_text()

        self.assertIn("python -m pytest tests/ -v", workflow_text)
        self.assertIn("python tests/offline_prompt_eval.py", workflow_text)
        self.assertIn("BEARGRUB_AUTO_INIT", workflow_text)
        self.assertIn("Guard against committed generated or secret files", workflow_text)

    def test_phase_2_plan_documents_ci_and_persistence_work(self):
        plan_text = (REPO_ROOT / "docs" / "PHASE2_PLAN.md").read_text()

        self.assertIn("Slice 1 - CI And Offline Prompt Eval", plan_text)
        self.assertIn("Slice 3 - Persistent Storage", plan_text)
        self.assertIn("OpenAI", plan_text)


if __name__ == "__main__":
    unittest.main()
