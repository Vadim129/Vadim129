package com.vadim129.rhythmoverlay;

import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;

import java.io.IOException;
import java.io.InputStream;

/**
 * Frame sequences sampled from the user-provided dance GIFs. They are deliberately rendered as
 * transparent PNG frames instead of replaying a GIF: EqualizerOverlayView advances them from bass
 * energy, so the dance cadence follows the music rather than a fixed GIF clock.
 */
public final class DancerSprite {
    public static final int PACK_COUNT = 5;
    public static final int FRAMES_PER_PACK = 12;
    private static final Bitmap[][] CACHE = new Bitmap[PACK_COUNT][FRAMES_PER_PACK];

    private DancerSprite() { }

    public static Bitmap frame(Context context, int pack, int frame) {
        int safePack = Math.max(0, Math.min(PACK_COUNT - 1, pack));
        int safeFrame = Math.max(0, Math.min(FRAMES_PER_PACK - 1, frame));
        synchronized (CACHE) {
            Bitmap cached = CACHE[safePack][safeFrame];
            if (cached != null) return cached;
            String path = String.format("dancers/%d/frame_%02d.png", safePack, safeFrame);
            InputStream input = null;
            try {
                input = context.getAssets().open(path);
                Bitmap decoded = BitmapFactory.decodeStream(input);
                CACHE[safePack][safeFrame] = decoded;
                return decoded;
            } catch (IOException ignored) {
                return null;
            } finally {
                if (input != null) {
                    try { input.close(); } catch (IOException ignored) { }
                }
            }
        }
    }
}
