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
 * Direct Gemini Developer API TTS client. It deliberately contains no embedded
 * API key. A small rolling prefetch queue hides network/model latency between
 * book fragments while a single AudioTrack keeps PCM output continuous.
 */
final class GeminiTtsEngine {
    // Flash-Lite is the low-latency Gemini 3.8 TTS model for read-aloud use.
    static final String MODEL = "gemini-3.8-flash-lite-tts";
    static final int SAMPLE_RATE = 24_000;
    private static final int PREFETCH_WINDOW = 3;
    private static final int CONNECT_TIMEOUT_MS = 20_000;
    private static final int READ_TIMEOUT_MS = 90_000;
    private static final int MAX_RESPONSE_BYTES = 25 * 1024 * 1024;

    private final Object trackLock = new Object();
    private final Set<HttpURLConnection> activeConnections = Collections.newSetFromMap(
            new ConcurrentHashMap<HttpURLConnection, Boolean>());
    private volatile AudioTrack currentTrack;

    interface Cancellation {
        boolean isCancelled();
    }

    interface SegmentProgress {
        void onSegmentCompleted(int index);
    }

    /**
     * Generates at most three upcoming phrases concurrently. They are played
     * in their original order through one AudioTrack, so there is no teardown
     * gap between fragments. Returns false only when cancelled.
     */
    boolean synthesizeAndPlayPrefetched(String apiKey, String voice, List<String> phrases,
                                        float requestedSpeed, Cancellation cancellation,
                                        SegmentProgress progress) throws IOException {
        if (apiKey == null || apiKey.trim().isEmpty()) {
            throw new IOException("Добавьте свой Gemini API-ключ в настройках");
        }
        if (phrases == null || phrases.isEmpty()) return true;
        ArrayList<String> cleanPhrases = new ArrayList<>();
        for (String phrase : phrases) {
            if (phrase != null && !phrase.trim().isEmpty()) cleanPhrases.add(phrase.trim());
        }
        if (cleanPhrases.isEmpty()) return true;

        int workers = Math.min(PREFETCH_WINDOW, cleanPhrases.size());
        ExecutorService prefetch = Executors.newFixedThreadPool(workers);
        Map<Integer, Future<byte[]>> pending = new HashMap<>();
        AudioTrack track = null;
        try {
            int nextToQueue = 0;
            while (nextToQueue < cleanPhrases.size() && pending.size() < PREFETCH_WINDOW) {
                queue(prefetch, pending, nextToQueue++, apiKey.trim(), voice, cleanPhrases, cancellation);
            }

            track = createTrack(cancellation);
            if (track == null) return false;
            float speed = Math.max(0.7f, Math.min(1.4f, requestedSpeed));
            track.setPlaybackRate(Math.round(SAMPLE_RATE * speed));
            track.play();

            for (int index = 0; index < cleanPhrases.size(); index++) {
                if (cancellation.isCancelled()) return false;
                Future<byte[]> future = pending.remove(index);
                if (future == null) throw new IOException("Потерян фрагмент очереди Gemini");
                byte[] pcm = await(future, cancellation);
                if (cancellation.isCancelled()) return false;

                // Refill before playback: the next request runs while this PCM is heard.
                while (nextToQueue < cleanPhrases.size() && pending.size() < PREFETCH_WINDOW) {
                    queue(prefetch, pending, nextToQueue++, apiKey.trim(), voice, cleanPhrases, cancellation);
                }
                if (!writePcm(track, pcm, cancellation)) {
                    if (cancellation.isCancelled()) return false;
                    throw new IOException("Не удалось воспроизвести аудио Gemini");
                }
                if (progress != null && !cancellation.isCancelled()) progress.onSegmentCompleted(index);
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
                       String apiKey, String voice, List<String> phrases, Cancellation cancellation) {
        final String phrase = phrases.get(index);
        pending.put(index, executor.submit(new Callable<byte[]>() {
            @Override
            public byte[] call() throws Exception {
                return requestPcm(apiKey, voice, phrase, cancellation);
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

    private static boolean writePcm(AudioTrack track, byte[] pcm, Cancellation cancellation) {
        try {
            int position = 0;
            while (position < pcm.length && !cancellation.isCancelled()) {
                int requested = Math.min(16 * 1024, pcm.length - position);
                int written = track.write(pcm, position, requested, AudioTrack.WRITE_BLOCKING);
                if (written <= 0) return false;
                position += written;
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
            voiceConfig.put("voice", voice == null || voice.isEmpty() ? "Kore" : voice);
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
