import asyncio
import asyncio
import logging

from prompt_toolkit.input import create_input
from prompt_toolkit.keys import Keys
from async_upnp_client.profiles.dlna import DmrDevice, TransportState
from async_upnp_client.client import UpnpDevice
from async_upnp_client.aiohttp import AiohttpRequester, AiohttpNotifyServer
from rich.text import Text
from rich.live import Live
from collections.abc import Sequence


from .server import get_local_ip

logger = logging.getLogger(__name__)

class DLNADeviceWrapper:
    def __init__(self, device: UpnpDevice, wait_task: asyncio.Event, stop_on_quit: bool, manual_refresh: bool) -> None:
        # Set properties
        self.upnp_device: UpnpDevice = device
        self.stop_on_quit: bool = stop_on_quit # Whether to stop playback after the program quits
        self.manual_refresh = manual_refresh

        self.device: DmrDevice|None = None
        self.wait_task: asyncio.Event = wait_task

        self.requester = AiohttpRequester()

        self.playlist: Sequence[str]|None = None
        self.playing_list: bool = False

        # These are sometimes set manualy because DLNA implemenation vary
        self.volume: float|None = None
        self.muted: bool|None = None

    async def start(self):
        # Start event server and subscribe to events
        self.event_server = AiohttpNotifyServer(self.requester, (get_local_ip(), 0))
        await self.event_server.async_start_server()

        self.device = DmrDevice(self.upnp_device, self.event_server.event_handler)

        # self.device.on_event = self.on_event

        await self.device.async_subscribe_services(auto_resubscribe=True)
        # Needed for property values to work right

        asyncio.create_task(self.key_listener())
        asyncio.create_task(self.term_updater())
        asyncio.create_task(self.refresh_loop())

    async def play_media(self, url: str, name: str):
        if self.device is None:
            raise RuntimeError
        
        logger.info(f'Playing {url} on device')
        await self.device.async_stop()
        await self.device.async_set_transport_uri(url, name)
        await self.device.async_wait_for_can_play()
        await self.device.async_play()

    async def play_pause(self):
        if self.device is None:
            raise RuntimeError
        
        if self.device.transport_state in [TransportState.PAUSED_PLAYBACK, TransportState.STOPPED]:
            await self.device.async_wait_for_can_play()
            await self.device.async_play()
        else:
            await self.device.async_pause()

    async def change_volume(self, change: int):
        if self.device is None:
            raise RuntimeError

        if self.volume is None:
            logger.warning('Device doesn\'t seem to support setting the volume')
            return
        
        new_volume = (int(self.volume * 100) + change) / 100 
        # This is needed because the device sometimes responds with for example: 0.04999 (instead of 5)
        # and then truncates 0.0599999 back down to 5

        if new_volume < 0:
            new_volume = 0
        elif new_volume > 1:
            new_volume = 1

        await self.device.async_set_volume_level(new_volume)

    async def handle_key(self, key: str|Keys):
        if self.device is None:
            raise RuntimeError
        
        match key:
            case ' ':
                await self.play_pause()
            case 'm':
                await self.device.async_mute_volume(not self.muted)
            case '=':
                await self.change_volume(1)
            case '-':
                await self.change_volume(-1)
            case '+':
                await self.change_volume(10)
            case '_':
                await self.change_volume(-10)
            case Keys.Right:
                await self.move_in_list(1)
            case Keys.Left:
                await self.move_in_list(-1)

    async def key_listener(self):
        if self.device is None:
            raise RuntimeError
        inp = create_input()

        with inp.raw_mode():
            while True:
                keys = inp.read_keys()

                for key in keys:
                    if key.key in ['q', Keys.ControlC]:
                        await self.device.async_unsubscribe_services()
                        await self.event_server.async_stop_server()
                        self.wait_task.set()
                        return
                    else:
                        try:
                            await self.handle_key(key.key)
                        except Exception as error:
                            logger.error(f'Failed to send command to device: {error}')
                
                await asyncio.sleep(0.05)
    def collect_info(self) -> list[str]:
        if self.device is None:
            raise RuntimeError
        
        if self.device.transport_state is None:
            state = 'UNKNOWN'
        else:
            state = self.device.transport_state.value
        
        if self.volume is None:
            volume = 'UNKNOWN'
        else:
            volume = f'{int(self.volume * 100)}%'

        if self.muted is None:
            muted = 'UNKNOWN'
        else:
            muted = str(self.muted)

        if self.device.av_transport_uri:
            source = self.device.av_transport_uri
        else:
            source = 'Unknown'

        return [state, volume, muted, source]

    async def render_status(self):
        if self.device is None:
            raise RuntimeError
        
        info = self.collect_info()

        help_text = f'Press q to quit, Space to play/pause, +/- to change volume (hold Shift to change by 10%){', right/left arrows for Next/Previous' if self.playing_list else ''} and m to mute'

        return Text(f"Status: {info[0]} \nVolume: {info[1]} \nMuted: {info[2]}\nSource: {info[3]}\n{help_text}")

    async def term_updater(self):
        if self.device is None:
            raise RuntimeError
        
        with Live(await self.render_status(), refresh_per_second=4) as live:
            while True:
                live.update(await self.render_status())
                await asyncio.sleep(0.25)

    async def play_playlist(self, playlist: Sequence[str]):
        if self.device is None:
            raise RuntimeError
        
        self.playlist = playlist
        self.playing_list = True

        if len(self.playlist) == 0:
            return
        elif len(self.playlist) == 1:
            await self.play_media(playlist[0], 'Media')
            return

        await self.play_media(playlist[0], 'Media')
        asyncio.create_task(self.playlist_loop())

    async def get_playlist_pos(self) -> int|None:
        if self.device is None:
            raise RuntimeError
        
        if self.playlist is None:
            return None
        
        track = self.device.av_transport_uri
        if track is None:
            return None
        
        if track not in self.playlist:
            return None
        
        return self.playlist.index(track)
    
    async def playlist_loop(self):
        if self.device is None:
            raise RuntimeError
        
        if self.playlist is None:
            raise RuntimeError
        
        while self.playing_list:
            await asyncio.sleep(3)
            index = await self.get_playlist_pos()
            if index is None:
                continue
            if index + 1 == len(self.playlist):
                self.playing_list = False
                return
            if self.device.has_next_transport_uri:
                await self.device.async_set_next_transport_uri(self.playlist[index + 1], 'Media')
            else:
                logger.warning('Device doesn\'t support setting next track. Playlists won\'t work right')
                return

    async def move_in_list(self, change: int):
        if self.device is None:
            raise RuntimeError
        
        index = await self.get_playlist_pos()
        if index is None or self.playlist is None:
            logger.warning('Not currently playing playlist')
            return

        if index + change >= len(self.playlist) or index + change < 0:
            logger.info('Reached end of playlist')
            return
        
        await self.play_media(self.playlist[index + change], 'Media')

    async def manual_collect_info(self) -> tuple[float|None, bool|None]:
        # Force update device info, because some device don't send notifications
        if self.device is None:
            raise RuntimeError
        await self.device.async_update(do_ping=True)

        service = self.device._service('RC')
        if service is None:
            return (None, None)
        
        volume: int = (await service.action("GetVolume").async_call(InstanceID=0, Channel="Master"))['CurrentVolume']
        mute: bool = (await service.action("GetMute").async_call(InstanceID=0, Channel="Master"))['CurrentMute']
        return (volume / 100, mute)
    
    async def refresh_loop(self):
        if self.device is None:
            raise RuntimeError
        
        while True:
            if self.manual_refresh:
                info = await self.manual_collect_info()
                self.volume = info[0]
                self.muted = info[1]
            else:
                self.volume = self.device.volume_level
                self.muted = self.device.is_volume_muted
            
            await asyncio.sleep(0.25)




        

        


