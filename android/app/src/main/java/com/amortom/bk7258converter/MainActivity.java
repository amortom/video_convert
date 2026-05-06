package com.amortom.bk7258converter;

import android.app.Activity;
import android.content.Intent;
import android.database.Cursor;
import android.net.Uri;
import android.os.Bundle;
import android.provider.OpenableColumns;
import android.text.InputType;
import android.view.View;
import android.view.Window;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.ScrollView;
import android.widget.Spinner;
import android.widget.TextView;
import android.widget.Toast;

import com.arthenica.ffmpegkit.FFmpegKit;
import com.arthenica.ffmpegkit.FFmpegSession;
import com.arthenica.ffmpegkit.ReturnCode;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class MainActivity extends Activity {
    private static final int REQ_PICK_INPUT = 1001;
    private static final int REQ_CREATE_OUTPUT = 1002;

    private static final int TARGET_WIDTH = 480;
    private static final int TARGET_HEIGHT = 480;
    private static final int MAX_FRAME_BYTES = 96 * 1024;

    private final ExecutorService executor = Executors.newSingleThreadExecutor();

    private Uri inputUri;
    private String inputName = "";

    private TextView inputView;
    private TextView statusView;
    private TextView logView;
    private ProgressBar progressBar;
    private Button selectButton;
    private Button convertButton;
    private Spinner fpsSpinner;
    private Spinner qualitySpinner;
    private EditText durationInput;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        requestWindowFeature(Window.FEATURE_NO_TITLE);
        getWindow().getDecorView().setKeepScreenOn(true);
        setContentView(buildContentView());
    }

    private View buildContentView() {
        ScrollView scroll = new ScrollView(this);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(18), dp(18), dp(18), dp(18));
        scroll.addView(root);

        TextView title = text("BK7258 Mobile Converter", 22, true);
        root.addView(title);

        TextView profile = text("MP4 / MJPEG / Baseline JPEG / YUV422 / 480x480 / no audio", 14, false);
        profile.setPadding(0, dp(4), 0, dp(14));
        root.addView(profile);

        inputView = text("No input selected", 14, false);
        inputView.setPadding(0, 0, 0, dp(10));
        root.addView(inputView);

        selectButton = new Button(this);
        selectButton.setText("Select MP4");
        selectButton.setOnClickListener(v -> pickInput());
        root.addView(selectButton, matchWidth());

        LinearLayout options = new LinearLayout(this);
        options.setOrientation(LinearLayout.HORIZONTAL);
        options.setPadding(0, dp(12), 0, 0);
        root.addView(options);

        LinearLayout fpsBox = optionBox("FPS");
        fpsSpinner = new Spinner(this);
        ArrayAdapter<String> fpsAdapter = new ArrayAdapter<>(
                this,
                android.R.layout.simple_spinner_dropdown_item,
                new String[]{"20", "21", "22", "23", "24", "25"}
        );
        fpsSpinner.setAdapter(fpsAdapter);
        fpsSpinner.setSelection(5);
        fpsBox.addView(fpsSpinner, matchWidth());
        options.addView(fpsBox, weightedBox());

        LinearLayout qualityBox = optionBox("JPEG qscale");
        qualitySpinner = new Spinner(this);
        ArrayAdapter<String> qualityAdapter = new ArrayAdapter<>(
                this,
                android.R.layout.simple_spinner_dropdown_item,
                new String[]{"2 best", "3 high", "4 normal", "5 smaller"}
        );
        qualitySpinner.setAdapter(qualityAdapter);
        qualitySpinner.setSelection(1);
        qualityBox.addView(qualitySpinner, matchWidth());
        options.addView(qualityBox, weightedBox());

        LinearLayout durationBox = optionBox("Max seconds");
        durationInput = new EditText(this);
        durationInput.setHint("blank");
        durationInput.setInputType(InputType.TYPE_CLASS_NUMBER | InputType.TYPE_NUMBER_FLAG_DECIMAL);
        durationBox.addView(durationInput, matchWidth());
        options.addView(durationBox, weightedBox());

        convertButton = new Button(this);
        convertButton.setText("Convert");
        convertButton.setEnabled(false);
        convertButton.setOnClickListener(v -> createOutput());
        LinearLayout.LayoutParams convertParams = matchWidth();
        convertParams.setMargins(0, dp(14), 0, 0);
        root.addView(convertButton, convertParams);

        progressBar = new ProgressBar(this);
        progressBar.setIndeterminate(false);
        progressBar.setVisibility(View.GONE);
        LinearLayout.LayoutParams progressParams = matchWidth();
        progressParams.setMargins(0, dp(12), 0, 0);
        root.addView(progressBar, progressParams);

        statusView = text("Ready", 14, true);
        statusView.setPadding(0, dp(12), 0, dp(8));
        root.addView(statusView);

        logView = text("", 13, false);
        logView.setTextIsSelectable(true);
        root.addView(logView, matchWidth());

        return scroll;
    }

    private LinearLayout optionBox(String label) {
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setPadding(0, 0, dp(8), 0);
        box.addView(text(label, 12, true));
        return box;
    }

    private TextView text(String value, int sp, boolean bold) {
        TextView view = new TextView(this);
        view.setText(value);
        view.setTextSize(sp);
        if (bold) {
            view.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);
        }
        return view;
    }

    private LinearLayout.LayoutParams matchWidth() {
        return new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
        );
    }

    private LinearLayout.LayoutParams weightedBox() {
        return new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f);
    }

    private void pickInput() {
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType("video/*");
        startActivityForResult(intent, REQ_PICK_INPUT);
    }

    private void createOutput() {
        if (inputUri == null) {
            toast("Select an input MP4 first");
            return;
        }

        Intent intent = new Intent(Intent.ACTION_CREATE_DOCUMENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType("video/mp4");
        intent.putExtra(Intent.EXTRA_TITLE, outputFileName(inputName));
        startActivityForResult(intent, REQ_CREATE_OUTPUT);
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (resultCode != RESULT_OK || data == null || data.getData() == null) {
            return;
        }

        if (requestCode == REQ_PICK_INPUT) {
            inputUri = data.getData();
            inputName = displayName(inputUri);
            try {
                getContentResolver().takePersistableUriPermission(
                        inputUri,
                        data.getFlags() & Intent.FLAG_GRANT_READ_URI_PERMISSION
                );
            } catch (SecurityException ignored) {
                // Some providers grant temporary access only; the current conversion still works.
            }
            inputView.setText(inputName);
            convertButton.setEnabled(true);
            statusView.setText("Ready");
            logView.setText("");
        } else if (requestCode == REQ_CREATE_OUTPUT) {
            Uri outputUri = data.getData();
            startConvert(outputUri);
        }
    }

    private void startConvert(Uri outputUri) {
        final int fps;
        final int qscale;
        final Double maxDuration;
        try {
            fps = selectedFps();
            qscale = selectedQscale();
            maxDuration = selectedMaxDuration();
        } catch (RuntimeException ex) {
            toast(ex.getMessage());
            return;
        }

        setBusy(true);
        appendLog("Input: " + inputName);

        executor.execute(() -> {
            File workDir = new File(getCacheDir(), "bk7258_work");
            File framesDir = new File(workDir, "frames");
            File inputFile = new File(workDir, "input.mp4");
            File tempOutput = new File(workDir, "output_bk7258_mjpeg_yuv422.mp4");

            try {
                clearDirectory(workDir);
                if (!framesDir.mkdirs() && !framesDir.isDirectory()) {
                    throw new IOException("Cannot create frame directory");
                }

                updateStatus("Copying input...");
                copyUriToFile(inputUri, inputFile);

                String command = ffmpegCommand(inputFile, framesDir, fps, qscale, maxDuration);

                updateStatus("Decoding to JPEG frames...");
                appendLog("FPS: " + fps + ", qscale: " + qscale);
                FFmpegSession session = FFmpegKit.execute(command);
                if (!ReturnCode.isSuccess(session.getReturnCode())) {
                    throw new IOException("FFmpeg failed\n" + safeLogs(session));
                }

                List<File> frames = listFrames(framesDir);

                updateStatus("Fixing JPEG sampling...");
                int fixedCount = fixFrameSampling(frames, qscale);
                if (fixedCount > 0) {
                    appendLog("Re-encoded " + fixedCount + " frame(s) for standard 4:2:2 sampling");
                }

                updateStatus("Checking JPEG profile...");
                validateFrames(frames);

                updateStatus("Building MP4 container...");
                Mp4JpegWriter.write(tempOutput, frames, TARGET_WIDTH, TARGET_HEIGHT, fps);

                updateStatus("Saving output...");
                copyFileToUri(tempOutput, outputUri);

                String done = String.format(Locale.US,
                        "Done: %d frames, %.2f MB",
                        frames.size(),
                        tempOutput.length() / 1024.0 / 1024.0);
                runOnUiThread(() -> {
                    setBusy(false);
                    statusView.setText(done);
                    appendLog(done);
                    toast("Conversion complete");
                });
            } catch (Throwable ex) {
                runOnUiThread(() -> {
                    setBusy(false);
                    statusView.setText("Failed");
                    appendLog("Error: " + ex.getMessage());
                    toast("Conversion failed");
                });
            } finally {
                clearDirectory(workDir);
            }
        });
    }

    private String ffmpegCommand(File inputFile, File framesDir, int fps, int qscale, Double maxDuration) {
        File framePattern = new File(framesDir, "frame_%06d.jpg");
        String filter = String.format(Locale.US,
                "fps=%d,scale=%d:%d:force_original_aspect_ratio=decrease:flags=lanczos,"
                        + "pad=%d:%d:(ow-iw)/2:(oh-ih)/2:color=black,format=yuvj422p",
                fps, TARGET_WIDTH, TARGET_HEIGHT, TARGET_WIDTH, TARGET_HEIGHT);

        StringBuilder cmd = new StringBuilder();
        cmd.append("-y -hide_banner -i ").append(quote(inputFile.getAbsolutePath())).append(' ');
        if (maxDuration != null) {
            cmd.append("-t ").append(String.format(Locale.US, "%.3f", maxDuration)).append(' ');
        }
        cmd.append("-an -vf ").append(quote(filter)).append(' ');
        cmd.append("-c:v mjpeg -q:v ").append(qscale).append(" -pix_fmt yuvj422p -f image2 ");
        cmd.append(quote(framePattern.getAbsolutePath()));
        return cmd.toString();
    }

    private void validateFrames(List<File> frames) throws IOException {
        if (frames.isEmpty()) {
            throw new IOException("No JPEG frames were generated");
        }

        long maxSize = 0;
        for (File frame : frames) {
            long size = frame.length();
            maxSize = Math.max(maxSize, size);
            if (size > MAX_FRAME_BYTES) {
                throw new IOException("JPEG frame exceeds 96KB: " + frame.getName() + " (" + size + " bytes)");
            }

            JpegInspector.JpegInfo info = JpegInspector.inspect(frame);
            if (!info.valid || !info.baseline || info.progressive
                    || info.width != TARGET_WIDTH || info.height != TARGET_HEIGHT
                    || !"yuv422".equals(info.subsampling)
                    || info.yH != 2 || info.yV != 1 || info.cH != 1 || info.cV != 1) {
                throw new IOException("JPEG profile check failed: " + frame.getName()
                        + " valid=" + info.valid
                        + " baseline=" + info.baseline
                        + " subsampling=" + info.subsampling
                        + " sampling=Y" + info.yH + "x" + info.yV
                        + "/C" + info.cH + "x" + info.cV
                        + " size=" + info.width + "x" + info.height);
            }
        }

        appendLog("JPEG profile: baseline / yuv422 / 480x480");
        appendLog("Max JPEG frame: " + maxSize + " bytes");
    }

    private int fixFrameSampling(List<File> frames, int qscale) throws IOException {
        int quality = Math.max(70, 100 - qscale * 5);
        int count = 0;
        for (File frame : frames) {
            JpegInspector.JpegInfo info = JpegInspector.inspect(frame);
            if (JpegSamplingFixer.needsFix(info)) {
                JpegSamplingFixer.fix(frame, quality);
                count++;
            }
        }
        return count;
    }

    private int selectedFps() {
        return Integer.parseInt((String) fpsSpinner.getSelectedItem());
    }

    private int selectedQscale() {
        String item = (String) qualitySpinner.getSelectedItem();
        return Integer.parseInt(item.substring(0, 1));
    }

    private Double selectedMaxDuration() {
        String value = durationInput.getText().toString().trim();
        if (value.isEmpty()) {
            return null;
        }
        double parsed = Double.parseDouble(value);
        if (parsed <= 0) {
            throw new IllegalArgumentException("Max seconds must be greater than 0");
        }
        return parsed;
    }

    private List<File> listFrames(File framesDir) {
        File[] files = framesDir.listFiles((dir, name) -> name.toLowerCase(Locale.US).endsWith(".jpg"));
        if (files == null) {
            return new ArrayList<>();
        }
        Arrays.sort(files, (a, b) -> a.getName().compareTo(b.getName()));
        return new ArrayList<>(Arrays.asList(files));
    }

    private void copyUriToFile(Uri uri, File output) throws IOException {
        try (InputStream in = getContentResolver().openInputStream(uri);
             FileOutputStream out = new FileOutputStream(output)) {
            if (in == null) {
                throw new IOException("Cannot open input file");
            }
            copy(in, out);
        }
    }

    private void copyFileToUri(File input, Uri uri) throws IOException {
        try (FileInputStream in = new FileInputStream(input);
             OutputStream out = getContentResolver().openOutputStream(uri, "w")) {
            if (out == null) {
                throw new IOException("Cannot open output file");
            }
            copy(in, out);
        }
    }

    private void copy(InputStream in, OutputStream out) throws IOException {
        byte[] buffer = new byte[256 * 1024];
        int read;
        while ((read = in.read(buffer)) != -1) {
            out.write(buffer, 0, read);
        }
    }

    private void clearDirectory(File dir) {
        if (!dir.exists()) {
            return;
        }
        File[] files = dir.listFiles();
        if (files == null) {
            return;
        }
        for (File file : files) {
            if (file.isDirectory()) {
                clearDirectory(file);
            }
            //noinspection ResultOfMethodCallIgnored
            file.delete();
        }
    }

    private String safeLogs(FFmpegSession session) {
        String logs = session.getAllLogsAsString();
        if (logs == null || logs.trim().isEmpty()) {
            return "No FFmpeg log available";
        }
        return logs.length() > 5000 ? logs.substring(logs.length() - 5000) : logs;
    }

    private String displayName(Uri uri) {
        try (Cursor cursor = getContentResolver().query(uri, null, null, null, null)) {
            if (cursor != null && cursor.moveToFirst()) {
                int index = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME);
                if (index >= 0) {
                    return cursor.getString(index);
                }
            }
        }
        return "input.mp4";
    }

    private String outputFileName(String name) {
        String base = name == null || name.trim().isEmpty() ? "output" : name.trim();
        int dot = base.lastIndexOf('.');
        if (dot > 0) {
            base = base.substring(0, dot);
        }
        return base + "_bk7258_mjpeg_yuv422.mp4";
    }

    private String quote(String value) {
        return "'" + value.replace("'", "'\\''") + "'";
    }

    private void setBusy(boolean busy) {
        selectButton.setEnabled(!busy);
        convertButton.setEnabled(!busy && inputUri != null);
        fpsSpinner.setEnabled(!busy);
        qualitySpinner.setEnabled(!busy);
        durationInput.setEnabled(!busy);
        progressBar.setVisibility(busy ? View.VISIBLE : View.GONE);
        progressBar.setIndeterminate(busy);
    }

    private void updateStatus(String text) {
        runOnUiThread(() -> {
            statusView.setText(text);
            appendLog(text);
        });
    }

    private void appendLog(String text) {
        runOnUiThread(() -> {
            String current = logView.getText().toString();
            if (current.isEmpty()) {
                logView.setText(text);
            } else {
                logView.setText(current + "\n" + text);
            }
        });
    }

    private void toast(String message) {
        Toast.makeText(this, message, Toast.LENGTH_SHORT).show();
    }

    private int dp(int value) {
        return (int) (value * getResources().getDisplayMetrics().density + 0.5f);
    }

    @Override
    protected void onDestroy() {
        executor.shutdownNow();
        super.onDestroy();
    }
}
