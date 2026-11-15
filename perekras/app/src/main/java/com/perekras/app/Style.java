package com.perekras.app;

import org.json.JSONException;
import org.json.JSONObject;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Настройки внешнего вида рабочего стола: одно оформление на все приложения
 * (маска формы, палитра, обои). Хранится в SharedPreferences.
 */
public final class Style {

    public static final String[] FORM_TITLES = {"Квадрат", "Круг", "Самсунг", "Как в теме"};
    public static final int FORM_SQUARE = 0;
    public static final int FORM_ROUND = 1;
    public static final int FORM_SAMSUNG = 2;
    public static final int FORM_THEME = 3;

    /** Пары: цвет фона, цвет значка. */
    private static final int[][] PALETTES = {
            {0xFF6D5BD0, 0xFFFFFFFF},
            {0xFF0B1B33, 0xFF5BE7C4},
            {0xFFFFFFFF, 0xFF1F2937},
            {0xFFFFD8A8, 0xFFFF6B6B},
            {0xFF101418, 0xFFFFC93C},
            {0xFFECECEC, 0xFF2B2B2B},
            {0xFF123C2B, 0xFFC7F464},
            {0xFF3C1A5B, 0xFFFF9EFF},
    };

    private Style() {
    }

    public static int paletteCount() {
        return PALETTES.length;
    }

    public static int bg(int palette) {
        return PALETTES[wrap(palette)][0];
    }

    public static int fg(int palette) {
        return PALETTES[wrap(palette)][1];
    }

    private static int wrap(int i) {
        int n = PALETTES.length;
        return ((i % n) + n) % n;
    }

    public static JSONObject toJson(int form, int palette, String wallpaper) {
        JSONObject o = new JSONObject();
        try {
            o.put("form", form);
            o.put("palette", palette);
            o.put("wallpaper", wallpaper == null ? "" : wallpaper);
        } catch (JSONException ignored) {
        }
        return o;
    }

    public static int form(String json) {
        return num(json, "form", FORM_SQUARE);
    }

    public static int palette(String json) {
        return num(json, "palette", 0);
    }

    public static String wallpaper(String json) {
        if (json == null) return "";
        try {
            return new JSONObject(json).optString("wallpaper", "");
        } catch (JSONException e) {
            return "";
        }
    }

    private static int num(String json, String key, int def) {
        if (json == null) return def;
        try {
            return new JSONObject(json).optInt(key, def);
        } catch (JSONException e) {
            return def;
        }
    }

    /** Разбор объекта «ключ → строка» из настроек. */
    public static Map<String, String> map(String json) {
        Map<String, String> m = new LinkedHashMap<>();
        if (json == null) return m;
        try {
            JSONObject o = new JSONObject(json);
            java.util.Iterator<String> it = o.keys();
            while (it.hasNext()) {
                String k = it.next();
                m.put(k, o.optString(k));
            }
        } catch (JSONException ignored) {
        }
        return m;
    }
}
