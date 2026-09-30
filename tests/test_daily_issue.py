import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DailyIssueTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        shutil.copytree(ROOT / 'scripts', self.root / 'scripts')
        for name in ('CLAUDE.md', 'STORY_BIBLE.md'):
            (self.root / name).write_text('test fixture')
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        self.env = dict(os.environ, PATH=str(self.bin) + ':' + os.environ['PATH'])
        self.stub('claude', 'exit 99')

    def stub(self, name, body):
        path = self.bin / name
        path.write_text('#!/bin/bash\n' + body + '\n')
        path.chmod(0o755)

    def run_daily(self):
        return subprocess.run(['bash', str(self.root / 'scripts/daily_issue.sh'), '2026-09-30'],
                              env=self.env, capture_output=True, text=True)

    def source(self):
        import json
        folder = self.root / 'episodes/2026-09-30'
        (folder / 'panels').mkdir(parents=True, exist_ok=True)
        for name in ('SCENARIO.md', 'ART_PROMPTS.md', 'panels/README.md'):
            (folder / name).write_text('fixture source')
        data = {'date': '2026-09-30', 'episode': 1, 'title': 'fixture',
                'description': 'fixture', 'credits': {'story': 'Codex', 'art': 'Codex'},
                'panels': [{'file': f'panels/{i:02d}.png', 'alt': '한국어',
                            'dialogue': ['대사']} for i in range(1, 9)]}
        (folder / 'metadata.json').write_text(json.dumps(data))
        return folder, data

    def test_invalid_source_cannot_reach_art(self):
        import json
        for mutation in ('date', 'duplicate', 'traversal', 'dialogue'):
            with self.subTest(mutation=mutation):
                folder, data = self.source()
                if mutation == 'date': data['date'] = '2026-09-29'
                if mutation == 'duplicate': data['panels'][1]['file'] = data['panels'][0]['file']
                if mutation == 'traversal': data['panels'][0]['file'] = '../outside.png'
                if mutation == 'dialogue': data['panels'][0]['dialogue'] = 'not an array'
                (folder / 'metadata.json').write_text(json.dumps(data))
                self.stub('codex', '''if [[ "$*" == *"status"* ]]; then
  echo 'Logged in using ChatGPT'; exit 0
fi
exit 0''')
                result = self.run_daily()
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertNotIn('[STEP] Codex: generating', result.stdout)

    def test_no_claude_executable_invocations(self):
        import re
        for name in ('daily_issue.sh', 'run_daily.sh'):
            text = (ROOT / 'scripts' / name).read_text()
            self.assertIsNone(re.search(r'(?m)^\s*(?:exec\s+)?claude\s', text))

    def test_api_key_login_is_rejected(self):
        self.stub('codex', "echo 'Logged in using an API key'; exit 0")
        result = self.run_daily()
        self.assertEqual(result.returncode, 14, result.stdout)
        self.assertNotIn('[STEP] Codex', result.stdout)

    def test_success_without_source_is_rejected(self):
        self.stub('codex', '''if [[ "$*" == *"status"* ]]; then
  echo 'Logged in using ChatGPT'
fi
exit 0''')
        result = self.run_daily()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('missing source artifacts', result.stdout)
        self.assertNotIn('[STEP] Codex: generating', result.stdout)

    def test_art_failure_propagates_for_valid_resumed_source(self):
        self.source()
        self.stub('codex', '''if [[ "$*" == *"status"* ]]; then
  echo 'Logged in using ChatGPT'; exit 0
fi
[[ -z "${OPENAI_API_KEY+x}" && -z "${CODEX_API_KEY+x}" ]] || exit 98
exit 43''')
        self.env.update(OPENAI_API_KEY='test-only', CODEX_API_KEY='test-only')
        result = self.run_daily()
        self.assertEqual(result.returncode, 43, result.stdout)
        self.assertIn('[RESUME]', result.stdout)
        self.assertNotIn('[STEP] publishing', result.stdout)

    def test_codex_failure_propagates_without_art_or_publish(self):
        self.stub('codex', '''if [[ "$*" == *"status"* ]]; then
  echo 'Logged in using ChatGPT'; exit 0
fi
printf '%s\\n' "$*" >> calls
exit 42''')
        result = self.run_daily()
        self.assertEqual(result.returncode, 42, result.stdout)
        calls = (self.root / 'calls').read_text().splitlines()
        self.assertEqual(len(calls), 1)
        self.assertIn('forced_login_method="chatgpt"', calls[0])
        self.assertNotIn('[STEP] publishing', result.stdout)


if __name__ == '__main__':
    unittest.main()
