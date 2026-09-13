#!/usr/bin/env python3
"""Append a CARTO basemap API key to every CARTO tile URL across ~/Experiments.

CARTO began watermarking keyless tile requests ("API KEY REQUIRED") in September
2026. Keys are free up to 5M tile requests a month; request one at
https://carto.com/basemaps/apikey.

    python3 machine/carto-key-sweep.py --dry-run
    python3 machine/carto-key-sweep.py --key YOUR_KEY
"""
import argparse, os, re, sys, collections

ROOT = os.path.expanduser('~/Experiments')
SKIP_DIRS = {'.git', '.claude', 'node_modules', '.venv', 'venv', '__pycache__', 'dist', 'build'}
EXTS = ('.html', '.js', '.jsx', '.ts', '.tsx', '.json', '.md')

# A CARTO *raster* tile URL, up to but not including any existing query string.
# Only the .png endpoints are watermarked; the vector tiles behind the GL styles
# (basemaps.cartocdn.com/gl/...) still serve clean without a key, so they are left
# alone. Bare https://carto.com/ attribution links deliberately do not match.
URL = re.compile(
    r'https://(?:\{s\}\.|[a-d]\.)?basemaps\.cartocdn\.com/(?!gl/)[^\s"\'`)]*?\.png'
    r'|https://cartodb-basemaps-(?:\{s\}|[a-d])\.global\.ssl\.fastly\.net/[^\s"\'`)]*?\.png'
)

def rewrite(text, key):
    """Return (new_text, n_changed). Skips URLs that already carry a key."""
    n = 0
    def sub(m):
        nonlocal n
        url = m.group(0)
        tail = text[m.end():m.end() + 12]
        if tail.startswith('?key=') or tail.startswith('&key='):
            return url
        n += 1
        return url + '?key=' + key
    return URL.sub(sub, text), n

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--key', help='CARTO basemap API key')
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()
    if not a.dry_run and not a.key:
        sys.exit('need --key, or --dry-run to preview')
    key = a.key or 'DRYRUNKEY'

    per_project = collections.Counter()
    files = 0
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if not fn.endswith(EXTS):
                continue
            path = os.path.join(dirpath, fn)
            try:
                src = open(path, encoding='utf-8').read()
            except (UnicodeDecodeError, OSError):
                continue
            out, n = rewrite(src, key)
            if not n:
                continue
            files += 1
            per_project[os.path.relpath(path, ROOT).split(os.sep)[0]] += n
            if not a.dry_run:
                open(path, 'w', encoding='utf-8').write(out)

    verb = 'would rewrite' if a.dry_run else 'rewrote'
    for proj, n in sorted(per_project.items()):
        print(f'{proj:38s} {n:3d} urls')
    print(f'\n{verb} {sum(per_project.values())} urls in {files} files '
          f'across {len(per_project)} projects')

if __name__ == '__main__':
    main()
