# dlnactl
dlnactl is a CLI tool for controlling and playing media on DLNA devices.
## Features
- Basic control (play/pause, volume, mute)
- Serve media files from local devices with integrated HTTP server
- Transcode media files to common formats (currently only audio)
- Set remote URL as source
- Playlists

## Instalation
```
pip install git+https://github.com/nicolaxe/dlnactl.git@main
```
or
```
git clone https://github.com/nicolaxe/dlnactl.git
cd dlnactl
pip install -e .
```

## Usage 
Running the command with no arguments
```
dlnactl
```
will scan for DLNA compatible devices. If only one is available, it will connect to it and allow for control.

If there are multiple devices on the network you'll need to specify it with the `-d DEVICE` flag.
```
dlnactl -d Tuner
```
will search and connect to a device named "Tuner".

Avaliable devices can be listed with
```
dlnactl --scan-devices
```
If a media file is passed as an argument, the file will be served on an HTTP server. The port to use for the server can be specified with `-p PORT`, if the port isn't set, it is selected by the OS.
```
dlnactl song.mp3 -p 8000 -d Tuner
```
will serve `song.mp3` on port 8000 and play it on "Tuner".

If the device doesn't support certain media formats, the file can be transcoded with the `-t CODEC` option. This will transcode the file to the specific format (currently supported are: mp3, flac, wav, opus, vorbis), and serve it on the HTTP server.
```
dlnactl song.opus -t mp3
```
will transcode `song.opus` to mp3 and play it.

You can also directly play a media file from a different server by using the `-u` option
```
dlnactl -u http://example.com/song.mp3
```

You can play playlists using the `--playlist` flag
```
dlnactl --playlist ~/Music/Favourites.m3u
```
**Note: Playlist support is problematic with some DLNA devices. This program implements it's own system. For this reason on most devices the integrated Next and Previous buttons won't work. Use the controls in the program**

If the volume or mute status don't seem to refresh correctly on your device you can try
```
dlnactl --force-manual-refresh
```
this polls the device explicitly instead of relying on notifications

## TODO List
- [ ] Config files
- [x] Playlist support
- [ ] Looping

## Known Issues
- Some devices require support for the HTTP `Range` header which aiohttp doesn't handle correctly
- Sometimes a scan will fail to detect any devices, requiring a retry
- Playlists are problematic
