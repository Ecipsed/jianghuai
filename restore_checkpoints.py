"""Verify GitHub Release parts and restore the original checkpoint directories."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import tarfile


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


class PartReader:
    def __init__(self, paths):
        self.paths = iter(paths)
        self.current = None

    def read(self, size=-1):
        if size < 0:
            raise ValueError('Only bounded reads are supported')
        remaining, blocks = size, []
        while remaining:
            if self.current is None:
                try:
                    self.current = next(self.paths).open('rb')
                except StopIteration:
                    break
            block = self.current.read(remaining)
            if block:
                blocks.append(block)
                remaining -= len(block)
            else:
                self.current.close()
                self.current = None
        return b''.join(blocks)

    def close(self):
        if self.current:
            self.current.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=Path(__file__).resolve().parent / 'checkpoint-manifest.json')
    parser.add_argument('--assets', type=Path, default=Path('checkpoint-assets'))
    parser.add_argument('--dest', type=Path, default=Path('.'))
    parser.add_argument('--method', choices=['all', 'osd', 'saim'], default='all')
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    methods = ['osd', 'saim'] if args.method == 'all' else [args.method]
    for method in methods:
        item = manifest['methods'][method]
        parts = []
        total = hashlib.sha256()
        for part in item['parts']:
            path = args.assets / part['name']
            if not path.is_file() or path.stat().st_size != part['bytes']:
                raise SystemExit('Missing/incomplete release asset: ' + str(path))
            value = hashlib.sha256()
            with path.open('rb') as stream:
                for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
                    value.update(block)
                    total.update(block)
            if value.hexdigest() != part['sha256']:
                raise SystemExit('Release asset checksum failed: ' + str(path))
            parts.append(path)
            print('Verified:', path.name, flush=True)
        if total.hexdigest() != item['archive_sha256']:
            raise SystemExit('Concatenated archive checksum failed: ' + method)
        if args.verify_only:
            continue
        expected = {entry['path']: entry for entry in item['members']}
        seen = set()
        reader = PartReader(parts)
        try:
            with tarfile.open(fileobj=reader, mode='r|', bufsize=8 * 1024 * 1024) as archive:
                for entry in archive:
                    name = PurePosixPath(entry.name)
                    if (name.is_absolute() or '..' in name.parts or not entry.isfile()
                            or name.parts[:3] != ('continual-pretrain', method, 'checkpoint')
                            or entry.name not in expected or entry.name in seen):
                        raise SystemExit('Unexpected archive entry: ' + entry.name)
                    metadata = expected[entry.name]
                    if entry.size != metadata['bytes']:
                        raise SystemExit('Unexpected file size: ' + entry.name)
                    destination = args.dest.joinpath(*name.parts)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    # Do not replace an existing differing checkpoint silently.
                    if destination.exists():
                        if destination.is_file() and digest(destination) == metadata['sha256']:
                            seen.add(entry.name)
                            print('Already present:', entry.name, flush=True)
                            continue
                        raise SystemExit('Existing file differs; choose another --dest: ' + str(destination))
                    temporary = destination.with_name(destination.name + '.download-partial')
                    value = hashlib.sha256()
                    try:
                        with archive.extractfile(entry) as source, temporary.open('wb') as target:
                            for block in iter(lambda: source.read(8 * 1024 * 1024), b''):
                                value.update(block)
                                target.write(block)
                        if value.hexdigest() != metadata['sha256']:
                            raise SystemExit('Extracted checkpoint checksum failed: ' + entry.name)
                        os.replace(temporary, destination)
                    finally:
                        if temporary.exists():
                            temporary.unlink()
                    seen.add(entry.name)
                    print('Restored:', entry.name, flush=True)
            if seen != set(expected):
                raise SystemExit('Incomplete checkpoint archive: ' + method)
        finally:
            reader.close()
    print('PASS: selected checkpoints verified' + ('' if args.verify_only else ' and restored'), flush=True)


if __name__ == '__main__':
    main()
