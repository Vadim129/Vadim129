package com.vadim129.rhythmoverlay;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.LinearGradient;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.RectF;
import android.graphics.Shader;
import android.os.SystemClock;
import android.view.MotionEvent;
import android.view.View;

/** The movable rectangular visualizer. It contains its own lightweight Canvas skin renderer. */
public class EqualizerOverlayView extends View {
    public interface DragCallback {
        void onDrag(float dx, float dy);
        void onClose();
    }

    private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint stroke = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Path clipPath = new Path();
    private final RectF rect = new RectF();
    private final float[] shown = new float[AudioLevels.BANDS];
    private final float density;
    private final boolean preview;
    private String skinId;
    private DragCallback dragCallback;
    private float downRawX;
    private float downRawY;
    private float downX;
    private float downY;
    private boolean dragging;
    private boolean movedDuringDrag;
    private long startedAt = SystemClock.elapsedRealtime();

    public EqualizerOverlayView(Context context) {
        this(context, null, false);
    }

    public EqualizerOverlayView(Context context, String skinId, boolean preview) {
        super(context);
        this.preview = preview;
        this.skinId = skinId;
        density = getResources().getDisplayMetrics().density;
        paint.setSubpixelText(true);
        stroke.setStyle(Paint.Style.STROKE);
        stroke.setStrokeCap(Paint.Cap.ROUND);
        setLayerType(View.LAYER_TYPE_SOFTWARE, null);
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
        Skin.Spec spec = skinId == null ? Skin.selected(getContext()) : Skin.byId(skinId);
        long now = SystemClock.elapsedRealtime();
        float time = (now - startedAt) / 1000f;
        float[] live = AudioLevels.snapshot();
        boolean liveData = !preview && AudioLevels.isFresh();
        float sensitivity = Skin.sensitivity(getContext()) / 100f;
        for (int i = 0; i < shown.length; i++) {
            float desired;
            if (liveData) {
                desired = Math.min(1f, live[i] * sensitivity);
            } else {
                float wave = (float) ((Math.sin(time * (2.2f + i * .13f) + i * .71f) + 1f) * .5f);
                desired = .12f + .18f * wave + (i % 4 == 0 ? .08f : 0f);
            }
            shown[i] += (desired - shown[i]) * (liveData ? .34f : .10f);
        }

        float radius = dp(preview ? 13 : 17);
        rect.set(0, 0, width, height);
        clipPath.reset();
        clipPath.addRoundRect(rect, radius, radius, Path.Direction.CW);
        canvas.save();
        canvas.clipPath(clipPath);
        drawBackdrop(canvas, spec, width, height, time);
        if (!preview) drawHeader(canvas, spec, width, time);
        boolean hasCharacter = spec.character != Skin.NONE;
        float top = preview ? dp(10) : dp(39);
        float bottom = height - dp(preview ? 10 : 13);
        float left = dp(13);
        float right = hasCharacter ? width * .58f : width - dp(13);
        drawBars(canvas, spec, left, right, top, bottom, time);
        if (hasCharacter) drawCharacter(canvas, spec, width, height, time, average());
        drawFrame(canvas, spec, width, height, radius);
        canvas.restore();
        postInvalidateDelayed(preview ? 70L : 33L);
    }

    private void drawBackdrop(Canvas canvas, Skin.Spec spec, int width, int height, float time) {
        paint.setShader(new LinearGradient(0, 0, width, height, spec.first, spec.second, Shader.TileMode.CLAMP));
        canvas.drawRect(0, 0, width, height, paint);
        paint.setShader(null);

        if ("aurora".equals(spec.id)) {
            for (int i = 0; i < 4; i++) {
                float y = height * (.27f + i * .14f) + (float) Math.sin(time * 1.1f + i) * dp(7);
                stroke.setStrokeWidth(dp(12));
                stroke.setColor(withAlpha(i % 2 == 0 ? 0xFF55F5C1 : 0xFF6AA8FF, 27));
                Path wave = new Path();
                wave.moveTo(-dp(20), y);
                for (int x = 0; x <= width + dp(20); x += dp(14)) {
                    wave.lineTo(x, y + (float) Math.sin(x / dp(32) + time * 1.7f + i) * dp(8));
                }
                canvas.drawPath(wave, stroke);
            }
        } else if ("pixel".equals(spec.id)) {
            paint.setColor(withAlpha(Color.WHITE, 9));
            float cell = dp(12);
            for (float x = 0; x < width; x += cell) canvas.drawRect(x, 0, x + dp(1), height, paint);
            for (float y = 0; y < height; y += cell) canvas.drawRect(0, y, width, y + dp(1), paint);
        } else if ("matrix".equals(spec.id)) {
            paint.setTextSize(dp(8));
            paint.setTypeface(android.graphics.Typeface.MONOSPACE);
            paint.setColor(withAlpha(0xFF91FFB0, 50));
            for (int i = 0; i < 15; i++) {
                float x = dp(7) + i * width / 15f;
                float y = ((time * (22 + i * 2) + i * 29) % (height + dp(25))) - dp(8);
                canvas.drawText(i % 2 == 0 ? "01" : "×", x, y, paint);
            }
        } else if ("cosmic".equals(spec.id)) {
            for (int i = 0; i < 25; i++) {
                float x = (i * 47 % 281) / 281f * width;
                float y = (i * 73 % 167) / 167f * height;
                float r = dp(.8f + (i % 3)) * (.75f + .25f * (float) Math.sin(time * 2 + i));
                paint.setColor(withAlpha(i % 4 == 0 ? 0xFFFFB8F3 : Color.WHITE, 90));
                canvas.drawCircle(x, y, r, paint);
            }
        } else if ("glass".equals(spec.id)) {
            paint.setColor(withAlpha(Color.WHITE, 20));
            canvas.drawCircle(width * .14f, height * .12f, width * .42f, paint);
            paint.setColor(withAlpha(0xFF9CCBFF, 18));
            canvas.drawCircle(width * .86f, height * .89f, width * .34f, paint);
        } else if ("sunset".equals(spec.id)) {
            paint.setColor(withAlpha(0xFFFFD17D, 26));
            canvas.drawCircle(width * .85f, height * .25f, dp(42), paint);
            stroke.setColor(withAlpha(0xFFFFE0A1, 24));
            stroke.setStrokeWidth(dp(1));
            for (int y = 0; y < height; y += dp(10)) canvas.drawLine(0, y, width, y, stroke);
        }
    }

    private void drawHeader(Canvas canvas, Skin.Spec spec, int width, float time) {
        float h = dp(31);
        paint.setColor(withAlpha(0xFF05060B, 125));
        canvas.drawRect(0, 0, width, h, paint);
        paint.setColor(spec.accent);
        float pulse = .75f + .25f * (float) Math.sin(time * 5f);
        canvas.drawCircle(dp(14), dp(15.5f), dp(3.5f) * pulse, paint);
        paint.setColor(Color.WHITE);
        paint.setTextSize(dp(11));
        paint.setTypeface(android.graphics.Typeface.create("sans-serif-medium", android.graphics.Typeface.NORMAL));
        canvas.drawText(spec.title, dp(23), dp(14), paint);
        paint.setTextSize(dp(8));
        paint.setTypeface(android.graphics.Typeface.create("sans-serif", android.graphics.Typeface.NORMAL));
        String state = AudioLevels.status();
        canvas.drawText(ellipsize(state, 28), dp(23), dp(24), paint);
        stroke.setColor(withAlpha(Color.WHITE, 175));
        stroke.setStrokeWidth(dp(1.4f));
        float cx = width - dp(16);
        float cy = dp(15.5f);
        canvas.drawLine(cx - dp(3), cy - dp(3), cx + dp(3), cy + dp(3), stroke);
        canvas.drawLine(cx + dp(3), cy - dp(3), cx - dp(3), cy + dp(3), stroke);
    }

    private void drawBars(Canvas canvas, Skin.Spec spec, float left, float right, float top, float bottom, float time) {
        float fullWidth = Math.max(dp(5), right - left);
        float gap = dp(preview ? 2 : 3);
        float barWidth = Math.max(dp(2), (fullWidth - gap * (shown.length - 1)) / shown.length);
        float maxHeight = Math.max(dp(10), bottom - top);
        boolean pixels = "pixel".equals(spec.id);
        boolean matrix = "matrix".equals(spec.id);
        for (int i = 0; i < shown.length; i++) {
            float x = left + i * (barWidth + gap);
            float ease = .16f + shown[i] * .84f;
            float h = maxHeight * ease;
            float y = bottom - h;
            int color = interpolate(spec.accent, i % 3 == 0 ? Color.WHITE : spec.second, i / (float) shown.length * .38f);
            if ("sunset".equals(spec.id)) color = interpolate(0xFFFFD76B, 0xFFFF5E99, i / (float) shown.length);
            if ("aurora".equals(spec.id)) color = interpolate(0xFF61FFD0, 0xFF77A8FF, i / (float) shown.length);
            if ("neon".equals(spec.id) || "mira".equals(spec.id) || "luna".equals(spec.id)) {
                paint.setShadowLayer(dp(6), 0, 0, withAlpha(spec.accent, 125));
            } else {
                paint.clearShadowLayer();
            }
            if (pixels || matrix) {
                float unit = dp(preview ? 4 : 5);
                int segments = Math.max(1, (int) (h / unit));
                for (int s = 0; s < segments; s++) {
                    float segmentY = bottom - (s + 1) * unit;
                    paint.setColor(withAlpha(color, s == segments - 1 ? 255 : 180));
                    canvas.drawRect(x, segmentY, x + barWidth, segmentY + unit - dp(1), paint);
                }
            } else if ("glass".equals(spec.id)) {
                paint.setShader(new LinearGradient(x, y, x, bottom, withAlpha(Color.WHITE, 240), withAlpha(spec.accent, 125), Shader.TileMode.CLAMP));
                canvas.drawRoundRect(x, y, x + barWidth, bottom, barWidth / 2, barWidth / 2, paint);
                paint.setShader(null);
            } else {
                paint.setColor(color);
                canvas.drawRoundRect(x, y, x + barWidth, bottom, barWidth / 2, barWidth / 2, paint);
            }
            paint.clearShadowLayer();
            // Small falling cap makes quiet changes legible.
            paint.setColor(withAlpha(Color.WHITE, 120));
            float capY = Math.max(top, y - dp(3));
            canvas.drawRoundRect(x, capY, x + barWidth, capY + dp(1.2f), dp(1), dp(1), paint);
        }
        if ("neon".equals(spec.id) || "aurora".equals(spec.id)) {
            stroke.setColor(withAlpha(spec.accent, 90));
            stroke.setStrokeWidth(dp(1));
            canvas.drawLine(left, bottom + dp(2), right, bottom + dp(2), stroke);
        }
    }

    private void drawCharacter(Canvas canvas, Skin.Spec spec, int width, int height, float time, float beat) {
        float cx = width * .79f;
        float baseY = height - dp(13);
        float bounce = dp(2 + 11 * beat) + (float) Math.sin(time * 4.4f) * dp(2);
        canvas.save();
        canvas.translate(cx, -bounce);
        canvas.rotate((float) Math.sin(time * 3.6f) * (4 + beat * 6), 0, baseY - height * .46f);
        if (spec.character == Skin.GIRL) {
            drawDancer(canvas, spec, baseY, time, beat);
        } else if (spec.character == Skin.CAT) {
            drawCat(canvas, spec, baseY, time, beat);
        } else if (spec.character == Skin.FOX) {
            drawFox(canvas, spec, baseY, time, beat);
        } else if (spec.character == Skin.PANDA) {
            drawPanda(canvas, spec, baseY, time, beat);
        } else if (spec.character == Skin.CAPYBARA) {
            drawCapybara(canvas, spec, baseY, time, beat);
        }
        canvas.restore();
    }

    private void drawDancer(Canvas canvas, Skin.Spec spec, float baseY, float time, float beat) {
        float headY = baseY - dp(79);
        float sway = (float) Math.sin(time * 4.2f) * dp(8 + beat * 5);
        int skin = "luna".equals(spec.id) ? 0xFFF0B899 : 0xFFD99A72;
        // back arm and hair
        stroke.setStrokeWidth(dp(5));
        stroke.setColor("luna".equals(spec.id) ? 0xFF6B3B98 : 0xFF241B35);
        canvas.drawLine(dp(-4), headY + dp(27), dp(-29) + sway, headY + dp(47), stroke);
        // legs in a relaxed dance step
        stroke.setColor(0xFF171524);
        stroke.setStrokeWidth(dp(8));
        canvas.drawLine(dp(-5), baseY - dp(30), dp(-13) - sway * .25f, baseY - dp(5), stroke);
        canvas.drawLine(dp(7), baseY - dp(30), dp(20) + sway * .25f, baseY - dp(5), stroke);
        paint.setColor(0xFFF7F7FC);
        canvas.drawRoundRect(dp(-20) - sway * .25f, baseY - dp(8), dp(-7) - sway * .25f, baseY - dp(3), dp(3), dp(3), paint);
        canvas.drawRoundRect(dp(14) + sway * .25f, baseY - dp(8), dp(29) + sway * .25f, baseY - dp(3), dp(3), dp(3), paint);
        // jacket/body
        paint.setColor("luna".equals(spec.id) ? 0xFF9FC9FF : 0xFFFFD36B);
        rect.set(dp(-17), headY + dp(23), dp(17), baseY - dp(28));
        canvas.drawRoundRect(rect, dp(10), dp(10), paint);
        paint.setColor(0xFF1B1930);
        canvas.drawRect(dp(-12), headY + dp(50), dp(12), baseY - dp(31), paint);
        // dancing front arm
        stroke.setStrokeWidth(dp(5));
        stroke.setColor(skin);
        canvas.drawLine(dp(12), headY + dp(32), dp(30) - sway, headY + dp(18), stroke);
        canvas.drawLine(dp(30) - sway, headY + dp(18), dp(25) - sway, headY + dp(4), stroke);
        // hair, head, headphones
        paint.setColor("luna".equals(spec.id) ? 0xFF38204B : 0xFF1A1627);
        canvas.drawCircle(0, headY, dp(18), paint);
        paint.setColor(skin);
        canvas.drawCircle(0, headY + dp(2), dp(13), paint);
        paint.setColor(0xFF12121C);
        stroke.setStrokeWidth(dp(3));
        stroke.setColor(0xFF12121C);
        canvas.drawArc(dp(-15), headY - dp(13), dp(15), headY + dp(14), 195, 150, false, stroke);
        paint.setColor(spec.accent);
        canvas.drawCircle(dp(-14), headY + dp(1), dp(4), paint);
        canvas.drawCircle(dp(14), headY + dp(1), dp(4), paint);
        paint.setColor(0xFF302439);
        canvas.drawCircle(dp(-5), headY + dp(2), dp(1.2f), paint);
        canvas.drawCircle(dp(5), headY + dp(2), dp(1.2f), paint);
        stroke.setStrokeWidth(dp(1));
        canvas.drawLine(dp(-3), headY + dp(9), dp(4), headY + dp(9), stroke);
        // DJ deck
        paint.setColor(withAlpha(0xFF05050A, 190));
        canvas.drawRoundRect(dp(-33), baseY - dp(19), dp(34), baseY, dp(5), dp(5), paint);
        paint.setColor(spec.accent);
        canvas.drawCircle(dp(-14), baseY - dp(10), dp(5 + beat * 2), paint);
        canvas.drawCircle(dp(16), baseY - dp(10), dp(5 + beat * 2), paint);
    }

    private void drawCat(Canvas canvas, Skin.Spec spec, float baseY, float time, float beat) {
        float bob = (float) Math.sin(time * 5f) * dp(3);
        paint.setColor(0xFFBBD9FF);
        canvas.drawOval(dp(-24), baseY - dp(55) + bob, dp(24), baseY - dp(12) + bob, paint);
        Path ears = new Path();
        ears.moveTo(dp(-19), baseY - dp(48) + bob); ears.lineTo(dp(-22), baseY - dp(71) + bob); ears.lineTo(dp(-4), baseY - dp(56) + bob);
        ears.moveTo(dp(5), baseY - dp(56) + bob); ears.lineTo(dp(22), baseY - dp(71) + bob); ears.lineTo(dp(20), baseY - dp(47) + bob);
        canvas.drawPath(ears, paint);
        paint.setColor(0xFF23304D);
        canvas.drawCircle(dp(-8), baseY - dp(45) + bob, dp(2.3f), paint);
        canvas.drawCircle(dp(8), baseY - dp(45) + bob, dp(2.3f), paint);
        paint.setColor(spec.accent);
        canvas.drawCircle(0, baseY - dp(38) + bob, dp(2.6f), paint);
        // paws swing independently with beat
        stroke.setColor(0xFFBBD9FF); stroke.setStrokeWidth(dp(7));
        canvas.drawLine(dp(-17), baseY - dp(30) + bob, dp(-31), baseY - dp(21) - beat * dp(14), stroke);
        canvas.drawLine(dp(17), baseY - dp(30) + bob, dp(30), baseY - dp(22) + beat * dp(13), stroke);
        // legs and tail
        stroke.setStrokeWidth(dp(8));
        canvas.drawLine(dp(-9), baseY - dp(16), dp(-15), baseY - dp(3), stroke);
        canvas.drawLine(dp(9), baseY - dp(16), dp(16), baseY - dp(3), stroke);
        stroke.setStyle(Paint.Style.STROKE); stroke.setStrokeWidth(dp(5));
        Path tail = new Path(); tail.moveTo(dp(21), baseY - dp(27)); tail.cubicTo(dp(44), baseY - dp(43), dp(39), baseY - dp(2), dp(25), baseY - dp(8));
        canvas.drawPath(tail, stroke);
    }

    private void drawFox(Canvas canvas, Skin.Spec spec, float baseY, float time, float beat) {
        float swing = (float) Math.sin(time * 4f) * dp(8);
        paint.setColor(0xFFFF9C45);
        canvas.drawOval(dp(-22), baseY - dp(52), dp(22), baseY - dp(11), paint);
        Path ears = new Path();
        ears.moveTo(dp(-19), baseY - dp(45)); ears.lineTo(dp(-20), baseY - dp(70)); ears.lineTo(dp(-2), baseY - dp(54));
        ears.moveTo(dp(3), baseY - dp(54)); ears.lineTo(dp(21), baseY - dp(70)); ears.lineTo(dp(19), baseY - dp(44));
        canvas.drawPath(ears, paint);
        paint.setColor(0xFFFFE8D3);
        canvas.drawOval(dp(-13), baseY - dp(43), dp(13), baseY - dp(23), paint);
        paint.setColor(0xFF2A1A19);
        canvas.drawCircle(dp(-7), baseY - dp(44), dp(2.2f), paint); canvas.drawCircle(dp(7), baseY - dp(44), dp(2.2f), paint);
        canvas.drawCircle(0, baseY - dp(32), dp(3), paint);
        stroke.setColor(0xFFFF9C45); stroke.setStrokeWidth(dp(7));
        canvas.drawLine(dp(-16), baseY - dp(31), dp(-30), baseY - dp(18) + swing, stroke);
        canvas.drawLine(dp(16), baseY - dp(31), dp(31), baseY - dp(18) - swing, stroke);
        canvas.drawLine(dp(-8), baseY - dp(16), dp(-16), baseY - dp(3), stroke);
        canvas.drawLine(dp(8), baseY - dp(16), dp(17), baseY - dp(3), stroke);
        Path tail = new Path(); tail.moveTo(dp(18), baseY - dp(25)); tail.cubicTo(dp(46), baseY - dp(49), dp(46), baseY - dp(12), dp(24), baseY - dp(11));
        stroke.setStrokeWidth(dp(12)); canvas.drawPath(tail, stroke);
        stroke.setColor(0xFFFFE8D3); stroke.setStrokeWidth(dp(5)); canvas.drawLine(dp(26), baseY - dp(12), dp(31), baseY - dp(14), stroke);
    }

    private void drawPanda(Canvas canvas, Skin.Spec spec, float baseY, float time, float beat) {
        float tilt = (float) Math.sin(time * 4.6f) * dp(4);
        paint.setColor(0xFFF4FFF9);
        canvas.drawOval(dp(-23), baseY - dp(55) + tilt, dp(23), baseY - dp(10) + tilt, paint);
        paint.setColor(0xFF15231F);
        canvas.drawCircle(dp(-15), baseY - dp(57) + tilt, dp(9), paint); canvas.drawCircle(dp(15), baseY - dp(57) + tilt, dp(9), paint);
        canvas.drawOval(dp(-15), baseY - dp(50) + tilt, dp(-3), baseY - dp(37) + tilt, paint);
        canvas.drawOval(dp(3), baseY - dp(50) + tilt, dp(15), baseY - dp(37) + tilt, paint);
        paint.setColor(0xFFFFFFFF);
        canvas.drawCircle(dp(-9), baseY - dp(44) + tilt, dp(2), paint); canvas.drawCircle(dp(9), baseY - dp(44) + tilt, dp(2), paint);
        paint.setColor(spec.accent); canvas.drawCircle(0, baseY - dp(34) + tilt, dp(3), paint);
        stroke.setColor(0xFF15231F); stroke.setStrokeWidth(dp(8));
        canvas.drawLine(dp(-17), baseY - dp(28), dp(-31), baseY - dp(22) - beat * dp(13), stroke);
        canvas.drawLine(dp(17), baseY - dp(28), dp(29), baseY - dp(20) + beat * dp(13), stroke);
        canvas.drawLine(dp(-8), baseY - dp(14), dp(-17), baseY - dp(3), stroke);
        canvas.drawLine(dp(8), baseY - dp(14), dp(17), baseY - dp(3), stroke);
        paint.setColor(spec.accent); canvas.drawRect(dp(-3), baseY - dp(29), dp(3), baseY - dp(16), paint);
    }

    private void drawCapybara(Canvas canvas, Skin.Spec spec, float baseY, float time, float beat) {
        float sway = (float) Math.sin(time * 3.5f) * dp(5);
        paint.setColor(0xFFC99064);
        canvas.drawRoundRect(dp(-28), baseY - dp(52), dp(28), baseY - dp(11), dp(17), dp(17), paint);
        paint.setColor(0xFFB5744B); canvas.drawCircle(dp(-17), baseY - dp(55), dp(7), paint); canvas.drawCircle(dp(17), baseY - dp(55), dp(7), paint);
        paint.setColor(0xFF382720); canvas.drawCircle(dp(-9), baseY - dp(40), dp(2.2f), paint); canvas.drawCircle(dp(9), baseY - dp(40), dp(2.2f), paint);
        paint.setColor(0xFFDFB38E); canvas.drawOval(dp(-13), baseY - dp(35), dp(13), baseY - dp(21), paint);
        paint.setColor(0xFF382720); canvas.drawCircle(dp(-5), baseY - dp(29), dp(1.7f), paint); canvas.drawCircle(dp(5), baseY - dp(29), dp(1.7f), paint);
        stroke.setColor(0xFFC99064); stroke.setStrokeWidth(dp(9));
        canvas.drawLine(dp(-22), baseY - dp(28), dp(-35), baseY - dp(17) + sway, stroke);
        canvas.drawLine(dp(22), baseY - dp(28), dp(34), baseY - dp(17) - sway, stroke);
        canvas.drawLine(dp(-11), baseY - dp(14), dp(-18), baseY - dp(3), stroke);
        canvas.drawLine(dp(11), baseY - dp(14), dp(18), baseY - dp(3), stroke);
        paint.setColor(spec.accent); canvas.drawRoundRect(dp(-17), baseY - dp(18), dp(17), baseY - dp(13), dp(2), dp(2), paint);
    }

    private void drawFrame(Canvas canvas, Skin.Spec spec, int width, int height, float radius) {
        stroke.setStyle(Paint.Style.STROKE);
        stroke.setStrokeWidth(dp(1));
        stroke.setColor(withAlpha(spec.accent, 130));
        rect.set(dp(.5f), dp(.5f), width - dp(.5f), height - dp(.5f));
        canvas.drawRoundRect(rect, radius, radius, stroke);
        stroke.setStyle(Paint.Style.STROKE);
    }

    private float average() {
        float sum = 0f;
        for (float value : shown) sum += value;
        return sum / shown.length;
    }

    private String ellipsize(String value, int max) {
        if (value == null) return "";
        return value.length() > max ? value.substring(0, max - 1) + "…" : value;
    }

    private static int withAlpha(int color, int alpha) {
        return Color.argb(Math.max(0, Math.min(255, alpha)), Color.red(color), Color.green(color), Color.blue(color));
    }

    private static int interpolate(int first, int second, float amount) {
        float t = Math.max(0f, Math.min(1f, amount));
        return Color.rgb((int) (Color.red(first) + (Color.red(second) - Color.red(first)) * t),
                (int) (Color.green(first) + (Color.green(second) - Color.green(first)) * t),
                (int) (Color.blue(first) + (Color.blue(second) - Color.blue(first)) * t));
    }

    @Override
    public boolean onTouchEvent(MotionEvent event) {
        // Let the containing skin card receive touches in gallery previews.
        if (preview) return false;
        if (dragCallback == null) return super.onTouchEvent(event);
        float headerLimit = dp(33);
        switch (event.getActionMasked()) {
            case MotionEvent.ACTION_DOWN:
                downX = event.getX();
                downY = event.getY();
                downRawX = event.getRawX();
                downRawY = event.getRawY();
                dragging = downY <= headerLimit;
                movedDuringDrag = false;
                return true;
            case MotionEvent.ACTION_MOVE:
                if (dragging) {
                    float dx = event.getRawX() - downRawX;
                    float dy = event.getRawY() - downRawY;
                    if (Math.abs(dx) > 0.5f || Math.abs(dy) > 0.5f) {
                        movedDuringDrag = true;
                        dragCallback.onDrag(dx, dy);
                        downRawX = event.getRawX();
                        downRawY = event.getRawY();
                    }
                }
                return true;
            case MotionEvent.ACTION_UP:
                if (downY <= headerLimit && !movedDuringDrag && event.getX() > getWidth() - dp(37)) {
                    dragCallback.onClose();
                } else if (!dragging) {
                    performClick();
                }
                dragging = false;
                return true;
            case MotionEvent.ACTION_CANCEL:
                dragging = false;
                return true;
            default:
                return true;
        }
    }

    @Override
    public boolean performClick() {
        super.performClick();
        return true;
    }
}
