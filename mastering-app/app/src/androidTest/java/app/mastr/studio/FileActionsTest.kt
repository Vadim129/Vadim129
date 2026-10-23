package app.mastr.studio

import android.app.Activity
import android.content.ContentValues
import android.content.Intent
import android.net.Uri
import android.provider.MediaStore
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.Assert.*
import java.io.File

@RunWith(AndroidJUnit4::class)
class FileActionsTest {
    private val ctx get()=InstrumentationRegistry.getInstrumentation().targetContext
    @Test fun wavAndM4aCreateDocumentsHaveExactTypes(){
        for((name,mime) in listOf("test.wav" to "audio/x-wav","test.m4a" to "audio/mp4")){
            val intent=SaveAudioDocument().createIntent(ctx,AudioExportRequest(name,mime))
            assertEquals(Intent.ACTION_CREATE_DOCUMENT,intent.action)
            assertEquals(mime,intent.type)
            assertEquals(name,intent.getStringExtra(Intent.EXTRA_TITLE))
            assertTrue(intent.hasCategory(Intent.CATEGORY_OPENABLE))
        }
    }
    @Test fun wildcardExportIsRejected(){
        try{AudioExportRequest("test.wav","audio/*");fail("Wildcard MIME must never reach a document provider")}catch(_:IllegalArgumentException){}
    }
    @Test fun importOffersManagersAndAllFiles(){
        for(mode in listOf(AudioImportMode.AUDIO,AudioImportMode.ALL_FILES)){
            val chooser=OpenAudioFile().createIntent(ctx,mode)
            assertEquals(Intent.ACTION_CHOOSER,chooser.action)
            @Suppress("DEPRECATION") val underlying=chooser.getParcelableExtra<Intent>(Intent.EXTRA_INTENT)!!
            assertEquals(Intent.ACTION_GET_CONTENT,underlying.action)
            assertEquals(if(mode==AudioImportMode.AUDIO)"audio/*"else"*/*",underlying.type)
            assertTrue(underlying.hasCategory(Intent.CATEGORY_OPENABLE))
        }
        val documents=OpenAudioFile().createIntent(ctx,AudioImportMode.DOCUMENTS)
        assertEquals(Intent.ACTION_OPEN_DOCUMENT,documents.action);assertEquals("*/*",documents.type)
        assertNull(OpenAudioFile().parseResult(Activity.RESULT_CANCELED,Intent().setData(Uri.parse("content://cancelled"))))
    }
    @Test fun androidProviderRecognizesSavedWavAndHeader(){
        val resolver=ctx.contentResolver
        val name="MASTR-mime-test-${System.nanoTime()}.wav"
        val values=ContentValues().apply{put(MediaStore.Audio.Media.DISPLAY_NAME,name);put(MediaStore.Audio.Media.MIME_TYPE,"audio/x-wav");put(MediaStore.Audio.Media.RELATIVE_PATH,"Music/MASTRTests");put(MediaStore.Audio.Media.IS_PENDING,1)}
        val uri=resolver.insert(MediaStore.Audio.Media.EXTERNAL_CONTENT_URI,values)!!
        val temp=File(ctx.cacheDir,name)
        try{
            AudioIO.writeWav(Audio(AudioEngine.demo().samples.copyOf(44100*2)),temp,24)
            resolver.openOutputStream(uri,"w")!!.use{out->temp.inputStream().use{it.copyTo(out)}}
            resolver.update(uri,ContentValues().apply{put(MediaStore.Audio.Media.IS_PENDING,0)},null,null)
            assertEquals("audio/x-wav",resolver.getType(uri))
            val header=ByteArray(12);resolver.openInputStream(uri)!!.use{java.io.DataInputStream(it).readFully(header)}
            assertEquals("RIFF",String(header,0,4));assertEquals("WAVE",String(header,8,4))
            val decoded=AudioIO.decode(ctx,uri){_,_->};assertEquals(44100,decoded.frames)
        }finally{resolver.delete(uri,null,null);temp.delete()}
    }
}
