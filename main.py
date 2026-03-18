import async_upnp_client.search as upnp_search
from async_upnp_client.aiohttp import AiohttpRequester, AiohttpNotifyServer
from async_upnp_client.client_factory import UpnpFactory
from async_upnp_client.client import UpnpDevice
from async_upnp_client.utils import CaseInsensitiveDict
import asyncio

from async_upnp_client.profiles.dlna import DmrDevice, TransportState
from async_upnp_client.event_handler import UpnpEventHandler

import sys
import termios
import tty





class DLNADeviceWrapper:
    def __init__(self, device: UpnpDevice, wait_task: asyncio.Event) -> None:
        # Set properties
        self.upnp_device: UpnpDevice = device
        self.state: TransportState | None = None
        self.muted: bool | None = None
        self.volume: float | None = None
        #self.loop: asyncio.AbstractEventLoop = loop
        self.device: DmrDevice|None = None
        self.wait_task: asyncio.Event = wait_task

        self.requester = AiohttpRequester()
        
        

    async def start(self):
        # Start event server and subscribe to events
        self.event_server = AiohttpNotifyServer(self.requester, ('192.168.50.235', 8090)) # TODO: This
        await self.event_server.async_start_server()

        self.device = DmrDevice(self.upnp_device, self.event_server.event_handler)

        self.device.on_event = self.on_event

        await self.device.async_subscribe_services(auto_resubscribe=True)

        asyncio.create_task(self.key_listener())


    def on_event(self, service, state_variables):
        print(type(service), type(state_variables))

    async def play_media(self, url: str, name: str):
        if self.device is None:
            raise RuntimeError

        await self.device.async_set_transport_uri(url, name)
        await self.device.async_wait_for_can_play()
        await self.device.async_play()

    async def handle_key(self, key: str):
        if self.device is None:
            raise RuntimeError
        

    async def key_listener(self):
        if self.device is None:
            raise RuntimeError
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        tty.setcbreak(fd)

        loop = asyncio.get_event_loop()

        try:
            while True:
                ch = await loop.run_in_executor(None, sys.stdin.read, 1)
                if (ch == 'q'):
                    await self.device.async_unsubscribe_services()
                    await self.event_server.async_stop_server()
                    self.wait_task.set()
                    return
                await self.handle_key(ch)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)




found_devices = []

async def save_detected_device(arg: CaseInsensitiveDict):
    found_devices.append(arg)


async def main():
    await upnp_search.async_search(save_detected_device, 1, "urn:schemas-upnp-org:device:MediaRenderer:1")
    
    requester = AiohttpRequester()
    factory = UpnpFactory(requester)

    wait_task = asyncio.Event()

    dlna_device = DLNADeviceWrapper(await factory.async_create_device(found_devices[0]['location']), wait_task)

    await dlna_device.start()

    await wait_task.wait()

    

asyncio.run(main())