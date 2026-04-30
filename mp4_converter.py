#!/usr/bin/env python3
"""
MP4 Video Converter for BK7258 SmartKid
========================================
将客户提供的 MP4 (H.264) 视频转换为 BK7258 终端可硬件解码播放的
MP4 (MJPEG, YUV422) 格式。

使用方法:
    python mp4_converter.py input.mp4
    python mp4_converter.py input.mp4 -o output.mp4
    python mp4_converter.py input.mp4 -w 480 -h 480 --fps 25 --quality 50
    python mp4_converter.py input.mp4 --max-size 2700  (限制输出文件大小, 单位KB)

依赖:
    pip install opencv-python Pillow
"""

import argparse
import io
import os
import struct
import sys
import time

import cv2
from PIL import Image

try:
    sys.stdout.reconfigure(line_buffering=True)
except AttributeError:
    pass


TERMINAL_DEFAULT_WIDTH = 480
TERMINAL_DEFAULT_HEIGHT = 480
TERMINAL_DEFAULT_FPS = 25
TERMINAL_DEFAULT_QUALITY = 85
TERMINAL_DEFAULT_MAX_FRAME_KB = 96
TERMINAL_DEFAULT_MIN_QUALITY = 50
APP_VERSION = "1.0.0"


# ===========================================================================
# JPEG encoding (Pillow, standard YUV 4:2:2 compatible with BK7258 HW decoder)
# ===========================================================================

def encode_jpeg_422(bgr_frame, quality):
    """Encode a BGR frame to JPEG with standard YUV 4:2:2 subsampling."""
    rgb = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
    img = Image.fromarray(rgb)
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=int(quality), subsampling='4:2:2',
             progressive=False, optimize=False)
    return buf.getvalue()


def encode_jpeg_422_limited(bgr_frame, quality, max_frame_bytes, min_quality):
    """Encode JPEG 4:2:2 and lower quality only if a frame exceeds the limit."""
    q = int(quality)
    min_q = int(min_quality)

    while True:
        jpeg_data = encode_jpeg_422(bgr_frame, q)
        if not max_frame_bytes or len(jpeg_data) <= max_frame_bytes:
            return jpeg_data, q

        if q <= min_q:
            raise ValueError(
                f"JPEG frame too large: {len(jpeg_data)} bytes > "
                f"{max_frame_bytes} bytes at quality {q}"
            )

        q = max(min_q, q - 5)


def inspect_jpeg(jpeg_data):
    """Return basic JPEG coding info from SOF0/SOF2 markers."""
    if not jpeg_data.startswith(b'\xff\xd8'):
        return {'valid': False, 'reason': 'missing SOI marker'}

    pos = 2
    data_len = len(jpeg_data)
    while pos + 4 <= data_len:
        while pos < data_len and jpeg_data[pos] == 0xff:
            pos += 1
        if pos >= data_len:
            break

        marker = jpeg_data[pos]
        pos += 1

        if marker in (0xd8, 0xd9):
            continue
        if 0xd0 <= marker <= 0xd7:
            continue
        if pos + 2 > data_len:
            break

        seg_len = struct.unpack('>H', jpeg_data[pos:pos + 2])[0]
        seg_start = pos + 2
        seg_end = pos + seg_len
        if seg_len < 2 or seg_end > data_len:
            break

        if marker in (0xc0, 0xc2):
            if seg_start + 6 > seg_end:
                break

            precision = jpeg_data[seg_start]
            height = struct.unpack('>H', jpeg_data[seg_start + 1:seg_start + 3])[0]
            width = struct.unpack('>H', jpeg_data[seg_start + 3:seg_start + 5])[0]
            comp_count = jpeg_data[seg_start + 5]
            comps = []
            comp_pos = seg_start + 6

            for _ in range(comp_count):
                if comp_pos + 3 > seg_end:
                    break
                comp_id = jpeg_data[comp_pos]
                sampling = jpeg_data[comp_pos + 1]
                comps.append((comp_id, sampling >> 4, sampling & 0x0f))
                comp_pos += 3

            subsampling = 'unknown'
            if len(comps) >= 3:
                y_h, y_v = comps[0][1], comps[0][2]
                c_h, c_v = comps[1][1], comps[1][2]
                if (y_h, y_v, c_h, c_v) == (2, 1, 1, 1):
                    subsampling = 'yuv422'
                elif (y_h, y_v, c_h, c_v) == (2, 2, 1, 1):
                    subsampling = 'yuv420'
                elif (y_h, y_v, c_h, c_v) == (1, 1, 1, 1):
                    subsampling = 'yuv444'

            return {
                'valid': True,
                'baseline': marker == 0xc0,
                'progressive': marker == 0xc2,
                'width': width,
                'height': height,
                'precision': precision,
                'components': comp_count,
                'subsampling': subsampling,
            }

        pos = seg_end

    return {'valid': False, 'reason': 'missing SOF marker'}


# ===========================================================================
# Frame resize / crop
# ===========================================================================

def resize_and_crop(frame, target_w, target_h, mode='crop'):
    """
    Resize frame to target resolution.
    mode='crop':    scale to cover, then center-crop (no black bars, may lose edges)
    mode='fit':     scale to fit, then pad with black (no cropping, may have black bars)
    mode='stretch': stretch directly to target size
    """
    h, w = frame.shape[:2]

    if mode == 'stretch':
        return cv2.resize(frame, (target_w, target_h))

    if mode == 'crop':
        # Scale to cover target area
        scale = max(target_w / w, target_h / h)
        new_w, new_h = int(w * scale), int(h * scale)
        resized = cv2.resize(frame, (new_w, new_h))
        # Center crop
        x0 = (new_w - target_w) // 2
        y0 = (new_h - target_h) // 2
        return resized[y0:y0 + target_h, x0:x0 + target_w]

    if mode == 'fit':
        import numpy as np
        scale = min(target_w / w, target_h / h)
        new_w, new_h = int(w * scale), int(h * scale)
        resized = cv2.resize(frame, (new_w, new_h))
        canvas = np.zeros((target_h, target_w, 3), dtype=np.uint8)
        x0 = (target_w - new_w) // 2
        y0 = (target_h - new_h) // 2
        canvas[y0:y0 + new_h, x0:x0 + new_w] = resized
        return canvas

    raise ValueError(f"Unknown resize mode: {mode}")


# ===========================================================================
# MP4 container builder (ISO 14496-12)
# ===========================================================================

def _u32(v):
    return struct.pack('>I', v)

def _u16(v):
    return struct.pack('>H', v)

def _box(tag, data):
    return struct.pack('>I', 8 + len(data)) + tag + data

def _fbox(tag, ver, flags, data):
    return _box(tag, struct.pack('>I', (ver << 24) | flags) + data)


def build_mp4(jpeg_frames, width, height, fps):
    """Build a minimal MP4 file containing MJPEG video from raw JPEG frames."""
    n = len(jpeg_frames)
    timescale = fps * 100
    sample_duration = 100
    total_duration = n * sample_duration

    # ftyp
    ftyp = _box(b'ftyp', b'isom' + _u32(0x200) + b'isomiso2mp41')

    # mdat
    mdat_payload = b''.join(jpeg_frames)
    mdat = struct.pack('>I', 8 + len(mdat_payload)) + b'mdat' + mdat_payload

    # Sample table info
    sizes = [len(j) for j in jpeg_frames]
    data_start = len(ftyp) + 8  # ftyp size + mdat header (8 bytes)
    offsets = []
    off = data_start
    for s in sizes:
        offsets.append(off)
        off += s

    # stsd - JPEG sample entry
    se = bytearray()
    se += b'\x00' * 6 + _u16(1)        # reserved + data_ref_index
    se += b'\x00' * 16                  # pre_defined + reserved
    se += _u16(width) + _u16(height)
    se += _u32(0x00480000) * 2          # 72 dpi h/v
    se += _u32(0) + _u16(1)             # reserved + frame_count
    se += b'\x00' * 32                  # compressor_name
    se += _u16(0x18)                    # depth = 24
    se += struct.pack('>h', -1)         # pre_defined
    stsd = _fbox(b'stsd', 0, 0, _u32(1) + _box(b'jpeg', bytes(se)))

    stts = _fbox(b'stts', 0, 0, _u32(1) + _u32(n) + _u32(sample_duration))
    stsc = _fbox(b'stsc', 0, 0, _u32(1) + _u32(1) + _u32(n) + _u32(1))
    stsz = _fbox(b'stsz', 0, 0, _u32(0) + _u32(n) + b''.join(_u32(s) for s in sizes))
    stco = _fbox(b'stco', 0, 0, _u32(1) + _u32(offsets[0]))

    stbl = _box(b'stbl', stsd + stts + stsc + stsz + stco)
    dref = _fbox(b'dref', 0, 0, _u32(1) + _fbox(b'url ', 0, 1, b''))
    dinf = _box(b'dinf', dref)
    vmhd = _fbox(b'vmhd', 0, 1, b'\x00' * 8)
    minf = _box(b'minf', vmhd + dinf + stbl)

    hdlr = _fbox(b'hdlr', 0, 0, _u32(0) + b'vide' + b'\x00' * 12 + b'VideoHandler\x00')
    mdhd = _fbox(b'mdhd', 0, 0, _u32(0) + _u32(0) + _u32(timescale) + _u32(total_duration) + _u32(0x55C40000))
    mdia = _box(b'mdia', mdhd + hdlr + minf)

    tkhd_d = (_u32(0) + _u32(0) + _u32(1) + _u32(0) + _u32(total_duration) +
              b'\x00' * 8 + _u16(0) * 2 + _u16(0) + _u16(0) +
              _u32(0x00010000) + _u32(0) + _u32(0) +
              _u32(0) + _u32(0x00010000) + _u32(0) +
              _u32(0) + _u32(0) + _u32(0x40000000) +
              _u32(width << 16) + _u32(height << 16))
    tkhd = _fbox(b'tkhd', 0, 3, tkhd_d)
    trak = _box(b'trak', tkhd + mdia)

    mvhd_d = (_u32(0) + _u32(0) + _u32(timescale) + _u32(total_duration) +
              _u32(0x00010000) + _u16(0x0100) + b'\x00' * 10 +
              _u32(0x00010000) + _u32(0) + _u32(0) +
              _u32(0) + _u32(0x00010000) + _u32(0) +
              _u32(0) + _u32(0) + _u32(0x40000000) +
              b'\x00' * 24 + _u32(2))
    mvhd = _fbox(b'mvhd', 0, 0, mvhd_d)
    moov = _box(b'moov', mvhd + trak)

    return ftyp + mdat + moov


# ===========================================================================
# Converter main logic
# ===========================================================================

def convert(input_path, output_path, target_w, target_h, fps, quality,
            resize_mode, max_size_kb, max_duration, max_frame_kb, min_quality):
    """Convert H.264 MP4 to MJPEG MP4 (YUV422) for BK7258."""

    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        print(f"Error: Cannot open input file: {input_path}")
        return False

    src_fps = cap.get(cv2.CAP_PROP_FPS) or 25
    src_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    src_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    src_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    src_duration = src_frames / src_fps if src_fps > 0 else 0

    print(f"Input:  {input_path}")
    print(f"        {src_w}x{src_h} @ {src_fps:.1f}fps, {src_frames} frames, {src_duration:.1f}s")
    print(f"Output: {target_w}x{target_h} @ {fps}fps, quality={quality}, mode={resize_mode}")
    if max_size_kb:
        print(f"        Max file size: {max_size_kb} KB")
    if max_duration:
        print(f"        Max duration: {max_duration}s")
    if max_frame_kb:
        print(f"        Max JPEG frame: {max_frame_kb} KB")
    print()

    # Calculate output frame count
    out_duration = min(src_duration, max_duration) if max_duration else src_duration
    total_out_frames = int(out_duration * fps)
    max_frame_bytes = max_frame_kb * 1024 if max_frame_kb else None

    jpeg_frames = []
    total_payload_size = 0
    max_frame_size = 0
    quality_adjusted_frames = 0
    min_used_quality = quality
    t_start = time.time()
    current_src_idx = -1
    current_frame = None

    for i in range(total_out_frames):
        # Map output frame index to source frame index
        src_idx = int(i * src_fps / fps)
        if src_idx >= src_frames:
            src_idx = src_frames - 1

        while current_src_idx < src_idx:
            ret, current_frame = cap.read()
            if not ret:
                print(f"\nWarning: Failed to read frame {src_idx}, stopping at frame {i}")
                current_frame = None
                break
            current_src_idx += 1

        if current_frame is None:
            break

        # Resize/crop
        frame = resize_and_crop(current_frame, target_w, target_h, resize_mode)

        # Encode to JPEG with standard YUV 4:2:2
        try:
            jpeg_data, used_quality = encode_jpeg_422_limited(
                frame, quality, max_frame_bytes, min_quality)
        except ValueError as exc:
            cap.release()
            print(f"\nError: {exc}")
            return False

        if used_quality < quality:
            quality_adjusted_frames += 1
            min_used_quality = min(min_used_quality, used_quality)

        max_frame_size = max(max_frame_size, len(jpeg_data))
        jpeg_frames.append(jpeg_data)
        total_payload_size += len(jpeg_data)

        # Check file size limit
        if max_size_kb:
            current_size = total_payload_size + 1024  # ~1KB overhead
            if current_size > max_size_kb * 1024:
                jpeg_frames.pop()  # remove last frame that exceeded limit
                total_payload_size -= len(jpeg_data)
                print(f"\n  File size limit reached at frame {i} ({current_size // 1024} KB)")
                break

        # Progress
        if (i + 1) % 10 == 0 or i == total_out_frames - 1:
            elapsed = time.time() - t_start
            pct = (i + 1) / total_out_frames * 100
            eta = elapsed / (i + 1) * (total_out_frames - i - 1)
            size_kb = total_payload_size // 1024
            print(f"  Converting: {i + 1}/{total_out_frames} ({pct:.0f}%) "
                  f"| {size_kb} KB | ETA {eta:.0f}s")

    cap.release()
    print()

    if not jpeg_frames:
        print("Error: No frames encoded")
        return False

    jpeg_info = inspect_jpeg(jpeg_frames[0])
    if (not jpeg_info.get('valid') or not jpeg_info.get('baseline') or
            jpeg_info.get('progressive') or jpeg_info.get('subsampling') != 'yuv422'):
        print(f"Error: JPEG profile check failed: {jpeg_info}")
        return False

    # Build MP4
    print(f"  Building MP4 ({len(jpeg_frames)} frames)...")
    mp4_data = build_mp4(jpeg_frames, target_w, target_h, fps)

    with open(output_path, 'wb') as f:
        f.write(mp4_data)

    file_size = len(mp4_data)
    out_duration = len(jpeg_frames) / fps
    avg_frame = sum(len(j) for j in jpeg_frames) // len(jpeg_frames)

    print(f"\nDone!")
    print(f"  Output:     {output_path}")
    print(f"  Size:       {file_size // 1024} KB ({file_size:,} bytes)")
    print(f"  Duration:   {out_duration:.1f}s ({len(jpeg_frames)} frames @ {fps}fps)")
    print(f"  Avg frame:  {avg_frame:,} bytes")
    print(f"  Max frame:  {max_frame_size:,} bytes")
    if quality_adjusted_frames:
        print(f"  Quality:    requested {quality}, min used {min_used_quality} "
              f"({quality_adjusted_frames} frames adjusted)")
    else:
        print(f"  Quality:    {quality}")
    print(f"  Format:     MP4 / MJPEG / YUV422 / no audio / {target_w}x{target_h}")
    print(f"  JPEG:       baseline / {jpeg_info.get('subsampling')} / "
          f"{jpeg_info.get('width')}x{jpeg_info.get('height')}")
    print(f"  Compatible: BK7258 HW JPEG Decoder OK")
    return True


# ===========================================================================
# CLI
# ===========================================================================

def main():
    parser = argparse.ArgumentParser(
        description='MP4 H.264/H.265 -> MP4 MJPEG YUV422 converter for BK7258',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s input.mp4                          # Default: 480x480, 25fps, q85
  %(prog)s input.mp4 -o out.mp4               # Specify output path
  %(prog)s input.mp4 -W 480 -H 480 -q 65      # Higher quality
  %(prog)s input.mp4 --max-size 2700           # Limit output to 2700KB (fit PSRAM)
  %(prog)s input.mp4 --max-duration 10         # Limit to 10 seconds
  %(prog)s input.mp4 --resize-mode fit         # Fit with black bars (no crop)
""")
    parser.add_argument('input', help='Input MP4 file (H.264)')
    parser.add_argument('-o', '--output', help='Output MP4 file path')
    parser.add_argument('-W', '--width', type=int, default=TERMINAL_DEFAULT_WIDTH,
                        help='Output width (default: 480)')
    parser.add_argument('-H', '--height', type=int, default=TERMINAL_DEFAULT_HEIGHT,
                        help='Output height (default: 480)')
    parser.add_argument('-f', '--fps', type=int, default=TERMINAL_DEFAULT_FPS,
                        help='Output FPS (default: 25, terminal range: 20-25)')
    parser.add_argument('-q', '--quality', type=int, default=TERMINAL_DEFAULT_QUALITY,
                        help='JPEG quality 1-95 (default: 85, recommended: 75-90)')
    parser.add_argument('-m', '--resize-mode', choices=['crop', 'fit', 'stretch'],
                        default='fit', help='Resize mode (default: fit)')
    parser.add_argument('--max-size', type=int, default=None,
                        help='Max output file size in KB (e.g. 2700 for ~2.7MB PSRAM)')
    parser.add_argument('--max-duration', type=float, default=None,
                        help='Max output duration in seconds')
    parser.add_argument('--max-frame-kb', type=int, default=TERMINAL_DEFAULT_MAX_FRAME_KB,
                        help='Max single JPEG frame size in KB (default: 96)')
    parser.add_argument('--min-quality', type=int, default=TERMINAL_DEFAULT_MIN_QUALITY,
                        help='Minimum quality for automatic per-frame size limiting (default: 50)')

    args = parser.parse_args()

    if not os.path.isfile(args.input):
        print(f"Error: Input file not found: {args.input}")
        sys.exit(1)

    if args.output is None:
        base = os.path.splitext(args.input)[0]
        args.output = f"{base}_bk7258_{args.width}x{args.height}_{args.fps}fps_q{args.quality}.mp4"

    if args.width <= 0 or args.height <= 0 or args.width % 2 or args.height % 2:
        print("Error: width and height must be positive even numbers")
        sys.exit(1)

    if args.fps < 20 or args.fps > 25:
        print("Error: terminal profile requires FPS in range 20-25")
        sys.exit(1)

    if args.quality < 1 or args.quality > 95:
        print("Error: quality must be in range 1-95")
        sys.exit(1)

    if args.min_quality < 1 or args.min_quality > args.quality:
        print("Error: min-quality must be in range 1..quality")
        sys.exit(1)

    print("=" * 60)
    print(f"  BK7258 SmartKid Video Converter v{APP_VERSION}")
    print("  MP4 (H.264/H.265) -> MP4 (MJPEG YUV422)")
    print("=" * 60)
    print()

    ok = convert(
        input_path=args.input,
        output_path=args.output,
        target_w=args.width,
        target_h=args.height,
        fps=args.fps,
        quality=args.quality,
        resize_mode=args.resize_mode,
        max_size_kb=args.max_size,
        max_duration=args.max_duration,
        max_frame_kb=args.max_frame_kb,
        min_quality=args.min_quality,
    )

    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
