package com.vadim129.rhythmoverlay;

import android.app.Activity;
import android.os.Bundle;
import android.view.Gravity;
import android.view.View;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

/** Original vector/Canvas skins including two dancers and five friendly animals. */
public class SkinGalleryActivity extends Activity {
    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().setStatusBarColor(Ui.BG);
        getWindow().setNavigationBarColor(Ui.BG);
        build();
    }

    private void build() {
        ScrollView scroll = new ScrollView(this);
        scroll.setBackgroundColor(Ui.BG);
        LinearLayout content = Ui.column(this);
        content.setPadding(Ui.dp(this, 20), Ui.dp(this, 18), Ui.dp(this, 20), Ui.dp(this, 30));
        scroll.addView(content);

        LinearLayout header = new LinearLayout(this);
        header.setGravity(Gravity.CENTER_VERTICAL);
        TextView titleBox = Ui.title(this, "Коллекция скинов");
        header.addView(titleBox, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1));
        TextView back = Ui.button(this, "Назад", 0xFF262B43, Ui.TEXT);
        back.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View view) { finish(); }
        });
        header.addView(back, new LinearLayout.LayoutParams(Ui.dp(this, 76), Ui.dp(this, 44)));
        content.addView(header);
        TextView description = Ui.subtitle(this, "Все скины рисуются прямо в приложении. Выберите карточку — она моментально станет скином плавающего виджета.");
        Ui.addMargin(content, description, LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT, 0, 7, 0, 16);

        String active = Skin.selectedId(this);
        for (final Skin.Spec spec : Skin.ALL) {
            final LinearLayout card = Ui.card(this);
            boolean selected = spec.id.equals(active);
            card.setBackground(Ui.outlined(selected ? 0xFF1D2342 : Ui.CARD, selected ? spec.accent : 0xFF303751, Ui.dp(this, 18)));
            card.setClickable(true);
            card.setFocusable(true);
            EqualizerOverlayView preview = new EqualizerOverlayView(this, spec.id, true);
            preview.setBackground(Ui.round(0x00000000, Ui.dp(this, 13)));
            card.addView(preview, new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, Ui.dp(this, 118)));

            LinearLayout textRow = new LinearLayout(this);
            textRow.setGravity(Gravity.CENTER_VERTICAL);
            TextView name = Ui.text(this, spec.title, 16, Ui.TEXT);
            name.setTypeface(android.graphics.Typeface.create("sans-serif-medium", android.graphics.Typeface.NORMAL));
            textRow.addView(name, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1));
            TextView mark = Ui.text(this, selected ? "ВЫБРАН" : "ВЫБРАТЬ", 10, selected ? spec.accent : Ui.MUTED);
            mark.setTypeface(android.graphics.Typeface.create("sans-serif-medium", android.graphics.Typeface.NORMAL));
            textRow.addView(mark);
            Ui.addMargin(card, textRow, LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT, 0, 12, 0, 0);
            TextView detail = Ui.subtitle(this, spec.subtitle);
            Ui.addMargin(card, detail, LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT, 0, 4, 0, 0);

            card.setOnClickListener(new View.OnClickListener() {
                @Override public void onClick(View view) {
                    Skin.select(SkinGalleryActivity.this, spec.id);
                    Toast.makeText(SkinGalleryActivity.this, "Выбран скин: " + spec.title, Toast.LENGTH_SHORT).show();
                    finish();
                }
            });
            Ui.addMargin(content, card, LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT, 0, 0, 0, 12);
        }
        setContentView(scroll);
    }
}
