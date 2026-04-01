import socket
import mimetypes
import magic
import logging
import os

from aiohttp import web
from aiohttp.web_request import Request
from pathlib import Path

logger = logging.getLogger(__name__)

def get_local_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80)) # This seems really hacky, but it's the best i can find
    ip = s.getsockname()[0]
    s.close()
    return ip

# Some slop code that "correctly" handles devices requesting stupid HTTP Ranges
# By "correctly" i mean it just accepts and sends back what the device expects, standards be damned
def get_file_response(path: Path, range_header: str, content_type: str):
    file_size = os.path.getsize(path)
    units, rng = range_header.split('=')
    start_str, end_str = rng.split('-')

    start = int(start_str)
    end = int(end_str) if end_str else file_size - 1

    if start >= file_size:
        logger.warning(f'Invalid HTTP Range header: {start} for "{path}" (size={file_size}), resetting to 0')
        start = 0
        end = file_size - 1

    end = min(end, file_size - 1)
    length = end - start + 1

    headers = {
            'content-type': content_type,
            'Accept-Ranges': 'bytes',
            'transferMode.dlna.org': 'Streaming',
            'Content-Range': f'bytes {start}-{end}/{file_size}',
            'Content-Length': str(length)
    }

    with open(path, 'rb') as f:
        f.seek(start)
        data = f.read(length)

    return web.Response(
        status=206,
        body=data,
        headers=headers,
        )



class DLNAServer:
    def __init__(self, paths: dict[str, Path], port: int) -> None:
        self.paths: dict[str, Path] = paths
        self.port = port
        
    async def _serve_file(self, request: Request):
        path = self.paths.get(request.path)
        if path is None:
            return web.Response(status=404)

        # MIME detection
        content_type = magic.from_file(path, mime=True)

        if content_type == 'application/octet-stream':
            logger.warning(f'Unable to determine filetype of "{path}". Using the file extension')
            content_type = mimetypes.guess_type(path)[0]
            if content_type is None:
                content_type = 'application/octet-stream'


        headers = {
            'content-type': content_type,
            'Accept-Ranges': 'bytes',
            'transferMode.dlna.org': 'Streaming',
        }

        range_header = request.headers.get('Range')

        if range_header:
            try:
                return get_file_response(path, range_header, content_type)
            except Exception as e:
                logger.exception(f'Bad range request: {range_header} ({e})')
                return web.Response(status=416)


        return web.FileResponse(path, headers=headers)

    async def start_server(self):
        self.app = web.Application()
        for path in self.paths.keys():
            self.app.router.add_get(path, self._serve_file)

        self.runner = web.AppRunner(self.app)
        await self.runner.setup()

        self.site = web.TCPSite(self.runner, "0.0.0.0", self.port)
        await self.site.start()

    def get_url(self):
        port: int = self.site._server.sockets[0].getsockname()[1] # type: ignore
        # _server.sockets does exist, but only after site.start(). I don't know a better way to do this
        ip = get_local_ip()
        return f'http://{ip}:{port}'