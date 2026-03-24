import logging
import asyncio
import os

from pathlib import Path

from .transcode import get_file_hash, Transcoder

logger = logging.getLogger(__name__)

cpu_threads = os.cpu_count()
if cpu_threads is None:
    max_tasks = 4 # Default to 4 ffmpeg jobs if we can't get a number
else:
    max_tasks = cpu_threads

sem = asyncio.Semaphore(max_tasks)

async def transcode_item(item: Path, transcoder: tuple[Transcoder, str]) -> tuple[str, Path]|None:
    async with sem: # Limit ffmpeg calls so we don't call it 100 times
        try:
            logger.info(f'Transcoding {item} to {transcoder[1]}')
            server_path = f'/media/{get_file_hash(item)}'
            file_result = await transcoder[0].transcode(item, transcoder[1])
            return server_path, file_result
        except FileNotFoundError:
            logger.warning(f'File {item} not found. Skipping')
        except Exception as error:
            logger.error(f'Processing file {item} failed with: {error}')



async def load_playlist(playlist_path: Path, transcoder: tuple[Transcoder, str]|None = None) -> dict[str, Path]:
    logger.info('Loading playlist')
    elements: dict[str, Path] = {}

    paths = []
    with open(playlist_path, 'r') as file:
        for line in file.read().splitlines():
            if not line.startswith('#'):
                paths.append(line)
    

    if transcoder: # If transcoding, run ffmpeg async for much faster transcoding
        results = await asyncio.gather(*(transcode_item(path, transcoder) for path in paths))
        for item in results:
            if item is None:
                continue
            elements[item[0]] = item[1]
    else: # If not transcoding iterate normally
        for path in paths:
            try:
                elements[f'/media/{get_file_hash(path)}'] = path
            except FileNotFoundError:
                logger.warning(f'File {path} not found. Skipping')
            except Exception as error:
                logger.error(f'Processing file {path} failed with: {error}')
        
    return elements
