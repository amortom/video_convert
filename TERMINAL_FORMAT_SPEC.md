# BK7258 Terminal Video Format

Converter version: v1.0.0

This is the required converter output profile.

- Container: MP4
- Video codec: MJPEG
- JPEG profile: Baseline, non-progressive
- JPEG subsampling: YUV 4:2:2
- ffprobe pixel format: yuvj422p
- Resolution: 480x480
- Frame rate: 20-25 fps, default 25 fps
- Audio: none
- Resize mode: fit with black padding by default
- Single JPEG frame size: <= 96 KB by default

Reference command:

```bat
python mp4_converter.py input.mp4 -o output.mp4
```

Reference output check:

```text
codec_name=mjpeg
codec_tag_string=jpeg
width=480
height=480
pix_fmt=yuvj422p
avg_frame_rate=25/1
```
