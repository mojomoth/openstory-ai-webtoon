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
