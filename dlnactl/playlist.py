import logging

from pathlib import Path

from .transcode import get_file_hash, Transcoder

logger = logging.getLogger(__name__)


async def load_playlist(playlist_path: Path, transcoder: tuple[Transcoder, str]|None = None) -> dict[str, Path]:
    logger.info('Loading playlist')
    elements: dict[str, Path] = {}

    paths = []
    with open(playlist_path, 'r') as file:
        for line in file.read().splitlines():
            if not line.startswith('#'):
                paths.append(line)
    
    for path in paths:
        try:
            if transcoder:
                result = await  transcoder[0].transcode(path, transcoder[1])
                elements[f'/media/{get_file_hash(path)}'] = result
            else:
                elements[f'/media/{get_file_hash(path)}'] = path
        except FileNotFoundError:
            logger.warning(f'File {path} not found. Skipping')
        
    return elements
