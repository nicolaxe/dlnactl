import tempfile
import asyncio

from ffmpeg.asyncio import FFmpeg
from pathlib import Path


async def transcode(input: Path, codec: str, output: Path):
    out_opts = {'c:a': codec}

    ffmpeg = (
        FFmpeg()
        .option("y")
        .input(input)
        .option('vn')
        .output(output,
                {'c:a': codec}
                )
    )

    await ffmpeg.execute()

