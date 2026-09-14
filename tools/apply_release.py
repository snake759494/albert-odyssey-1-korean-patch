"""Apply Albert Odyssey 1 v1.0.0 with input, patch and output hash verification."""
import argparse
import hashlib
from pathlib import Path
import subprocess
import sys

SOURCE_SIZE = 1048576
SOURCE_MD5 = '8822eb60ec69ede557c3294bae005b32'
SOURCE_SHA = 'abc9ee63a624dbabfd255774a254517a46be54c37aa26a89db2a299277548190'
PATCH_SHA = '57daeca98a2ca096429337e1d0e4b87dfc163ef02a8b2595d059ee2c38e3f719'
OUTPUT_SHA = '5509b4d8afda2bc497c2245bd2824629a703eac907d65660347041ffba2f183b'

def digest(path, kind='sha256'):
    h = hashlib.new(kind)
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('xdelta', 'source', 'patch', 'output'):
        parser.add_argument('--' + name, required=True, type=Path)
    args = parser.parse_args()
    source, patch, output, exe = (p.resolve() for p in (args.source, args.patch, args.output, args.xdelta))
    if output.exists() or output in (source, patch, exe):
        raise ValueError('Output must be a new file, different from all inputs.')
    if source.stat().st_size != SOURCE_SIZE or digest(source, 'md5') != SOURCE_MD5 or digest(source) != SOURCE_SHA:
        raise ValueError('Original ROM hash mismatch. Use the unmodified Japanese ROM listed in README.')
    if digest(patch) != PATCH_SHA:
        raise ValueError('Patch SHA-256 mismatch.')
    print('Input and patch verified. Applying...', flush=True)
    # Reserve a new file atomically. Stream decoded output into it, never overwrite an existing path.
    with output.open('xb') as out:
        subprocess.run([str(exe), '-d', '-c', '-s', str(source), str(patch)], stdout=out, check=True)
    if output.stat().st_size != 2097152 or digest(output) != OUTPUT_SHA:
        raise ValueError('Output verification failed. Do not use the resulting file.')
    print('PASS: output SHA-256 = ' + OUTPUT_SHA)

if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print('ERROR: ' + str(exc), file=sys.stderr)
        sys.exit(1)
