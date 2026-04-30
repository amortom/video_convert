package com.amortom.bk7258converter;

import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;

final class JpegInspector {
    private JpegInspector() {
    }

    static JpegInfo inspect(File file) throws IOException {
        long size = file.length();
        if (size <= 0 || size > Integer.MAX_VALUE) {
            return JpegInfo.invalid("invalid file size");
        }
        byte[] data = new byte[(int) size];
        try (FileInputStream in = new FileInputStream(file)) {
            int off = 0;
            while (off < data.length) {
                int read = in.read(data, off, data.length - off);
                if (read == -1) {
                    break;
                }
                off += read;
            }
            if (off != data.length) {
                return JpegInfo.invalid("short read");
            }
        }
        return inspect(data);
    }

    static JpegInfo inspect(byte[] data) {
        if (data.length < 4 || u8(data[0]) != 0xff || u8(data[1]) != 0xd8) {
            return JpegInfo.invalid("missing SOI marker");
        }

        int pos = 2;
        while (pos + 4 <= data.length) {
            while (pos < data.length && u8(data[pos]) == 0xff) {
                pos++;
            }
            if (pos >= data.length) {
                break;
            }

            int marker = u8(data[pos++]);
            if (marker == 0xd8 || marker == 0xd9) {
                continue;
            }
            if (marker >= 0xd0 && marker <= 0xd7) {
                continue;
            }
            if (pos + 2 > data.length) {
                break;
            }

            int segmentLength = u16(data, pos);
            int segmentStart = pos + 2;
            int segmentEnd = pos + segmentLength;
            if (segmentLength < 2 || segmentEnd > data.length) {
                break;
            }

            if (marker == 0xc0 || marker == 0xc2) {
                if (segmentStart + 6 > segmentEnd) {
                    break;
                }
                int precision = u8(data[segmentStart]);
                int height = u16(data, segmentStart + 1);
                int width = u16(data, segmentStart + 3);
                int componentCount = u8(data[segmentStart + 5]);
                int compPos = segmentStart + 6;

                int yH = -1;
                int yV = -1;
                int cH = -1;
                int cV = -1;
                for (int i = 0; i < componentCount; i++) {
                    if (compPos + 3 > segmentEnd) {
                        break;
                    }
                    int sampling = u8(data[compPos + 1]);
                    if (i == 0) {
                        yH = sampling >> 4;
                        yV = sampling & 0x0f;
                    } else if (i == 1) {
                        cH = sampling >> 4;
                        cV = sampling & 0x0f;
                    }
                    compPos += 3;
                }

                String subsampling = samplingName(yH, yV, cH, cV);

                return new JpegInfo(true, marker == 0xc0, marker == 0xc2,
                        width, height, precision, componentCount, subsampling, "",
                        yH, yV, cH, cV);
            }

            pos = segmentEnd;
        }

        return JpegInfo.invalid("missing SOF marker");
    }

    private static String samplingName(int yH, int yV, int cH, int cV) {
        if (yH <= 0 || yV <= 0 || cH <= 0 || cV <= 0) {
            return "unknown";
        }

        if (yH == cH && yV == cV) {
            return "yuv444";
        }
        if (yH == cH * 2 && yV == cV) {
            return "yuv422";
        }
        if (yH == cH * 2 && yV == cV * 2) {
            return "yuv420";
        }

        // Some encoders scale all vertical sampling factors by 2. For example,
        // FFmpeg may emit 4:2:2 as Y=2x2 and Cb/Cr=1x2.
        if (yH / (double) cH == 2.0 && yV / (double) cV == 1.0) {
            return "yuv422";
        }
        if (yH / (double) cH == 2.0 && yV / (double) cV == 2.0) {
            return "yuv420";
        }

        return "unknown";
    }

    private static int u8(byte value) {
        return value & 0xff;
    }

    private static int u16(byte[] data, int offset) {
        return (u8(data[offset]) << 8) | u8(data[offset + 1]);
    }

    static final class JpegInfo {
        final boolean valid;
        final boolean baseline;
        final boolean progressive;
        final int width;
        final int height;
        final int precision;
        final int componentCount;
        final String subsampling;
        final String reason;
        final int yH;
        final int yV;
        final int cH;
        final int cV;

        JpegInfo(boolean valid, boolean baseline, boolean progressive,
                 int width, int height, int precision, int componentCount,
                 String subsampling, String reason,
                 int yH, int yV, int cH, int cV) {
            this.valid = valid;
            this.baseline = baseline;
            this.progressive = progressive;
            this.width = width;
            this.height = height;
            this.precision = precision;
            this.componentCount = componentCount;
            this.subsampling = subsampling;
            this.reason = reason;
            this.yH = yH;
            this.yV = yV;
            this.cH = cH;
            this.cV = cV;
        }

        static JpegInfo invalid(String reason) {
            return new JpegInfo(false, false, false, 0, 0, 0, 0,
                    "unknown", reason, -1, -1, -1, -1);
        }
    }
}
