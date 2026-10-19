package com.vadim129.rhythmoverlay;

import android.app.Activity;
import android.os.Bundle;
import android.view.Gravity;
import android.view.View;
import android.widget.HorizontalScrollView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

/** Browsable catalogue: 25 motif families × four distinct layouts = 100 selectable skins. */
public class SkinGalleryActivity extends Activity {
    private LinearLayout categoryRow;
    private LinearLayout skinList;
    private String activeCategory;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().setStatusBarColor(Ui.BG);
        getWindow().setNavigationBarColor(Ui.BG);
        activeCategory = Skin.selected(this).category;
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
        TextView titleBox = Ui.title(this, "100 скинов");
        header.addView(titleBox, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1));
        TextView back = Ui.button(this, "Назад", 0xFF262B43, Ui.TEXT);
        back.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View view) { finish(); }
        });
        header.addView(back, new LinearLayout.LayoutParams(Ui.dp(this, 76), Ui.dp(this, 44)));
        content.addView(header);
        TextView description = Ui.subtitle(this,
                "25 разных направлений по 4 самостоятельные композиции: карты, камни, стихии, космос, музыка, природа и абстракция. Это не просто перекрашенные варианты.");
        Ui.addMargin(content, description, LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT, 0, 7, 0, 14);

        HorizontalScrollView categoryScroll = new HorizontalScrollView(this);
        categoryScroll.setHorizontalScrollBarEnabled(false);
        categoryRow = new LinearLayout(this);
        categoryRow.setOrientation(LinearLayout.HORIZONTAL);
        categoryScroll.addView(categoryRow, new HorizontalScrollView.LayoutParams(HorizontalScrollView.LayoutParams.WRAP_CONTENT,
                HorizontalScrollView.LayoutParams.WRAP_CONTENT));
        content.addView(categoryScroll, new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, Ui.dp(this, 48)));

        skinList = Ui.column(this);
        Ui.addMargin(content, skinList, LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT, 0, 12, 0, 0);
        setContentView(scroll);
        renderCategories();
        renderSkins();
    }

    private void renderCategories() {
        categoryRow.removeAllViews();
        for (final String category : Skin.categories()) {
            TextView chip = Ui.button(this, category, category.equals(activeCategory) ? 0xFF5A4392 : 0xFF222942,
                    category.equals(activeCategory) ? 0xFFFFFFFF : Ui.MUTED);
            chip.setTextSize(12);
            chip.setMinHeight(Ui.dp(this, 38));
            chip.setPadding(Ui.dp(this, 12), Ui.dp(this, 6), Ui.dp(this, 12), Ui.dp(this, 6));
            chip.setOnClickListener(new View.OnClickListener() {
                @Override public void onClick(View view) {
                    activeCategory = category;
                    renderCategories();
                    renderSkins();
                }
            });
            LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(LinearLayout.LayoutParams.WRAP_CONTENT, Ui.dp(this, 40));
            params.setMargins(0, 0, Ui.dp(this, 8), 0);
            categoryRow.addView(chip, params);
        }
    }

    private void renderSkins() {
        skinList.removeAllViews();
        String active = Skin.selectedId(this);
        for (final Skin.Spec spec : Skin.inCategory(activeCategory)) {
            final LinearLayout card = Ui.card(this);
            boolean selected = spec.id.equals(active);
            card.setBackground(Ui.outlined(selected ? 0xFF1D2342 : Ui.CARD, selected ? spec.accent : 0xFF303751, Ui.dp(this, 18)));
            card.setClickable(true);
            card.setFocusable(true);
            EqualizerOverlayView preview = new EqualizerOverlayView(this, spec.id, true);
            card.addView(preview, new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, Ui.dp(this, 136)));

            LinearLayout textRow = new LinearLayout(this);
            textRow.setGravity(Gravity.CENTER_VERTICAL);
            TextView name = Ui.text(this, spec.title, 16, Ui.TEXT);
            name.setTypeface(android.graphics.Typeface.create("sans-serif-medium", android.graphics.Typeface.NORMAL));
            textRow.addView(name, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1));
            TextView mark = Ui.text(this, selected ? "ВЫБРАН" : "ВЫБРАТЬ", 10, selected ? spec.accent : Ui.MUTED);
            mark.setTypeface(android.graphics.Typeface.create("sans-serif-medium", android.graphics.Typeface.NORMAL));
            textRow.addView(mark);
            Ui.addMargin(card, textRow, LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT, 0, 12, 0, 0);
            TextView detail = Ui.subtitle(this, spec.category + " · вариант " + (spec.variant + 1) + " из 4");
            Ui.addMargin(card, detail, LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT, 0, 4, 0, 0);

            card.setOnClickListener(new View.OnClickListener() {
                @Override public void onClick(View view) {
                    Skin.select(SkinGalleryActivity.this, spec.id);
                    Toast.makeText(SkinGalleryActivity.this, "Выбран скин: " + spec.title, Toast.LENGTH_SHORT).show();
                    finish();
                }
            });
            Ui.addMargin(skinList, card, LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT, 0, 0, 0, 12);
        }
    }
}
