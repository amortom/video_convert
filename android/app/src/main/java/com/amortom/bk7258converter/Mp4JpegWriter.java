package com.amortom.bk7258converter;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.util.List;

final class Mp4JpegWriter {
    private Mp4JpegWriter() {
    }

    static void write(File output, List<File> frames, int width, int height, int fps) throws IOException {
        if (frames.isEmpty()) {
            throw new IOException("No JPEG frames to write");
        }

        int[] sizes = new int[frames.size()];
        long payloadSize = 0;
        for (int i = 0; i < frames.size(); i++) {
            long size = frames.get(i).length();
            if (size <= 0 || size > Integer.MAX_VALUE) {
                throw new IOException("Invalid JPEG frame size: " + frames.get(i).getName());
            }
            sizes[i] = (int) size;
            payloadSize += size;
        }
        if (payloadSize + 8 > 0xffffffffL) {
            throw new IOException("Output is too large for 32-bit MP4 boxes");
        }

        byte[] ftyp = box("ftyp", concat(ascii("isom"), u32(0x200), ascii("isomiso2mp41")));
        int firstFrameOffset = ftyp.length + 8;

        byte[] moov = buildMoov(sizes, firstFrameOffset, width, height, fps);

        try (FileOutputStream out = new FileOutputStream(output)) {
            out.write(ftyp);
            out.write(u32((int) (8 + payloadSize)));
            out.write(ascii("mdat"));

            byte[] buffer = new byte[256 * 1024];
            for (File frame : frames) {
                try (FileInputStream in = new FileInputStream(frame)) {
                    int read;
                    while ((read = in.read(buffer)) != -1) {
                        out.write(buffer, 0, read);
                    }
                }
            }

            out.write(moov);
        }
    }

    private static byte[] buildMoov(int[] sizes, int firstFrameOffset,
                                    int width, int height, int fps) throws IOException {
        int sampleCount = sizes.length;
        int timescale = fps * 100;
        int sampleDuration = 100;
        int totalDuration = sampleCount * sampleDuration;

        ByteArrayOutputStream sampleEntry = new ByteArrayOutputStream();
        sampleEntry.write(new byte[6]);
        sampleEntry.write(u16(1));
        sampleEntry.write(new byte[16]);
        sampleEntry.write(u16(width));
        sampleEntry.write(u16(height));
        sampleEntry.write(u32(0x00480000));
        sampleEntry.write(u32(0x00480000));
        sampleEntry.write(u32(0));
        sampleEntry.write(u16(1));
        sampleEntry.write(new byte[32]);
        sampleEntry.write(u16(0x18));
        sampleEntry.write(i16(-1));

        byte[] stsd = fbox("stsd", 0, 0,
                concat(u32(1), box("jpeg", sampleEntry.toByteArray())));
        byte[] stts = fbox("stts", 0, 0,
                concat(u32(1), u32(sampleCount), u32(sampleDuration)));
        byte[] stsc = fbox("stsc", 0, 0,
                concat(u32(1), u32(1), u32(sampleCount), u32(1)));

        ByteArrayOutputStream stszPayload = new ByteArrayOutputStream();
        stszPayload.write(u32(0));
        stszPayload.write(u32(sampleCount));
        for (int size : sizes) {
            stszPayload.write(u32(size));
        }
        byte[] stsz = fbox("stsz", 0, 0, stszPayload.toByteArray());
        byte[] stco = fbox("stco", 0, 0, concat(u32(1), u32(firstFrameOffset)));

        byte[] stbl = box("stbl", concat(stsd, stts, stsc, stsz, stco));
        byte[] dref = fbox("dref", 0, 0, concat(u32(1), fbox("url ", 0, 1, new byte[0])));
        byte[] dinf = box("dinf", dref);
        byte[] vmhd = fbox("vmhd", 0, 1, new byte[8]);
        byte[] minf = box("minf", concat(vmhd, dinf, stbl));

        byte[] hdlr = fbox("hdlr", 0, 0,
                concat(u32(0), ascii("vide"), new byte[12], ascii("VideoHandler\0")));
        byte[] mdhd = fbox("mdhd", 0, 0,
                concat(u32(0), u32(0), u32(timescale), u32(totalDuration), u32(0x55C40000)));
        byte[] mdia = box("mdia", concat(mdhd, hdlr, minf));

        byte[] tkhdPayload = concat(
                u32(0), u32(0), u32(1), u32(0), u32(totalDuration),
                new byte[8], u16(0), u16(0), u16(0), u16(0),
                u32(0x00010000), u32(0), u32(0),
                u32(0), u32(0x00010000), u32(0),
                u32(0), u32(0), u32(0x40000000),
                u32(width << 16), u32(height << 16)
        );
        byte[] tkhd = fbox("tkhd", 0, 3, tkhdPayload);
        byte[] trak = box("trak", concat(tkhd, mdia));

        byte[] mvhdPayload = concat(
                u32(0), u32(0), u32(timescale), u32(totalDuration),
                u32(0x00010000), u16(0x0100), new byte[10],
                u32(0x00010000), u32(0), u32(0),
                u32(0), u32(0x00010000), u32(0),
                u32(0), u32(0), u32(0x40000000),
                new byte[24], u32(2)
        );
        byte[] mvhd = fbox("mvhd", 0, 0, mvhdPayload);
        return box("moov", concat(mvhd, trak));
    }

    private static byte[] box(String type, byte[] payload) throws IOException {
        return concat(u32(8 + payload.length), ascii(type), payload);
    }

    private static byte[] fbox(String type, int version, int flags, byte[] payload) throws IOException {
        return box(type, concat(u32((version << 24) | flags), payload));
    }

    private static byte[] u32(int value) {
        return new byte[]{
                (byte) ((value >>> 24) & 0xff),
                (byte) ((value >>> 16) & 0xff),
                (byte) ((value >>> 8) & 0xff),
                (byte) (value & 0xff)
        };
    }

    private static byte[] u16(int value) {
        return new byte[]{
                (byte) ((value >>> 8) & 0xff),
                (byte) (value & 0xff)
        };
    }

    private static byte[] i16(int value) {
        return u16(value & 0xffff);
    }

    private static byte[] ascii(String value) {
        byte[] out = new byte[value.length()];
        for (int i = 0; i < value.length(); i++) {
            out[i] = (byte) value.charAt(i);
        }
        return out;
    }

    private static byte[] concat(byte[]... chunks) throws IOException {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        for (byte[] chunk : chunks) {
            out.write(chunk);
        }
        return out.toByteArray();
    }
}
