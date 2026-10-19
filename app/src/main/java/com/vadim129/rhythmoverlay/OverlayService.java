package com.vadim129.rhythmoverlay;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.ServiceInfo;
import android.graphics.PixelFormat;
import android.net.Uri;
import android.os.Build;
import android.os.IBinder;
import android.provider.Settings;
import android.view.Gravity;
import android.view.WindowManager;

/** Foreground service which owns exactly one user-enabled, draggable overlay window. */
public class OverlayService extends Service implements SharedPreferences.OnSharedPreferenceChangeListener {
    public static final String ACTION_SHOW = "com.vadim129.rhythmoverlay.SHOW";
    public static final String ACTION_STOP = "com.vadim129.rhythmoverlay.STOP";
    public static final String EXTRA_CAPTURE_DATA = "capture_data";
    public static final String EXTRA_CAPTURE_RESULT = "capture_result";

    private static final int NOTIFICATION_ID = 8021;
    private static final String CHANNEL_ID = "rhythm_overlay";
    private static final String PREF_WIDTH = "overlay_width";
    private static final String PREF_HEIGHT = "overlay_height";

    private WindowManager windowManager;
    private WindowManager.LayoutParams params;
    private EqualizerOverlayView overlay;
    private SharedPreferences preferences;
    private AudioMonitor audioMonitor;
    private boolean foreground;

    @Override
    public void onCreate() {
        super.onCreate();
        windowManager = (WindowManager) getSystemService(WINDOW_SERVICE);
        preferences = Skin.prefs(this);
        preferences.registerOnSharedPreferenceChangeListener(this);
        audioMonitor = new AudioMonitor(this);
        createChannel();
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        String action = intent == null ? ACTION_SHOW : intent.getAction();
        if (ACTION_STOP.equals(action)) {
            stopOverlay();
            return START_NOT_STICKY;
        }
        ensureForeground(false);
        if (!Settings.canDrawOverlays(this)) {
            AudioLevels.setStatus("Нужно разрешение поверх других окон");
            stopSelf();
            return START_NOT_STICKY;
        }
        showOverlay();
        Intent captureData = intent == null ? null : (Intent) intent.getParcelableExtra(EXTRA_CAPTURE_DATA);
        int result = intent == null ? 0 : intent.getIntExtra(EXTRA_CAPTURE_RESULT, 0);
        if (captureData != null && Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            ensureForeground(true);
            audioMonitor.start(captureData, result);
        } else if (overlay != null && !AudioLevels.isFresh()) {
            audioMonitor.start(null, 0);
        }
        return START_STICKY;
    }

    private void showOverlay() {
        if (overlay != null) return;
        int scale = Skin.scale(this);
        int defaultWidth = dp(286) * scale / 100;
        int defaultHeight = dp(174) * scale / 100;
        int width = clampWidth(preferences.getInt(PREF_WIDTH, defaultWidth));
        int height = clampHeight(preferences.getInt(PREF_HEIGHT, defaultHeight));
        params = new WindowManager.LayoutParams(width, height,
                Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                        ? WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
                        : WindowManager.LayoutParams.TYPE_PHONE,
                WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE
                        | WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN
                        | WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS,
                PixelFormat.TRANSLUCENT);
        params.gravity = Gravity.TOP | Gravity.START;
        params.x = preferences.getInt("overlay_x", dp(18));
        params.y = preferences.getInt("overlay_y", dp(105));
        params.alpha = Math.max(.55f, Math.min(1f, Skin.opacity(this) / 100f));
        overlay = new EqualizerOverlayView(this);
        overlay.setDragCallback(new EqualizerOverlayView.DragCallback() {
            @Override public void onDrag(float dx, float dy) {
                if (params == null || overlay == null) return;
                params.x += Math.round(dx);
                params.y += Math.round(dy);
                try {
                    windowManager.updateViewLayout(overlay, params);
                } catch (Exception ignored) { }
            }

            @Override public void onResize(float scaleFactor) {
                resizeOverlay(scaleFactor);
            }

            @Override public void onClose() {
                stopOverlay();
            }

            @Override public void onOpenSettings() {
                openSettings();
            }
        });
        try {
            windowManager.addView(overlay, params);
            preferences.edit().putBoolean(Skin.PREF_OVERLAY_RUNNING, true).apply();
        } catch (Exception error) {
            overlay = null;
            preferences.edit().putBoolean(Skin.PREF_OVERLAY_RUNNING, false).apply();
            AudioLevels.setStatus("Не удалось открыть виджет");
            stopSelf();
        }
    }

    private void updateWindow(boolean resetSizeFromSettings) {
        if (overlay == null || params == null) return;
        if (resetSizeFromSettings) {
            int scale = Skin.scale(this);
            params.width = clampWidth(dp(286) * scale / 100);
            params.height = clampHeight(dp(174) * scale / 100);
            preferences.edit().putInt(PREF_WIDTH, params.width).putInt(PREF_HEIGHT, params.height).apply();
        }
        params.alpha = Math.max(.55f, Math.min(1f, Skin.opacity(this) / 100f));
        try {
            windowManager.updateViewLayout(overlay, params);
            overlay.invalidate();
        } catch (Exception ignored) { }
    }

    private void resizeOverlay(float scaleFactor) {
        if (overlay == null || params == null) return;
        float ratio = params.height / (float) Math.max(1, params.width);
        int width = clampWidth(Math.round(params.width * scaleFactor));
        int height = clampHeight(Math.round(width * ratio));
        params.width = width;
        params.height = height;
        preferences.edit().putInt(PREF_WIDTH, width).putInt(PREF_HEIGHT, height).apply();
        try {
            windowManager.updateViewLayout(overlay, params);
            overlay.invalidate();
        } catch (Exception ignored) { }
    }

    private void openSettings() {
        Intent settings = new Intent(this, SettingsActivity.class);
        settings.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_REORDER_TO_FRONT);
        try {
            startActivity(settings);
        } catch (Exception ignored) { }
    }

    private int clampWidth(int value) {
        return Math.max(dp(150), Math.min(dp(720), value));
    }

    private int clampHeight(int value) {
        return Math.max(dp(90), Math.min(dp(480), value));
    }

    private void ensureForeground(boolean usesProjection) {
        Notification notification = makeNotification();
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            int type = 0;
            if (Build.VERSION.SDK_INT >= 34) type |= ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE;
            if (usesProjection && Build.VERSION.SDK_INT >= 29) type |= ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PROJECTION;
            if (type != 0 && Build.VERSION.SDK_INT >= 29) {
                startForeground(NOTIFICATION_ID, notification, type);
            } else {
                startForeground(NOTIFICATION_ID, notification);
            }
        } else {
            startForeground(NOTIFICATION_ID, notification);
        }
        foreground = true;
    }

    private void createChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return;
        NotificationChannel channel = new NotificationChannel(CHANNEL_ID, "Ритм-виджет", NotificationManager.IMPORTANCE_LOW);
        channel.setDescription("Управление плавающим музыкальным эквалайзером");
        channel.setShowBadge(false);
        NotificationManager manager = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        if (manager != null) manager.createNotificationChannel(channel);
    }

    private Notification makeNotification() {
        Intent open = new Intent(this, MainActivity.class);
        open.setFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        PendingIntent openIntent = PendingIntent.getActivity(this, 1, open, pendingFlags());
        Intent stop = new Intent(this, OverlayService.class).setAction(ACTION_STOP);
        PendingIntent stopIntent = PendingIntent.getService(this, 2, stop, pendingFlags());
        return new Notification.Builder(this, CHANNEL_ID)
                .setSmallIcon(android.R.drawable.ic_media_play)
                .setContentTitle("Ритм-виджет включён")
                .setContentText("Тяните одним пальцем · удерживайте: шестерёнка и крестик · щипок меняет размер")
                .setOngoing(true)
                .setContentIntent(openIntent)
                .addAction(new Notification.Action.Builder(android.R.drawable.ic_menu_close_clear_cancel, "Закрыть", stopIntent).build())
                .build();
    }

    private int pendingFlags() {
        return PendingIntent.FLAG_UPDATE_CURRENT | (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M ? PendingIntent.FLAG_IMMUTABLE : 0);
    }

    private void stopOverlay() {
        if (params != null) {
            preferences.edit()
                    .putInt("overlay_x", params.x)
                    .putInt("overlay_y", params.y)
                    .putInt(PREF_WIDTH, params.width)
                    .putInt(PREF_HEIGHT, params.height)
                    .apply();
        }
        if (overlay != null) {
            try { windowManager.removeView(overlay); } catch (Exception ignored) { }
            overlay = null;
        }
        audioMonitor.stop();
        AudioLevels.clear();
        preferences.edit().putBoolean(Skin.PREF_OVERLAY_RUNNING, false).apply();
        if (foreground) {
            stopForeground(true);
            foreground = false;
        }
        stopSelf();
    }

    @Override
    public void onSharedPreferenceChanged(SharedPreferences sharedPreferences, String key) {
        if (Skin.PREF_SCALE.equals(key)) {
            updateWindow(true);
        } else if (Skin.PREF_SKIN.equals(key) || Skin.PREF_OPACITY.equals(key) || Skin.PREF_SENSITIVITY.equals(key)) {
            updateWindow(false);
        }
        if (Skin.PREF_AUDIO_MODE.equals(key) && overlay != null) {
            audioMonitor.start(null, 0);
        }
    }

    @Override
    public void onDestroy() {
        preferences.unregisterOnSharedPreferenceChangeListener(this);
        if (overlay != null) {
            try { windowManager.removeView(overlay); } catch (Exception ignored) { }
            overlay = null;
        }
        if (audioMonitor != null) audioMonitor.stop();
        preferences.edit().putBoolean(Skin.PREF_OVERLAY_RUNNING, false).apply();
        super.onDestroy();
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    public static Intent settingsIntent(Context context) {
        return new Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                Uri.parse("package:" + context.getPackageName()));
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }
}
