# dlnactl
dlnactl is a minimal CLI tool to controlling and playing media on DLNA devices.
## Features
- Basic control (play/pause, volume, mute)
- Serve media files from local devices with integrated HTTP server
- Transcode media files to common formats (currently only audio)
- Set remote URL as source

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
If a media file is passed with the `-f FILE` argument, the file will be served on an HTTP server. The port to use for the server can be specified with `-p PORT`, if the port isn't set it is selected by the OS.
```
dlnactl -f song.mp3 -p 8000 -d Tuner
```
will serve `song.mp3` on port 8000 and play it on "Tuner".

If the device doesn't support certain media formats, the file can be transcoded with the `-t CODEC` option. This will transcode the file to the specific format (currently supported are: mp3, flac, wav, opus, vorbis), and serve it on the HTTP server.
```
dlnactl -f song.opus -t mp3
```
will transcode `song.opus` to mp3 and play it.


