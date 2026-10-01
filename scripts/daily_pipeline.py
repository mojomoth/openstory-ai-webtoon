#!/usr/bin/env python3
"""Bounded, resumable publication; dependencies are Python's standard library."""
from __future__ import annotations

import datetime as dt
from contextlib import contextmanager
import hashlib
import fcntl
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import time
import zlib
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
SITE = 'https://openstory-ai-webtoon.vercel.app'


class Failure(Exception):
    def __init__(self, message, code=10):
        super().__init__(message)
        self.code = code


def limit(name, default, maximum):
    try:
        value = float(os.environ.get(name, default))
        if not math.isfinite(value) or not 0 < value <= maximum:
            raise ValueError()
        return value
    except ValueError:
        raise Failure('invalid timeout setting: ' + name)


def validate_source(root, date, allow_missing=False):
    folder = root / 'episodes' / date
    required = ['SCENARIO.md', 'ART_PROMPTS.md', 'metadata.json', 'panels/README.md']
    if folder.is_symlink() or (folder / 'panels').is_symlink():
        raise Failure('unsafe source directory')
    if not allow_missing and any(not (folder / name).is_file() for name in required):
        raise Failure('missing source artifacts')
    if any((folder / name).is_symlink() or not (folder / name).read_text(encoding='utf-8').strip()
           for name in required if (folder / name).exists()):
        raise Failure('empty or unsafe source artifacts')
    data = json.loads((folder / 'metadata.json').read_text(encoding='utf-8'))
    if not isinstance(data, dict) or data.get('date') != date:
        raise Failure('metadata date mismatch')
    if not isinstance(data.get('episode'), int) or data['episode'] < 1:
        raise Failure('invalid episode number')
    if any(not isinstance(data.get(k), str) or not data[k].strip() for k in ('title', 'description')):
        raise Failure('missing metadata text')
    if not isinstance(data.get('credits'), dict) or any(
            not isinstance(data['credits'].get(k), str) or not data['credits'][k].strip()
            for k in ('story', 'art')):
        raise Failure('missing metadata credits')
    panels = data.get('panels')
    if not isinstance(panels, list) or not 8 <= len(panels) <= 14:
        raise Failure('invalid panel count/type')
    seen = set()
    for panel in panels:
        if not isinstance(panel, dict) or not isinstance(panel.get('file'), str):
            raise Failure('invalid panel')
        path = Path(panel['file'])
        if (path.is_absolute() or '..' in path.parts or len(path.parts) != 2
                or path.parts[0] != 'panels' or path.suffix.lower() not in ('.png', '.webp')
                or str(path) != panel['file'] or str(path) in seen):
            raise Failure('invalid/duplicate panel path')
        if not isinstance(panel.get('alt'), str) or not panel['alt'].strip():
            raise Failure('invalid panel alt')
        lines = panel.get('dialogue')
        if not isinstance(lines, list) or not lines or not all(isinstance(x, str) and x.strip() for x in lines):
            raise Failure('invalid dialogue')
        if (folder / path).resolve().parent != (folder / 'panels').resolve():
            raise Failure('unsafe panel path')
        seen.add(str(path))
    return data


def validate_png(path):
    """Check complete PNG framing/CRC, legal IHDR, and every inflated scanline.

    Includes Adam7 passes; filters operate on bytes so no image package is needed.
    Bound decompression to the exact declared image size to reject zip bombs.
    """
    raw = path.read_bytes()
    if raw[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError('PNG signature')
    pos, chunks, compressed = 8, [], bytearray()
    header = None
    palette = None
    ended_idat = False
    while pos < len(raw):
        if pos + 12 > len(raw):
            raise ValueError('truncated chunk')
        size = struct.unpack('>I', raw[pos:pos+4])[0]
        kind = raw[pos+4:pos+8]
        end = pos + 12 + size
        if end > len(raw) or not re.fullmatch(b'[A-Za-z]{4}', kind) or kind[2] & 32:
            raise ValueError('invalid chunk')
        data = raw[pos+8:pos+8+size]
        if zlib.crc32(kind + data) & 0xffffffff != struct.unpack('>I', raw[end-4:end])[0]:
            raise ValueError('chunk CRC')
        if not chunks and kind != b'IHDR':
            raise ValueError('missing IHDR')
        if kind == b'IHDR':
            if chunks or size != 13:
                raise ValueError('invalid IHDR')
            header = struct.unpack('>IIBBBBB', data)
        elif kind == b'PLTE':
            if palette is not None or b'IDAT' in chunks or not size or size % 3 or size > 768:
                raise ValueError('invalid palette')
            palette = size // 3
        elif kind == b'IDAT':
            if ended_idat:
                raise ValueError('noncontiguous IDAT')
            compressed.extend(data)
        elif kind == b'IEND':
            if size or end != len(raw) or b'IDAT' not in chunks:
                raise ValueError('invalid IEND')
        elif kind[0] & 32 == 0:
            raise ValueError('unknown critical chunk')
        if b'IDAT' in chunks and kind != b'IDAT':
            ended_idat = True
        chunks.append(kind)
        pos = end
    if not chunks or chunks[-1] != b'IEND':
        raise ValueError('missing IEND')
    w, h, depth, color, compression, filtering, interlace = header
    depths = {0: (1, 2, 4, 8, 16), 2: (8, 16), 3: (1, 2, 4, 8), 4: (8, 16), 6: (8, 16)}
    if (not 0 < w <= 16384 or not 0 < h <= 16384 or depth not in depths.get(color, ())
            or compression or filtering or interlace not in (0, 1)):
        raise ValueError('invalid image header')
    if color == 3 and (palette is None or palette > 2 ** depth):
        raise ValueError('missing/invalid palette')
    if color in (0, 4) and palette is not None:
        raise ValueError('unexpected palette')
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color]
    passes = [(0, 0, 1, 1)] if not interlace else [
        (0, 0, 8, 8), (4, 0, 8, 8), (0, 4, 4, 8), (2, 0, 4, 4),
        (0, 2, 2, 4), (1, 0, 2, 2), (0, 1, 1, 2)]
    rows = []
    for x, y, dx, dy in passes:
        pw, ph = max(0, (w-x+dx-1)//dx), max(0, (h-y+dy-1)//dy)
        if pw and ph:
            rows.append((pw, ph, (pw*channels*depth+7)//8))
    expected = sum(ph*(size+1) for _, ph, size in rows)
    if expected > 128 * 1024 * 1024:
        raise ValueError('image too large')
    decoder = zlib.decompressobj()
    pixels = decoder.decompress(compressed, expected + 1)
    if len(pixels) != expected or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
        raise ValueError('invalid pixel stream')
    offset = 0
    for pw, ph, size in rows:
        previous = bytearray(size)
        bpp = max(1, (channels*depth+7)//8)
        for _ in range(ph):
            filt = pixels[offset]
            if filt > 4:
                raise ValueError('invalid PNG filter')
            row = bytearray(pixels[offset+1:offset+1+size])
            # For indexed images reconstruct filters and check each palette index.
            if color == 3:
                for i in range(size):
                    a = row[i-bpp] if i >= bpp else 0
                    b = previous[i]
                    c = previous[i-bpp] if i >= bpp else 0
                    p = a+b-c
                    pa, pb, pc = abs(p-a), abs(p-b), abs(p-c)
                    predictor = a if pa <= pb and pa <= pc else b if pb <= pc else c
                    row[i] = (row[i] + (0, a, b, (a+b)//2, predictor)[filt]) & 255
                for i in range(pw):
                    value = (row[i*depth//8] >> (8-depth-(i*depth % 8))) & ((1 << depth)-1)
                    if value >= palette:
                        raise ValueError('palette index out of range')
            previous = row
            offset += size+1


class Pipeline:
    def __init__(self):
        self.deadline = time.monotonic() + limit('WEBTOON_TOTAL_TIMEOUT', 3240, 3240)
        self.step_timeout = limit('WEBTOON_STEP_TIMEOUT', 600, 3240)
        self.art_timeout = limit('WEBTOON_ART_TIMEOUT', 300, 3240)
        self.step = 'preflight'
        self.log = None
        self.secrets = []
        self.pending = ROOT / '.run-logs/daily/pending-target'

    def say(self, message):
        for secret in self.secrets:
            if secret:
                message = message.replace(secret, '[REDACTED]')
        print(message, flush=True)
        if self.log:
            self.log.write(message + '\n')
            self.log.flush()

    def run(self, args, *, cwd=ROOT, env=None, timeout=None, allowed=(0,), private=False):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise Failure('total deadline exceeded', 124)
        proc = subprocess.Popen(args, cwd=cwd, env=env, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, start_new_session=True)
        try:
            out, err = proc.communicate(timeout=min(remaining, self.step_timeout, timeout or self.step_timeout))
        except subprocess.TimeoutExpired:
            raise Failure('command deadline exceeded', 124)
        finally:
            # Kill the whole group, including descendants surviving their leader.
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.wait()
        if proc.returncode not in allowed:
            # Never echo command arguments/output: auth/CLIs can contain tokens.
            raise Failure('command failed at ' + self.step, proc.returncode if proc.returncode > 0 else 128-proc.returncode)
        if err and not private:
            self.say('[CLI] completed with diagnostic output (omitted)')
        return out

    def raster(self, path):
        if not path.is_file() or path.is_symlink():
            return False
        try:
            if path.suffix.lower() == '.png':
                validate_png(path)
            else:
                raw = path.read_bytes()
                if (raw[:4] != b'RIFF' or raw[8:12] != b'WEBP'
                        or len(raw) < 20 or struct.unpack('<I', raw[4:8])[0] + 8 != len(raw)):
                    return False
                with tempfile.TemporaryDirectory() as tmp:
                    output = Path(tmp) / 'decoded.png'
                    if shutil.which('sips'):
                        self.run(['sips', '-s', 'format', 'png', str(path), '--out', str(output)])
                    elif shutil.which('dwebp'):
                        self.run(['dwebp', str(path), '-o', str(output)])
                    else:
                        return False
                    validate_png(output)
            return True
        except Failure as exc:
            if exc.code == 124:
                raise
            return False
        except (ValueError, OSError, zlib.error, struct.error):
            return False

    def target(self, explicit):
        if self.pending.exists():
            date = self.pending.read_text().strip()
            if explicit and explicit != date:
                raise Failure('pending target must finish before another date')
            return date
        if explicit:
            return explicit
        today = dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date()
        entries = []
        for folder in sorted((ROOT / 'episodes').glob('*')):
            try:
                date = dt.date.fromisoformat(folder.name)
            except ValueError:
                continue
            if not folder.is_dir() or date > today:
                continue
            try:
                data = validate_source(ROOT, folder.name, allow_missing=True)
            except (Failure, ValueError, OSError):
                return folder.name
            tracked = self.run(['git', 'ls-files', '--', str(folder / 'metadata.json')])
            if not tracked or any(not self.raster(folder / p['file']) for p in data['panels']):
                return folder.name
            entries.append(date)
        return min(max(entries, default=today-dt.timedelta(days=1))+dt.timedelta(days=1), today).isoformat()

    def art_workspace(self, date, panel):
        return self.pending.parent / 'art' / date / Path(panel['file']).name

    def recover_art(self, folder, date, panel):
        work = self.art_workspace(date, panel)
        staged = work / 'episodes' / date
        destination = folder / panel['file']
        # Only recover an output made for these exact source instructions.
        names = ('metadata.json', 'SCENARIO.md', 'ART_PROMPTS.md')
        if (not self.raster(destination) and all((staged / name).is_file()
                and (staged / name).read_bytes() == (folder / name).read_bytes() for name in names)
                and self.raster(staged / panel['file'])):
            replacement = destination.with_suffix(destination.suffix + '.tmp')
            shutil.copyfile(staged / panel['file'], replacement)
            replacement.replace(destination)
            self.say('[RESUME] recovered validated ' + panel['file'])
            shutil.rmtree(work)

    @contextmanager
    def art_attempt(self, date, panel):
        # Keep interrupted work until the next run can validate and recover it.
        work = self.art_workspace(date, panel)
        work.mkdir(parents=True, exist_ok=True)
        yield work
        shutil.rmtree(work)

    def codex(self, command, *args, cwd=ROOT, timeout=None):
        env = dict(os.environ)
        for key in ('OPENAI_API_KEY', 'OPENAI_BASE_URL', 'CODEX_API_KEY'):
            env.pop(key, None)
        return self.run(['codex', command] + (['--ignore-user-config'] if command == 'exec' else []) +
                        ['-c', 'forced_login_method="chatgpt"', '-c', 'model_provider="openai"'] + list(args),
                        cwd=cwd, env=env, timeout=timeout, private=True)

    def auth(self):
        self.step = 'codex-auth'
        if b'Logged in using ChatGPT' not in self.codex('login', 'status'):
            raise Failure('ChatGPT subscription login is required; API-key fallback is forbidden.', 14)

    def execute(self, explicit):
        os.chdir(ROOT)
        self.run(['git', 'rev-parse', '--is-inside-work-tree'])
        for name in ('scripts/publish_daily.py', 'STORY_BIBLE.md', 'CLAUDE.md'):
            if not (ROOT / name).is_file():
                raise Failure('required project files are missing')
        date = self.target(explicit)
        if dt.date.fromisoformat(date).isoformat() != date:
            raise Failure('invalid target date')
        self.pending.parent.mkdir(parents=True, exist_ok=True)
        self.log = (self.pending.parent / (date + '.log')).open('a')
        temp = self.pending.with_suffix('.tmp')
        with temp.open('w') as stream:
            stream.write(date + '\n')
            stream.flush()
            os.fsync(stream.fileno())
        temp.replace(self.pending)
        self.say('[RUNNER] target=' + date)
        folder = ROOT / 'episodes' / date
        authenticated = False
        required = ('SCENARIO.md', 'ART_PROMPTS.md', 'metadata.json', 'panels/README.md')
        for name in required:
            source = folder / name
            if source.exists() and (source.is_symlink() or not source.is_file()
                                    or not source.read_text(encoding='utf-8').strip()):
                raise Failure('empty or unsafe source artifacts')
        if (folder / 'metadata.json').is_file():
            validate_source(ROOT, date, allow_missing=True)
        if not all((folder / x).is_file() for x in required):
            self.auth()
            authenticated = True
            self.step = 'codex-writing'
            self.say('[STEP] Codex: scenario, canon and final dialogue')
            with tempfile.TemporaryDirectory(prefix='webtoon-source-') as tmp:
                work = Path(tmp)
                for name in ('STORY_BIBLE.md', 'CLAUDE.md'):
                    shutil.copy2(ROOT / name, work / name)
                staged = work / 'episodes' / date
                staged.mkdir(parents=True, exist_ok=True)
                (staged / 'panels').mkdir(exist_ok=True)
                for name in required:
                    if (folder / name).is_file():
                        shutil.copy2(folder / name, staged / name)
                previous = sorted(p for p in (ROOT / 'episodes').glob('*')
                                  if p.is_dir() and p.name < date)[-3:]
                for prior in previous:
                    destination = work / 'episodes' / prior.name
                    destination.mkdir()
                    for name in ('SCENARIO.md', 'ART_PROMPTS.md', 'metadata.json'):
                        if (prior / name).is_file():
                            shutil.copy2(prior / name, destination / name)
                self.codex('exec', '--skip-git-repo-check', '--sandbox', 'workspace-write',
                       f'Today is {date}. Read all STORY_BIBLE.md, CLAUDE.md and the previous three episodes. '
                       f'Complete episodes/{date}/SCENARIO.md, ART_PROMPTS.md, metadata.json, panels/README.md. '
                       'Preserve existing work. Write 8–12 connected Korean panels continuing the last image; '
                       'advance one thread and add one clue, respecting memory costs, character state and dates. '
                       f'Metadata date must be {date}, each panel needs unique panels/NN.png or .webp, Korean alt '
                       'and nonempty dialogue array. Credit Codex (ChatGPT subscription). Update only this episode '
                       'and its canon in STORY_BIBLE.md. Do not generate images, commit, deploy, modify code or settings. '
                       'Use only ChatGPT subscription, no API keys, paid APIs or Claude.', cwd=work)
                validate_source(work, date)
                (folder / 'panels').mkdir(parents=True, exist_ok=True)
                for name in required:
                    if not (folder / name).exists():
                        shutil.copy2(staged / name, folder / name)
                canon = work / 'STORY_BIBLE.md'
                if canon.is_symlink() or not canon.read_text(encoding='utf-8').strip():
                    raise Failure('invalid generated canon')
                shutil.copy2(canon, ROOT / 'STORY_BIBLE.md')

        else:
            self.say('[RESUME] existing episode source; skipping writing.')
        self.step = 'validate-source'
        data = validate_source(ROOT, date)
        for panel in data['panels']:
            self.recover_art(folder, date, panel)
        incomplete = [p for p in data['panels'] if not self.raster(folder / p['file'])]
        if incomplete and not authenticated:
            self.auth()
        for panel in incomplete:
            self.step = 'codex-raster-art'
            self.say('[STEP] Codex: generating ' + panel['file'])
            # Codex can only contribute the one validated output from this workspace.
            with self.art_attempt(date, panel) as work:
                for name in ('STORY_BIBLE.md', 'CLAUDE.md'):
                    shutil.copy2(ROOT / name, work / name)
                staged = work / 'episodes' / date
                staged.mkdir(parents=True, exist_ok=True)
                (staged / 'panels').mkdir(exist_ok=True)
                for name in required:
                    shutil.copy2(folder / name, staged / name)
                for p in data['panels']:
                    if self.raster(folder / p['file']):
                        shutil.copy2(folder / p['file'], staged / p['file'])
                asset = staged / panel['file']
                self.codex('exec', '--skip-git-repo-check', '--sandbox', 'workspace-write',
                           f'Read STORY_BIBLE.md, CLAUDE.md and episodes/{date}/ source and metadata. '
                           f'Generate ONLY episodes/{date}/{panel["file"]} as a finished actual 1024x1536 raster '
                           'webtoon panel, with character continuity and room for dialogue overlays. Preserve ink/paper/'
                           'letterpress visual grammar, red only for correction danger. Do not imitate a living artist. '
                           'Use only ChatGPT subscription image generation; no API keys, paid APIs, Claude, SVG, placeholders '
                           'or text-only art. Preserve all existing files and metadata. Do not publish, commit or deploy.',
                           cwd=work, timeout=self.art_timeout)
                if not self.raster(asset):
                    raise Failure('generated raster validation failed')
                destination = folder / panel['file']
                if not self.raster(destination):
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    replacement = destination.with_suffix(destination.suffix + '.tmp')
                    shutil.copyfile(asset, replacement)
                    replacement.replace(destination)
        data = validate_source(ROOT, date)
        if any(not self.raster(folder / p['file']) for p in data['panels']):
            raise Failure('incomplete raster episode')
        self.step = 'validate-publish'
        self.say('[STEP] publishing static outputs')
        self.run([sys.executable, 'scripts/publish_daily.py', '--through', date])
        publication = ['STORY_BIBLE.md', 'index.html', 'archive.html', 'rss.xml', 'sitemap.xml']
        publication += [str(p.with_name('index.html').relative_to(ROOT))
                        for p in sorted((ROOT / 'episodes').glob('*/metadata.json'))
                        if p.parent.name <= date]
        publication += [f'episodes/{date}/{name}' for name in required]
        publication += [f'episodes/{date}/{p["file"]}' for p in data['panels']]
        self.step = 'git-commit'
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(os.environ, GIT_INDEX_FILE=str(Path(tmp) / 'index'))
            head = self.run(['git', 'rev-parse', '--verify', 'HEAD'], allowed=(0, 128))
            self.run(['git', 'read-tree', 'HEAD'] if head else ['git', 'read-tree', '--empty'], env=env)
            self.run(['git', 'add', '--'] + publication, env=env)
            changes = self.run(['git', 'diff', '--cached', '--name-only'], env=env)
            if changes.strip():
                self.run(['git', 'commit', '-m', 'feat: publish episode for ' + date], env=env)
            else:
                self.say('[RESUME] publication already committed; continuing push/deploy.')
            self.run(['git', 'reset', '-q', 'HEAD', '--'] + publication)
        self.step = 'publication-secrets'
        # Keep the existing secret source; never log its output or exception text.
        raw = self.run(['bash', '-c', 'set -ae; source /Users/jy/.secrets; env -0'], private=True)
        secrets = dict(entry.split(b'=', 1) for entry in raw.split(b'\0') if b'=' in entry)
        github = secrets.get(b'GITHUB_TOKEN', b'').decode()
        vercel = secrets.get(b'VERCEL_TOKEN', b'').decode()
        self.secrets = [github, vercel]
        if not github or not vercel:
            raise Failure('publication credentials missing')
        self.step = 'github-push'
        self.run(['git', 'push', f'https://x-access-token:{github}@github.com/mojomoth/openstory-ai-webtoon.git', 'main'], private=True)
        self.step = 'vercel-deploy'
        self.run(['npx', '--yes', 'vercel', '--prod', '--yes', '--name', 'openstory-ai-webtoon', '--token', vercel], private=True)
        self.step = 'verify-production'
        checks = [('index.html', '', {'text/html'}),
                  (f'episodes/{date}/index.html', f'episodes/{date}', {'text/html'}),
                  ('archive.html', 'archive.html', {'text/html'}),
                  ('rss.xml', 'rss.xml', {'application/rss+xml', 'application/xml', 'text/xml'}),
                  ('sitemap.xml', 'sitemap.xml', {'application/xml', 'text/xml'})]
        checks += [(f'episodes/{date}/{p["file"]}', f'episodes/{date}/{p["file"]}',
                    {'image/png' if p['file'].lower().endswith('.png') else 'image/webp'}) for p in data['panels']]
        with tempfile.TemporaryDirectory() as tmp:
            for local, url, mime in checks:
                body = Path(tmp) / 'body'
                info = self.run(['curl', '--fail', '--silent', '--show-error', '--location',
                                 '--connect-timeout', '15', '--max-time', str(min(60, self.step_timeout)),
                                 '--output', str(body), '--write-out', '%{http_code}\n%{content_type}', SITE + '/' + quote(url)])
                status, _, content_type = info.decode().partition('\n')
                if (status != '200' or content_type.split(';')[0].strip().lower() not in mime
                        or not body.is_file() or hashlib.sha256(body.read_bytes()).digest() !=
                        hashlib.sha256((ROOT / local).read_bytes()).digest()):
                    raise Failure('HTTP MIME/hash verification failed for ' + local, 13)
                self.say('[HTTP] verified ' + local)
        self.pending.unlink()
        self.say('[SUCCESS] published: ' + SITE + '/episodes/' + date)


def worker(explicit):
    pipeline = Pipeline()
    def interrupted(signum, frame):
        raise Failure('total deadline or interruption', 124)
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    lock = None
    try:
        pipeline.pending.parent.mkdir(parents=True, exist_ok=True)
        lock = (pipeline.pending.parent / 'pipeline.lock').open('a')
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise Failure('another daily pipeline is running', 75)
        pipeline.execute(explicit)
        return 0
    except Failure as exc:
        pipeline.say('[FAIL] step=' + pipeline.step + ' ' + str(exc))
        return exc.code
    except Exception:
        # No traceback/CLI arguments: they can contain publication credentials.
        pipeline.say('[FAIL] step=' + pipeline.step + ' invalid input or runtime failure')
        return 10
    finally:
        if pipeline.log:
            pipeline.log.close()
        if lock:
            lock.close()


def main():
    if len(sys.argv) > 1 and sys.argv[1] == '--worker':
        return worker(sys.argv[2] if len(sys.argv) > 2 else '')
    total = limit('WEBTOON_TOTAL_TIMEOUT', 3240, 3240)
    proc = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), '--worker'] + sys.argv[1:],
                            start_new_session=True)
    def stop(signum=None, frame=None):
        try:
            os.killpg(proc.pid, signal.SIGTERM)
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()
        except ProcessLookupError:
            pass
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        return proc.wait(timeout=total)
    except subprocess.TimeoutExpired:
        stop()
        print('[FAIL] total deadline exceeded', flush=True)
        return 124


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Failure as exc:
        print('[FAIL] ' + str(exc), flush=True)
        sys.exit(exc.code)
