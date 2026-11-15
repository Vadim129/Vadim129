package com.perekras.app;

import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.net.Uri;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;

/** Импорт картинок (значок вместо приложения, свои обои). */
public final class Media {

    public static final int MAX = 1024;

    private Media() {
    }

    public static File dir(Context c) {
        File d = new File(c.getFilesDir(), "images");
        if (!d.exists()) d.mkdirs();
        return d;
    }

    /**
     * Копирует выбранную картинку внутрь приложения и возвращает её имя
     * (например custom_1731.png) либо null, если прочитать не удалось.
     */
    public static String storeImage(Context c, Uri uri) {
        InputStream in = null;
        FileOutputStream out = null;
        try {
            in = c.getContentResolver().openInputStream(uri);
            if (in == null) return null;
            BitmapFactory.Options o = new BitmapFactory.Options();
            o.inJustDecodeBounds = true;
            BitmapFactory.decodeStream(in, null, o);
            if (in != null) in.close();
            in = c.getContentResolver().openInputStream(uri);
            BitmapFactory.Options o2 = new BitmapFactory.Options();
            o2.inSampleSize = sample(o.outWidth, o.outHeight);
            Bitmap bm = BitmapFactory.decodeStream(in, null, o2);
            if (bm == null) return null;
            String name = "custom_" + System.currentTimeMillis() + ".png";
            out = new FileOutputStream(new File(dir(c), name));
            bm.compress(Bitmap.CompressFormat.PNG, 100, out);
            return name;
        } catch (IOException e) {
            return null;
        } finally {
            close(in);
            if (out != null) {
                try {
                    out.close();
                } catch (IOException ignored) {
                }
            }
        }
    }

    private static int sample(int w, int h) {
        int s = 2;
        while (w / s > MAX || h / s > MAX) s *= 2;
        return s;
    }

    public static Bitmap load(Context c, String name) {
        if (name == null || name.isEmpty()) return null;
        File f = new File(dir(c), name);
        return f.exists() ? BitmapFactory.decodeFile(f.getAbsolutePath()) : null;
    }

    private static void close(InputStream in) {
        if (in != null) {
            try {
                in.close();
            } catch (IOException ignored) {
            }
        }
    }
}
