package app.mastr.studio

import android.app.Activity
import android.content.Intent
import android.net.Uri
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.Assert.*
import java.io.File

@RunWith(AndroidJUnit4::class)
class FileActionsTest {
    private val ctx get() = InstrumentationRegistry.getInstrumentation().targetContext
    @Test fun oneImportPathOffersAllFileManagersAndTypes() {
        val chooser = OpenAudioFile().createIntent(ctx, Unit)
        assertEquals(Intent.ACTION_CHOOSER, chooser.action)
        @Suppress("DEPRECATION") val underlying = chooser.getParcelableExtra<Intent>(Intent.EXTRA_INTENT)!!
        assertEquals(Intent.ACTION_GET_CONTENT, underlying.action)
        assertEquals("*/*", underlying.type)
        assertTrue(underlying.hasCategory(Intent.CATEGORY_OPENABLE))
        assertNull(OpenAudioFile().parseResult(Activity.RESULT_CANCELED, Intent().setData(Uri.parse("content://cancelled"))))
    }
    @Test fun downloadsPublishesValidWavWithNoPickerOrSecondLimiter() {
        val resolver = ctx.contentResolver
        val file = File(ctx.cacheDir, "MASTR-download-test-${System.nanoTime()}.wav")
        val audio = Audio(AudioEngine.demo().samples.copyOf(44100 * 2))
        AudioIO.writeWav(audio, file, 24)
        val uri = DownloadsStore.save(ctx, file, "audio/x-wav")
        try {
            assertEquals("audio/x-wav", resolver.getType(uri))
            resolver.query(uri, arrayOf("relative_path", "is_pending"), null, null, null)!!.use {
                assertTrue(it.moveToFirst()); assertEquals("Download/", it.getString(0)); assertEquals(0, it.getInt(1))
            }
            val saved = File(ctx.cacheDir, "download-readback.wav")
            try {
                resolver.openInputStream(uri)!!.use { input -> saved.outputStream().use { input.copyTo(it) } }
                assertArrayEquals(file.readBytes(), saved.readBytes())
                assertEquals(audio.frames, AudioIO.readWav(saved).frames)
                assertEquals(AudioEngine.analyze(audio).lufs, AudioEngine.analyze(AudioIO.readWav(saved)).lufs, .001)
            } finally { saved.delete() }
        } finally { resolver.delete(uri, null, null); file.delete() }
    }
    @Test fun updateParserSkipsUnrelatedDraftAndUnsafeAssets() {
        val release = """[{"tag_name":"v99.0.0","assets":[]},{"tag_name":"mastr-v1.2.0","draft":false,"prerelease":false,"body":"Test","assets":[{"name":"MASTR-Studio-1.2.0.apk","size":10,"browser_download_url":"https://github.com/Vadim129/Vadim129/releases/download/mastr-v1.2.0/MASTR-Studio-1.2.0.apk"}]}]"""
        assertEquals("1.2.0", AppUpdates.parse(release, "1.1.0")!!.version)
        assertNull(AppUpdates.parse(release, "1.2.0"))
        assertNull(AppUpdates.parse(release.replace("https://github.com/", "http://github.com/"), "1.1.0"))
        assertNull(AppUpdates.parse(release.replace("\"draft\":false", "\"draft\":true"), "1.1.0"))
        assertNull(AppUpdates.parse(release.replace("\"prerelease\":false", "\"prerelease\":true"), "1.1.0"))
    }
    @Test fun updateScheduleAndNumericVersions() {
        assertTrue(AppUpdates.due(0, 100)); assertFalse(AppUpdates.due(100, 101))
        assertTrue(AppUpdates.due(100, 100 + AppUpdates.WEEK_MS))
        assertTrue(AppUpdates.isNewer("1.10.0", "1.9.0"))
        assertFalse(AppUpdates.isNewer("1.0.0", "1.1.0"))
        assertFalse(AppUpdates.isNewer("1.2.0-beta", "1.1.0"))
    }
    @Test fun upgradeRemovesPreviouslyDownloadedNetworkAndStemCache() {
        val model = File(ctx.filesDir, "UVR_MDXNET_Main.onnx"); model.writeText("migration test")
        val partial = File(ctx.filesDir, "UVR_MDXNET_Main.onnx.part"); partial.writeText("partial")
        val stem = File(ctx.cacheDir, "vocals-test.wav"); stem.writeText("stem cache")
        StudioViewModel(ctx.applicationContext as android.app.Application)
        assertFalse(model.exists()); assertFalse(partial.exists()); assertFalse(stem.exists())
    }
}
