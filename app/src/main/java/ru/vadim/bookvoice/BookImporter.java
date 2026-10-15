package ru.vadim.bookvoice;

import android.content.ContentResolver;
import android.content.Context;
import android.database.Cursor;
import android.net.Uri;
import android.provider.OpenableColumns;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.util.Locale;
import java.util.UUID;

/** Copies a document selected by SAF into app-private storage, then validates it locally. */
public final class BookImporter {
    private static final long MAX_IMPORT_BYTES = 100L * 1024L * 1024L;

    private BookImporter() {
    }

    public static Book importBook(Context context, Uri source, BookStore store) throws IOException {
        if (source == null) throw new IOException("Не выбран файл");
        String sourceName = displayName(context, source);
        String extension = extensionFromNameOrMime(sourceName, context.getContentResolver().getType(source));
        String title = titleFromName(sourceName);
        String id = UUID.randomUUID().toString();
        File libraryDirectory = new File(context.getFilesDir(), "books");
        if (!libraryDirectory.exists() && !libraryDirectory.mkdirs()) {
            throw new IOException("Не удалось создать приватную библиотеку");
        }
        File temporary = new File(libraryDirectory, id + ".part");
        File destination = new File(libraryDirectory, id + "." + extension);
        try {
            copyIntoPrivateStorage(context.getContentResolver(), source, temporary);
            if (!temporary.renameTo(destination)) {
                copyFile(temporary, destination);
                //noinspection ResultOfMethodCallIgnored
                temporary.delete();
            }

            Book book = new Book();
            book.id = id;
            book.title = title;
            book.localPath = destination.getAbsolutePath();
            book.sourceName = sourceName;
            book.format = BookParser.formatFromName(destination.getName());
            book.position = 0;
            book.currentPage = 1;
            book.lastOpened = System.currentTimeMillis();

            BookParser.ParsedBook parsed = BookParser.parse(context, book);
            // Scanned PDFs are still retained, so the reader can explain what is needed.
            if (parsed.text.trim().isEmpty() && !"PDF".equals(book.format)) {
                throw new IOException("В выбранном файле не найден текст");
            }
            book.totalPages = parsed.pageCount;
            store.put(book);
            return book;
        } catch (IOException error) {
            //noinspection ResultOfMethodCallIgnored
            temporary.delete();
            //noinspection ResultOfMethodCallIgnored
            destination.delete();
            throw error;
        } catch (Exception error) {
            //noinspection ResultOfMethodCallIgnored
            temporary.delete();
            //noinspection ResultOfMethodCallIgnored
            destination.delete();
            throw new IOException("Не удалось импортировать книгу: " + message(error), error);
        }
    }

    private static void copyIntoPrivateStorage(ContentResolver resolver, Uri source, File destination) throws IOException {
        InputStream input = resolver.openInputStream(source);
        if (input == null) throw new IOException("Не удалось прочитать выбранный файл");
        try (InputStream stream = input; FileOutputStream output = new FileOutputStream(destination)) {
            byte[] buffer = new byte[32 * 1024];
            long copied = 0;
            int count;
            while ((count = stream.read(buffer)) != -1) {
                copied += count;
                if (copied > MAX_IMPORT_BYTES) {
                    throw new IOException("Файл больше 100 МБ. Импорт остановлен для защиты памяти устройства.");
                }
                output.write(buffer, 0, count);
            }
            output.getFD().sync();
        }
    }

    private static void copyFile(File source, File destination) throws IOException {
        try (FileInputStream input = new FileInputStream(source); FileOutputStream output = new FileOutputStream(destination)) {
            byte[] buffer = new byte[32 * 1024];
            int count;
            while ((count = input.read(buffer)) != -1) output.write(buffer, 0, count);
            output.getFD().sync();
        }
    }

    private static String displayName(Context context, Uri uri) {
        Cursor cursor = null;
        try {
            cursor = context.getContentResolver().query(uri, new String[]{OpenableColumns.DISPLAY_NAME}, null, null, null);
            if (cursor != null && cursor.moveToFirst()) {
                int column = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME);
                if (column >= 0) {
                    String name = cursor.getString(column);
                    if (name != null && !name.trim().isEmpty()) return name.trim();
                }
            }
        } catch (Exception ignored) {
        } finally {
            if (cursor != null) cursor.close();
        }
        String lastSegment = uri.getLastPathSegment();
        return lastSegment == null || lastSegment.trim().isEmpty() ? "Книга.txt" : lastSegment;
    }

    private static String extensionFromNameOrMime(String filename, String mime) {
        String lower = filename == null ? "" : filename.toLowerCase(Locale.ROOT);
        if (lower.endsWith(".fb2.zip")) return "fb2.zip";
        int index = lower.lastIndexOf('.');
        if (index >= 0 && index < lower.length() - 1) {
            String extension = lower.substring(index + 1);
            if (extension.matches("[a-z0-9]{1,8}")) return extension;
        }
        if ("application/epub+zip".equals(mime)) return "epub";
        if ("application/pdf".equals(mime)) return "pdf";
        if ("application/vnd.openxmlformats-officedocument.wordprocessingml.document".equals(mime)) return "docx";
        if ("text/html".equals(mime)) return "html";
        return "txt";
    }

    private static String titleFromName(String sourceName) {
        if (sourceName == null || sourceName.trim().isEmpty()) return "Без названия";
        String title = sourceName.trim();
        String lower = title.toLowerCase(Locale.ROOT);
        if (lower.endsWith(".fb2.zip")) title = title.substring(0, title.length() - ".fb2.zip".length());
        else {
            int period = title.lastIndexOf('.');
            if (period > 0) title = title.substring(0, period);
        }
        return title.trim().isEmpty() ? "Без названия" : title.trim();
    }

    private static String message(Exception exception) {
        String message = exception.getMessage();
        return message == null || message.trim().isEmpty() ? "неизвестная ошибка" : message;
    }
}
