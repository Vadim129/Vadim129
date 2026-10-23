package app.mastr.studio

import android.content.Context
import ai.onnxruntime.*
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.nio.FloatBuffer
import java.security.MessageDigest
import org.json.JSONObject
import kotlin.math.*

data class Stems(val vocals:File,val instrumental:File)
class StemSeparator(private val context:Context) {
    val info=JSONObject(context.assets.open("model_info.json").bufferedReader().use {it.readText()})
    private val model=File(context.filesDir,info.getString("filename"))
    val isReady get()=model.exists()&&model.length()==info.getLong("size")
    private fun sha(file:File):String {val digest=MessageDigest.getInstance("SHA-256");file.inputStream().buffered().use {input->val b=ByteArray(65536);while(true){val n=input.read(b);if(n<0)break;digest.update(b,0,n)}};return digest.digest().joinToString(""){"%02x".format(it)}}
    fun download(progress:(Float,String)->Unit) {
        val expected=info.getString("sha256");require(expected.length==64){"В сборке нет проверенной конфигурации AI-модели"}
        if(isReady&&sha(model)==expected)return
        val part=File(context.filesDir,model.name+".part");part.delete();var connection:HttpURLConnection?=null
        try{
            connection=URL(info.getString("url")).openConnection() as HttpURLConnection
            connection.connectTimeout=25000;connection.readTimeout=30000;connection.instanceFollowRedirects=true;connection.setRequestProperty("User-Agent","MastrStudio/1.0")
            require(connection.responseCode==200){"Не удалось скачать модель (${connection.responseCode}). Проверьте интернет."}
            val expectedSize=info.getLong("size");var total=0L
            connection.inputStream.buffered().use {input->part.outputStream().buffered().use {output->val b=ByteArray(65536);while(true){val n=input.read(b);if(n<0)break;output.write(b,0,n);total+=n;require(total<=expectedSize){"Неверный размер модели"};progress((total.toFloat()/expectedSize).coerceIn(0f,1f),"AI-модель: ${total/1_000_000} / ${expectedSize/1_000_000} МБ")}}}
            require(part.length()==expectedSize&&sha(part)==expected){"Проверка модели не пройдена. Повторите загрузку."}
            if(model.exists())model.delete();check(part.renameTo(model)){"Не удалось сохранить модель"}
        }finally{connection?.disconnect();part.delete()}
    }
    fun separate(audio:Audio,progress:(Float,String)->Unit):Stems {
        require(audio.rate==44100&&audio.frames>0)
        require(isReady){"Сначала загрузите AI-модель"}
        require(sha(model)==info.getString("sha256")){"Модель повреждена. Удалите и загрузите её заново."}
        val transform=SpectralTransform(info.getInt("n_fft"),info.getInt("dim_f"),info.getInt("dim_t"))
        val trim=transform.nfft/2;val usable=transform.chunk-trim*2;val compensate=info.getDouble("compensate").toFloat()
        val env=OrtEnvironment.getEnvironment()
        val options=OrtSession.SessionOptions();options.setIntraOpNumThreads(min(2,Runtime.getRuntime().availableProcessors()));options.setInterOpNumThreads(1);options.setOptimizationLevel(OrtSession.SessionOptions.OptLevel.ALL_OPT)
        val vocalFile=File(context.cacheDir,"vocals-${System.nanoTime()}.wav");val instFile=File(context.cacheDir,"instrumental-${System.nanoTime()}.wav")
        var success=false
        try{
            env.createSession(model.absolutePath,options).use { session->
                val inputName=session.inputNames.first();val shape=longArrayOf(1,4,transform.frequencies.toLong(),transform.times.toLong())
                AudioIO.WavWriter(vocalFile,floating=true).use { vocalWriter->AudioIO.WavWriter(instFile,floating=true).use { instWriter->
                    var start=0
                    while(start<audio.frames){
                        progress(start.toFloat()/audio.frames,"Разделение: ${(start/44100)} / ${audio.frames/44100} сек")
                        val chunk=FloatArray(transform.chunk*2)
                        for(i in 0 until transform.chunk){val source=start-trim+i;if(source in 0 until audio.frames){chunk[2*i]=audio.samples[2*source];chunk[2*i+1]=audio.samples[2*source+1]}}
                        val spectrum=transform.forward(chunk)
                        // Consistent with UVR MDX inference: ignore subsonic/DC bins.
                        for(c in 0..3)for(f in 0..2)for(t in 0 until transform.times)spectrum[(c*transform.frequencies+f)*transform.times+t]=0f
                        val predicted=OnnxTensor.createTensor(env,FloatBuffer.wrap(spectrum),shape).use { tensor->session.run(mapOf(inputName to tensor)).use { result->
                            val output=result[0] as? OnnxTensor ?: error("Неверный выход модели")
                            val buffer=output.floatBuffer;val data=FloatArray(buffer.remaining());buffer.get(data);data
                        }}
                        require(predicted.size==spectrum.size&&predicted.all {it.isFinite()}){"Модель вернула некорректный результат"}
                        val time=transform.inverse(predicted);val count=min(usable,audio.frames-start);val vocals=FloatArray(count*2);val instrumental=FloatArray(count*2)
                        for(i in vocals.indices){val v=time[trim*2+i]*compensate;vocals[i]=v;instrumental[i]=audio.samples[start*2+i]-v}
                        // Float WAV retains headroom. Export applies sample-peak protection.
                        vocalWriter.append(vocals);instWriter.append(instrumental);start+=count
                    }
                }}
            }
            success=true;progress(1f,"Две дорожки готовы")
            return Stems(vocalFile,instFile)
        }finally{options.close();if(!success){vocalFile.delete();instFile.delete()}}
    }
    fun removeModel(){model.delete()}
}
