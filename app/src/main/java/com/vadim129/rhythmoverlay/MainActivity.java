package com.vadim129.rhythmoverlay;

import android.Manifest;
import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.media.projection.MediaProjectionManager;
import android.os.Build;
import android.os.Bundle;
import android.provider.Settings;
import android.view.Gravity;
import android.view.View;
import android.view.Window;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

/** Main control panel. The overlay is never started silently: this page is the explicit control. */
public class MainActivity extends Activity {
    private static final int REQUEST_MICROPHONE = 41;
    private static final int REQUEST_NOTIFICATIONS = 42;
    private static final int REQUEST_CAPTURE = 43;

    private TextView overlayStatus;
    private TextView primaryButton;
    private TextView skinName;
    private EqualizerOverlayView preview;
    private boolean pendingOverlayStart;
    private boolean captureAfterMicrophone;
    // MediaProjection consent is a short-lived in-memory token; retain it while the user enables overlay permission.
    private Intent pendingCaptureData;
    private int pendingCaptureResult;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        Window window = getWindow();
        window.setStatusBarColor(Ui.BG);
        window.setNavigationBarColor(Ui.BG);
        buildContent();
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (pendingOverlayStart && Settings.canDrawOverlays(this)) {
            pendingOverlayStart = false;
            Intent captureData = pendingCaptureData;
            int captureResult = pendingCaptureResult;
            pendingCaptureData = null;
            pendingCaptureResult = 0;
            startOverlay(captureData, captureResult);
        }
        refreshState();
    }

    private void buildContent() {
        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        scroll.setBackgroundColor(Ui.BG);
        LinearLayout content = Ui.column(this);
        content.setPadding(Ui.dp(this, 20), Ui.dp(this, 19), Ui.dp(this, 20), Ui.dp(this, 30));
        scroll.addView(content, new ScrollView.LayoutParams(ScrollView.LayoutParams.MATCH_PARENT, ScrollView.LayoutParams.WRAP_CONTENT));

        LinearLayout header = new LinearLayout(this);
        header.setGravity(Gravity.CENTER_VERTICAL);
        header.setOrientation(LinearLayout.HORIZONTAL);
        LinearLayout titleBox = Ui.column(this);
        TextView eyebrow = Ui.text(this, "ПЛАВАЮЩИЙ ВИЗУАЛИЗАТОР", 10, Ui.ACCENT);
        eyebrow.setLetterSpacing(.13f);
        titleBox.addView(eyebrow);
        TextView title = Ui.title(this, "Ритм-виджет");
        Ui.addMargin(titleBox, title, LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT, 0, 4, 0, 0);
        header.addView(titleBox, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1));
        TextView settings = Ui.button(this, "⚙", 0xFF20253A, Ui.TEXT);
        settings.setTextSize(20);
        settings.setContentDescription("Открыть настройки");
        settings.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View view) {
                startActivity(new Intent(MainActivity.this, SettingsActivity.class));
            }
        });
        header.addView(settings, new LinearLayout.LayoutParams(Ui.dp(this, 48), Ui.dp(this, 46)));
        content.addView(header);

        TextView intro = Ui.subtitle(this, "Прозрачный эквалайзер поверх экрана: тяните одним пальцем, щипком меняйте размер.");
        Ui.addMargin(content, intro, LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT, 0, 9, 0, 17);

        FrameLayout visualCard = new FrameLayout(this);
        visualCard.setBackground(Ui.round(0xFF121629, Ui.dp(this, 20)));
        preview = new EqualizerOverlayView(this, Skin.selectedId(this), true);
        visualCard.addView(preview, new FrameLayout.LayoutParams(FrameLayout.LayoutParams.MATCH_PARENT, Ui.dp(this, 174)));
        TextView previewChip = Ui.text(this, "ПРЕДПРОСМОТР", 10, Ui.TEXT);
        previewChip.setGravity(Gravity.CENTER);
        previewChip.setTypeface(android.graphics.Typeface.create("sans-serif-medium", android.graphics.Typeface.NORMAL));
        previewChip.setBackground(Ui.round(0xAA080A12, Ui.dp(this, 10)));
        FrameLayout.LayoutParams chipParams = new FrameLayout.LayoutParams(Ui.dp(this, 112), Ui.dp(this, 27), Gravity.TOP | Gravity.END);
        chipParams.setMargins(0, Ui.dp(this, 11), Ui.dp(this, 11), 0);
        visualCard.addView(previewChip, chipParams);
        content.addView(visualCard, new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, Ui.dp(this, 174)));

        LinearLayout statusCard = Ui.card(this);
        LinearLayout statusTop = new LinearLayout(this);
        statusTop.setGravity(Gravity.CENTER_VERTICAL);
        TextView statusTitle = Ui.text(this, "Статус виджета", 15, Ui.TEXT);
        statusTitle.setTypeface(android.graphics.Typeface.create("sans-serif-medium", android.graphics.Typeface.NORMAL));
        statusTop.addView(statusTitle, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1));
        overlayStatus = Ui.text(this, "", 12, Ui.GREEN);
        overlayStatus.setGravity(Gravity.CENTER_VERTICAL);
        statusTop.addView(overlayStatus);
        statusCard.addView(statusTop);
        primaryButton = Ui.button(this, "", Ui.ACCENT, 0xFFFFFFFF);
        primaryButton.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View view) {
                if (Skin.prefs(MainActivity.this).getBoolean(Skin.PREF_OVERLAY_RUNNING, false)) {
                    stopOverlay();
                } else {
                    beginOverlay();
                }
            }
        });
        Ui.addMargin(statusCard, primaryButton, LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT, 0, 13, 0, 0);
        Ui.addMargin(content, statusCard, LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT, 0, 16, 0, 0);

        LinearLayout skinCard = Ui.card(this);
        TextView skinSection = Ui.text(this, "Внешний вид", 15, Ui.TEXT);
        skinSection.setTypeface(android.graphics.Typeface.create("sans-serif-medium", android.graphics.Typeface.NORMAL));
        skinCard.addView(skinSection);
        skinName = Ui.subtitle(this, "");
        Ui.addMargin(skinCard, skinName, LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT, 0, 4, 0, 10);
        TextView chooseSkin = Ui.button(this, "Открыть 100 скинов  ›", 0xFF222942, Ui.TEXT);
        chooseSkin.setGravity(Gravity.CENTER_VERTICAL);
        chooseSkin.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View view) {
                startActivity(new Intent(MainActivity.this, SkinGalleryActivity.class));
            }
        });
        skinCard.addView(chooseSkin, new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT));
        Ui.addMargin(content, skinCard, LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT, 0, 14, 0, 0);

        LinearLayout audioCard = Ui.card(this);
        TextView audioTitle = Ui.text(this, "Реакция на музыку", 15, Ui.TEXT);
        audioTitle.setTypeface(android.graphics.Typeface.create("sans-serif-medium", android.graphics.Typeface.NORMAL));
        audioCard.addView(audioTitle);
        TextView audioCopy = Ui.subtitle(this, "Подключите системный захват — он реагирует на приложения, которые разрешают Android захватывать их звук. Микрофон остаётся запасным вариантом.");
        Ui.addMargin(audioCard, audioCopy, LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT, 0, 5, 0, 12);
        TextView capture = Ui.button(this, "Подключить звук телефона", 0xFF315A8A, Ui.TEXT);
        capture.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View view) {
                requestPlaybackCapture();
            }
        });
        audioCard.addView(capture, new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT));
        TextView microphone = Ui.button(this, "Разрешить микрофон / звук рядом", 0xFF222942, Ui.TEXT);
        microphone.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View view) {
                requestMicrophone(false);
            }
        });
        Ui.addMargin(audioCard, microphone, LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT, 0, 8, 0, 0);
        Ui.addMargin(content, audioCard, LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT, 0, 14, 0, 0);

        LinearLayout guideCard = Ui.card(this);
        guideCard.setBackground(Ui.outlined(0xFF111729, 0xFF343B61, Ui.dp(this, 18)));
        TextView guideTitle = Ui.text(this, "Как пользоваться", 14, Ui.TEXT);
        guideTitle.setTypeface(android.graphics.Typeface.create("sans-serif-medium", android.graphics.Typeface.NORMAL));
        guideCard.addView(guideTitle);
        TextView guide = Ui.subtitle(this, "1. Разрешите показ поверх других окон.\n2. Включите виджет.\n3. Тяните его одним пальцем; раздвигайте или сдвигайте двумя пальцами, чтобы изменить размер.\n4. Удерживайте виджет — откроются настройки. Закрыть его можно здесь или через уведомление.");
        Ui.addMargin(guideCard, guide, LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT, 0, 7, 0, 0);
        Ui.addMargin(content, guideCard, LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT, 0, 14, 0, 0);

        setContentView(scroll);
    }

    private void refreshState() {
        boolean enabled = Skin.prefs(this).getBoolean(Skin.PREF_OVERLAY_RUNNING, false);
        if (overlayStatus != null) {
            overlayStatus.setText(enabled ? "●  ВКЛЮЧЁН" : "○  ВЫКЛЮЧЕН");
            overlayStatus.setTextColor(enabled ? Ui.GREEN : Ui.MUTED);
        }
        if (primaryButton != null) {
            primaryButton.setText(enabled ? "Закрыть плавающий виджет" : "Включить плавающий виджет");
            primaryButton.setBackground(Ui.round(enabled ? 0xFF4B285F : Ui.ACCENT, Ui.dp(this, 13)));
        }
        Skin.Spec selected = Skin.selected(this);
        if (skinName != null) skinName.setText("Сейчас: " + selected.title + " · " + selected.category + " · " + Skin.EXPECTED_SKIN_COUNT + " скинов в коллекции");
        if (preview != null) preview.setSkinId(selected.id);
    }

    private void beginOverlay() {
        if (!Settings.canDrawOverlays(this)) {
            pendingOverlayStart = true;
            Toast.makeText(this, "Разрешите показ поверх других приложений", Toast.LENGTH_LONG).show();
            startActivity(OverlayService.settingsIntent(this));
            return;
        }
        requestNotificationPermission();
        startOverlay(null, 0);
    }

    private void startOverlay(Intent captureData, int captureResult) {
        Intent service = new Intent(this, OverlayService.class).setAction(OverlayService.ACTION_SHOW);
        if (captureData != null) {
            service.putExtra(OverlayService.EXTRA_CAPTURE_DATA, captureData);
            service.putExtra(OverlayService.EXTRA_CAPTURE_RESULT, captureResult);
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) startForegroundService(service);
        else startService(service);
        Toast.makeText(this, captureData == null ? "Виджет включается" : "Захват музыки подключён", Toast.LENGTH_SHORT).show();
    }

    private void stopOverlay() {
        startService(new Intent(this, OverlayService.class).setAction(OverlayService.ACTION_STOP));
        refreshState();
    }

    private void requestNotificationPermission() {
        if (Build.VERSION.SDK_INT >= 33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, REQUEST_NOTIFICATIONS);
        }
    }

    private void requestPlaybackCapture() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q) {
            Toast.makeText(this, "На Android 9 и ниже доступен режим микрофона или аудиосессии", Toast.LENGTH_LONG).show();
            requestMicrophone(false);
            return;
        }
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            captureAfterMicrophone = true;
            requestMicrophone(true);
            return;
        }
        beginProjectionRequest();
    }

    private void requestMicrophone(boolean thenCapture) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.M || checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) {
            if (thenCapture) beginProjectionRequest();
            else Toast.makeText(this, "Доступ к микрофону уже есть. Включите виджет или выберите источник в настройках.", Toast.LENGTH_LONG).show();
            return;
        }
        captureAfterMicrophone = thenCapture;
        requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO}, REQUEST_MICROPHONE);
    }

    private void beginProjectionRequest() {
        MediaProjectionManager manager = (MediaProjectionManager) getSystemService(Context.MEDIA_PROJECTION_SERVICE);
        if (manager == null) {
            Toast.makeText(this, "Системный захват звука недоступен", Toast.LENGTH_LONG).show();
            return;
        }
        Toast.makeText(this, "Подтвердите системный запрос Android. Захватить можно только приложения, которые это разрешают.", Toast.LENGTH_LONG).show();
        startActivityForResult(manager.createScreenCaptureIntent(), REQUEST_CAPTURE);
    }

    @Override
    @SuppressWarnings("deprecation")
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == REQUEST_CAPTURE) {
            if (resultCode == RESULT_OK && data != null) {
                if (!Settings.canDrawOverlays(this)) {
                    pendingOverlayStart = true;
                    pendingCaptureData = data;
                    pendingCaptureResult = resultCode;
                    Toast.makeText(this, "Сначала разрешите показ поверх других окон", Toast.LENGTH_LONG).show();
                    startActivity(OverlayService.settingsIntent(this));
                } else {
                    requestNotificationPermission();
                    startOverlay(data, resultCode);
                }
            } else {
                Toast.makeText(this, "Захват звука не был разрешён", Toast.LENGTH_SHORT).show();
            }
        }
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == REQUEST_MICROPHONE) {
            boolean granted = grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED;
            if (granted && captureAfterMicrophone) {
                captureAfterMicrophone = false;
                beginProjectionRequest();
            } else if (granted) {
                Toast.makeText(this, "Микрофон разрешён. В настройках выберите «Микрофон» или включите виджет в авто-режиме.", Toast.LENGTH_LONG).show();
            } else {
                Toast.makeText(this, "Без доступа к звуку доступна только демо-анимация", Toast.LENGTH_LONG).show();
            }
        }
    }
}
