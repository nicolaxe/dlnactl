import logging

from pathlib import Path

from .transcode import get_file_hash

logger = logging.getLogger(__name__)


def load_playlist(playlist_path: Path, transcode: str|None = None) -> dict[str, Path]:
    logger.info('Loading playlist')
    elements: dict[str, Path] = {}

    paths = []
    with open(playlist_path, 'r') as file:
        for line in file.read().splitlines():
            if not line.startswith('#'):
                paths.append(line)
    
    for path in paths:
        try:
            elements[f'/media/{get_file_hash(path)}'] = path
        except FileNotFoundError:
            logger.warning(f'File {path} not found. Skipping')
        
    return elements
