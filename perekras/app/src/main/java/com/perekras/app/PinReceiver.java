package com.perekras.app;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

/**
 * Срабатывает, когда рабочий стол добавил наш ярлык. Запоминаем приложение
 * в списке перекрашенных, чтобы потом можно было обновить оформление одной
 * кнопкой и показать всё в собственной панели.
 */
public class PinReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context c, Intent i) {
        if (i == null) return;
        String key = i.getStringExtra(Apps.EXTRA_KEY);
        if (key == null || key.isEmpty()) return;
        Apps.addPicked(c, key);
        Apps.notifyHome(c);
    }
}
