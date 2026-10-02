import json
import shutil
import subprocess
import sys
import test_daily_issue


class SplitPipelineTests(test_daily_issue.DailyIssueTests):
    def copy_episode(self, folder, date):
        destination = folder.with_name(date)
        shutil.copytree(folder, destination)
        data = json.loads((destination / 'metadata.json').read_text())
        data['date'] = date
        (destination / 'metadata.json').write_text(json.dumps(data))
        return destination

    def test_historical_reader_excludes_extra_draft_files(self):
        folder, _ = self.complete()
        prior = self.copy_episode(folder, '2026-09-29')
        (prior / 'index.html').write_text('legacy reader')
        (prior / 'draft.txt').write_text('unpublished spoiler')
        (prior / 'panels/extra.png').write_text('unpublished image')
        self.real_git('add', 'episodes/2026-09-29')
        self.real_git('commit', '-m', 'legacy reader with extras')
        self.assertEqual(self.mode('produce').returncode, 0)
        self.stub('npx', '''test -f episodes/2026-09-29/index.html || exit 60
test ! -e episodes/2026-09-29/draft.txt || exit 61
test ! -e episodes/2026-09-29/panels/extra.png || exit 62''')
        result = self.mode('publish')
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_corrupt_committed_historical_raster_blocks_publication(self):
        folder, _ = self.complete()
        self.assertEqual(self.mode('produce').returncode, 0)
        prior = self.copy_episode(folder, '2026-09-29')
        (prior / 'index.html').write_text('legacy reader')
        (prior / 'panels/01.png').write_bytes(b'corrupt')
        self.real_git('add', 'episodes/2026-09-29')
        self.real_git('commit', '-m', 'corrupt legacy reader')
        # A valid working copy must not conceal corrupt committed history.
        self.raster(prior / 'panels/01.png')
        result = self.mode('publish')
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertFalse((self.root / 'events').exists())

    def mode(self, mode, date='2026-09-30'):
        return subprocess.run([sys.executable, str(self.root / 'scripts/daily_pipeline.py'),
                               '--mode', mode, date], env=self.env, capture_output=True,
                              text=True, timeout=15)

    def test_committed_unpublished_draft_is_not_legacy_publication(self):
        folder, data = self.complete()
        self.assertEqual(self.mode('produce').returncode, 0)
        prior = folder.with_name('2026-09-29')
        shutil.copytree(folder, prior)
        data['date'] = prior.name
        (prior / 'metadata.json').write_text(json.dumps(data))
        self.real_git('add', 'episodes/2026-09-29')
        self.real_git('commit', '-m', 'draft only, no published reader')
        result = self.mode('publish')
        self.assertEqual(result.returncode, 75, result.stdout)
        self.assertFalse((self.root / 'events').exists())

    def test_producer_does_not_skip_committed_complete_draft_without_reader(self):
        folder, _ = self.complete()
        self.copy_episode(folder, '2026-09-29')
        self.real_git('add', 'episodes/2026-09-29')
        self.real_git('commit', '-m', 'complete unpublished draft')
        result = self.mode('produce')
        self.assertEqual(result.returncode, 75, result.stdout)
        self.assertIn('oldest pending episode', result.stdout)
        self.assertFalse((self.root / '.run-logs/daily/ready/2026-09-30.json').exists())

    def test_historical_sealing_rejects_later_source_canon(self):
        folder, _ = self.complete()
        later = self.copy_episode(folder, '2026-10-01')
        (self.root / 'STORY_BIBLE.md').write_text('later draft canon')
        for mode in ('recover', 'produce'):
            with self.subTest(mode=mode):
                result = self.mode(mode)
                self.assertEqual(result.returncode, 75, result.stdout)
                self.assertIn('canon provenance', result.stdout)
                self.assertFalse((self.root / '.run-logs/daily/ready/2026-09-30.json').exists())
        self.assertTrue(later.exists())
        self.assertFalse((self.root / 'events').exists())

    def test_out_of_order_source_production_rejected_before_model(self):
        folder, _ = self.complete()
        self.copy_episode(folder, '2026-10-01')
        (folder / 'SCENARIO.md').unlink()
        self.stub('codex', 'echo called >> "$FIXTURE_ROOT/model-calls"; exit 99')
        result = self.mode('produce')
        self.assertEqual(result.returncode, 75, result.stdout)
        self.assertIn('canon provenance', result.stdout)
        self.assertFalse((self.root / 'model-calls').exists())

    def test_exact_ready_snapshot_allows_older_recovery(self):
        folder, _ = self.complete()
        self.assertEqual(self.mode('produce').returncode, 0)
        self.copy_episode(folder, '2026-10-01')
        (self.root / 'STORY_BIBLE.md').write_text('later draft canon')
        result = self.mode('recover')
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.real_git('show', 'HEAD:STORY_BIBLE.md'), b'test fixture')

    def test_explicit_latest_september_22_recovery(self):
        folder, _ = self.complete()
        self.copy_episode(folder, '2026-09-22')
        shutil.rmtree(folder)
        result = self.mode('recover', '2026-09-22')
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertTrue((self.root / '.run-logs/daily/ready/2026-09-22.published').exists())

    def test_rollback_rejected_after_later_committed_reader(self):
        folder, _ = self.complete()
        self.assertEqual(self.mode('produce').returncode, 0)
        self.assertEqual(self.mode('publish').returncode, 0)
        self.copy_episode(folder, '2026-10-01')
        self.assertEqual(self.mode('produce', '2026-10-01').returncode, 0)
        self.assertEqual(self.mode('publish', '2026-10-01').returncode, 0)
        # Committed legacy readers remain a rollback boundary without receipts.
        for path in (self.root / '.run-logs/daily/ready').glob('2026-10-01.*'):
            path.unlink()
        # The guard must also work when B is absent from the working tree.
        shutil.rmtree(self.root / 'episodes/2026-10-01')
        head = self.real_git('rev-parse', 'HEAD')
        events = (self.root / 'events').read_bytes()
        home = (self.root / 'index.html').read_bytes()
        for mode in ('publish', 'recover'):
            result = self.mode(mode)
            self.assertEqual(result.returncode, 75, result.stdout)
            self.assertIn('newer publication', result.stdout)
            self.assertEqual(self.real_git('rev-parse', 'HEAD'), head)
            self.assertEqual((self.root / 'events').read_bytes(), events)
            self.assertEqual((self.root / 'index.html').read_bytes(), home)

    def test_rollback_rejected_by_verified_receipt_without_committed_reader(self):
        folder, _ = self.complete()
        self.assertEqual(self.mode('produce').returncode, 0)
        self.copy_episode(folder, '2026-10-01')
        self.assertEqual(self.mode('produce', '2026-10-01').returncode, 0)
        receipt = self.root / '.run-logs/daily/ready/2026-10-01.published'
        receipt.write_text('HTTP verified\n')
        result = self.mode('publish')
        self.assertEqual(result.returncode, 75, result.stdout)
        self.assertIn('newer publication', result.stdout)
        self.assertFalse((self.root / 'events').exists())

    def recover_backlog(self, explicit):
        folder, _ = self.complete()
        self.assertEqual(self.mode('produce').returncode, 0)
        later = self.copy_episode(folder, '2026-10-01')
        (later / 'panels/08.png').unlink()
        pending = self.root / '.run-logs/daily/pending-target'
        pending.write_text('2026-10-01\n')
        (self.root / 'STORY_BIBLE.md').write_text('later draft canon')
        result = self.mode('recover', '2026-09-30') if explicit else self.runner()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertTrue((pending.parent / 'ready/2026-09-30.published').exists())
        self.assertEqual(pending.read_text(), '2026-10-01\n')
        self.assertFalse((pending.parent / 'ready/2026-10-01.json').exists())
        self.assertEqual((self.root / 'STORY_BIBLE.md').read_text(), 'later draft canon')
        self.assertEqual(self.real_git('show', 'HEAD:STORY_BIBLE.md'), b'test fixture')

    def test_combined_recovery_drains_oldest_ready_before_newer_pending(self):
        self.recover_backlog(explicit=False)

    def test_explicit_combined_recovery_keeps_newer_pending(self):
        self.recover_backlog(explicit=True)

    def test_producer_auth_and_transient_provider_failures_are_distinct(self):
        self.source()
        self.stub('codex', '''if [[ "$*" == *status* ]]; then
  echo 'Logged in using ChatGPT'; exit 0
fi
echo 'HTTP 429 rate limit' >&2; exit 1''')
        result = self.mode('produce')
        self.assertEqual(result.returncode, 75, result.stdout)
        self.assertIn('[YIELD]', result.stdout)
        self.stub('codex', '''if [[ "$*" == *status* ]]; then
  echo 'Logged in using ChatGPT'; exit 0
fi
echo 'HTTP 403 forbidden' >&2; exit 1''')
        result = self.mode('produce')
        self.assertEqual(result.returncode, 14, result.stdout)
        self.assertIn('authorization', result.stdout)
        status = json.loads((self.root / '.run-logs/daily/producer-status.json').read_text())
        self.assertEqual(status['state'], 'failed')

    def test_producer_advances_ready_backlog_without_publishing(self):
        self.complete()
        self.assertEqual(self.mode('produce').returncode, 0)
        result = self.mode('produce', '')
        self.assertIn('target=2026-10-01', result.stdout)
        self.assertNotIn('target=2026-09-30', result.stdout)
        self.assertFalse((self.root / 'events').exists())

    def test_publisher_refuses_future_and_earlier_unready(self):
        self.complete()
        self.assertEqual(self.mode('produce').returncode, 0)
        earlier = self.root / 'episodes/2026-09-29'
        earlier.mkdir()
        (earlier / 'SCENARIO.md').write_text('unfinished')
        result = self.mode('publish')
        self.assertEqual(result.returncode, 75, result.stdout)
        self.assertEqual(self.mode('publish', '2999-01-01').returncode, 75)
        self.assertFalse((self.root / 'events').exists())

    def test_both_modes_share_nonblocking_lock(self):
        import fcntl
        lock = self.root / '.run-logs/daily/pipeline.lock'
        lock.parent.mkdir(parents=True)
        with lock.open('a') as stream:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            for mode in ('produce', 'publish'):
                result = self.mode(mode)
                self.assertEqual(result.returncode, 75, result.stdout)
                self.assertIn('another daily pipeline', result.stdout)
                self.assertFalse((lock.parent / 'producer-status.json').exists())

    def test_producer_timeout_yields_then_recovers_only_missing_art(self):
        folder, data = self.complete()
        asset = folder / data['panels'][-1]['file']
        (self.root / 'valid.png').write_bytes(asset.read_bytes())
        asset.unlink()
        self.stub('codex', '''if [[ "$*" == *status* ]]; then
  echo 'Logged in using ChatGPT'; exit 0
fi
prompt="${!#}"
target="${prompt#*Generate ONLY }"
target="${target%% as a finished*}"
echo "$target" >> "$FIXTURE_ROOT/art-calls"
cp "$FIXTURE_ROOT/valid.png" "$target"
sleep 60''')
        self.env['WEBTOON_ART_TIMEOUT'] = '0.5'
        result = self.mode('produce')
        self.assertEqual(result.returncode, 75, result.stdout)
        self.assertIn('[YIELD]', result.stdout)
        self.assertEqual((self.root / 'art-calls').read_text().strip(),
                         'episodes/2026-09-30/panels/08.png')
        self.stub('codex', 'exit 99')
        result = self.mode('produce')
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn('recovered validated', result.stdout)
        self.assertFalse((self.root / 'events').exists())

    def test_publish_rejects_unready_and_tampered_without_model(self):
        folder, _ = self.complete()
        self.assertEqual(self.mode('publish').returncode, 75)
        self.assertEqual(self.mode('produce').returncode, 0)
        (folder / 'SCENARIO.md').write_text('changed')
        self.assertEqual(self.mode('publish').returncode, 10)
        self.assertFalse((self.root / 'events').exists())

    def test_deployment_excludes_drafts_and_uses_sealed_bible(self):
        self.complete()
        self.assertEqual(self.mode('produce').returncode, 0)
        draft = self.root / 'episodes/2026-10-01'
        draft.mkdir()
        (draft / 'secret-draft.txt').write_text('future spoiler')
        (self.root / 'STORY_BIBLE.md').write_text('future canon')
        self.stub('npx', '''test ! -e episodes/2026-10-01 || exit 61
[[ "$(cat STORY_BIBLE.md)" == 'test fixture' ]] || exit 62
test ! -e .run-logs || exit 63
exit 0''')
        result = self.mode('publish')
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual((self.root / 'STORY_BIBLE.md').read_text(), 'future canon')
        self.assertEqual(self.real_git('show', 'HEAD:STORY_BIBLE.md').strip(), b'test fixture')

    def test_produce_ready_then_publish_without_model(self):
        self.complete()
        produced = self.mode('produce')
        self.assertEqual(produced.returncode, 0, produced.stdout)
        self.assertIn('[READY]', produced.stdout)
        self.assertFalse((self.root / 'events').exists())
        ready = self.root / '.run-logs/daily/ready/2026-09-30.json'
        self.assertTrue(ready.exists())
        result = self.mode('publish')
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn('[SUCCESS]', result.stdout)
