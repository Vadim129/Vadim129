package com.vadim129.rhythmoverlay;

import android.content.Context;
import android.content.SharedPreferences;

import java.util.Arrays;
import java.util.Collections;
import java.util.List;

/** A small, local catalogue. All artwork is rendered with Canvas: no licensed image pack is used. */
public final class Skin {
    public static final String PREFS = "rhythm_preferences";
    public static final String PREF_SKIN = "selected_skin";
    public static final String PREF_OPACITY = "overlay_opacity";
    public static final String PREF_SCALE = "overlay_scale";
    public static final String PREF_SENSITIVITY = "sensitivity";
    public static final String PREF_AUDIO_MODE = "audio_mode";
    public static final String PREF_OVERLAY_RUNNING = "overlay_running";

    public static final int NONE = 0;
    public static final int GIRL = 1;
    public static final int CAT = 2;
    public static final int FOX = 3;
    public static final int PANDA = 4;
    public static final int CAPYBARA = 5;

    public static final class Spec {
        public final String id;
        public final String title;
        public final String subtitle;
        public final int first;
        public final int second;
        public final int accent;
        public final int character;

        private Spec(String id, String title, String subtitle, int first, int second, int accent, int character) {
            this.id = id;
            this.title = title;
            this.subtitle = subtitle;
            this.first = first;
            this.second = second;
            this.accent = accent;
            this.character = character;
        }
    }

    public static final List<Spec> ALL = Collections.unmodifiableList(Arrays.asList(
            new Spec("neon", "Неоновый импульс", "Электрический сине-фиолетовый свет", 0xFF071322, 0xFF30196B, 0xFF7C5CFF, NONE),
            new Spec("aurora", "Полярный ритм", "Северное сияние и мягкие волны", 0xFF05251F, 0xFF0B4960, 0xFF55F5C1, NONE),
            new Spec("sunset", "Тёплый закат", "Розовый бас и янтарные пики", 0xFF35102D, 0xFFB83760, 0xFFFFCB6B, NONE),
            new Spec("glass", "Лёд и стекло", "Полупрозрачный хрустальный спектр", 0xFF18213B, 0xFF526E9F, 0xFFE0F1FF, NONE),
            new Spec("pixel", "Пиксельный клуб", "Аркадная сетка и квадратные биты", 0xFF111121, 0xFF40216F, 0xFFFF70D1, NONE),
            new Spec("matrix", "Зелёный сигнал", "Терминальный саундскейп", 0xFF03170B, 0xFF075A2B, 0xFF91FFB0, NONE),
            new Spec("cosmic", "Космо-бит", "Звёздная пыль вокруг каждого удара", 0xFF111033, 0xFF3C175F, 0xFFFF83E5, NONE),
            new Spec("mira", "Мира, DJ", "Танцующая DJ и неоновый пульт", 0xFF231329, 0xFF6D2E70, 0xFFFFD36B, GIRL),
            new Spec("luna", "Луна танцует", "Лёгкий dance-pop силуэт", 0xFF172149, 0xFF7C4CAF, 0xFF94D9FF, GIRL),
            new Spec("cat", "Кошка Луна", "Мурчащий танец под каждый бас", 0xFF19213C, 0xFF35518E, 0xFF8CF4FF, CAT),
            new Spec("fox", "Лис Ритм", "Рыжий groove и живой хвост", 0xFF3A1A12, 0xFF93401A, 0xFFFFC16B, FOX),
            new Spec("panda", "Панда Beat", "Добрый брейк-данс в бамбуковом свете", 0xFF132827, 0xFF2B6055, 0xFFB9FFE6, PANDA),
            new Spec("capybara", "Капибара Groove", "Самый спокойный танец в мире", 0xFF322317, 0xFF715039, 0xFFFFDB9B, CAPYBARA)
    ));

    private Skin() { }

    public static SharedPreferences prefs(Context context) {
        return context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    public static Spec selected(Context context) {
        return byId(prefs(context).getString(PREF_SKIN, "neon"));
    }

    public static String selectedId(Context context) {
        return prefs(context).getString(PREF_SKIN, "neon");
    }

    public static void select(Context context, String id) {
        prefs(context).edit().putString(PREF_SKIN, byId(id).id).apply();
    }

    public static Spec byId(String id) {
        if (id != null) {
            for (Spec spec : ALL) {
                if (spec.id.equals(id)) return spec;
            }
        }
        return ALL.get(0);
    }

    public static int opacity(Context context) {
        return prefs(context).getInt(PREF_OPACITY, 92);
    }

    public static int scale(Context context) {
        return prefs(context).getInt(PREF_SCALE, 100);
    }

    public static int sensitivity(Context context) {
        return prefs(context).getInt(PREF_SENSITIVITY, 100);
    }
}
