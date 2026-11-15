package com.perekras.app;

import android.app.Activity;
import android.graphics.Bitmap;
import android.os.Bundle;
import android.text.Editable;
import android.text.TextWatcher;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.AdapterView;
import android.widget.BaseAdapter;
import android.widget.Button;
import android.widget.EditText;
import android.widget.ListView;
import android.widget.TextView;
import android.widget.Toast;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/** Список приложений: отметить галочкой — перекрасить и закрепить ярлык. */
public class AppsActivity extends Activity {

    public static final String EXTRA_ICON_ID = "icon_id";

    private List<Apps.Row> all = new ArrayList<>();
    private final List<Apps.Row> shown = new ArrayList<>();
    private final List<String> marked = new ArrayList<>();
    private AppsAdapter adapter;
    private TextView counter;
    private EditText search;
    private String customIcon;

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        customIcon = getIntent().getStringExtra(EXTRA_ICON_ID);

        android.widget.LinearLayout root = new android.widget.LinearLayout(this);
        root.setOrientation(android.widget.LinearLayout.VERTICAL);
        int pad = dp(12);
        root.setPadding(pad, pad, pad, pad);

        TextView t = new TextView(this);
        t.setText(customIcon != null ? "Кому поставить свою картинку?" : "Что перекрасить?");
        t.setTextSize(20);
        root.addView(t);

        search = new EditText(this);
        search.setHint("Поиск по названию");
        search.setSingleLine(true);
        search.addTextChangedListener(new TextWatcher() {
            @Override
            public void beforeTextChanged(CharSequence s, int a, int b1, int c) {
            }

            @Override
            public void onTextChanged(CharSequence s, int a, int b1, int c) {
                filter(s.toString());
            }

            @Override
            public void afterTextChanged(Editable s) {
            }
        });
        root.addView(search);

        counter = new TextView(this);
        counter.setTextSize(13);
        root.addView(counter);

        ListView lv = new ListView(this);
        adapter = new AppsAdapter();
        lv.setAdapter(adapter);
        lv.setOnItemClickListener(new AdapterView.OnItemClickListener() {
            @Override
            public void onItemClick(AdapterView<?> parent, View v, int pos, long id) {
                toggle(shown.get(pos).key());
            }
        });
        root.addView(lv, new android.widget.LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));

        Button apply = new Button(this);
        apply.setText(customIcon != null ? "Поставить картинку" : "Перекрасить отмеченные");
        apply.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                apply();
            }
        });
        root.addView(apply);

        setContentView(root);
        reload();
    }

    private void reload() {
        all = Apps.installed(this);
        for (String k : Apps.picked(this)) {
            if (!marked.contains(k)) marked.add(k);
        }
        filter(search.getText().toString());
        updateCounter();
    }

    private void filter(String q) {
        String s = q == null ? "" : q.trim().toLowerCase(Locale.ROOT);
        shown.clear();
        for (Apps.Row r : all) {
            if (s.isEmpty() || r.label.toLowerCase(Locale.ROOT).contains(s)
                    || r.pkg.toLowerCase(Locale.ROOT).contains(s)) {
                shown.add(r);
            }
        }
        adapter.notifyDataSetChanged();
    }

    private void toggle(String key) {
        if (marked.contains(key)) marked.remove(key);
        else marked.add(key);
        adapter.notifyDataSetChanged();
        updateCounter();
    }

    private void updateCounter() {
        counter.setText("Отмечено: " + marked.size()
                + (Apps.canPin(this) ? " · ярлыки добавляются с подтверждением"
                                     : " · этот рабочий стол не умеет ярлыки")
                + (all.isEmpty() ? " · список приложений пуст — нужно разрешение" : ""));
    }

    private void apply() {
        if (marked.isEmpty()) {
            Toast.makeText(this, "Ничего не отмечено", Toast.LENGTH_SHORT).show();
            return;
        }
        int form = Style.form(Styler.styleJson(this));
        int pal = Style.palette(Styler.styleJson(this));
        int size = iconSize();
        int ok = 0;
        int noRoom = 0;
        for (String k : new ArrayList<>(marked)) {
            String[] pa = Apps.split(k);
            if (pa == null) continue;
            String pkg = pa[0];
            String act = pa[1];
            Bitmap art;
            if (customIcon != null) {
                Bitmap c = Media.load(this, customIcon);
                art = c == null ? Apps.iconOf(this, pkg, act, size) : Bitmap.createScaledBitmap(c, size, size, true);
            } else {
                art = Styler.make(this, Apps.iconOf(this, pkg, act, size), k, form, pal);
            }
            String label = labelOf(pkg, act);
            if (Apps.requestPin(this, pkg, act, art, label)) {
                ok++;
                if (customIcon != null) {
                    Apps.rememberIcon(this, k, customIcon);
                }
            } else {
                noRoom++;
            }
        }
        String msg = "Запрос отправлен: " + ok;
        if (noRoom > 0) msg += ", не поддержано: " + noRoom;
        Toast.makeText(this, msg, Toast.LENGTH_LONG).show();
        Apps.notifyHome(this);
        finish();
    }

    private String labelOf(String pkg, String act) {
        String k = Apps.key(pkg, act);
        for (Apps.Row r : all) if (r.key().equals(k)) return r.label;
        return pkg;
    }

    private int iconSize() {
        int px = Math.round(108 * getResources().getDisplayMetrics().density);
        return Math.min(512, Math.max(108, px));
    }

    private int dp(int v) {
        return Math.round(v * getResources().getDisplayMetrics().density);
    }

    // ------------------------------------------------------------- адаптер

    private class AppsAdapter extends BaseAdapter {
        @Override
        public int getCount() {
            return shown.size();
        }

        @Override
        public Object getItem(int i) {
            return shown.get(i);
        }

        @Override
        public long getItemId(int i) {
            return i;
        }

        @Override
        public View getView(int pos, View reuse, ViewGroup parent) {
            View v = reuse;
            if (v == null) {
                v = LayoutInflater.from(AppsActivity.this)
                        .inflate(android.R.layout.simple_list_item_2, parent, false);
            }
            Apps.Row r = shown.get(pos);
            TextView t1 = v.findViewById(android.R.id.text1);
            TextView t2 = v.findViewById(android.R.id.text2);
            boolean on = marked.contains(r.key());
            t1.setText((on ? "✓ " : "") + r.label);
            t2.setText(r.pkg + (Apps.picked(AppsActivity.this).contains(r.key()) ? " · уже есть" : ""));
            return v;
        }
    }
}
