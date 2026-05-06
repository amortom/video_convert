package com.amortom.bk7258converter;

import android.graphics.Bitmap;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.OutputStream;

/**
 * Minimal baseline JPEG encoder that guarantees standard YUV 4:2:2 sampling
 * factors (Y=2x1, Cb=1x1, Cr=1x1) required by the BK7258 hardware decoder.
 */
final class Jpeg422Encoder {

    private final int[] lumaQt = new int[64];
    private final int[] chromaQt = new int[64];

    private static final int[] STD_LUMA_QT = {
            16, 11, 10, 16, 24, 40, 51, 61,
            12, 12, 14, 19, 26, 58, 60, 55,
            14, 13, 16, 24, 40, 57, 69, 56,
            14, 17, 22, 29, 51, 87, 80, 62,
            18, 22, 37, 56, 68, 109, 103, 77,
            24, 35, 55, 64, 81, 104, 113, 92,
            49, 64, 78, 87, 103, 121, 120, 101,
            72, 92, 95, 98, 112, 100, 103, 99
    };

    private static final int[] STD_CHROMA_QT = {
            17, 18, 24, 47, 99, 99, 99, 99,
            18, 21, 26, 66, 99, 99, 99, 99,
            24, 26, 56, 99, 99, 99, 99, 99,
            47, 66, 99, 99, 99, 99, 99, 99,
            99, 99, 99, 99, 99, 99, 99, 99,
            99, 99, 99, 99, 99, 99, 99, 99,
            99, 99, 99, 99, 99, 99, 99, 99,
            99, 99, 99, 99, 99, 99, 99, 99
    };

    private static final int[] ZIGZAG = {
            0, 1, 8, 16, 9, 2, 3, 10,
            17, 24, 32, 25, 18, 11, 4, 5,
            12, 19, 26, 33, 40, 48, 41, 34,
            27, 20, 13, 6, 7, 14, 21, 28,
            35, 42, 49, 56, 57, 50, 43, 36,
            29, 22, 15, 23, 30, 37, 44, 51,
            58, 59, 52, 45, 38, 31, 39, 46,
            53, 60, 61, 54, 47, 55, 62, 63
    };

    // Pre-computed cosine table for DCT
    private static final double[][] COS = new double[8][8];

    static {
        for (int k = 0; k < 8; k++)
            for (int n = 0; n < 8; n++)
                COS[k][n] = Math.cos((2 * n + 1) * k * Math.PI / 16.0);
    }

    // Standard Huffman tables (JPEG Annex K)
    private static final int[] DC_LUMA_BITS = {0, 1, 5, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0};
    private static final int[] DC_LUMA_VALS = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11};

    private static final int[] DC_CHROMA_BITS = {0, 3, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0};
    private static final int[] DC_CHROMA_VALS = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11};

    private static final int[] AC_LUMA_BITS = {0, 2, 1, 3, 3, 2, 4, 3, 5, 5, 4, 4, 0, 0, 1, 0x7d};
    private static final int[] AC_LUMA_VALS = {
            0x01, 0x02, 0x03, 0x00, 0x04, 0x11, 0x05, 0x12, 0x21, 0x31, 0x41, 0x06, 0x13, 0x51, 0x61, 0x07,
            0x22, 0x71, 0x14, 0x32, 0x81, 0x91, 0xa1, 0x08, 0x23, 0x42, 0xb1, 0xc1, 0x15, 0x52, 0xd1, 0xf0,
            0x24, 0x33, 0x62, 0x72, 0x82, 0x09, 0x0a, 0x16, 0x17, 0x18, 0x19, 0x1a, 0x25, 0x26, 0x27, 0x28,
            0x29, 0x2a, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39, 0x3a, 0x43, 0x44, 0x45, 0x46, 0x47, 0x48, 0x49,
            0x4a, 0x53, 0x54, 0x55, 0x56, 0x57, 0x58, 0x59, 0x5a, 0x63, 0x64, 0x65, 0x66, 0x67, 0x68, 0x69,
            0x6a, 0x73, 0x74, 0x75, 0x76, 0x77, 0x78, 0x79, 0x7a, 0x83, 0x84, 0x85, 0x86, 0x87, 0x88, 0x89,
            0x8a, 0x92, 0x93, 0x94, 0x95, 0x96, 0x97, 0x98, 0x99, 0x9a, 0xa2, 0xa3, 0xa4, 0xa5, 0xa6, 0xa7,
            0xa8, 0xa9, 0xaa, 0xb2, 0xb3, 0xb4, 0xb5, 0xb6, 0xb7, 0xb8, 0xb9, 0xba, 0xc2, 0xc3, 0xc4, 0xc5,
            0xc6, 0xc7, 0xc8, 0xc9, 0xca, 0xd2, 0xd3, 0xd4, 0xd5, 0xd6, 0xd7, 0xd8, 0xd9, 0xda, 0xe1, 0xe2,
            0xe3, 0xe4, 0xe5, 0xe6, 0xe7, 0xe8, 0xe9, 0xea, 0xf1, 0xf2, 0xf3, 0xf4, 0xf5, 0xf6, 0xf7, 0xf8,
            0xf9, 0xfa
    };

    private static final int[] AC_CHROMA_BITS = {0, 2, 1, 2, 4, 4, 3, 4, 7, 5, 4, 4, 0, 1, 2, 0x77};
    private static final int[] AC_CHROMA_VALS = {
            0x00, 0x01, 0x02, 0x03, 0x11, 0x04, 0x05, 0x21, 0x31, 0x06, 0x12, 0x41, 0x51, 0x07, 0x61, 0x71,
            0x13, 0x22, 0x32, 0x81, 0x08, 0x14, 0x42, 0x91, 0xa1, 0xb1, 0xc1, 0x09, 0x23, 0x33, 0x52, 0xf0,
            0x15, 0x62, 0x72, 0xd1, 0x0a, 0x16, 0x24, 0x34, 0xe1, 0x25, 0xf1, 0x17, 0x18, 0x19, 0x1a, 0x26,
            0x27, 0x28, 0x29, 0x2a, 0x35, 0x36, 0x37, 0x38, 0x39, 0x3a, 0x43, 0x44, 0x45, 0x46, 0x47, 0x48,
            0x49, 0x4a, 0x53, 0x54, 0x55, 0x56, 0x57, 0x58, 0x59, 0x5a, 0x63, 0x64, 0x65, 0x66, 0x67, 0x68,
            0x69, 0x6a, 0x73, 0x74, 0x75, 0x76, 0x77, 0x78, 0x79, 0x7a, 0x82, 0x83, 0x84, 0x85, 0x86, 0x87,
            0x88, 0x89, 0x8a, 0x92, 0x93, 0x94, 0x95, 0x96, 0x97, 0x98, 0x99, 0x9a, 0xa2, 0xa3, 0xa4, 0xa5,
            0xa6, 0xa7, 0xa8, 0xa9, 0xaa, 0xb2, 0xb3, 0xb4, 0xb5, 0xb6, 0xb7, 0xb8, 0xb9, 0xba, 0xc2, 0xc3,
            0xc4, 0xc5, 0xc6, 0xc7, 0xc8, 0xc9, 0xca, 0xd2, 0xd3, 0xd4, 0xd5, 0xd6, 0xd7, 0xd8, 0xd9, 0xda,
            0xe2, 0xe3, 0xe4, 0xe5, 0xe6, 0xe7, 0xe8, 0xe9, 0xea, 0xf2, 0xf3, 0xf4, 0xf5, 0xf6, 0xf7, 0xf8,
            0xf9, 0xfa
    };

    // Compiled Huffman lookup: [symbol] -> {code, length}
    private final int[] dcLumaCode, dcLumaLen;
    private final int[] dcChromaCode, dcChromaLen;
    private final int[] acLumaCode, acLumaLen;
    private final int[] acChromaCode, acChromaLen;

    Jpeg422Encoder(int quality) {
        int s = quality < 50 ? 5000 / quality : 200 - quality * 2;
        for (int i = 0; i < 64; i++) {
            lumaQt[i] = clamp1_255((STD_LUMA_QT[i] * s + 50) / 100);
            chromaQt[i] = clamp1_255((STD_CHROMA_QT[i] * s + 50) / 100);
        }
        dcLumaCode = new int[17];
        dcLumaLen = new int[17];
        buildHuff(DC_LUMA_BITS, DC_LUMA_VALS, dcLumaCode, dcLumaLen);
        dcChromaCode = new int[17];
        dcChromaLen = new int[17];
        buildHuff(DC_CHROMA_BITS, DC_CHROMA_VALS, dcChromaCode, dcChromaLen);
        acLumaCode = new int[256];
        acLumaLen = new int[256];
        buildHuff(AC_LUMA_BITS, AC_LUMA_VALS, acLumaCode, acLumaLen);
        acChromaCode = new int[256];
        acChromaLen = new int[256];
        buildHuff(AC_CHROMA_BITS, AC_CHROMA_VALS, acChromaCode, acChromaLen);
    }

    private static void buildHuff(int[] bits, int[] vals, int[] codes, int[] lens) {
        int code = 0, k = 0;
        for (int i = 0; i < 16; i++) {
            for (int j = 0; j < bits[i]; j++) {
                codes[vals[k]] = code;
                lens[vals[k]] = i + 1;
                k++;
                code++;
            }
            code <<= 1;
        }
    }

    byte[] encode(Bitmap bmp) throws IOException {
        int w = bmp.getWidth();
        int h = bmp.getHeight();
        int[] px = new int[w * h];
        bmp.getPixels(px, 0, w, 0, 0, w, h);

        int cw = (w + 1) / 2;
        int[] yP = new int[w * h];
        int[] cbP = new int[cw * h];
        int[] crP = new int[cw * h];
        rgbToYcc(px, yP, cbP, crP, w, h, cw);

        ByteArrayOutputStream out = new ByteArrayOutputStream();
        writeMarker(out, 0xD8);                         // SOI
        writeApp0(out);                                  // JFIF
        writeDqt(out, 0, lumaQt);                        // Luma QT
        writeDqt(out, 1, chromaQt);                      // Chroma QT
        writeSof(out, w, h);                             // SOF0: Y=2x1 Cb=1x1 Cr=1x1
        writeDht(out, 0, 0, DC_LUMA_BITS, DC_LUMA_VALS);
        writeDht(out, 1, 0, AC_LUMA_BITS, AC_LUMA_VALS);
        writeDht(out, 0, 1, DC_CHROMA_BITS, DC_CHROMA_VALS);
        writeDht(out, 1, 1, AC_CHROMA_BITS, AC_CHROMA_VALS);
        writeSos(out);                                   // SOS header
        writeScan(out, yP, cbP, crP, w, h, cw);         // Entropy data
        writeMarker(out, 0xD9);                          // EOI
        return out.toByteArray();
    }

    // ---- colour conversion ----

    private static void rgbToYcc(int[] px, int[] y, int[] cb, int[] cr,
                                 int w, int h, int cw) {
        for (int row = 0; row < h; row++) {
            int rw = row * w;
            int rc = row * cw;
            for (int col = 0; col < w; col += 2) {
                int p0 = px[rw + col];
                int r0 = (p0 >> 16) & 0xff, g0 = (p0 >> 8) & 0xff, b0 = p0 & 0xff;
                int p1 = col + 1 < w ? px[rw + col + 1] : p0;
                int r1 = (p1 >> 16) & 0xff, g1 = (p1 >> 8) & 0xff, b1 = p1 & 0xff;

                y[rw + col] = clamp0_255((77 * r0 + 150 * g0 + 29 * b0 + 128) >> 8);
                if (col + 1 < w)
                    y[rw + col + 1] = clamp0_255((77 * r1 + 150 * g1 + 29 * b1 + 128) >> 8);

                int rS = r0 + r1, gS = g0 + g1, bS = b0 + b1;
                cb[rc + col / 2] = clamp0_255(((-43 * rS - 85 * gS + 128 * bS + 256) >> 9) + 128);
                cr[rc + col / 2] = clamp0_255(((128 * rS - 107 * gS - 21 * bS + 256) >> 9) + 128);
            }
        }
    }

    // ---- DCT & quantisation ----

    private static void fdct(int[] blk) {
        double[] tmp = new double[64];
        for (int r = 0; r < 8; r++) {
            int off = r << 3;
            for (int k = 0; k < 8; k++) {
                double s = 0;
                for (int n = 0; n < 8; n++) s += blk[off + n] * COS[k][n];
                tmp[off + k] = s * (k == 0 ? 1.0 / Math.sqrt(8) : 0.5);
            }
        }
        for (int c = 0; c < 8; c++) {
            for (int k = 0; k < 8; k++) {
                double s = 0;
                for (int n = 0; n < 8; n++) s += tmp[(n << 3) + c] * COS[k][n];
                blk[(k << 3) + c] = (int) Math.round(s * (k == 0 ? 1.0 / Math.sqrt(8) : 0.5));
            }
        }
    }

    private static void quantZigzag(int[] blk, int[] qt) {
        int[] out = new int[64];
        for (int i = 0; i < 64; i++) {
            int pos = ZIGZAG[i];
            int q = qt[pos];
            out[i] = (blk[pos] + (blk[pos] > 0 ? q / 2 : -q / 2)) / q;
        }
        System.arraycopy(out, 0, blk, 0, 64);
    }

    // ---- entropy coding ----

    private void writeScan(OutputStream raw, int[] yP, int[] cbP, int[] crP,
                           int w, int h, int cw) throws IOException {
        BitWriter bw = new BitWriter(raw);
        int[] dcPred = new int[3];
        int mcuCols = (w + 15) / 16;
        int mcuRows = (h + 7) / 8;

        for (int mr = 0; mr < mcuRows; mr++) {
            for (int mc = 0; mc < mcuCols; mc++) {
                // Y0 (left 8x8)
                encodeBlock(bw, getBlock(yP, w, h, mc * 16, mr * 8),
                        lumaQt, dcPred, 0, dcLumaCode, dcLumaLen, acLumaCode, acLumaLen);
                // Y1 (right 8x8)
                encodeBlock(bw, getBlock(yP, w, h, mc * 16 + 8, mr * 8),
                        lumaQt, dcPred, 0, dcLumaCode, dcLumaLen, acLumaCode, acLumaLen);
                // Cb
                encodeBlock(bw, getBlock(cbP, cw, h, mc * 8, mr * 8),
                        chromaQt, dcPred, 1, dcChromaCode, dcChromaLen, acChromaCode, acChromaLen);
                // Cr
                encodeBlock(bw, getBlock(crP, cw, h, mc * 8, mr * 8),
                        chromaQt, dcPred, 2, dcChromaCode, dcChromaLen, acChromaCode, acChromaLen);
            }
        }
        bw.flush();
    }

    private static int[] getBlock(int[] plane, int pw, int ph, int x0, int y0) {
        int[] b = new int[64];
        for (int r = 0; r < 8; r++) {
            int y = y0 + r;
            if (y >= ph) continue;
            int rowOff = y * pw;
            for (int c = 0; c < 8; c++) {
                int x = x0 + c;
                if (x < pw) b[(r << 3) + c] = plane[rowOff + x] - 128;
            }
        }
        return b;
    }

    private void encodeBlock(BitWriter bw, int[] blk, int[] qt, int[] dcPred,
                             int comp, int[] dcC, int[] dcL, int[] acC, int[] acL) throws IOException {
        fdct(blk);
        quantZigzag(blk, qt);

        int diff = blk[0] - dcPred[comp];
        dcPred[comp] = blk[0];
        int cat = category(diff);
        bw.writeBits(dcC[cat], dcL[cat]);
        if (cat > 0) bw.writeBits(encodeVal(diff, cat), cat);

        int last = 63;
        while (last > 0 && blk[last] == 0) last--;

        int run = 0;
        for (int i = 1; i <= last; i++) {
            if (blk[i] == 0) {
                run++;
                if (run == 16) {
                    bw.writeBits(acC[0xF0], acL[0xF0]);
                    run = 0;
                }
            } else {
                cat = category(blk[i]);
                int sym = (run << 4) | cat;
                bw.writeBits(acC[sym], acL[sym]);
                bw.writeBits(encodeVal(blk[i], cat), cat);
                run = 0;
            }
        }
        if (last < 63) bw.writeBits(acC[0], acL[0]); // EOB
    }

    private static int category(int v) {
        if (v < 0) v = -v;
        int c = 0;
        while (v > 0) { v >>= 1; c++; }
        return c;
    }

    private static int encodeVal(int v, int cat) {
        return v < 0 ? v + (1 << cat) - 1 : v;
    }

    // ---- marker writers ----

    private static void writeMarker(OutputStream o, int marker) throws IOException {
        o.write(0xFF);
        o.write(marker);
    }

    private static void writeApp0(OutputStream o) throws IOException {
        writeMarker(o, 0xE0);
        byte[] d = {0, 16, 0x4A, 0x46, 0x49, 0x46, 0, 1, 1, 0, 0, 1, 0, 1, 0, 0};
        o.write(d);
    }

    private void writeDqt(OutputStream o, int id, int[] qt) throws IOException {
        writeMarker(o, 0xDB);
        o.write(0); o.write(67); // length = 2 + 1 + 64
        o.write(id);
        for (int i = 0; i < 64; i++) o.write(qt[ZIGZAG[i]]);
    }

    private static void writeSof(OutputStream o, int w, int h) throws IOException {
        writeMarker(o, 0xC0);
        o.write(0); o.write(17); // length
        o.write(8);              // precision
        o.write(h >> 8); o.write(h & 0xFF);
        o.write(w >> 8); o.write(w & 0xFF);
        o.write(3);              // components
        o.write(1); o.write(0x21); o.write(0); // Y: H=2 V=1 Qt=0
        o.write(2); o.write(0x11); o.write(1); // Cb: H=1 V=1 Qt=1
        o.write(3); o.write(0x11); o.write(1); // Cr: H=1 V=1 Qt=1
    }

    private static void writeDht(OutputStream o, int acFlag, int id,
                                 int[] bits, int[] vals) throws IOException {
        writeMarker(o, 0xC4);
        int len = 2 + 1 + 16 + vals.length;
        o.write(len >> 8); o.write(len & 0xFF);
        o.write((acFlag << 4) | id);
        for (int b : bits) o.write(b);
        for (int v : vals) o.write(v);
    }

    private static void writeSos(OutputStream o) throws IOException {
        writeMarker(o, 0xDA);
        o.write(0); o.write(12); // length
        o.write(3);              // components
        o.write(1); o.write(0x00); // Y  → DC0/AC0
        o.write(2); o.write(0x11); // Cb → DC1/AC1
        o.write(3); o.write(0x11); // Cr → DC1/AC1
        o.write(0); o.write(63); o.write(0); // spectral, approx
    }

    // ---- helpers ----

    private static int clamp0_255(int v) { return v < 0 ? 0 : Math.min(v, 255); }
    private static int clamp1_255(int v) { return v < 1 ? 1 : Math.min(v, 255); }

    // ---- bit writer with byte-stuffing ----

    private static final class BitWriter {
        private final OutputStream out;
        private int buf;
        private int bits;

        BitWriter(OutputStream out) { this.out = out; }

        void writeBits(int code, int len) throws IOException {
            buf = (buf << len) | (code & ((1 << len) - 1));
            bits += len;
            while (bits >= 8) {
                bits -= 8;
                int b = (buf >> bits) & 0xFF;
                out.write(b);
                if (b == 0xFF) out.write(0); // byte stuffing
            }
        }

        void flush() throws IOException {
            if (bits > 0) {
                int b = (buf << (8 - bits)) | ((1 << (8 - bits)) - 1);
                out.write(b & 0xFF);
                if ((b & 0xFF) == 0xFF) out.write(0);
                bits = 0;
                buf = 0;
            }
        }
    }
}
