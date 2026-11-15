package com.perekras.app;

import android.app.Activity;
import android.os.Bundle;
import android.view.Gravity;
import android.view.ViewGroup;
import android.widget.TextView;

/** Запускается лаунчером, когда применена тема. Ничего не показывает. */
public class EmptyActivity extends Activity {
    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        TextView t = new TextView(this);
        t.setText("Перекрас: тема применена");
        t.setGravity(Gravity.CENTER);
        setContentView(t);
        finish();
    }
}
