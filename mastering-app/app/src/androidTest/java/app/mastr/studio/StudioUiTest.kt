package app.mastr.studio
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import org.junit.Rule
import org.junit.Test

class StudioUiTest {
    @get:Rule val rule=createAndroidComposeRule<MainActivity>()
    @Test fun demoMasterAndExportDialog(){rule.onNodeWithTag("demo").performClick();rule.waitUntil(20000){rule.onAllNodesWithTag("render").fetchSemanticsNodes().isNotEmpty()};rule.onNodeWithTag("render").performScrollTo().performClick();rule.waitUntil(30000){rule.onAllNodesWithTag("export").fetchSemanticsNodes().isNotEmpty()};rule.onNodeWithTag("export").performScrollTo().performClick();rule.onNodeWithText("Экспорт аудио").assertIsDisplayed();rule.onNodeWithText("WAV · 24 бит").assertIsDisplayed()}
    @Test fun navigationWorks(){rule.onNodeWithTag("tab-stems").performClick();rule.onNodeWithText("UVR · MDX-Net").assertIsDisplayed();rule.onNodeWithTag("tab-library").performClick();rule.onNodeWithText("Мои пресеты").assertIsDisplayed()}
}
