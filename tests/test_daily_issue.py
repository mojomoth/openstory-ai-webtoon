import os
import json
import sys
import time
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
        self.git = shutil.which('git')
        subprocess.run([self.git, 'init', '-q', '-b', 'main', str(self.root)], check=True)
        for key, value in [('user.email', 'test@example.invalid'), ('user.name', 'Test')]:
            subprocess.run([self.git, '-C', str(self.root), 'config', key, value], check=True)
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        self.env = dict(os.environ, PATH=str(self.bin) + ':' + os.environ['PATH'])
        for key in list(self.env):
            if key.startswith('WEBTOON_'):
                del self.env[key]
        self.env['FIXTURE_ROOT'] = str(self.root)
        self.stub('claude', 'exit 99')
        self.stub('codex', 'exit 99')
        self.stub('git', f'''if [[ "$1" == push ]]; then
  echo push >> "$FIXTURE_ROOT/events"
  echo "$*" >&2
  exit "${{PUSH_EXIT:-0}}"
fi
exec '{self.git}' "$@"''')
        self.stub('bash', '''if [[ "$1" == -c && "$2" == *"source /Users/jy/.secrets"* ]]; then
  printf 'GITHUB_TOKEN=fake-github-secret\\0VERCEL_TOKEN=fake-vercel-secret\\0'
  exit 0
fi
exec /bin/bash "$@"''')
        self.stub('npx', '''echo deploy >> "$FIXTURE_ROOT/events"
echo "$*" >&2
exit "${DEPLOY_EXIT:-0}"''')
        curl = self.bin / 'curl'
        curl.write_text('#!' + sys.executable + '\n' + '''import os, sys, pathlib, shutil
root = pathlib.Path(os.environ['FIXTURE_ROOT'])
args = sys.argv[1:]
url = args[-1].split('.app/', 1)[1]
path = url or 'index.html'
if path.startswith('episodes/') and len(path.split('/')) == 2:
    path += '/index.html'
with (root / 'http-calls').open('a') as f: f.write(path + '\\n')
output = pathlib.Path(args[args.index('--output')+1])
shutil.copyfile(root / path, output)
mime = 'image/png' if path.endswith('.png') else 'application/xml' if path.endswith('.xml') else 'text/html'
if os.environ.get('BAD_HASH') == path: output.write_bytes(b'stale')
if os.environ.get('BAD_MIME') == path: mime = 'text/plain'
print('200\\n' + mime, end='')
''')
        curl.chmod(0o755)

    def stub(self, name, body):
        path = self.bin / name
        path.write_text('#!/bin/bash\n' + body + '\n')
        path.chmod(0o755)

    def run_daily(self):
        return subprocess.run(['bash', str(self.root / 'scripts/daily_issue.sh'), '2026-09-30'],
                              env=self.env, capture_output=True, text=True, timeout=15)

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

    def raster(self, path):
        import struct
        import zlib
        def chunk(kind, data):
            return (struct.pack('>I', len(data)) + kind + data
                    + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff))
        path.write_bytes(b'\x89PNG\r\n\x1a\n'
                         + chunk(b'IHDR', struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0))
                         + chunk(b'IDAT', zlib.compress(b'\0\xff\0\0'))
                         + chunk(b'IEND', b''))

    def test_chatgpt_auth_status_on_stderr_is_accepted(self):
        self.source()
        self.stub('codex', '''if [[ "$*" == *"status"* ]]; then
  echo 'Logged in using ChatGPT' >&2; exit 0
fi
exit 43''')
        result = self.run_daily()
        self.assertEqual(result.returncode, 43, result.stdout)

    def test_complete_rasters_skip_all_codex_including_auth(self):
        folder, data = self.source()
        for panel in data['panels']:
            self.raster(folder / panel['file'])
        self.stub('codex', '''echo "$*" >> codex-calls
if [[ "$*" == *"status"* ]]; then
  echo 'Logged in using ChatGPT'; exit 0
fi
exit 43''')
        result = self.run_daily()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertFalse((self.root / 'codex-calls').exists(),
                         'complete valid raster episode invoked Codex: ' +
                         ((self.root / 'codex-calls').read_text()
                          if (self.root / 'codex-calls').exists() else ''))

    def complete(self):
        folder, data = self.source()
        for panel in data['panels']:
            self.raster(folder / panel['file'])
        return folder, data

    def real_git(self, *args):
        return subprocess.check_output([self.git, '-C', str(self.root), *args])

    def runner(self):
        return subprocess.run(['/bin/bash', str(self.root / 'scripts/run_daily.sh')],
                              env=self.env, capture_output=True, text=True, timeout=15)

    def test_selection_skips_committed_legacy_episode_without_source_readme(self):
        folder, data = self.complete()
        prior = folder.with_name('2026-09-29')
        shutil.copytree(folder, prior)
        data['date'] = prior.name
        (prior / 'metadata.json').write_text(json.dumps(data))
        (prior / 'panels/README.md').unlink()
        self.real_git('add', 'episodes/2026-09-29')
        self.real_git('commit', '-m', 'legacy published episode')
        result = self.runner()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn('target=2026-09-30', result.stdout)

    def test_committed_retry_pushes_and_deploys_and_preserves_index(self):
        folder, _ = self.complete()
        (folder / 'unrelated.txt').write_text('not publication')
        orphan = self.root / 'episodes/2026-01-01/index.html'
        orphan.parent.mkdir(parents=True)
        orphan.write_text('not rendered by publisher')
        (self.root / 'unrelated').write_text('keep staged')
        self.real_git('add', 'unrelated')
        before = self.real_git('ls-files', '--stage', '--', 'unrelated')
        first = self.run_daily()
        self.assertEqual(first.returncode, 0, first.stdout)
        self.assertEqual(self.real_git('ls-files', '--stage', '--', 'unrelated'), before)
        tracked = self.real_git('ls-tree', '-r', '--name-only', 'HEAD')
        self.assertNotIn(b'unrelated', tracked)
        self.assertNotIn(b'2026-01-01', tracked)
        head = self.real_git('rev-parse', 'HEAD')
        second = self.run_daily()
        self.assertEqual(second.returncode, 0, second.stdout)
        self.assertEqual(self.real_git('rev-parse', 'HEAD'), head)
        self.assertEqual((self.root / 'events').read_text().splitlines(),
                         ['push', 'deploy', 'push', 'deploy'])
        self.assertEqual(len((self.root / 'http-calls').read_text().splitlines()), 26)
        self.assertFalse((self.root / '.run-logs/daily/pending-target').exists())

    def test_commit_push_deploy_failures_propagate_and_resume(self):
        self.complete()
        hook = self.root / '.git/hooks/pre-commit'
        hook.write_text('#!/bin/sh\nexit 1\n')
        hook.chmod(0o755)
        result = self.run_daily()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertFalse((self.root / 'events').exists())
        pending = self.root / '.run-logs/daily/pending-target'
        self.assertEqual(pending.read_text().strip(), '2026-09-30')
        hook.unlink()
        self.env['PUSH_EXIT'] = '41'
        result = self.runner()
        self.assertEqual(result.returncode, 41, result.stdout)
        self.assertEqual((self.root / 'events').read_text().splitlines(), ['push'])
        self.env['PUSH_EXIT'] = '0'
        self.env['DEPLOY_EXIT'] = '42'
        head = self.real_git('rev-parse', 'HEAD')
        result = self.runner()
        self.assertEqual(result.returncode, 42, result.stdout)
        self.assertTrue(pending.exists())
        self.assertEqual(self.real_git('rev-parse', 'HEAD'), head)
        self.env['DEPLOY_EXIT'] = '0'
        result = self.runner()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn('target=2026-09-30', result.stdout)
        self.assertNotIn('fake-github-secret', result.stdout + result.stderr)
        self.assertNotIn('fake-vercel-secret', result.stdout + result.stderr)
        self.assertFalse(pending.exists())

    def test_http_mime_and_hash_failures_keep_pending(self):
        self.complete()
        for var, path in [('BAD_MIME', 'index.html'), ('BAD_HASH', 'archive.html'),
                          ('BAD_HASH', 'episodes/2026-09-30/panels/08.png')]:
            with self.subTest(var=var, path=path):
                self.env[var] = path
                result = self.run_daily()
                self.assertEqual(result.returncode, 13, result.stdout)
                self.assertTrue((self.root / '.run-logs/daily/pending-target').exists())
                del self.env[var]

    def test_empty_and_malformed_source_refused(self):
        for name in ['SCENARIO.md', 'ART_PROMPTS.md', 'panels/README.md', 'metadata.json']:
            folder, _ = self.complete()
            (folder / name).write_text('  ')
            result = self.run_daily()
            self.assertEqual(result.returncode, 10, result.stdout)
            self.assertNotIn('[STEP] Codex:', result.stdout)
            self.assertFalse((self.root / 'events').exists())
        folder, _ = self.complete()
        (folder / 'metadata.json').write_text('{invalid json')
        self.assertEqual(self.run_daily().returncode, 10)

    def test_only_incomplete_assets_regenerated_and_good_files_preserved(self):
        folder, data = self.complete()
        good = (folder / data['panels'][0]['file']).read_bytes()
        (self.root / 'valid.png').write_bytes(good)
        (folder / data['panels'][1]['file']).write_bytes(good[:-5])
        (folder / data['panels'][2]['file']).unlink()
        self.stub('codex', '''if [[ "$*" == *status* ]]; then
  echo 'Logged in using ChatGPT'; exit 0
fi
printf '%s\\n' "$*" >> "$FIXTURE_ROOT/art-calls"
for path in episodes/*/panels/*.png; do echo damaged > "$path"; done
prompt="${!#}"
target="${prompt#*Generate ONLY }"
target="${target%% as a finished*}"
cp "$FIXTURE_ROOT/valid.png" "$target"
''')
        result = self.run_daily()
        self.assertEqual(result.returncode, 0, result.stdout)
        calls = (self.root / 'art-calls').read_text().splitlines()
        self.assertEqual(len(calls), 2)
        self.assertIn('panels/02.png as a finished', calls[0])
        self.assertIn('panels/03.png as a finished', calls[1])
        for p in data['panels']:
            self.assertEqual((folder / p['file']).read_bytes(), good)

    def test_corrupt_generated_raster_refused_before_commit(self):
        folder, data = self.complete()
        (folder / data['panels'][0]['file']).write_bytes(b'not a png')
        self.stub('codex', '''if [[ "$*" == *status* ]]; then
  echo 'Logged in using ChatGPT'; exit 0
fi
prompt="${!#}"
target="${prompt#*Generate ONLY }"
target="${target%% as a finished*}"
printf '\\211PNG\\r\\n\\032\\n' > "$target"
''')
        result = self.run_daily()
        self.assertEqual(result.returncode, 10, result.stdout)
        self.assertNotIn('[STEP] publishing', result.stdout)
        self.assertFalse((self.root / 'events').exists())

    def test_timeout_kills_child_process_group_and_keeps_pending(self):
        for kind in ['STEP', 'TOTAL', 'ART']:
            with self.subTest(timeout=kind):
                self.source()
                self.env['WEBTOON_' + kind + '_TIMEOUT'] = '0.8'
                self.stub('codex', '''if [[ "$*" == *status* ]]; then
  echo 'Logged in using ChatGPT'; exit 0
fi
sleep 60 &
echo $! > "$FIXTURE_ROOT/child-pid"
wait
''')
                start = time.monotonic()
                result = self.run_daily()
                self.assertEqual(result.returncode, 124, result.stdout)
                self.assertLess(time.monotonic() - start, 4)
                pid = (self.root / 'child-pid').read_text().strip()
                state = subprocess.run(['ps', '-o', 'stat=', '-p', pid], capture_output=True, text=True).stdout.strip()
                self.assertTrue(not state or state.startswith('Z'), state)
                self.assertTrue((self.root / '.run-logs/daily/pending-target').exists())
                del self.env['WEBTOON_' + kind + '_TIMEOUT']

    def test_missing_source_completion_preserves_existing_source_and_images(self):
        folder, data = self.complete()
        preserved = (folder / 'ART_PROMPTS.md').read_bytes()
        images = [(folder / p['file']).read_bytes() for p in data['panels']]
        (folder / 'SCENARIO.md').unlink()
        self.stub('codex', '''if [[ "$*" == *status* ]]; then
  echo 'Logged in using ChatGPT'; exit 0
fi
echo completed > episodes/2026-09-30/SCENARIO.md
echo unwanted-change > episodes/2026-09-30/ART_PROMPTS.md
mkdir -p episodes/2026-09-30/panels
echo corrupt > episodes/2026-09-30/panels/01.png
''')
        result = self.run_daily()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual((folder / 'ART_PROMPTS.md').read_bytes(), preserved)
        self.assertEqual([(folder / p['file']).read_bytes() for p in data['panels']], images)
        self.assertNotIn('[STEP] Codex: generating', result.stdout)

    def test_interrupted_art_recovers_valid_output_without_codex(self):
        folder, data = self.complete()
        asset = folder / data['panels'][0]['file']
        (self.root / 'valid.png').write_bytes(asset.read_bytes())
        asset.unlink()
        self.stub('codex', '''if [[ "$*" == *status* ]]; then
  echo 'Logged in using ChatGPT'; exit 0
fi
prompt="${!#}"
target="${prompt#*Generate ONLY }"
target="${target%% as a finished*}"
cp "$FIXTURE_ROOT/valid.png" "$target"
sleep 60
''')
        self.env['WEBTOON_ART_TIMEOUT'] = '0.5'
        result = self.run_daily()
        self.assertEqual(result.returncode, 124, result.stdout)
        self.stub('codex', 'exit 99')
        result = self.runner()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn('recovered validated', result.stdout)
        self.assertEqual(asset.read_bytes(), (self.root / 'valid.png').read_bytes())

    def test_explicit_python_probe_and_invalid_limits(self):
        self.complete()
        python = self.bin / 'selected-python'
        python.write_text('#!/bin/bash\necho selected >> "$FIXTURE_ROOT/python-calls"\nexec '
                          + ('/usr/bin/python3' if sys.platform == 'darwin' else sys.executable)
                          + ' "$@"\n')
        python.chmod(0o755)
        self.env['WEBTOON_PYTHON'] = str(python)
        result = self.run_daily()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(len((self.root / 'python-calls').read_text().splitlines()), 2)
        self.env['WEBTOON_TOTAL_TIMEOUT'] = '3300'
        result = self.run_daily()
        self.assertEqual(result.returncode, 10, result.stdout)
        python.write_text('#!/bin/bash\nexit 3\n')
        result = self.run_daily()
        self.assertEqual(result.returncode, 10, result.stdout)
        self.assertIn('runtime probe failed', result.stderr)

    def test_python_probe_timeout_kills_its_child_group(self):
        self.stub('hanging-python', '''sleep 60 &
echo $! > "$FIXTURE_ROOT/probe-child"
wait
''')
        self.env['WEBTOON_PYTHON'] = str(self.bin / 'hanging-python')
        start = time.monotonic()
        result = self.run_daily()
        self.assertEqual(result.returncode, 10, result.stdout + result.stderr)
        self.assertLess(time.monotonic() - start, 8)
        pid = (self.root / 'probe-child').read_text().strip()
        state = subprocess.run(['ps', '-o', 'stat=', '-p', pid], capture_output=True, text=True).stdout.strip()
        self.assertTrue(not state or state.startswith('Z'), state)

    def test_png_crc_zlib_scanlines_and_webp_decoder(self):
        import importlib.util
        import struct
        import zlib
        spec = importlib.util.spec_from_file_location('daily_pipeline', ROOT / 'scripts/daily_pipeline.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        path = self.root / 'image.png'
        self.raster(path)
        valid = path.read_bytes()
        def chunk(kind, data):
            return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind+data) & 0xffffffff)
        header = valid[:33]
        for bad in [valid[:-1], valid+b'extra', valid[:40]+b'X'+valid[41:],
                    header+chunk(b'IDAT', b'not zlib')+chunk(b'IEND', b''),
                    header+chunk(b'IDAT', zlib.compress(b'\x05\0\0\0'))+chunk(b'IEND', b''),
                    header+chunk(b'IDAT', zlib.compress(b'\0'))+chunk(b'IEND', b'')]:
            path.write_bytes(bad)
            self.assertFalse(module.Pipeline().raster(path))
        path.write_bytes(valid)
        self.assertTrue(module.Pipeline().raster(path))
        # A plausible RIFF header is insufficient: an actual decoder must accept it.
        path = self.root / 'image.webp'
        path.write_bytes(b'RIFF'+struct.pack('<I', 12)+b'WEBPVP8 '+b'\0'*4)
        self.assertFalse(module.Pipeline().raster(path))

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
printf '%s\\n' "$*" >> "$FIXTURE_ROOT/calls"
exit 42''')
        result = self.run_daily()
        self.assertEqual(result.returncode, 42, result.stdout)
        calls = (self.root / 'calls').read_text().splitlines()
        self.assertEqual(len(calls), 1)
        self.assertIn('forced_login_method="chatgpt"', calls[0])
        self.assertNotIn('[STEP] publishing', result.stdout)


if __name__ == '__main__':
    unittest.main()
