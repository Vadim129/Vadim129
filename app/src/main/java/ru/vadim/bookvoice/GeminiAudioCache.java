package ru.vadim.bookvoice;

import android.content.Context;
import android.os.StatFs;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.List;

/**
 * Private, no-backup cache for generated Gemini PCM. Entries are tied to a
 * book, exact source range, voice and PCM format, so replaying a saved passage
 * does not consume another Gemini request. The cache is globally LRU-bounded
 * to at most one third of currently free storage (and never over 768 MiB).
 */
final class GeminiAudioCache {
    private static final String CACHE_DIRECTORY = "bookvoice-gemini-audio-v2";
    private static final String PCM_FORMAT = "s16le-24000-mono-v1";
    private static final long MAX_CACHE_BYTES = 768L * 1024L * 1024L;
    private static final long MAX_ENTRY_BYTES = 40L * 1024L * 1024L;
    private static final int MIN_PCM_BYTES = 2;

    private final File rootDirectory;
    private final File bookDirectory;
    private final Object lock = new Object();

    GeminiAudioCache(Context context, String bookId) {
        Context app = context.getApplicationContext();
        File base = app.getNoBackupFilesDir();
        if (base == null) base = app.getFilesDir();
        rootDirectory = new File(base, CACHE_DIRECTORY);
        bookDirectory = new File(rootDirectory, directoryId(bookId));
    }

    /** Returns a verified cache hit for this exact book segment, or null. */
    byte[] read(int start, int end, String voice, String text) {
        if (!isUsableSegment(start, end, text)) return null;
        synchronized (lock) {
            return readFile(fileFor(start, end, voice, text));
        }
    }

    /**
     * Looks for a previously saved long passage which covers the requested
     * position. It lets a stopped reader resume from the saved PCM rather than
     * regenerating the rest of that long passage.
     */
    Hit findCovering(String voice, String completeText, int position) {
        if (completeText == null || position < 0 || position >= completeText.length()) return null;
        synchronized (lock) {
            File[] files = bookDirectory.listFiles();
            if (files == null) return null;
            String expectedVoice = voiceSignature(voice);
            Entry candidate = null;
            for (File file : files) {
                Entry entry = parseEntry(file);
                if (entry == null || !expectedVoice.equals(entry.voiceSignature)
                        || entry.start > position || entry.end <= position
                        || entry.end > completeText.length()) continue;
                String currentText = completeText.substring(entry.start, entry.end);
                if (!entry.textSignature.equals(signature(currentText))) {
                    deleteQuietly(file);
                    continue;
                }
                // Prefer the entry which starts closest to the resume point.
                if (candidate == null || entry.start > candidate.start) candidate = entry;
            }
            if (candidate == null) return null;
            byte[] pcm = readFile(candidate.file);
            if (pcm == null) return null;
            int relativeCharacters = position - candidate.start;
            int segmentCharacters = Math.max(1, candidate.end - candidate.start);
            int offset = (int) (((long) pcm.length * relativeCharacters) / segmentCharacters);
            offset &= ~1; // 16-bit PCM frame boundary.
            if (offset >= pcm.length - MIN_PCM_BYTES) return null;
            return new Hit(candidate.start, candidate.end, pcm, offset);
        }
    }

    /** Persists a completed Gemini response atomically; cache failures never stop speech. */
    void store(int start, int end, String voice, String text, byte[] pcm) {
        if (!isUsableSegment(start, end, text) || pcm == null || pcm.length < MIN_PCM_BYTES
                || pcm.length > MAX_ENTRY_BYTES || (pcm.length & 1) != 0) return;
        synchronized (lock) {
            try {
                if (!bookDirectory.isDirectory() && !bookDirectory.mkdirs()) return;
                File target = fileFor(start, end, voice, text);
                if (target.isFile()) {
                    target.setLastModified(System.currentTimeMillis());
                    return;
                }
                long limit = cacheLimitBytes();
                if (limit <= pcm.length) return;
                trimTo(Math.max(0L, limit - pcm.length));
                File temporary = new File(bookDirectory, target.getName() + ".part");
                deleteQuietly(temporary);
                try (FileOutputStream output = new FileOutputStream(temporary)) {
                    output.write(pcm);
                    output.getFD().sync();
                }
                if (target.exists()) deleteQuietly(target);
                if (!temporary.renameTo(target)) {
                    deleteQuietly(temporary);
                    return;
                }
                target.setLastModified(System.currentTimeMillis());
                trimTo(limit);
            } catch (Exception ignored) {
                // The reader must still work if storage is full or unavailable.
            }
        }
    }

    static void deleteBookCache(Context context, String bookId) {
        if (context == null || bookId == null || bookId.trim().isEmpty()) return;
        try {
            Context app = context.getApplicationContext();
            File base = app.getNoBackupFilesDir();
            if (base == null) base = app.getFilesDir();
            File root = new File(base, CACHE_DIRECTORY);
            File book = new File(root, directoryId(bookId));
            deleteRecursively(book);
        } catch (Exception ignored) {
        }
    }

    private File fileFor(int start, int end, String voice, String text) {
        return new File(bookDirectory, start + "-" + end + "-" + voiceSignature(voice)
                + "-" + signature(text) + ".pcm");
    }

    private static String directoryId(String bookId) {
        String result = signature("book|" + safe(bookId));
        return result.length() <= 32 ? result : result.substring(0, 32);
    }

    private static String voiceSignature(String voice) {
        return signature(GeminiTtsEngine.MODEL + "|" + PCM_FORMAT + "|" + safe(voice));
    }

    private byte[] readFile(File file) {
        if (file == null || !file.isFile()) return null;
        long length = file.length();
        if (length < MIN_PCM_BYTES || length > MAX_ENTRY_BYTES || (length & 1L) != 0L) {
            deleteQuietly(file);
            return null;
        }
        try {
            byte[] pcm = new byte[(int) length];
            int offset = 0;
            try (FileInputStream input = new FileInputStream(file)) {
                while (offset < pcm.length) {
                    int count = input.read(pcm, offset, pcm.length - offset);
                    if (count < 0) break;
                    offset += count;
                }
            }
            if (offset != pcm.length) throw new IOException("Неполный PCM-кэш");
            file.setLastModified(System.currentTimeMillis());
            return pcm;
        } catch (Exception ignored) {
            deleteQuietly(file);
            return null;
        }
    }

    private long cacheLimitBytes() {
        try {
            File statPath = rootDirectory.getParentFile() == null ? rootDirectory : rootDirectory.getParentFile();
            StatFs stat = new StatFs(statPath.getAbsolutePath());
            long available = stat.getAvailableBytes();
            return Math.min(MAX_CACHE_BYTES, Math.max(0L, available / 3L));
        } catch (Exception ignored) {
            return 0L;
        }
    }

    private void trimTo(long targetBytes) {
        ArrayList<File> files = new ArrayList<>();
        collectPcmFiles(rootDirectory, files);
        long total = 0L;
        for (File file : files) total += Math.max(0L, file.length());
        if (total <= targetBytes) return;
        Collections.sort(files, new Comparator<File>() {
            @Override
            public int compare(File first, File second) {
                return Long.compare(first.lastModified(), second.lastModified());
            }
        });
        for (File file : files) {
            if (total <= targetBytes) break;
            long bytes = Math.max(0L, file.length());
            if (file.delete()) total -= bytes;
        }
    }

    private static void collectPcmFiles(File directory, List<File> output) {
        File[] files = directory == null ? null : directory.listFiles();
        if (files == null) return;
        for (File file : files) {
            if (file.isDirectory()) {
                collectPcmFiles(file, output);
            } else if (file.getName().endsWith(".pcm")) {
                output.add(file);
            } else if (file.getName().endsWith(".part")) {
                deleteQuietly(file);
            }
        }
    }

    private static Entry parseEntry(File file) {
        if (file == null || !file.isFile() || !file.getName().endsWith(".pcm")) return null;
        String bare = file.getName().substring(0, file.getName().length() - 4);
        String[] parts = bare.split("-", -1);
        if (parts.length != 4) return null;
        try {
            int start = Integer.parseInt(parts[0]);
            int end = Integer.parseInt(parts[1]);
            if (start < 0 || end <= start || parts[2].isEmpty() || parts[3].isEmpty()) return null;
            return new Entry(file, start, end, parts[2], parts[3]);
        } catch (Exception ignored) {
            return null;
        }
    }

    private static boolean isUsableSegment(int start, int end, String text) {
        return start >= 0 && end > start && text != null && !text.trim().isEmpty();
    }

    private static String signature(String value) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] bytes = digest.digest(safe(value).getBytes(StandardCharsets.UTF_8));
            StringBuilder result = new StringBuilder(bytes.length * 2);
            for (byte current : bytes) result.append(String.format("%02x", current & 0xff));
            return result.toString();
        } catch (Exception ignored) {
            return Integer.toHexString(safe(value).hashCode());
        }
    }

    private static String safe(String value) {
        return value == null ? "" : value;
    }

    private static void deleteRecursively(File file) {
        if (file == null || !file.exists()) return;
        if (file.isDirectory()) {
            File[] children = file.listFiles();
            if (children != null) {
                for (File child : children) deleteRecursively(child);
            }
        }
        deleteQuietly(file);
    }

    private static void deleteQuietly(File file) {
        try {
            if (file != null && file.exists()) file.delete();
        } catch (Exception ignored) {
        }
    }

    static final class Hit {
        final int start;
        final int end;
        final byte[] pcm;
        final int offsetBytes;

        Hit(int start, int end, byte[] pcm, int offsetBytes) {
            this.start = start;
            this.end = end;
            this.pcm = pcm;
            this.offsetBytes = offsetBytes;
        }
    }

    private static final class Entry {
        final File file;
        final int start;
        final int end;
        final String voiceSignature;
        final String textSignature;

        Entry(File file, int start, int end, String voiceSignature, String textSignature) {
            this.file = file;
            this.start = start;
            this.end = end;
            this.voiceSignature = voiceSignature;
            this.textSignature = textSignature;
        }
    }
}
