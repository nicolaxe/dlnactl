import socket
import mimetypes
import asyncio

from aiohttp import web
from aiohttp.web_request import Request
from pathlib import Path

def get_local_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80)) # This seems really hacky, but it's the best i can find
    ip = s.getsockname()[0]
    s.close()
    return ip



class DLNAServer:
    def __init__(self, paths: dict[str, Path], port: int) -> None:
        self.paths: dict[str, Path] = paths
        self.port = port
        
    async def _serve_file(self, request: Request):
        path = self.paths.get(request.path)
        if path is None:
            return web.Response(status=404)
        # For whatever reason aiohttp often fails to auto-detect the MIME type. I have to set it manually
        content_type = mimetypes.guess_type(path)[0]
        if content_type is None:
            content_type = 'application/octet-stream'
        headers = {'content-type': content_type}
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