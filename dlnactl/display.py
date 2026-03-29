import logging
import asyncio

from prompt_toolkit.keys import Keys
from rich.text import Text
from rich.live import Live
from prompt_toolkit.input import create_input

from .device import DLNADeviceWrapper

logger = logging.getLogger(__name__)

def convert_time(time: int) -> str:
    # Convert time in seconds to "HH:MM:SS"
    hours = time // 3600
    time = time % 3600
    minutes = time // 60
    seconds = time % 60

    return f'{str(hours).zfill(2)}:{str(minutes).zfill(2)}:{str(seconds).zfill(2)}'


class StatusDisplay:
    def __init__(self, device_wrapper: DLNADeviceWrapper) -> None:
        self.device: DLNADeviceWrapper = device_wrapper

    async def start(self):
        asyncio.create_task(self.key_listener())
        asyncio.create_task(self.term_updater())

    async def handle_key(self, key: str|Keys):
        match key:
            case ' ':
                await self.device.play_pause()
            case 'm':
                await self.device.toggle_mute()
            case '=':
                await self.device.change_volume(1)
            case '-':
                await self.device.change_volume(-1)
            case '+':
                await self.device.change_volume(10)
            case '_':
                await self.device.change_volume(-10)
            case Keys.Right:
                await self.device.move_in_list(1)
            case Keys.Left:
                await self.device.move_in_list(-1)
            case '.':
                await self.device.seek_rel(10)
            case ',':
                await self.device.seek_rel(-10)
            case '>':
                await self.device.seek_rel(100)
            case '<':
                await self.device.seek_rel(-100)

    async def key_listener(self):
        inp = create_input()

        with inp.raw_mode():
            while True:
                keys = inp.read_keys()

                for key in keys:
                    if key.key in ['q', Keys.ControlC]:
                        await self.device.close()
                        self.device.wait_task.set()
                        return
                    else:
                        try:
                            await self.handle_key(key.key)
                        except Exception as error:
                            logger.error(f'Failed to send command to device: {error}')
                
                await asyncio.sleep(0.05)

    async def render_status(self):
        info = self.collect_info()

        help_text = f'Press q to quit, Space to play/pause, +/- to change volume (hold Shift to change by 10%){', right/left arrows for Next/Previous' if self.device.playing_list else ''} and m to mute'

        return Text(f'''Status: {info[0]} 
Volume: {info[1]} 
Muted: {info[2]}
Source: {info[3]}
Position: {info[5]}/{info[4]}
{help_text}''') # This is very ugly, but better then a single line with a bilion \n

    async def term_updater(self):
        with Live(await self.render_status(), refresh_per_second=4) as live:
            while True:
                live.update(await self.render_status())
                await asyncio.sleep(0.25)

    def collect_info(self) -> list[str]:
        if self.device.transport_state is None:
            state = 'UNKNOWN'
        else:
            state = self.device.transport_state.value
        
        if self.device.volume is None:
            volume = 'UNKNOWN'
        else:
            volume = f'{int(self.device.volume * 100)}%'

        if self.device.muted is None:
            muted = 'UNKNOWN'
        else:
            muted = str(self.device.muted)

        if self.device.av_transport_uri:
            source = self.device.av_transport_uri
        else:
            source = 'Unknown'

        if self.device.media_duration is None:
            duration = 'Unknown'
        else:
            duration = convert_time(self.device.media_duration)

        if self.device.media_position is None:
            position = 'Unknown'
        else:
            position = convert_time(self.device.media_position)


        return [state, volume, muted, source, duration, position]
        