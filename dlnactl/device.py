import asyncio
import asyncio
import logging

from async_upnp_client.profiles.dlna import DmrDevice, TransportState
from async_upnp_client.client import UpnpDevice
from async_upnp_client.aiohttp import AiohttpRequester, AiohttpNotifyServer
from collections.abc import Sequence

from .server import get_local_ip

logger = logging.getLogger(__name__)

class DLNADeviceWrapper:
    def __init__(self, device: UpnpDevice, wait_task: asyncio.Event, stop_on_quit: bool, manual_refresh: bool) -> None:
        # Set properties
        self.upnp_device: UpnpDevice = device
        self.stop_on_quit: bool = stop_on_quit # Whether to stop playback after the program quits
        self.manual_refresh = manual_refresh

        self._raw_device: DmrDevice|None = None # Preferably don't use this in other code
        self.wait_task: asyncio.Event = wait_task

        self.requester = AiohttpRequester()

        self.playlist: Sequence[str]|None = None
        self.playing_list: bool = False

        # These are sometimes set manualy because DLNA implemenation vary
        self._stored_volume: float|None = None
        self._stored_muted: bool|None = None

    async def start(self):
        # Start event server and subscribe to events
        self.event_server = AiohttpNotifyServer(self.requester, (get_local_ip(), 0))
        await self.event_server.async_start_server()

        self._raw_device = DmrDevice(self.upnp_device, self.event_server.event_handler)

        # self.device.on_event = self.on_event

        await self._raw_device.async_subscribe_services(auto_resubscribe=True)
        # Needed for property values to work right

        #asyncio.create_task(self.key_listener())
        #asyncio.create_task(self.term_updater())
        asyncio.create_task(self.refresh_loop())

    async def play_media(self, url: str, name: str):
        if self._raw_device is None:
            raise RuntimeError
        
        logger.info(f'Playing {url} on device')
        await self._raw_device.async_stop()
        await self._raw_device.async_set_transport_uri(url, name)
        await self._raw_device.async_wait_for_can_play()
        await self._raw_device.async_play()

    async def play_pause(self):
        if self._raw_device is None:
            raise RuntimeError
        
        if self._raw_device.transport_state in [TransportState.PAUSED_PLAYBACK, TransportState.STOPPED]:
            await self._raw_device.async_wait_for_can_play()
            await self._raw_device.async_play()
        else:
            await self._raw_device.async_pause()

    async def change_volume(self, change: int):
        if self._raw_device is None:
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

        await self._raw_device.async_set_volume_level(new_volume)


    async def play_playlist(self, playlist: Sequence[str]):
        if self._raw_device is None:
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
        if self._raw_device is None:
            raise RuntimeError
        
        if self.playlist is None:
            return None
        
        track = self._raw_device.av_transport_uri
        if track is None:
            return None
        
        if track not in self.playlist:
            return None
        
        return self.playlist.index(track)
    
    async def playlist_loop(self):
        if self._raw_device is None:
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
            if self._raw_device.has_next_transport_uri:
                await self._raw_device.async_set_next_transport_uri(self.playlist[index + 1], 'Media')
            else:
                logger.warning('Device doesn\'t support setting next track. Playlists won\'t work right')
                return

    async def move_in_list(self, change: int):
        if self._raw_device is None:
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
        if self._raw_device is None:
            raise RuntimeError
        await self._raw_device.async_update(do_ping=True)

        service = self._raw_device._service('RC')
        if service is None:
            return (None, None)
        
        volume: int = (await service.action("GetVolume").async_call(InstanceID=0, Channel="Master"))['CurrentVolume']
        mute: bool = (await service.action("GetMute").async_call(InstanceID=0, Channel="Master"))['CurrentMute']
        return (volume / 100, mute)
    
    async def refresh_loop(self):
        if self._raw_device is None:
            raise RuntimeError
        
        while True:
            info = await self.manual_collect_info()
            self._stored_volume = info[0]
            self._stored_muted = info[1]
            await asyncio.sleep(0.25)

    @property
    def volume(self) -> float|None:
        if self._raw_device is None:
            raise RuntimeError
        
        if self.manual_refresh:
            return self._stored_volume
        else:
            return self._raw_device.volume_level
        
    @property
    def muted(self) -> float|None:
        if self._raw_device is None:
            raise RuntimeError
        
        if self.manual_refresh:
            return self._stored_muted
        else:
            return self._raw_device.is_volume_muted
        
    @property
    def transport_state(self):
        if self._raw_device is None:
            raise RuntimeError
        
        return self._raw_device.transport_state
    
    @property
    def av_transport_uri(self):
        if self._raw_device is None:
            raise RuntimeError
        
        return self._raw_device.av_transport_uri
        
    async def toggle_mute(self):
        if self._raw_device is None:
            raise RuntimeError
        
        await self._raw_device.async_mute_volume(not self.muted)

    async def close(self):
        if self._raw_device is None:
            raise RuntimeError
        await self._raw_device.async_unsubscribe_services()
        await self.event_server.async_stop_server()





        

        


