package app.mastr.studio
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import org.junit.Rule
import org.junit.Test

class StudioUiTest {
    @get:Rule val rule = createAndroidComposeRule<MainActivity>()
    @Test fun demoMasterAndExportDialog() {
        rule.onNodeWithTag("demo").performClick()
        rule.waitUntil(20000) { rule.onAllNodesWithTag("render").fetchSemanticsNodes().isNotEmpty() }
        rule.onNodeWithText("Интенсивность").assertDoesNotExist()
        rule.onNodeWithTag("render").performScrollTo().performClick()
        rule.waitUntil(60000) { rule.onAllNodesWithTag("export").fetchSemanticsNodes().isNotEmpty() }
        rule.onNodeWithTag("play-original").performClick()
        rule.onNodeWithTag("play-master").performClick()
        rule.onNodeWithTag("export").performScrollTo().performClick()
        rule.onNodeWithText("Экспорт аудио").assertIsDisplayed()
        rule.onNodeWithText("WAV · 24 бит").assertIsDisplayed()
        rule.onNodeWithTag("save-downloads").assertIsDisplayed()
        lateinit var vm: StudioViewModel
        rule.activityRule.scenario.onActivity { vm = androidx.lifecycle.ViewModelProvider(it)[StudioViewModel::class.java] }
        val previous = vm.state.value.history.size
        rule.onNodeWithTag("save-downloads").performClick()
        rule.waitUntil(30000) { !vm.state.value.busy && vm.state.value.history.size > previous }
        val name = vm.state.value.history.first().name
        val resolver = rule.activity.contentResolver
        resolver.query(android.provider.MediaStore.Downloads.EXTERNAL_CONTENT_URI, arrayOf("_id"), "_display_name = ?", arrayOf(name), null)!!.use {
            org.junit.Assert.assertTrue(it.moveToFirst())
            val uri = android.content.ContentUris.withAppendedId(android.provider.MediaStore.Downloads.EXTERNAL_CONTENT_URI, it.getLong(0))
            val copy = java.io.File(rule.activity.cacheDir, "ui-export-readback.wav")
            try {
                resolver.openInputStream(uri)!!.use { input -> copy.outputStream().use { input.copyTo(it) } }
                val decoded = AudioIO.readWav(copy)
                org.junit.Assert.assertEquals(vm.state.value.master!!.frames, decoded.frames)
                org.junit.Assert.assertEquals(vm.state.value.masteredAnalysis!!.lufs, AudioEngine.analyze(decoded).lufs, .001)
            } finally { copy.delete(); resolver.delete(uri, null, null) }
        }
    }
    @Test fun libraryAndManualUpdatesAreAccessibleWithoutNeuralFeatures() {
        rule.onNodeWithTag("tab-library").performClick()
        rule.onNodeWithText("Проверить обновления").assertIsDisplayed()
        rule.onNodeWithText("UVR · MDX-Net").assertDoesNotExist()
        rule.onNodeWithTag("tab-stems").assertDoesNotExist()
    }
    @Test fun aboutContainsVersionAndManualCheck() {
        rule.onNodeWithContentDescription("О приложении").performClick()
        rule.onNodeWithTag("check-updates").assertIsDisplayed()
        rule.onNodeWithText("MASTR Studio ${BuildConfig.VERSION_NAME}").assertIsDisplayed()
    }
}
