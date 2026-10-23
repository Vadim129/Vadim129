package app.mastr.studio

import android.app.Activity
import android.content.ContentValues
import android.content.Context
import android.content.Intent
import android.media.MediaScannerConnection
import android.net.Uri
import android.os.Build
import android.os.Environment
import android.provider.MediaStore
import androidx.activity.result.contract.ActivityResultContract
import java.io.File

/** All providers, including those that mislabel WAV as application/octet-stream. */
class OpenAudioFile : ActivityResultContract<Unit, Uri?>() {
    override fun createIntent(context: Context, input: Unit): Intent = Intent.createChooser(
        Intent(Intent.ACTION_GET_CONTENT).addCategory(Intent.CATEGORY_OPENABLE).setType("*/*"),
        "Открыть аудиофайл"
    )
    override fun parseResult(resultCode: Int, intent: Intent?): Uri? =
        if (resultCode == Activity.RESULT_OK) intent?.data else null
}

object DownloadsStore {
    /** Publish atomically; no folder picker and no broad storage access on Android 10+. */
    fun save(context: Context, file: File, mime: String): Uri {
        require(mime == "audio/x-wav" || mime == "audio/mp4")
        val resolver = context.contentResolver
        if (Build.VERSION.SDK_INT >= 29) {
            val values = ContentValues().apply {
                put(MediaStore.Downloads.DISPLAY_NAME, file.name)
                put(MediaStore.Downloads.MIME_TYPE, mime)
                put(MediaStore.Downloads.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS)
                put(MediaStore.Downloads.IS_PENDING, 1)
            }
            val uri = requireNotNull(resolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values)) {
                "Не удалось создать файл в Загрузках"
            }
            try {
                resolver.openOutputStream(uri, "w").use { out ->
                    requireNotNull(out); file.inputStream().use { it.copyTo(out) }
                }
                check(resolver.update(uri, ContentValues().apply { put(MediaStore.Downloads.IS_PENDING, 0) }, null, null) > 0)
                return uri
            } catch (e: Throwable) { resolver.delete(uri, null, null); throw e }
        }
        @Suppress("DEPRECATION")
        val dir = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS)
        check(dir.isDirectory || dir.mkdirs()) { "Не удалось открыть Загрузки" }
        var target = File(dir, file.name)
        var suffix = 1
        while (!target.createNewFile()) target = File(dir, "${file.nameWithoutExtension} (${suffix++}).${file.extension}")
        try { file.inputStream().use { input -> target.outputStream().use { input.copyTo(it) } } }
        catch (e: Throwable) { target.delete(); throw e }
        MediaScannerConnection.scanFile(context, arrayOf(target.absolutePath), arrayOf(mime), null)
        return Uri.fromFile(target)
    }
}
