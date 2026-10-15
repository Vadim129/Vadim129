package ru.vadim.bookvoice;

import android.content.Context;
import android.os.Build;
import android.text.Html;

import com.tom_roush.pdfbox.android.PDFBoxResourceLoader;
import com.tom_roush.pdfbox.pdmodel.PDDocument;
import com.tom_roush.pdfbox.text.PDFTextStripper;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.ByteBuffer;
import java.nio.charset.CharacterCodingException;
import java.nio.charset.Charset;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Enumeration;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.Locale;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;

/**
 * Local-only readers for the formats supported by the app. The output is one
 * normalized text stream, so the same page resume and TTS code works for all formats.
 */
public final class BookParser {
    public static final int PAGE_CHARACTERS = 1_800;
    private static final long MAX_TEXT_SOURCE_BYTES = 70L * 1024L * 1024L;
    private static volatile boolean pdfBoxReady;

    private BookParser() {
    }

    public static final class ParsedBook {
        public final String text;
        public final int pageCount;
        public final String note;

        ParsedBook(String text, String note) {
            this.text = normalizeText(text);
            this.pageCount = pageCountForText(this.text);
            this.note = note;
        }
    }

    public static ParsedBook parse(Context context, Book book) throws IOException {
        if (book == null || book.localPath == null) throw new IOException("Не найден файл книги");
        File file = new File(book.localPath);
        if (!file.exists() || !file.isFile()) throw new IOException("Файл книги больше не найден");
        String format = book.format == null ? formatFromName(file.getName()) : book.format.toUpperCase(Locale.ROOT);
        String text;
        String note = "";
        switch (format) {
            case "EPUB":
                text = readEpub(file);
                note = "EPUB • локально извлечённый текст";
                break;
            case "FB2":
                text = readFb2(file);
                note = "FB2 • локально извлечённый текст";
                break;
            case "PDF":
                text = readPdf(context, file);
                note = "PDF • текст извлечён локально";
                break;
            case "DOCX":
                text = readDocx(file);
                note = "DOCX • локально извлечённый текст";
                break;
            case "HTML":
            case "HTM":
                text = htmlToText(readPlainText(file));
                note = "HTML • локально извлечённый текст";
                break;
            case "TXT":
            default:
                text = readPlainText(file);
                note = "TXT • локальный файл";
                break;
        }
        return new ParsedBook(text, note);
    }

    public static int pageCountForText(String text) {
        if (text == null || text.length() == 0) return 1;
        return Math.max(1, (int) Math.ceil(text.length() / (double) PAGE_CHARACTERS));
    }

    public static String formatFromName(String filename) {
        if (filename == null) return "TXT";
        String lower = filename.toLowerCase(Locale.ROOT);
        if (lower.endsWith(".epub")) return "EPUB";
        if (lower.endsWith(".fb2") || lower.endsWith(".fb2.zip")) return "FB2";
        if (lower.endsWith(".pdf")) return "PDF";
        if (lower.endsWith(".docx")) return "DOCX";
        if (lower.endsWith(".html")) return "HTML";
        if (lower.endsWith(".htm")) return "HTM";
        return "TXT";
    }

    private static String readPlainText(File file) throws IOException {
        byte[] bytes = readAll(file, MAX_TEXT_SOURCE_BYTES);
        if (bytes.length >= 3 && (bytes[0] & 0xFF) == 0xEF && (bytes[1] & 0xFF) == 0xBB && (bytes[2] & 0xFF) == 0xBF) {
            return new String(bytes, 3, bytes.length - 3, StandardCharsets.UTF_8);
        }
        if (bytes.length >= 2 && (bytes[0] & 0xFF) == 0xFF && (bytes[1] & 0xFF) == 0xFE) {
            return new String(bytes, 2, bytes.length - 2, StandardCharsets.UTF_16LE);
        }
        if (bytes.length >= 2 && (bytes[0] & 0xFF) == 0xFE && (bytes[1] & 0xFF) == 0xFF) {
            return new String(bytes, 2, bytes.length - 2, StandardCharsets.UTF_16BE);
        }
        try {
            return StandardCharsets.UTF_8.newDecoder()
                    .onMalformedInput(CodingErrorAction.REPORT)
                    .onUnmappableCharacter(CodingErrorAction.REPORT)
                    .decode(ByteBuffer.wrap(bytes)).toString();
        } catch (CharacterCodingException ignored) {
            // Most legacy Russian plain-text books use this encoding.
            return new String(bytes, Charset.forName("windows-1251"));
        }
    }

    private static String readFb2(File file) throws IOException {
        String xml;
        String lower = file.getName().toLowerCase(Locale.ROOT);
        if (lower.endsWith(".zip")) {
            try (ZipFile zip = new ZipFile(file)) {
                ZipEntry source = null;
                Enumeration<? extends ZipEntry> entries = zip.entries();
                while (entries.hasMoreElements()) {
                    ZipEntry candidate = entries.nextElement();
                    if (!candidate.isDirectory() && candidate.getName().toLowerCase(Locale.ROOT).endsWith(".fb2")) {
                        source = candidate;
                        break;
                    }
                }
                if (source == null) throw new IOException("В архиве не найден FB2-файл");
                xml = readStream(zip.getInputStream(source), MAX_TEXT_SOURCE_BYTES);
            }
        } else {
            xml = readPlainText(file);
        }
        xml = xml.replaceAll("(?is)<binary\\b[^>]*>.*?</binary>", "");
        xml = xml.replaceAll("(?is)</?(?:p|v|subtitle|title|section|epigraph|poem|stanza|empty-line)\\b[^>]*>", "\n");
        return xmlToText(xml);
    }

    private static String readDocx(File file) throws IOException {
        try (ZipFile zip = new ZipFile(file)) {
            ZipEntry document = zip.getEntry("word/document.xml");
            if (document == null) throw new IOException("В DOCX не найден текст документа");
            String xml = readStream(zip.getInputStream(document), MAX_TEXT_SOURCE_BYTES);
            xml = xml.replaceAll("(?is)<w:tab\\b[^>]*/>", "\t");
            xml = xml.replaceAll("(?is)</w:p>", "\n\n");
            xml = xml.replaceAll("(?is)</w:tr>", "\n");
            return xmlToText(xml);
        }
    }

    private static String readEpub(File file) throws IOException {
        try (ZipFile zip = new ZipFile(file)) {
            ZipEntry container = zip.getEntry("META-INF/container.xml");
            String opfPath = null;
            if (container != null) {
                String containerXml = readStream(zip.getInputStream(container), 512 * 1024L);
                opfPath = attributeFromTag(containerXml, "rootfile", "full-path");
            }
            if (opfPath == null || opfPath.isEmpty()) {
                Enumeration<? extends ZipEntry> entries = zip.entries();
                while (entries.hasMoreElements()) {
                    ZipEntry entry = entries.nextElement();
                    if (entry.getName().toLowerCase(Locale.ROOT).endsWith(".opf")) {
                        opfPath = entry.getName();
                        break;
                    }
                }
            }
            if (opfPath == null) throw new IOException("В EPUB не найден файл структуры книги");
            opfPath = normalizeZipPath(opfPath);
            ZipEntry opf = zip.getEntry(opfPath);
            if (opf == null) throw new IOException("Повреждён EPUB: отсутствует OPF");
            String opfXml = readStream(zip.getInputStream(opf), 2 * 1024L * 1024L);

            Map<String, String> manifest = new LinkedHashMap<>();
            Matcher itemMatcher = Pattern.compile("(?is)<item\\b([^>]*)>").matcher(opfXml);
            while (itemMatcher.find()) {
                String attrs = itemMatcher.group(1);
                String id = attribute(attrs, "id");
                String href = attribute(attrs, "href");
                String media = attribute(attrs, "media-type");
                if (id != null && href != null && (media == null || media.contains("html") || media.contains("xhtml"))) {
                    manifest.put(id, href);
                }
            }

            ArrayList<String> chapters = new ArrayList<>();
            Matcher spineMatcher = Pattern.compile("(?is)<itemref\\b([^>]*)>").matcher(opfXml);
            while (spineMatcher.find()) {
                String idRef = attribute(spineMatcher.group(1), "idref");
                if (idRef != null && manifest.containsKey(idRef)) chapters.add(manifest.get(idRef));
            }
            // A few old EPUBs omit a usable spine. Reading all XHTML manifest entries is a useful fallback.
            if (chapters.isEmpty()) chapters.addAll(manifest.values());
            if (chapters.isEmpty()) throw new IOException("В EPUB не найдены главы с текстом");

            String opfDirectory = "";
            int separator = opfPath.lastIndexOf('/');
            if (separator >= 0) opfDirectory = opfPath.substring(0, separator + 1);
            StringBuilder allText = new StringBuilder();
            for (String href : chapters) {
                String chapterPath = normalizeZipPath(opfDirectory + decodeEntities(href));
                ZipEntry chapter = zip.getEntry(chapterPath);
                if (chapter == null) continue;
                String chapterHtml = readStream(zip.getInputStream(chapter), MAX_TEXT_SOURCE_BYTES);
                String chapterText = htmlToText(chapterHtml);
                if (!chapterText.isEmpty()) {
                    if (allText.length() > 0) allText.append("\n\n");
                    allText.append(chapterText);
                }
            }
            if (allText.length() == 0) throw new IOException("Не удалось извлечь текст глав EPUB");
            return allText.toString();
        }
    }

    private static String readPdf(Context context, File file) throws IOException {
        try {
            if (!pdfBoxReady) {
                synchronized (BookParser.class) {
                    if (!pdfBoxReady) {
                        PDFBoxResourceLoader.init(context.getApplicationContext());
                        pdfBoxReady = true;
                    }
                }
            }
            try (PDDocument document = PDDocument.load(file)) {
                PDFTextStripper stripper = new PDFTextStripper();
                return stripper.getText(document);
            }
        } catch (Exception exception) {
            throw new IOException("Не удалось прочитать текст PDF: " + safeMessage(exception), exception);
        }
    }

    private static String htmlToText(String html) {
        if (html == null) return "";
        String cleaned = html
                .replaceAll("(?is)<(script|style|head|svg)[^>]*>.*?</\\1>", "")
                .replaceAll("(?is)<br\\s*/?>", "\n")
                .replaceAll("(?is)</?(p|div|section|article|h[1-6]|li|blockquote|tr)\\b[^>]*>", "\n");
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N) {
            return Html.fromHtml(cleaned, Html.FROM_HTML_MODE_LEGACY).toString();
        }
        // minSdk is 26, but retaining this branch makes the helper safe if reused.
        //noinspection deprecation
        return Html.fromHtml(cleaned).toString();
    }

    private static String xmlToText(String xml) {
        if (xml == null) return "";
        String noDeclarations = xml.replaceAll("(?is)<\\?.*?\\?>", "")
                .replaceAll("(?is)<!DOCTYPE.*?(?:\\[.*?\\]>)?", "")
                .replaceAll("(?is)<[^>]+>", "");
        return decodeEntities(noDeclarations);
    }

    private static String normalizeText(String raw) {
        if (raw == null) return "";
        return raw.replace("\u00A0", " ")
                .replace("\r\n", "\n")
                .replace('\r', '\n')
                .replaceAll("[\\t\\x0B\\f ]+", " ")
                .replaceAll(" *\\n *", "\n")
                .replaceAll("\\n{3,}", "\n\n")
                .trim();
    }

    private static String readStream(InputStream input, long limit) throws IOException {
        try (InputStream source = input; ByteArrayOutputStream output = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[16 * 1024];
            long total = 0;
            int count;
            while ((count = source.read(buffer)) != -1) {
                total += count;
                if (total > limit) throw new IOException("Книга слишком велика для безопасного открытия");
                output.write(buffer, 0, count);
            }
            byte[] bytes = output.toByteArray();
            try {
                return StandardCharsets.UTF_8.newDecoder()
                        .onMalformedInput(CodingErrorAction.REPORT)
                        .onUnmappableCharacter(CodingErrorAction.REPORT)
                        .decode(ByteBuffer.wrap(bytes)).toString();
            } catch (CharacterCodingException ignored) {
                return new String(bytes, Charset.forName("windows-1251"));
            }
        }
    }

    private static byte[] readAll(File file, long limit) throws IOException {
        if (file.length() > limit) throw new IOException("Книга больше 70 МБ. Откройте файл меньшего размера.");
        try (FileInputStream input = new FileInputStream(file); ByteArrayOutputStream output = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[16 * 1024];
            int count;
            while ((count = input.read(buffer)) != -1) output.write(buffer, 0, count);
            return output.toByteArray();
        }
    }

    private static String attributeFromTag(String xml, String tag, String attribute) {
        Matcher matcher = Pattern.compile("(?is)<" + Pattern.quote(tag) + "\\b([^>]*)>").matcher(xml);
        return matcher.find() ? attribute(matcher.group(1), attribute) : null;
    }

    private static String attribute(String attributes, String name) {
        if (attributes == null) return null;
        Matcher matcher = Pattern.compile("(?is)\\b" + Pattern.quote(name) + "\\s*=\\s*(['\"])(.*?)\\1").matcher(attributes);
        return matcher.find() ? decodeEntities(matcher.group(2)) : null;
    }

    private static String normalizeZipPath(String path) {
        if (path == null) return "";
        String[] pieces = path.replace('\\', '/').split("/");
        ArrayList<String> normalized = new ArrayList<>();
        for (String piece : pieces) {
            if (piece.isEmpty() || ".".equals(piece)) continue;
            if ("..".equals(piece)) {
                if (!normalized.isEmpty()) normalized.remove(normalized.size() - 1);
            } else {
                normalized.add(piece);
            }
        }
        StringBuilder output = new StringBuilder();
        for (String piece : normalized) {
            if (output.length() > 0) output.append('/');
            output.append(piece);
        }
        return output.toString();
    }

    private static String decodeEntities(String source) {
        if (source == null) return "";
        String decoded = source.replace("&nbsp;", " ")
                .replace("&amp;", "&")
                .replace("&quot;", "\"")
                .replace("&apos;", "'")
                .replace("&lt;", "<")
                .replace("&gt;", ">");
        Matcher matcher = Pattern.compile("&#(x?[0-9a-fA-F]+);").matcher(decoded);
        StringBuffer result = new StringBuffer();
        while (matcher.find()) {
            String token = matcher.group(1);
            try {
                int codePoint = token.startsWith("x") || token.startsWith("X")
                        ? Integer.parseInt(token.substring(1), 16)
                        : Integer.parseInt(token);
                matcher.appendReplacement(result, Matcher.quoteReplacement(new String(Character.toChars(codePoint))));
            } catch (Exception ignored) {
                matcher.appendReplacement(result, Matcher.quoteReplacement(matcher.group()));
            }
        }
        matcher.appendTail(result);
        return result.toString();
    }

    private static String safeMessage(Exception exception) {
        String message = exception.getMessage();
        return message == null || message.trim().isEmpty() ? "неизвестная ошибка" : message;
    }
}
