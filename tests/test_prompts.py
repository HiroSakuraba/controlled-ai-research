import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PromptPackTests(unittest.TestCase):
    def test_manifest_hashes_frozen_prompt_files(self):
        manifest = json.loads((ROOT / 'prompts' / 'manifest.json').read_text())
        self.assertEqual(manifest['schema'], 'controlled-ai-prompt-v1')
        for name in ('actor', 'monitor', 'adversary'):
            entry = manifest[name]
            contents = (ROOT / 'prompts' / entry['file']).read_bytes()
            self.assertEqual(hashlib.sha256(contents).hexdigest(), entry['sha256'])
