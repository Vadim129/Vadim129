package com.vadim129.rhythmoverlay;

import android.content.Context;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.view.Gravity;
import android.view.View;
import android.widget.LinearLayout;
import android.widget.TextView;

/** Tiny programmatic design system so the app has no dependency on an external UI library. */
public final class Ui {
    public static final int BG = 0xFF090B13;
    public static final int CARD = 0xFF141727;
    public static final int CARD_ALT = 0xFF1B2033;
    public static final int TEXT = 0xFFF4F5FF;
    public static final int MUTED = 0xFFADB4D3;
    public static final int ACCENT = 0xFFA78BFA;
    public static final int GREEN = 0xFF55E6AD;

    private Ui() { }

    public static int dp(Context context, float value) {
        return Math.round(value * context.getResources().getDisplayMetrics().density);
    }

    public static LinearLayout column(Context context) {
        LinearLayout layout = new LinearLayout(context);
        layout.setOrientation(LinearLayout.VERTICAL);
        return layout;
    }

    public static TextView text(Context context, String value, float size, int color) {
        TextView text = new TextView(context);
        text.setText(value);
        text.setTextSize(size);
        text.setTextColor(color);
        text.setIncludeFontPadding(false);
        text.setLineSpacing(0, 1.08f);
        return text;
    }

    public static TextView title(Context context, String value) {
        TextView text = text(context, value, 22, TEXT);
        text.setTypeface(Typeface.create("sans-serif", Typeface.BOLD));
        return text;
    }

    public static TextView subtitle(Context context, String value) {
        TextView text = text(context, value, 13, MUTED);
        return text;
    }

    public static TextView button(Context context, String value, int fill, int color) {
        TextView button = text(context, value, 14, color);
        button.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
        button.setGravity(Gravity.CENTER);
        button.setMinHeight(dp(context, 46));
        button.setPadding(dp(context, 14), dp(context, 11), dp(context, 14), dp(context, 11));
        button.setBackground(round(fill, dp(context, 13)));
        button.setClickable(true);
        button.setFocusable(true);
        return button;
    }

    public static GradientDrawable round(int color, int radius) {
        GradientDrawable drawable = new GradientDrawable();
        drawable.setColor(color);
        drawable.setCornerRadius(radius);
        return drawable;
    }

    public static GradientDrawable outlined(int fill, int stroke, int radius) {
        GradientDrawable drawable = round(fill, radius);
        drawable.setStroke(Math.max(1, radius / 9), stroke);
        return drawable;
    }

    public static LinearLayout card(Context context) {
        LinearLayout card = column(context);
        card.setPadding(dp(context, 16), dp(context, 15), dp(context, 16), dp(context, 15));
        card.setBackground(round(CARD, dp(context, 18)));
        return card;
    }

    public static void addMargin(LinearLayout parent, View child, int width, int height, int left, int top, int right, int bottom) {
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(width, height);
        params.setMargins(dp(parent.getContext(), left), dp(parent.getContext(), top), dp(parent.getContext(), right), dp(parent.getContext(), bottom));
        parent.addView(child, params);
    }

    public static int brighten(int color, float factor) {
        return Color.rgb(Math.min(255, (int) (Color.red(color) * factor)),
                Math.min(255, (int) (Color.green(color) * factor)),
                Math.min(255, (int) (Color.blue(color) * factor)));
    }
}
