package com.amortom.bk7258converter;

import android.graphics.Bitmap;
import android.graphics.BitmapFactory;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;

/**
 * Re-encodes JPEG frames that have non-standard 4:2:2 sampling factors
 * (e.g. Y=2x2/C=1x2 from some FFmpeg builds) into standard Y=2x1/C=1x1
 * that the BK7258 hardware JPEG decoder requires.
 */
final class JpegSamplingFixer {
    private JpegSamplingFixer() {}

    /**
     * Returns true if the JPEG has ratio-equivalent 4:2:2 but non-standard sampling factors.
     */
    static boolean needsFix(JpegInspector.JpegInfo info) {
        if (!info.valid || !info.baseline) return false;
        // Already standard 4:2:2
        if (info.yH == 2 && info.yV == 1 && info.cH == 1 && info.cV == 1) return false;
        // Check ratio-equivalent 4:2:2 (horizontal 2:1, vertical 1:1)
        if (info.yH <= 0 || info.cH <= 0 || info.yV <= 0 || info.cV <= 0) return false;
        return info.yH == info.cH * 2 && info.yV == info.cV;
    }

    /**
     * Re-encodes a JPEG file with standard Y=2x1/C=1x1 (4:2:2) sampling
     * using a custom baseline JPEG encoder.
     */
    static void fix(File file, int quality) throws IOException {
        Bitmap bmp = BitmapFactory.decodeFile(file.getAbsolutePath());
        if (bmp == null) throw new IOException("Cannot decode: " + file.getName());
        try {
            Jpeg422Encoder encoder = new Jpeg422Encoder(quality);
            byte[] jpeg = encoder.encode(bmp);
            try (FileOutputStream fos = new FileOutputStream(file)) {
                fos.write(jpeg);
            }
        } finally {
            bmp.recycle();
        }
    }
}
