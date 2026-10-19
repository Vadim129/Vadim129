package com.vadim129.rhythmoverlay;

import android.content.Context;
import android.content.SharedPreferences;

import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;

/**
 * The catalogue deliberately contains 100 actual visual compositions, not one renderer with
 * recoloured presets. Each of the 25 families has its own drawing routine and four layouts.
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

    public static final int HEARTS = 0;
    public static final int DIAMONDS = 1;
    public static final int CLUBS = 2;
    public static final int SPADES = 3;
    public static final int RUBY = 4;
    public static final int SAPPHIRE = 5;
    public static final int EMERALD = 6;
    public static final int AMETHYST = 7;
    public static final int FIRE = 8;
    public static final int WATER = 9;
    public static final int ICE = 10;
    public static final int LIGHTNING = 11;
    public static final int SUN = 12;
    public static final int MOON = 13;
    public static final int CONSTELLATION = 14;
    public static final int COMET = 15;
    public static final int VINYL = 16;
    public static final int CASSETTE = 17;
    public static final int SYNTHWAVE = 18;
    public static final int ARCADE = 19;
    public static final int SAKURA = 20;
    public static final int LOTUS = 21;
    public static final int BUBBLES = 22;
    public static final int INK = 23;
    public static final int HOLOGRAM = 24;

    public static final class Spec {
        public final String id;
        public final String title;
        public final String category;
        public final int kind;
        public final int variant;
        public final int primary;
        public final int secondary;
        public final int accent;

        private Spec(String id, String title, String category, int kind, int variant,
                     int primary, int secondary, int accent) {
            this.id = id;
            this.title = title;
            this.category = category;
            this.kind = kind;
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
        add(skins, "hearts", "Карты · Черви", HEARTS, 0xFFE53E5D, 0xFFFF9CA8, 0xFFFFE5EA,
                "Валет червей", "Дама червей", "Король червей", "Туз червей");
        add(skins, "diamonds", "Карты · Бубны", DIAMONDS, 0xFFFF714D, 0xFFFFC265, 0xFFFFF0D0,
                "Валет бубен", "Дама бубен", "Король бубен", "Туз бубен");
        add(skins, "clubs", "Карты · Трефы", CLUBS, 0xFF36C987, 0xFF9BF3C1, 0xFFE5FFF0,
                "Валет треф", "Дама треф", "Король треф", "Туз треф");
        add(skins, "spades", "Карты · Пики", SPADES, 0xFF8B9BBB, 0xFFD7E3FF, 0xFFFFFFFF,
                "Валет пик", "Дама пик", "Король пик", "Туз пик");

        add(skins, "ruby", "Камни · Рубин", RUBY, 0xFFE1234A, 0xFFFF627C, 0xFFFFCDD6,
                "Рубиновая огранка", "Рубиновая корона", "Рубиновый разлом", "Рубиновый талисман");
        add(skins, "sapphire", "Камни · Сапфир", SAPPHIRE, 0xFF276CE6, 0xFF61B4FF, 0xFFD6F0FF,
                "Сапфировая огранка", "Сапфировая корона", "Сапфировый разлом", "Сапфировый талисман");
        add(skins, "emerald", "Камни · Изумруд", EMERALD, 0xFF11A86A, 0xFF69F5B0, 0xFFD6FFE9,
                "Изумрудная огранка", "Изумрудная корона", "Изумрудный разлом", "Изумрудный талисман");
        add(skins, "amethyst", "Камни · Аметист", AMETHYST, 0xFF8E4BE3, 0xFFD889FF, 0xFFF2D8FF,
                "Аметистовая огранка", "Аметистовая корона", "Аметистовый разлом", "Аметистовый талисман");

        add(skins, "fire", "Стихии · Огонь", FIRE, 0xFFFF562C, 0xFFFFB044, 0xFFFFEC9F,
                "Искра", "Костёр", "Плазма", "Феникс");
        add(skins, "water", "Стихии · Вода", WATER, 0xFF168EE9, 0xFF64DEFF, 0xFFD8F8FF,
                "Прилив", "Водоворот", "Дождь", "Каскад");
        add(skins, "ice", "Стихии · Лёд", ICE, 0xFF78DFFF, 0xFFB8F4FF, 0xFFFFFFFF,
                "Иней", "Кристалл льда", "Полярная звезда", "Морозный узор");
        add(skins, "lightning", "Стихии · Молния", LIGHTNING, 0xFFFFD83D, 0xFFFF8C42, 0xFFFFF5B5,
                "Разряд", "Гроза", "Электродуга", "Шторм");

        add(skins, "sun", "Космос · Солнце", SUN, 0xFFFFA62B, 0xFFFFD66B, 0xFFFFF5BD,
                "Рассвет", "Полдень", "Корона", "Солнечный ветер");
        add(skins, "moon", "Космос · Луна", MOON, 0xFF9BAAFF, 0xFFD6DCFF, 0xFFFFFFFF,
                "Новолуние", "Серп", "Полнолуние", "Лунное затмение");
        add(skins, "constellation", "Космос · Созвездия", CONSTELLATION, 0xFF88A7FF, 0xFFE2E9FF, 0xFFFFFFFF,
                "Орион", "Лира", "Кассиопея", "Дракон");
        add(skins, "comet", "Космос · Кометы", COMET, 0xFFFF75D3, 0xFF8DEBFF, 0xFFFFFFFF,
                "Розовая комета", "Ледяная комета", "Золотой след", "Метеорный дождь");

        add(skins, "vinyl", "Музыка · Винил", VINYL, 0xFFFF4F92, 0xFF7E5CFF, 0xFFFFE9F4,
                "Розовый диск", "Ночной диск", "Двойной диск", "Солнечный диск");
        add(skins, "cassette", "Музыка · Кассеты", CASSETTE, 0xFFFFB64C, 0xFFFF6E84, 0xFFFFF0C8,
                "Mixtape", "Хром", "Кислотная лента", "Золотая лента");
        add(skins, "synth", "Музыка · Синтвейв", SYNTHWAVE, 0xFFFF4DC4, 0xFF7C5CFF, 0xFFC7F5FF,
                "Сетка", "Лазер", "Горизонт", "Ночная трасса");
        add(skins, "arcade", "Музыка · Аркада", ARCADE, 0xFF44FFB6, 0xFFFF5DE1, 0xFFE9FEFF,
                "Пиксельный бит", "Галактика", "Лабиринт", "Бонус-уровень");

        add(skins, "sakura", "Природа · Сакура", SAKURA, 0xFFFF83B7, 0xFFFFC8E0, 0xFFFFF5FA,
                "Лепестки", "Ветка", "Весенний ветер", "Розовый дождь");
        add(skins, "lotus", "Природа · Лотос", LOTUS, 0xFFB96CFF, 0xFFFFA7E1, 0xFFFFE8F7,
                "Лиловый лотос", "Розовый лотос", "Ночной лотос", "Золотой лотос");
        add(skins, "bubbles", "Природа · Пузыри", BUBBLES, 0xFF4AD8FF, 0xFFB1F7FF, 0xFFFFFFFF,
                "Лагуна", "Газировка", "Жемчуг", "Мыльная радуга");
        add(skins, "ink", "Абстракция · Чернила", INK, 0xFF5B5EFF, 0xFFFF73B4, 0xFFF2E7FF,
                "Чернильная волна", "Клякса", "Шёлковый след", "Спираль");
        add(skins, "hologram", "Абстракция · Голограмма", HOLOGRAM, 0xFF55FBE6, 0xFF5D93FF, 0xFFE4FFFF,
                "Призма", "Куб", "Радар", "Вектор");
        if (skins.size() != EXPECTED_SKIN_COUNT) {
            throw new IllegalStateException("Catalogue must contain exactly " + EXPECTED_SKIN_COUNT + " skins");
        }
        return skins;
    }

    private static void add(List<Spec> list, String idPrefix, String category, int kind,
                            int primary, int secondary, int accent, String a, String b, String c, String d) {
        String[] names = new String[]{a, b, c, d};
        for (int variant = 0; variant < names.length; variant++) {
            list.add(new Spec(idPrefix + "-" + (variant + 1), names[variant], category, kind, variant,
                    shade(primary, variant), shade(secondary, (variant + 2) % 4), accent));
        }
    }

    private static int shade(int color, int variant) {
        float[] factors = new float[]{.84f, 1f, .92f, 1.10f};
        float factor = factors[variant];
        int r = Math.min(255, Math.max(0, (int) (((color >> 16) & 0xFF) * factor)));
        int g = Math.min(255, Math.max(0, (int) (((color >> 8) & 0xFF) * factor)));
        int b = Math.min(255, Math.max(0, (int) ((color & 0xFF) * factor)));
        return 0xFF000000 | (r << 16) | (g << 8) | b;
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
        ArrayList<Spec> result = new ArrayList<Spec>(4);
        for (Spec spec : ALL) if (spec.category.equals(category)) result.add(spec);
        return result;
    }

    public static SharedPreferences prefs(Context context) {
        return context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    public static Spec selected(Context context) {
        return byId(prefs(context).getString(PREF_SKIN, "hearts-1"));
    }

    public static String selectedId(Context context) {
        return prefs(context).getString(PREF_SKIN, "hearts-1");
    }

    public static void select(Context context, String id) {
        prefs(context).edit().putString(PREF_SKIN, byId(id).id).apply();
    }

    public static Spec byId(String id) {
        if (id != null) {
            for (Spec spec : ALL) if (spec.id.equals(id)) return spec;
        }
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
}
