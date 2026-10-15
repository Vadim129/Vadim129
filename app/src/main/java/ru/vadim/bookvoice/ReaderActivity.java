package ru.vadim.bookvoice;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Typeface;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.speech.tts.TextToSpeech;
import android.speech.tts.UtteranceProgressListener;
import android.speech.tts.Voice;
import android.text.SpannableString;
import android.text.Spanned;
import android.text.style.BackgroundColorSpan;
import android.text.style.ForegroundColorSpan;
import android.text.style.StyleSpan;
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
import java.util.Locale;
import java.util.Set;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** Reader backed only by Android's built-in text-to-speech service. */
public final class ReaderActivity extends Activity implements TextToSpeech.OnInitListener {
    public static final String EXTRA_BOOK_ID = "book_id";
    private static final String TTS_PREFS = "bookvoice_tts";
    private static final String PREF_SYSTEM_VOICE = "system_voice";
    private static final String PREF_RATE = "rate";
    private static final int SYSTEM_TTS_CHUNK_CHARS = 1_200;
    private static final long PROGRESS_SAVE_INTERVAL_MS = 1_500L;
    private static final String SYSTEM_UTTERANCE_PREFIX = "bookvoice-system:";

    private BookStore bookStore;
    private Book book;
    private SharedPreferences ttsPreferences;
    private ExecutorService worker;
    private TextToSpeech systemTts;
    private boolean systemTtsReady;
    private boolean reopenTtsAfterSettings;
    private SystemTtsSegment activeSystemSegment;
    private String activeUtteranceId;
    private int nextSystemPosition;
    private final Handler mainHandler = new Handler(Looper.getMainLooper());
    private Runnable systemFallbackHighlighter;
    private boolean systemRangeReported;
    private boolean speaking;
    private int speechSession;
    private boolean readerReady;
    private long lastProgressSaveAt;
    private int highlightedStart = -1;
    private int highlightedEnd = -1;

    private String fullText = "";
    private int totalPages = 1;
    private int currentPage = 1;
    private int readingPosition;
    private boolean adjustingSeek;

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
        createSystemTts();
        refreshTtsLabels();
        loadBook();
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (reopenTtsAfterSettings) {
            reopenTtsAfterSettings = false;
            shutdownSystemTts();
            createSystemTts();
        }
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
        shutdownSystemTts();
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
        TextView title = Ui.heading(this, book.title, 18);
        title.setMaxLines(1);
        title.setEllipsize(android.text.TextUtils.TruncateAt.END);
        TextView subtitle = Ui.text(this, book.format + " · место чтения сохранится автоматически", 12, Ui.MUTED);
        headerTexts.addView(title);
        headerTexts.addView(subtitle);
        LinearLayout.LayoutParams headerTextParams = new LinearLayout.LayoutParams(0,
                ViewGroup.LayoutParams.WRAP_CONTENT, 1f);
        headerTextParams.leftMargin = Ui.dp(this, 10);
        header.addView(headerTexts, headerTextParams);
        root.addView(header);

        statusView = Ui.text(this, "Открываем книгу и встроенную озвучку…", 13, Ui.FOREST_DARK);
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
        speakButton.setContentDescription("Начать или остановить встроенную Android-озвучку");
        speakButton.setOnClickListener(view -> toggleSpeech());
        speakRow.addView(speakButton, new LinearLayout.LayoutParams(0, Ui.dp(this, 48), 1.25f));
        Button voiceButton = Ui.button(this, "Голос", Ui.MINT, Ui.FOREST_DARK);
        voiceButton.setContentDescription("Выбрать русский системный голос Android");
        voiceButton.setOnClickListener(view -> showSystemVoicePicker());
        LinearLayout.LayoutParams voiceParams = new LinearLayout.LayoutParams(0, Ui.dp(this, 48), .75f);
        voiceParams.leftMargin = Ui.dp(this, 8);
        speakRow.addView(voiceButton, voiceParams);
        LinearLayout.LayoutParams speakRowParams = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,
                Ui.dp(this, 48));
        speakRowParams.topMargin = Ui.dp(this, 6);
        controls.addView(speakRow, speakRowParams);

        LinearLayout ttsStatus = new LinearLayout(this);
        ttsStatus.setGravity(Gravity.CENTER_VERTICAL);
        voiceSummary = Ui.text(this, "Встроенный Android TTS · загружается…", 12, Ui.MUTED);
        voiceSummary.setMaxLines(1);
        voiceSummary.setEllipsize(android.text.TextUtils.TruncateAt.END);
        voiceSummary.setContentDescription("Открыть выбор системного голоса Android");
        voiceSummary.setOnClickListener(view -> showSystemVoicePicker());
        ttsStatus.addView(voiceSummary, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        speedSummary = Ui.text(this, "", 13, Ui.FOREST_DARK);
        speedSummary.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        speedSummary.setGravity(Gravity.CENTER);
        speedSummary.setPadding(Ui.dp(this, 10), Ui.dp(this, 5), Ui.dp(this, 10), Ui.dp(this, 5));
        speedSummary.setBackground(Ui.round(Ui.MINT, 10));
        speedSummary.setOnClickListener(view -> showSpeedPicker());
        speedSummary.setContentDescription("Изменить скорость встроенной озвучки");
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
        worker.execute(() -> {
            try {
                final BookParser.ParsedBook parsed = BookParser.parse(getApplicationContext(), book);
                runOnUiThread(() -> {
                    fullText = parsed.text;
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
                    statusView.setText(parsed.note + "  •  можно читать или слушать встроенным голосом Android");
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
        renderCurrentPage();
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

    /** Repaints only the visible page with the word or range currently being read. */
    private void renderCurrentPage() {
        if (pageText == null || fullText.isEmpty()) return;
        int pageStart = Math.max(0, (currentPage - 1) * BookParser.PAGE_CHARACTERS);
        int pageEnd = Math.min(fullText.length(), pageStart + BookParser.PAGE_CHARACTERS);
        SpannableString rendered = new SpannableString(fullText.substring(pageStart, pageEnd));
        if (speaking && readingPosition >= pageStart && readingPosition < pageEnd) {
            int start = highlightedStart;
            int end = highlightedEnd;
            if (start < pageStart || end <= start || start >= pageEnd) {
                int[] word = wordRangeAt(readingPosition, pageStart, pageEnd);
                start = word[0];
                end = word[1];
            }
            int localStart = clamp(start, pageStart, pageEnd) - pageStart;
            int localEnd = clamp(end, pageStart, pageEnd) - pageStart;
            if (localEnd > localStart) {
                rendered.setSpan(new BackgroundColorSpan(Ui.MINT), localStart, localEnd,
                        Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
                rendered.setSpan(new ForegroundColorSpan(Ui.FOREST_DARK), localStart, localEnd,
                        Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
                rendered.setSpan(new StyleSpan(Typeface.BOLD), localStart, localEnd,
                        Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
            }
        }
        pageText.setText(rendered);
    }

    private int[] wordRangeAt(int position, int lower, int upper) {
        int cursor = clamp(position, lower, Math.max(lower, upper - 1));
        int start = cursor;
        int end = cursor;
        while (start > lower && isWordCharacter(fullText.charAt(start - 1))) start--;
        while (end < upper && isWordCharacter(fullText.charAt(end))) end++;
        if (end <= start) end = Math.min(upper, start + 1);
        return new int[]{start, end};
    }

    private static boolean isWordCharacter(char character) {
        return Character.isLetterOrDigit(character) || character == '\'' || character == '’'
                || character == '-';
    }

    private int pageForPosition(int position) {
        return clamp((position / BookParser.PAGE_CHARACTERS) + 1, 1, totalPages);
    }

    private int skipWhitespace(int position) {
        int cursor = clamp(position, 0, fullText.length());
        while (cursor < fullText.length() && Character.isWhitespace(fullText.charAt(cursor))) cursor++;
        return cursor;
    }

    private void saveReadingPosition() {
        if (book == null || fullText.isEmpty()) return;
        bookStore.saveReadingState(book, readingPosition, currentPage, totalPages);
    }

    private void updateControls() {
        if (speakButton == null) return;
        speakButton.setEnabled(readerReady && !fullText.trim().isEmpty() && systemTtsReady);
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
        if (systemTts == null) {
            voiceSummary.setText("Встроенный Android TTS недоступен · нажмите для настроек");
        } else if (!systemTtsReady) {
            voiceSummary.setText("Встроенный Android TTS · загружается или ждёт русский голос…");
        } else {
            Voice voice = null;
            try {
                voice = systemTts.getVoice();
            } catch (Exception ignored) {
            }
            String details = voice == null ? "русский системный голос" : voice.getName();
            voiceSummary.setText("Встроенный Android TTS · " + details);
        }
        if (speedSummary != null) speedSummary.setText(formatRate(ttsPreferences.getFloat(PREF_RATE, 1f)));
    }

    private void toggleSpeech() {
        if (speaking) {
            stopSpeaking(true);
        } else {
            startSystemSpeech();
        }
    }

    private void startSystemSpeech() {
        if (!readerReady || fullText.trim().isEmpty()) return;
        if (!systemTtsReady || systemTts == null) {
            showSystemTtsSetup();
            return;
        }
        int start = skipWhitespace(readingPosition);
        if (start >= fullText.length()) {
            finishSystemSpeech(++speechSession, null, true);
            return;
        }
        speaking = true;
        speechSession++;
        int session = speechSession;
        activeSystemSegment = null;
        activeUtteranceId = null;
        nextSystemPosition = start;
        highlightedStart = start;
        highlightedEnd = Math.min(fullText.length(), start + 1);
        clearSystemFallbackHighlight();
        systemRangeReported = false;
        lastProgressSaveAt = 0L;
        try {
            systemTts.setSpeechRate(ttsPreferences.getFloat(PREF_RATE, 1f));
        } catch (Exception error) {
            finishSystemSpeech(session, error, false);
            return;
        }
        renderCurrentPage();
        statusView.setText("Встроенный Android TTS начинает чтение · текст будет подсвечиваться…");
        updateControls();
        speakNextSystemSegment(session);
    }

    /** Builds and queues only one Android-TTS segment at a time to keep large books lightweight. */
    private void speakNextSystemSegment(int session) {
        if (session != speechSession || !speaking) return;
        if (systemTts == null || !systemTtsReady) {
            finishSystemSpeech(session, new IllegalStateException("Встроенный Android TTS недоступен"), false);
            return;
        }
        int start = skipWhitespace(nextSystemPosition);
        if (start >= fullText.length()) {
            finishSystemSpeech(session, null, true);
            return;
        }
        int maximum = Math.min(SYSTEM_TTS_CHUNK_CHARS,
                Math.max(400, TextToSpeech.getMaxSpeechInputLength() - 100));
        int next = safeSpeechEnd(start, maximum);
        int end = next;
        while (end > start && Character.isWhitespace(fullText.charAt(end - 1))) end--;
        if (end <= start) {
            nextSystemPosition = Math.max(start + 1, next);
            speakNextSystemSegment(session);
            return;
        }
        activeSystemSegment = new SystemTtsSegment(start, end, fullText.substring(start, end));
        nextSystemPosition = skipWhitespace(Math.max(next, start + 1));
        activeUtteranceId = SYSTEM_UTTERANCE_PREFIX + session + ":" + start;
        Bundle params = new Bundle();
        params.putString(TextToSpeech.Engine.KEY_PARAM_UTTERANCE_ID, activeUtteranceId);
        int result;
        try {
            result = systemTts.speak(activeSystemSegment.text, TextToSpeech.QUEUE_FLUSH, params, activeUtteranceId);
        } catch (Exception error) {
            finishSystemSpeech(session, error, false);
            return;
        }
        if (result != TextToSpeech.SUCCESS) {
            finishSystemSpeech(session,
                    new IllegalStateException("Встроенный Android TTS отказался начать озвучку"), false);
        }
    }

    private void finishSystemUtterance(String utteranceId, Exception failure) {
        SystemTtsSegment segment = activeSegmentFor(utteranceId);
        if (segment == null) return;
        int session = speechSession;
        clearSystemFallbackHighlight();
        systemRangeReported = false;
        activeSystemSegment = null;
        activeUtteranceId = null;
        if (failure != null) {
            finishSystemSpeech(session, failure, false);
            return;
        }
        saveSpeechProgress(session, segment.end, true, Math.max(segment.start, segment.end - 1), segment.end,
                "Встроенный Android TTS читает · текст подсвечен…");
        speakNextSystemSegment(session);
    }

    private SystemTtsSegment activeSegmentFor(String utteranceId) {
        if (!speaking || activeSystemSegment == null || activeUtteranceId == null
                || !activeUtteranceId.equals(utteranceId)) return null;
        return activeSystemSegment;
    }

    /**
     * Engines that implement onRangeStart provide exact word/range highlighting.
     * Older engines get a deliberately conservative, rate-aware moving fallback.
     */
    private void startSystemFallbackHighlight(final int session, final String utteranceId,
                                              final SystemTtsSegment segment) {
        clearSystemFallbackHighlight();
        systemRangeReported = false;
        final long startedAt = SystemClock.elapsedRealtime();
        final float rate = Math.max(.7f, Math.min(1.4f, ttsPreferences.getFloat(PREF_RATE, 1f)));
        final long expectedDuration = Math.max(1_500L,
                Math.round((segment.end - segment.start) * 1_000f / (14f * rate)));
        systemFallbackHighlighter = new Runnable() {
            @Override
            public void run() {
                if (systemFallbackHighlighter != this || systemRangeReported || !speaking
                        || session != speechSession || activeSystemSegment != segment
                        || !utteranceId.equals(activeUtteranceId)) return;
                long elapsed = SystemClock.elapsedRealtime() - startedAt;
                float fraction = Math.max(0f, Math.min(.97f, elapsed / (float) expectedDuration));
                int position = segment.start + Math.round((segment.end - segment.start) * fraction);
                saveSpeechProgress(session, position, false, -1, -1,
                        "Встроенный Android TTS читает · текст подсвечен…");
                mainHandler.postDelayed(this, 700L);
            }
        };
        mainHandler.postDelayed(systemFallbackHighlighter, 650L);
    }

    private void clearSystemFallbackHighlight() {
        if (systemFallbackHighlighter != null) {
            mainHandler.removeCallbacks(systemFallbackHighlighter);
            systemFallbackHighlighter = null;
        }
    }

    private void saveSpeechProgress(int session, int sourcePosition, boolean segmentFinished,
                                    int spokenStart, int spokenEnd, String status) {
        if (!speaking || session != speechSession || fullText.isEmpty()) return;
        int bounded = Math.min(Math.max(0, fullText.length() - 1),
                clamp(sourcePosition, 0, fullText.length()));
        // A late exact onRangeStart must be allowed to correct the estimated fallback position.
        if (!segmentFinished && bounded < readingPosition && spokenStart < 0) return;
        readingPosition = bounded;
        if (spokenStart >= 0 && spokenEnd > spokenStart) {
            highlightedStart = spokenStart;
            highlightedEnd = spokenEnd;
        } else {
            int[] word = wordRangeAt(readingPosition, 0, fullText.length());
            highlightedStart = word[0];
            highlightedEnd = word[1];
        }
        int previousPage = currentPage;
        currentPage = pageForPosition(readingPosition);
        if (currentPage != previousPage) {
            showPage(false);
        } else {
            renderCurrentPage();
        }
        statusView.setText(status);
        long now = SystemClock.elapsedRealtime();
        if (segmentFinished || now - lastProgressSaveAt >= PROGRESS_SAVE_INTERVAL_MS) {
            lastProgressSaveAt = now;
            saveReadingPosition();
        }
    }

    private void finishSystemSpeech(final int session, final Exception failure, final boolean complete) {
        runOnUiThread(() -> {
            if (session != speechSession) return;
            speaking = false;
            clearSystemFallbackHighlight();
            systemRangeReported = false;
            activeSystemSegment = null;
            activeUtteranceId = null;
            highlightedStart = -1;
            highlightedEnd = -1;
            if (failure != null) {
                statusView.setText(errorMessage(failure) + " · позиция сохранена");
            } else if (complete) {
                readingPosition = Math.max(0, fullText.length() - 1);
                currentPage = pageForPosition(readingPosition);
                saveReadingPosition();
                statusView.setText("Книга озвучена до конца");
            }
            renderCurrentPage();
            updateControls();
        });
    }

    private void stopSpeaking(boolean announce) {
        speechSession++;
        boolean wasSpeaking = speaking;
        speaking = false;
        if (systemTts != null) {
            try {
                systemTts.stop();
            } catch (Exception ignored) {
            }
        }
        clearSystemFallbackHighlight();
        systemRangeReported = false;
        activeSystemSegment = null;
        activeUtteranceId = null;
        highlightedStart = -1;
        highlightedEnd = -1;
        renderCurrentPage();
        if (wasSpeaking && announce && statusView != null) {
            statusView.setText("Остановлено · продолжим с сохранённого места");
        }
        updateControls();
        saveReadingPosition();
    }

    private void createSystemTts() {
        systemTtsReady = false;
        try {
            systemTts = new TextToSpeech(getApplicationContext(), this);
        } catch (Exception error) {
            systemTts = null;
            if (voiceSummary != null) {
                voiceSummary.setText("Не удалось запустить встроенный Android TTS: " + errorMessage(error));
            }
            updateControls();
        }
    }

    private void shutdownSystemTts() {
        systemTtsReady = false;
        clearSystemFallbackHighlight();
        if (systemTts != null) {
            try {
                systemTts.stop();
                systemTts.shutdown();
            } catch (Exception ignored) {
            }
            systemTts = null;
        }
    }

    @Override
    public void onInit(int status) {
        runOnUiThread(() -> {
            if (status != TextToSpeech.SUCCESS || systemTts == null) {
                systemTtsReady = false;
                if (voiceSummary != null) {
                    voiceSummary.setText("Не удалось запустить встроенный Android TTS · нажмите для настроек");
                }
                updateControls();
                return;
            }
            try {
                systemTts.setOnUtteranceProgressListener(new UtteranceProgressListener() {
                    @Override
                    public void onStart(String utteranceId) {
                        runOnUiThread(() -> {
                            SystemTtsSegment segment = activeSegmentFor(utteranceId);
                            if (segment == null || systemRangeReported) return;
                            saveSpeechProgress(speechSession, segment.start, false, segment.start,
                                    Math.min(segment.end, segment.start + 1),
                                    "Встроенный Android TTS читает · текст подсвечен…");
                            startSystemFallbackHighlight(speechSession, utteranceId, segment);
                        });
                    }

                    @Override
                    public void onDone(String utteranceId) {
                        runOnUiThread(() -> finishSystemUtterance(utteranceId, null));
                    }

                    @Override
                    public void onError(String utteranceId) {
                        runOnUiThread(() -> finishSystemUtterance(utteranceId,
                                new IllegalStateException("Встроенный Android TTS не смог озвучить фрагмент")));
                    }

                    @Override
                    public void onError(String utteranceId, int errorCode) {
                        runOnUiThread(() -> finishSystemUtterance(utteranceId,
                                new IllegalStateException("Ошибка встроенного Android TTS (" + errorCode + ")")));
                    }

                    @Override
                    public void onRangeStart(String utteranceId, int start, int end, int frame) {
                        runOnUiThread(() -> {
                            SystemTtsSegment segment = activeSegmentFor(utteranceId);
                            if (segment == null) return;
                            systemRangeReported = true;
                            clearSystemFallbackHighlight();
                            int absoluteStart = clamp(segment.start + Math.max(0, start), segment.start, segment.end);
                            int absoluteEnd = clamp(segment.start + Math.max(start, end), absoluteStart, segment.end);
                            saveSpeechProgress(speechSession, absoluteStart, false, absoluteStart, absoluteEnd,
                                    "Встроенный Android TTS читает · текст подсвечен…");
                        });
                    }
                });
                int language = systemTts.setLanguage(new Locale("ru", "RU"));
                systemTtsReady = language != TextToSpeech.LANG_MISSING_DATA
                        && language != TextToSpeech.LANG_NOT_SUPPORTED;
                if (systemTtsReady) applySavedSystemTtsSettings();
            } catch (Exception error) {
                systemTtsReady = false;
                if (voiceSummary != null) {
                    voiceSummary.setText("Встроенный Android TTS недоступен: " + errorMessage(error));
                }
            }
            refreshTtsLabels();
            updateControls();
        });
    }

    private void applySavedSystemTtsSettings() {
        if (!systemTtsReady || systemTts == null) return;
        try {
            systemTts.setSpeechRate(ttsPreferences.getFloat(PREF_RATE, 1f));
            Voice saved = systemVoiceNamed(ttsPreferences.getString(PREF_SYSTEM_VOICE, ""));
            if (saved != null && systemTts.setVoice(saved) == TextToSpeech.SUCCESS) return;
            Voice automatic = bestRussianSystemVoice();
            if (automatic != null && systemTts.setVoice(automatic) == TextToSpeech.SUCCESS) {
                ttsPreferences.edit().putString(PREF_SYSTEM_VOICE, automatic.getName()).apply();
            }
        } catch (Exception ignored) {
            // The engine can still use the Russian language selected in onInit.
        }
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

    private void showSystemVoicePicker() {
        if (!systemTtsReady || systemTts == null) {
            showSystemTtsSetup();
            return;
        }
        final ArrayList<Voice> voices = russianSystemVoices();
        if (voices.isEmpty()) {
            new AlertDialog.Builder(this)
                    .setTitle("Русский голос Android TTS")
                    .setMessage("Этот речевой движок не показал список русских голосов. Он может использовать системный голос по умолчанию. Для загрузки или выбора голоса откройте настройки Android.")
                    .setNegativeButton("Закрыть", null)
                    .setPositiveButton("Настройки Android", (dialog, which) -> openSystemTtsSettings())
                    .show();
            return;
        }
        String saved = ttsPreferences.getString(PREF_SYSTEM_VOICE, "");
        String[] labels = new String[voices.size()];
        int checked = 0;
        for (int index = 0; index < voices.size(); index++) {
            Voice voice = voices.get(index);
            labels[index] = voice.getName() + (voice.isNetworkConnectionRequired()
                    ? " · сеть" : " · устройство");
            if (voice.getName().equals(saved)) checked = index;
        }
        new AlertDialog.Builder(this)
                .setTitle("Русский голос Android TTS")
                .setSingleChoiceItems(labels, checked, (dialog, which) -> {
                    Voice voice = voices.get(which);
                    stopSpeaking(false);
                    try {
                        if (systemTts.setVoice(voice) == TextToSpeech.SUCCESS) {
                            ttsPreferences.edit().putString(PREF_SYSTEM_VOICE, voice.getName()).apply();
                            refreshTtsLabels();
                            Toast.makeText(this, "Системный голос выбран", Toast.LENGTH_SHORT).show();
                            dialog.dismiss();
                        } else {
                            Toast.makeText(this, "Этот системный голос недоступен", Toast.LENGTH_SHORT).show();
                        }
                    } catch (Exception error) {
                        Toast.makeText(this, "Не удалось выбрать голос", Toast.LENGTH_SHORT).show();
                    }
                })
                .setNeutralButton("Настройки Android", (dialog, which) -> openSystemTtsSettings())
                .setNegativeButton("Отмена", null)
                .show();
    }

    private void showSystemTtsSetup() {
        new AlertDialog.Builder(this)
                .setTitle("Встроенный Android TTS")
                .setMessage("На телефоне не найден готовый русский системный голос. Установите или включите его в настройках синтеза речи Android, затем вернитесь в приложение.")
                .setNegativeButton("Отмена", null)
                .setPositiveButton("Настройки Android", (dialog, which) -> openSystemTtsSettings())
                .show();
    }

    private void openSystemTtsSettings() {
        reopenTtsAfterSettings = true;
        try {
            startActivity(new Intent("com.android.settings.TTS_SETTINGS"));
        } catch (Exception ignored) {
            try {
                startActivity(new Intent(TextToSpeech.Engine.ACTION_INSTALL_TTS_DATA));
            } catch (Exception error) {
                reopenTtsAfterSettings = false;
                Toast.makeText(this, "Не удалось открыть настройки Android TTS", Toast.LENGTH_SHORT).show();
            }
        }
    }

    private ArrayList<Voice> russianSystemVoices() {
        ArrayList<Voice> voices = new ArrayList<>();
        if (systemTts == null) return voices;
        try {
            Set<Voice> source = systemTts.getVoices();
            if (source != null) {
                for (Voice voice : source) {
                    if (voice != null && voice.getLocale() != null
                            && "ru".equalsIgnoreCase(voice.getLocale().getLanguage())) {
                        voices.add(voice);
                    }
                }
            }
        } catch (Exception ignored) {
        }
        Collections.sort(voices, new Comparator<Voice>() {
            @Override
            public int compare(Voice first, Voice second) {
                if (first.isNetworkConnectionRequired() != second.isNetworkConnectionRequired()) {
                    return first.isNetworkConnectionRequired() ? 1 : -1;
                }
                int quality = Integer.compare(second.getQuality(), first.getQuality());
                return quality != 0 ? quality : first.getName().compareToIgnoreCase(second.getName());
            }
        });
        return voices;
    }

    private Voice bestRussianSystemVoice() {
        ArrayList<Voice> voices = russianSystemVoices();
        return voices.isEmpty() ? null : voices.get(0);
    }

    private Voice systemVoiceNamed(String name) {
        if (name == null || name.isEmpty() || systemTts == null) return null;
        try {
            Set<Voice> voices = systemTts.getVoices();
            if (voices != null) {
                for (Voice voice : voices) {
                    if (voice != null && name.equals(voice.getName())) return voice;
                }
            }
        } catch (Exception ignored) {
        }
        return null;
    }

    private void showSpeedPicker() {
        final float[] speeds = new float[]{.7f, .85f, 1f, 1.15f, 1.3f, 1.45f};
        String[] labels = new String[speeds.length];
        float saved = ttsPreferences.getFloat(PREF_RATE, 1f);
        int checked = 2;
        for (int index = 0; index < speeds.length; index++) {
            labels[index] = formatRate(speeds[index]);
            if (Math.abs(speeds[index] - saved) < .03f) checked = index;
        }
        new AlertDialog.Builder(this)
                .setTitle("Скорость озвучки")
                .setSingleChoiceItems(labels, checked, (dialog, which) -> {
                    float selected = speeds[which];
                    ttsPreferences.edit().putFloat(PREF_RATE, selected).apply();
                    if (systemTtsReady && systemTts != null) {
                        try {
                            systemTts.setSpeechRate(selected);
                        } catch (Exception ignored) {
                        }
                    }
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

    private static final class SystemTtsSegment {
        final int start;
        final int end;
        final String text;

        SystemTtsSegment(int start, int end, String text) {
            this.start = start;
            this.end = end;
            this.text = text;
        }
    }
}
