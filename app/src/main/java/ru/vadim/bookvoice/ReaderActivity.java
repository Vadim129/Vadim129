package ru.vadim.bookvoice;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Typeface;
import android.net.Uri;
import android.os.Bundle;
import android.text.InputType;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.SeekBar;
import android.widget.TextView;
import android.widget.Toast;

import java.util.ArrayList;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** Reader backed exclusively by the user's Gemini TTS configuration. */
public final class ReaderActivity extends Activity {
    public static final String EXTRA_BOOK_ID = "book_id";
    private static final String TTS_PREFS = "bookvoice_tts";
    private static final String PREF_GEMINI_VOICE = "gemini_voice";
    private static final String PREF_RATE = "rate";
    private static final String SECRET_GEMINI_KEY = "gemini_api_key";
    private static final int GEMINI_CHUNK_CHARS = 440;

    private BookStore bookStore;
    private Book book;
    private SharedPreferences ttsPreferences;
    private SecretStore secretStore;
    private ExecutorService worker;
    private ExecutorService speechWorker;
    private GeminiTtsEngine gemini;
    private volatile boolean speaking;
    private volatile int speechSession;
    private boolean readerReady;

    private String fullText = "";
    private String parserNote = "";
    private int totalPages = 1;
    private int currentPage = 1;
    private int readingPosition;
    private boolean adjustingSeek;

    private TextView titleView;
    private TextView statusView;
    private TextView pageText;
    private TextView pageCounter;
    private TextView voiceSummary;
    private TextView speedSummary;
    private Button speakButton;
    private Button previousButton;
    private Button nextButton;
    private SeekBar pageSeek;
    private ScrollView readerScroll;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().setStatusBarColor(Ui.PAPER);
        getWindow().setNavigationBarColor(Ui.PAPER);
        getWindow().getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR);
        bookStore = new BookStore(this);
        ttsPreferences = getSharedPreferences(TTS_PREFS, Context.MODE_PRIVATE);
        secretStore = new SecretStore(this);
        worker = Executors.newSingleThreadExecutor();
        speechWorker = Executors.newSingleThreadExecutor();
        gemini = new GeminiTtsEngine();
        String id = getIntent().getStringExtra(EXTRA_BOOK_ID);
        book = bookStore.getBook(id);
        if (book == null) {
            Toast.makeText(this, "Книга не найдена в библиотеке", Toast.LENGTH_SHORT).show();
            finish();
            return;
        }
        setContentView(createScreen());
        refreshTtsLabels();
        loadBook();
    }

    @Override
    protected void onPause() {
        saveReadingPosition();
        super.onPause();
    }

    @Override
    protected void onStop() {
        stopSpeaking(false);
        super.onStop();
    }

    @Override
    protected void onDestroy() {
        stopSpeaking(false);
        if (worker != null) worker.shutdownNow();
        if (speechWorker != null) speechWorker.shutdownNow();
        super.onDestroy();
    }

    private View createScreen() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(Ui.PAPER);

        LinearLayout header = new LinearLayout(this);
        header.setGravity(Gravity.CENTER_VERTICAL);
        header.setPadding(Ui.dp(this, 12), Ui.dp(this, 10), Ui.dp(this, 16), Ui.dp(this, 8));
        Button back = Ui.button(this, "‹", Ui.SAND, Ui.FOREST_DARK);
        back.setTextSize(28);
        back.setPadding(0, 0, 0, Ui.dp(this, 3));
        back.setContentDescription("Вернуться в библиотеку");
        back.setOnClickListener(view -> finish());
        header.addView(back, new LinearLayout.LayoutParams(Ui.dp(this, 48), Ui.dp(this, 46)));

        LinearLayout headerTexts = new LinearLayout(this);
        headerTexts.setOrientation(LinearLayout.VERTICAL);
        titleView = Ui.heading(this, book.title, 18);
        titleView.setMaxLines(1);
        titleView.setEllipsize(android.text.TextUtils.TruncateAt.END);
        TextView subtitle = Ui.text(this, book.format + " · место чтения сохранится автоматически", 12, Ui.MUTED);
        headerTexts.addView(titleView);
        headerTexts.addView(subtitle);
        LinearLayout.LayoutParams headerTextParams = new LinearLayout.LayoutParams(0,
                ViewGroup.LayoutParams.WRAP_CONTENT, 1f);
        headerTextParams.leftMargin = Ui.dp(this, 10);
        header.addView(headerTexts, headerTextParams);
        root.addView(header);

        statusView = Ui.text(this, "Открываем книгу…", 13, Ui.FOREST_DARK);
        statusView.setPadding(Ui.dp(this, 20), Ui.dp(this, 4), Ui.dp(this, 20), Ui.dp(this, 8));
        root.addView(statusView);

        readerScroll = new ScrollView(this);
        readerScroll.setFillViewport(true);
        pageText = Ui.text(this, "", 20, Ui.INK);
        pageText.setTextIsSelectable(true);
        pageText.setLineSpacing(Ui.dp(this, 6), 1.05f);
        pageText.setPadding(Ui.dp(this, 22), Ui.dp(this, 18), Ui.dp(this, 22), Ui.dp(this, 28));
        readerScroll.addView(pageText, new ScrollView.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT));
        root.addView(readerScroll, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));

        LinearLayout controls = new LinearLayout(this);
        controls.setOrientation(LinearLayout.VERTICAL);
        controls.setPadding(Ui.dp(this, 16), Ui.dp(this, 10), Ui.dp(this, 16), Ui.dp(this, 12));
        controls.setBackground(Ui.outlined(Ui.PAPER, Ui.LINE, 0));

        LinearLayout navigation = new LinearLayout(this);
        navigation.setGravity(Gravity.CENTER_VERTICAL);
        previousButton = Ui.button(this, "‹ Назад", Ui.SAND, Ui.FOREST_DARK);
        previousButton.setOnClickListener(view -> goToPage(currentPage - 1));
        navigation.addView(previousButton, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, Ui.dp(this, 44)));
        pageCounter = Ui.text(this, "Страница 1 из 1", 14, Ui.INK);
        pageCounter.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        pageCounter.setGravity(Gravity.CENTER);
        navigation.addView(pageCounter, new LinearLayout.LayoutParams(0, Ui.dp(this, 44), 1f));
        nextButton = Ui.button(this, "Вперёд ›", Ui.SAND, Ui.FOREST_DARK);
        nextButton.setOnClickListener(view -> goToPage(currentPage + 1));
        navigation.addView(nextButton, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, Ui.dp(this, 44)));
        controls.addView(navigation);

        pageSeek = new SeekBar(this);
        pageSeek.setMax(0);
        pageSeek.setProgressTintList(android.content.res.ColorStateList.valueOf(Ui.FOREST));
        pageSeek.setThumbTintList(android.content.res.ColorStateList.valueOf(Ui.FOREST));
        pageSeek.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener() {
            @Override
            public void onProgressChanged(SeekBar seekBar, int progress, boolean fromUser) {
                if (fromUser && !adjustingSeek) goToPage(progress + 1);
            }

            @Override
            public void onStartTrackingTouch(SeekBar seekBar) {
            }

            @Override
            public void onStopTrackingTouch(SeekBar seekBar) {
            }
        });
        controls.addView(pageSeek, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, Ui.dp(this, 28)));

        LinearLayout speakRow = new LinearLayout(this);
        speakRow.setGravity(Gravity.CENTER_VERTICAL);
        speakButton = Ui.button(this, "▶ Озвучить", Ui.FOREST, Ui.PAPER);
        speakButton.setOnClickListener(view -> toggleSpeech());
        speakRow.addView(speakButton, new LinearLayout.LayoutParams(0, Ui.dp(this, 48), 1.35f));
        Button voiceButton = Ui.button(this, "Голос", Ui.MINT, Ui.FOREST_DARK);
        voiceButton.setOnClickListener(view -> showGeminiVoicePicker());
        LinearLayout.LayoutParams voiceParams = new LinearLayout.LayoutParams(0, Ui.dp(this, 48), 0.8f);
        voiceParams.leftMargin = Ui.dp(this, 8);
        speakRow.addView(voiceButton, voiceParams);
        Button settingsButton = Ui.button(this, "Ключ", Ui.SAND, Ui.FOREST_DARK);
        settingsButton.setContentDescription("Настроить или удалить Gemini API ключ");
        settingsButton.setOnClickListener(view -> showGeminiSetup());
        LinearLayout.LayoutParams settingsParams = new LinearLayout.LayoutParams(0, Ui.dp(this, 48), 0.75f);
        settingsParams.leftMargin = Ui.dp(this, 8);
        speakRow.addView(settingsButton, settingsParams);
        LinearLayout.LayoutParams speakRowParams = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, Ui.dp(this, 48));
        speakRowParams.topMargin = Ui.dp(this, 6);
        controls.addView(speakRow, speakRowParams);

        LinearLayout ttsStatus = new LinearLayout(this);
        ttsStatus.setGravity(Gravity.CENTER_VERTICAL);
        voiceSummary = Ui.text(this, "Gemini AI загружается…", 12, Ui.MUTED);
        voiceSummary.setMaxLines(1);
        voiceSummary.setEllipsize(android.text.TextUtils.TruncateAt.END);
        voiceSummary.setOnClickListener(view -> showGeminiSetup());
        ttsStatus.addView(voiceSummary, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        speedSummary = Ui.text(this, "", 13, Ui.FOREST_DARK);
        speedSummary.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        speedSummary.setGravity(Gravity.CENTER);
        speedSummary.setPadding(Ui.dp(this, 10), Ui.dp(this, 5), Ui.dp(this, 10), Ui.dp(this, 5));
        speedSummary.setBackground(Ui.round(Ui.MINT, 10));
        speedSummary.setOnClickListener(view -> showSpeedPicker());
        speedSummary.setContentDescription("Изменить скорость озвучки");
        ttsStatus.addView(speedSummary, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT,
                ViewGroup.LayoutParams.WRAP_CONTENT));
        LinearLayout.LayoutParams ttsStatusParams = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT);
        ttsStatusParams.topMargin = Ui.dp(this, 9);
        controls.addView(ttsStatus, ttsStatusParams);
        root.addView(controls);
        updateControls();
        return root;
    }

    private void loadBook() {
        statusView.setText("Открываем книгу и подготавливаем Gemini AI…");
        worker.execute(() -> {
            try {
                final BookParser.ParsedBook parsed = BookParser.parse(getApplicationContext(), book);
                runOnUiThread(() -> {
                    fullText = parsed.text;
                    parserNote = parsed.note;
                    totalPages = parsed.pageCount;
                    if (fullText.trim().isEmpty()) {
                        statusView.setText("В этом PDF не найден текстовый слой");
                        pageText.setText("Эта PDF-книга выглядит как скан или содержит только изображения. "
                                + "Чтобы читать и слушать её в приложении, сначала создайте текстовую версию с OCR.");
                        setReaderEnabled(false);
                        saveReadingPosition();
                        return;
                    }
                    readingPosition = clamp(book.position, 0, Math.max(0, fullText.length() - 1));
                    currentPage = pageForPosition(readingPosition);
                    statusView.setText(parserNote + "  •  можно читать или слушать Gemini AI");
                    setReaderEnabled(true);
                    showPage(false);
                    saveReadingPosition();
                });
            } catch (final Exception error) {
                runOnUiThread(() -> {
                    statusView.setText("Не удалось открыть книгу");
                    pageText.setText("Ошибка открытия:\n" + errorMessage(error)
                            + "\n\nПопробуйте удалить книгу из библиотеки и импортировать исходный файл ещё раз.");
                    setReaderEnabled(false);
                });
            }
        });
    }

    private void setReaderEnabled(boolean enabled) {
        readerReady = enabled;
        previousButton.setEnabled(enabled && currentPage > 1);
        nextButton.setEnabled(enabled && currentPage < totalPages);
        pageSeek.setEnabled(enabled);
        if (enabled) {
            adjustingSeek = true;
            pageSeek.setMax(Math.max(0, totalPages - 1));
            pageSeek.setProgress(Math.max(0, currentPage - 1));
            adjustingSeek = false;
        }
        updateControls();
    }

    private void goToPage(int requestedPage) {
        if (fullText.isEmpty()) return;
        stopSpeaking(false);
        currentPage = clamp(requestedPage, 1, totalPages);
        readingPosition = Math.min(fullText.length() - 1, (currentPage - 1) * BookParser.PAGE_CHARACTERS);
        showPage(true);
    }

    private void showPage(boolean persist) {
        if (fullText.isEmpty()) return;
        currentPage = pageForPosition(readingPosition);
        int start = (currentPage - 1) * BookParser.PAGE_CHARACTERS;
        int end = Math.min(fullText.length(), start + BookParser.PAGE_CHARACTERS);
        pageText.setText(fullText.substring(start, end));
        pageCounter.setText("Страница " + currentPage + " из " + totalPages);
        previousButton.setEnabled(currentPage > 1);
        nextButton.setEnabled(currentPage < totalPages);
        adjustingSeek = true;
        pageSeek.setMax(Math.max(0, totalPages - 1));
        pageSeek.setProgress(Math.max(0, currentPage - 1));
        adjustingSeek = false;
        readerScroll.post(() -> readerScroll.fullScroll(View.FOCUS_UP));
        if (persist) saveReadingPosition();
    }

    private int pageForPosition(int position) {
        return clamp((position / BookParser.PAGE_CHARACTERS) + 1, 1, totalPages);
    }

    private void saveReadingPosition() {
        if (book == null || fullText.isEmpty()) return;
        bookStore.saveReadingState(book, readingPosition, currentPage, totalPages);
    }

    private void updateControls() {
        if (speakButton == null) return;
        speakButton.setEnabled(readerReady && !fullText.trim().isEmpty());
        if (speaking) {
            speakButton.setText("■ Остановить");
            speakButton.setBackgroundTintList(android.content.res.ColorStateList.valueOf(Ui.FOREST_DARK));
        } else {
            speakButton.setText("▶ Озвучить");
            speakButton.setBackgroundTintList(android.content.res.ColorStateList.valueOf(Ui.FOREST));
        }
        if (speedSummary != null) speedSummary.setText(formatRate(ttsPreferences.getFloat(PREF_RATE, 1f)));
    }

    private void refreshTtsLabels() {
        if (voiceSummary == null) return;
        String key = secretStore == null ? "" : secretStore.get(SECRET_GEMINI_KEY);
        String voice = ttsPreferences.getString(PREF_GEMINI_VOICE, "Kore");
        voiceSummary.setText(key.isEmpty()
                ? "Gemini AI · добавьте личный API-ключ"
                : "Gemini 3.8 Flash-Lite · " + voice + " · очередь 3 фразы");
        if (speedSummary != null) speedSummary.setText(formatRate(ttsPreferences.getFloat(PREF_RATE, 1f)));
    }

    private void toggleSpeech() {
        if (speaking) {
            stopSpeaking(true);
            return;
        }
        if (!readerReady || fullText.trim().isEmpty()) return;
        if (secretStore.get(SECRET_GEMINI_KEY).isEmpty()) {
            showGeminiSetup();
            return;
        }
        startGeminiSpeech();
    }

    private void startGeminiSpeech() {
        speaking = true;
        speechSession++;
        final int session = speechSession;
        final int start = clamp(readingPosition, 0, Math.max(0, fullText.length() - 1));
        statusView.setText("Gemini готовит первые 3 фразы…");
        updateControls();
        speechWorker.execute(() -> runGeminiSpeech(session, start));
    }

    private void runGeminiSpeech(final int session, int start) {
        try {
            SpeechPlan plan = makeSpeechPlan(start);
            if (plan.phrases.isEmpty()) {
                finishGeminiSpeech(session, null, true);
                return;
            }
            String apiKey = secretStore.get(SECRET_GEMINI_KEY);
            if (apiKey.isEmpty()) throw new IllegalStateException("Gemini API-ключ не найден");
            boolean complete = gemini.synthesizeAndPlayPrefetched(apiKey,
                    ttsPreferences.getString(PREF_GEMINI_VOICE, "Kore"), plan.phrases,
                    ttsPreferences.getFloat(PREF_RATE, 1f),
                    () -> isSpeechCancelled(session), index -> {
                        final int playedUntil = plan.ends.get(index);
                        runOnUiThread(() -> saveGeminiChunk(session, playedUntil));
                    });
            if (!complete || isSpeechCancelled(session)) return;
            finishGeminiSpeech(session, null, true);
        } catch (final Exception error) {
            finishGeminiSpeech(session, error, false);
        }
    }

    private SpeechPlan makeSpeechPlan(int start) {
        ArrayList<String> phrases = new ArrayList<>();
        ArrayList<Integer> ends = new ArrayList<>();
        int cursor = start;
        while (cursor < fullText.length()) {
            while (cursor < fullText.length() && Character.isWhitespace(fullText.charAt(cursor))) cursor++;
            if (cursor >= fullText.length()) break;
            int end = safeSpeechEnd(cursor, GEMINI_CHUNK_CHARS);
            String phrase = fullText.substring(cursor, end).trim();
            if (!phrase.isEmpty()) {
                phrases.add(phrase);
                ends.add(end);
            }
            cursor = Math.max(end, cursor + 1);
        }
        return new SpeechPlan(phrases, ends);
    }

    private boolean isSpeechCancelled(int session) {
        return !speaking || session != speechSession || isFinishing() || isDestroyed();
    }

    private void saveGeminiChunk(int session, int playedUntil) {
        if (isSpeechCancelled(session)) return;
        readingPosition = Math.min(Math.max(0, fullText.length() - 1),
                clamp(playedUntil, 0, fullText.length()));
        int previousPage = currentPage;
        currentPage = pageForPosition(readingPosition);
        if (currentPage != previousPage) showPage(false);
        statusView.setText("Озвучиваем · следующая фраза уже готовится…");
        saveReadingPosition();
    }

    private void finishGeminiSpeech(final int session, final Exception failure, final boolean complete) {
        runOnUiThread(() -> {
            if (session != speechSession) return;
            speaking = false;
            if (failure != null) {
                statusView.setText(errorMessage(failure) + " · позиция сохранена");
            } else if (complete) {
                readingPosition = Math.max(0, fullText.length() - 1);
                currentPage = pageForPosition(readingPosition);
                saveReadingPosition();
                statusView.setText("Книга озвучена до конца");
            }
            updateControls();
        });
    }

    private void stopSpeaking(boolean announce) {
        speechSession++;
        boolean wasSpeaking = speaking;
        speaking = false;
        if (gemini != null) gemini.stop();
        if (wasSpeaking && announce && statusView != null) {
            statusView.setText("Остановлено · продолжим с сохранённого места");
        }
        updateControls();
        saveReadingPosition();
    }

    private int safeSpeechEnd(int start, int maximum) {
        int target = Math.min(fullText.length(), start + maximum);
        if (target >= fullText.length()) return target;
        int minimum = Math.min(target, start + Math.max(180, maximum / 3));
        for (int index = target; index > minimum; index--) {
            char character = fullText.charAt(index - 1);
            if (character == '.' || character == '!' || character == '?' || character == ';'
                    || character == ':' || character == '\n') return index;
        }
        for (int index = target; index > minimum; index--) {
            if (Character.isWhitespace(fullText.charAt(index - 1))) return index;
        }
        return target;
    }

    private void showGeminiVoicePicker() {
        if (secretStore.get(SECRET_GEMINI_KEY).isEmpty()) {
            showGeminiSetup();
            return;
        }
        final String[] voices = new String[]{
                "Kore", "Aoede", "Leda", "Zephyr", "Puck", "Charon", "Fenrir", "Orus",
                "Callirrhoe", "Autonoe", "Enceladus", "Iapetus", "Umbriel", "Algieba", "Despina",
                "Erinome", "Algenib", "Rasalgethi", "Laomedeia", "Achernar", "Alnilam", "Schedar",
                "Gacrux", "Pulcherrima", "Achird", "Zubenelgenubi", "Vindemiatrix", "Sadachbia",
                "Sadaltager", "Sulafat"
        };
        String current = ttsPreferences.getString(PREF_GEMINI_VOICE, "Kore");
        int checked = 0;
        for (int index = 0; index < voices.length; index++) {
            if (voices[index].equals(current)) checked = index;
        }
        new AlertDialog.Builder(this)
                .setTitle("Голос Gemini AI · русский текст")
                .setSingleChoiceItems(voices, checked, (dialog, which) -> {
                    ttsPreferences.edit().putString(PREF_GEMINI_VOICE, voices[which]).apply();
                    refreshTtsLabels();
                    dialog.dismiss();
                })
                .setNeutralButton("Настроить ключ", (dialog, which) -> showGeminiSetup())
                .setNegativeButton("Отмена", null)
                .show();
    }

    private void showGeminiSetup() {
        LinearLayout content = new LinearLayout(this);
        content.setOrientation(LinearLayout.VERTICAL);
        int padding = Ui.dp(this, 22);
        content.setPadding(padding, Ui.dp(this, 8), padding, 0);

        TextView note = Ui.text(this,
                "Gemini озвучивает текст через ваш личный API-ключ. Только фрагменты, которые сейчас читаются, отправляются в Google.",
                14, Ui.INK);
        note.setLineSpacing(Ui.dp(this, 3), 1f);
        content.addView(note);

        TextView link = Ui.text(this, "Получить API-ключ: aistudio.google.com/apikey", 14, Ui.FOREST_DARK);
        link.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        link.getPaint().setUnderlineText(true);
        link.setContentDescription("Открыть Google AI Studio для получения API ключа");
        LinearLayout.LayoutParams linkParams = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT);
        linkParams.topMargin = Ui.dp(this, 12);
        content.addView(link, linkParams);
        link.setOnClickListener(view -> {
            try {
                startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse("https://aistudio.google.com/apikey")));
            } catch (Exception error) {
                Toast.makeText(this, "Не удалось открыть aistudio.google.com", Toast.LENGTH_SHORT).show();
            }
        });

        TextView caption = Ui.text(this, "Gemini API key", 13, Ui.MUTED);
        LinearLayout.LayoutParams captionParams = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT);
        captionParams.topMargin = Ui.dp(this, 16);
        content.addView(caption, captionParams);
        EditText keyField = new EditText(this);
        keyField.setSingleLine(true);
        keyField.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        keyField.setHint("AIza…");
        keyField.setText(secretStore.get(SECRET_GEMINI_KEY));
        content.addView(keyField, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT));

        String storageHint = secretStore.usesPrivateFallback(SECRET_GEMINI_KEY)
                ? "Android Keystore недоступен: ключ сохранён в закрытом зашифрованном хранилище приложения."
                : "Ключ хранится только на этом устройстве и шифруется Android Keystore.";
        TextView hint = Ui.text(this, storageHint, 12, Ui.MUTED);
        hint.setPadding(0, Ui.dp(this, 8), 0, 0);
        content.addView(hint);

        Button deleteKeyButton = Ui.button(this, "Удалить ключ с устройства", Ui.SAND, Ui.FOREST_DARK);
        LinearLayout.LayoutParams deleteParams = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,
                Ui.dp(this, 44));
        deleteParams.topMargin = Ui.dp(this, 14);
        content.addView(deleteKeyButton, deleteParams);
        deleteKeyButton.setEnabled(!keyField.getText().toString().trim().isEmpty());
        deleteKeyButton.setOnClickListener(view -> {
            secretStore.remove(SECRET_GEMINI_KEY);
            keyField.setText("");
            deleteKeyButton.setEnabled(false);
            refreshTtsLabels();
            Toast.makeText(this, "Gemini API-ключ удалён с устройства", Toast.LENGTH_SHORT).show();
        });

        final AlertDialog dialog = new AlertDialog.Builder(this)
                .setTitle("Gemini AI · ключ")
                .setView(content)
                .setNegativeButton("Закрыть", null)
                .setPositiveButton("Сохранить ключ", null)
                .create();
        dialog.setOnShowListener(ignored -> dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(view -> {
            String key = keyField.getText().toString().trim();
            if (key.length() < 12) {
                keyField.setError("Введите API-ключ из Google AI Studio");
                return;
            }
            try {
                boolean privateFallback = secretStore.put(SECRET_GEMINI_KEY, key);
                deleteKeyButton.setEnabled(true);
                refreshTtsLabels();
                Toast.makeText(this, privateFallback
                        ? "Ключ сохранён в закрытом хранилище приложения"
                        : "Gemini API-ключ сохранён", Toast.LENGTH_LONG).show();
                dialog.dismiss();
            } catch (Exception error) {
                keyField.setError("Не удалось сохранить ключ: " + errorMessage(error));
            }
        }));
        dialog.show();
    }

    private void showSpeedPicker() {
        final float[] speeds = new float[]{0.7f, 0.85f, 1.0f, 1.15f, 1.3f, 1.45f};
        String[] labels = new String[speeds.length];
        float saved = ttsPreferences.getFloat(PREF_RATE, 1f);
        int checked = 2;
        for (int i = 0; i < speeds.length; i++) {
            labels[i] = formatRate(speeds[i]);
            if (Math.abs(speeds[i] - saved) < 0.03f) checked = i;
        }
        new AlertDialog.Builder(this)
                .setTitle("Скорость озвучки")
                .setSingleChoiceItems(labels, checked, (dialog, which) -> {
                    ttsPreferences.edit().putFloat(PREF_RATE, speeds[which]).apply();
                    refreshTtsLabels();
                    dialog.dismiss();
                })
                .setNegativeButton("Отмена", null)
                .show();
    }

    private static String formatRate(float rate) {
        return String.format(Locale.US, "%.2f×", rate).replace(".00", "").replace('.', ',');
    }

    private static int clamp(int value, int lower, int upper) {
        return Math.max(lower, Math.min(upper, value));
    }

    private static String errorMessage(Exception exception) {
        String message = exception.getMessage();
        return message == null || message.trim().isEmpty() ? "неизвестная ошибка" : message;
    }

    private static final class SpeechPlan {
        final ArrayList<String> phrases;
        final ArrayList<Integer> ends;

        SpeechPlan(ArrayList<String> phrases, ArrayList<Integer> ends) {
            this.phrases = phrases;
            this.ends = ends;
        }
    }
}
