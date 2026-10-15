package ru.vadim.bookvoice;

import org.json.JSONException;
import org.json.JSONObject;

/** A compact, locally persisted entry in the reading library. */
public final class Book {
    public String id;
    public String title;
    public String localPath;
    public String sourceName;
    public String format;
    public int position;
    public int currentPage;
    public int totalPages;
    public long lastOpened;

    public Book() {
    }

    public JSONObject toJson() throws JSONException {
        JSONObject object = new JSONObject();
        object.put("id", id);
        object.put("title", title);
        object.put("localPath", localPath);
        object.put("sourceName", sourceName);
        object.put("format", format);
        object.put("position", position);
        object.put("currentPage", currentPage);
        object.put("totalPages", totalPages);
        object.put("lastOpened", lastOpened);
        return object;
    }

    public static Book fromJson(JSONObject object) {
        Book book = new Book();
        book.id = object.optString("id", "");
        book.title = object.optString("title", "Без названия");
        book.localPath = object.optString("localPath", "");
        book.sourceName = object.optString("sourceName", "");
        book.format = object.optString("format", "TXT");
        book.position = Math.max(0, object.optInt("position", 0));
        book.currentPage = Math.max(1, object.optInt("currentPage", 1));
        book.totalPages = Math.max(1, object.optInt("totalPages", 1));
        book.lastOpened = object.optLong("lastOpened", 0L);
        return book;
    }

    public int progressPercent() {
        if (totalPages <= 0) return 0;
        return Math.min(100, Math.max(0, Math.round((currentPage * 100f) / totalPages)));
    }
}
