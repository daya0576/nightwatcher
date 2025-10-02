# Night Watcher 🦇

A Simple IP Camera Viewer with Custom Detection

<img width="750" alt="image" src="https://github.com/user-attachments/assets/ae929319-e10a-4e53-b919-e67355f346c4" />


Inspired by: 
- NiceGUI Opencv Webcam Example from [@zauberzeug](https://github.com/zauberzeug)

# Features

1. **Performance**: Blazing fast streaming without any delay
2. **Cross Platform Support**: Works on any device with a browser
3. **Privacy & Extensibility**: Local models and custom detection script support
4. **Simplicity**: Minimal navigations and css styles


# Get Started

```shell
# Install uv and all the dependencies
uv venv && source .venv/bin/activate
uv sync

# Setup URL of video stream
export RTSP_URLS=protocol://host:port/script_name?script_params|auth

# Start the server
uv run python -m nightwatcher.main
```


# About 
This project is made with love for families, tested by my wife :p 

Hoping you can enjoy this project and feel free to contribute!

[[Read more...]](https://changchen.me/blog/20250811/nightwatcher/)


# WIP
- [ ] Detection timelines with snapshots
