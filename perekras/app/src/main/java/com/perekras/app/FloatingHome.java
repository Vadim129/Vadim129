package com.perekras.app;

import android.app.Activity;
import android.content.BroadcastReceiver;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.graphics.Bitmap;
import android.graphics.Color;
import android.graphics.drawable.ColorDrawable;
import android.os.Build;
import android.os.Bundle;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.AdapterView;
import android.widget.BaseAdapter;
import android.widget.GridView;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import java.util.ArrayList;
import java.util.List;

/**
 * Необязательный собственный рабочий стол: все приложения в одном стиле
 * и на выбранных обоях. Работает как обычный домашний экран, если выбрать
 * его в настройках; иначе открывается как обычное окно для проверки.
 */
public class FloatingHome extends Activity {

    public static final String ACTION_REFRESH = "com.perekras.app.REFRESH";

    private GridView grid;
    private final List<Apps.Row> rows = new ArrayList<>();
    private HomeAdapter adapter;
    private BroadcastReceiver receiver;
    private int iconPx;

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        iconPx = Math.round(64 * getResources().getDisplayMetrics().density);

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(Color.BLACK);

        grid = new GridView(this);
        grid.setNumColumns(GridView.AUTO_FIT);
        grid.setColumnWidth(iconPx + dp(28));
        grid.setVerticalSpacing(dp(12));
        grid.setHorizontalSpacing(dp(4));
        grid.setPadding(dp(10), dp(28), dp(10), dp(10));
        grid.setStretchMode(GridView.STRETCH_COLUMN_WIDTH);
        grid.setBackgroundColor(Color.TRANSPARENT);
        adapter = new HomeAdapter();
        grid.setAdapter(adapter);
        grid.setOnItemClickListener(new AdapterView.OnItemClickListener() {
            @Override
            public void onItemClick(AdapterView<?> parent, View v, int pos, long id) {
                Apps.Row r = rows.get(pos);
                if (!Apps.launch(FloatingHome.this, r.pkg, r.act)) {
                    Toast.makeText(FloatingHome.this, "Не удалось запустить",
                            Toast.LENGTH_SHORT).show();
                }
            }
        });
        grid.setOnItemLongClickListener(new AdapterView.OnItemLongClickListener() {
            @Override
            public boolean onItemLongClick(AdapterView<?> parent, View v, int pos, long id) {
                Apps.Row r = rows.get(pos);
                Toast.makeText(FloatingHome.this,
                        r.pkg + "\nоткрыть настройки стиля — «Перекрас» в списке приложений",
                        Toast.LENGTH_LONG).show();
                return true;
            }
        });
        root.addView(grid, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));

        LinearLayout bar = new LinearLayout(this);
        bar.setOrientation(LinearLayout.HORIZONTAL);
        bar.setPadding(dp(8), dp(6), dp(8), dp(28));
        bar.addView(barButton("Перекрас", new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                startActivity(new Intent(FloatingHome.this, MainActivity.class));
            }
        }));
        bar.addView(barButton("Все приложения", new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                startActivity(new Intent(FloatingHome.this, AppsActivity.class));
            }
        }));
        root.addView(bar);

        setContentView(root);
        receiver = new BroadcastReceiver() {
            @Override
            public void onReceive(Context c, Intent i) {
                reload();
            }
        };

        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT);
        root.setLayoutParams(lp);
    }

    @Override
    protected void onResume() {
        super.onResume();
        IntentFilter f = new IntentFilter(ACTION_REFRESH);
        if (Build.VERSION.SDK_INT >= 33) {
            registerReceiver(receiver, f, Context.RECEIVER_NOT_EXPORTED);
        } else {
            registerReceiver(receiver, f);
        }
        reload();
    }

    @Override
    protected void onPause() {
        super.onPause();
        try {
            unregisterReceiver(receiver);
        } catch (Throwable ignored) {
        }
    }

    private void reload() {
        rows.clear();
        String json = Styler.styleJson(this);
        int form = Style.form(json);

        // сначала то, что человек перекрасил и закрепил
        for (String k : Apps.picked(this)) {
            String[] pa = Apps.split(k);
            if (pa == null) continue;
            rows.add(new Apps.Row(pa[0], pa[1], label(pa[0], pa[1]), null));
        }
        if (rows.isEmpty()) {
            for (Apps.Row r : Apps.installed(this)) rows.add(r);
        }

        Bitmap wall = Styler.wallpaper(this, Style.wallpaper(json));
        if (wall != null) {
            grid.setBackground(new android.graphics.drawable.BitmapDrawable(getResources(), wall));
        } else {
            grid.setBackground(new ColorDrawable(Style.bg(Style.palette(json))));
        }
        adapter.notifyDataSetChanged();
        setTitle(Style.FORM_TITLES[Math.max(0, Math.min(form, Style.FORM_TITLES.length - 1))]);
    }

    private String label(String pkg, String act) {
        try {
            CharSequence l = getPackageManager()
                    .getActivityInfo(new ComponentName(pkg, act), 0)
                    .loadLabel(getPackageManager());
            return l == null ? pkg : l.toString();
        } catch (Throwable t) {
            return pkg;
        }
    }

    private TextView barButton(String text, View.OnClickListener l) {
        TextView t = new TextView(this);
        t.setText(text);
        t.setTextSize(14);
        t.setGravity(Gravity.CENTER);
        t.setPadding(dp(10), dp(10), dp(10), dp(10));
        t.setOnClickListener(l);
        t.setLayoutParams(new LinearLayout.LayoutParams(0,
                ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        return t;
    }

    private int dp(int v) {
        return Math.round(v * getResources().getDisplayMetrics().density);
    }

    private class HomeAdapter extends BaseAdapter {
        @Override
        public int getCount() {
            return rows.size();
        }

        @Override
        public Object getItem(int i) {
            return rows.get(i);
        }

        @Override
        public long getItemId(int i) {
            return i;
        }

        @Override
        public View getView(int pos, View reuse, ViewGroup parent) {
            LinearLayout box = new LinearLayout(FloatingHome.this);
            box.setOrientation(LinearLayout.VERTICAL);
            box.setGravity(Gravity.CENTER_HORIZONTAL);
            Apps.Row r = rows.get(pos);

            ImageView iv = new ImageView(FloatingHome.this);
            iv.setLayoutParams(new LinearLayout.LayoutParams(iconPx, iconPx));
            Bitmap b = Apps.styled(FloatingHome.this, r.pkg, r.act,
                    Math.max(1, Math.round(192f * getResources().getDisplayMetrics().density / 3f)));
            int form = Style.form(Styler.styleJson(FloatingHome.this));
            Bitmap shown = Styler.masked(FloatingHome.this, b,
                    "home__" + r.pkg + "__" + r.act, form);
            iv.setImageBitmap(shown);
            box.addView(iv);

            TextView tv = new TextView(FloatingHome.this);
            tv.setText(r.label);
            tv.setTextSize(12);
            tv.setGravity(Gravity.CENTER);
            tv.setTextColor(Color.WHITE);
            tv.setMaxLines(1);
            tv.setPadding(0, dp(4), 0, 0);
            box.addView(tv);
            box.setBackgroundColor(Color.TRANSPARENT);
            return box;
        }
    }
}
