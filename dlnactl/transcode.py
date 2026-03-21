import tempfile
import asyncio
import hashlib

from ffmpeg.asyncio import FFmpeg
from pathlib import Path

# {codec: (encoder_name, file_extention, default_bitrate)}
CODEC_PARAMETERS : dict[str, tuple[str, str, int|None]]= {
    'mp3': ('libmp3lame', 'mp3', 320),
    'opus': ('libopus', 'opus', 192),
    'flac': ('flac', 'flac', None),
    'vorbis': ('libvorbis', 'ogg', 256),
    'wav': ('pcm_f16le', 'wav', None)
}

def get_file_hash(file_path: Path) -> str:
    hash_func = hashlib.blake2b(digest_size=8)
    
    with open(file_path, 'rb') as file:
        while chunk := file.read(1024 * 1024):
            hash_func.update(chunk)
    
    return hash_func.hexdigest()

class Transcoder:
    def __init__(self):
        self.tempdir = tempfile.TemporaryDirectory()

    async def transcode(self, input: Path, codec: str) -> Path:
        if codec not in CODEC_PARAMETERS.keys():
            raise RuntimeError(f'Codec "{codec}" not supported')
        
        out_name = f'{get_file_hash(input)}.{CODEC_PARAMETERS[codec][1]}'
        out_file = Path(self.tempdir.name)/out_name

        if out_file.exists():
            return out_file

        encoder = CODEC_PARAMETERS[codec][0]
        bitrate = CODEC_PARAMETERS[codec][2]

        await self.call_ffmpeg(input, encoder, out_file, bitrate)
        return out_file


    async def call_ffmpeg(self, input: Path, encoder: str, output: Path, bitrate_k: int|None):
        out_opts = {'c:a': encoder}
        if bitrate_k:
            out_opts['b:a'] = f'{bitrate_k}k'

        ffmpeg = (
            FFmpeg()
            .option("y")
            .input(input)
            .option('vn')
            .output(output,
                    out_opts #type: ignore Pretty sure pylance is wrong here
                    )
        )

        await ffmpeg.execute()
