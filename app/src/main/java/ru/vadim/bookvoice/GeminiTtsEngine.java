package ru.vadim.bookvoice;

import android.media.AudioAttributes;
import android.media.AudioFormat;
import android.media.AudioManager;
import android.media.AudioTrack;
import android.os.Build;
import android.util.Base64;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;

/**
 * Small direct Gemini Developer API client. It intentionally accepts an API key
 * only at runtime from SecretStore; there is no shared key hidden in the APK.
 */
final class GeminiTtsEngine {
    static final String MODEL = "gemini-3.8-flash-tts";
    static final int SAMPLE_RATE = 24_000;
    private static final int CONNECT_TIMEOUT_MS = 20_000;
    private static final int READ_TIMEOUT_MS = 90_000;
    private static final int MAX_RESPONSE_BYTES = 25 * 1024 * 1024;
    private final Object trackLock = new Object();
    private volatile AudioTrack currentTrack;

    interface Cancellation {
        boolean isCancelled();
    }

    /** Returns false when cancelled while playing; throws only for a real API/network failure. */
    boolean synthesizeAndPlay(String apiKey, String voice, String text, float speed,
                              Cancellation cancellation) throws IOException {
        if (apiKey == null || apiKey.trim().isEmpty()) {
            throw new IOException("Добавьте свой Gemini API-ключ в настройках движка");
        }
        if (text == null || text.trim().isEmpty()) return true;
        byte[] pcm = requestPcm(apiKey.trim(), voice, text.trim(), cancellation);
        if (cancellation.isCancelled()) return false;
        return playPcm(pcm, speed, cancellation);
    }

    void stop() {
        AudioTrack track;
        synchronized (trackLock) {
            track = currentTrack;
            currentTrack = null;
        }
        releaseQuietly(track);
    }

    private byte[] requestPcm(String apiKey, String voice, String text, Cancellation cancellation) throws IOException {
        HttpURLConnection connection = null;
        try {
            URL url = new URL("https://generativelanguage.googleapis.com/v1beta/models/"
                    + MODEL + ":generateContent");
            connection = (HttpURLConnection) url.openConnection();
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
            InputStream stream = code >= 200 && code < 300 ? connection.getInputStream() : connection.getErrorStream();
            String reply = readUtf8(stream, MAX_RESPONSE_BYTES);
            if (code < 200 || code >= 300) {
                throw new IOException("Gemini вернул " + code + ": " + apiError(reply));
            }
            try {
                JSONObject root = new JSONObject(reply);
                JSONArray candidates = root.optJSONArray("candidates");
                if (candidates == null || candidates.length() == 0) {
                    throw new IOException("Gemini не вернул аудио: " + apiError(reply));
                }
                JSONObject content = candidates.optJSONObject(0).optJSONObject("content");
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
                throw new IOException("Gemini не вернул PCM-аудио. Попробуйте другой голос или ключ.");
            } catch (IOException error) {
                throw error;
            } catch (Exception error) {
                throw new IOException("Не удалось разобрать ответ Gemini", error);
            }
        } finally {
            if (connection != null) connection.disconnect();
        }
    }

    private static String requestBody(String voice, String text) throws IOException {
        try {
            JSONObject speechMetadata = new JSONObject();
            speechMetadata.put("style", "Natural, expressive Russian audiobook narration. Read only the supplied book text, calmly and clearly.");
            JSONObject part = new JSONObject();
            part.put("text", text);
            part.put("speechMetadata", speechMetadata);
            JSONObject content = new JSONObject();
            content.put("role", "user");
            content.put("parts", new JSONArray().put(part));

            JSONObject audio = new JSONObject();
            audio.put("mimeType", "AUDIO_L16");
            audio.put("sampleRate", SAMPLE_RATE);
            JSONObject responseFormat = new JSONObject();
            responseFormat.put("audio", audio);
            JSONObject voiceConfig = new JSONObject();
            voiceConfig.put("voice", voice == null || voice.isEmpty() ? "Kore" : voice);
            JSONObject speechConfig = new JSONObject();
            speechConfig.put("voiceConfig", voiceConfig);
            speechConfig.put("languageCode", "ru-RU");
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

    private boolean playPcm(byte[] pcm, float requestedSpeed, Cancellation cancellation) throws IOException {
        if (pcm == null || pcm.length == 0) throw new IOException("Gemini вернул пустое аудио");
        int minimum = AudioTrack.getMinBufferSize(SAMPLE_RATE, AudioFormat.CHANNEL_OUT_MONO,
                AudioFormat.ENCODING_PCM_16BIT);
        if (minimum <= 0) throw new IOException("Устройство не поддерживает PCM-аудио Gemini");
        AudioAttributes attributes = new AudioAttributes.Builder()
                .setUsage(AudioAttributes.USAGE_MEDIA)
                .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                .build();
        AudioFormat format = new AudioFormat.Builder()
                .setSampleRate(SAMPLE_RATE)
                .setEncoding(AudioFormat.ENCODING_PCM_16BIT)
                .setChannelMask(AudioFormat.CHANNEL_OUT_MONO)
                .build();
        AudioTrack track = new AudioTrack(attributes, format, Math.max(minimum, 16 * 1024),
                AudioTrack.MODE_STREAM, AudioManager.AUDIO_SESSION_ID_GENERATE);
        synchronized (trackLock) {
            if (cancellation.isCancelled()) {
                releaseQuietly(track);
                return false;
            }
            currentTrack = track;
        }
        try {
            float speed = Math.max(0.7f, Math.min(1.4f, requestedSpeed));
            // Gemini emits 24 kHz PCM. Playback-rate adjustment keeps the reader's speed control useful.
            track.setPlaybackRate(Math.round(SAMPLE_RATE * speed));
            track.play();
            int position = 0;
            while (position < pcm.length && !cancellation.isCancelled()) {
                int requested = Math.min(16 * 1024, pcm.length - position);
                int written = track.write(pcm, position, requested, AudioTrack.WRITE_BLOCKING);
                if (written <= 0) throw new IOException("Не удалось воспроизвести аудио Gemini");
                position += written;
            }
            return !cancellation.isCancelled();
        } catch (IllegalStateException error) {
            if (cancellation.isCancelled()) return false;
            throw new IOException("Воспроизведение Gemini было прервано", error);
        } finally {
            synchronized (trackLock) {
                if (currentTrack == track) currentTrack = null;
            }
            releaseQuietly(track);
        }
    }

    private static String readUtf8(InputStream input, int maximumBytes) throws IOException {
        if (input == null) return "";
        try (InputStream source = input; ByteArrayOutputStream output = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[8 * 1024];
            int count;
            while ((count = source.read(buffer)) != -1) {
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
            return compact.isEmpty() ? "неизвестная ошибка API" : compact.substring(0, Math.min(260, compact.length()));
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
