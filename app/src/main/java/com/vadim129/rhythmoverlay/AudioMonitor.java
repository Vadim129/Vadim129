package com.vadim129.rhythmoverlay;

import android.Manifest;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.media.AudioAttributes;
import android.media.AudioFormat;
import android.media.AudioRecord;
import android.media.AudioPlaybackCaptureConfiguration;
import android.media.MediaRecorder;
import android.media.audiofx.Visualizer;
import android.media.projection.MediaProjection;
import android.media.projection.MediaProjectionManager;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;

/**
 * Captures an audio spectrum when Android/device policy allows it.
 *
 * Playback capture is the most accurate route on Android 10+: the user explicitly grants
 * a system capture prompt and apps which opt out of Android playback capture cannot be read.
 * On devices where a global audio session is exposed, Visualizer(0) is tried. Finally the
 * microphone can be used for speakers/ambient music. There is intentionally no hidden capture.
 */
public final class AudioMonitor {
    public static final String MODE_AUTO = "auto";
    public static final String MODE_PLAYBACK = "playback";
    public static final String MODE_MIC = "mic";
    public static final String MODE_DEMO = "demo";

    private final Context appContext;
    private volatile boolean running;
    private volatile AudioRecord recorder;
    private volatile Visualizer visualizer;
    private volatile MediaProjection projection;
    private Thread worker;
    private final Handler mainHandler = new Handler(Looper.getMainLooper());

    public AudioMonitor(Context context) {
        appContext = context.getApplicationContext();
    }

    public synchronized void start(Intent projectionData, int projectionResultCode) {
        stop();
        running = true;
        String mode = Skin.prefs(appContext).getString(Skin.PREF_AUDIO_MODE, MODE_AUTO);
        if (MODE_DEMO.equals(mode)) {
            AudioLevels.clear();
            AudioLevels.setStatus("Демо-анимация");
            return;
        }

        if (projectionData != null && Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            if (startPlaybackCapture(projectionData, projectionResultCode)) return;
        }

        if (MODE_PLAYBACK.equals(mode)) {
            AudioLevels.clear();
            AudioLevels.setStatus("Нажмите «Подключить звук» в приложении");
            return;
        }
        if (MODE_MIC.equals(mode)) {
            if (startMicrophone()) return;
        } else {
            if (startGlobalVisualizer()) return;
            if (startMicrophone()) return;
        }

        AudioLevels.clear();
        AudioLevels.setStatus(hasRecordPermission() ? "Звук недоступен — демо" : "Нужен доступ к микрофону");
    }

    public synchronized void stop() {
        running = false;
        if (visualizer != null) {
            try {
                visualizer.setEnabled(false);
                visualizer.release();
            } catch (Exception ignored) { }
            visualizer = null;
        }
        if (recorder != null) {
            try {
                recorder.stop();
            } catch (Exception ignored) { }
            try {
                recorder.release();
            } catch (Exception ignored) { }
            recorder = null;
        }
        if (projection != null) {
            try {
                projection.stop();
            } catch (Exception ignored) { }
            projection = null;
        }
        worker = null;
    }

    private boolean hasRecordPermission() {
        return Build.VERSION.SDK_INT < Build.VERSION_CODES.M ||
                appContext.checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED;
    }

    @SuppressWarnings("deprecation")
    private boolean startGlobalVisualizer() {
        if (!hasRecordPermission()) return false;
        try {
            final Visualizer candidate = new Visualizer(0);
            int[] range = Visualizer.getCaptureSizeRange();
            candidate.setCaptureSize(range[1]);
            int rate = Math.max(VisualizeConstants.MIN_CAPTURE_RATE, Visualizer.getMaxCaptureRate() / 2);
            candidate.setDataCaptureListener(new Visualizer.OnDataCaptureListener() {
                @Override
                public void onWaveFormDataCapture(Visualizer ignored, byte[] waveform, int samplingRate) {
                    // FFT data below provides useful frequency bands; waveform is not needed here.
                }

                @Override
                public void onFftDataCapture(Visualizer ignored, byte[] fft, int samplingRate) {
                    if (running) publishFft(fft);
                }
            }, rate, false, true);
            candidate.setEnabled(true);
            visualizer = candidate;
            AudioLevels.setStatus("Аудиосессия устройства");
            return true;
        } catch (Throwable ignored) {
            return false;
        }
    }

    private boolean startPlaybackCapture(Intent data, int resultCode) {
        if (!hasRecordPermission()) {
            AudioLevels.setStatus("Для захвата нужен доступ к микрофону");
            return false;
        }
        try {
            MediaProjectionManager manager = (MediaProjectionManager) appContext.getSystemService(Context.MEDIA_PROJECTION_SERVICE);
            if (manager == null) return false;
            final MediaProjection capturedProjection = manager.getMediaProjection(resultCode, data);
            if (capturedProjection == null) return false;
            capturedProjection.registerCallback(new MediaProjection.Callback() {
                @Override public void onStop() {
                    AudioLevels.clear();
                    AudioLevels.setStatus("Захват телефона остановлен");
                    stopRecordOnly();
                }
            }, mainHandler);

            AudioPlaybackCaptureConfiguration config = new AudioPlaybackCaptureConfiguration.Builder(capturedProjection)
                    .addMatchingUsage(AudioAttributes.USAGE_MEDIA)
                    .addMatchingUsage(AudioAttributes.USAGE_GAME)
                    .build();
            int sampleRate = 44100;
            int min = AudioRecord.getMinBufferSize(sampleRate, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT);
            int buffer = Math.max(min, 4096) * 2;
            AudioFormat format = new AudioFormat.Builder()
                    .setEncoding(AudioFormat.ENCODING_PCM_16BIT)
                    .setSampleRate(sampleRate)
                    .setChannelMask(AudioFormat.CHANNEL_IN_MONO)
                    .build();
            AudioRecord candidate = new AudioRecord.Builder()
                    .setAudioFormat(format)
                    .setBufferSizeInBytes(buffer)
                    .setAudioPlaybackCaptureConfig(config)
                    .build();
            if (candidate.getState() != AudioRecord.STATE_INITIALIZED) {
                candidate.release();
                capturedProjection.stop();
                return false;
            }
            projection = capturedProjection;
            recorder = candidate;
            candidate.startRecording();
            startPcmWorker(candidate, "Захват аудио телефона");
            return true;
        } catch (Throwable ignored) {
            return false;
        }
    }

    private boolean startMicrophone() {
        if (!hasRecordPermission()) return false;
        try {
            int sampleRate = 22050;
            int min = AudioRecord.getMinBufferSize(sampleRate, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT);
            if (min <= 0) return false;
            AudioRecord candidate = new AudioRecord(MediaRecorder.AudioSource.DEFAULT, sampleRate,
                    AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT, Math.max(min * 2, 4096));
            if (candidate.getState() != AudioRecord.STATE_INITIALIZED) {
                candidate.release();
                return false;
            }
            recorder = candidate;
            candidate.startRecording();
            startPcmWorker(candidate, "Микрофон / музыка рядом");
            return true;
        } catch (Throwable ignored) {
            return false;
        }
    }

    private void startPcmWorker(final AudioRecord record, final String status) {
        AudioLevels.setStatus(status);
        worker = new Thread(new Runnable() {
            @Override public void run() {
                short[] samples = new short[512];
                while (running && recorder == record) {
                    int count;
                    try {
                        count = record.read(samples, 0, samples.length);
                    } catch (Throwable ignored) {
                        break;
                    }
                    if (count > 0) publishPcm(samples, count);
                }
            }
        }, "rhythm-audio");
        worker.setDaemon(true);
        worker.start();
    }

    private synchronized void stopRecordOnly() {
        if (recorder != null) {
            try { recorder.stop(); } catch (Exception ignored) { }
            try { recorder.release(); } catch (Exception ignored) { }
            recorder = null;
        }
    }

    private static void publishFft(byte[] fft) {
        float[] bands = new float[AudioLevels.BANDS];
        int bins = Math.max(1, fft.length / 2 - 1);
        for (int band = 0; band < bands.length; band++) {
            int from = 1 + (int) (Math.pow((double) band / bands.length, 1.65d) * (bins - 1));
            int to = 1 + (int) (Math.pow((double) (band + 1) / bands.length, 1.65d) * (bins - 1));
            to = Math.max(from + 1, Math.min(bins, to));
            double power = 0;
            for (int bin = from; bin < to; bin++) {
                int index = bin * 2;
                if (index + 1 >= fft.length) break;
                int real = fft[index];
                int imaginary = fft[index + 1];
                power += Math.sqrt(real * real + imaginary * imaginary);
            }
            bands[band] = (float) Math.min(1d, Math.log1p(power) / 5.3d);
        }
        AudioLevels.publish(bands);
    }

    private static void publishPcm(short[] samples, int count) {
        int fftSize = Math.min(256, count);
        float[] bands = new float[AudioLevels.BANDS];
        // A compact DFT works well enough for 16 display bands and avoids third-party DSP code.
        for (int band = 0; band < bands.length; band++) {
            int from = 1 + band * 5;
            int to = from + 5;
            double energy = 0;
            for (int k = from; k < to; k++) {
                double re = 0;
                double im = 0;
                for (int n = 0; n < fftSize; n++) {
                    double window = 0.5d - 0.5d * Math.cos(2d * Math.PI * n / (fftSize - 1));
                    double sample = samples[n] / 32768d * window;
                    double angle = 2d * Math.PI * k * n / fftSize;
                    re += sample * Math.cos(angle);
                    im -= sample * Math.sin(angle);
                }
                energy += Math.sqrt(re * re + im * im);
            }
            bands[band] = (float) Math.min(1d, Math.sqrt(energy / 5d) * 1.15d);
        }
        AudioLevels.publish(bands);
    }

    private static final class VisualizeConstants {
        private static final int MIN_CAPTURE_RATE = 8000;
        private VisualizeConstants() { }
    }
}
