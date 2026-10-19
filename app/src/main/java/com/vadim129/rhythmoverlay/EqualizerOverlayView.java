package com.vadim129.rhythmoverlay;

import android.content.Context;
import android.graphics.Bitmap;
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
 * Transparent audio-reactive overlay. It renders real equalizer layouts only: bars, mirrors,
 * LEDs, dots, waves, circles, orbits, tunnels, particles, and beat-driven dancer scenes.
 */
public class EqualizerOverlayView extends View {
    public interface DragCallback {
        void onDrag(float dx, float dy);
        void onResize(float scaleFactor);
        void onClose();
        void onOpenSettings();
    }

    private static final int CONTROL_NONE = 0;
    private static final int CONTROL_SETTINGS = 1;
    private static final int CONTROL_CLOSE = 2;

    private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG | Paint.FILTER_BITMAP_FLAG);
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
    private int controlTarget;
    private boolean controlsVisible;
    private float smoothedBeat;
    private float lastBass;
    private long startedAt = SystemClock.elapsedRealtime();
    private long lastDanceStep;
    private int danceFrame;
    private int dancePack = -1;

    private final Runnable longPress = new Runnable() {
        @Override public void run() {
            if (touchActive && !moved && !resizing && !preview && dragCallback != null) {
                longPressed = true;
                showControls();
                performLongClick();
            }
        }
    };

    private final Runnable hideControls = new Runnable() {
        @Override public void run() {
            controlsVisible = false;
            invalidate();
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
        stroke.setStrokeJoin(Paint.Join.ROUND);
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
                dragCallback.onResize(clamp(detector.getScaleFactor(), .90f, 1.12f));
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
        int width = getWidth();
        int height = getHeight();
        if (width < 2 || height < 2) return;

        // There is no card/background layer in the overlay — only the animated equalizer pixels.
        canvas.drawColor(Color.TRANSPARENT, PorterDuff.Mode.CLEAR);
        Skin.Spec spec = skinId == null ? Skin.selected(getContext()) : Skin.byId(skinId);
        long now = SystemClock.elapsedRealtime();
        float time = (now - startedAt) / 1000f;
        updateLevels(time);
        float beat = smoothedBeat;

        switch (spec.style) {
            case Skin.LINEAR: drawLinear(canvas, spec, width, height, beat); break;
            case Skin.MIRROR: drawMirror(canvas, spec, width, height, beat); break;
            case Skin.LED: drawLed(canvas, spec, width, height, beat); break;
            case Skin.DOTS: drawDots(canvas, spec, width, height, time, beat); break;
            case Skin.WAVE: drawWave(canvas, spec, width, height, time, beat); break;
            case Skin.CIRCULAR: drawCircular(canvas, spec, width, height, time, beat, false); break;
            case Skin.ORBIT: drawOrbit(canvas, spec, width, height, time, beat); break;
            case Skin.TUNNEL: drawTunnel(canvas, spec, width, height, time, beat); break;
            case Skin.PARTICLES: drawParticles(canvas, spec, width, height, time, beat); break;
            case Skin.DANCER: drawDancer(canvas, spec, width, height, now, time, beat); break;
            default: drawLinear(canvas, spec, width, height, beat); break;
        }
        if (controlsVisible && !preview) drawEditControls(canvas, width, height);
        postInvalidateDelayed(preview ? 80L : 33L);
    }

    private void updateLevels(float time) {
        boolean live = !preview && AudioLevels.isFresh();
        float[] values = AudioLevels.snapshot();
        float sensitivity = Skin.sensitivity(getContext()) / 100f;
        for (int i = 0; i < shown.length; i++) {
            float target;
            if (live) {
                target = clamp(values[i] * sensitivity, 0f, 1f);
            } else {
                float rhythm = (float) ((Math.sin(time * (2.15f + i * .11f) + i * .68f) + 1d) * .5d);
                target = .10f + rhythm * .22f + (i < 4 ? .06f : 0f);
            }
            shown[i] += (target - shown[i]) * (live ? .34f : .11f);
        }
        float bass = (shown[0] + shown[1] + shown[2] + shown[3]) * .25f;
        float average = 0f;
        for (float value : shown) average += value;
        average /= shown.length;
        float transient = Math.max(0f, bass - lastBass) * 1.8f;
        lastBass += (bass - lastBass) * .22f;
        float targetBeat = clamp(average * .56f + bass * .44f + transient, 0f, 1f);
        smoothedBeat += (targetBeat - smoothedBeat) * .30f;
    }

    private void drawLinear(Canvas canvas, Skin.Spec spec, int w, int h, float beat) {
        int count = shown.length;
        float margin = dp(10 + (spec.variant % 3) * 3);
        float gap = dp(spec.variant % 2 == 0 ? 3f : 1.6f);
        float available = w - margin * 2f - gap * (count - 1);
        float barWidth = Math.max(dp(1.5f), available / count);
        float baseline = h - dp(10 + (spec.variant % 3) * 5);
        float maximum = h * (.50f + (spec.variant % 4) * .045f);
        for (int i = 0; i < count; i++) {
            float level = shown[i];
            float barHeight = maximum * (.10f + level * .90f);
            float x = margin + i * (barWidth + gap);
            float y = baseline - barHeight;
            int color = bandColor(spec, i, count);
            paint.setColor(alpha(color, 225));
            if (spec.variant == 1 || spec.variant == 4) {
                stroke.setStrokeWidth(Math.max(dp(1f), barWidth));
                stroke.setColor(alpha(color, 220));
                stroke.setShadowLayer(dp(5), 0, 0, alpha(color, 115));
                canvas.drawLine(x + barWidth / 2f, baseline, x + barWidth / 2f, y, stroke);
                stroke.clearShadowLayer();
            } else if (spec.variant == 2 || spec.variant == 6) {
                canvas.drawRect(x, y, x + barWidth, baseline, paint);
            } else {
                float radius = Math.min(barWidth * .5f, dp(5));
                canvas.drawRoundRect(x, y, x + barWidth, baseline, radius, radius, paint);
            }
            if (spec.variant == 3 || spec.variant == 5 || spec.variant == 8) {
                paint.setColor(alpha(spec.accent, 190));
                float cap = Math.max(dp(1.4f), barWidth * .18f);
                canvas.drawRoundRect(x, Math.max(dp(4), y - dp(4)), x + barWidth, Math.max(dp(4), y - dp(4)) + cap,
                        cap, cap, paint);
            }
        }
        if (spec.variant == 7 || spec.variant == 9) {
            stroke.setStrokeWidth(dp(1));
            stroke.setColor(alpha(spec.secondary, 95));
            canvas.drawLine(margin, baseline + dp(4), w - margin, baseline + dp(4), stroke);
        }
    }

    private void drawMirror(Canvas canvas, Skin.Spec spec, int w, int h, float beat) {
        int count = shown.length;
        float margin = dp(10);
        float gap = dp(2.2f);
        float width = (w - margin * 2f - gap * (count - 1)) / count;
        float center = h * (.48f + (spec.variant % 3 - 1) * .035f);
        float max = Math.min(h * .42f, h * (.20f + beat * .05f));
        for (int i = 0; i < count; i++) {
            float extent = max * (.13f + shown[i] * .87f);
            float x = margin + i * (width + gap);
            int color = bandColor(spec, i, count);
            paint.setColor(alpha(color, 215));
            float radius = Math.min(width * .45f, dp(4));
            if (spec.variant == 2 || spec.variant == 7) {
                canvas.drawRect(x, center - extent, x + width, center - dp(1), paint);
                canvas.drawRect(x, center + dp(1), x + width, center + extent, paint);
            } else {
                canvas.drawRoundRect(x, center - extent, x + width, center - dp(1), radius, radius, paint);
                canvas.drawRoundRect(x, center + dp(1), x + width, center + extent, radius, radius, paint);
            }
            if (spec.variant == 1 || spec.variant == 4 || spec.variant == 8) {
                stroke.setStrokeWidth(dp(1));
                stroke.setColor(alpha(spec.accent, 120));
                canvas.drawLine(x + width * .5f, center - extent - dp(4), x + width * .5f, center + extent + dp(4), stroke);
            }
        }
        stroke.setStrokeWidth(dp(spec.variant == 5 ? 2f : 1f));
        stroke.setColor(alpha(spec.secondary, 115));
        canvas.drawLine(margin, center, w - margin, center, stroke);
    }

    private void drawLed(Canvas canvas, Skin.Spec spec, int w, int h, float beat) {
        int count = shown.length;
        float margin = dp(11);
        float colWidth = (w - margin * 2f) / count;
        int segments = 7 + spec.variant;
        float gap = dp(spec.variant % 2 == 0 ? 2f : 1f);
        float segmentHeight = (h * .64f - gap * (segments - 1)) / segments;
        float bottom = h - dp(10);
        for (int i = 0; i < count; i++) {
            int lit = Math.max(1, (int) Math.ceil(shown[i] * segments));
            float x = margin + i * colWidth + gap * .5f;
            float cellWidth = Math.max(dp(2), colWidth - gap);
            for (int s = 0; s < segments; s++) {
                float y = bottom - (s + 1) * segmentHeight - s * gap;
                boolean on = s < lit;
                int color = bandColor(spec, i + s, count + segments);
                paint.setColor(alpha(color, on ? 230 : 37));
                if (spec.variant == 1 || spec.variant == 6) {
                    canvas.drawCircle(x + cellWidth / 2f, y + segmentHeight / 2f, Math.min(cellWidth, segmentHeight) * .34f, paint);
                } else {
                    float radius = spec.variant == 3 || spec.variant == 8 ? dp(1f) : segmentHeight * .22f;
                    canvas.drawRoundRect(x, y, x + cellWidth, y + segmentHeight, radius, radius, paint);
                }
            }
        }
    }

    private void drawDots(Canvas canvas, Skin.Spec spec, int w, int h, float time, float beat) {
        int columns = shown.length;
        int rows = 8 + spec.variant % 3;
        float margin = dp(11);
        float stepX = (w - margin * 2f) / columns;
        float stepY = (h * .62f) / rows;
        float bottom = h - dp(10);
        for (int i = 0; i < columns; i++) {
            int lit = Math.max(1, (int) (shown[i] * rows));
            for (int row = 0; row < rows; row++) {
                float x = margin + i * stepX + stepX * .5f;
                float y = bottom - row * stepY;
                boolean on = row < lit;
                float radius = dp(1.4f + (spec.variant % 3) * .42f);
                if (spec.variant == 4 || spec.variant == 9) radius *= 1f + .22f * (float) Math.sin(time * 3f + i + row);
                paint.setColor(alpha(bandColor(spec, i + row, columns + rows), on ? 225 : 35));
                if (spec.variant == 2 || spec.variant == 6) {
                    canvas.drawRect(x - radius, y - radius, x + radius, y + radius, paint);
                } else {
                    canvas.drawCircle(x, y, radius, paint);
                }
            }
        }
    }

    private void drawWave(Canvas canvas, Skin.Spec spec, int w, int h, float time, float beat) {
        int layers = 1 + spec.variant % 4;
        for (int layer = layers - 1; layer >= 0; layer--) {
            float middle = h * (.5f + (layer - (layers - 1) * .5f) * .08f);
            float amplitude = h * (.12f + .035f * (spec.variant % 4) + beat * .08f) * (1f - layer * .12f);
            path.reset();
            for (int x = 0; x <= w; x += Math.max(2, (int) dp(4))) {
                float normalized = x / (float) w * (shown.length - 1);
                int index = Math.min(shown.length - 1, (int) normalized);
                float local = shown[index];
                float y = middle + (float) Math.sin(x / dp(18 + spec.variant * 2) + time * (2.0f + layer * .35f))
                        * amplitude * (.20f + local * .95f);
                if (x == 0) path.moveTo(x, y); else path.lineTo(x, y);
            }
            stroke.setStrokeWidth(dp(layer == 0 ? 2.4f : 1.1f));
            stroke.setColor(alpha(layer % 2 == 0 ? spec.primary : spec.secondary, 220 - layer * 35));
            stroke.setShadowLayer(layer == 0 ? dp(5) : 0, 0, 0, alpha(spec.primary, 100));
            canvas.drawPath(path, stroke);
            stroke.clearShadowLayer();
        }
        if (spec.variant == 2 || spec.variant == 7) {
            paint.setColor(alpha(spec.accent, 80));
            canvas.drawCircle(w * .5f, h * .5f, dp(5 + beat * 14), paint);
        }
    }

    private void drawCircular(Canvas canvas, Skin.Spec spec, int w, int h, float time, float beat, boolean behindDancer) {
        float cx = w * .5f;
        float cy = h * .5f;
        float base = Math.min(w, h) * (behindDancer ? .27f : .21f);
        int count = spec.variant == 6 ? 32 : shown.length * 2;
        float rotation = time * (spec.variant % 2 == 0 ? .10f : -.10f);
        for (int i = 0; i < count; i++) {
            float a = (float) (Math.PI * 2d * i / count + rotation);
            float local = shown[(i * shown.length / count) % shown.length];
            float length = Math.min(w, h) * (.055f + local * (.16f + spec.variant % 3 * .025f));
            float inner = base + (spec.variant == 3 ? (i % 2) * dp(4) : 0);
            stroke.setStrokeWidth(dp(spec.variant == 4 || spec.variant == 9 ? 1.2f : 2.2f));
            int color = bandColor(spec, i, count);
            stroke.setColor(alpha(color, 220));
            if (spec.variant == 5 || spec.variant == 8) stroke.setShadowLayer(dp(5), 0, 0, alpha(color, 120));
            canvas.drawLine(cx + (float) Math.cos(a) * inner, cy + (float) Math.sin(a) * inner,
                    cx + (float) Math.cos(a) * (inner + length), cy + (float) Math.sin(a) * (inner + length), stroke);
            stroke.clearShadowLayer();
        }
        if (!behindDancer) {
            stroke.setStrokeWidth(dp(1));
            stroke.setColor(alpha(spec.secondary, 130));
            canvas.drawCircle(cx, cy, base - dp(6), stroke);
            if (spec.variant == 1 || spec.variant == 7) {
                paint.setColor(alpha(spec.primary, 75 + (int) (beat * 80)));
                canvas.drawCircle(cx, cy, base * .32f + beat * dp(6), paint);
            }
        }
    }

    private void drawOrbit(Canvas canvas, Skin.Spec spec, int w, int h, float time, float beat) {
        float cx = w * .5f;
        float cy = h * .5f;
        float base = Math.min(w, h) * .16f;
        int rings = 2 + spec.variant % 4;
        for (int ring = 0; ring < rings; ring++) {
            float radius = base + ring * dp(10 + spec.variant);
            stroke.setStrokeWidth(dp(ring == 0 ? 2f : 1f));
            stroke.setColor(alpha(ring % 2 == 0 ? spec.primary : spec.secondary, 190 - ring * 20));
            canvas.drawCircle(cx, cy, radius + beat * dp(3 + ring), stroke);
            int satellites = 1 + (ring + spec.variant) % 3;
            for (int s = 0; s < satellites; s++) {
                float a = time * (1.2f + ring * .28f) + (float) Math.PI * 2f * s / satellites * (ring % 2 == 0 ? 1f : -1f);
                float x = cx + (float) Math.cos(a) * radius;
                float y = cy + (float) Math.sin(a) * radius;
                paint.setColor(alpha(spec.accent, 210));
                canvas.drawCircle(x, y, dp(2 + beat * 2), paint);
            }
        }
        paint.setColor(alpha(spec.primary, 85 + (int) (beat * 100)));
        paint.setShadowLayer(dp(9), 0, 0, alpha(spec.primary, 140));
        canvas.drawCircle(cx, cy, base * (.56f + beat * .22f), paint);
        paint.clearShadowLayer();
    }

    private void drawTunnel(Canvas canvas, Skin.Spec spec, int w, int h, float time, float beat) {
        float cx = w * .5f;
        float cy = h * .5f;
        int frames = 5 + spec.variant % 4;
        for (int frame = frames; frame >= 1; frame--) {
            float depth = frame / (float) frames;
            float wave = shown[(frame * 2 + spec.variant) % shown.length];
            float halfW = w * (.08f + depth * .44f) * (1f + wave * .12f);
            float halfH = h * (.06f + depth * .37f) * (1f + beat * .12f);
            stroke.setStrokeWidth(dp(frame == frames ? 1.8f : 1f));
            stroke.setColor(alpha(frame % 2 == 0 ? spec.primary : spec.secondary, 70 + (int) (depth * 130)));
            if (spec.variant == 2 || spec.variant == 7) {
                path.reset();
                path.moveTo(cx, cy - halfH); path.lineTo(cx + halfW, cy); path.lineTo(cx, cy + halfH); path.lineTo(cx - halfW, cy); path.close();
                canvas.drawPath(path, stroke);
            } else {
                rect.set(cx - halfW, cy - halfH, cx + halfW, cy + halfH);
                canvas.drawRoundRect(rect, dp(3 + spec.variant), dp(3 + spec.variant), stroke);
            }
        }
        if (spec.variant == 1 || spec.variant == 5 || spec.variant == 9) {
            stroke.setColor(alpha(spec.accent, 105));
            for (int i = 0; i < shown.length; i += 3) {
                float x = i / (float) shown.length * w;
                canvas.drawLine(cx, cy, x, h, stroke);
            }
        }
    }

    private void drawParticles(Canvas canvas, Skin.Spec spec, int w, int h, float time, float beat) {
        int particles = 40 + spec.variant * 5;
        for (int i = 0; i < particles; i++) {
            int band = i % shown.length;
            float energy = shown[band];
            float x = fractional(i * 0.618f + time * (.022f + band * .0015f)) * w;
            float y = fractional(i * 0.381f - time * (.032f + band * .001f) - energy * .12f) * h;
            float size = dp(.8f + (i % 3) * .55f + energy * (2.8f + beat * 2f));
            int color = bandColor(spec, i, particles);
            paint.setColor(alpha(color, 65 + (int) (energy * 180)));
            if (spec.variant == 1 || spec.variant == 6) {
                canvas.drawRect(x - size, y - size, x + size, y + size, paint);
            } else {
                canvas.drawCircle(x, y, size, paint);
            }
        }
        // A low, readable spectrum anchors the particle field as an actual equalizer.
        float base = h * .82f;
        float step = w / shown.length;
        for (int i = 0; i < shown.length; i++) {
            stroke.setStrokeWidth(dp(1.5f));
            stroke.setColor(alpha(bandColor(spec, i, shown.length), 180));
            canvas.drawLine(i * step + step * .5f, base, i * step + step * .5f,
                    base - h * (.05f + shown[i] * .23f), stroke);
        }
    }

    private void drawDancer(Canvas canvas, Skin.Spec spec, int w, int h, long now, float time, float beat) {
        int pack = Math.min(DancerSprite.PACK_COUNT - 1, spec.variant / 2);
        if (pack != dancePack) {
            dancePack = pack;
            danceFrame = 0;
            lastDanceStep = now;
        }
        long cadence = (long) (330 - beat * 190);
        if (now - lastDanceStep >= cadence || beat > lastBass + .15f) {
            danceFrame = (danceFrame + (beat > .62f ? 2 : 1)) % DancerSprite.FRAMES_PER_PACK;
            lastDanceStep = now;
        }
        // Clean EQ geometry sits behind the dancer; the person itself is a transparent frame sequence.
        if (spec.variant % 2 == 0) drawDancerSideBars(canvas, spec, w, h, beat);
        else drawCircular(canvas, spec, w, h, time, beat, true);

        Bitmap frame = DancerSprite.frame(getContext(), pack, danceFrame);
        if (frame == null) return;
        float maxHeight = h * .93f;
        float ratio = frame.getWidth() / (float) frame.getHeight();
        float targetHeight = Math.min(maxHeight, w * .83f / ratio);
        float targetWidth = targetHeight * ratio;
        float bounce = dp(3 + beat * 15);
        float scale = 1f + beat * .045f;
        float centerX = w * .5f;
        float centerY = h - targetHeight * .47f - bounce;
        canvas.save();
        canvas.scale(scale, scale, centerX, centerY);
        rect.set(centerX - targetWidth * .5f, h - targetHeight - bounce,
                centerX + targetWidth * .5f, h - bounce);
        paint.setAlpha(255);
        canvas.drawBitmap(frame, null, rect, paint);
        canvas.restore();
    }

    private void drawDancerSideBars(Canvas canvas, Skin.Spec spec, int w, int h, float beat) {
        int perSide = 7;
        float base = h - dp(9);
        float max = h * .34f;
        for (int side = 0; side < 2; side++) {
            for (int i = 0; i < perSide; i++) {
                int band = side == 0 ? i : shown.length - 1 - i;
                float x = side == 0 ? dp(7) + i * dp(8) : w - dp(7) - (i + 1) * dp(8);
                float height = max * (.12f + shown[band] * .88f);
                stroke.setStrokeWidth(dp(3));
                stroke.setColor(alpha(bandColor(spec, i + side * perSide, perSide * 2), 215));
                canvas.drawLine(x, base, x, base - height, stroke);
            }
        }
    }

    private void drawEditControls(Canvas canvas, int w, int h) {
        float y = dp(20);
        float gearX = dp(20);
        float closeX = w - dp(20);
        stroke.setStrokeWidth(dp(2));
        stroke.setColor(alpha(Color.WHITE, 230));
        stroke.setShadowLayer(dp(5), 0, 0, alpha(0xFF579BFF, 165));
        canvas.drawCircle(gearX, y, dp(11), stroke);
        canvas.drawCircle(closeX, y, dp(11), stroke);
        for (int i = 0; i < 8; i++) {
            float a = (float) (Math.PI * 2d * i / 8d);
            canvas.drawLine(gearX + (float) Math.cos(a) * dp(7), y + (float) Math.sin(a) * dp(7),
                    gearX + (float) Math.cos(a) * dp(10), y + (float) Math.sin(a) * dp(10), stroke);
        }
        canvas.drawCircle(gearX, y, dp(3), stroke);
        canvas.drawLine(closeX - dp(4), y - dp(4), closeX + dp(4), y + dp(4), stroke);
        canvas.drawLine(closeX + dp(4), y - dp(4), closeX - dp(4), y + dp(4), stroke);
        stroke.clearShadowLayer();
    }

    private int bandColor(Skin.Spec spec, int index, int total) {
        float position = total <= 1 ? 0f : index / (float) (total - 1);
        if (position < .5f) return Skin.mix(spec.primary, spec.secondary, position * 2f);
        return Skin.mix(spec.secondary, spec.accent, (position - .5f) * 2f);
    }

    private void showControls() {
        controlsVisible = true;
        removeCallbacks(hideControls);
        postDelayed(hideControls, 5200L);
        invalidate();
    }

    private boolean inCircle(float x, float y, float cx, float cy) {
        float dx = x - cx;
        float dy = y - cy;
        return dx * dx + dy * dy <= dp(17) * dp(17);
    }

    private static int alpha(int color, int alpha) {
        return Color.argb(Math.max(0, Math.min(255, alpha)), Color.red(color), Color.green(color), Color.blue(color));
    }

    private static float clamp(float value, float min, float max) {
        return Math.max(min, Math.min(max, value));
    }

    private static float fractional(float value) {
        return value - (float) Math.floor(value);
    }

    @Override
    public boolean onTouchEvent(MotionEvent event) {
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
                controlTarget = CONTROL_NONE;
                if (controlsVisible) {
                    if (inCircle(downX, downY, dp(20), dp(20))) controlTarget = CONTROL_SETTINGS;
                    if (inCircle(downX, downY, getWidth() - dp(20), dp(20))) controlTarget = CONTROL_CLOSE;
                }
                if (controlTarget == CONTROL_NONE) postDelayed(longPress, ViewConfiguration.getLongPressTimeout());
                return true;
            case MotionEvent.ACTION_POINTER_DOWN:
                resizing = true;
                removeCallbacks(longPress);
                return true;
            case MotionEvent.ACTION_MOVE:
                if (!resizing && !longPressed && controlTarget == CONTROL_NONE) {
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
                touchActive = false;
                removeCallbacks(longPress);
                if (controlTarget == CONTROL_CLOSE && inCircle(event.getX(), event.getY(), getWidth() - dp(20), dp(20))) {
                    dragCallback.onClose();
                } else if (controlTarget == CONTROL_SETTINGS && inCircle(event.getX(), event.getY(), dp(20), dp(20))) {
                    controlsVisible = false;
                    dragCallback.onOpenSettings();
                }
                controlTarget = CONTROL_NONE;
                resizing = false;
                return true;
            case MotionEvent.ACTION_CANCEL:
                touchActive = false;
                controlTarget = CONTROL_NONE;
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
