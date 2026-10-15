package ru.vadim.bookvoice;

import android.content.Context;
import android.content.res.ColorStateList;
import android.content.res.Resources;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.TextView;

/** Small programmatic UI toolkit; keeping the app dependency-free also keeps the APK compact. */
final class Ui {
    static final int PAPER = Color.rgb(255, 249, 242);
    static final int INK = Color.rgb(28, 27, 31);
    static final int FOREST = Color.rgb(30, 91, 74);
    static final int FOREST_DARK = Color.rgb(18, 60, 49);
    static final int MINT = Color.rgb(221, 243, 232);
    static final int SAND = Color.rgb(244, 237, 228);
    static final int MUTED = Color.rgb(112, 106, 101);
    static final int LINE = Color.rgb(222, 215, 208);
    static final int DANGER = Color.rgb(156, 66, 52);

    private Ui() {
    }

    static int dp(Context context, float value) {
        return Math.round(value * context.getResources().getDisplayMetrics().density);
    }

    static TextView text(Context context, String value, float sp, int color) {
        TextView view = new TextView(context);
        view.setText(value);
        view.setTextSize(sp);
        view.setTextColor(color);
        view.setIncludeFontPadding(true);
        return view;
    }

    static TextView heading(Context context, String value, float sp) {
        TextView view = text(context, value, sp, INK);
        view.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        return view;
    }

    static Button button(Context context, String value, int background, int foreground) {
        Button button = new Button(context);
        button.setText(value);
        button.setTextColor(foreground);
        button.setTextSize(14);
        button.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        button.setAllCaps(false);
        button.setGravity(Gravity.CENTER);
        button.setMinHeight(dp(context, 44));
        button.setMinimumHeight(dp(context, 44));
        button.setPadding(dp(context, 14), 0, dp(context, 14), 0);
        button.setBackground(round(background, 14));
        button.setBackgroundTintList(ColorStateList.valueOf(background));
        return button;
    }

    static GradientDrawable round(int color, float radiusDp) {
        GradientDrawable drawable = new GradientDrawable();
        drawable.setColor(color);
        drawable.setCornerRadius(radiusDp * Resources.getSystem().getDisplayMetrics().density);
        return drawable;
    }

    static GradientDrawable outlined(int fill, int stroke, float radiusDp) {
        GradientDrawable drawable = round(fill, radiusDp);
        drawable.setStroke(Math.max(1, Math.round(Resources.getSystem().getDisplayMetrics().density)), stroke);
        return drawable;
    }

    static void setMargins(View view, int left, int top, int right, int bottom) {
        if (view.getLayoutParams() instanceof android.view.ViewGroup.MarginLayoutParams) {
            ((android.view.ViewGroup.MarginLayoutParams) view.getLayoutParams()).setMargins(left, top, right, bottom);
        }
    }
}
