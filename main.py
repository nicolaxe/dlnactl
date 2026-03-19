import asyncio
import async_upnp_client.search as upnp_search
import logging

from async_upnp_client.client_factory import UpnpFactory
from async_upnp_client.utils import CaseInsensitiveDict
from async_upnp_client.aiohttp import AiohttpRequester
from rich.logging import RichHandler

from device import DLNADeviceWrapper


logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="%H:%M:%S",
    handlers=[RichHandler(show_path=False, show_time=False)]
)
logging.getLogger("aiohttp.access").setLevel(logging.WARNING)


found_devices: list[tuple[str, CaseInsensitiveDict]] = []

async def save_detected_device(arg: CaseInsensitiveDict, factory: UpnpFactory):
    try:
        device = await factory.async_create_device(arg['location'])
        logger.info(f'Found device: {device.name}')
        found_devices.append((device.name, arg))
    except:
        logger.warning(f'Device {arg.get('X-ModelName')} failed to respond. Ignoring it')

def select_device(list: list[tuple[str, CaseInsensitiveDict]], name: str|None) -> CaseInsensitiveDict|None:
    if not len(list) > 0:
        logger.error('No DLNA devices found on local network')
        return None

    if name is None:
        if len(list) == 1:
            logger.info(f'Using device: {list[0][0]}')
            return list[0][1]
        else:
            logger.error('Multiple devices found and a name wasn\'t specified')
    
    for device in list:
        if device[0] == name:
            logger.info(f'Using device: {device[0]}')
            return device[1]
            
    logger.error(f'Device "{name}" not found')    
            
    
    

async def main():
    logger.info('Scanning for devices')
    
    requester = AiohttpRequester()
    factory = UpnpFactory(requester)

    await upnp_search.async_search(
        lambda arg: save_detected_device(arg, factory),
        4,
        "urn:schemas-upnp-org:device:MediaRenderer:1")

    wait_task = asyncio.Event()
    selected_device = select_device(found_devices, None)

    if selected_device is None:
        return
    
    dlna_device = DLNADeviceWrapper(await factory.async_create_device(selected_device['location']), wait_task)

    await dlna_device.start()

    await wait_task.wait()

    

asyncio.run(main())