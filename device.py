import sys
import termios
import tty
import asyncio
import logging

from async_upnp_client.profiles.dlna import DmrDevice, TransportState
from async_upnp_client.client import UpnpDevice, UpnpService, UpnpStateVariable
from async_upnp_client.aiohttp import AiohttpRequester, AiohttpNotifyServer
from rich.text import Text
from rich.live import Live

logger = logging.getLogger(__name__)

class DLNADeviceWrapper:
    def __init__(self, device: UpnpDevice, wait_task: asyncio.Event) -> None:
        # Set properties
        self.upnp_device: UpnpDevice = device

        # self.state: str | None = None
        # self.muted: bool | None = None
        # self.volume: float | None = None

        #self.loop: asyncio.AbstractEventLoop = loop
        self.device: DmrDevice|None = None
        self.wait_task: asyncio.Event = wait_task

        self.requester = AiohttpRequester()
        
        

    async def start(self):
        # Start event server and subscribe to events
        self.event_server = AiohttpNotifyServer(self.requester, ('192.168.50.235', 8090)) # TODO: This
        await self.event_server.async_start_server()

        self.device = DmrDevice(self.upnp_device, self.event_server.event_handler)

        # self.device.on_event = self.on_event

        await self.device.async_subscribe_services(auto_resubscribe=True)
        # Needed for property values to work right

        asyncio.create_task(self.key_listener())
        asyncio.create_task(self.term_updater())

    # def handle_transport_event(self, state: Sequence[UpnpStateVariable]):
    #     for property in state:
    #         if property.name == 'TransportState':
    #             self.state = property.value

    # def handle_rendering_event(self, state: Sequence[UpnpStateVariable]):
    #     for property in state:
    #         if property.name == 'Mute':
    #             self.muted = property.value
    #         elif property.name == 'Volume':
    #             self.volume = property.value
            

    # def on_event(self, service: UpnpService, state: Sequence[UpnpStateVariable]):
    #     if service.service_id == 'urn:upnp-org:serviceId:AVTransport':
    #         self.handle_transport_event(state)
    #     elif service.service_id == 'urn:upnp-org:serviceId:RenderingControl':
    #         self.handle_rendering_event(state)

    async def play_media(self, url: str, name: str):
        if self.device is None:
            raise RuntimeError

        await self.device.async_set_transport_uri(url, name)
        await self.device.async_wait_for_can_play()
        await self.device.async_play()

    async def play_pause(self):
        if self.device is None:
            raise RuntimeError
        
        if self.device.transport_state in [TransportState.PAUSED_PLAYBACK, TransportState.STOPPED]:
            await self.device.async_play()
        else:
            await self.device.async_pause()

    async def change_volume(self, change: int):
        if self.device is None:
            raise RuntimeError

        if self.device.volume_level is None:
            logger.warning('Device doesn\'t seem to support setting the volume')
            return
        
        new_volume = (int(self.device.volume_level * 100) + change) / 100 
        # This is needed because the device sometimes responds with for example: 0.04999 (instead of 6)
        # and then truncates 0.0599999 back down to 6

        if new_volume < 0:
            new_volume = 0
        elif new_volume > 1:
            new_volume = 1

        await self.device.async_set_volume_level(new_volume)

    async def handle_key(self, key: str):
        if self.device is None:
            raise RuntimeError
        
        match key:
            case ' ':
                await self.play_pause()
            case 'm':
                await self.device.async_mute_volume(not self.device.is_volume_muted)
            case '=':
                await self.change_volume(1)
            case '-':
                await self.change_volume(-1)
            case '+':
                await self.change_volume(10)
            case '_':
                await self.change_volume(-10)

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

    def render_status(self):
        if self.device is None:
            raise RuntimeError
        
        if self.device.transport_state is None:
            state = 'UNKNOWN'
        else:
            state = self.device.transport_state.value
        
        if self.device.volume_level is None:
            volume = 'UNKNOWN'
        else:
            volume = f'{int(self.device.volume_level * 100)}%'

        if self.device.is_volume_muted is None:
            muted = 'UNKNOWN'
        else:
            muted = str(self.device.is_volume_muted)
        
        help_text = 'Press q to quit, Space to play/pause, +/- to change volume (hold Shift to change by 10%) and m to mute'
        return Text(f"Status: {state} \nVolume: {volume} \nMuted: {muted}\n{help_text}")

    async def term_updater(self):
        with Live(self.render_status(), refresh_per_second=4) as live:
            while True:
                live.update(self.render_status())
                await asyncio.sleep(0.25)
