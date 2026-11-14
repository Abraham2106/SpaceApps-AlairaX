"""Content-addressed raw snapshots and a URL-keyed latest-snapshot index."""

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    temporary.replace(path)


class RawCache:
    def __init__(self, directory: str | Path, *, timeout: float = 30, attempts: int = 3):
        if timeout <= 0 or not 1 <= attempts <= 5:
            raise ValueError('positive timeout and 1–5 attempts required')
        self.directory = Path(directory)
        self.timeout, self.attempts = timeout, attempts

    def get(self, url: str, *, refresh: bool = False, offline: bool = False) -> tuple[bytes, dict]:
        if refresh and offline:
            raise ValueError('refresh and offline are mutually exclusive')
        key = sha256(url.encode('utf-8')).hexdigest()
        index_path = self.directory / f'{key}.json'
        if index_path.exists() and not refresh:
            metadata = json.loads(index_path.read_text(encoding='utf-8'))
            digest = metadata.get('sha256', '')
            if metadata.get('url') != url or len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
                raise ValueError('invalid cache metadata')
            body = (self.directory / f'{digest}.body').read_bytes()
            if sha256(body).hexdigest() != digest:
                raise ValueError('raw cache checksum mismatch; explicitly refresh it')
            return body, metadata
        if offline:
            raise FileNotFoundError(f'No cached response for {url}')
        request = Request(url, headers={'User-Agent': 'NandaView/0.1 (NASA Space Apps climate research)'})
        for attempt in range(self.attempts):
            try:
                with urlopen(request, timeout=self.timeout) as response:
                    body = response.read()
                    metadata = {
                        'url': url, 'fetched_at': datetime.now(timezone.utc).isoformat(),
                        'sha256': sha256(body).hexdigest(), 'status': response.status,
                        'content_type': response.headers.get('Content-Type'),
                        'etag': response.headers.get('ETag'),
                        'last_modified': response.headers.get('Last-Modified'),
                    }
                break
            except HTTPError as error:
                if error.code not in (429, 500, 502, 503, 504) or attempt == self.attempts - 1:
                    raise
            except (URLError, TimeoutError):
                if attempt == self.attempts - 1:
                    raise
            time.sleep(2 ** attempt)
        self.directory.mkdir(parents=True, exist_ok=True)
        body_path = self.directory / f'{metadata["sha256"]}.body'
        if not body_path.exists() or sha256(body_path.read_bytes()).hexdigest() != metadata['sha256']:
            temporary = body_path.with_suffix('.body.tmp')
            temporary.write_bytes(body)
            temporary.replace(body_path)
        # Refresh retains every old response body and its provenance sidecar.
        write_json(self.directory / f'{key}-{metadata["sha256"]}.snapshot.json', metadata)
        write_json(index_path, metadata)
        return body, metadata
