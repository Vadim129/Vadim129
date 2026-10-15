package ru.vadim.bookvoice;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.graphics.Typeface;
import android.net.Uri;
import android.os.Bundle;
import android.provider.Settings;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** Library screen. All import work is deliberately performed off the UI thread. */
public final class MainActivity extends Activity {
    private static final int PICK_BOOK = 42;
    private BookStore bookStore;
    private LinearLayout library;
    private ExecutorService io;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().setStatusBarColor(Ui.PAPER);
        getWindow().setNavigationBarColor(Ui.PAPER);
        getWindow().getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR);
        bookStore = new BookStore(this);
        io = Executors.newSingleThreadExecutor();
        setContentView(createScreen());
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (library != null) renderLibrary();
    }

    @Override
    protected void onDestroy() {
        if (io != null) io.shutdownNow();
        super.onDestroy();
    }

    private View createScreen() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(Ui.PAPER);

        LinearLayout header = new LinearLayout(this);
        header.setGravity(Gravity.CENTER_VERTICAL);
        header.setPadding(Ui.dp(this, 20), Ui.dp(this, 18), Ui.dp(this, 20), Ui.dp(this, 14));
        LinearLayout headerText = new LinearLayout(this);
        headerText.setOrientation(LinearLayout.VERTICAL);
        TextView title = Ui.heading(this, "Книжный голос", 28);
        TextView subtitle = Ui.text(this, "Ваша библиотека и место, где вы остановились", 14, Ui.MUTED);
        headerText.addView(title);
        headerText.addView(subtitle);
        header.addView(headerText, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));

        Button add = Ui.button(this, "+ Импорт", Ui.FOREST, Ui.PAPER);
        add.setContentDescription("Импортировать книгу");
        add.setOnClickListener(view -> chooseBook());
        header.addView(add, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, Ui.dp(this, 48)));
        root.addView(header);

        TextView formats = Ui.text(this, "EPUB  ·  FB2  ·  PDF  ·  TXT  ·  HTML  ·  DOCX", 12, Ui.FOREST);
        formats.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        formats.setLetterSpacing(0.05f);
        formats.setPadding(Ui.dp(this, 20), 0, Ui.dp(this, 20), Ui.dp(this, 10));
        root.addView(formats);

        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        library = new LinearLayout(this);
        library.setOrientation(LinearLayout.VERTICAL);
        library.setPadding(Ui.dp(this, 16), Ui.dp(this, 4), Ui.dp(this, 16), Ui.dp(this, 100));
        scroll.addView(library, new ScrollView.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        root.addView(scroll, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));
        return root;
    }

    private void renderLibrary() {
        library.removeAllViews();
        List<Book> books = bookStore.getBooks();
        if (books.isEmpty()) {
            library.addView(emptyState());
            return;
        }
        TextView label = Ui.text(this, "ЧИТАЮ СЕЙЧАС", 12, Ui.MUTED);
        label.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        label.setLetterSpacing(0.08f);
        label.setPadding(Ui.dp(this, 4), Ui.dp(this, 12), 0, Ui.dp(this, 10));
        library.addView(label);
        for (Book book : books) library.addView(bookCard(book));
    }

    private View emptyState() {
        LinearLayout card = new LinearLayout(this);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setGravity(Gravity.CENTER_HORIZONTAL);
        card.setPadding(Ui.dp(this, 28), Ui.dp(this, 56), Ui.dp(this, 28), Ui.dp(this, 48));
        card.setBackground(Ui.outlined(Ui.SAND, Ui.LINE, 22));
        TextView icon = Ui.text(this, "▤", 48, Ui.FOREST);
        icon.setGravity(Gravity.CENTER);
        TextView title = Ui.heading(this, "Начните свою библиотеку", 22);
        title.setGravity(Gravity.CENTER);
        TextView hint = Ui.text(this,
                "Добавьте книгу с телефона. Приложение сохранит её локально, покажет прогресс и откроет на нужной странице в следующий раз.",
                15, Ui.MUTED);
        hint.setGravity(Gravity.CENTER);
        hint.setLineSpacing(Ui.dp(this, 3), 1f);
        Button importButton = Ui.button(this, "Выбрать книгу", Ui.FOREST, Ui.PAPER);
        importButton.setOnClickListener(view -> chooseBook());
        card.addView(icon, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        LinearLayout.LayoutParams titleParams = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        titleParams.topMargin = Ui.dp(this, 14);
        card.addView(title, titleParams);
        LinearLayout.LayoutParams hintParams = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        hintParams.topMargin = Ui.dp(this, 8);
        card.addView(hint, hintParams);
        LinearLayout.LayoutParams buttonParams = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, Ui.dp(this, 48));
        buttonParams.topMargin = Ui.dp(this, 22);
        card.addView(importButton, buttonParams);
        return card;
    }

    private View bookCard(final Book book) {
        LinearLayout card = new LinearLayout(this);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setPadding(Ui.dp(this, 18), Ui.dp(this, 16), Ui.dp(this, 12), Ui.dp(this, 12));
        card.setBackground(Ui.outlined(0xFFFFFFFF, Ui.LINE, 18));
        card.setClickable(true);
        card.setFocusable(true);
        card.setOnClickListener(view -> openReader(book.id));

        LinearLayout titleRow = new LinearLayout(this);
        titleRow.setGravity(Gravity.CENTER_VERTICAL);
        TextView title = Ui.heading(this, book.title, 19);
        title.setMaxLines(2);
        title.setEllipsize(android.text.TextUtils.TruncateAt.END);
        titleRow.addView(title, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        TextView format = Ui.text(this, book.format, 11, Ui.FOREST_DARK);
        format.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        format.setGravity(Gravity.CENTER);
        format.setPadding(Ui.dp(this, 8), Ui.dp(this, 5), Ui.dp(this, 8), Ui.dp(this, 5));
        format.setBackground(Ui.round(Ui.MINT, 10));
        titleRow.addView(format, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        card.addView(titleRow);

        TextView progress = Ui.text(this, "Страница " + book.currentPage + " из " + book.totalPages + "  ·  " + book.progressPercent() + "%", 14, Ui.MUTED);
        LinearLayout.LayoutParams progressParams = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        progressParams.topMargin = Ui.dp(this, 6);
        card.addView(progress, progressParams);

        ProgressBar bar = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        bar.setMax(100);
        bar.setProgress(book.progressPercent());
        bar.setProgressTintList(android.content.res.ColorStateList.valueOf(Ui.FOREST));
        bar.setBackgroundTintList(android.content.res.ColorStateList.valueOf(Ui.SAND));
        LinearLayout.LayoutParams barParams = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, Ui.dp(this, 4));
        barParams.topMargin = Ui.dp(this, 14);
        barParams.rightMargin = Ui.dp(this, 4);
        card.addView(bar, barParams);

        LinearLayout actions = new LinearLayout(this);
        actions.setGravity(Gravity.CENTER_VERTICAL);
        LinearLayout.LayoutParams actionsParams = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, Ui.dp(this, 48));
        actionsParams.topMargin = Ui.dp(this, 12);
        Button continueButton = Ui.button(this, book.position > 0 ? "Продолжить" : "Открыть", Ui.MINT, Ui.FOREST_DARK);
        continueButton.setOnClickListener(view -> openReader(book.id));
        actions.addView(continueButton, new LinearLayout.LayoutParams(0, Ui.dp(this, 44), 1f));
        Button deleteButton = Ui.button(this, "Удалить", Ui.SAND, Ui.DANGER);
        deleteButton.setOnClickListener(view -> confirmDelete(book));
        LinearLayout.LayoutParams deleteParams = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, Ui.dp(this, 44));
        deleteParams.leftMargin = Ui.dp(this, 8);
        actions.addView(deleteButton, deleteParams);
        card.addView(actions, actionsParams);

        LinearLayout.LayoutParams cardParams = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        cardParams.bottomMargin = Ui.dp(this, 12);
        card.setLayoutParams(cardParams);
        return card;
    }

    private void chooseBook() {
        Intent picker = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        picker.addCategory(Intent.CATEGORY_OPENABLE);
        picker.setType("*/*");
        picker.putExtra(Intent.EXTRA_MIME_TYPES, new String[]{
                "application/epub+zip", "application/pdf", "text/plain", "text/html",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/zip"
        });
        picker.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION);
        startActivityForResult(picker, PICK_BOOK);
    }

    @Override
    @SuppressWarnings("deprecation")
    protected void onActivityResult(int requestCode, int resultCode, Intent result) {
        super.onActivityResult(requestCode, resultCode, result);
        if (requestCode != PICK_BOOK || resultCode != RESULT_OK || result == null || result.getData() == null) return;
        Uri source = result.getData();
        try {
            getContentResolver().takePersistableUriPermission(source, Intent.FLAG_GRANT_READ_URI_PERMISSION);
        } catch (SecurityException ignored) {
            // The file is copied immediately, so a provider need not offer a persistent grant.
        }
        importAsync(source);
    }

    private void importAsync(final Uri source) {
        final AlertDialog progress = importingDialog();
        progress.show();
        io.execute(() -> {
            try {
                final Book book = BookImporter.importBook(getApplicationContext(), source, bookStore);
                runOnUiThread(() -> {
                    if (!isFinishing()) progress.dismiss();
                    openReader(book.id);
                });
            } catch (final Exception error) {
                runOnUiThread(() -> {
                    if (!isFinishing()) progress.dismiss();
                    showError("Не удалось добавить книгу", error.getMessage());
                });
            }
        });
    }

    private AlertDialog importingDialog() {
        LinearLayout content = new LinearLayout(this);
        content.setOrientation(LinearLayout.HORIZONTAL);
        content.setGravity(Gravity.CENTER_VERTICAL);
        content.setPadding(Ui.dp(this, 24), Ui.dp(this, 18), Ui.dp(this, 24), Ui.dp(this, 18));
        ProgressBar spinner = new ProgressBar(this);
        content.addView(spinner, new LinearLayout.LayoutParams(Ui.dp(this, 32), Ui.dp(this, 32)));
        TextView message = Ui.text(this, "Импортируем и готовим книгу…", 16, Ui.INK);
        LinearLayout.LayoutParams messageParams = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        messageParams.leftMargin = Ui.dp(this, 16);
        content.addView(message, messageParams);
        return new AlertDialog.Builder(this).setView(content).setCancelable(false).create();
    }

    private void openReader(String bookId) {
        Intent reader = new Intent(this, ReaderActivity.class);
        reader.putExtra(ReaderActivity.EXTRA_BOOK_ID, bookId);
        startActivity(reader);
    }

    private void confirmDelete(final Book book) {
        new AlertDialog.Builder(this)
                .setTitle("Удалить книгу?")
                .setMessage("«" + book.title + "» будет удалена только из этой читалки и из её приватной библиотеки.")
                .setNegativeButton("Отмена", null)
                .setPositiveButton("Удалить", (dialog, which) -> {
                    bookStore.remove(book);
                    renderLibrary();
                    Toast.makeText(this, "Книга удалена", Toast.LENGTH_SHORT).show();
                })
                .show();
    }

    private void showError(String title, String detail) {
        new AlertDialog.Builder(this)
                .setTitle(title)
                .setMessage(detail == null || detail.trim().isEmpty() ? "Попробуйте выбрать другой файл." : detail)
                .setPositiveButton("Понятно", null)
                .show();
    }
}
