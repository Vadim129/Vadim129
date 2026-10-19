package com.vadim129.rhythmoverlay;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.PorterDuff;
import android.graphics.RectF;
import android.os.SystemClock;
import android.view.MotionEvent;
import android.view.ScaleGestureDetector;
import android.view.View;
import android.view.ViewConfiguration;

/**
 * A deliberately transparent overlay: it paints only the skin and equalizer, never a rectangle
 * background or caption. One finger drags it, two fingers resize it, and a long press opens settings.
 */
public class EqualizerOverlayView extends View {
    public interface DragCallback {
        void onDrag(float dx, float dy);
        void onResize(float scaleFactor);
        void onOpenSettings();
    }

    private static final int BARS_VERTICAL = 0;
    private static final int BARS_FACET = 1;
    private static final int BARS_WAVE = 2;
    private static final int BARS_RADIAL = 3;
    private static final int BARS_PIXEL = 4;

    private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint stroke = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Path path = new Path();
    private final RectF rect = new RectF();
    private final float[] shown = new float[AudioLevels.BANDS];
    private final float density;
    private final boolean preview;
    private final int touchSlop;
    private final ScaleGestureDetector scaleDetector;
    private String skinId;
    private DragCallback dragCallback;
    private float downRawX;
    private float downRawY;
    private float downX;
    private float downY;
    private boolean touchActive;
    private boolean moved;
    private boolean resizing;
    private boolean longPressed;
    private long startedAt = SystemClock.elapsedRealtime();

    private final Runnable longPress = new Runnable() {
        @Override public void run() {
            if (touchActive && !moved && !resizing && !preview && dragCallback != null) {
                longPressed = true;
                performLongClick();
                dragCallback.onOpenSettings();
            }
        }
    };

    public EqualizerOverlayView(Context context) {
        this(context, null, false);
    }

    public EqualizerOverlayView(Context context, String skinId, boolean preview) {
        super(context);
        this.preview = preview;
        this.skinId = skinId;
        density = getResources().getDisplayMetrics().density;
        touchSlop = ViewConfiguration.get(context).getScaledTouchSlop();
        stroke.setStyle(Paint.Style.STROKE);
        stroke.setStrokeCap(Paint.Cap.ROUND);
        setLayerType(View.LAYER_TYPE_SOFTWARE, null);
        scaleDetector = new ScaleGestureDetector(context, new ScaleGestureDetector.SimpleOnScaleGestureListener() {
            @Override public boolean onScaleBegin(ScaleGestureDetector detector) {
                if (EqualizerOverlayView.this.preview || dragCallback == null) return false;
                resizing = true;
                removeCallbacks(longPress);
                return true;
            }

            @Override public boolean onScale(ScaleGestureDetector detector) {
                if (dragCallback == null) return false;
                float factor = Math.max(.90f, Math.min(1.12f, detector.getScaleFactor()));
                dragCallback.onResize(factor);
                return true;
            }

            @Override public void onScaleEnd(ScaleGestureDetector detector) {
                resizing = false;
            }
        });
    }

    public void setSkinId(String id) {
        skinId = id;
        invalidate();
    }

    public void setDragCallback(DragCallback callback) {
        dragCallback = callback;
    }

    private float dp(float value) {
        return value * density;
    }

    @Override
    protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);
        final int width = getWidth();
        final int height = getHeight();
        if (width < 2 || height < 2) return;

        // The Window itself is translucent. Clearing prevents a stale frame from becoming a background.
        canvas.drawColor(Color.TRANSPARENT, PorterDuff.Mode.CLEAR);
        Skin.Spec spec = skinId == null ? Skin.selected(getContext()) : Skin.byId(skinId);
        float time = (SystemClock.elapsedRealtime() - startedAt) / 1000f;
        boolean live = !preview && AudioLevels.isFresh();
        float[] levels = AudioLevels.snapshot();
        float sensitivity = Skin.sensitivity(getContext()) / 100f;
        for (int i = 0; i < shown.length; i++) {
            float target;
            if (live) {
                target = clamp(levels[i] * sensitivity, 0f, 1f);
            } else {
                float rhythm = (float) ((Math.sin(time * (2.25f + i * .14f) + i * .63f) + 1d) * .5d);
                target = .10f + rhythm * .22f + (i % 5 == 0 ? .08f : 0f);
            }
            shown[i] += (target - shown[i]) * (live ? .34f : .10f);
        }
        float beat = average();
        drawSkinArt(canvas, spec, width, height, time, beat);
        drawEqualizer(canvas, spec, width, height, time);
        postInvalidateDelayed(preview ? 78L : 33L);
    }

    private void drawSkinArt(Canvas canvas, Skin.Spec spec, int w, int h, float time, float beat) {
        switch (spec.kind) {
            case Skin.HEARTS: drawCards(canvas, spec, w, h, time, 0); break;
            case Skin.DIAMONDS: drawCards(canvas, spec, w, h, time, 1); break;
            case Skin.CLUBS: drawCards(canvas, spec, w, h, time, 2); break;
            case Skin.SPADES: drawCards(canvas, spec, w, h, time, 3); break;
            case Skin.RUBY: case Skin.SAPPHIRE: case Skin.EMERALD: case Skin.AMETHYST:
                drawGem(canvas, spec, w, h, time, beat); break;
            case Skin.FIRE: drawFire(canvas, spec, w, h, time, beat); break;
            case Skin.WATER: drawWater(canvas, spec, w, h, time, beat); break;
            case Skin.ICE: drawIce(canvas, spec, w, h, time, beat); break;
            case Skin.LIGHTNING: drawLightning(canvas, spec, w, h, time, beat); break;
            case Skin.SUN: drawSun(canvas, spec, w, h, time, beat); break;
            case Skin.MOON: drawMoon(canvas, spec, w, h, time, beat); break;
            case Skin.CONSTELLATION: drawConstellation(canvas, spec, w, h, time); break;
            case Skin.COMET: drawComets(canvas, spec, w, h, time, beat); break;
            case Skin.VINYL: drawVinyl(canvas, spec, w, h, time, beat); break;
            case Skin.CASSETTE: drawCassette(canvas, spec, w, h, time, beat); break;
            case Skin.SYNTHWAVE: drawSynthwave(canvas, spec, w, h, time, beat); break;
            case Skin.ARCADE: drawArcade(canvas, spec, w, h, time, beat); break;
            case Skin.SAKURA: drawSakura(canvas, spec, w, h, time, beat); break;
            case Skin.LOTUS: drawLotus(canvas, spec, w, h, time, beat); break;
            case Skin.BUBBLES: drawBubbles(canvas, spec, w, h, time, beat); break;
            case Skin.INK: drawInk(canvas, spec, w, h, time, beat); break;
            case Skin.HOLOGRAM: drawHologram(canvas, spec, w, h, time, beat); break;
            default: break;
        }
    }

    private void drawCards(Canvas canvas, Skin.Spec spec, int w, int h, float time, int suit) {
        float cx = w * .5f;
        float cy = h * .52f;
        float giant = Math.min(w, h) * (.26f + spec.variant * .025f);
        paint.setColor(alpha(spec.primary, 35));
        drawSuit(canvas, suit, cx, cy, giant, paint);
        int count = spec.variant + 1;
        float spread = Math.min(w, h) * .28f;
        for (int i = 0; i < count; i++) {
            float angle = (float) (time * (.28f + i * .04f) + (Math.PI * 2d * i / count));
            float x = cx + (float) Math.cos(angle) * spread;
            float y = cy + (float) Math.sin(angle) * spread * .65f;
            paint.setColor(alpha(i % 2 == 0 ? spec.accent : spec.secondary, 155));
            drawSuit(canvas, suit, x, y, dp(9 + (i % 2) * 2), paint);
        }
        stroke.setStrokeWidth(dp(1.2f));
        stroke.setColor(alpha(spec.accent, 135));
        canvas.drawCircle(cx, cy, giant * 1.1f, stroke);
    }

    private void drawGem(Canvas canvas, Skin.Spec spec, int w, int h, float time, float beat) {
        float cx = w * .5f;
        float cy = h * .5f;
        int sides = 4 + spec.variant * 2;
        float radius = Math.min(w, h) * (.33f + beat * .08f);
        path.reset();
        for (int i = 0; i < sides; i++) {
            float a = (float) (time * .32f + Math.PI * 2d * i / sides - Math.PI / 2d);
            float x = cx + (float) Math.cos(a) * radius;
            float y = cy + (float) Math.sin(a) * radius;
            if (i == 0) path.moveTo(x, y); else path.lineTo(x, y);
        }
        path.close();
        paint.setColor(alpha(spec.primary, 58));
        canvas.drawPath(path, paint);
        stroke.setStrokeWidth(dp(1.7f));
        stroke.setColor(alpha(spec.accent, 205));
        canvas.drawPath(path, stroke);
        for (int i = 0; i < sides; i++) {
            float a = (float) (time * .32f + Math.PI * 2d * i / sides - Math.PI / 2d);
            float x = cx + (float) Math.cos(a) * radius;
            float y = cy + (float) Math.sin(a) * radius;
            stroke.setColor(alpha(i % 2 == 0 ? spec.secondary : spec.accent, 125));
            canvas.drawLine(cx, cy, x, y, stroke);
        }
        paint.setColor(alpha(Color.WHITE, 155));
        canvas.drawCircle(cx - radius * .18f, cy - radius * .2f, dp(3.5f), paint);
    }

    private void drawFire(Canvas canvas, Skin.Spec spec, int w, int h, float time, float beat) {
        float base = h * .88f;
        int flames = 3 + spec.variant;
        for (int i = 0; i < flames; i++) {
            float x = w * (i + 1f) / (flames + 1f);
            float top = base - h * (.24f + .18f * (float) Math.abs(Math.sin(time * 2.2f + i)) + beat * .12f);
            path.reset();
            path.moveTo(x - dp(16), base);
            path.cubicTo(x - dp(25), base - dp(30), x + dp(8), top + dp(24), x, top);
            path.cubicTo(x + dp(22), top + dp(25), x + dp(27), base - dp(29), x + dp(16), base);
            path.close();
            paint.setColor(alpha(i % 2 == 0 ? spec.primary : spec.secondary, 74 + i * 14));
            canvas.drawPath(path, paint);
            stroke.setStrokeWidth(dp(1.3f));
            stroke.setColor(alpha(spec.accent, 170));
            canvas.drawPath(path, stroke);
        }
    }

    private void drawWater(Canvas canvas, Skin.Spec spec, int w, int h, float time, float beat) {
        int waves = 3 + spec.variant;
        for (int wave = 0; wave < waves; wave++) {
            float base = h * (.28f + wave * .15f);
            path.reset();
            path.moveTo(-dp(10), base);
            for (float x = 0; x <= w + dp(10); x += dp(8)) {
                float y = base + (float) Math.sin(x / dp(26) + time * (1.3f + wave * .1f)) * dp(6 + beat * 12);
                path.lineTo(x, y);
            }
            stroke.setStrokeWidth(dp(1.2f + wave * .35f));
            stroke.setColor(alpha(wave % 2 == 0 ? spec.primary : spec.secondary, 170 - wave * 13));
            canvas.drawPath(path, stroke);
        }
        for (int i = 0; i < 4 + spec.variant; i++) {
            float x = ((i * 53 + time * 16) % (w + dp(20))) - dp(10);
            float y = h * (.18f + (i % 3) * .2f);
            paint.setColor(alpha(spec.accent, 145));
            canvas.drawCircle(x, y, dp(1.8f + (i % 2)), paint);
        }
    }

    private void drawIce(Canvas canvas, Skin.Spec spec, int w, int h, float time, float beat) {
        float cx = w * .5f;
        float cy = h * .5f;
        float radius = Math.min(w, h) * (.33f + beat * .08f);
        stroke.setStrokeWidth(dp(1.5f));
        for (int arm = 0; arm < 6; arm++) {
            float a = (float) (Math.PI * 2d * arm / 6d + time * .06f);
            float ex = cx + (float) Math.cos(a) * radius;
            float ey = cy + (float) Math.sin(a) * radius;
            stroke.setColor(alpha(spec.primary, 205));
            canvas.drawLine(cx, cy, ex, ey, stroke);
            float bx = cx + (float) Math.cos(a) * radius * .57f;
            float by = cy + (float) Math.sin(a) * radius * .57f;
            float side = (float) (Math.PI / 4d);
            canvas.drawLine(bx, by, bx + (float) Math.cos(a + side) * radius * .25f,
                    by + (float) Math.sin(a + side) * radius * .25f, stroke);
            canvas.drawLine(bx, by, bx + (float) Math.cos(a - side) * radius * .25f,
                    by + (float) Math.sin(a - side) * radius * .25f, stroke);
        }
        paint.setColor(alpha(spec.secondary, 100));
        canvas.drawCircle(cx, cy, radius * .18f, paint);
    }

    private void drawLightning(Canvas canvas, Skin.Spec spec, int w, int h, float time, float beat) {
        int bolts = 1 + spec.variant;
        for (int bolt = 0; bolt < bolts; bolt++) {
            float x = w * (bolt + 1f) / (bolts + 1f);
            float y = h * .13f;
            path.reset();
            path.moveTo(x + (float) Math.sin(time * 4 + bolt) * dp(5), y);
            path.lineTo(x - dp(11), h * .42f);
            path.lineTo(x + dp(5), h * .42f);
            path.lineTo(x - dp(14), h * .82f);
            path.lineTo(x + dp(17), h * .49f);
            path.lineTo(x + dp(1), h * .49f);
            stroke.setStrokeWidth(dp(2f + beat * 2f));
            stroke.setColor(alpha(bolt % 2 == 0 ? spec.primary : spec.accent, 220));
            stroke.setShadowLayer(dp(7), 0, 0, alpha(spec.accent, 160));
            canvas.drawPath(path, stroke);
            stroke.clearShadowLayer();
        }
    }

    private void drawSun(Canvas canvas, Skin.Spec spec, int w, int h, float time, float beat) {
        float cx = w * .5f;
        float cy = h * .5f;
        float radius = Math.min(w, h) * (.18f + beat * .06f);
        paint.setColor(alpha(spec.primary, 115));
        canvas.drawCircle(cx, cy, radius, paint);
        stroke.setStrokeWidth(dp(1.5f));
        int rays = 10 + spec.variant * 3;
        for (int i = 0; i < rays; i++) {
            float a = (float) (time * .22f + Math.PI * 2d * i / rays);
            float in = radius + dp(7);
            float out = radius + dp(18 + (i % 3) * 6);
            stroke.setColor(alpha(i % 2 == 0 ? spec.accent : spec.secondary, 190));
            canvas.drawLine(cx + (float) Math.cos(a) * in, cy + (float) Math.sin(a) * in,
                    cx + (float) Math.cos(a) * out, cy + (float) Math.sin(a) * out, stroke);
        }
    }

    private void drawMoon(Canvas canvas, Skin.Spec spec, int w, int h, float time, float beat) {
        float cx = w * (.48f + (float) Math.sin(time * .2f) * .03f);
        float cy = h * .5f;
        float r = Math.min(w, h) * (.27f + beat * .04f);
        paint.setColor(alpha(spec.primary, 110));
        canvas.drawCircle(cx, cy, r, paint);
        paint.setColor(Color.TRANSPARENT);
        paint.setXfermode(new android.graphics.PorterDuffXfermode(PorterDuff.Mode.CLEAR));
        float shift = new float[]{r * .7f, r * .3f, 0f, -r * .33f}[spec.variant];
        canvas.drawCircle(cx + shift, cy - r * .13f, r * .93f, paint);
        paint.setXfermode(null);
        stroke.setStrokeWidth(dp(1.4f));
        stroke.setColor(alpha(spec.accent, 205));
        canvas.drawCircle(cx, cy, r, stroke);
        for (int i = 0; i < 5; i++) {
            float x = (i * 71 % 233) / 233f * w;
            float y = (i * 47 % 149) / 149f * h;
            paint.setColor(alpha(spec.secondary, 160));
            canvas.drawCircle(x, y, dp(1.1f + i % 2), paint);
        }
    }

    private void drawConstellation(Canvas canvas, Skin.Spec spec, int w, int h, float time) {
        int points = 5 + spec.variant;
        float[] xs = new float[points];
        float[] ys = new float[points];
        for (int i = 0; i < points; i++) {
            xs[i] = w * (.13f + ((i * 47 + spec.variant * 19) % 73) / 100f);
            ys[i] = h * (.16f + ((i * 31 + spec.variant * 11) % 66) / 100f);
        }
        stroke.setStrokeWidth(dp(1));
        for (int i = 0; i < points; i++) {
            int next = (i + 1 + spec.variant % 2) % points;
            stroke.setColor(alpha(spec.primary, 120));
            canvas.drawLine(xs[i], ys[i], xs[next], ys[next], stroke);
            float sparkle = dp(2f + (float) Math.abs(Math.sin(time * 3 + i)) * 2.5f);
            paint.setColor(alpha(i % 2 == 0 ? Color.WHITE : spec.secondary, 220));
            canvas.drawCircle(xs[i], ys[i], sparkle, paint);
        }
    }

    private void drawComets(Canvas canvas, Skin.Spec spec, int w, int h, float time, float beat) {
        int count = 2 + spec.variant;
        stroke.setStrokeCap(Paint.Cap.ROUND);
        for (int i = 0; i < count; i++) {
            float p = (time * (.09f + i * .018f) + i * .27f) % 1f;
            float x = w * (1f - p);
            float y = h * (.18f + ((i * 23) % 60) / 100f + p * .22f);
            float tail = dp(28 + beat * 35);
            stroke.setStrokeWidth(dp(2 + i % 2));
            stroke.setColor(alpha(i % 2 == 0 ? spec.primary : spec.secondary, 180));
            canvas.drawLine(x + tail, y - tail * .32f, x, y, stroke);
            paint.setColor(alpha(Color.WHITE, 240));
            canvas.drawCircle(x, y, dp(2.5f + beat * 2), paint);
        }
    }

    private void drawVinyl(Canvas canvas, Skin.Spec spec, int w, int h, float time, float beat) {
        int disks = 1 + (spec.variant > 1 ? 1 : 0);
        for (int i = 0; i < disks; i++) {
            float cx = w * (.42f + i * .20f);
            float cy = h * .52f;
            float r = Math.min(w, h) * (.29f - i * .035f + beat * .03f);
            paint.setColor(alpha(0xFF11111A, 100));
            canvas.drawCircle(cx, cy, r, paint);
            stroke.setStrokeWidth(dp(1.1f));
            for (int ring = 1; ring < 4; ring++) {
                stroke.setColor(alpha(spec.secondary, 70 + ring * 15));
                canvas.drawCircle(cx, cy, r * ring / 4f, stroke);
            }
            float a = time * (1.3f + i * .3f);
            stroke.setColor(alpha(spec.accent, 195));
            canvas.drawLine(cx, cy, cx + (float) Math.cos(a) * r * .73f, cy + (float) Math.sin(a) * r * .73f, stroke);
            paint.setColor(alpha(spec.primary, 205));
            canvas.drawCircle(cx, cy, r * .2f, paint);
            paint.setColor(alpha(Color.WHITE, 190));
            canvas.drawCircle(cx, cy, dp(2), paint);
        }
    }

    private void drawCassette(Canvas canvas, Skin.Spec spec, int w, int h, float time, float beat) {
        float left = w * .16f;
        float right = w * .84f;
        float top = h * .27f;
        float bottom = h * .73f;
        stroke.setStrokeWidth(dp(1.8f));
        stroke.setColor(alpha(spec.primary, 205));
        rect.set(left, top, right, bottom);
        canvas.drawRoundRect(rect, dp(13), dp(13), stroke);
        stroke.setColor(alpha(spec.secondary, 145));
        canvas.drawLine(left + dp(13), h * .49f, right - dp(13), h * .49f, stroke);
        float[] wheels = new float[]{w * .34f, w * .66f};
        for (float cx : wheels) {
            float r = dp(13 + beat * 4);
            stroke.setColor(alpha(spec.accent, 210));
            canvas.drawCircle(cx, h * .51f, r, stroke);
            for (int s = 0; s < 4 + spec.variant; s++) {
                float a = time * 2.4f + s * (float) Math.PI * 2 / (4 + spec.variant);
                canvas.drawLine(cx, h * .51f, cx + (float) Math.cos(a) * r * .72f,
                        h * .51f + (float) Math.sin(a) * r * .72f, stroke);
            }
        }
        path.reset();
        path.moveTo(w * .42f, bottom - dp(7)); path.lineTo(w * .58f, bottom - dp(7));
        path.lineTo(w * .62f, bottom - dp(18)); path.lineTo(w * .38f, bottom - dp(18)); path.close();
        paint.setColor(alpha(spec.secondary, 100));
        canvas.drawPath(path, paint);
    }

    private void drawSynthwave(Canvas canvas, Skin.Spec spec, int w, int h, float time, float beat) {
        float horizon = h * (.58f + spec.variant * .035f);
        stroke.setStrokeWidth(dp(1));
        for (int i = 0; i < 8; i++) {
            float y = horizon + i * i * h * .008f;
            stroke.setColor(alpha(i % 2 == 0 ? spec.primary : spec.secondary, 90));
            canvas.drawLine(0, y, w, y, stroke);
        }
        for (int i = -5; i <= 5; i++) {
            stroke.setColor(alpha(spec.accent, 85));
            canvas.drawLine(w * .5f, horizon, w * (.5f + i * .19f), h, stroke);
        }
        path.reset();
        path.moveTo(0, horizon);
        for (float x = 0; x <= w; x += dp(7)) {
            float y = horizon - (float) Math.abs(Math.sin(x / dp(31) + time * 1.3f)) * (dp(13) + beat * dp(16));
            path.lineTo(x, y);
        }
        stroke.setStrokeWidth(dp(2));
        stroke.setColor(alpha(spec.primary, 220));
        canvas.drawPath(path, stroke);
    }

    private void drawArcade(Canvas canvas, Skin.Spec spec, int w, int h, float time, float beat) {
        float cell = dp(8);
        int cols = Math.max(8, (int) (w / cell));
        int rows = Math.max(5, (int) (h / cell));
        for (int row = 0; row < rows; row++) {
            for (int col = 0; col < cols; col++) {
                float wave = (float) Math.sin(time * 3 + col * .6f + row * .42f);
                if ((col + row + spec.variant) % (3 + spec.variant % 2) == 0 && wave > -.15f) {
                    paint.setColor(alpha((row + col) % 2 == 0 ? spec.primary : spec.secondary, 75 + (int) (wave * 45)));
                    canvas.drawRect(col * cell, row * cell, col * cell + cell * .66f, row * cell + cell * .66f, paint);
                }
            }
        }
        paint.setColor(alpha(spec.accent, 180));
        float px = w * (.48f + (float) Math.sin(time * 1.7f) * .18f);
        float py = h * (.54f + (float) Math.cos(time * 1.3f) * .17f);
        canvas.drawRect(px - cell, py - cell, px + cell, py + cell, paint);
        canvas.drawRect(px - cell * 1.6f, py, px + cell * 1.6f, py + cell, paint);
    }

    private void drawSakura(Canvas canvas, Skin.Spec spec, int w, int h, float time, float beat) {
        int blossoms = 5 + spec.variant * 2;
        for (int i = 0; i < blossoms; i++) {
            float x = ((i * 43 + time * (11 + i % 3 * 4)) % (w + dp(25))) - dp(12);
            float y = ((i * 71 + time * (15 + i % 4 * 3)) % (h + dp(25))) - dp(12);
            float size = dp(4 + i % 3 + beat * 2);
            drawFlower(canvas, x, y, size, time * .6f + i, i % 2 == 0 ? spec.primary : spec.secondary);
        }
        stroke.setStrokeWidth(dp(1.2f));
        stroke.setColor(alpha(spec.accent, 95));
        path.reset(); path.moveTo(0, h * .2f); path.cubicTo(w * .3f, h * .38f, w * .72f, h * .04f, w, h * .23f);
        canvas.drawPath(path, stroke);
    }

    private void drawLotus(Canvas canvas, Skin.Spec spec, int w, int h, float time, float beat) {
        float cx = w * .5f;
        float cy = h * (.6f + (float) Math.sin(time * 1.4f) * .02f);
        int petals = 8 + spec.variant * 2;
        for (int i = 0; i < petals; i++) {
            float a = (float) (Math.PI * 2d * i / petals + time * .12f);
            canvas.save();
            canvas.rotate((float) Math.toDegrees(a), cx, cy);
            rect.set(cx - dp(7), cy - dp(37) - beat * dp(7), cx + dp(7), cy);
            paint.setColor(alpha(i % 2 == 0 ? spec.primary : spec.secondary, 85 + (i % 3) * 25));
            canvas.drawOval(rect, paint);
            canvas.restore();
        }
        paint.setColor(alpha(spec.accent, 180));
        canvas.drawCircle(cx, cy, dp(6 + beat * 4), paint);
        stroke.setStrokeWidth(dp(1));
        stroke.setColor(alpha(spec.secondary, 120));
        canvas.drawLine(0, h * .78f, w, h * .78f, stroke);
    }

    private void drawBubbles(Canvas canvas, Skin.Spec spec, int w, int h, float time, float beat) {
        int count = 9 + spec.variant * 3;
        stroke.setStrokeWidth(dp(1.1f));
        for (int i = 0; i < count; i++) {
            float x = (i * 59 % 263) / 263f * w + (float) Math.sin(time + i) * dp(7);
            float y = h - ((time * (18 + i % 4 * 6) + i * 27) % (h + dp(25)));
            float r = dp(3 + i % 4 + beat * 3);
            stroke.setColor(alpha(i % 2 == 0 ? spec.primary : spec.secondary, 135));
            canvas.drawCircle(x, y, r, stroke);
            paint.setColor(alpha(Color.WHITE, 145));
            canvas.drawCircle(x - r * .25f, y - r * .3f, Math.max(dp(.9f), r * .16f), paint);
        }
    }

    private void drawInk(Canvas canvas, Skin.Spec spec, int w, int h, float time, float beat) {
        int strokes = 2 + spec.variant;
        for (int s = 0; s < strokes; s++) {
            float centerY = h * (.25f + s * .16f);
            path.reset();
            path.moveTo(-dp(15), centerY);
            path.cubicTo(w * .22f, centerY - dp(35 + s * 6), w * .58f, centerY + dp(35 + beat * 22), w + dp(15), centerY - dp(10));
            stroke.setStrokeWidth(dp(5 + s * 2));
            stroke.setColor(alpha(s % 2 == 0 ? spec.primary : spec.secondary, 50 + s * 20));
            canvas.drawPath(path, stroke);
            stroke.setStrokeWidth(dp(1.3f));
            stroke.setColor(alpha(spec.accent, 165));
            canvas.drawPath(path, stroke);
        }
        paint.setColor(alpha(spec.primary, 85));
        canvas.drawCircle(w * (.3f + .12f * spec.variant), h * .67f, dp(8 + beat * 7), paint);
    }

    private void drawHologram(Canvas canvas, Skin.Spec spec, int w, int h, float time, float beat) {
        float cx = w * .5f;
        float cy = h * .5f;
        float radius = Math.min(w, h) * (.28f + beat * .04f);
        int sides = 3 + spec.variant;
        for (int layer = 0; layer < 3; layer++) {
            path.reset();
            float r = radius * (1f - layer * .22f);
            for (int i = 0; i < sides; i++) {
                float a = (float) (time * (.35f + layer * .14f) + Math.PI * 2d * i / sides);
                float x = cx + (float) Math.cos(a) * r;
                float y = cy + (float) Math.sin(a) * r * .72f;
                if (i == 0) path.moveTo(x, y); else path.lineTo(x, y);
            }
            path.close();
            stroke.setStrokeWidth(dp(1.1f));
            stroke.setColor(alpha(layer % 2 == 0 ? spec.primary : spec.secondary, 170 - layer * 30));
            canvas.drawPath(path, stroke);
        }
        stroke.setColor(alpha(spec.accent, 105));
        for (int i = -2; i <= 2; i++) canvas.drawLine(cx - radius, cy + i * dp(10), cx + radius, cy + i * dp(10), stroke);
    }

    private void drawEqualizer(Canvas canvas, Skin.Spec spec, int w, int h, float time) {
        switch (barMode(spec.kind)) {
            case BARS_FACET: drawFacetBars(canvas, spec, w, h); break;
            case BARS_WAVE: drawWaveBars(canvas, spec, w, h, time); break;
            case BARS_RADIAL: drawRadialBars(canvas, spec, w, h, time); break;
            case BARS_PIXEL: drawPixelBars(canvas, spec, w, h); break;
            default: drawVerticalBars(canvas, spec, w, h); break;
        }
    }

    private int barMode(int kind) {
        if (kind <= Skin.SPADES || (kind >= Skin.RUBY && kind <= Skin.AMETHYST)) return BARS_FACET;
        if (kind >= Skin.FIRE && kind <= Skin.LIGHTNING) return BARS_WAVE;
        if ((kind >= Skin.SUN && kind <= Skin.COMET) || kind == Skin.VINYL || kind == Skin.LOTUS
                || kind == Skin.BUBBLES || kind == Skin.HOLOGRAM) return BARS_RADIAL;
        if (kind == Skin.CASSETTE || kind == Skin.ARCADE) return BARS_PIXEL;
        return BARS_VERTICAL;
    }

    private void drawVerticalBars(Canvas canvas, Skin.Spec spec, int w, int h) {
        float gap = dp(3);
        float width = (w - dp(24) - gap * (shown.length - 1)) / shown.length;
        float base = h - dp(10);
        float max = h * .57f;
        for (int i = 0; i < shown.length; i++) {
            float bar = max * (.14f + shown[i] * .86f);
            float x = dp(12) + i * (width + gap);
            float y = base - bar;
            paint.setColor(alpha(i % 3 == 0 ? spec.accent : spec.primary, 205));
            paint.setShadowLayer(dp(5), 0, 0, alpha(spec.primary, 120));
            canvas.drawRoundRect(x, y, x + width, base, width / 2f, width / 2f, paint);
            paint.clearShadowLayer();
        }
    }

    private void drawFacetBars(Canvas canvas, Skin.Spec spec, int w, int h) {
        float cx = w * .5f;
        float bottom = h * .87f;
        float unit = w / (shown.length + 3f);
        for (int i = 0; i < shown.length; i++) {
            float x = unit * (i + 1.5f);
            float high = h * (.10f + shown[i] * .38f);
            path.reset();
            path.moveTo(x, bottom);
            path.lineTo(x + unit * .40f, bottom - high * .5f);
            path.lineTo(x, bottom - high);
            path.lineTo(x - unit * .40f, bottom - high * .5f);
            path.close();
            paint.setColor(alpha(i % 2 == 0 ? spec.primary : spec.secondary, 145));
            canvas.drawPath(path, paint);
            stroke.setStrokeWidth(dp(1));
            stroke.setColor(alpha(spec.accent, 190));
            canvas.drawPath(path, stroke);
            stroke.setColor(alpha(spec.secondary, 100));
            canvas.drawLine(x, bottom, cx, h * .5f, stroke);
        }
    }

    private void drawWaveBars(Canvas canvas, Skin.Spec spec, int w, int h, float time) {
        float gap = dp(2);
        float barWidth = (w - dp(20) - gap * (shown.length - 1)) / shown.length;
        for (int i = 0; i < shown.length; i++) {
            float x = dp(10) + i * (barWidth + gap);
            float base = h * (.72f + (float) Math.sin(i * .55f + time * .8f) * .08f);
            float bar = h * (.09f + shown[i] * .42f);
            path.reset();
            path.moveTo(x, base);
            path.cubicTo(x + barWidth * .2f, base - bar * .4f, x + barWidth * .75f, base - bar,
                    x + barWidth, base - bar);
            path.lineTo(x + barWidth, base);
            path.close();
            paint.setColor(alpha(i % 2 == 0 ? spec.primary : spec.secondary, 145));
            canvas.drawPath(path, paint);
            stroke.setStrokeWidth(dp(1.1f));
            stroke.setColor(alpha(spec.accent, 180));
            canvas.drawPath(path, stroke);
        }
    }

    private void drawRadialBars(Canvas canvas, Skin.Spec spec, int w, int h, float time) {
        float cx = w * .5f;
        float cy = h * .5f;
        float radius = Math.min(w, h) * .19f;
        for (int i = 0; i < shown.length; i++) {
            float a = (float) (Math.PI * 2d * i / shown.length + time * .1f);
            float outer = radius + h * (.08f + shown[i] * .24f);
            stroke.setStrokeWidth(dp(2.1f));
            stroke.setColor(alpha(i % 3 == 0 ? spec.accent : spec.primary, 205));
            stroke.setShadowLayer(dp(4), 0, 0, alpha(spec.primary, 100));
            canvas.drawLine(cx + (float) Math.cos(a) * radius, cy + (float) Math.sin(a) * radius,
                    cx + (float) Math.cos(a) * outer, cy + (float) Math.sin(a) * outer, stroke);
            stroke.clearShadowLayer();
        }
    }

    private void drawPixelBars(Canvas canvas, Skin.Spec spec, int w, int h) {
        float size = dp(5);
        float gap = dp(2);
        float xStep = (w - dp(18)) / shown.length;
        float base = h - dp(11);
        for (int i = 0; i < shown.length; i++) {
            int segments = 1 + (int) (shown[i] * 8);
            for (int s = 0; s < segments; s++) {
                paint.setColor(alpha((s + i) % 2 == 0 ? spec.primary : spec.accent, 165 + s * 10));
                float x = dp(9) + i * xStep;
                float y = base - (s + 1) * (size + gap);
                canvas.drawRect(x, y, x + Math.max(dp(3), xStep - gap), y + size, paint);
            }
        }
    }

    private void drawSuit(Canvas canvas, int suit, float x, float y, float size, Paint p) {
        path.reset();
        if (suit == 0) { // heart
            path.moveTo(x, y + size * .9f);
            path.cubicTo(x - size * 1.25f, y + size * .1f, x - size * .64f, y - size * .78f, x, y - size * .2f);
            path.cubicTo(x + size * .64f, y - size * .78f, x + size * 1.25f, y + size * .1f, x, y + size * .9f);
        } else if (suit == 1) { // diamond
            path.moveTo(x, y - size); path.lineTo(x + size * .72f, y); path.lineTo(x, y + size); path.lineTo(x - size * .72f, y); path.close();
        } else if (suit == 2) { // club
            canvas.drawCircle(x, y - size * .30f, size * .48f, p);
            canvas.drawCircle(x - size * .43f, y + size * .20f, size * .44f, p);
            canvas.drawCircle(x + size * .43f, y + size * .20f, size * .44f, p);
            path.moveTo(x - size * .22f, y + size * .74f); path.lineTo(x + size * .22f, y + size * .74f);
            path.lineTo(x + size * .13f, y + size * .25f); path.lineTo(x - size * .13f, y + size * .25f); path.close();
        } else { // spade
            path.moveTo(x, y - size);
            path.cubicTo(x - size * 1.15f, y - size * .05f, x - size * .68f, y + size * .48f, x, y + size * .24f);
            path.cubicTo(x + size * .68f, y + size * .48f, x + size * 1.15f, y - size * .05f, x, y - size);
            canvas.drawPath(path, p);
            path.reset(); path.moveTo(x - size * .22f, y + size * .78f); path.lineTo(x + size * .22f, y + size * .78f);
            path.lineTo(x + size * .12f, y + size * .16f); path.lineTo(x - size * .12f, y + size * .16f); path.close();
        }
        canvas.drawPath(path, p);
    }

    private void drawFlower(Canvas canvas, float x, float y, float size, float rotation, int color) {
        for (int petal = 0; petal < 5; petal++) {
            canvas.save();
            canvas.rotate(rotation * 40 + petal * 72, x, y);
            rect.set(x - size * .36f, y - size, x + size * .36f, y + size * .04f);
            paint.setColor(alpha(color, 130));
            canvas.drawOval(rect, paint);
            canvas.restore();
        }
        paint.setColor(alpha(0xFFFFE2A1, 210));
        canvas.drawCircle(x, y, size * .20f, paint);
    }

    private float average() {
        float sum = 0f;
        for (float value : shown) sum += value;
        return sum / shown.length;
    }

    private static int alpha(int color, int alpha) {
        return Color.argb(Math.max(0, Math.min(255, alpha)), Color.red(color), Color.green(color), Color.blue(color));
    }

    private static float clamp(float value, float min, float max) {
        return Math.max(min, Math.min(max, value));
    }

    @Override
    public boolean onTouchEvent(MotionEvent event) {
        // Gallery previews must not consume the card's click target.
        if (preview) return false;
        if (dragCallback == null) return super.onTouchEvent(event);
        scaleDetector.onTouchEvent(event);
        switch (event.getActionMasked()) {
            case MotionEvent.ACTION_DOWN:
                touchActive = true;
                moved = false;
                resizing = false;
                longPressed = false;
                downX = event.getX();
                downY = event.getY();
                downRawX = event.getRawX();
                downRawY = event.getRawY();
                postDelayed(longPress, ViewConfiguration.getLongPressTimeout());
                return true;
            case MotionEvent.ACTION_POINTER_DOWN:
                resizing = true;
                removeCallbacks(longPress);
                return true;
            case MotionEvent.ACTION_MOVE:
                if (!resizing && !longPressed) {
                    float dx = event.getRawX() - downRawX;
                    float dy = event.getRawY() - downRawY;
                    if (!moved && Math.hypot(event.getX() - downX, event.getY() - downY) > touchSlop) {
                        moved = true;
                        removeCallbacks(longPress);
                    }
                    if (moved) {
                        dragCallback.onDrag(dx, dy);
                        downRawX = event.getRawX();
                        downRawY = event.getRawY();
                    }
                }
                return true;
            case MotionEvent.ACTION_UP:
            case MotionEvent.ACTION_CANCEL:
                touchActive = false;
                removeCallbacks(longPress);
                resizing = false;
                return true;
            default:
                return true;
        }
    }

    @Override
    public boolean performLongClick() {
        super.performLongClick();
        return true;
    }
}
