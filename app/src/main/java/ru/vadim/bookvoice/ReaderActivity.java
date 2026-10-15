package ru.vadim.bookvoice;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Context;
import android.content.SharedPreferences;
import android.graphics.Typeface;
import android.os.Bundle;
import android.speech.tts.TextToSpeech;
import android.speech.tts.UtteranceProgressListener;
import android.speech.tts.Voice;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.SeekBar;
import android.widget.TextView;
import android.widget.Toast;

import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** Reader with a system-TTS controller. Text never leaves the device. */
public final class ReaderActivity extends Activity implements TextToSpeech.OnInitListener {
    public static final String EXTRA_BOOK_ID = "book_id";
    private static final String TTS_PREFS = "bookvoice_tts";
    private static final String PREF_ENGINE = "engine";
    private static final String PREF_VOICE = "voice";
    private static final String PREF_RATE = "rate";

    private BookStore bookStore;
    private Book book;
    private SharedPreferences ttsPreferences;
    private ExecutorService worker;
    private TextToSpeech tts;
    private boolean ttsReady;
    private boolean speaking;
    private int speechSession;
    private int speechCursor;

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
        worker = Executors.newSingleThreadExecutor();
        String id = getIntent().getStringExtra(EXTRA_BOOK_ID);
        book = bookStore.getBook(id);
        if (book == null) {
            Toast.makeText(this, "Книга не найдена в библиотеке", Toast.LENGTH_SHORT).show();
            finish();
            return;
        }
        setContentView(createScreen());
        createTts(ttsPreferences.getString(PREF_ENGINE, ""));
        loadBook();
    }

    @Override
    protected void onPause() {
        saveReadingPosition();
        super.onPause();
    }

    @Override
    protected void onStop() {
        // Do not leave a second book talking if the user returns to the library or another app.
        stopSpeaking(false);
        super.onStop();
    }

    @Override
    protected void onDestroy() {
        stopSpeaking(false);
        if (tts != null) {
            tts.shutdown();
            tts = null;
        }
        if (worker != null) worker.shutdownNow();
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
        LinearLayout.LayoutParams headerTextParams = new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f);
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
        readerScroll.addView(pageText, new ScrollView.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
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
        voiceButton.setOnClickListener(view -> showVoicePicker());
        LinearLayout.LayoutParams voiceParams = new LinearLayout.LayoutParams(0, Ui.dp(this, 48), 0.8f);
        voiceParams.leftMargin = Ui.dp(this, 8);
        speakRow.addView(voiceButton, voiceParams);
        Button engineButton = Ui.button(this, "Движок", Ui.SAND, Ui.FOREST_DARK);
        engineButton.setOnClickListener(view -> showEnginePicker());
        LinearLayout.LayoutParams engineParams = new LinearLayout.LayoutParams(0, Ui.dp(this, 48), 0.95f);
        engineParams.leftMargin = Ui.dp(this, 8);
        speakRow.addView(engineButton, engineParams);
        LinearLayout.LayoutParams speakRowParams = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, Ui.dp(this, 48));
        speakRowParams.topMargin = Ui.dp(this, 6);
        controls.addView(speakRow, speakRowParams);

        LinearLayout ttsStatus = new LinearLayout(this);
        ttsStatus.setGravity(Gravity.CENTER_VERTICAL);
        voiceSummary = Ui.text(this, "Голос загружается…", 12, Ui.MUTED);
        voiceSummary.setMaxLines(1);
        voiceSummary.setEllipsize(android.text.TextUtils.TruncateAt.END);
        ttsStatus.addView(voiceSummary, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        speedSummary = Ui.text(this, "", 13, Ui.FOREST_DARK);
        speedSummary.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        speedSummary.setGravity(Gravity.CENTER);
        speedSummary.setPadding(Ui.dp(this, 10), Ui.dp(this, 5), Ui.dp(this, 10), Ui.dp(this, 5));
        speedSummary.setBackground(Ui.round(Ui.MINT, 10));
        speedSummary.setOnClickListener(view -> showSpeedPicker());
        speedSummary.setContentDescription("Изменить скорость озвучки");
        ttsStatus.addView(speedSummary, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        LinearLayout.LayoutParams ttsStatusParams = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        ttsStatusParams.topMargin = Ui.dp(this, 9);
        controls.addView(ttsStatus, ttsStatusParams);
        root.addView(controls);
        updateControls();
        return root;
    }

    private void loadBook() {
        statusView.setText("Открываем книгу и подготавливаем озвучку…");
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
                    statusView.setText(parserNote + "  •  можно читать или слушать");
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
        previousButton.setEnabled(enabled && currentPage > 1);
        nextButton.setEnabled(enabled && currentPage < totalPages);
        pageSeek.setEnabled(enabled);
        speakButton.setEnabled(enabled);
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

    private void createTts(String engine) {
        stopSpeaking(false);
        ttsReady = false;
        if (tts != null) {
            tts.shutdown();
            tts = null;
        }
        try {
            if (engine == null || engine.trim().isEmpty()) {
                tts = new TextToSpeech(this, this);
            } else {
                tts = new TextToSpeech(this, this, engine);
            }
            voiceSummary.setText("Подключаем движок озвучки…");
        } catch (Exception exception) {
            voiceSummary.setText("Озвучка недоступна: " + errorMessage(exception));
            updateControls();
        }
    }

    @Override
    public void onInit(int status) {
        runOnUiThread(() -> {
            if (status != TextToSpeech.SUCCESS || tts == null) {
                ttsReady = false;
                voiceSummary.setText("Не удалось запустить системную озвучку");
                updateControls();
                return;
            }
            ttsReady = true;
            tts.setOnUtteranceProgressListener(new UtteranceProgressListener() {
                @Override
                public void onStart(String utteranceId) {
                    runOnUiThread(() -> {
                        if (isCurrentUtterance(utteranceId)) {
                            statusView.setText("Озвучиваем книгу…");
                        }
                    });
                }

                @Override
                public void onDone(String utteranceId) {
                    runOnUiThread(() -> finishUtterance(utteranceId, null));
                }

                @Override
                public void onError(String utteranceId) {
                    runOnUiThread(() -> finishUtterance(utteranceId, "Движок не смог озвучить этот фрагмент"));
                }

                @Override
                public void onError(String utteranceId, int errorCode) {
                    runOnUiThread(() -> finishUtterance(utteranceId, "Ошибка озвучки (" + errorCode + ")"));
                }
            });
            applySavedTtsSettings();
            updateControls();
        });
    }

    private void applySavedTtsSettings() {
        if (!ttsReady || tts == null) return;
        float rate = ttsPreferences.getFloat(PREF_RATE, 1f);
        tts.setSpeechRate(clamp(rate, 0.6f, 1.5f));
        String savedVoice = ttsPreferences.getString(PREF_VOICE, "");
        Voice matchingVoice = voiceNamed(savedVoice);
        if (matchingVoice != null) {
            tts.setVoice(matchingVoice);
        } else if (savedVoice == null || savedVoice.isEmpty()) {
            Voice automatic = bestInstalledVoice();
            if (automatic != null && tts.setVoice(automatic) == TextToSpeech.SUCCESS) {
                ttsPreferences.edit().putString(PREF_VOICE, automatic.getName()).apply();
            }
        }
        refreshTtsLabels();
    }

    private void updateControls() {
        if (speakButton == null) return;
        boolean canSpeak = !fullText.trim().isEmpty() && ttsReady;
        speakButton.setEnabled(canSpeak);
        if (speaking) {
            speakButton.setText("❚❚ Пауза");
            speakButton.setBackgroundTintList(android.content.res.ColorStateList.valueOf(Ui.FOREST_DARK));
        } else {
            speakButton.setText("▶ Озвучить");
            speakButton.setBackgroundTintList(android.content.res.ColorStateList.valueOf(Ui.FOREST));
        }
        if (!ttsReady && voiceSummary != null && tts == null) {
            voiceSummary.setText("Озвучка недоступна на этом устройстве");
        }
        if (speedSummary != null) {
            speedSummary.setText(formatRate(ttsPreferences == null ? 1f : ttsPreferences.getFloat(PREF_RATE, 1f)));
        }
    }

    private void refreshTtsLabels() {
        if (voiceSummary == null) return;
        if (!ttsReady || tts == null) {
            voiceSummary.setText("Системная озвучка недоступна");
            return;
        }
        Voice voice = null;
        try {
            voice = tts.getVoice();
        } catch (Exception ignored) {
        }
        String engineName = tts.getDefaultEngine();
        if (voice == null) {
            voiceSummary.setText("Системный голос" + (engineName == null ? "" : " · " + engineName));
        } else {
            String mode = voice.isNetworkConnectionRequired() ? "сеть" : "офлайн";
            voiceSummary.setText(voice.getLocale().getDisplayName(new Locale("ru")) + " · " + qualityLabel(voice) + " · " + mode);
        }
        speedSummary.setText(formatRate(ttsPreferences.getFloat(PREF_RATE, 1f)));
    }

    private void toggleSpeech() {
        if (speaking) {
            stopSpeaking(true);
            return;
        }
        if (!ttsReady || tts == null) {
            Toast.makeText(this, "Системная озвучка ещё не готова", Toast.LENGTH_SHORT).show();
            return;
        }
        if (fullText.trim().isEmpty()) return;
        speaking = true;
        speechSession++;
        speechCursor = clamp(readingPosition, 0, Math.max(0, fullText.length() - 1));
        speakNext(speechSession);
        updateControls();
    }

    private void stopSpeaking(boolean announce) {
        speechSession++;
        boolean wasSpeaking = speaking;
        speaking = false;
        if (tts != null) {
            try {
                tts.stop();
            } catch (Exception ignored) {
            }
        }
        if (wasSpeaking && announce && statusView != null) statusView.setText("Пауза · продолжим с сохранённого места");
        updateControls();
        saveReadingPosition();
    }

    private void speakNext(int session) {
        if (!speaking || session != speechSession || tts == null) return;
        int length = fullText.length();
        while (speechCursor < length && Character.isWhitespace(fullText.charAt(speechCursor))) speechCursor++;
        if (speechCursor >= length) {
            speaking = false;
            readingPosition = Math.max(0, length - 1);
            currentPage = pageForPosition(readingPosition);
            saveReadingPosition();
            statusView.setText("Книга озвучена до конца");
            updateControls();
            return;
        }
        int maximum = Math.min(3_000, Math.max(800, TextToSpeech.getMaxSpeechInputLength() - 100));
        int end = safeSpeechEnd(speechCursor, maximum);
        String phrase = fullText.substring(speechCursor, end).trim();
        if (phrase.isEmpty()) {
            speechCursor = Math.min(length, end + 1);
            speakNext(session);
            return;
        }
        String utteranceId = session + ":" + end;
        Bundle params = new Bundle();
        params.putString(TextToSpeech.Engine.KEY_PARAM_UTTERANCE_ID, utteranceId);
        int result = tts.speak(phrase, TextToSpeech.QUEUE_FLUSH, params, utteranceId);
        if (result != TextToSpeech.SUCCESS) {
            finishUtterance(utteranceId, "Движок отказался начать озвучку");
        }
    }

    private int safeSpeechEnd(int start, int maximum) {
        int target = Math.min(fullText.length(), start + maximum);
        if (target >= fullText.length()) return target;
        int minimum = Math.min(target, start + Math.max(180, maximum / 3));
        for (int index = target; index > minimum; index--) {
            char character = fullText.charAt(index - 1);
            if (character == '.' || character == '!' || character == '?' || character == ';' || character == ':' || character == '\n') {
                return index;
            }
        }
        for (int index = target; index > minimum; index--) {
            if (Character.isWhitespace(fullText.charAt(index - 1))) return index;
        }
        return target;
    }

    private void finishUtterance(String utteranceId, String failure) {
        if (!isCurrentUtterance(utteranceId)) return;
        int separator = utteranceId.lastIndexOf(':');
        if (separator < 1) return;
        int nextPosition;
        try {
            nextPosition = Integer.parseInt(utteranceId.substring(separator + 1));
        } catch (NumberFormatException ignored) {
            return;
        }
        speechCursor = clamp(nextPosition, 0, fullText.length());
        readingPosition = Math.min(Math.max(0, fullText.length() - 1), speechCursor);
        int previousPage = currentPage;
        currentPage = pageForPosition(readingPosition);
        if (currentPage != previousPage) showPage(false);
        saveReadingPosition();
        if (failure != null) {
            speaking = false;
            statusView.setText(failure + " · позиция сохранена");
            updateControls();
            return;
        }
        speakNext(speechSession);
    }

    private boolean isCurrentUtterance(String utteranceId) {
        if (!speaking || utteranceId == null) return false;
        int separator = utteranceId.indexOf(':');
        if (separator < 1) return false;
        try {
            return Integer.parseInt(utteranceId.substring(0, separator)) == speechSession;
        } catch (NumberFormatException ignored) {
            return false;
        }
    }

    private void showVoicePicker() {
        if (!ttsReady || tts == null) {
            Toast.makeText(this, "Озвучка ещё не готова", Toast.LENGTH_SHORT).show();
            return;
        }
        final ArrayList<Voice> voices = installedVoices();
        if (voices.isEmpty()) {
            new AlertDialog.Builder(this)
                    .setTitle("Нет доступных голосов")
                    .setMessage("Установите голосовые пакеты в системных настройках Android → Синтез речи, затем вернитесь в приложение.")
                    .setNegativeButton("Отмена", null)
                    .setPositiveButton("Настройки", (dialog, which) -> {
                        try {
                            startActivity(new android.content.Intent(android.speech.tts.TextToSpeech.Engine.ACTION_INSTALL_TTS_DATA));
                        } catch (Exception ignored) {
                            startActivity(new android.content.Intent(android.provider.Settings.ACTION_SETTINGS));
                        }
                    })
                    .show();
            return;
        }
        String[] labels = new String[voices.size()];
        int checked = -1;
        String saved = ttsPreferences.getString(PREF_VOICE, "");
        for (int i = 0; i < voices.size(); i++) {
            Voice voice = voices.get(i);
            labels[i] = voice.getLocale().getDisplayName(new Locale("ru")) + " — " + qualityLabel(voice)
                    + (voice.isNetworkConnectionRequired() ? " · сеть" : " · офлайн");
            if (voice.getName().equals(saved)) checked = i;
        }
        final AlertDialog dialog = new AlertDialog.Builder(this)
                .setTitle("Выберите бесплатный системный голос")
                .setSingleChoiceItems(labels, checked, null)
                .setNegativeButton("Отмена", null)
                .create();
        dialog.setOnShowListener(ignored -> dialog.getListView().setOnItemClickListener((parent, view, position, id) -> {
            Voice selected = voices.get(position);
            stopSpeaking(false);
            int result = tts.setVoice(selected);
            if (result == TextToSpeech.SUCCESS) {
                ttsPreferences.edit().putString(PREF_VOICE, selected.getName()).apply();
                refreshTtsLabels();
                Toast.makeText(this, "Голос выбран", Toast.LENGTH_SHORT).show();
                dialog.dismiss();
            } else {
                Toast.makeText(this, "Этот голос пока недоступен", Toast.LENGTH_SHORT).show();
            }
        }));
        dialog.show();
    }

    private void showEnginePicker() {
        if (tts == null) return;
        final List<TextToSpeech.EngineInfo> engines = tts.getEngines();
        if (engines == null || engines.isEmpty()) {
            Toast.makeText(this, "На устройстве не найден TTS-движок", Toast.LENGTH_SHORT).show();
            return;
        }
        String active = ttsPreferences.getString(PREF_ENGINE, "");
        String[] labels = new String[engines.size()];
        int checked = 0;
        for (int i = 0; i < engines.size(); i++) {
            TextToSpeech.EngineInfo engine = engines.get(i);
            labels[i] = engine.label == null ? engine.name : engine.label.toString();
            if (engine.name.equals(active)) checked = i;
        }
        new AlertDialog.Builder(this)
                .setTitle("Движок озвучки")
                .setSingleChoiceItems(labels, checked, (dialog, which) -> {
                    String selectedEngine = engines.get(which).name;
                    ttsPreferences.edit().putString(PREF_ENGINE, selectedEngine).remove(PREF_VOICE).apply();
                    dialog.dismiss();
                    createTts(selectedEngine);
                })
                .setNegativeButton("Отмена", null)
                .show();
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
                    float selected = speeds[which];
                    ttsPreferences.edit().putFloat(PREF_RATE, selected).apply();
                    if (ttsReady && tts != null) tts.setSpeechRate(selected);
                    refreshTtsLabels();
                    dialog.dismiss();
                })
                .setNegativeButton("Отмена", null)
                .show();
    }

    private ArrayList<Voice> installedVoices() {
        ArrayList<Voice> list = new ArrayList<>();
        try {
            Set<Voice> source = tts.getVoices();
            if (source != null) {
                for (Voice voice : source) {
                    // getVoices() returns the voices currently exposed by the selected engine.
                    if (voice != null) list.add(voice);
                }
            }
        } catch (Exception ignored) {
        }
        Collections.sort(list, new Comparator<Voice>() {
            @Override
            public int compare(Voice first, Voice second) {
                boolean firstLocale = first.getLocale().getLanguage().equals(Locale.getDefault().getLanguage());
                boolean secondLocale = second.getLocale().getLanguage().equals(Locale.getDefault().getLanguage());
                if (firstLocale != secondLocale) return firstLocale ? -1 : 1;
                int quality = Integer.compare(second.getQuality(), first.getQuality());
                if (quality != 0) return quality;
                if (first.isNetworkConnectionRequired() != second.isNetworkConnectionRequired()) {
                    return first.isNetworkConnectionRequired() ? 1 : -1;
                }
                return first.getName().compareToIgnoreCase(second.getName());
            }
        });
        return list;
    }

    private Voice bestInstalledVoice() {
        ArrayList<Voice> voices = installedVoices();
        return voices.isEmpty() ? null : voices.get(0);
    }

    private Voice voiceNamed(String name) {
        if (name == null || name.isEmpty() || tts == null) return null;
        try {
            Set<Voice> voices = tts.getVoices();
            if (voices != null) {
                for (Voice voice : voices) if (name.equals(voice.getName())) return voice;
            }
        } catch (Exception ignored) {
        }
        return null;
    }

    private static String qualityLabel(Voice voice) {
        if (voice.getQuality() >= Voice.QUALITY_VERY_HIGH) return "очень высокое качество";
        if (voice.getQuality() >= Voice.QUALITY_HIGH) return "высокое качество";
        if (voice.getQuality() >= Voice.QUALITY_NORMAL) return "стандартное качество";
        return "базовое качество";
    }

    private static String formatRate(float rate) {
        return String.format(Locale.US, "%.2f×", rate).replace(".00", "").replace('.', ',');
    }

    private static int clamp(int value, int lower, int upper) {
        return Math.max(lower, Math.min(upper, value));
    }

    private static float clamp(float value, float lower, float upper) {
        return Math.max(lower, Math.min(upper, value));
    }

    private static String errorMessage(Exception exception) {
        String message = exception.getMessage();
        return message == null || message.trim().isEmpty() ? "неизвестная ошибка" : message;
    }
}
