package app.mastr.studio

import android.app.DownloadManager
import android.content.Context
import android.net.Uri
import android.os.Environment
import org.json.JSONArray
import java.net.HttpURLConnection
import java.net.URL

/** Dedicated MASTR tags: unrelated InkClip releases in the same repository are ignored. */
data class AppRelease(val version: String, val url: String, val notes: String)
object AppUpdates {
    const val WEEK_MS = 7L * 24 * 60 * 60 * 1000
    private const val REPO = "Vadim129/Vadim129"
    fun isNewer(remote: String, current: String): Boolean {
        fun parts(s: String): List<Int>? = s.split('.').takeIf { it.size == 3 }?.map { it.toIntOrNull() ?: return null }
        val a = parts(remote) ?: return false
        val b = parts(current) ?: return false
        for (i in 0..2) if (a[i] != b[i]) return a[i] > b[i]
        return false
    }
    fun due(last: Long, now: Long): Boolean = last == 0L || now < last || now - last >= WEEK_MS
    fun parse(json: String, current: String): AppRelease? {
        val list = JSONArray(json)
        var best: AppRelease? = null
        for (i in 0 until list.length()) {
            val r = list.getJSONObject(i)
            if (r.optBoolean("draft") || r.optBoolean("prerelease")) continue
            val tag = r.optString("tag_name")
            if (!tag.matches(Regex("mastr-v[0-9]+\\.[0-9]+\\.[0-9]+"))) continue
            val version = tag.removePrefix("mastr-v")
            if (!isNewer(version, current) || (best != null && !isNewer(version, best.version))) continue
            val assets = r.optJSONArray("assets") ?: continue
            for (j in 0 until assets.length()) {
                val asset = assets.getJSONObject(j)
                val expected = "MASTR-Studio-$version.apk"
                val url = asset.optString("browser_download_url")
                if (asset.optString("name") == expected && asset.optLong("size") > 0 &&
                    url == "https://github.com/$REPO/releases/download/$tag/$expected") {
                    best = AppRelease(version, url, r.optString("body").take(1800)); break
                }
            }
        }
        return best
    }
    fun check(current: String): AppRelease? {
        val connection = URL("https://api.github.com/repos/$REPO/releases?per_page=100").openConnection() as HttpURLConnection
        try {
            connection.connectTimeout = 10000; connection.readTimeout = 10000
            connection.setRequestProperty("Accept", "application/vnd.github+json")
            connection.setRequestProperty("User-Agent", "MASTR-Studio/$current")
            check(connection.responseCode == 200) { "GitHub недоступен (${connection.responseCode}). Попробуйте позже." }
            val bytes = connection.inputStream.use { input ->
                val out = java.io.ByteArrayOutputStream()
                val buffer = ByteArray(8192)
                while (true) {
                    val n = input.read(buffer); if (n < 0) break
                    out.write(buffer, 0, n); check(out.size() <= 2_000_000) { "Слишком большой ответ GitHub" }
                }
                out.toByteArray()
            }
            check(bytes.size <= 2_000_000) { "Слишком большой ответ GitHub" }
            return parse(bytes.toString(Charsets.UTF_8), current)
        } finally { connection.disconnect() }
    }
    fun download(context: Context, release: AppRelease): Long {
        // Only an explicit user tap enqueues a download; installation is never silent.
        require(release.url == "https://github.com/$REPO/releases/download/mastr-v${release.version}/MASTR-Studio-${release.version}.apk")
        val request = DownloadManager.Request(Uri.parse(release.url))
            .setTitle("MASTR Studio ${release.version}")
            .setDescription("Обновление приложения с GitHub")
            .setMimeType("application/vnd.android.package-archive")
            .setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
            .setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, "MASTR-Studio-${release.version}-${System.currentTimeMillis()}.apk")
        return (context.getSystemService(Context.DOWNLOAD_SERVICE) as DownloadManager).enqueue(request)
    }
}
