package com.perekras.app;

import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.LauncherApps;
import android.content.pm.PackageManager;
import android.content.pm.ResolveInfo;
import android.content.pm.ShortcutInfo;
import android.content.pm.ShortcutManager;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Rect;
import android.graphics.drawable.Drawable;
import android.graphics.drawable.Icon;

import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;

/**
 * Что перекрашено, как получить значки приложений и как закрепить результат
 * ярлыками на рабочем столе.
 */
public final class Apps {

    public static final String EXTRA_PACKAGE = "pkg";
    public static final String EXTRA_ACTIVITY = "act";
    public static final String EXTRA_LABEL = "label";

    private static final String PREFS = "desk";
    private static final String KEY_KEYS = "picked";
    private static final String KEY_LAST = "last_package";
    private static final String KEY_QUERY_KIND = "query_kind";
    private static final String KEY_ICONS = "own_icons";

    private Apps() {
    }

    public static SharedPreferences prefs(Context c) {
        return c.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    /** Список «package/activity» тех приложений, что уже перекрашены. */
    public static List<String> picked(Context c) {
        String raw = prefs(c).getString(KEY_KEYS, "");
        List<String> out = new ArrayList<>();
        if (raw == null || raw.isEmpty()) return out;
        for (String s : raw.split("\n")) {
            if (!s.isEmpty()) out.add(s);
        }
        return out;
    }

    public static boolean isPicked(Context c, String key) {
        return picked(c).contains(key);
    }

    public static void addPicked(Context c, String key) {
        List<String> list = picked(c);
        if (list.contains(key)) return;
        list.add(key);
        save(context(c), list);
    }

    public static void removePicked(Context c, String key) {
        List<String> list = picked(c);
        list.remove(key);
        save(c, list);
    }

    private static Context context(Context c) {
        return c;
    }

    private static void save(Context c, List<String> list) {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < list.size(); i++) {
            if (i > 0) sb.append('\n');
            sb.append(list.get(i));
        }
        prefs(c).edit().putString(KEY_KEYS, sb.toString()).apply();
    }

    /** Сколько ещё ярлыков получится закрепить (у приложения их лимит). */
    public static int freeSlots(Context c) {
        ShortcutManager sm = c.getSystemService(ShortcutManager.class);
        int max = sm == null ? 0 : sm.getMaxShortcutCountPerActivity();
        return Math.max(0, max - picked(c).size());
    }

    public static int maxSlots(Context c) {
        ShortcutManager sm = c.getSystemService(ShortcutManager.class);
        return sm == null ? 0 : sm.getMaxShortcutCountPerActivity();
    }

    /** Какая своя картинка поставлена приложению (пусто — общая). */
    public static String iconFor(Context c, String key) {
        return Style.map(prefs(c).getString(KEY_ICONS, null)).get(Styler.safe(key));
    }

    public static void rememberIcon(Context c, String key, String image) {
        java.util.Map<String, String> m = Style.map(prefs(c).getString(KEY_ICONS, null));
        m.put(Styler.safe(key), image);
        org.json.JSONObject o = new org.json.JSONObject();
        try {
            for (java.util.Map.Entry<String, String> e : m.entrySet()) {
                if (e.getValue() != null) o.put(e.getKey(), e.getValue());
            }
        } catch (org.json.JSONException ignored) {
        }
        prefs(c).edit().putString(KEY_ICONS, o.toString()).apply();
    }

    /** Готовая картинка ярлыка: своя картинка, кэш перекраски или настоящий значок. */
    public static Bitmap styled(Context c, String pkg, String act, int size) {
        String key = key(pkg, act);
        String own = iconFor(c, key);
        if (own != null && !own.isEmpty()) {
            Bitmap b = Media.load(c, own);
            if (b != null) return b;
        }
        Bitmap cached = Styler.cached(c, key);
        if (cached != null) return cached;
        return iconOf(c, pkg, act, size);
    }

    /** Обратный разбор ключа: {package, activity} или null для чужих ключей. */
    public static String[] split(String key) {
        int i = key.indexOf("__");
        if (i <= 0) return null;
        String pkg = key.substring(0, i);
        String act = key.substring(i + 2);
        if (pkg.isEmpty()) return null;
        return new String[]{pkg, act};
    }

    public static String lastPackage(Context c) {
        return prefs(c).getString(KEY_LAST, null);
    }

    public static void setLastPackage(Context c, String pkg) {
        prefs(c).edit().putString(KEY_LAST, pkg).apply();
    }

    /** 0 — пробуем показать «все приложения», 1 — только видимые без разрешения. */
    public static int queryKind(Context c) {
        return prefs(c).getInt(KEY_QUERY_KIND, 0);
    }

    public static void setQueryKind(Context c, int kind) {
        prefs(c).edit().putInt(KEY_QUERY_KIND, kind).apply();
    }

    public static void notifyHome(Context c) {
        Intent i = new Intent(FloatingHome.ACTION_REFRESH);
        i.setPackage(c.getPackageName());
        c.sendBroadcast(i);
    }

    // ---------------------------------------------------------------- ярлыки

    public static boolean pin(Context c, String pkg, String act, Bitmap icon, String label) {
        ShortcutManager sm = c.getSystemService(ShortcutManager.class);
        if (sm == null) return false;
        List<String> have = picked(c);
        if (have.size() >= sm.getMaxShortcutCountPerActivity()) return false;
        try {
            sm.pinShortcuts(Collections.singletonList(shortcut(c, pkg, act, icon, label)),
                    Collections.singletonList(launcherIntent(c)));
            addPicked(c, key(pkg, act));
            return true;
        } catch (Throwable t) {
            return false;
        }
    }

    /** Куда вернуться после запуска приложения по ярлыку. */
    public static Intent launcherIntent(Context c) {
        return new Intent(c, FloatingHome.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
    }

    /** Ключ приложения: стабильный и безопасный как идентификатор ярлыка и имя файла. */
    public static String key(String pkg, String act) {
        return Styler.safe(pkg + "__" + (act == null ? "" : act));
    }

    public static ShortcutInfo shortcut(Context c, String pkg, String act, Bitmap icon, String label) {
        Intent launch;
        if (act != null && !act.isEmpty()) {
            launch = new Intent(Intent.ACTION_MAIN).setClassName(pkg, act);
        } else {
            launch = c.getPackageManager().getLaunchIntentForPackage(pkg);
            if (launch == null) launch = new Intent(Intent.ACTION_MAIN);
        }
        launch.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        return new ShortcutInfo.Builder(c, Styler.safe(key(pkg, act)))
                .setShortLabel(label(label, pkg))
                .setLongLabel(label(label, pkg))
                .setIcon(Icon.createWithBitmap(icon))
                .setIntent(launch)
                .setRank(0)
                .build();
    }

    private static String label(String label, String pkg) {
        String s = label == null || label.trim().isEmpty() ? pkg : label.trim();
        return s.length() > 40 ? s.substring(0, 40) : s;
    }

    /**
     * Запасной ярлык: если в системе не нашлось подходящего приложения,
     * ставим ярлык на своего «тихого» помощника — тема всё равно применится.
     */
    public static ShortcutInfo fallback(Context c, Bitmap icon, String label) {
        Intent i = new Intent(c, EmptyActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        return new ShortcutInfo.Builder(c, "theme_" + System.currentTimeMillis())
                .setShortLabel(label(label, "Перекрас"))
                .setLongLabel(label(label, "Перекрас"))
                .setIcon(Icon.createWithBitmap(icon))
                .setIntent(i)
                .build();
    }

    public static boolean pinFallback(Context c, Bitmap icon, String label) {
        ShortcutManager sm = c.getSystemService(ShortcutManager.class);
        if (sm == null) return false;
        try {
            sm.pinShortcuts(Collections.singletonList(fallback(c, icon, label)),
                    Collections.singletonList(launcherIntent(c)));
            return true;
        } catch (Throwable t) {
            return false;
        }
    }

    /**
     * Отметить тему применённой. На устройствах, где система умеет отдавать
     * перерисованные значки (свой «помощник значков»), достаточно поставить
     * один ярлык-маркер. Иначе человек видит предупреждение на экране.
     */
    public static void applyTheme(Context c, Bitmap icon, String label) {
        pinFallback(c, icon, label);
        hideDynamic(c);
    }

    public static void unpin(Context c, String pkg, String act) {
        ShortcutManager sm = c.getSystemService(ShortcutManager.class);
        if (sm == null) return;
        List<String> id = Collections.singletonList(Styler.safe(key(pkg, act)));
        try {
            sm.disableShortcuts(id);
        } catch (Throwable ignored) {
        }
        removePicked(c, key(pkg, act));
    }

    /**
     * Сбрасывает встроенные «динамические» ярлыки. Иначе на некоторых
     * лаунчерах рядом со значком приложения висит стрелка-меню.
     */
    public static void hideDynamic(Context c) {
        ShortcutManager sm = c.getSystemService(ShortcutManager.class);
        if (sm == null) return;
        try {
            List<String> ids = new ArrayList<>();
            for (ShortcutInfo i : sm.getDynamicShortcuts()) ids.add(i.getId());
            if (!ids.isEmpty()) sm.removeDynamicShortcuts(ids);
        } catch (Throwable ignored) {
        }
    }

    // ------------------------------------------------------------- приложения

    /** Приложение с иконкой на рабочем столе. */
    public static final class Row {
        public final String pkg;
        public final String act;
        public final String label;
        public final Drawable icon;

        Row(String pkg, String act, String label, Drawable icon) {
            this.pkg = pkg;
            this.act = act;
            this.label = label;
            this.icon = icon;
        }

        public String key() {
            return Apps.key(pkg, act);
        }
    }

    /** Все приложения, которые можно запустить. */
    public static List<Row> installed(Context c) {
        PackageManager pm = c.getPackageManager();
        List<Row> out = new ArrayList<>();
        Set<String> seen = new LinkedHashSet<>();
        Intent main = new Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER);
        List<ResolveInfo> ris;
        try {
            ris = pm.queryIntentActivities(main, 0);
        } catch (Throwable t) {
            ris = Collections.emptyList();
        }
        for (ResolveInfo ri : ris) {
            if (ri.activityInfo == null) continue;
            String pkg = ri.activityInfo.packageName;
            String act = ri.activityInfo.name;
            if (pkg.equals(c.getPackageName()) && act.equals(MainActivity.class.getName())) continue;
            String k = key(pkg, act);
            if (!seen.add(k)) continue;
            CharSequence lab = null;
            Drawable d = null;
            try {
                lab = ri.loadLabel(pm);
            } catch (Throwable ignored) {
            }
            try {
                d = ri.activityInfo.loadIcon(pm);
            } catch (Throwable ignored) {
            }
            out.add(new Row(pkg, act, lab == null ? pkg : lab.toString(), d));
        }
        Collections.sort(out, new Comparator<Row>() {
            @Override
            public int compare(Row a, Row b) {
                return a.label.compareToIgnoreCase(b.label);
            }
        });
        return out;
    }

    // ----------------------------------------------------------------- значки

    public static Bitmap iconOf(Context c, String pkg, String act, int size) {
        Drawable d = null;
        try {
            PackageManager pm = c.getPackageManager();
            if (act != null && !act.isEmpty()) {
                d = pm.getActivityIcon(new ComponentName(pkg, act));
            }
            if (d == null) d = pm.getApplicationIcon(pkg);
        } catch (Throwable ignored) {
        }
        return draw(d, size);
    }

    public static Bitmap draw(Drawable d, int size) {
        Bitmap b = Bitmap.createBitmap(size, size, Bitmap.Config.ARGB_8888);
        Canvas cv = new Canvas(b);
        if (d != null) {
            d.setBounds(new Rect(0, 0, size, size));
            d.draw(cv);
        }
        return b;
    }

    /** Значок ярлыка так, как его рисует система (крупнее и «как у людей»). */
    public static Bitmap shortcutIcon(Context c, ShortcutInfo info, int size) {
        try {
            LauncherApps la = c.getSystemService(LauncherApps.class);
            if (la == null) return null;
            Drawable d = la.getShortcutIconDrawable(info, c.getResources().getDisplayMetrics().densityDpi);
            return d == null ? null : draw(d, size);
        } catch (Throwable t) {
            return null;
        }
    }

    public static List<ShortcutInfo> pinnedShortcuts(Context c) {
        ShortcutManager sm = c.getSystemService(ShortcutManager.class);
        if (sm == null) return Collections.emptyList();
        try {
            return sm.getPinnedShortcuts();
        } catch (Throwable t) {
            return Collections.emptyList();
        }
    }

    /** Запуск приложения по «пакет/активити» (для собственного рабочего стола). */
    public static boolean launch(Context c, String pkg, String act) {
        try {
            Intent i;
            if (act != null && !act.isEmpty()) {
                i = new Intent(Intent.ACTION_MAIN).setClassName(pkg, act);
            } else {
                i = c.getPackageManager().getLaunchIntentForPackage(pkg);
            }
            if (i == null) return false;
            i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            c.startActivity(i);
            return true;
        } catch (Throwable t) {
            return false;
        }
    }

    /** Открыть системный экран «Домашний экран» — выбрать наш рабочий стол. */
    public static Intent homeSettings(Context c) {
        Intent i = new Intent(android.provider.Settings.ACTION_HOME_SETTINGS);
        i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        return i;
    }

    public static boolean isDefaultHome(Context c) {
        try {
            Intent home = new Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_HOME);
            ResolveInfo ri = c.getPackageManager().resolveActivity(home, PackageManager.MATCH_DEFAULT_ONLY);
            return ri != null && ri.activityInfo != null
                    && c.getPackageName().equals(ri.activityInfo.packageName);
        } catch (Throwable t) {
            return false;
        }
    }
}
