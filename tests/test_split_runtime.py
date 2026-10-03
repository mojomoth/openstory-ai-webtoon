import json
import unittest
import test_daily_issue
import test_split_pipeline


class SplitRuntimeTests(unittest.TestCase):
    setUp = test_daily_issue.DailyIssueTests.setUp
    stub = test_daily_issue.DailyIssueTests.stub
    source = test_daily_issue.DailyIssueTests.source
    raster = test_daily_issue.DailyIssueTests.raster
    complete = test_daily_issue.DailyIssueTests.complete
    real_git = test_daily_issue.DailyIssueTests.real_git
    mode = test_split_pipeline.SplitPipelineTests.mode

    def test_scheduler_wrapper_reports_intentional_pending_as_deferred(self):
        import subprocess
        import sys
        self.source()
        self.stub('codex', "if [[ \"$*\" == *status* ]]; then echo 'Logged in using ChatGPT'; exit 0; fi; sleep 60")
        self.env['WEBTOON_PYTHON'] = sys.executable
        self.env['WEBTOON_TOTAL_TIMEOUT'] = '0.8'
        result = subprocess.run(['/bin/bash', str(self.root / 'scripts/run_producer.sh')],
                                env=self.env, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn('[DEFERRED]', result.stdout)
        self.assertNotIn('[SUCCESS]', result.stdout)
        self.assertEqual(json.loads((self.root / '.run-logs/daily/producer-status.json').read_text())['state'], 'pending')

    def test_scheduler_wrapper_preserves_real_failures_and_bare_75(self):
        import subprocess
        import sys
        self.env['WEBTOON_PYTHON'] = sys.executable
        for code, message in [(75, '[FAIL] another daily pipeline is running'),
                              (75, '[YIELD] total deadline; production remains pending'),
                              (14, '[FAIL] authorization failed'), (10, '[FAIL] invalid input'),
                              (1, '[YIELD] pending; next producer run resumes: test'),
                              (75, '[YIELD] pending; next producer run resumes: test\n[FAIL] late failure')]:
            with self.subTest(code=code, message=message):
                (self.root / 'scripts/daily_pipeline.py').write_text(
                    'import sys\nprint(' + repr(message) + ')\nsys.exit(' + str(code) + ')\n')
                result = subprocess.run(['/bin/bash', str(self.root / 'scripts/run_producer.sh')],
                                        env=self.env, capture_output=True, text=True, timeout=15)
                self.assertEqual(result.returncode, code, result.stdout)
                self.assertNotIn('[DEFERRED]', result.stdout)

    def test_failed_push_reports_allowlisted_cause_without_credentials(self):
        self.complete()
        self.assertEqual(self.mode('produce').returncode, 0)
        self.stub('git', f'''if [[ "$1" == push ]]; then
  echo 'error: RPC failed; HTTP 408 fake-github-secret fake-vercel-secret' >&2
  exit 1
fi
exec '{self.git}' "$@"''')
        result = self.mode('publish')
        self.assertEqual(result.returncode, 1)
        self.assertIn('Git push failed: HTTP 408', result.stdout)
        self.assertNotIn('fake-github-secret', result.stdout)
        self.assertNotIn('fake-vercel-secret', result.stdout)
        self.assertFalse((self.root / '.run-logs/daily/ready/2026-09-30.published').exists())

    def test_total_timeout_yields_pending_not_success(self):
        self.source()
        self.stub('codex', '''if [[ "$*" == *status* ]]; then
  echo 'Logged in using ChatGPT'; exit 0
fi
sleep 60''')
        self.env['WEBTOON_TOTAL_TIMEOUT'] = '0.8'
        result = self.mode('produce')
        self.assertEqual(result.returncode, 75, result.stdout)
        self.assertIn('[YIELD]', result.stdout)
        status = json.loads((self.root / '.run-logs/daily/producer-status.json').read_text())
        self.assertEqual(status['state'], 'pending')

    def test_sealed_future_episode_cannot_publish(self):
        folder, data = self.complete()
        future = folder.with_name('2999-01-01')
        folder.rename(future)
        data['date'] = future.name
        (future / 'metadata.json').write_text(json.dumps(data))
        result = self.mode('produce', future.name)
        self.assertEqual(result.returncode, 0, result.stdout)
        result = self.mode('publish', future.name)
        self.assertEqual(result.returncode, 75, result.stdout)
        self.assertFalse((self.root / 'events').exists())

    def test_isolated_deployment_explicitly_targets_existing_project(self):
        self.complete()
        self.assertEqual(self.mode('produce').returncode, 0)
        self.stub('npx', '''[[ "$*" == *"--project openstory-ai-webtoon"* ]] || exit 64''')
        result = self.mode('publish')
        self.assertEqual(result.returncode, 0, result.stdout)
