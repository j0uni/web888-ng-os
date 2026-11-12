#!/usr/bin/env python3
"""Make public release metadata; never traverse the private key or backup dirs."""
import json
from pathlib import Path
import sys
from fw_image import sha
kit, version = Path(sys.argv[1]), sys.argv[2]
publish = kit / 'publish'
files = sorted(p for p in publish.iterdir() if p.is_file() and p.suffix == '.raucb')
checksums = []
for p in files:
    digest = sha(p)
    checksums.append(f'{digest}  {p.name}\n')
(publish / 'SHA256SUMS').write_text(''.join(checksums))
(publish / 'latest.json').write_text(json.dumps(dict(version=version,
    bundle=f'web888-{version}.raucb', source='https://jouni.kapsi.fi/web888fw/',
    trust='Owner-signed RAUC bundle; JSON is informational, RAUC signature is authoritative'), indent=2) + '\n')
