# BK7258 Android Converter

Android offline prototype for converting customer `MP4(H.264)` videos into the
BK7258 terminal format.

## Output Profile

- Container: MP4
- Video codec: MJPEG
- JPEG profile: Baseline, non-progressive
- JPEG subsampling: YUV 4:2:2
- Pixel format target: `yuvj422p`
- Resolution: `480x480`
- FPS: `20-25`, default `25`
- Audio: none
- Resize: fit with black padding
- Max JPEG frame size: `96KB`

## Implementation

The Android app uses a two-step pipeline:

1. FFmpegKit decodes the input video into `480x480` MJPEG frames with
   `yuvj422p`.
2. The app validates the JPEG profile and writes the final MP4 container with a
   `jpeg` sample entry, matching the Windows converter strategy.

This avoids relying on Android media APIs or FFmpeg MP4 muxing behavior for the
terminal-critical final container.

## Build

Open the `android/` folder in Android Studio, then build `app`.

Command-line build on a machine with Android SDK and Gradle:

```bat
gradle -p android assembleDebug
```

The GitHub Actions workflow `.github/workflows/android.yml` can also build a
debug APK artifact.

## Notes

- Default quality is FFmpeg MJPEG `qscale=3`.
- If a generated JPEG frame exceeds `96KB`, conversion stops and reports an
  error. Use a larger qscale value, for example `4` or `5`, to reduce size.
- This Android prototype should be validated with the physical terminal before
  publishing a customer APK.
- FFmpegKit is GPL-based in this configuration; confirm licensing before
  commercial distribution.
