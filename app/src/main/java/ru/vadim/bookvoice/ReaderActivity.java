package ru.vadim.bookvoice;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Typeface;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.speech.tts.TextToSpeech;
import android.speech.tts.UtteranceProgressListener;
import android.speech.tts.Voice;
import android.text.InputType;
import android.text.SpannableString;
import android.text.Spanned;
import android.text.style.BackgroundColorSpan;
import android.text.style.ForegroundColorSpan;
import android.text.style.StyleSpan;
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
import java.util.Collections;
import java.util.Comparator;
import java.util.Locale;
import java.util.Set;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** Reader offering quota-efficient Gemini TTS and the phone's built-in Android TTS. */
public final class ReaderActivity extends Activity implements TextToSpeech.OnInitListener {
    public static final String EXTRA_BOOK_ID = "book_id";
    private static final String TTS_PREFS = "bookvoice_tts";
    private static final String PREF_PROVIDER = "provider";
    private static final String PREF_GEMINI_VOICE = "gemini_voice";
    private static final String PREF_SYSTEM_VOICE = "system_voice";
    private static final String PREF_RATE = "rate";
    private static final String PROVIDER_GEMINI = "gemini";
    private static final String PROVIDER_SYSTEM = "system";
    private static final String SECRET_GEMINI_KEY = "gemini_api_key";
    // Near the practical GenerateContent TTS limit while staying viable on phone RAM.
    private static final int GEMINI_CHUNK_CHARS = 8_000;
    private static final int SYSTEM_TTS_CHUNK_CHARS = 1_200;
    private static final long PROGRESS_SAVE_INTERVAL_MS = 1_500L;
    private static final String SYSTEM_UTTERANCE_PREFIX = "bookvoice-system:";

    private BookStore bookStore;
    private Book book;
    private SharedPreferences ttsPreferences;
    private SecretStore secretStore;
    private ExecutorService worker;
    private ExecutorService speechWorker;
    private GeminiTtsEngine gemini;
    private GeminiAudioCache audioCache;
    private TextToSpeech systemTts;
    private boolean systemTtsReady;
    private ArrayList<SystemTtsSegment> systemSpeechPlan;
    private final Handler mainHandler = new Handler(Looper.getMainLooper());
    private Runnable systemFallbackHighlighter;
    private boolean systemRangeReported;
    private volatile boolean speaking;
    private volatile int speechSession;
    private boolean readerReady;
    private long lastProgressSaveAt;
    private int highlightedStart = -1;
    private int highlightedEnd = -1;

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
    private Button modeButton;
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
        audioCache = new GeminiAudioCache(this, book.id);
        setContentView(createScreen());
        createSystemTts();
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
        shutdownSystemTts();
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
        modeButton = Ui.button(this, "AI", Ui.SAND, Ui.FOREST_DARK);
        modeButton.setContentDescription("Выбрать Gemini AI или встроенный Android TTS");
        modeButton.setOnClickListener(view -> showProviderPicker());
        LinearLayout.LayoutParams modeParams = new LinearLayout.LayoutParams(0, Ui.dp(this, 48), 0.45f);
        modeParams.leftMargin = Ui.dp(this, 8);
        speakRow.addView(modeButton, modeParams);
        Button voiceButton = Ui.button(this, "Голос", Ui.MINT, Ui.FOREST_DARK);
        voiceButton.setOnClickListener(view -> showVoicePicker());
        LinearLayout.LayoutParams voiceParams = new LinearLayout.LayoutParams(0, Ui.dp(this, 48), 0.75f);
        voiceParams.leftMargin = Ui.dp(this, 8);
        speakRow.addView(voiceButton, voiceParams);
        Button settingsButton = Ui.button(this, "Ключ", Ui.SAND, Ui.FOREST_DARK);
        settingsButton.setContentDescription("Настроить или удалить Gemini API ключ");
        settingsButton.setOnClickListener(view -> showGeminiSetup());
        LinearLayout.LayoutParams settingsParams = new LinearLayout.LayoutParams(0, Ui.dp(this, 48), 0.55f);
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
        voiceSummary.setOnClickListener(view -> showVoicePicker());
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
                    statusView.setText(parserNote + "  •  можно читать или слушать выбранным голосом");
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

    /** Repaints only the visible page with the word/range currently being spoken. */
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

    private void saveReadingPosition() {
        if (book == null || fullText.isEmpty()) return;
        bookStore.saveReadingState(book, readingPosition, currentPage, totalPages);
    }

    private boolean isSystemProvider() {
        return PROVIDER_SYSTEM.equals(ttsPreferences.getString(PREF_PROVIDER, PROVIDER_GEMINI));
    }

    private void updateControls() {
        if (speakButton == null) return;
        boolean ready = !isSystemProvider() || systemTtsReady;
        speakButton.setEnabled(readerReady && !fullText.trim().isEmpty() && ready);
        if (speaking) {
            speakButton.setText("■ Остановить");
            speakButton.setBackgroundTintList(android.content.res.ColorStateList.valueOf(Ui.FOREST_DARK));
        } else {
            speakButton.setText("▶ Озвучить");
            speakButton.setBackgroundTintList(android.content.res.ColorStateList.valueOf(Ui.FOREST));
        }
        if (modeButton != null) modeButton.setText(isSystemProvider() ? "TTS" : "AI");
        if (speedSummary != null) speedSummary.setText(formatRate(ttsPreferences.getFloat(PREF_RATE, 1f)));
    }

    private void refreshTtsLabels() {
        if (voiceSummary == null) return;
        if (isSystemProvider()) {
            if (!systemTtsReady || systemTts == null) {
                voiceSummary.setText("Встроенный Android TTS · загружается…");
            } else {
                Voice voice = null;
                try {
                    voice = systemTts.getVoice();
                } catch (Exception ignored) {
                }
                String details = voice == null ? "системный голос" : voice.getName();
                voiceSummary.setText("Встроенный Android TTS · " + details);
            }
        } else {
            String key = secretStore == null ? "" : secretStore.get(SECRET_GEMINI_KEY);
            String voice = ttsPreferences.getString(PREF_GEMINI_VOICE, "Kore");
            voiceSummary.setText(key.isEmpty()
                    ? "Gemini AI · добавьте личный API-ключ"
                    : "Gemini 3.8 Flash-Lite · " + voice + " · длинный текст + кэш");
        }
        if (speedSummary != null) speedSummary.setText(formatRate(ttsPreferences.getFloat(PREF_RATE, 1f)));
        if (modeButton != null) modeButton.setText(isSystemProvider() ? "TTS" : "AI");
    }

    private void toggleSpeech() {
        if (speaking) {
            stopSpeaking(true);
            return;
        }
        if (!readerReady || fullText.trim().isEmpty()) return;
        if (isSystemProvider()) {
            startSystemSpeech();
            return;
        }
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
        highlightedStart = start;
        highlightedEnd = Math.min(fullText.length(), start + 1);
        renderCurrentPage();
        lastProgressSaveAt = 0L;
        statusView.setText("Gemini готовит максимально длинный фрагмент и сохранит аудио…");
        updateControls();
        speechWorker.execute(() -> runGeminiSpeech(session, start));
    }

    private void runGeminiSpeech(final int session, int start) {
        try {
            final String voice = ttsPreferences.getString(PREF_GEMINI_VOICE, "Kore");
            final SpeechPlan plan = makeSpeechPlan(start, voice);
            if (plan.segments.isEmpty()) {
                finishGeminiSpeech(session, null, true);
                return;
            }
            String apiKey = secretStore.get(SECRET_GEMINI_KEY);
            if (apiKey.isEmpty()) throw new IllegalStateException("Gemini API-ключ не найден");
            final long[] lastProgressPostedAt = new long[]{0L};
            boolean complete = gemini.synthesizeAndPlayPrefetched(apiKey, voice, plan.segments,
                    ttsPreferences.getFloat(PREF_RATE, 1f), audioCache,
                    () -> isSpeechCancelled(session), (index, fraction) -> {
                        GeminiTtsEngine.Segment segment = plan.segments.get(index);
                        long now = SystemClock.elapsedRealtime();
                        if (fraction < 0.999f && now - lastProgressPostedAt[0] < 700L) return;
                        lastProgressPostedAt[0] = now;
                        final int sourcePosition = segment.start + Math.round(
                                (segment.end - segment.start) * Math.max(0f, Math.min(1f, fraction)));
                        final boolean segmentFinished = fraction >= 0.999f;
                        runOnUiThread(() -> saveGeminiProgress(session, sourcePosition, segmentFinished));
                    });
            if (!complete || isSpeechCancelled(session)) return;
            finishGeminiSpeech(session, null, true);
        } catch (final Exception error) {
            finishGeminiSpeech(session, error, false);
        }
    }

    private SpeechPlan makeSpeechPlan(int start, String voice) {
        ArrayList<GeminiTtsEngine.Segment> segments = new ArrayList<>();
        int cursor = skipWhitespace(start);
        // A resume point inside a previously saved long passage starts directly from its local PCM.
        if (audioCache != null && cursor < fullText.length()) {
            GeminiAudioCache.Hit hit = audioCache.findCovering(voice, fullText, cursor);
            if (hit != null && hit.end > cursor) {
                String cachedText = fullText.substring(hit.start, hit.end);
                segments.add(new GeminiTtsEngine.Segment(hit.start, hit.end, cachedText,
                        hit.offsetBytes, hit.pcm));
                cursor = hit.end;
            }
        }
        while (cursor < fullText.length()) {
            cursor = skipWhitespace(cursor);
            if (cursor >= fullText.length()) break;
            int nextCursor = safeSpeechEnd(cursor, GEMINI_CHUNK_CHARS);
            int end = nextCursor;
            while (end > cursor && Character.isWhitespace(fullText.charAt(end - 1))) end--;
            if (end > cursor) {
                segments.add(new GeminiTtsEngine.Segment(cursor, end, fullText.substring(cursor, end)));
            }
            cursor = Math.max(nextCursor, cursor + 1);
        }
        return new SpeechPlan(segments);
    }

    private int skipWhitespace(int position) {
        int cursor = clamp(position, 0, fullText.length());
        while (cursor < fullText.length() && Character.isWhitespace(fullText.charAt(cursor))) cursor++;
        return cursor;
    }

    private boolean isSpeechCancelled(int session) {
        return !speaking || session != speechSession || isFinishing() || isDestroyed();
    }

    private void saveGeminiProgress(int session, int sourcePosition, boolean segmentFinished) {
        saveSpeechProgress(session, sourcePosition, segmentFinished, -1, -1,
                "Gemini читает · текст подсвечен, аудио сохраняется…");
    }

    private void saveSpeechProgress(int session, int sourcePosition, boolean segmentFinished,
                                    int spokenStart, int spokenEnd, String status) {
        if (isSpeechCancelled(session)) return;
        int bounded = Math.min(Math.max(0, fullText.length() - 1),
                clamp(sourcePosition, 0, fullText.length()));
        if (!segmentFinished && bounded < readingPosition) return;
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

    private void finishGeminiSpeech(final int session, final Exception failure, final boolean complete) {
        finishSpeech(session, failure, complete, "Книга озвучена до конца");
    }

    private void finishSpeech(final int session, final Exception failure, final boolean complete,
                              final String completeMessage) {
        runOnUiThread(() -> {
            if (session != speechSession) return;
            speaking = false;
            clearSystemFallbackHighlight();
            systemRangeReported = false;
            highlightedStart = -1;
            highlightedEnd = -1;
            if (failure != null) {
                statusView.setText(errorMessage(failure) + " · позиция сохранена");
            } else if (complete) {
                readingPosition = Math.max(0, fullText.length() - 1);
                currentPage = pageForPosition(readingPosition);
                saveReadingPosition();
                statusView.setText(completeMessage);
            }
            renderCurrentPage();
            updateControls();
        });
    }

    private void stopSpeaking(boolean announce) {
        speechSession++;
        boolean wasSpeaking = speaking;
        speaking = false;
        if (gemini != null) gemini.stop();
        if (systemTts != null) {
            try {
                systemTts.stop();
            } catch (Exception ignored) {
            }
        }
        clearSystemFallbackHighlight();
        systemRangeReported = false;
        systemSpeechPlan = null;
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
            if (isSystemProvider() && voiceSummary != null) {
                voiceSummary.setText("Встроенный Android TTS недоступен: " + errorMessage(error));
            }
        }
    }

    private void shutdownSystemTts() {
        systemTtsReady = false;
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
                if (isSystemProvider() && voiceSummary != null) {
                    voiceSummary.setText("Не удалось запустить встроенный Android TTS");
                }
                updateControls();
                return;
            }
            int language = systemTts.setLanguage(new Locale("ru", "RU"));
            systemTtsReady = language != TextToSpeech.LANG_MISSING_DATA
                    && language != TextToSpeech.LANG_NOT_SUPPORTED;
            systemTts.setOnUtteranceProgressListener(new UtteranceProgressListener() {
                @Override
                public void onStart(String utteranceId) {
                    runOnUiThread(() -> {
                        SystemTtsSegment segment = systemSegmentFor(utteranceId);
                        if (segment == null) return;
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
                        SystemTtsSegment segment = systemSegmentFor(utteranceId);
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
            if (systemTtsReady) applySavedSystemTtsSettings();
            refreshTtsLabels();
            updateControls();
        });
    }

    private void applySavedSystemTtsSettings() {
        if (!systemTtsReady || systemTts == null) return;
        systemTts.setSpeechRate(ttsPreferences.getFloat(PREF_RATE, 1f));
        Voice saved = systemVoiceNamed(ttsPreferences.getString(PREF_SYSTEM_VOICE, ""));
        if (saved != null && systemTts.setVoice(saved) == TextToSpeech.SUCCESS) return;
        Voice automatic = bestRussianSystemVoice();
        if (automatic != null && systemTts.setVoice(automatic) == TextToSpeech.SUCCESS) {
            ttsPreferences.edit().putString(PREF_SYSTEM_VOICE, automatic.getName()).apply();
        }
    }

    private void startSystemSpeech() {
        if (!systemTtsReady || systemTts == null) {
            Toast.makeText(this, "Встроенный Android TTS ещё не готов. Установите русский голос в настройках Android.",
                    Toast.LENGTH_LONG).show();
            return;
        }
        speaking = true;
        speechSession++;
        int session = speechSession;
        int start = clamp(readingPosition, 0, Math.max(0, fullText.length() - 1));
        highlightedStart = start;
        highlightedEnd = Math.min(fullText.length(), start + 1);
        clearSystemFallbackHighlight();
        systemRangeReported = false;
        renderCurrentPage();
        lastProgressSaveAt = 0L;
        systemSpeechPlan = makeSystemSpeechPlan(start);
        if (systemSpeechPlan.isEmpty()) {
            finishSpeech(session, null, true, "Книга озвучена до конца");
            return;
        }
        systemTts.setSpeechRate(ttsPreferences.getFloat(PREF_RATE, 1f));
        statusView.setText("Встроенный Android TTS начинает чтение…");
        updateControls();
        speakSystemSegment(session, 0);
    }

    private ArrayList<SystemTtsSegment> makeSystemSpeechPlan(int start) {
        ArrayList<SystemTtsSegment> plan = new ArrayList<>();
        int maximum = Math.min(SYSTEM_TTS_CHUNK_CHARS,
                Math.max(400, TextToSpeech.getMaxSpeechInputLength() - 100));
        int cursor = skipWhitespace(start);
        while (cursor < fullText.length()) {
            int next = safeSpeechEnd(cursor, maximum);
            int end = next;
            while (end > cursor && Character.isWhitespace(fullText.charAt(end - 1))) end--;
            if (end > cursor) plan.add(new SystemTtsSegment(cursor, end, fullText.substring(cursor, end)));
            cursor = skipWhitespace(Math.max(next, cursor + 1));
        }
        return plan;
    }

    /**
     * Some Android TTS engines emit onRangeStart for every word, while others only
     * report utterance start/end. Keep the latter readable too with a deliberately
     * conservative, rate-aware word estimate until a real range arrives.
     */
    private void startSystemFallbackHighlight(final int session, final String utteranceId,
                                              final SystemTtsSegment segment) {
        clearSystemFallbackHighlight();
        systemRangeReported = false;
        final long startedAt = SystemClock.elapsedRealtime();
        final float rate = Math.max(0.7f, Math.min(1.4f, ttsPreferences.getFloat(PREF_RATE, 1f)));
        // Russian prose averages around fourteen visible characters per second at 1×.
        final long expectedDuration = Math.max(1_500L,
                Math.round((segment.end - segment.start) * 1_000f / (14f * rate)));
        systemFallbackHighlighter = new Runnable() {
            @Override
            public void run() {
                if (systemFallbackHighlighter != this || systemRangeReported || !speaking
                        || session != speechSession || !isSystemProvider()
                        || systemSegmentFor(utteranceId) != segment) return;
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

    private void speakSystemSegment(int session, int index) {
        if (session != speechSession || !speaking || !isSystemProvider()) return;
        if (systemSpeechPlan == null || index >= systemSpeechPlan.size()) {
            finishSpeech(session, null, true, "Книга озвучена до конца");
            return;
        }
        if (systemTts == null || !systemTtsReady) {
            finishSpeech(session, new IllegalStateException("Встроенный Android TTS недоступен"), false, "");
            return;
        }
        SystemTtsSegment segment = systemSpeechPlan.get(index);
        String utteranceId = systemUtteranceId(session, index);
        Bundle params = new Bundle();
        params.putString(TextToSpeech.Engine.KEY_PARAM_UTTERANCE_ID, utteranceId);
        int result = systemTts.speak(segment.text, TextToSpeech.QUEUE_FLUSH, params, utteranceId);
        if (result != TextToSpeech.SUCCESS) {
            finishSpeech(session, new IllegalStateException("Встроенный Android TTS отказался начать озвучку"),
                    false, "");
        }
    }

    private void finishSystemUtterance(String utteranceId, Exception failure) {
        int[] parsed = parseSystemUtterance(utteranceId);
        if (parsed == null || parsed[0] != speechSession || !speaking || !isSystemProvider()) return;
        clearSystemFallbackHighlight();
        systemRangeReported = false;
        if (failure != null) {
            finishSpeech(parsed[0], failure, false, "");
            return;
        }
        if (systemSpeechPlan == null || parsed[1] < 0 || parsed[1] >= systemSpeechPlan.size()) return;
        SystemTtsSegment segment = systemSpeechPlan.get(parsed[1]);
        saveSpeechProgress(parsed[0], segment.end, true, Math.max(segment.start, segment.end - 1),
                segment.end, "Встроенный Android TTS читает · текст подсвечен…");
        speakSystemSegment(parsed[0], parsed[1] + 1);
    }

    private SystemTtsSegment systemSegmentFor(String utteranceId) {
        int[] parsed = parseSystemUtterance(utteranceId);
        if (parsed == null || parsed[0] != speechSession || !speaking || !isSystemProvider()
                || systemSpeechPlan == null || parsed[1] < 0 || parsed[1] >= systemSpeechPlan.size()) return null;
        return systemSpeechPlan.get(parsed[1]);
    }

    private static String systemUtteranceId(int session, int index) {
        return SYSTEM_UTTERANCE_PREFIX + session + ":" + index;
    }

    private static int[] parseSystemUtterance(String utteranceId) {
        if (utteranceId == null || !utteranceId.startsWith(SYSTEM_UTTERANCE_PREFIX)) return null;
        try {
            String[] pieces = utteranceId.substring(SYSTEM_UTTERANCE_PREFIX.length()).split(":", -1);
            if (pieces.length != 2) return null;
            return new int[]{Integer.parseInt(pieces[0]), Integer.parseInt(pieces[1])};
        } catch (Exception ignored) {
            return null;
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

    private void showProviderPicker() {
        final String[] choices = new String[]{
                "Gemini AI · длинные фрагменты и сохранённый аудиокэш",
                "Встроенный Android TTS · голос телефона"
        };
        int checked = isSystemProvider() ? 1 : 0;
        new AlertDialog.Builder(this)
                .setTitle("Режим озвучки")
                .setSingleChoiceItems(choices, checked, (dialog, which) -> {
                    String provider = which == 1 ? PROVIDER_SYSTEM : PROVIDER_GEMINI;
                    if (!provider.equals(ttsPreferences.getString(PREF_PROVIDER, PROVIDER_GEMINI))) {
                        stopSpeaking(false);
                        ttsPreferences.edit().putString(PREF_PROVIDER, provider).apply();
                    }
                    refreshTtsLabels();
                    updateControls();
                    dialog.dismiss();
                    if (PROVIDER_GEMINI.equals(provider)
                            && secretStore.get(SECRET_GEMINI_KEY).isEmpty()) {
                        showGeminiSetup();
                    } else if (PROVIDER_SYSTEM.equals(provider) && !systemTtsReady) {
                        showSystemTtsSetup();
                    }
                })
                .setNegativeButton("Отмена", null)
                .show();
    }

    private void showVoicePicker() {
        if (isSystemProvider()) {
            showSystemVoicePicker();
        } else {
            showGeminiVoicePicker();
        }
    }

    private void showSystemVoicePicker() {
        if (!systemTtsReady || systemTts == null) {
            showSystemTtsSetup();
            return;
        }
        final ArrayList<Voice> voices = russianSystemVoices();
        if (voices.isEmpty()) {
            showSystemTtsSetup();
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
                    if (systemTts.setVoice(voice) == TextToSpeech.SUCCESS) {
                        ttsPreferences.edit().putString(PREF_SYSTEM_VOICE, voice.getName()).apply();
                        refreshTtsLabels();
                        Toast.makeText(this, "Системный голос выбран", Toast.LENGTH_SHORT).show();
                        dialog.dismiss();
                    } else {
                        Toast.makeText(this, "Этот системный голос недоступен", Toast.LENGTH_SHORT).show();
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
                .setPositiveButton("Настройки", (dialog, which) -> openSystemTtsSettings())
                .show();
    }

    private void openSystemTtsSettings() {
        try {
            startActivity(new Intent("com.android.settings.TTS_SETTINGS"));
        } catch (Exception ignored) {
            try {
                startActivity(new Intent(TextToSpeech.Engine.ACTION_INSTALL_TTS_DATA));
            } catch (Exception error) {
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
                for (Voice voice : voices) if (name.equals(voice.getName())) return voice;
            }
        } catch (Exception ignored) {
        }
        return null;
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
                "Gemini озвучивает длинные фрагменты через ваш личный API-ключ. Готовое аудио сохраняется только в закрытом хранилище приложения, чтобы не запрашивать те же места повторно.",
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
                    float selected = speeds[which];
                    ttsPreferences.edit().putFloat(PREF_RATE, selected).apply();
                    if (systemTtsReady && systemTts != null) systemTts.setSpeechRate(selected);
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
        final ArrayList<GeminiTtsEngine.Segment> segments;

        SpeechPlan(ArrayList<GeminiTtsEngine.Segment> segments) {
            this.segments = segments;
        }
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
