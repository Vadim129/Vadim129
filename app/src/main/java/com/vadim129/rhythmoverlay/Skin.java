package com.vadim129.rhythmoverlay;

import android.content.Context;
import android.content.SharedPreferences;
import android.graphics.Color;

import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;

/**
 * 100 visualizer presets built from ten recognisable equalizer formats. The "variant" changes
 * geometry, anchoring, segmentation and motion — colour is only the finishing palette.
 */
public final class Skin {
    public static final String PREFS = "rhythm_preferences";
    public static final String PREF_SKIN = "selected_skin";
    public static final String PREF_OPACITY = "overlay_opacity";
    public static final String PREF_SCALE = "overlay_scale";
    public static final String PREF_SENSITIVITY = "sensitivity";
    public static final String PREF_AUDIO_MODE = "audio_mode";
    public static final String PREF_OVERLAY_RUNNING = "overlay_running";

    public static final int EXPECTED_SKIN_COUNT = 100;
    public static final int PRESETS_PER_FAMILY = 10;

    public static final int LINEAR = 0;
    public static final int MIRROR = 1;
    public static final int LED = 2;
    public static final int DOTS = 3;
    public static final int WAVE = 4;
    public static final int CIRCULAR = 5;
    public static final int ORBIT = 6;
    public static final int TUNNEL = 7;
    public static final int PARTICLES = 8;
    public static final int DANCER = 9;

    private static final int[][] PALETTES = new int[][]{
            {0xFF54D7FF, 0xFF4779FF, 0xFFE5FAFF}, // ice blue
            {0xFFB36BFF, 0xFFFF63CD, 0xFFFFE8FA}, // ultraviolet
            {0xFF41F5B5, 0xFF1CBCE9, 0xFFE4FFF7}, // aqua
            {0xFFFFB84C, 0xFFFF5E83, 0xFFFFF1C7}, // sunset
            {0xFFFF4F9C, 0xFFFFA6D3, 0xFFFFECF5}, // rose
            {0xFFB6FF4A, 0xFF33E6A0, 0xFFF5FFE2}, // lime
            {0xFFFFEC58, 0xFFFF9448, 0xFFFFF8CF}, // gold
            {0xFF7B9BFF, 0xFF72F4FF, 0xFFEAF2FF}, // electric
            {0xFFFB6CFF, 0xFF856DFF, 0xFFF8EFFF}, // synth
            {0xFFFFFFFF, 0xFFC3D2FF, 0xFFFFFFFF}  // monochrome
    };

    public static final class Spec {
        public final String id;
        public final String title;
        public final String category;
        public final int style;
        public final int variant;
        public final int primary;
        public final int secondary;
        public final int accent;

        private Spec(String id, String title, String category, int style, int variant,
                     int primary, int secondary, int accent) {
            this.id = id;
            this.title = title;
            this.category = category;
            this.style = style;
            this.variant = variant;
            this.primary = primary;
            this.secondary = secondary;
            this.accent = accent;
        }
    }

    public static final List<Spec> ALL = Collections.unmodifiableList(createCatalogue());
    private static final List<String> CATEGORIES = Collections.unmodifiableList(createCategories());

    private Skin() { }

    private static List<Spec> createCatalogue() {
        ArrayList<Spec> skins = new ArrayList<Spec>(EXPECTED_SKIN_COUNT);
        add(skins, "linear", "Линейный спектр", LINEAR,
                "Clean Bars", "Rounded Flow", "Studio Meter", "Bassline", "Needles",
                "Peak Hold", "Wide Bands", "Night Grid", "Soft Columns", "Mono Hi-Fi");
        add(skins, "mirror", "Зеркальный спектр", MIRROR,
                "Twin Horizon", "Diamond Mirror", "Center Pulse", "Double Bass", "Symmetric Flow",
                "Signal Wings", "Mirror Peak", "Dual Vector", "Balanced Beat", "Wide Mirror");
        add(skins, "led", "LED-сегменты", LED,
                "Classic LED", "Violet Steps", "Amber Meter", "Studio Blocks", "Neon Ladder",
                "Peak Stack", "Bass Grid", "Segment Flow", "Digital Rack", "Bright Meter");
        add(skins, "dots", "Точечный спектр", DOTS,
                "Dotline", "Orbit Dots", "Pixel Rain", "Soft Matrix", "Signal Beads",
                "Stereo Dots", "Point Pulse", "Dot Hills", "Digital Snow", "Fine Grain");
        add(skins, "wave", "Осциллограф", WAVE,
                "Smooth Wave", "Double Wave", "Ribbon", "Pulse Line", "Stereo Trace",
                "Liquid Signal", "Bass Curve", "Wide Oscillo", "Fine Scope", "Flowing Line");
        add(skins, "circle", "Круговой спектр", CIRCULAR,
                "Circular Core", "Halo Bars", "Starburst", "Clockwise Ring", "Pulse Crown",
                "Radial Fine", "Split Ring", "Bloom Circle", "Sound Sun", "Round Spectrum");
        add(skins, "orbit", "Кольца и орбиты", ORBIT,
                "Breathing Orb", "Triple Orbit", "Audio Halo", "Satellite Ring", "Core Pulse",
                "Luminous Orbit", "Beat Planet", "Echo Rings", "Orbital Field", "Minimal Core");
        add(skins, "tunnel", "Глубина и туннель", TUNNEL,
                "Perspective Bars", "Audio Tunnel", "Chevron Depth", "Vector Hall", "Receding Grid",
                "Bass Corridor", "Signal Portal", "Prism Depth", "Frame Rush", "Deep Spectrum");
        add(skins, "particles", "Частицы и следы", PARTICLES,
                "Spark Field", "Signal Dust", "Beat Sparks", "Wave Particles", "Audio Rain",
                "Pulse Trail", "Frequency Mist", "Light Drops", "Particle Bloom", "Star Signal");
        add(skins, "dance", "Танцевальные сцены", DANCER,
                "Dance · Cyan", "Dance · Cyan Halo", "Dance · Teal", "Dance · Teal Ring", "Dance · Vocal",
                "Dance · Vocal Spectrum", "Dance · Freestyle", "Dance · Freestyle Halo", "Dance · Rose", "Dance · Rose Ring");
        if (skins.size() != EXPECTED_SKIN_COUNT) {
            throw new IllegalStateException("Catalogue must contain exactly " + EXPECTED_SKIN_COUNT + " presets");
        }
        return skins;
    }

    private static void add(List<Spec> output, String prefix, String category, int style, String... names) {
        if (names.length != PRESETS_PER_FAMILY) {
            throw new IllegalArgumentException("Each visualizer family needs " + PRESETS_PER_FAMILY + " presets");
        }
        for (int variant = 0; variant < names.length; variant++) {
            int[] palette = PALETTES[(style * 3 + variant) % PALETTES.length];
            output.add(new Spec(prefix + "-" + String.format("%02d", variant + 1), names[variant], category,
                    style, variant, palette[0], palette[1], palette[2]));
        }
    }

    private static List<String> createCategories() {
        Set<String> result = new LinkedHashSet<String>();
        for (Spec spec : ALL) result.add(spec.category);
        return new ArrayList<String>(result);
    }

    public static List<String> categories() {
        return CATEGORIES;
    }

    public static List<Spec> inCategory(String category) {
        ArrayList<Spec> result = new ArrayList<Spec>(PRESETS_PER_FAMILY);
        for (Spec spec : ALL) if (spec.category.equals(category)) result.add(spec);
        return result;
    }

    public static SharedPreferences prefs(Context context) {
        return context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    public static Spec selected(Context context) {
        return byId(prefs(context).getString(PREF_SKIN, "linear-01"));
    }

    public static String selectedId(Context context) {
        return prefs(context).getString(PREF_SKIN, "linear-01");
    }

    public static void select(Context context, String id) {
        prefs(context).edit().putString(PREF_SKIN, byId(id).id).apply();
    }

    public static Spec byId(String id) {
        if (id != null) for (Spec spec : ALL) if (spec.id.equals(id)) return spec;
        return ALL.get(0);
    }

    public static int opacity(Context context) {
        return prefs(context).getInt(PREF_OPACITY, 100);
    }

    public static int scale(Context context) {
        return prefs(context).getInt(PREF_SCALE, 100);
    }

    public static int sensitivity(Context context) {
        return prefs(context).getInt(PREF_SENSITIVITY, 100);
    }

    public static int mix(int first, int second, float amount) {
        float t = Math.max(0f, Math.min(1f, amount));
        return Color.rgb((int) (Color.red(first) + (Color.red(second) - Color.red(first)) * t),
                (int) (Color.green(first) + (Color.green(second) - Color.green(first)) * t),
                (int) (Color.blue(first) + (Color.blue(second) - Color.blue(first)) * t));
    }
}
