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
