package app.mastr.studio

import android.app.Activity
import android.content.Context
import android.content.Intent
import android.net.Uri
import androidx.activity.result.contract.ActivityResultContract

/** A concrete MIME type is mandatory: wildcards are NOT valid document types. */
data class AudioExportRequest(val name:String,val mime:String) {
    init { require(mime=="audio/wav" || mime=="audio/mp4") }
}
enum class AudioImportMode { AUDIO, ALL_FILES, DOCUMENTS }

class SaveAudioDocument:ActivityResultContract<AudioExportRequest,Uri?>() {
    override fun createIntent(context:Context,input:AudioExportRequest):Intent =
        Intent(Intent.ACTION_CREATE_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE)
            .setType(input.mime).putExtra(Intent.EXTRA_TITLE,input.name)
    override fun parseResult(resultCode:Int,intent:Intent?):Uri? =
        if(resultCode==Activity.RESULT_OK)intent?.data else null
}

/** GET_CONTENT can expose installed file managers as well as DocumentsUI.
 * The all-files path handles WAVs incorrectly labelled as octet-stream by providers.
 * A separate OPEN_DOCUMENT path retains the standard provider sidebar option.
 * Access is scoped to the selected URI; no all-files / broad storage permission.
 */
class OpenAudioFile:ActivityResultContract<AudioImportMode,Uri?>() {
    override fun createIntent(context:Context,input:AudioImportMode):Intent {
        val intent=Intent(if(input==AudioImportMode.DOCUMENTS)Intent.ACTION_OPEN_DOCUMENT else Intent.ACTION_GET_CONTENT)
            .addCategory(Intent.CATEGORY_OPENABLE)
            .setType(if(input==AudioImportMode.AUDIO)"audio/*" else "*/*")
        return if(input==AudioImportMode.DOCUMENTS)intent
            else Intent.createChooser(intent,if(input==AudioImportMode.AUDIO)"Откуда открыть аудио?" else "Выберите файл или файловый менеджер")
    }
    override fun parseResult(resultCode:Int,intent:Intent?):Uri? =
        if(resultCode==Activity.RESULT_OK)intent?.data else null
}
