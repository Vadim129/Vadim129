package com.vadim129.rhythmoverlay;

import android.os.SystemClock;

/** Thread-safe bridge from an audio worker to every visualizer view. */
public final class AudioLevels {
    public static final int BANDS = 16;
    private static volatile float[] levels = new float[BANDS];
    private static volatile long updatedAt;
    private static volatile String status = "Демо-анимация";

    private AudioLevels() { }

    public static void publish(float[] input) {
        float[] copy = new float[BANDS];
        for (int i = 0; i < BANDS; i++) {
            float value = i < input.length ? input[i] : 0f;
            copy[i] = Math.max(0f, Math.min(1f, value));
        }
        levels = copy;
        updatedAt = SystemClock.elapsedRealtime();
    }

    public static float[] snapshot() {
        return levels;
    }

    public static boolean isFresh() {
        return SystemClock.elapsedRealtime() - updatedAt < 900L;
    }

    public static void clear() {
        levels = new float[BANDS];
        updatedAt = 0L;
    }

    public static void setStatus(String value) {
        status = value == null ? "Демо-анимация" : value;
    }

    public static String status() {
        return status;
    }
}
