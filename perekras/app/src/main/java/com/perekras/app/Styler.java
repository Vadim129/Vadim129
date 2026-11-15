package com.perekras.app;

import android.content.Context;
import android.content.SharedPreferences;
import android.content.res.AssetManager;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.BitmapShader;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.PorterDuff;
import android.graphics.PorterDuffColorFilter;
import android.graphics.PorterDuffXfermode;
import android.graphics.RectF;
import android.graphics.Shader;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.util.regex.Pattern;

/**
 * Готовит «перекрашенный» значок: подложка цвета палитры, рисунок приложения —
 * маской того же цвета. Кэш лежит в files/style/&lt;ключ&gt;.png, поэтому картинка
 * перерисовывается только при смене оформления.
 */
public final class Styler {

    private static final String PREFS = "style";
    private static final String KEY_STYLE = "style_json";
    private static final String KEY_VERSION = "style_version";

    private Styler() {
    }

    public static SharedPreferences prefs(Context c) {
        return c.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    public static String styleJson(Context c) {
        return prefs(c).getString(KEY_STYLE, null);
    }

    public static int version(Context c) {
        return prefs(c).getInt(KEY_VERSION, 1);
    }

    public static void saveStyle(Context c, int form, int palette, String wallpaper) {
        prefs(c).edit()
                .putString(KEY_STYLE, Style.toJson(form, palette, wallpaper).toString())
                .putInt(KEY_VERSION, version(c) + 1)
                .apply();
    }

    public static File cacheDir(Context c) {
        File d = new File(c.getFilesDir(), "style");
        if (!d.exists()) d.mkdirs();
        return d;
    }

    public static String safe(String key) {
        return key.replaceAll("[^A-Za-z0-9_.-]", "_");
    }

    public static File file(Context c, String key) {
        return new File(cacheDir(c), safe(key) + ".png");
    }

    /** Готовая картинка из кэша или null. */
    public static Bitmap cached(Context c, String key) {
        File f = file(c, key);
        return f.exists() ? BitmapFactory.decodeFile(f.getAbsolutePath()) : null;
    }

    /**
     * Перекрашивает значок и кладёт результат в кэш.
     *
     * @param art     настоящий значок приложения
     * @param key     package или package/activity (имя файла кэша)
     * @param form    форма маски ({@link Style})
     * @param palette индекс палитры
     */
    public static Bitmap make(Context c, Bitmap art, String key, int form, int palette) {
        int size = 1;
        if (art != null) size = Math.max(art.getWidth(), art.getHeight());
        size = Math.max(size, 8);
        Bitmap out = Bitmap.createBitmap(size, size, Bitmap.Config.ARGB_8888);
        Canvas cv = new Canvas(out);

        Paint bg = new Paint(Paint.ANTI_ALIAS_FLAG);
        bg.setColor(Style.bg(palette));
        drawForm(cv, form, size, bg);

        if (art != null) {
            Paint art_ = new Paint(Paint.ANTI_ALIAS_FLAG);
            art_.setFilterBitmap(true);
            art_.setShader(new BitmapShader(art, Shader.TileMode.CLAMP, Shader.TileMode.CLAMP));
            art_.setColorFilter(new PorterDuffColorFilter(Style.fg(palette), PorterDuff.Mode.SRC_ATOP));
            drawForm(cv, form, size, art_);
        }
        save(out, file(c, key));
        return out;
    }

    /** Значок «как есть», но приведённый к форме маски. */
    public static Bitmap masked(Context c, Bitmap art, String key, int form) {
        int size = Math.max(art == null ? 8 : Math.max(art.getWidth(), art.getHeight()), 8);
        Bitmap out = Bitmap.createBitmap(size, size, Bitmap.Config.ARGB_8888);
        Canvas cv = new Canvas(out);
        Paint p = new Paint(Paint.ANTI_ALIAS_FLAG);
        p.setFilterBitmap(true);
        p.setShader(new BitmapShader(art, Shader.TileMode.CLAMP, Shader.TileMode.CLAMP));
        drawForm(cv, form, size, p);
        save(out, file(c, key));
        return out;
    }

    private static void drawForm(Canvas cv, int form, int size, Paint p) {
        float r = radius(form, size);
        if (form == Style.FORM_ROUND) {
            cv.drawCircle(size / 2f, size / 2f, size / 2f, p);
        } else {
            cv.drawRoundRect(new RectF(0, 0, size, size), r, r, p);
        }
    }

    public static float radius(int form, int size) {
        switch (form) {
            case Style.FORM_ROUND:
                return size / 2f;
            case Style.FORM_SAMSUNG:
                return size * 0.30f;
            case Style.FORM_THEME:
                return size * 0.36f;
            default:
                return size * 0.22f;
        }
    }

    /** Тонирует рисунок в цвет палитры, не меняя форму. */
    public static Bitmap tinted(Bitmap art, int palette) {
        Bitmap out = art.copy(Bitmap.Config.ARGB_8888, true);
        Canvas cv = new Canvas(out);
        Paint p = new Paint();
        p.setColorFilter(new PorterDuffColorFilter(Style.fg(palette), PorterDuff.Mode.SRC_ATOP));
        cv.drawBitmap(out, 0, 0, p);
        return out;
    }

    public static void save(Bitmap b, File f) {
        FileOutputStream o = null;
        try {
            File dir = f.getParentFile();
            if (dir != null && !dir.exists()) dir.mkdirs();
            o = new FileOutputStream(f);
            b.compress(Bitmap.CompressFormat.PNG, 100, o);
        } catch (IOException ignored) {
        } finally {
            if (o != null) {
                try {
                    o.close();
                } catch (IOException ignored) {
                }
            }
        }
    }

    /** Обои из assets/walls; null, если обои не выбраны или файла нет. */
    public static Bitmap wallpaper(Context c, String name) {
        if (name == null || name.isEmpty()) return null;
        if (!Pattern.matches("[A-Za-z0-9_.-]+", name)) return null;
        AssetManager am = c.getAssets();
        InputStream in = null;
        try {
            in = am.open("walls/" + name);
            Bitmap b = BitmapFactory.decodeStream(in);
            return b;
        } catch (IOException e) {
            return null;
        } finally {
            if (in != null) {
                try {
                    in.close();
                } catch (IOException ignored) {
                }
            }
        }
    }
}
