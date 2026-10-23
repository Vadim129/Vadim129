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

data class ExportEntry(val name: String, val detail: String, val date: Long)
data class StudioState(
    val tab: Int = 0, val trackName: String = "", val audio: Audio? = null, val master: Audio? = null,
    val analysis: Analysis? = null, val masteredAnalysis: Analysis? = null,
    val presetId: String = "balanced", val settings: Settings = Presets.all.first().settings,
    val category: String = "Все", val favorites: Set<String> = emptySet(),
    val busy: Boolean = false, val progress: Float = 0f, val task: String = "", val error: String? = null,
    val source: String = "original", val playing: Boolean = false, val position: Float = 0f, val volume: Float = 1f,
    val history: List<ExportEntry> = emptyList(), val message: String? = null,
    val checkingUpdate: Boolean = false, val update: AppRelease? = null,
    val loudnessWarning: String? = null
)
class StudioViewModel(app: Application) : AndroidViewModel(app) {
    private val prefs = app.getSharedPreferences("studio", 0)
    private val _state = MutableStateFlow(StudioState())
    val state: StateFlow<StudioState> = _state.asStateFlow()
    private var work: Job? = null
    private var playback: Job? = null
    private var currentTrack: AudioTrack? = null
    @Volatile private var playFrame = 0
    @Volatile private var playVersion = 0
    init {
        val favorite = prefs.getStringSet("favorites", emptySet())?.toSet() ?: emptySet()
        val histories = runCatching {
            val a = JSONArray(prefs.getString("history", "[]"))
            (0 until a.length()).map { val o = a.getJSONObject(it); ExportEntry(o.getString("name"), o.getString("detail"), o.getLong("date")) }
        }.getOrDefault(emptyList())
        _state.update { it.copy(favorites = favorite, history = histories) }
        // Migration: delete the old downloaded neural network, even on an in-place update.
        app.filesDir.listFiles()?.filter { it.extension == "onnx" || it.name.endsWith(".onnx.part") || it.name == "model_info.json" }?.forEach { it.delete() }
        app.cacheDir.listFiles()?.filter {
            it.name.startsWith("vocals") || it.name.startsWith("instrumental") ||
            it.name.startsWith("uvr") || System.currentTimeMillis() - it.lastModified() > 86_400_000
        }?.forEach { it.deleteRecursively() }
    }
    fun tab(index: Int) { _state.update { it.copy(tab = index) } }
    fun category(c: String) { _state.update { it.copy(category = c) } }
    fun errorHandled() { _state.update { it.copy(error = null) } }
    fun messageHandled() { _state.update { it.copy(message = null) } }
    fun favorite(id: String) {
        val ids = state.value.favorites.toMutableSet(); if (!ids.add(id)) ids.remove(id)
        prefs.edit().putStringSet("favorites", ids).apply(); _state.update { it.copy(favorites = ids) }
    }
    fun select(p: Preset) {
        if (state.value.busy) return
        stop()
        val settings = state.value.analysis?.let { AudioEngine.automaticSettings(it, p.settings) } ?: p.settings.copy(amount = 1.0)
        _state.update { it.copy(presetId = p.id, settings = settings, master = null, masteredAnalysis = null, source = "original", loudnessWarning = null) }
    }
    private fun launchTask(title: String, block: suspend CoroutineScope.() -> Unit) {
        if (state.value.busy) return
        stop(); _state.update { it.copy(busy = true, progress = 0f, task = title, error = null) }
        work = viewModelScope.launch(Dispatchers.Default) {
            try { block() }
            catch (_: CancellationException) { }
            catch (_: OutOfMemoryError) { _state.update { it.copy(error = "Недостаточно памяти. Закройте другие приложения или выберите более короткий трек.") } }
            catch (e: Exception) { _state.update { it.copy(error = e.message ?: "Не удалось выполнить операцию") } }
            finally { _state.update { it.copy(busy = false, task = "", progress = 0f) } }
        }
    }
    private fun progress(job: Job): (Float, String) -> Unit = { p, t -> job.ensureActive(); _state.update { it.copy(progress = p.coerceIn(0f, 1f), task = t) } }
    private fun acceptAudio(a: Audio, name: String) {
        val stats = AudioEngine.analyze(a)
        _state.update { it.copy(trackName = name, audio = a, master = null, analysis = stats,
            settings = AudioEngine.automaticSettings(stats), presetId = "balanced", masteredAnalysis = null,
            source = "original", position = 0f, loudnessWarning = null) }
    }
    fun import(uri: Uri) { launchTask("Открываем трек") {
        val callback = progress(currentCoroutineContext().job)
        val name = AudioIO.name(getApplication(), uri)
        val a = AudioIO.decode(getApplication(), uri, callback)
        callback(.94f, "Подбор настроек по вашему треку"); acceptAudio(a, name)
    } }
    fun demo() { launchTask("Создаём демотрек") { acceptAudio(AudioEngine.demo(), "Демо • 12 сек") } }
    fun render() {
        val a = state.value.audio ?: return
        val s = state.value.settings
        launchTask("Мастеринг") {
            val result = AudioEngine.master(a, s, progress(currentCoroutineContext().job))
            val stats = AudioEngine.analyze(result)
            val warning = if (stats.lufs < (state.value.analysis?.lufs ?: -70.0) - .2)
                "Достичь исходной громкости без перегруза не удалось. Защита пиков сохранена; проверьте результат перед экспортом." else null
            _state.update { it.copy(master = result, masteredAnalysis = stats, source = "master", position = 0f, loudnessWarning = warning) }
        }
    }
    fun cancel() { work?.cancel() }
    fun chooseSource(source: String) {
        if (state.value.busy || (source == "master" && state.value.master == null)) return
        val playing = state.value.playing; val position = state.value.position
        stop(); _state.update { it.copy(source = source, position = position) }; if (playing) play()
    }
    fun export(format: String) {
        val a = state.value.master ?: return
        launchTask("Сохраняем в Загрузки") {
            val base = state.value.trackName.substringBeforeLast('.').replace(Regex("[^\\p{L}\\p{N} _-]"), "").take(65).ifBlank { "Track" }
            val ext = if (format == "m4a") "m4a" else "wav"
            val file = File(getApplication<Application>().cacheDir, "$base-master-${System.currentTimeMillis()}.$ext")
            try {
                // PCM is the measured master. Do NOT run another limiter at export.
                if (format == "m4a") AudioIO.writeAac(a, file) else AudioIO.writeWav(a, file, if (format == "wav16") 16 else 24)
                currentCoroutineContext().ensureActive()
                withContext(Dispatchers.IO) { DownloadsStore.save(getApplication(), file, if (format == "m4a") "audio/mp4" else "audio/x-wav") }
                val entry = ExportEntry(file.name, "Загрузки · ${if (ext == "m4a") "AAC 256 кбит/с" else "WAV"} · 44,1 кГц", System.currentTimeMillis())
                val history = (listOf(entry) + state.value.history).take(30)
                prefs.edit().putString("history", JSONArray().apply { history.forEach { put(JSONObject().put("name", it.name).put("detail", it.detail).put("date", it.date)) } }.toString()).apply()
                _state.update { it.copy(history = history, message = "Сохранено в Загрузки: ${file.name}") }
            } finally { file.delete() }
        }
    }
    fun checkUpdates(manual: Boolean) {
        if (state.value.checkingUpdate) return
        val now = System.currentTimeMillis()
        if (!manual && !AppUpdates.due(prefs.getLong("update_check_at", 0), now)) return
        prefs.edit().putLong("update_check_at", now).apply()
        _state.update { it.copy(checkingUpdate = true) }
        viewModelScope.launch {
            try {
                val release = withContext(Dispatchers.IO) { AppUpdates.check(BuildConfig.VERSION_NAME) }
                _state.update { it.copy(update = release, message = if (manual && release == null) "У вас последняя версия MASTR Studio: ${BuildConfig.VERSION_NAME}" else it.message) }
            } catch (e: Exception) {
                if (manual) _state.update { it.copy(error = "Не удалось проверить обновления. Проверьте интернет и попробуйте ещё раз. ${e.message ?: ""}") }
            } finally { _state.update { it.copy(checkingUpdate = false) } }
        }
    }
    fun dismissUpdate() { _state.update { it.copy(update = null) } }
    fun downloadUpdate() {
        val release = state.value.update ?: return
        try {
            AppUpdates.download(getApplication(), release)
            _state.update { it.copy(update = null, message = "Обновление скачивается в Загрузки. По завершении откройте APK из уведомления и подтвердите установку.") }
        } catch (_: Exception) { _state.update { it.copy(error = "Не удалось начать скачивание. Проверьте доступ к Загрузкам и системный Диспетчер загрузки.") } }
    }
    fun volume(v:Float){_state.update{it.copy(volume=v.coerceIn(0f,1f))};runCatching{currentTrack?.setVolume(v)}}
    fun seek(fraction:Float){val a=state.value.audio?:return;playFrame=(fraction.coerceIn(0f,1f)*a.frames).toInt();_state.update{it.copy(position=fraction.coerceIn(0f,1f))};if(state.value.playing){stop();play()}}
    private fun selectedAudio():Audio? = if (state.value.source == "master") state.value.master else state.value.audio
    fun togglePlay(){if(state.value.playing)stop()else play()}
    private fun play(){if(state.value.busy||state.value.audio==null)return;val version=++playVersion;_state.update{it.copy(playing=true)}
        playback=viewModelScope.launch(Dispatchers.IO){var track:AudioTrack?=null
            try{val a=selectedAudio()?:return@launch;var pos=(state.value.position*a.frames).toInt().coerceIn(0,a.frames);if(pos>=a.frames-10)pos=0
                val initialFrame=pos
                val size=max(16384,AudioTrack.getMinBufferSize(a.rate,AudioFormat.CHANNEL_OUT_STEREO,AudioFormat.ENCODING_PCM_FLOAT));val t=AudioTrack.Builder().setAudioAttributes(AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_MEDIA).setContentType(AudioAttributes.CONTENT_TYPE_MUSIC).build()).setAudioFormat(AudioFormat.Builder().setSampleRate(a.rate).setChannelMask(AudioFormat.CHANNEL_OUT_STEREO).setEncoding(AudioFormat.ENCODING_PCM_FLOAT).build()).setBufferSizeInBytes(size).setTransferMode(AudioTrack.MODE_STREAM).build();track=t;currentTrack=t;t.setVolume(state.value.volume);t.play()
                while(pos<a.frames&&isActive&&version==playVersion){val frames=min(2048,a.frames-pos);val n=t.write(a.samples,pos*2,frames*2,AudioTrack.WRITE_BLOCKING);if(n<=0)break;pos+=n/2;playFrame=pos;_state.update{it.copy(position=(pos.toFloat()/a.frames).coerceIn(0f,1f))}}
                if(pos>=a.frames){while(isActive&&version==playVersion&&t.playbackHeadPosition<pos-initialFrame)delay(10);if(isActive&&version==playVersion)_state.update{it.copy(position=0f)}}
            }catch(_:CancellationException){}catch(e:Exception){if(version==playVersion)_state.update{it.copy(error="Ошибка воспроизведения: ${e.message}")}}
            finally{runCatching{track?.pause();track?.flush();track?.release()};if(version==playVersion){currentTrack=null;_state.update{it.copy(playing=false)}}}
        }
    }
    fun stop(){playVersion++;playback?.cancel();runCatching{currentTrack?.pause();currentTrack?.flush()};currentTrack=null;_state.update{it.copy(playing=false)}}
    override fun onCleared() { stop(); super.onCleared() }
}
