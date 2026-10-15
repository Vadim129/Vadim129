package ru.vadim.bookvoice;

import android.content.Context;
import android.content.res.AssetManager;
import android.media.AudioAttributes;
import android.media.AudioFormat;
import android.media.AudioManager;
import android.media.AudioTrack;

import com.k2fsa.sherpa.onnx.GeneratedAudio;
import com.k2fsa.sherpa.onnx.OfflineTts;
import com.k2fsa.sherpa.onnx.OfflineTtsConfig;
import com.k2fsa.sherpa.onnx.OfflineTtsModelConfig;
import com.k2fsa.sherpa.onnx.OfflineTtsVitsModelConfig;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;

import kotlin.jvm.functions.Function1;

/**
 * Embedded Russian Piper/VITS neural TTS. It never needs a network connection:
 * two int8 Russian models are packaged as checked assets in the APK.
 */
final class PiperTtsEngine {
    static final String IRINA = "piper_irina";
    static final String DMITRI = "piper_dmitri";
    private static final String ASSET_VERSION = "v2";
    private final Context context;
    private final Object lifecycleLock = new Object();
    private final Object trackLock = new Object();
    private OfflineTts tts;
    private String loadedVoice = "";
    private volatile AudioTrack currentTrack;

    interface Cancellation {
        boolean isCancelled();
    }

    PiperTtsEngine(Context context) {
        this.context = context.getApplicationContext();
    }

    static String displayName(String voiceId) {
        return DMITRI.equals(voiceId) ? "Piper Дмитрий" : "Piper Ирина";
    }

    /**
     * Starts output sentence-by-sentence while VITS is still generating later
     * sentences. The old implementation waited for an entire 700-character
     * chunk before opening AudioTrack, which made a fast model feel frozen.
     */
    boolean synthesizeAndPlay(String voiceId, String text, float speed, Cancellation cancellation) throws IOException {
        if (text == null || text.trim().isEmpty()) return true;
        OfflineTts engine = ensureLoaded(voiceId);
        if (cancellation.isCancelled()) return false;
        return generateAndPlayStreaming(engine, text.trim(), speed, cancellation);
    }

    void stop() {
        AudioTrack track;
        synchronized (trackLock) {
            track = currentTrack;
            currentTrack = null;
        }
        releaseTrack(track);
    }

    void release() {
        stop();
        synchronized (lifecycleLock) {
            if (tts != null) {
                try {
                    tts.release();
                } catch (Throwable ignored) {
                }
                tts = null;
                loadedVoice = "";
            }
        }
    }

    private OfflineTts ensureLoaded(String requestedVoice) throws IOException {
        VoiceSpec spec = VoiceSpec.from(requestedVoice);
        synchronized (lifecycleLock) {
            if (tts != null && spec.id.equals(loadedVoice)) return tts;
            if (tts != null) {
                try {
                    tts.release();
                } catch (Throwable ignored) {
                }
                tts = null;
            }
            File dataDir = copyEspeakData();
            try {
                OfflineTtsVitsModelConfig vits = new OfflineTtsVitsModelConfig();
                vits.setModel(spec.assetPrefix + "/" + spec.modelFile);
                vits.setTokens(spec.assetPrefix + "/tokens.txt");
                vits.setDataDir(dataDir.getAbsolutePath());
                vits.setNoiseScale(0.667f);
                vits.setNoiseScaleW(0.8f);
                vits.setLengthScale(1.0f);

                OfflineTtsModelConfig model = new OfflineTtsModelConfig();
                model.setVits(vits);
                // Four worker threads noticeably reduce VITS latency on current phones,
                // while two remain available on entry-level dual-core devices.
                model.setNumThreads(preferredThreadCount());
                model.setDebug(false);
                model.setProvider("cpu");

                OfflineTtsConfig config = new OfflineTtsConfig();
                config.setModel(model);
                config.setMaxNumSentences(1);
                config.setSilenceScale(0.18f);
                tts = new OfflineTts(context.getAssets(), config);
                loadedVoice = spec.id;
                return tts;
            } catch (Throwable error) {
                throw new IOException("Не удалось загрузить " + displayName(spec.id) + ".", error);
            }
        }
    }

    /** Both Russian models use one identical eSpeak data set. */
    private File copyEspeakData() throws IOException {
        File root = new File(context.getFilesDir(), "piper-data-" + ASSET_VERSION);
        File marker = new File(root, ".ready");
        File output = new File(root, "espeak-ng-data");
        if (marker.exists() && output.isDirectory()) return output;
        deleteTree(root);
        copyAssetTree("piper/espeak-ng-data", output);
        if (!output.isDirectory()) throw new IOException("Не найдены данные произношения Piper");
        if (!root.exists() && !root.mkdirs()) throw new IOException("Не удалось подготовить Piper");
        try (FileOutputStream ignored = new FileOutputStream(marker)) {
            // Marker is written only after the shared eSpeak assets have been copied.
        }
        return output;
    }

    private void copyAssetTree(String assetPath, File destination) throws IOException {
        AssetManager manager = context.getAssets();
        String[] children = manager.list(assetPath);
        if (children != null && children.length > 0) {
            if (!destination.exists() && !destination.mkdirs()) {
                throw new IOException("Не удалось создать папку данных Piper");
            }
            for (String child : children) {
                copyAssetTree(assetPath + "/" + child, new File(destination, child));
            }
            return;
        }
        File parent = destination.getParentFile();
        if (parent != null && !parent.exists() && !parent.mkdirs()) {
            throw new IOException("Не удалось создать папку данных Piper");
        }
        try (InputStream input = manager.open(assetPath); FileOutputStream output = new FileOutputStream(destination)) {
            byte[] buffer = new byte[16 * 1024];
            int count;
            while ((count = input.read(buffer)) != -1) output.write(buffer, 0, count);
            output.getFD().sync();
        }
    }

    private boolean generateAndPlayStreaming(OfflineTts engine, String text, float speed,
                                             Cancellation cancellation) throws IOException {
        int sampleRate;
        try {
            sampleRate = engine.sampleRate();
        } catch (Throwable error) {
            throw new IOException("Piper не сообщил частоту аудио", error);
        }
        int minimum = AudioTrack.getMinBufferSize(sampleRate, AudioFormat.CHANNEL_OUT_MONO,
                AudioFormat.ENCODING_PCM_FLOAT);
        if (minimum <= 0) throw new IOException("Устройство не поддерживает аудио Piper");
        AudioTrack track = new AudioTrack(
                new AudioAttributes.Builder()
                        .setUsage(AudioAttributes.USAGE_MEDIA)
                        .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                        .build(),
                new AudioFormat.Builder()
                        .setSampleRate(sampleRate)
                        .setEncoding(AudioFormat.ENCODING_PCM_FLOAT)
                        .setChannelMask(AudioFormat.CHANNEL_OUT_MONO)
                        .build(),
                Math.max(minimum, 32 * 1024),
                AudioTrack.MODE_STREAM,
                AudioManager.AUDIO_SESSION_ID_GENERATE);
        synchronized (trackLock) {
            if (cancellation.isCancelled()) {
                releaseTrack(track);
                return false;
            }
            currentTrack = track;
        }
        final boolean[] receivedSamples = new boolean[]{false};
        final boolean[] writeFailed = new boolean[]{false};
        try {
            track.play();
            Function1<float[], Integer> callback = samples -> {
                if (cancellation.isCancelled()) return 0;
                if (samples == null || samples.length == 0) return 1;
                receivedSamples[0] = true;
                if (!writeSamples(track, samples, cancellation)) {
                    writeFailed[0] = true;
                    return 0;
                }
                return cancellation.isCancelled() ? 0 : 1;
            };
            GeneratedAudio generated = engine.generateWithCallback(text, 0,
                    clamp(speed, 0.7f, 1.35f), callback);
            if (cancellation.isCancelled()) return false;
            if (writeFailed[0]) throw new IOException("Не удалось воспроизвести Piper");
            // Older native builds can return the final buffer without invoking the
            // callback. Keep this compatibility path, but never play audio twice.
            if (!receivedSamples[0]) {
                if (generated == null || generated.getSamples() == null || generated.getSamples().length == 0) {
                    throw new IOException("Piper вернул пустое аудио");
                }
                if (!writeSamples(track, generated.getSamples(), cancellation)) {
                    if (cancellation.isCancelled()) return false;
                    throw new IOException("Не удалось воспроизвести Piper");
                }
            }
            return !cancellation.isCancelled();
        } catch (IllegalStateException error) {
            if (cancellation.isCancelled()) return false;
            throw new IOException("Воспроизведение Piper было прервано", error);
        } catch (IOException error) {
            throw error;
        } catch (Throwable error) {
            if (cancellation.isCancelled()) return false;
            throw new IOException("Piper не смог создать аудио. Попробуйте более короткий фрагмент.", error);
        } finally {
            synchronized (trackLock) {
                if (currentTrack == track) currentTrack = null;
            }
            releaseTrack(track);
        }
    }

    private static boolean writeSamples(AudioTrack track, float[] samples, Cancellation cancellation) {
        try {
            int offset = 0;
            while (offset < samples.length && !cancellation.isCancelled()) {
                int request = Math.min(4_096, samples.length - offset);
                int written = track.write(samples, offset, request, AudioTrack.WRITE_BLOCKING);
                if (written <= 0) return false;
                offset += written;
            }
            return !cancellation.isCancelled();
        } catch (IllegalStateException ignored) {
            return false;
        }
    }

    private static int preferredThreadCount() {
        int cores = Runtime.getRuntime().availableProcessors();
        return Math.max(2, Math.min(4, cores));
    }

    private static void deleteTree(File file) {
        if (file == null || !file.exists()) return;
        if (file.isDirectory()) {
            File[] children = file.listFiles();
            if (children != null) for (File child : children) deleteTree(child);
        }
        //noinspection ResultOfMethodCallIgnored
        file.delete();
    }

    private static void releaseTrack(AudioTrack track) {
        if (track == null) return;
        try {
            track.pause();
        } catch (Exception ignored) {
        }
        try {
            track.flush();
        } catch (Exception ignored) {
        }
        try {
            track.release();
        } catch (Exception ignored) {
        }
    }

    private static float clamp(float value, float minimum, float maximum) {
        return Math.max(minimum, Math.min(maximum, value));
    }

    private static final class VoiceSpec {
        final String id;
        final String folder;
        final String assetPrefix;
        final String modelFile;

        VoiceSpec(String id, String folder, String modelFile) {
            this.id = id;
            this.folder = folder;
            this.assetPrefix = "piper/" + folder;
            this.modelFile = modelFile;
        }

        static VoiceSpec from(String id) {
            if (DMITRI.equals(id)) {
                return new VoiceSpec(DMITRI, "dmitri", "model.onnx");
            }
            return new VoiceSpec(IRINA, "irina", "model.onnx");
        }
    }
}
