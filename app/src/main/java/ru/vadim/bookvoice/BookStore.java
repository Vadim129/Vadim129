package ru.vadim.bookvoice;

import android.content.Context;
import android.content.SharedPreferences;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.File;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.List;

/** Stores only library metadata. Book bytes live in the app-private files directory. */
public final class BookStore {
    private static final String PREFS = "bookvoice_library";
    private static final String KEY_BOOKS = "books";
    private final SharedPreferences preferences;

    public BookStore(Context context) {
        preferences = context.getApplicationContext().getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    public synchronized List<Book> getBooks() {
        ArrayList<Book> books = new ArrayList<>();
        String saved = preferences.getString(KEY_BOOKS, "[]");
        try {
            JSONArray array = new JSONArray(saved == null ? "[]" : saved);
            for (int i = 0; i < array.length(); i++) {
                JSONObject object = array.optJSONObject(i);
                if (object == null) continue;
                Book book = Book.fromJson(object);
                if (!book.id.isEmpty() && !book.localPath.isEmpty()) {
                    books.add(book);
                }
            }
        } catch (Exception ignored) {
            // A corrupted metadata cache should never make the user's files inaccessible.
        }
        Collections.sort(books, new Comparator<Book>() {
            @Override
            public int compare(Book first, Book second) {
                return Long.compare(second.lastOpened, first.lastOpened);
            }
        });
        return books;
    }

    public synchronized Book getBook(String id) {
        if (id == null) return null;
        for (Book book : getBooks()) {
            if (id.equals(book.id)) return book;
        }
        return null;
    }

    public synchronized void put(Book updated) {
        if (updated == null || updated.id == null || updated.id.isEmpty()) return;
        List<Book> books = getBooks();
        boolean replaced = false;
        for (int i = 0; i < books.size(); i++) {
            if (updated.id.equals(books.get(i).id)) {
                books.set(i, updated);
                replaced = true;
                break;
            }
        }
        if (!replaced) books.add(updated);
        save(books);
    }

    public synchronized void saveReadingState(Book book, int position, int page, int totalPages) {
        if (book == null) return;
        book.position = Math.max(0, position);
        book.currentPage = Math.max(1, page);
        book.totalPages = Math.max(1, totalPages);
        book.lastOpened = System.currentTimeMillis();
        put(book);
    }

    public synchronized void remove(Book book) {
        if (book == null) return;
        List<Book> books = getBooks();
        for (int i = books.size() - 1; i >= 0; i--) {
            if (book.id.equals(books.get(i).id)) books.remove(i);
        }
        save(books);
        try {
            File data = new File(book.localPath);
            if (data.exists()) data.delete();
        } catch (Exception ignored) {
        }
    }

    private void save(List<Book> books) {
        JSONArray array = new JSONArray();
        for (Book book : books) {
            try {
                array.put(book.toJson());
            } catch (Exception ignored) {
            }
        }
        preferences.edit().putString(KEY_BOOKS, array.toString()).apply();
    }
}
