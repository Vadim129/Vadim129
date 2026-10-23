package app.mastr.studio

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.SystemBarStyle
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.viewModels
import androidx.compose.foundation.*
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.*
import androidx.compose.foundation.shape.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material.icons.outlined.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.*
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.*
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.*
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import kotlin.math.*
import java.text.SimpleDateFormat
import java.util.*

private val Bg = Color(0xFF080E1B)
private val Panel = Color(0xEB142034)
private val Muted = Color(0xFFA1B0C8)
private val Accent = Color(0xFF79E8D4)
private val Violet = Color(0xFFB9ABFF)
private val Line = Color(0xFF2B3B54)
private val StudioColors = darkColorScheme(primary = Accent, onPrimary = Bg, secondary = Violet,
    background = Bg, surface = Panel, onSurface = Color(0xFFF3F6FF), surfaceVariant = Color(0xFF1D2B43), onSurfaceVariant = Muted, outline = Line)

class MainActivity : ComponentActivity() {
    private val vm: StudioViewModel by viewModels()
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge(statusBarStyle = SystemBarStyle.dark(android.graphics.Color.TRANSPARENT), navigationBarStyle = SystemBarStyle.dark(android.graphics.Color.TRANSPARENT))
        if (savedInstanceState == null && intent.getBooleanExtra("demo", false)) vm.demo()
        setContent { MaterialTheme(colorScheme = StudioColors) { StudioApp(vm) } }
    }
    override fun onStart() { super.onStart(); vm.checkUpdates(false) }
    override fun onStop() { vm.stop(); super.onStop() }
}

/** Procedural aurora: sharp at every display size, no large bitmaps or network assets. */
@Composable private fun Aurora(modifier: Modifier = Modifier, content: @Composable BoxScope.() -> Unit) {
    Box(modifier.background(Bg)) {
        Canvas(Modifier.matchParentSize()) {
            drawRect(Brush.verticalGradient(listOf(Color(0xFF101D36), Bg, Color(0xFF111A2B))))
            val a = Offset(size.width * 1.05f, size.height * .12f)
            drawCircle(Brush.radialGradient(listOf(Color(0x554C53B7), Color.Transparent), a, size.width * .95f), size.width * .95f, a)
            val b = Offset(-size.width * .2f, size.height * .62f)
            drawCircle(Brush.radialGradient(listOf(Color(0x3332BCAC), Color.Transparent), b, size.width), size.width, b)
            for (i in 0..6) {
                val path = Path().apply {
                    moveTo(-size.width * .2f, size.height * .2f + i * 14f)
                    cubicTo(size.width * .3f, size.height * .45f + i * 14f,
                        size.width * .5f, -size.height * .04f + i * 14f, size.width * 1.2f, size.height * .16f + i * 14f)
                }
                drawPath(path, Color(0x1279E8D4), style = androidx.compose.ui.graphics.drawscope.Stroke(1.5f))
            }
        }
        content()
    }
}

@Composable fun StudioApp(vm: StudioViewModel) {
    val s by vm.state.collectAsStateWithLifecycle()
    val context = LocalContext.current
    var export by remember { mutableStateOf(false) }
    var format by remember { mutableStateOf("wav24") }
    var help by remember { mutableStateOf(false) }
    var licenses by remember { mutableStateOf(false) }
    var pendingDownload by remember { mutableStateOf(false) }
    val snackbar = remember { SnackbarHostState() }
    val importer = rememberLauncherForActivityResult(OpenAudioFile()) { uri -> uri?.let { vm.import(it) } }
    val permission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted) { if (pendingDownload) vm.downloadUpdate() else vm.export(format) }
    }
    fun saveOrDownload(update: Boolean) {
        pendingDownload = update
        if (Build.VERSION.SDK_INT <= 28 && context.checkSelfPermission(Manifest.permission.WRITE_EXTERNAL_STORAGE) != PackageManager.PERMISSION_GRANTED)
            permission.launch(Manifest.permission.WRITE_EXTERNAL_STORAGE)
        else if (update) vm.downloadUpdate() else vm.export(format)
    }
    val open: () -> Unit = { importer.launch(Unit) }
    LaunchedEffect(s.message) { s.message?.let { snackbar.showSnackbar(it); vm.messageHandled() } }
    Aurora(Modifier.fillMaxSize()) {
        Scaffold(containerColor = Color.Transparent, snackbarHost = { SnackbarHost(snackbar) }, topBar = {
            Row(Modifier.fillMaxWidth().statusBarsPadding().padding(horizontal = 22.dp, vertical = 12.dp), verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Outlined.GraphicEq, null, tint = Accent, modifier = Modifier.size(34.dp))
                Spacer(Modifier.width(10.dp))
                Column { Text("MASTR", fontSize = 24.sp, letterSpacing = 3.sp, fontWeight = FontWeight.Black); Text("SOUND, REFINED.", fontSize = 8.sp, color = Muted, letterSpacing = 2.sp) }
                Spacer(Modifier.weight(1f))
                Surface(color = Accent.copy(alpha = .09f), shape = CircleShape) { Text("OFFLINE", Modifier.padding(horizontal = 10.dp, vertical = 7.dp), color = Accent, fontSize = 9.sp, fontWeight = FontWeight.Bold) }
                IconButton(onClick = { help = true }) { Icon(Icons.Outlined.Info, "О приложении", tint = Muted) }
            }
        }, bottomBar = {
            Column {
                if (s.audio != null) Player(s, vm)
                NavigationBar(containerColor = Bg.copy(alpha = .85f), tonalElevation = 0.dp, windowInsets = WindowInsets(0, 0, 0, 0), modifier = Modifier.navigationBarsPadding().height(66.dp)) {
                    listOf("Мастеринг" to Icons.Outlined.Tune, "Библиотека" to Icons.Outlined.Folder).forEachIndexed { i, item ->
                        NavigationBarItem(selected = s.tab == i, onClick = { vm.tab(i) }, icon = { Icon(item.second, item.first) }, label = { Text(item.first, fontSize = 11.sp) }, modifier = Modifier.testTag(if (i == 0) "tab-master" else "tab-library"), colors = NavigationBarItemDefaults.colors(selectedIconColor = Accent, selectedTextColor = Accent, indicatorColor = Accent.copy(alpha = .12f), unselectedIconColor = Muted, unselectedTextColor = Muted))
                    }
                }
            }
        }) { padding ->
            if (s.tab == 0) MasterPage(s, vm, Modifier.padding(padding), open) { export = true }
            else LibraryPage(s, vm, Modifier.padding(padding), open)
        }
    }
    if (s.busy) androidx.compose.ui.window.Dialog(onDismissRequest = {}) {
        Surface(shape = RoundedCornerShape(28.dp), color = Panel) {
            Column(Modifier.padding(26.dp), verticalArrangement = Arrangement.spacedBy(18.dp)) {
                Text("Создаём твой звук", fontSize = 21.sp, fontWeight = FontWeight.Bold)
                Text(s.task, color = Muted, fontSize = 14.sp)
                LinearProgressIndicator(progress = { s.progress }, modifier = Modifier.fillMaxWidth().height(5.dp).clip(CircleShape))
                Text("На устройстве. Аудио никуда не отправляется.", color = Muted, fontSize = 12.sp)
                TextButton(onClick = { vm.cancel() }, modifier = Modifier.align(Alignment.End)) { Text("Отменить") }
            }
        }
    }
    s.error?.let { AlertDialog(onDismissRequest = { vm.errorHandled() }, title = { Text("Не получилось") }, text = { Text(it) }, confirmButton = { TextButton(onClick = { vm.errorHandled() }) { Text("Понятно") } }) }
    if (export) AlertDialog(onDismissRequest = { export = false }, title = { Text("Экспорт аудио") }, text = {
        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("Сразу в папку «Загрузки». Выбирать папку не нужно.", color = Muted, fontSize = 13.sp)
            listOf("wav24" to "WAV · 24 бит", "wav16" to "WAV · 16 бит", "m4a" to "M4A · AAC 256").forEach { (id, label) ->
                Row(Modifier.fillMaxWidth().clickable { format = id }, verticalAlignment = Alignment.CenterVertically) { RadioButton(selected = format == id, onClick = { format = id }); Text(label, fontSize = 14.sp) }
            }
            Text("WAV сохраняет измеренный мастер без повторной обработки. AAC — компактный формат с потерями.", color = Muted, fontSize = 11.sp)
        }
    }, confirmButton = { Button(onClick = { export = false; saveOrDownload(false) }, modifier = Modifier.testTag("save-downloads")) { Text("Сохранить в Загрузки") } }, dismissButton = { TextButton(onClick = { export = false }) { Text("Отмена") } })
    if (help) AlertDialog(onDismissRequest = { help = false }, title = { Text("MASTR Studio ${BuildConfig.VERSION_NAME}") }, text = {
        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text("Локальный мастеринг без нейросетей и загрузки музыки на сервер. Настройки подбираются при открытии трека. Пресет меняет характер, а не требует ручной настройки.", fontSize = 13.sp)
            Text("LUFS — общая громкость. Пик dBFS — максимальный отсчёт. Стерео CORR — сходство каналов, а не оценка качества.", color = Muted, fontSize = 12.sp)
            Text("Проверка GitHub — раз в неделю при открытии приложения. Установка APK только с вашего подтверждения.", color = Muted, fontSize = 12.sp)
            OutlinedButton(onClick = { vm.checkUpdates(true) }, enabled = !s.checkingUpdate, modifier = Modifier.fillMaxWidth().testTag("check-updates")) { Text(if (s.checkingUpdate) "Проверяем…" else "Проверить обновления") }
            TextButton(onClick = { help = false; licenses = true }) { Text("Лицензии компонентов") }
        }
    }, confirmButton = { TextButton(onClick = { help = false }) { Text("Закрыть") } })
    s.update?.let { release ->
        AlertDialog(onDismissRequest = { vm.dismissUpdate() }, title = { Text("Доступна версия ${release.version}") }, text = {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text("Официальный APK с GitHub → Загрузки. Текущая версия: ${BuildConfig.VERSION_NAME}.", fontSize = 13.sp)
                Text(release.notes.ifBlank { "Новая версия MASTR Studio" }, fontSize = 12.sp, color = Muted, maxLines = 12, overflow = TextOverflow.Ellipsis)
            }
        }, confirmButton = { Button(onClick = { saveOrDownload(true) }) { Text("Скачать APK") } }, dismissButton = { TextButton(onClick = { vm.dismissUpdate() }) { Text("Позже") } })
    }
    if (licenses) AlertDialog(onDismissRequest = { licenses = false }, title = { Text("Лицензии") }, text = { val text = remember { context.assets.open("THIRD_PARTY_NOTICES.txt").bufferedReader().use { it.readText() } }; Text(text, modifier = Modifier.heightIn(max = 360.dp).verticalScroll(rememberScrollState()), fontSize = 10.sp) }, confirmButton = { TextButton(onClick = { licenses = false }) { Text("Закрыть") } })
}

@Composable private fun Hero(open: () -> Unit, demo: () -> Unit) {
    Box(Modifier.fillMaxWidth().clip(RoundedCornerShape(30.dp)).background(Brush.linearGradient(listOf(Color(0xFF253858), Color(0xFF242749), Color(0xFF173D46))))) {
        Canvas(Modifier.matchParentSize()) {
            for (i in 0..36) {
                val x = size.width * .52f + i * size.width / 65
                val h = (sin(i * .5f) * .16f + .3f) * size.height
                drawLine(Accent.copy(alpha = .10f), Offset(x, size.height * .43f - h / 2), Offset(x, size.height * .43f + h / 2), 3f, StrokeCap.Round)
            }
        }
        Column(Modifier.padding(25.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
            Text("МЕНЬШЕ НАСТРОЕК. БОЛЬШЕ МУЗЫКИ.", color = Accent, fontSize = 9.sp, letterSpacing = 1.sp, fontWeight = FontWeight.Bold)
            Text("Твой звук.\nНовый уровень.", fontSize = 34.sp, lineHeight = 37.sp, fontWeight = FontWeight.Bold, letterSpacing = (-1).sp)
            Text("Открой трек. Выбери характер.\nСохрани готовый мастер.", fontSize = 14.sp, lineHeight = 21.sp, color = Color(0xFFC9D6E9))
            Button(onClick = open, shape = RoundedCornerShape(16.dp), modifier = Modifier.fillMaxWidth().height(52.dp).testTag("import")) { Icon(Icons.Outlined.FolderOpen, null); Spacer(Modifier.width(8.dp)); Text("Открыть аудиофайл", fontWeight = FontWeight.Bold) }
            TextButton(onClick = demo, modifier = Modifier.align(Alignment.CenterHorizontally).testTag("demo")) { Icon(Icons.Outlined.PlayCircle, null, tint = Violet); Spacer(Modifier.width(8.dp)); Text("Попробовать демотрек", color = Violet) }
        }
    }
}

@Composable private fun MasterPage(s: StudioState, vm: StudioViewModel, modifier: Modifier, open: () -> Unit, export: () -> Unit) {
    val list = rememberLazyListState()
    LaunchedEffect(s.master) { if (s.master != null) list.animateScrollToItem(2) }
    val filtered = Presets.all.filter { s.category == "Все" || it.category == s.category || (s.category == "Избранное" && it.id in s.favorites) }
    LazyColumn(modifier.fillMaxSize(), state = list, contentPadding = PaddingValues(start = 20.dp, end = 20.dp, bottom = 24.dp), verticalArrangement = Arrangement.spacedBy(18.dp)) {
        item {
            if (s.audio == null) Hero(open) { vm.demo() }
            else Surface(shape = RoundedCornerShape(26.dp), color = Panel) {
                Column(Modifier.padding(20.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Outlined.AudioFile, null, tint = Violet); Spacer(Modifier.width(12.dp))
                        Column(Modifier.weight(1f)) { Text(s.trackName, fontWeight = FontWeight.Bold, maxLines = 1, overflow = TextOverflow.Ellipsis); Text("ИСХОДНИК · 44,1 кГц · ${clock(s.audio.seconds)}", fontSize = 10.sp, color = Muted) }
                        IconButton(onClick = open, enabled = !s.busy) { Icon(Icons.Outlined.FolderOpen, "Открыть аудиофайл", tint = Muted) }
                    }
                    Waveform(s.audio, s.position, Modifier.fillMaxWidth().height(78.dp)) { vm.seek(it) }
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                        Metric("ГРОМКОСТЬ", s.analysis?.lufs, "LUFS"); Metric("ПИК", s.analysis?.peak, "dBFS"); Metric("СТЕРЕО", s.analysis?.correlation, "CORR", 2)
                    }
                }
            }
        }
        item {
            Surface(shape = RoundedCornerShape(26.dp), color = Panel) {
                Column(Modifier.padding(22.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
                    Text(if (s.audio == null) "ГОТОВО БЕЗ РУЧНЫХ НАСТРОЕК" else "НАСТРОЕНО ДЛЯ ЭТОГО ТРЕКА", color = Accent, fontSize = 9.sp, letterSpacing = 1.sp, fontWeight = FontWeight.Bold)
                    Text(Presets.all.first { it.id == s.presetId }.name, fontSize = 22.sp, fontWeight = FontWeight.Bold)
                    Text("Баланс частот, мягкая компрессия и контроль пиков. Цель по громкости — не ниже исходника.", color = Muted, fontSize = 13.sp, lineHeight = 20.sp)
                    if (s.audio != null) Button(onClick = { vm.render() }, enabled = !s.busy, shape = RoundedCornerShape(16.dp), modifier = Modifier.fillMaxWidth().height(52.dp).testTag("render")) { Icon(Icons.Outlined.GraphicEq, null); Spacer(Modifier.width(9.dp)); Text(if (s.master == null) "Сделать мастер" else "Пересчитать мастер", fontWeight = FontWeight.Bold) }
                }
            }
        }
        if (s.master != null) item {
            Box(Modifier.fillMaxWidth().clip(RoundedCornerShape(26.dp)).background(Brush.linearGradient(listOf(Color(0xFF183E46), Color(0xFF202F4A))))) {
                Column(Modifier.padding(22.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
                    Text("МАСТЕР ГОТОВ", color = Accent, fontSize = 11.sp, fontWeight = FontWeight.Bold, letterSpacing = 1.sp)
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) { Metric("ДО", s.analysis?.lufs, "LUFS"); Metric("ПОСЛЕ", s.masteredAnalysis?.lufs, "LUFS"); Metric("ПИК", s.masteredAnalysis?.peak, "dBFS") }
                    Text(s.loudnessWarning ?: "Громкость проверена после ограничения пиков. Сравни исходник и результат кнопками A / B в плеере.", color = if (s.loudnessWarning != null) Color(0xFFFFC18C) else Muted, fontSize = 12.sp, lineHeight = 18.sp)
                    Button(onClick = export, shape = RoundedCornerShape(16.dp), modifier = Modifier.fillMaxWidth().height(50.dp).testTag("export")) { Icon(Icons.Outlined.FileDownload, null); Spacer(Modifier.width(8.dp)); Text("Сохранить мастер", fontWeight = FontWeight.Bold) }
                }
            }
        }
        item { Column(verticalArrangement = Arrangement.spacedBy(6.dp)) { Text("Выбери характер", fontSize = 24.sp, fontWeight = FontWeight.Bold); Text("${Presets.all.size} пресета · настройки адаптируются автоматически", color = Muted, fontSize = 12.sp) } }
        item { LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) { items(listOf("Все", "Избранное", "Базовые", "Жанры", "Вокал", "Площадки", "Восстановление")) { c -> FilterChip(selected = s.category == c, onClick = { vm.category(c) }, label = { Text(c, fontSize = 11.sp) }, shape = CircleShape) } } }
        if (filtered.isEmpty()) item { Text("Добавь пресет в избранное значком сердца.", color = Muted, fontSize = 13.sp) }
        items(filtered.chunked(2)) { row ->
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                row.forEach { p ->
                    val selected = s.presetId == p.id
                    Surface(onClick = { vm.select(p) }, enabled = !s.busy, color = if (selected) Color(0xFF254451) else Panel, shape = RoundedCornerShape(22.dp), modifier = Modifier.weight(1f)) {
                        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Icon(if (selected) Icons.Default.CheckCircle else Icons.Outlined.GraphicEq, null, tint = if (selected) Accent else Violet, modifier = Modifier.size(22.dp)); Spacer(Modifier.weight(1f))
                                IconButton(onClick = { vm.favorite(p.id) }, modifier = Modifier.size(28.dp)) { Icon(if (p.id in s.favorites) Icons.Default.Favorite else Icons.Outlined.FavoriteBorder, "В избранное: ${p.name}", tint = Violet, modifier = Modifier.size(18.dp)) }
                            }
                            Text(p.name, fontSize = 14.sp, fontWeight = FontWeight.Bold, minLines = 2, maxLines = 2, overflow = TextOverflow.Ellipsis)
                            Text(p.description, fontSize = 11.sp, lineHeight = 16.sp, color = Muted, minLines = 3, maxLines = 3, overflow = TextOverflow.Ellipsis)
                        }
                    }
                }
                if (row.size == 1) Spacer(Modifier.weight(1f))
            }
        }
        item { Text("Всё на устройстве · без нейросетей · до 5 минут на трек", color = Muted, fontSize = 11.sp) }
    }
}

@Composable private fun Metric(label: String, value: Double?, unit: String, digits: Int = 1) {
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Text(label, color = Muted, fontSize = 8.sp, letterSpacing = 1.sp)
        Text(value?.let { "%.$digits".plus("f").format(it) } ?: "—", fontSize = 21.sp, fontWeight = FontWeight.Bold)
        Text(unit, color = Muted, fontSize = 9.sp)
    }
}
@Composable private fun Waveform(a: Audio, position: Float, modifier: Modifier, onSeek: (Float) -> Unit) {
    val peaks = remember(a) { FloatArray(140) { b ->
        val start = (b.toLong() * a.frames / 140).toInt(); val end = ((b + 1L) * a.frames / 140).toInt()
        var p = 0f; for (i in start until end step max(1, (end - start) / 80)) p = max(p, max(abs(a.samples[2 * i]), abs(a.samples[2 * i + 1]))); p
    } }
    Canvas(modifier.pointerInput(a) { detectTapGestures { onSeek((it.x / size.width).coerceIn(0f, 1f)) } }) {
        val step = size.width / peaks.size
        peaks.forEachIndexed { i, p -> val h = max(3f, p.coerceAtMost(1f) * size.height * .9f); drawRoundRect(if (i.toFloat() / peaks.size <= position) Accent else Violet.copy(alpha = .38f), Offset(i * step, (size.height - h) / 2), androidx.compose.ui.geometry.Size(max(1f, step * .55f), h), androidx.compose.ui.geometry.CornerRadius(step * .3f)) }
        drawLine(Accent, Offset(position * size.width, 0f), Offset(position * size.width, size.height), 2f)
    }
}
@Composable private fun Player(s: StudioState, vm: StudioViewModel) {
    var drag by remember { mutableStateOf<Float?>(null) }
    Surface(color = Color(0xF2152338), shadowElevation = 8.dp) {
        Column(Modifier.padding(horizontal = 20.dp, vertical = 8.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                FilledIconButton(onClick = { vm.togglePlay() }, enabled = !s.busy, modifier = Modifier.size(42.dp)) { Icon(if (s.playing) Icons.Default.Pause else Icons.Default.PlayArrow, if (s.playing) "Пауза" else "Воспроизвести") }
                Spacer(Modifier.width(10.dp))
                Column(Modifier.weight(1f)) { Text(s.trackName, fontSize = 12.sp, fontWeight = FontWeight.Bold, maxLines = 1, overflow = TextOverflow.Ellipsis); Text(if (s.source == "master") "МАСТЕР" else "ИСХОДНИК", color = Accent, fontSize = 9.sp) }
                if (s.master != null) {
                    TextButton(onClick = { vm.chooseSource("original") }, enabled = !s.busy, contentPadding = PaddingValues(8.dp), modifier = Modifier.width(38.dp).testTag("play-original")) { Text("A", color = if (s.source == "original") Accent else Muted, fontWeight = FontWeight.Bold) }
                    TextButton(onClick = { vm.chooseSource("master") }, enabled = !s.busy, contentPadding = PaddingValues(8.dp), modifier = Modifier.width(38.dp).testTag("play-master")) { Text("B", color = if (s.source == "master") Accent else Muted, fontWeight = FontWeight.Bold) }
                }
            }
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(clock((s.audio?.seconds ?: 0.0) * s.position), color = Muted, fontSize = 9.sp)
                Slider(value = drag ?: s.position, onValueChange = { drag = it }, onValueChangeFinished = { drag?.let { vm.seek(it) }; drag = null }, enabled = !s.busy, modifier = Modifier.weight(1f).height(26.dp))
                Text(clock(s.audio?.seconds ?: 0.0), color = Muted, fontSize = 9.sp)
            }
        }
    }
}
@Composable private fun LibraryPage(s: StudioState, vm: StudioViewModel, modifier: Modifier, open: () -> Unit) {
    LazyColumn(modifier.fillMaxSize(), contentPadding = PaddingValues(22.dp), verticalArrangement = Arrangement.spacedBy(18.dp)) {
        item { Text("Твоя библиотека", fontSize = 29.sp, fontWeight = FontWeight.Bold) }
        item { Text("Готовые файлы — в папке «Загрузки». Старые экспорты остаются там, куда были сохранены раньше.", color = Muted, fontSize = 13.sp, lineHeight = 20.sp) }
        item { Button(onClick = { vm.tab(0); open() }, shape = RoundedCornerShape(16.dp)) { Text("Открыть аудиофайл") } }
        item { OutlinedButton(onClick = { vm.checkUpdates(true) }, enabled = !s.checkingUpdate, modifier = Modifier.fillMaxWidth()) { Icon(Icons.Outlined.SystemUpdate, null); Spacer(Modifier.width(8.dp)); Text(if (s.checkingUpdate) "Проверяем…" else "Проверить обновления") } }
        item { Text("ИСТОРИЯ ЭКСПОРТА", color = Accent, fontSize = 11.sp, letterSpacing = 1.sp) }
        if (s.history.isEmpty()) item { Text("Сделай первый мастер — он появится здесь.", color = Muted, fontSize = 14.sp) }
        items(s.history) { entry -> Surface(color = Panel, shape = RoundedCornerShape(22.dp)) {
            Column(Modifier.fillMaxWidth().padding(18.dp), verticalArrangement = Arrangement.spacedBy(7.dp)) {
                Text(entry.name, fontSize = 14.sp, fontWeight = FontWeight.Bold)
                Text(entry.detail, fontSize = 11.sp, color = Muted)
                Text(SimpleDateFormat("dd MMM, HH:mm", Locale("ru")).format(Date(entry.date)), color = Muted, fontSize = 10.sp)
            }
        } }
        item { Text("MASTR Studio ${BuildConfig.VERSION_NAME} · обновления с GitHub", fontSize = 11.sp, color = Muted) }
    }
}
private fun clock(seconds: Double): String { val s = seconds.toInt().coerceAtLeast(0); return "%d:%02d".format(s / 60, s % 60) }
