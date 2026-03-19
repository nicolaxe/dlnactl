import socket
import mimetypes

from aiohttp import web
from pathlib import Path

def get_local_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80)) # This seems really hacky, but it's the best i can find
    ip = s.getsockname()[0]
    s.close()
    return ip



class DLNAServer:
    def __init__(self, path: Path, port: int) -> None:
        self.path = path
        self.port = port
        
    async def _serve_file(self, request):
        # For whatever reason aiohttp often fails to auto-detect the MIME type. I have to set it manually
        content_type = mimetypes.guess_type(self.path)[0]
        if content_type is None:
            content_type = 'application/octet-stream'
        headers = {'content-type': content_type}
        return web.FileResponse(self.path, headers=headers)

    async def start_server(self):
        self.app = web.Application()
        self.app.router.add_get("/media", self._serve_file)

        self.runner = web.AppRunner(self.app)
        await self.runner.setup()

        self.site = web.TCPSite(self.runner, "0.0.0.0", self.port)
        await self.site.start()

    def get_url(self):
        port: int = self.site._server.sockets[0].getsockname()[1] # type: ignore
        # _server.sockets does exist, but only after site.start(). I don't know a better way to do this
        ip = get_local_ip()
        return f'http://{ip}:{port}/media'

