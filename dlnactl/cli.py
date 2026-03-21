import asyncio
import async_upnp_client.search as upnp_search
import logging
import argparse

from async_upnp_client.client_factory import UpnpFactory
from async_upnp_client.utils import CaseInsensitiveDict
from async_upnp_client.aiohttp import AiohttpRequester
from rich.logging import RichHandler
from pathlib import Path

from .device import DLNADeviceWrapper
from .server import DLNAServer
from .transcode import CODEC_PARAMETERS, Transcoder

# Set up argument parsing
parser = argparse.ArgumentParser(
                    prog='dlnactl',
                    description='A simple CLI DLNA remote/server')

parser.add_argument('-f', '--filename', type=str, help='media file to serve')
parser.add_argument('-u', '--url', type=str, help='URL to play on device')
parser.add_argument('-p', '--port', type=int, help='port to run the HTTP server on. Random by default. Does nothing unless --filename is also set', required=False)
parser.add_argument('-d', '--device', type=str, help='name of the DLNA device to control. Required if there are multiple devices on the network')
parser.add_argument('-t', '--transcode', type=str, choices=CODEC_PARAMETERS.keys(), help='If set program will first transcode file to desired format')
parser.add_argument('-v', '--verbose', action='store_true')

parser.add_argument('--scan-devices', action='store_true', help='scan for DLNA renderer devices and exit')

args = parser.parse_args()

# Set up logging
logger = logging.getLogger(__name__)
if args.verbose:
    level = logging.DEBUG
else:
    level = logging.INFO

logging.basicConfig(
    level=level,
    format="%(message)s",
    datefmt="%H:%M:%S",
    handlers=[RichHandler(show_path=False, show_time=False)]
)
logging.getLogger("aiohttp.access").setLevel(logging.WARNING)



found_devices: list[tuple[str, CaseInsensitiveDict]] = []

async def save_detected_device(arg: CaseInsensitiveDict, factory: UpnpFactory):
    try:
        device = await factory.async_create_device(arg['location'])
        if args.scan_devices:
            logger.info(f'Found device: "{device.name}" at {arg['location']}')
        found_devices.append((device.name, arg))
    except:
        logger.warning(f'Device {arg.get('X-ModelName')} failed to respond. Ignoring it')


def select_device(name: str|None) -> CaseInsensitiveDict|None:
    if not len(found_devices) > 0:
        logger.error('No DLNA devices found on local network')
        return None

    if name is None:
        if len(found_devices) == 1:
            logger.info(f'No device specified, using: "{found_devices[0][0]}"')
            return found_devices[0][1]
        else:
            logger.error('Multiple devices found and a name wasn\'t specified')
    
    for device in found_devices:
        if device[0] == name:
            logger.info(f'Using device: {device[0]}')
            return device[1]
            
    logger.error(f'Device "{name}" not found')  

async def handle_transcode(transcoder: Transcoder) -> Path|None:
    if args.filename is None:
        return None
    
    if args.transcode is None:
        return Path(args.filename)
    
    logger.info(f'Transcoding {args.filename} to {args.transcode}')
    return await transcoder.transcode(Path(args.filename), args.transcode)

    

def check_arguments() -> bool:
    # Check argument validity, return True on error and False on Success
    if args.filename and args.url:
        logger.error('Cannot set both --filename and --url at once')
        return True
    
    if args.filename:
        if not Path(args.filename).exists():
            logger.error(f'File "{args.filename}" doesn\'t exist')
            return True
        
    if not args.filename and args.transcode:
        logger.error('Cannot set --transcode without setting --file')
        return True
    
    if args.url and args.transcode:
        logger.error('Cannot transcode a remote URL')
        return True

    return False
    

async def main_async():
    # Check if args are correct
    if check_arguments():
        return
    
    # Find and select device
    logger.info('Scanning for devices')
    
    requester = AiohttpRequester()
    factory = UpnpFactory(requester)

    await upnp_search.async_search(
        lambda arg: save_detected_device(arg, factory),
        search_target="urn:schemas-upnp-org:device:MediaRenderer:1")
    
    if args.scan_devices:
        return # Exit after scan if --scan-devices if set

    wait_task = asyncio.Event()
    selected_device = select_device(args.device)

    if selected_device is None:
        return
    
    # Connect device
    dlna_device = DLNADeviceWrapper(await factory.async_create_device(selected_device['location']), wait_task, bool(args.filename))
    await dlna_device.start()

    # If casting, cast
    transcoder = Transcoder()
    try:
        file = await handle_transcode(transcoder)
    except Exception as error:
        logger.error(f'Transcoding failed with: {error}')
        return
    
    if file:
        if args.port:
            port = args.port
        else:
            port = 0
        dlna_server = DLNAServer(file, port)
        await dlna_server.start_server()
        url = dlna_server.get_url()
        logger.info(f'Started HTTP server on {url}')
        await dlna_device.play_media(url, 'Media')


    await wait_task.wait()
    # Clean tempdir
    transcoder.tempdir.cleanup()


def main():
    asyncio.run(main_async())

if __name__ == '__main__':  
    main()