# Split production and publication

Use executable absolute paths in the scheduler:

- `/Users/jy/work/repo/openstory-ai-webtoon/scripts/run_producer.sh`
- `/Users/jy/work/repo/openstory-ai-webtoon/scripts/run_publisher.sh`

Optional positional argument is the original episode date (e.g. `2026-09-22`).
`daily_issue.sh DATE`, `run_daily.sh`, and `daily_pipeline.py DATE` retain combined recovery compatibility. Do not schedule these alongside the split jobs.

## Suggested schedule (Asia/Seoul)

- Producer: `10 * * * *` (hourly at :10, maximum 40 minutes).
- Publisher: `0 6 * * *` (06:00 Korean time, publication only).

Before enabling, verify the scheduler's actual timezone/next-run preview is **Asia/Seoul (UTC+09:00)**, not merely the shell's `TZ`. Verify inherited PATH contains Codex, git, npx, curl and the runner can execute under the scheduler account. The shell runtime probe chooses a working Python/XML interpreter. Scheduler timeouts should exceed the producer's 2400s bound and publisher's 3240s bound by at least 60s. Disable the previous combined job. No schedule is installed by these scripts.

Production selects the durable pending date first, then the oldest unsealed draft, then the day after the latest existing episode, stopping at KST today + two days. It never rebases overdue episode dates to wall-clock today. One episode per bounded invocation lets the hourly schedule drain a backlog and then maintain the buffer. Historical gaps before the latest episode are not automatically fabricated/re-numbered.

Production validates source and existing raster bytes, recovers interrupted art workspaces only when source instructions match, and requests only missing/invalid panels using Codex ChatGPT subscription OAuth. No API-key fallback. Defaults: total 2400s, command 900s, art 600s; `WEBTOON_*_TIMEOUT` variables allow bounded overrides. A timeout/transient provider error exits **75**, logs `[YIELD]`, and leaves pending state/art for the next invocation. It does not claim success. Authentication/authorization and permanent errors exit nonzero with `[FAIL]`; fix those rather than repeatedly restarting a whole episode.

## Publication contract

The publisher never invokes Codex, even for login. It checks the ready manifest, source hashes, every raster and sealed canon, selects the oldest unpublished ready episode, refuses a future episode or skipping an earlier draft, then renders/deploys an isolated public tree. It does not upload the repository working directory, untracked draft directories, `.run-logs`, or working future canon. Git commits use the sealed bible with a private index, preserving the producer's current working bible and unrelated staged files. Older pages/assets come from committed history. Publication receipts are written only after push/deploy and HTTP 200/MIME/SHA-256 verification of all new panels and primary routes. A failed publication remains eligible on the next invocation; an explicit date permits authorized retry of the latest publication, but targets older than a committed later reader or verified receipt are rejected to prevent rollback. Legacy historical publication requires committed reader HTML plus metadata and validated raster bytes; unreferenced draft files are excluded. Sealing an older episode against canon with later source drafts fails closed unless that episode already has an intact sealed snapshot.

Both modes hold `.run-logs/daily/pipeline.lock` throughout the operation. Contention exits 75 without changing shared state. Do not delete this file to bypass a running worker.

Durable local state (back up with the repository's working data, not just Git):

- `.run-logs/daily/pending-target`: interrupted production/legacy recovery date.
- `.run-logs/daily/producer-status.json`: ready/buffered/pending/failed status.
- `.run-logs/daily/ready/DATE.json`: exact source/art hash manifest.
- `.run-logs/daily/ready/DATE.bible.md`: canon snapshot for that ready episode.
- `.run-logs/daily/ready/DATE.published`: HTTP-verified publication receipt.
- `.run-logs/daily/art/DATE/`: recoverable interrupted per-panel workspace.

Never manually bless a partial episode by creating a manifest. Run the producer to validate and seal it. A hash mismatch requires investigation, not deleting the ready gate automatically. The 06:00 publisher may return `[WAIT]` when nothing is ready; this deliberately keeps the previous complete episode online rather than exposing a draft.

## Smoke checks (no model or deployment)

There is no `--dry-run` publication flag. Check argument parsing without side effects:

```sh
/Users/jy/work/repo/openstory-ai-webtoon/scripts/run_producer.sh --help
/Users/jy/work/repo/openstory-ai-webtoon/scripts/run_publisher.sh --help
cd /Users/jy/work/repo/openstory-ai-webtoon
/usr/bin/python3 -m unittest discover -s tests -q
```

The suite uses isolated temporary repositories and stubbed model/network commands. After all ready episodes have verified publication receipts, invoking `scripts/run_publisher.sh` without a date returns `[WAIT] no ready episode` with exit 0; it is only a no-op when the ready queue is empty. Never use a date-bearing publisher invocation as a dry run: it performs a real retry/deployment. Likewise, a normal producer invocation may generate billable-to-subscription artwork and is not a dry run.
