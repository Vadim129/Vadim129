package com.vadim129.rhythmoverlay;

import android.app.Activity;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.os.Bundle;
import android.view.Gravity;
import android.view.View;
import android.widget.LinearLayout;
import android.widget.RadioButton;
import android.widget.RadioGroup;
import android.widget.ScrollView;
import android.widget.SeekBar;
import android.widget.TextView;

/** Persistent visual and sound settings. Changes are observed immediately by a live overlay. */
public class SettingsActivity extends Activity {
    private SharedPreferences prefs;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().setStatusBarColor(Ui.BG);
        getWindow().setNavigationBarColor(Ui.BG);
        prefs = Skin.prefs(this);
        build();
    }

    private void build() {
        ScrollView scroll = new ScrollView(this);
        scroll.setBackgroundColor(Ui.BG);
        LinearLayout content = Ui.column(this);
        content.setPadding(Ui.dp(this, 20), Ui.dp(this, 18), Ui.dp(this, 20), Ui.dp(this, 28));
        scroll.addView(content);

        LinearLayout top = new LinearLayout(this);
        top.setGravity(Gravity.CENTER_VERTICAL);
        TextView headline = Ui.title(this, "Настройки");
        top.addView(headline, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1));
        TextView close = Ui.button(this, "Готово", 0xFF262B43, Ui.TEXT);
        close.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View view) { finish(); }
        });
        top.addView(close, new LinearLayout.LayoutParams(Ui.dp(this, 83), Ui.dp(this, 44)));
        content.addView(top);
        TextView copy = Ui.subtitle(this, "Все изменения применяются сразу к уже открытому виджету.");
        Ui.addMargin(content, copy, LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT, 0, 7, 0, 16);

        LinearLayout appearance = Ui.card(this);
        addSectionTitle(appearance, "Вид и движение", "Выберите характер виджета и его размер.");
        TextView skins = Ui.button(this, "Коллекция скинов  ·  " + Skin.selected(this).title + "  ›", 0xFF262D4A, Ui.TEXT);
        skins.setGravity(Gravity.CENTER_VERTICAL);
        skins.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View view) {
                startActivity(new Intent(SettingsActivity.this, SkinGalleryActivity.class));
            }
        });
        appearance.addView(skins, new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT));
        addSlider(appearance, "Прозрачность", 55, 100, Skin.opacity(this), Skin.PREF_OPACITY, "%");
        addSlider(appearance, "Размер прямоугольника", 80, 140, Skin.scale(this), Skin.PREF_SCALE, "%");
        addSlider(appearance, "Чувствительность полос", 50, 200, Skin.sensitivity(this), Skin.PREF_SENSITIVITY, "%");
        content.addView(appearance, new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT));

        LinearLayout source = Ui.card(this);
        Ui.addMargin(content, source, LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT, 0, 14, 0, 0);
        addSectionTitle(source, "Источник движения", "Авто пробует системную аудиосессию, затем микрофон. Для самой точной реакции используйте «Подключить звук телефона» на главном экране.");
        RadioGroup group = new RadioGroup(this);
        group.setOrientation(RadioGroup.VERTICAL);
        addRadio(group, "Авто", AudioMonitor.MODE_AUTO);
        addRadio(group, "Только захват телефона", AudioMonitor.MODE_PLAYBACK);
        addRadio(group, "Только микрофон / музыка рядом", AudioMonitor.MODE_MIC);
        addRadio(group, "Демо-анимация", AudioMonitor.MODE_DEMO);
        String saved = prefs.getString(Skin.PREF_AUDIO_MODE, AudioMonitor.MODE_AUTO);
        for (int index = 0; index < group.getChildCount(); index++) {
            View child = group.getChildAt(index);
            if (saved.equals(child.getTag())) {
                group.check(child.getId());
                break;
            }
        }
        group.setOnCheckedChangeListener(new RadioGroup.OnCheckedChangeListener() {
            @Override public void onCheckedChanged(RadioGroup radioGroup, int checkedId) {
                View selected = radioGroup.findViewById(checkedId);
                if (selected != null && selected.getTag() != null) {
                    prefs.edit().putString(Skin.PREF_AUDIO_MODE, String.valueOf(selected.getTag())).apply();
                }
            }
        });
        source.addView(group);

        LinearLayout privacy = Ui.card(this);
        privacy.setBackground(Ui.outlined(0xFF101727, 0xFF374164, Ui.dp(this, 18)));
        TextView privacyTitle = Ui.text(this, "Приватность и ограничения Android", 14, Ui.TEXT);
        privacyTitle.setTypeface(android.graphics.Typeface.create("sans-serif-medium", android.graphics.Typeface.NORMAL));
        privacy.addView(privacyTitle);
        TextView privacyText = Ui.subtitle(this, "Виджет не отправляет звук и не хранит записи. Системный захват работает только после явного подтверждения Android и только для программ, разрешивших захват воспроизведения. Если приложение блокирует это, используйте микрофон или демо.");
        Ui.addMargin(privacy, privacyText, LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT, 0, 7, 0, 0);
        Ui.addMargin(content, privacy, LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT, 0, 14, 0, 0);

        setContentView(scroll);
    }

    private void addSectionTitle(LinearLayout parent, String title, String detail) {
        TextView heading = Ui.text(this, title, 15, Ui.TEXT);
        heading.setTypeface(android.graphics.Typeface.create("sans-serif-medium", android.graphics.Typeface.NORMAL));
        parent.addView(heading);
        TextView note = Ui.subtitle(this, detail);
        Ui.addMargin(parent, note, LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT, 0, 5, 0, 12);
    }

    private void addSlider(LinearLayout parent, final String label, final int min, final int max, int initial, final String key, final String suffix) {
        LinearLayout row = Ui.column(this);
        TextView caption = Ui.text(this, "", 13, Ui.TEXT);
        row.addView(caption);
        SeekBar seek = new SeekBar(this);
        seek.setMax(max - min);
        seek.setProgress(Math.max(0, Math.min(max - min, initial - min)));
        updateSliderCaption(caption, label, initial, suffix);
        seek.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener() {
            @Override public void onProgressChanged(SeekBar bar, int value, boolean fromUser) {
                int actual = min + value;
                updateSliderCaption(caption, label, actual, suffix);
                prefs.edit().putInt(key, actual).apply();
            }
            @Override public void onStartTrackingTouch(SeekBar bar) { }
            @Override public void onStopTrackingTouch(SeekBar bar) { }
        });
        Ui.addMargin(row, seek, LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT, 0, 2, 0, 0);
        Ui.addMargin(parent, row, LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT, 0, 9, 0, 0);
    }

    private void updateSliderCaption(TextView view, String title, int value, String suffix) {
        view.setText(title + "   " + value + suffix);
    }

    private void addRadio(RadioGroup group, String title, String value) {
        RadioButton button = new RadioButton(this);
        button.setId(View.generateViewId());
        button.setTag(value);
        button.setText(title);
        button.setTextColor(Ui.TEXT);
        button.setTextSize(14);
        button.setPadding(Ui.dp(this, 1), Ui.dp(this, 5), 0, Ui.dp(this, 5));
        group.addView(button, new RadioGroup.LayoutParams(RadioGroup.LayoutParams.MATCH_PARENT, RadioGroup.LayoutParams.WRAP_CONTENT));
    }
}
