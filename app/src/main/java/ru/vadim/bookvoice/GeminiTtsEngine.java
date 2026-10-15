package ru.vadim.bookvoice;

import android.media.AudioAttributes;
import android.media.AudioFormat;
import android.media.AudioManager;
import android.media.AudioTrack;
import android.util.Base64;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.Callable;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;

/**
 * Direct Gemini Developer API TTS client. It uses the low-cost Flash-Lite TTS
 * model, long book passages, a one-item rolling prefetch, and a continuous
 * AudioTrack. One long request at startup avoids spending three daily requests
 * before the listener has heard anything; the next request starts during the
 * current passage's playback.
 */
final class GeminiTtsEngine {
    static final String MODEL = "gemini-3.8-flash-lite-tts";
    static final int SAMPLE_RATE = 24_000;
    private static final int PREFETCH_WINDOW = 1;
    private static final int CONNECT_TIMEOUT_MS = 20_000;
    private static final int READ_TIMEOUT_MS = 180_000;
    private static final int MAX_RESPONSE_BYTES = 40 * 1024 * 1024;

    private final Object trackLock = new Object();
    private final Set<HttpURLConnection> activeConnections = Collections.newSetFromMap(
            new ConcurrentHashMap<HttpURLConnection, Boolean>());
    private volatile AudioTrack currentTrack;

    interface Cancellation {
        boolean isCancelled();
    }

    interface SegmentProgress {
        /** Fraction is relative to the complete source segment, including a resumed cached prefix. */
        void onSegmentProgress(int index, float fraction);
    }

    /** A book range backed either by a local cache hit or a future Gemini request. */
    static final class Segment {
        final int start;
        final int end;
        final String text;
        final int cachedOffsetBytes;
        final byte[] initialPcm;

        Segment(int start, int end, String text) {
            this(start, end, text, 0, null);
        }

        Segment(int start, int end, String text, int cachedOffsetBytes, byte[] initialPcm) {
            this.start = start;
            this.end = end;
            this.text = text;
            this.cachedOffsetBytes = Math.max(0, cachedOffsetBytes) & ~1;
            this.initialPcm = initialPcm;
        }
    }

    /**
     * Generates one long upcoming segment at a time. The successor request is
     * scheduled just before writing the current PCM, so it is generated while
     * the listener hears the current passage. Cached passages skip Gemini
     * completely and remain playable after the app restarts.
     */
    boolean synthesizeAndPlayPrefetched(String apiKey, String voice, List<Segment> segments,
                                        float requestedSpeed, GeminiAudioCache cache,
                                        Cancellation cancellation, SegmentProgress progress)
            throws IOException {
        if (apiKey == null || apiKey.trim().isEmpty()) {
            throw new IOException("Добавьте свой Gemini API-ключ в настройках");
        }
        if (segments == null || segments.isEmpty()) return true;
        ArrayList<Segment> cleanSegments = new ArrayList<>();
        for (Segment segment : segments) {
            if (segment != null && segment.end > segment.start && segment.text != null
                    && !segment.text.trim().isEmpty()) cleanSegments.add(segment);
        }
        if (cleanSegments.isEmpty()) return true;

        String selectedVoice = voice == null || voice.trim().isEmpty() ? "Kore" : voice.trim();
        int workers = Math.min(PREFETCH_WINDOW, cleanSegments.size());
        ExecutorService prefetch = Executors.newFixedThreadPool(workers);
        Map<Integer, Future<byte[]>> pending = new HashMap<>();
        AudioTrack track = null;
        try {
            int nextToQueue = 0;
            while (nextToQueue < cleanSegments.size() && pending.size() < PREFETCH_WINDOW) {
                queue(prefetch, pending, nextToQueue++, apiKey.trim(), selectedVoice,
                        cleanSegments, cache, cancellation);
            }

            track = createTrack(cancellation);
            if (track == null) return false;
            float speed = Math.max(0.7f, Math.min(1.4f, requestedSpeed));
            track.setPlaybackRate(Math.round(SAMPLE_RATE * speed));
            track.play();

            for (int index = 0; index < cleanSegments.size(); index++) {
                if (cancellation.isCancelled()) return false;
                Segment segment = cleanSegments.get(index);
                Future<byte[]> future = pending.remove(index);
                if (future == null) throw new IOException("Потерян фрагмент очереди Gemini");
                byte[] pcm = await(future, cancellation);
                if (cancellation.isCancelled()) return false;

                // Queue the next long passage before current PCM is played.
                while (nextToQueue < cleanSegments.size() && pending.size() < PREFETCH_WINDOW) {
                    queue(prefetch, pending, nextToQueue++, apiKey.trim(), selectedVoice,
                            cleanSegments, cache, cancellation);
                }
                if (!writePcm(track, pcm, segment.cachedOffsetBytes, cancellation, progress, index)) {
                    if (cancellation.isCancelled()) return false;
                    throw new IOException("Не удалось воспроизвести аудио Gemini");
                }
            }
            waitForBufferedAudio(requestedSpeed, cancellation);
            return !cancellation.isCancelled();
        } catch (InterruptedException error) {
            Thread.currentThread().interrupt();
            return false;
        } finally {
            for (Future<byte[]> future : pending.values()) future.cancel(true);
            prefetch.shutdownNow();
            releaseCurrentTrack(track);
        }
    }

    void stop() {
        AudioTrack track;
        synchronized (trackLock) {
            track = currentTrack;
            currentTrack = null;
        }
        releaseQuietly(track);
        // Disconnecting unblocks HTTP reads immediately when the user presses pause.
        for (HttpURLConnection connection : activeConnections) {
            try {
                connection.disconnect();
            } catch (Exception ignored) {
            }
        }
        activeConnections.clear();
    }

    private void queue(ExecutorService executor, Map<Integer, Future<byte[]>> pending, int index,
                       String apiKey, String voice, List<Segment> segments, GeminiAudioCache cache,
                       Cancellation cancellation) {
        final Segment segment = segments.get(index);
        pending.put(index, executor.submit(new Callable<byte[]>() {
            @Override
            public byte[] call() throws Exception {
                if (segment.initialPcm != null && segment.initialPcm.length > 0) return segment.initialPcm;
                if (cache != null) {
                    byte[] cached = cache.read(segment.start, segment.end, voice, segment.text);
                    if (cached != null) return cached;
                }
                byte[] pcm = requestPcm(apiKey, voice, segment.text, cancellation);
                if (!cancellation.isCancelled() && cache != null && pcm.length > 0) {
                    cache.store(segment.start, segment.end, voice, segment.text, pcm);
                }
                return pcm;
            }
        }));
    }

    private static byte[] await(Future<byte[]> future, Cancellation cancellation)
            throws IOException, InterruptedException {
        try {
            byte[] pcm = future.get();
            if (cancellation.isCancelled()) return new byte[0];
            if (pcm == null || pcm.length == 0) throw new IOException("Gemini вернул пустое аудио");
            return pcm;
        } catch (ExecutionException error) {
            Throwable cause = error.getCause();
            if (cause instanceof IOException) throw (IOException) cause;
            throw new IOException("Не удалось получить аудио Gemini", cause);
        }
    }

    private AudioTrack createTrack(Cancellation cancellation) throws IOException {
        int minimum = AudioTrack.getMinBufferSize(SAMPLE_RATE, AudioFormat.CHANNEL_OUT_MONO,
                AudioFormat.ENCODING_PCM_16BIT);
        if (minimum <= 0) throw new IOException("Устройство не поддерживает PCM-аудио Gemini");
        AudioTrack track = new AudioTrack(
                new AudioAttributes.Builder()
                        .setUsage(AudioAttributes.USAGE_MEDIA)
                        .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                        .build(),
                new AudioFormat.Builder()
                        .setSampleRate(SAMPLE_RATE)
                        .setEncoding(AudioFormat.ENCODING_PCM_16BIT)
                        .setChannelMask(AudioFormat.CHANNEL_OUT_MONO)
                        .build(),
                Math.max(minimum, 32 * 1024),
                AudioTrack.MODE_STREAM,
                AudioManager.AUDIO_SESSION_ID_GENERATE);
        synchronized (trackLock) {
            if (cancellation.isCancelled()) {
                releaseQuietly(track);
                return null;
            }
            currentTrack = track;
        }
        return track;
    }

    /** Let the final AudioTrack buffer drain instead of clipping the last syllable. */
    private static void waitForBufferedAudio(float requestedSpeed, Cancellation cancellation)
            throws InterruptedException {
        float speed = Math.max(0.7f, Math.min(1.4f, requestedSpeed));
        long remaining = Math.round(1_000f / speed);
        while (remaining > 0 && !cancellation.isCancelled()) {
            long slice = Math.min(50L, remaining);
            Thread.sleep(slice);
            remaining -= slice;
        }
    }

    private static boolean writePcm(AudioTrack track, byte[] pcm, int cachedOffsetBytes,
                                    Cancellation cancellation, SegmentProgress progress, int index) {
        try {
            int position = Math.min(Math.max(0, cachedOffsetBytes & ~1), Math.max(0, pcm.length - 2));
            int nextProgressAt = position + SAMPLE_RATE * 2;
            if (progress != null) progress.onSegmentProgress(index, position / (float) pcm.length);
            while (position < pcm.length && !cancellation.isCancelled()) {
                int requested = Math.min(16 * 1024, pcm.length - position);
                int written = track.write(pcm, position, requested, AudioTrack.WRITE_BLOCKING);
                if (written <= 0) return false;
                position += written;
                if (progress != null && (position >= nextProgressAt || position >= pcm.length)) {
                    progress.onSegmentProgress(index, Math.min(1f, position / (float) pcm.length));
                    nextProgressAt = position + SAMPLE_RATE * 2;
                }
            }
            return !cancellation.isCancelled();
        } catch (IllegalStateException ignored) {
            return false;
        }
    }

    private void releaseCurrentTrack(AudioTrack track) {
        synchronized (trackLock) {
            if (currentTrack == track) currentTrack = null;
        }
        releaseQuietly(track);
    }

    private byte[] requestPcm(String apiKey, String voice, String text, Cancellation cancellation)
            throws IOException {
        if (cancellation.isCancelled()) return new byte[0];
        HttpURLConnection connection = null;
        try {
            URL url = new URL("https://generativelanguage.googleapis.com/v1beta/models/"
                    + MODEL + ":generateContent");
            connection = (HttpURLConnection) url.openConnection();
            activeConnections.add(connection);
            connection.setRequestMethod("POST");
            connection.setDoOutput(true);
            connection.setConnectTimeout(CONNECT_TIMEOUT_MS);
            connection.setReadTimeout(READ_TIMEOUT_MS);
            connection.setRequestProperty("Content-Type", "application/json; charset=utf-8");
            connection.setRequestProperty("x-goog-api-key", apiKey);
            byte[] request = requestBody(voice, text).getBytes(StandardCharsets.UTF_8);
            connection.setFixedLengthStreamingMode(request.length);
            try (OutputStream output = connection.getOutputStream()) {
                output.write(request);
            }
            if (cancellation.isCancelled()) return new byte[0];
            int code = connection.getResponseCode();
            InputStream stream = code >= 200 && code < 300
                    ? connection.getInputStream() : connection.getErrorStream();
            String reply = readUtf8(stream, MAX_RESPONSE_BYTES, cancellation);
            if (cancellation.isCancelled()) return new byte[0];
            if (code < 200 || code >= 300) {
                throw new IOException("Gemini вернул " + code + ": " + apiError(reply));
            }
            return parsePcm(reply);
        } finally {
            if (connection != null) {
                activeConnections.remove(connection);
                connection.disconnect();
            }
        }
    }

    /** Matches the current generateContent REST schema for Gemini 3.8 TTS. */
    private static String requestBody(String voice, String text) throws IOException {
        try {
            JSONObject speechMetadata = new JSONObject();
            speechMetadata.put("style", "calm, natural Russian audiobook narration");
            JSONObject part = new JSONObject();
            part.put("text", text);
            part.put("speech_metadata", speechMetadata);
            JSONObject content = new JSONObject();
            content.put("role", "user");
            content.put("parts", new JSONArray().put(part));

            JSONObject responseAudio = new JSONObject();
            responseAudio.put("mimeType", "AUDIO_L16");
            responseAudio.put("sampleRate", SAMPLE_RATE);
            JSONObject responseFormat = new JSONObject();
            responseFormat.put("audio", responseAudio);
            JSONObject voiceConfig = new JSONObject();
            voiceConfig.put("voice", voice);
            JSONObject speechConfig = new JSONObject();
            speechConfig.put("voiceConfig", voiceConfig);
            JSONObject generation = new JSONObject();
            generation.put("responseModalities", new JSONArray().put("AUDIO"));
            generation.put("responseFormat", responseFormat);
            generation.put("speechConfig", speechConfig);

            JSONObject body = new JSONObject();
            body.put("contents", new JSONArray().put(content));
            body.put("generationConfig", generation);
            return body.toString();
        } catch (Exception error) {
            throw new IOException("Не удалось подготовить запрос Gemini", error);
        }
    }

    private static byte[] parsePcm(String reply) throws IOException {
        try {
            JSONObject root = new JSONObject(reply);
            JSONArray candidates = root.optJSONArray("candidates");
            if (candidates == null || candidates.length() == 0) {
                throw new IOException("Gemini не вернул аудио: " + apiError(reply));
            }
            JSONObject candidate = candidates.optJSONObject(0);
            JSONObject content = candidate == null ? null : candidate.optJSONObject("content");
            JSONArray parts = content == null ? null : content.optJSONArray("parts");
            if (parts == null) throw new IOException("Gemini не вернул аудиоданные");
            for (int index = 0; index < parts.length(); index++) {
                JSONObject part = parts.optJSONObject(index);
                if (part == null) continue;
                JSONObject inlineData = part.optJSONObject("inlineData");
                if (inlineData == null) inlineData = part.optJSONObject("inline_data");
                String encoded = inlineData == null ? "" : inlineData.optString("data", "");
                if (!encoded.isEmpty()) return Base64.decode(encoded, Base64.DEFAULT);
            }
            throw new IOException("Gemini не вернул PCM-аудио. Проверьте ключ и доступ к Gemini TTS.");
        } catch (IOException error) {
            throw error;
        } catch (Exception error) {
            throw new IOException("Не удалось разобрать ответ Gemini", error);
        }
    }

    private static String readUtf8(InputStream input, int maximumBytes, Cancellation cancellation)
            throws IOException {
        if (input == null) return "";
        try (InputStream source = input; ByteArrayOutputStream output = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[8 * 1024];
            int count;
            while ((count = source.read(buffer)) != -1) {
                if (cancellation.isCancelled()) return "";
                if (output.size() + count > maximumBytes) throw new IOException("Ответ Gemini слишком большой");
                output.write(buffer, 0, count);
            }
            return output.toString(StandardCharsets.UTF_8.name());
        }
    }

    private static String apiError(String source) {
        try {
            JSONObject root = new JSONObject(source);
            JSONObject error = root.optJSONObject("error");
            String message = error == null ? "" : error.optString("message", "");
            return message.isEmpty() ? "неизвестная ошибка API" : message;
        } catch (Exception ignored) {
            String compact = source == null ? "" : source.replaceAll("\\s+", " ").trim();
            return compact.isEmpty() ? "неизвестная ошибка API"
                    : compact.substring(0, Math.min(260, compact.length()));
        }
    }

    private static void releaseQuietly(AudioTrack track) {
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
}
