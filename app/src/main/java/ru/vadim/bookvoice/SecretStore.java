package ru.vadim.bookvoice;

import android.content.Context;
import android.content.SharedPreferences;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.Key;
import java.security.KeyStore;
import java.security.SecureRandom;

import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;
import javax.crypto.spec.SecretKeySpec;

/**
 * Stores a user-supplied cloud key locally. Android Keystore is always tried
 * first. Some OEM ROMs expose a broken/invalidated Keystore AES entry; on
 * those devices an AES key in the app's private no-backup directory keeps the
 * feature usable without ever placing the API key in SharedPreferences as text.
 */
final class SecretStore {
    private static final String ANDROID_KEYSTORE = "AndroidKeyStore";
    private static final String KEY_ALIAS = "bookvoice_gemini_key_v2";
    private static final String LEGACY_KEY_ALIAS = "bookvoice_gemini_key_v1";
    private static final String PREFS = "bookvoice_secrets";
    private static final String HARDWARE_PREFIX = "k";
    private static final String PRIVATE_PREFIX = "p";
    private static final int AES_KEY_BYTES = 32;
    private static final SecureRandom RANDOM = new SecureRandom();

    private final SharedPreferences preferences;
    private final File privateKeyFile;

    SecretStore(Context context) {
        Context app = context.getApplicationContext();
        preferences = app.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        File directory = app.getNoBackupFilesDir();
        if (directory == null) directory = app.getFilesDir();
        privateKeyFile = new File(directory, ".bookvoice-gemini-key-material-v1");
    }

    String get(String name) {
        String packed = preferences.getString(name, "");
        if (packed == null || packed.isEmpty()) return "";
        try {
            String[] pieces = packed.split(":", 3);
            if (pieces.length == 2) {
                // Compatibility with the first 1.1.0 format: IV:ciphertext.
                return decrypt(pieces[0], pieces[1], getOrCreateHardwareKey());
            }
            if (pieces.length != 3) throw new IllegalStateException("Неверный формат секрета");
            if (PRIVATE_PREFIX.equals(pieces[0])) {
                return decrypt(pieces[1], pieces[2], getPrivateKey());
            }
            if (HARDWARE_PREFIX.equals(pieces[0])) {
                return decrypt(pieces[1], pieces[2], getOrCreateHardwareKey());
            }
            throw new IllegalStateException("Неизвестный формат секрета");
        } catch (Exception ignored) {
            // A stale Keystore record must not permanently block entering a new key.
            clearStoredValue(name);
            deleteHardwareKeyQuietly();
            return "";
        }
    }

    /**
     * @return true only when the device Keystore was unavailable and the
     * app-private encrypted fallback was used.
     */
    boolean put(String name, String value) throws Exception {
        if (value == null || value.trim().isEmpty()) {
            remove(name);
            return false;
        }
        String normalized = value.trim();
        try {
            String packed = encrypt(HARDWARE_PREFIX, normalized, getOrCreateHardwareKey());
            save(name, packed);
            deletePrivateKeyQuietly();
            return false;
        } catch (Exception hardwareFailure) {
            // Broken aliases are unfortunately common after restoring Android backups
            // or on a few vendor ROMs. Do not keep retrying the same bad key.
            deleteHardwareKeyQuietly();
            String packed = encrypt(PRIVATE_PREFIX, normalized, getPrivateKey());
            save(name, packed);
            return true;
        }
    }

    boolean usesPrivateFallback(String name) {
        String packed = preferences.getString(name, "");
        return packed != null && packed.startsWith(PRIVATE_PREFIX + ":");
    }

    void remove(String name) {
        clearStoredValue(name);
        deleteHardwareKeyQuietly();
        deletePrivateKeyQuietly();
    }

    private void save(String name, String packed) throws IOException {
        if (!preferences.edit().putString(name, packed).commit()) {
            throw new IOException("Не удалось записать ключ в хранилище приложения");
        }
    }

    private void clearStoredValue(String name) {
        preferences.edit().remove(name).commit();
    }

    private static String encrypt(String prefix, String value, SecretKey key) throws Exception {
        byte[] iv = new byte[12];
        RANDOM.nextBytes(iv);
        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.ENCRYPT_MODE, key, new GCMParameterSpec(128, iv));
        byte[] encrypted = cipher.doFinal(value.getBytes(StandardCharsets.UTF_8));
        return prefix + ":" + Base64.encodeToString(iv, Base64.NO_WRAP) + ":"
                + Base64.encodeToString(encrypted, Base64.NO_WRAP);
    }

    private static String decrypt(String encodedIv, String encodedCiphertext, SecretKey key) throws Exception {
        byte[] iv = Base64.decode(encodedIv, Base64.NO_WRAP);
        byte[] encrypted = Base64.decode(encodedCiphertext, Base64.NO_WRAP);
        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.DECRYPT_MODE, key, new GCMParameterSpec(128, iv));
        return new String(cipher.doFinal(encrypted), StandardCharsets.UTF_8);
    }

    private SecretKey getOrCreateHardwareKey() throws Exception {
        KeyStore keyStore = KeyStore.getInstance(ANDROID_KEYSTORE);
        keyStore.load(null);
        if (keyStore.containsAlias(KEY_ALIAS)) {
            Key existing = keyStore.getKey(KEY_ALIAS, null);
            if (existing instanceof SecretKey) return (SecretKey) existing;
            keyStore.deleteEntry(KEY_ALIAS);
        }
        KeyGenerator generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, ANDROID_KEYSTORE);
        generator.init(new KeyGenParameterSpec.Builder(KEY_ALIAS,
                KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setRandomizedEncryptionRequired(true)
                .build());
        return generator.generateKey();
    }

    private SecretKey getPrivateKey() throws Exception {
        if (privateKeyFile.isFile()) {
            byte[] encoded = readSmallFile(privateKeyFile, 256);
            byte[] bytes = Base64.decode(encoded, Base64.NO_WRAP);
            if (bytes.length == AES_KEY_BYTES) return new SecretKeySpec(bytes, "AES");
            deletePrivateKeyQuietly();
        }
        File directory = privateKeyFile.getParentFile();
        if (directory != null && !directory.exists() && !directory.mkdirs()) {
            throw new IOException("Не удалось подготовить закрытое хранилище");
        }
        byte[] bytes = new byte[AES_KEY_BYTES];
        RANDOM.nextBytes(bytes);
        try (FileOutputStream output = new FileOutputStream(privateKeyFile)) {
            output.write(Base64.encode(bytes, Base64.NO_WRAP));
            output.getFD().sync();
        }
        return new SecretKeySpec(bytes, "AES");
    }

    private static byte[] readSmallFile(File file, int maximum) throws IOException {
        long size = file.length();
        if (size <= 0 || size > maximum) throw new IOException("Некорректный файл ключа");
        byte[] result = new byte[(int) size];
        int offset = 0;
        try (FileInputStream input = new FileInputStream(file)) {
            while (offset < result.length) {
                int count = input.read(result, offset, result.length - offset);
                if (count < 0) break;
                offset += count;
            }
        }
        if (offset != result.length) throw new IOException("Не удалось прочитать файл ключа");
        return result;
    }

    private void deleteHardwareKeyQuietly() {
        try {
            KeyStore keyStore = KeyStore.getInstance(ANDROID_KEYSTORE);
            keyStore.load(null);
            if (keyStore.containsAlias(KEY_ALIAS)) keyStore.deleteEntry(KEY_ALIAS);
            if (keyStore.containsAlias(LEGACY_KEY_ALIAS)) keyStore.deleteEntry(LEGACY_KEY_ALIAS);
        } catch (Exception ignored) {
        }
    }

    private void deletePrivateKeyQuietly() {
        try {
            if (privateKeyFile.exists()) privateKeyFile.delete();
        } catch (Exception ignored) {
        }
    }
}
