# BK7258 Video Converter

Offline Windows GUI tool for converting customer `MP4(H.264)` videos into the
terminal-compatible `MP4(MJPEG)` format required by the BK7258 device.

## Customer Download

Use the packaged offline release from GitHub Releases:

- https://github.com/amortom/video_convert/releases/tag/v1.0.0
- Direct download: https://github.com/amortom/video_convert/releases/download/v1.0.0/BK7258VideoConverter_v1.0.0.zip
- SHA256: see `BK7258VideoConverter_v1.0.0.sha256.txt`

After downloading, extract the whole folder and run:

```text
BK7258VideoConverter.exe
```

Do not copy only the EXE. Keep `_internal/` and `BK7258ConverterWorker.exe`
in the same folder as the GUI program.

## Required Output Format

- Container: MP4
- Video codec: MJPEG
- JPEG profile: Baseline, non-progressive
- JPEG subsampling: YUV 4:2:2
- Pixel format: `yuvj422p`
- Resolution: `480x480`
- Frame rate: `20-25fps`, default `25fps`
- Audio: none
- Resize mode: fit with black padding by default
- Max single JPEG frame: `96KB` by default

The important terminal requirement is `YUV 4:2:2 / yuvj422p`. Do not change
the converter back to `yuvj420p`.

## Source Usage

Install dependencies:

```bat
pip install -r requirements.txt
```

Run command-line conversion:

```bat
python mp4_converter.py input.mp4 -o output.mp4
```

Run the GUI from source:

```bat
python gui_converter.py
```

## Build Offline Release

Build worker:

```bat
python -m PyInstaller --noconfirm --clean --console --onefile --name BK7258ConverterWorker mp4_converter.py --distpath dist_worker --workpath build_worker
```

Build GUI:

```bat
python -m PyInstaller --noconfirm --clean --windowed --onedir --name BK7258VideoConverter --add-data "TERMINAL_FORMAT_SPEC.md;." gui_converter.py
```

Copy `BK7258ConverterWorker.exe`, `CUSTOMER_README.txt`,
`TERMINAL_FORMAT_SPEC.md`, `VERSION.txt`, and release notes into
`dist/BK7258VideoConverter/`, then zip the full folder.
