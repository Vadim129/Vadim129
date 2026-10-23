package app.mastr.studio

import android.app.Application
import android.media.*
import android.net.Uri
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import kotlin.math.*

data class ExportEntry(val name:String,val detail:String,val date:Long)
data class StudioState(
    val tab:Int=0,val trackName:String="",val audio:Audio?=null,val master:Audio?=null,
    val analysis:Analysis?=null,val masteredAnalysis:Analysis?=null,
    val presetId:String="balanced",val settings:Settings=Presets.all.first().settings,
    val category:String="Все",val query:String="",val favorites:Set<String> = emptySet(),val customs:List<Preset> = emptyList(),
    val busy:Boolean=false,val progress:Float=0f,val task:String="",val error:String?=null,
    val stems:Stems?=null,val modelReady:Boolean=false,val source:String="original",
    val playing:Boolean=false,val position:Float=0f,val volume:Float=.85f,val advanced:Boolean=false,
    val history:List<ExportEntry> = emptyList(),val savedMaster:Boolean=false
)
class StudioViewModel(app:Application):AndroidViewModel(app) {
    private val prefs=app.getSharedPreferences("studio",0)
    private val separator=StemSeparator(app)
    private val _state=MutableStateFlow(StudioState(modelReady=separator.isReady))
    val state:StateFlow<StudioState> = _state.asStateFlow()
    private var work:Job?=null;private var playback:Job?=null
    private var currentTrack:AudioTrack?=null
    @Volatile private var playFrame=0
    @Volatile private var playVersion=0
    private var prepared:File?=null
    init {
        val favorite=prefs.getStringSet("favorites",emptySet())?.toSet() ?: emptySet()
        val histories=runCatching{val a=JSONArray(prefs.getString("history","[]"));(0 until a.length()).map { val o=a.getJSONObject(it);ExportEntry(o.getString("name"),o.getString("detail"),o.getLong("date")) }}.getOrDefault(emptyList())
        val custom=runCatching{val a=JSONArray(prefs.getString("customs","[]"));(0 until a.length()).map { val o=a.getJSONObject(it);Preset(o.getString("id"),o.getString("name"),"Мои","Сохранённые настройки","CUSTOM",settingsFromJson(o.getJSONObject("settings"))) }}.getOrDefault(emptyList())
        _state.update {it.copy(favorites=favorite,history=histories,customs=custom)}
        // Old temporary files expire; model and saved presets are kept.
        app.cacheDir.listFiles()?.filter {System.currentTimeMillis()-it.lastModified()>86_400_000}?.forEach {it.delete()}
    }
    fun tab(index:Int){_state.update {it.copy(tab=index)}}
    fun category(c:String){_state.update{it.copy(category=c)}}
    fun query(q:String){_state.update{it.copy(query=q)}}
    fun errorHandled(){_state.update{it.copy(error=null)}}
    fun advanced(){_state.update{it.copy(advanced=!it.advanced)}}
    fun favorite(id:String){val ids=state.value.favorites.toMutableSet();if(!ids.add(id))ids.remove(id);prefs.edit().putStringSet("favorites",ids).apply();_state.update{it.copy(favorites=ids)}}
    fun select(p:Preset){if(state.value.busy)return;stop();_state.update{it.copy(presetId=p.id,settings=p.settings,master=null,masteredAnalysis=null,source="original",savedMaster=false)}}
    fun settings(s:Settings){if(state.value.busy)return;stop();_state.update{it.copy(settings=s,master=null,masteredAnalysis=null,source="original",savedMaster=false)}}
    fun autoPreset(){val a=state.value.analysis?:return;val id=when{a.lowRatio>.57->"clarity";a.peak-a.rms<7->"dynamic";a.lufs < -23->"demo";else->"balanced"};select(Presets.all.first{it.id==id})}
    private fun launchTask(title:String,block:suspend CoroutineScope.()->Unit){if(state.value.busy)return;stop();_state.update{it.copy(busy=true,progress=0f,task=title,error=null)};work=viewModelScope.launch(Dispatchers.Default){try{block()}catch(_:CancellationException){}catch(e:OutOfMemoryError){_state.update{it.copy(error="Недостаточно памяти. Закройте другие приложения или выберите более короткий трек.")}}catch(e:Exception){_state.update{it.copy(error=e.message?:"Не удалось выполнить операцию")}}finally{_state.update{it.copy(busy=false,task="",progress=0f)}}}}
    private fun progress(job:Job):(Float,String)->Unit = {p,t->job.ensureActive();_state.update{it.copy(progress=p.coerceIn(0f,1f),task=t)}}
    fun import(uri:Uri){launchTask("Открываем трек"){val callback=progress(currentCoroutineContext().job);val name=AudioIO.name(getApplication(),uri);val a=AudioIO.decode(getApplication(),uri,callback);callback(.94f,"Анализ громкости");val stats=AudioEngine.analyze(a);state.value.stems?.let{it.vocals.delete();it.instrumental.delete()};_state.update{it.copy(trackName=name,audio=a,master=null,analysis=stats,masteredAnalysis=null,stems=null,source="original",position=0f,savedMaster=false)}}}
    fun demo(){launchTask("Создаём демотрек"){val a=AudioEngine.demo();_state.update{it.copy(trackName="Демо • 12 сек",audio=a,analysis=AudioEngine.analyze(a),master=null,masteredAnalysis=null,stems=null,source="original",position=0f,savedMaster=false)}}}
    fun render(){val a=state.value.audio?:return;val s=state.value.settings;launchTask("Мастеринг"){val result=AudioEngine.master(a,s,progress(currentCoroutineContext().job));val stats=AudioEngine.analyze(result);_state.update{it.copy(master=result,masteredAnalysis=stats,source="master",position=0f,savedMaster=false)}}}
    fun split(){val a=state.value.audio?:return;launchTask("Подготовка AI"){val p=progress(currentCoroutineContext().job);separator.download{v,t->p(v*.2f,t)};_state.update{it.copy(modelReady=true)};val stems=separator.separate(a){v,t->p(.2f+v*.8f,t)};state.value.stems?.let{it.vocals.delete();it.instrumental.delete()};_state.update{it.copy(stems=stems)}}}
    fun removeModel(){if(state.value.busy)return;separator.removeModel();_state.update{it.copy(modelReady=false)}}
    fun cancel(){work?.cancel()}
    fun clear(){if(state.value.busy)return;stop();state.value.stems?.let{it.vocals.delete();it.instrumental.delete()};_state.update{it.copy(audio=null,master=null,analysis=null,masteredAnalysis=null,stems=null,trackName="",source="original",position=0f)}}
    fun chooseSource(source:String){if(state.value.busy)return;val playing=state.value.playing;val position=state.value.position;stop();_state.update{it.copy(source=source,position=position)};if(playing)play()}
    fun volume(v:Float){_state.update{it.copy(volume=v.coerceIn(0f,1f))};runCatching{currentTrack?.setVolume(v)}}
    fun seek(fraction:Float){val a=state.value.audio?:return;playFrame=(fraction.coerceIn(0f,1f)*a.frames).toInt();_state.update{it.copy(position=fraction.coerceIn(0f,1f))};if(state.value.playing){stop();play()}}
    private fun selectedAudio():Audio? = when(state.value.source){"master"->state.value.master;"vocals"->state.value.stems?.let{AudioIO.readWav(it.vocals)};"instrumental"->state.value.stems?.let{AudioIO.readWav(it.instrumental)};else->state.value.audio}
    fun togglePlay(){if(state.value.playing)stop()else play()}
    private fun play(){if(state.value.busy||state.value.audio==null)return;val version=++playVersion;_state.update{it.copy(playing=true)}
        playback=viewModelScope.launch(Dispatchers.IO){var track:AudioTrack?=null
            try{val a=selectedAudio()?:return@launch;var pos=(state.value.position*a.frames).toInt().coerceIn(0,a.frames);if(pos>=a.frames-10)pos=0
                val size=max(16384,AudioTrack.getMinBufferSize(a.rate,AudioFormat.CHANNEL_OUT_STEREO,AudioFormat.ENCODING_PCM_FLOAT));val t=AudioTrack.Builder().setAudioAttributes(AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_MEDIA).setContentType(AudioAttributes.CONTENT_TYPE_MUSIC).build()).setAudioFormat(AudioFormat.Builder().setSampleRate(a.rate).setChannelMask(AudioFormat.CHANNEL_OUT_STEREO).setEncoding(AudioFormat.ENCODING_PCM_FLOAT).build()).setBufferSizeInBytes(size).setTransferMode(AudioTrack.MODE_STREAM).build();track=t;currentTrack=t;t.setVolume(state.value.volume);t.play()
                while(pos<a.frames&&isActive&&version==playVersion){val frames=min(2048,a.frames-pos);val n=t.write(a.samples,pos*2,frames*2,AudioTrack.WRITE_BLOCKING);if(n<=0)break;pos+=n/2;playFrame=pos;_state.update{it.copy(position=(pos.toFloat()/a.frames).coerceIn(0f,1f))}}
                if(pos>=a.frames)_state.update{it.copy(position=0f)}
            }catch(_:CancellationException){}catch(e:Exception){if(version==playVersion)_state.update{it.copy(error="Ошибка воспроизведения: ${e.message}")}}
            finally{runCatching{track?.pause();track?.flush();track?.release()};if(version==playVersion){currentTrack=null;_state.update{it.copy(playing=false)}}}
        }
    }
    fun stop(){playVersion++;playback?.cancel();runCatching{currentTrack?.pause();currentTrack?.flush()};currentTrack=null;_state.update{it.copy(playing=false)}}
    fun prepareExport(source:String,format:String,onReady:(String,String)->Unit){val name=state.value.trackName.substringBeforeLast('.').replace(Regex("[^\\p{L}\\p{N} _-]"),"").take(70).ifBlank{"Track"};launchTask("Подготовка экспорта"){
        val a=when(source){"master"->state.value.master?:error("Сначала сделайте мастер");"vocals"->AudioIO.readWav(state.value.stems?.vocals?:error("Сначала разделите трек"));"instrumental"->AudioIO.readWav(state.value.stems?.instrumental?:error("Сначала разделите трек"));else->state.value.audio?:error("Сначала откройте трек")}
        val suffix=when(source){"master"->"master";"vocals"->"vocals";"instrumental"->"instrumental";else->"original"};val ext=if(format=="m4a")"m4a" else "wav";val file=File(getApplication<Application>().cacheDir,"$name-$suffix.$ext")
        val samples=a.samples.copyOf();AudioEngine.limiter(samples,10.0.pow(-1.0/20));val safe=Audio(samples)
        if(format=="m4a")AudioIO.writeAac(safe,file)else AudioIO.writeWav(safe,file,if(format=="wav16")16 else 24)
        _state.update{it.copy(savedMaster=false)};prepared=file;withContext(Dispatchers.Main){onReady(file.name,if(ext=="m4a")"audio/mp4"else"audio/wav")}
    }}
    fun saveExport(uri:Uri){val file=prepared?:return;launchTask("Сохраняем файл"){getApplication<Application>().contentResolver.openOutputStream(uri,"w").use { out->requireNotNull(out){"Не удалось сохранить файл"};file.inputStream().use{it.copyTo(out)}};val item=ExportEntry(file.name,"${if(file.extension=="m4a")"AAC 256 кбит/с" else "WAV"} · 44,1 кГц · ${(file.length()/1_000_000.0).let{"%.1f".format(it)}} МБ",System.currentTimeMillis());val history=(listOf(item)+state.value.history).take(30);val arr=JSONArray();history.forEach{arr.put(JSONObject().put("name",it.name).put("detail",it.detail).put("date",it.date))};prefs.edit().putString("history",arr.toString()).apply();_state.update{it.copy(history=history,savedMaster=true)};prepared=null}}
    fun savePreset(name:String){val s=state.value.settings;val p=Preset("custom-${System.currentTimeMillis()}",name.trim().take(32).ifBlank{"Мой мастер"},"Мои","Сохранённые настройки","CUSTOM",s);val all=(state.value.customs+p).takeLast(30);val arr=JSONArray();all.forEach{arr.put(JSONObject().put("id",it.id).put("name",it.name).put("settings",settingsToJson(it.settings)))};prefs.edit().putString("customs",arr.toString()).apply();_state.update{it.copy(customs=all,presetId=p.id)}}
    override fun onCleared(){stop();work?.cancel();super.onCleared()}
    private fun settingsToJson(s:Settings)=JSONObject().put("bass",s.bass).put("body",s.body).put("presence",s.presence).put("air",s.air).put("ratio",s.ratio).put("threshold",s.threshold).put("width",s.width).put("warmth",s.warmth).put("target",s.target).put("ceiling",s.ceiling).put("denoise",s.denoise).put("amount",s.amount)
    private fun settingsFromJson(o:JSONObject)=Settings(o.optDouble("bass",0.0),o.optDouble("body",0.0),o.optDouble("presence",0.0),o.optDouble("air",0.0),o.optDouble("ratio",1.5),o.optDouble("threshold",-18.0),o.optDouble("width",1.0),o.optDouble("warmth",0.0),o.optDouble("target",-14.0),o.optDouble("ceiling",-1.0),o.optDouble("denoise",0.0),o.optDouble("amount",.75))
}
