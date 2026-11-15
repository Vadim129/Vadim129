package com.perekras.app;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.ComponentName;
import android.graphics.Bitmap;
import android.content.Intent;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.provider.Settings;
import android.view.View;
import android.view.ViewGroup;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.Spinner;
import android.widget.TextView;
import android.widget.Toast;

/**
 * Главный экран: одно оформление сразу для всех приложений, выбор обоев,
 * «перекрасить все» и подсказка, как работает запасной вариант с домашним
 * экраном. Интерфейс собран кодом, чтобы не тянуть AppCompat.
 */
public class MainActivity extends Activity {

    private static final int REQ_ICON = 41;
    private static final int REQ_WALL = 42;

    private static final String[] WALLS = {
            "", "wall_dots.png", "wall_waves.png", "wall_dark.png"
    };
    private static final String[] WALL_TITLES = {
            "Без обоев (однотонный фон)", "Точки", "Волны", "Тёмные градиенты", "Своя картинка"
    };

    private Spinner form;
    private Spinner palette;
    private Spinner walls;
    private TextView info;
    private String pendingIcon;
    private String pendingWall;

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        ScrollView sc = new ScrollView(this);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        int pad = dp(20);
        root.setPadding(pad, pad, pad, pad);
        sc.addView(root);
        setContentView(sc);

        String json = Styler.styleJson(this);

        root.addView(title("Перекрас"));
        root.addView(hint("Одно оформление — все значки на рабочем столе. Без рута. "
                + "Готовый значок ставится ярлыком: рабочий стол спросит подтверждение."));

        root.addView(label("Форма значка"));
        form = new Spinner(this);
        form.setAdapter(adapter(Style.FORM_TITLES));
        form.setSelection(Math.max(0, Style.form(json)));
        root.addView(form);

        root.addView(label("Палитра"));
        palette = new Spinner(this);
        String[] names = new String[Style.paletteCount()];
        for (int i = 0; i < names.length; i++) names[i] = "Палитра " + (i + 1);
        palette.setAdapter(adapter(names));
        palette.setSelection(Math.max(0, Style.palette(json)));
        root.addView(palette);

        root.addView(label("Обои"));
        walls = new Spinner(this);
        walls.setAdapter(adapter(WALL_TITLES));
        String w = Style.wallpaper(json);
        for (int i = 0; i < WALLS.length; i++) if (WALLS[i].equals(w)) walls.setSelection(i);
        root.addView(walls);

        root.addView(button("Применить ко всем ярлыкам", new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                applyAll();
            }
        }));
        root.addView(button("Перекрасить ещё приложение (выбрать значок)", new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                pickIcon();
            }
        }));
        root.addView(button("Добавить приложение из установленных", new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                startActivity(new Intent(MainActivity.this, AppsActivity.class));
            }
        }));
        root.addView(button("Свои обои из картинки", new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                pickWallpaper();
            }
        }));

        info = new TextView(this);
        info.setTextSize(15);
        info.setPadding(0, dp(16), 0, dp(16));
        root.addView(info);

        root.addView(title("Панель вместо домашнего экрана"));
        root.addView(hint("Самый полный режим: наш рабочий стол рисует все значки "
                + "в одном стиле и с обоями. Для этого надо выбрать его домашним экраном — "
                + "обычно лаунчер не даёт такое сделать программно, зато настройка никуда не денется."));
        root.addView(button("Открыть настройки домашнего экрана", new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                try {
                    startActivity(Apps.homeSettings(MainActivity.this));
                } catch (Throwable t) {
                    Toast.makeText(MainActivity.this, "Не нашлось системного экрана настроек",
                            Toast.LENGTH_SHORT).show();
                }
            }
        }));
        root.addView(button("Попробовать панель сейчас", new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                startActivity(new Intent(MainActivity.this, FloatingHome.class));
            }
        }));

        root.addView(title("Разрешение на список приложений"));
        root.addView(hint("На Android 11+ система показывает не всё, что установлено. "
                + "Кнопка ниже открывает настройку, где это разрешается."));
        root.addView(button("Разрешить запрашивать приложения", new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                Intent i = new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS);
                i.setData(Uri.parse("package:" + getPackageName()));
                startActivity(i);
            }
        }));

        root.addView(title("Все значки сразу"));
        root.addView(hint("Если система отдаёт значки приложений через свой помощник "
                + "(так делают производители в темах оформления), тема применяется "
                + "без закрепления каждого значка: достаточно одного ярлыка-маркера. "
                + "Ниже — кнопка для такого режима и честное предупреждение."));
        root.addView(button("Применить тему ко всем значкам", new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                applyFullTheme();
            }
        }));
    }

    @Override
    protected void onResume() {
        super.onResume();
        refreshInfo();
    }

    private void refreshInfo() {
        int n = Apps.picked(this).size();
        StringBuilder sb = new StringBuilder();
        sb.append("Перекрашено приложений: ").append(n).append('\n');
        if (!Apps.canPin(this)) {
            sb.append("Этот рабочий стол не умеет добавлять ярлыки — пользуйся панелью ниже.\n");
        }
        sb.append(Apps.isDefaultHome(this)
                ? "Панель уже выбрана домашним экраном."
                : "Домашний экран — штатный лаунчер (значки меняются по одному).");
        info.setText(sb.toString());
    }

    private void applyAll() {
        int f = form.getSelectedItemPosition();
        int p = palette.getSelectedItemPosition();
        String w = wallpaperChoice();
        Styler.saveStyle(this, f, p, w);
        Apps.hideDynamic(this);
        int ok = 0;
        for (String k : Apps.picked(this)) {
            String[] pa = Apps.split(k);
            if (pa == null) continue;
            String pkg = pa[0];
            String act = pa[1];
            Bitmap icon = Styler.make(this, Apps.iconOf(this, pkg, act, iconSize()), k, f, p);
            if (Apps.requestPin(this, pkg, act, icon, labelOf(pkg, act))) ok++;
        }
        Toast.makeText(this, ok == 0
                ? "Пока нечего перекрашивать — добавь приложения"
                : "Запрос отправлен: подтверди добавление " + ok + " ярлыков на рабочем столе",
                Toast.LENGTH_LONG).show();
        Apps.notifyHome(this);
        refreshInfo();
    }

    /**
     * Полная тема: сохраняем оформление и просим систему показать его на всех
     * значках. Система делает это только через свой компонент-помощник, поэтому
     * здесь ставится один ярлык-маркер и выводится предупреждение, если тему
     * поддержать нечем.
     */
    private void applyFullTheme() {
        int f = form.getSelectedItemPosition();
        int p = palette.getSelectedItemPosition();
        String w = wallpaperChoice();
        Styler.saveStyle(this, f, p, w);
        Apps.hideDynamic(this);
        Bitmap marker = Styler.make(this, appsIcon(), "theme_marker", f, p);
        Apps.applyTheme(this, marker, "Перекрас: тема");
        new AlertDialog.Builder(this)
                .setTitle("Тема сохранена")
                .setMessage("Оформление применено к ярлыкам «Перекраса», и на рабочем столе "
                        + "появился маркер темы.\n\nЧтобы система перерисовала значки всех "
                        + "приложений сама, нужен системный компонент-помощник: на обычном "
                        + "телефоне его нет, а без него Android не даёт менять чужие значки "
                        + "целиком. Рабочие пути: перекрасить нужные приложения по одному "
                        + "(кнопка выше) или включить панель «Перекраса» домашним экраном.")
                .setPositiveButton("Понятно", null)
                .show();
        Apps.notifyHome(this);
        refreshInfo();
    }

    private void pickIcon() {
        Intent i = new Intent(Intent.ACTION_GET_CONTENT);
        i.setType("image/*");
        i.putExtra(Intent.EXTRA_LOCAL_ONLY, true);
        try {
            startActivityForResult(Intent.createChooser(i, "Значок"), REQ_ICON);
        } catch (Throwable t) {
            Toast.makeText(this, "Не нашлось файлового менеджера", Toast.LENGTH_SHORT).show();
        }
    }

    private void pickWallpaper() {
        Intent i = new Intent(Intent.ACTION_GET_CONTENT);
        i.setType("image/*");
        i.putExtra(Intent.EXTRA_LOCAL_ONLY, true);
        try {
            startActivityForResult(Intent.createChooser(i, "Обои"), REQ_WALL);
        } catch (Throwable t) {
            Toast.makeText(this, "Не нашлось файлового менеджера", Toast.LENGTH_SHORT).show();
        }
    }

    @Override
    protected void onActivityResult(int req, int res, Intent data) {
        super.onActivityResult(req, res, data);
        if (res != RESULT_OK || data == null || data.getData() == null) return;
        if (req == REQ_ICON) {
            pendingIcon = Media.storeImage(this, data.getData());
            if (pendingIcon != null) {
                Toast.makeText(this, "Значок сохранён — выбери приложение", Toast.LENGTH_SHORT).show();
                startActivity(new Intent(this, AppsActivity.class)
                        .putExtra(AppsActivity.EXTRA_ICON_ID, pendingIcon));
            }
        } else if (req == REQ_WALL) {
            pendingWall = Media.storeImage(this, data.getData());
            if (pendingWall != null) {
                Styler.prefs(this).edit().putString(Style.KEY_OWN_WALL, pendingWall).apply();
                Toast.makeText(this, "Обои сохранены — применяю", Toast.LENGTH_SHORT).show();
                applyAll();
            }
        }
    }

    private Bitmap appsIcon() {
        try {
            return Apps.draw(getPackageManager().getApplicationIcon(getPackageName()), iconSize());
        } catch (Throwable t) {
            return Bitmap.createBitmap(iconSize(), iconSize(), Bitmap.Config.ARGB_8888);
        }
    }

    /** Размер картинки ярлыка: как у адаптивной иконки (108dp), но не больше 512px. */
    /** Что сейчас выбрано в списке обоев, с учётом своей картинки. */
    private String wallpaperChoice() {
        int i = Math.max(0, walls.getSelectedItemPosition());
        if (i >= WALLS.length - 1) {
            String own = Styler.prefs(this).getString(Style.KEY_OWN_WALL, "");
            return own == null ? "" : own;
        }
        return WALLS[i];
    }

    private int iconSize() {
        int px = Math.round(108 * getResources().getDisplayMetrics().density);
        return Math.min(512, Math.max(108, px));
    }

    private String labelOf(String pkg, String act) {
        try {
            ComponentName cn = new ComponentName(pkg, act);
            CharSequence l = getPackageManager().getActivityInfo(cn, 0).loadLabel(getPackageManager());
            return l == null ? pkg : l.toString();
        } catch (Throwable t) {
            return pkg;
        }
    }

    // ------------------------------------------------------------ украшения

    private ArrayAdapter<String> adapter(String[] items) {
        ArrayAdapter<String> a = new ArrayAdapter<>(this, android.R.layout.simple_spinner_item, items);
        a.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
        return a;
    }

    private TextView title(String s) {
        TextView t = new TextView(this);
        t.setText(s);
        t.setTextSize(22);
        t.setPadding(0, dp(8), 0, dp(8));
        return t;
    }

    private TextView label(String s) {
        TextView t = new TextView(this);
        t.setText(s);
        t.setTextSize(14);
        t.setPadding(0, dp(14), 0, dp(4));
        return t;
    }

    private TextView hint(String s) {
        TextView t = new TextView(this);
        t.setText(s);
        t.setTextSize(14);
        t.setPadding(0, dp(4), 0, dp(12));
        return t;
    }

    private Button button(String s, View.OnClickListener l) {
        Button b = new Button(this);
        b.setText(s);
        b.setOnClickListener(l);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        lp.topMargin = dp(6);
        b.setLayoutParams(lp);
        return b;
    }

    private int dp(int v) {
        return Math.round(v * getResources().getDisplayMetrics().density);
    }
}
