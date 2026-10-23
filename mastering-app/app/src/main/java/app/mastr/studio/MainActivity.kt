package app.mastr.studio

import android.content.Intent
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
import androidx.compose.material.icons.automirrored.filled.*
import androidx.compose.material.icons.filled.*
import androidx.compose.material.icons.outlined.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.*
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.*
import androidx.compose.ui.graphics.vector.ImageVector
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

private val Bg=Color(0xFF101115)
private val Panel=Color(0xFF1A1C23)
private val Panel2=Color(0xFF22252E)
private val Muted=Color(0xFF9195A5)
private val Lime=Color(0xFFC4F36A)
private val Violet=Color(0xFFB3A0FF)
private val Line=Color(0xFF30333D)
private val StudioColors=darkColorScheme(primary=Lime,onPrimary=Color(0xFF182000),secondary=Violet,background=Bg,surface=Panel,onSurface=Color(0xFFF3F4F8),surfaceVariant=Panel2,onSurfaceVariant=Muted,outline=Line)

class MainActivity:ComponentActivity() {
    private val vm:StudioViewModel by viewModels()
    override fun onCreate(savedInstanceState:Bundle?){super.onCreate(savedInstanceState);enableEdgeToEdge(statusBarStyle=SystemBarStyle.dark(android.graphics.Color.TRANSPARENT),navigationBarStyle=SystemBarStyle.dark(android.graphics.Color.TRANSPARENT));if(savedInstanceState==null&&intent.getBooleanExtra("demo",false))vm.demo();setContent {MaterialTheme(colorScheme=StudioColors){StudioApp(vm)}}}
    override fun onStop(){vm.stop();super.onStop()}
}
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun StudioApp(vm:StudioViewModel){
    val s by vm.state.collectAsStateWithLifecycle();val context=LocalContext.current
    var export by remember{mutableStateOf(false)};var exportSource by remember{mutableStateOf("master")};var format by remember{mutableStateOf("wav24")}
    var licenses by remember{mutableStateOf(false)}
    var savePreset by remember{mutableStateOf(false)};var presetName by remember{mutableStateOf("")};var help by remember{mutableStateOf(false)};var consent by remember{mutableStateOf(false)}
    val snackbar=remember{SnackbarHostState()}
    val importer=rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()){uri->uri?.let{vm.import(it)}}
    val exporter=rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("audio/*")){uri->uri?.let{vm.saveExport(it)}}
    val open={importer.launch(arrayOf("audio/*","application/ogg"))}
    val showExport:(String)->Unit={source->exportSource=source;export=true}
    LaunchedEffect(s.savedMaster){if(s.savedMaster)snackbar.showSnackbar("Аудиофайл сохранён")}
    Scaffold(containerColor=Bg,snackbarHost={SnackbarHost(snackbar)},topBar={
        Row(Modifier.fillMaxWidth().statusBarsPadding().padding(horizontal=22.dp,vertical=14.dp),verticalAlignment=Alignment.CenterVertically){
            Logo(Modifier.size(30.dp));Spacer(Modifier.width(10.dp));Column{Text("MASTR",fontSize=23.sp,fontWeight=FontWeight.Black,letterSpacing=3.sp);Text("P O C K E T   S T U D I O",fontSize=8.sp,color=Muted)}
            Spacer(Modifier.weight(1f));Surface(color=Lime.copy(alpha=.08f),shape=CircleShape,border=BorderStroke(1.dp,Lime.copy(alpha=.15f))){Row(Modifier.padding(horizontal=9.dp,vertical=5.dp),verticalAlignment=Alignment.CenterVertically){Box(Modifier.size(5.dp).background(Lime,CircleShape));Spacer(Modifier.width(5.dp));Text("LOCAL",fontSize=9.sp,color=Lime,fontWeight=FontWeight.Bold)}}
            IconButton(onClick={help=true},modifier=Modifier.size(38.dp)){Icon(Icons.Outlined.Info,"О приложении",tint=Muted,modifier=Modifier.size(21.dp))}
        }
    },bottomBar={Column{if(s.audio!=null)Player(s,vm);NavigationBar(windowInsets=WindowInsets(0,0,0,0),containerColor=Bg,tonalElevation=0.dp,modifier=Modifier.navigationBarsPadding().height(68.dp)){
        listOf(Triple("Мастеринг",Icons.Outlined.Tune,"tab-master"),Triple("Дорожки",Icons.Outlined.Layers,"tab-stems"),Triple("Библиотека",Icons.Outlined.Folder,"tab-library")).forEachIndexed{i,item->NavigationBarItem(selected=s.tab==i,onClick={vm.tab(i)},icon={Icon(item.second,item.first,Modifier.size(22.dp))},label={Text(item.first,fontSize=10.sp,fontWeight=FontWeight.Medium)},modifier=Modifier.testTag(item.third),colors=NavigationBarItemDefaults.colors(selectedIconColor=Lime,selectedTextColor=Lime,indicatorColor=Lime.copy(alpha=.08f),unselectedIconColor=Muted,unselectedTextColor=Muted))}
    }}}){padding->
        when(s.tab){
            0->MasterPage(s,vm,Modifier.padding(padding),open,{showExport("master")},{savePreset=true})
            1->StemsPage(s,vm,Modifier.padding(padding),open,{if(s.modelReady)vm.split()else consent=true},showExport)
            else->LibraryPage(s,vm,Modifier.padding(padding),open)
        }
    }
    if(s.busy)androidx.compose.ui.window.Dialog(onDismissRequest={}){Surface(shape=RoundedCornerShape(24.dp),color=Panel){Column(Modifier.padding(28.dp),verticalArrangement=Arrangement.spacedBy(18.dp)){Row(verticalAlignment=Alignment.CenterVertically){Icon(Icons.Outlined.GraphicEq,null,tint=Lime);Spacer(Modifier.width(10.dp));Text("Студия работает",fontWeight=FontWeight.Bold,fontSize=18.sp)};Text(s.task,color=Muted,fontSize=14.sp);LinearProgressIndicator(progress={s.progress},modifier=Modifier.fillMaxWidth().height(6.dp).clip(CircleShape),color=Lime,trackColor=Line);Text("${(s.progress*100).toInt()}%",color=Lime,fontSize=12.sp);Text("Обработка идёт на устройстве. Не закрывайте приложение до завершения.",color=Muted,fontSize=12.sp);TextButton(onClick={vm.cancel()},modifier=Modifier.align(Alignment.End)){Text("Отменить")}}}}
    s.error?.let{message->AlertDialog(onDismissRequest={vm.errorHandled()},title={Text("Не получилось")},text={Text(message)},confirmButton={TextButton(onClick={vm.errorHandled()}){Text("Понятно")}})}
    if(consent)AlertDialog(onDismissRequest={consent=false},icon={Icon(Icons.Outlined.CloudDownload,null,tint=Violet)},title={Text("Скачать AI-модель?")},text={Text("Нужно около 67 МБ. Модель загружается с GitHub один раз; затем разделение работает без интернета. Ваш трек никуда не отправляется. На телефоне обработка может занять несколько минут.")},confirmButton={TextButton(onClick={consent=false;vm.split()}){Text("Скачать и разделить")}},dismissButton={TextButton(onClick={consent=false}){Text("Не сейчас")}})
    if(savePreset)AlertDialog(onDismissRequest={savePreset=false},title={Text("Мой пресет")},text={OutlinedTextField(value=presetName,onValueChange={presetName=it.take(32)},label={Text("Название")},singleLine=true)},confirmButton={TextButton(onClick={vm.savePreset(presetName);presetName="";savePreset=false}){Text("Сохранить")}},dismissButton={TextButton(onClick={savePreset=false}){Text("Отмена")}})
    if(export)AlertDialog(onDismissRequest={export=false},title={Text("Экспорт аудио")},text={Column(verticalArrangement=Arrangement.spacedBy(7.dp)){
        Text(when(exportSource){"vocals"->"Отдельная дорожка: вокал";"instrumental"->"Отдельная дорожка: инструментал";"master"->"Обработанный мастер";else->"Исходная запись"},color=Muted,fontSize=13.sp)
        listOf(Triple("wav24","WAV · 24 бит","Без потерь · для дальнейшей работы"),Triple("wav16","WAV · 16 бит","Без потерь · универсальный формат"),Triple("m4a","M4A · AAC 256","Компактно · для отправки и публикации")).forEach{(id,label,detail)->Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(12.dp)).clickable{format=id}.padding(vertical=4.dp),verticalAlignment=Alignment.CenterVertically){RadioButton(selected=format==id,onClick={format=id});Column{Text(label,fontSize=14.sp,fontWeight=FontWeight.SemiBold);Text(detail,color=Muted,fontSize=10.sp)}}}
        Text("Стерео · 44,1 кГц. Формат MP3 не экспортируется; MP3 можно импортировать.",fontSize=11.sp,color=Muted)
    }},confirmButton={Button(onClick={export=false;vm.prepareExport(exportSource,format){name,_->exporter.launch(name)}}){Text("Выбрать папку")}},dismissButton={TextButton(onClick={export=false}){Text("Отмена")}})
    if(licenses)AlertDialog(onDismissRequest={licenses=false},title={Text("Лицензии компонентов")},text={val notices=remember{context.assets.open("THIRD_PARTY_NOTICES.txt").bufferedReader().use{it.readText()}};Text(notices,fontSize=10.sp,lineHeight=14.sp,modifier=Modifier.heightIn(max=400.dp).verticalScroll(rememberScrollState()))},confirmButton={TextButton(onClick={licenses=false}){Text("Закрыть")}})
    if(help)AlertDialog(onDismissRequest={help=false},title={Text("MASTR Studio 1.0")},text={Column(verticalArrangement=Arrangement.spacedBy(11.dp)){Text("Личная студия мастеринга. Без аккаунта, подписки и отправки аудио на сервер.");Text("32 пресета, ручная настройка, громкость LUFS с гейтированием, защита пиков, шумоподавление и разделение на вокал / инструментал. В этой версии — до 5 минут на трек.",fontSize=13.sp);Text("Мастеринг работает офлайн. Для AI-разделения сначала нужна модель ~67 МБ. Скорость и качество зависят от телефона и исходной записи; утечки между дорожками возможны. Это не полный аналог BandLab и не DAW.",fontSize=12.sp,color=Muted);TextButton(onClick={context.startActivity(Intent(Intent.ACTION_VIEW,android.net.Uri.parse("https://github.com/TRvlvr/model_repo")))}){Text("Авторы и источник AI-модели")};TextButton(onClick={help=false;licenses=true}){Text("Лицензии компонентов")}}},confirmButton={TextButton(onClick={help=false}){Text("Закрыть")}})
}
@Composable private fun Logo(modifier:Modifier){Canvas(modifier){val heights=listOf(.42f,.9f,.65f,.32f);val w=size.width/7;heights.forEachIndexed{i,h->drawRoundRect(Lime,Offset(i*w*1.8f,(size.height-size.height*h)/2),androidx.compose.ui.geometry.Size(w,size.height*h),androidx.compose.ui.geometry.CornerRadius(w/2))}}}
@Composable private fun Eyebrow(text:String,color:Color=Muted){Text(text,fontSize=10.sp,fontWeight=FontWeight.Bold,letterSpacing=1.7.sp,color=color)}
@Composable private fun SectionTitle(title:String,subtitle:String?=null,action:@Composable (()->Unit)?=null){Row(Modifier.fillMaxWidth(),verticalAlignment=Alignment.CenterVertically){Column(Modifier.weight(1f)){Text(title,fontSize=21.sp,fontWeight=FontWeight.Bold,letterSpacing=(-.5).sp);if(subtitle!=null)Text(subtitle,color=Muted,fontSize=12.sp,modifier=Modifier.padding(top=4.dp))};action?.invoke()}}
@Composable private fun Hint(icon:ImageVector,text:String){Row(horizontalArrangement=Arrangement.spacedBy(7.dp),verticalAlignment=Alignment.CenterVertically){Icon(icon,null,Modifier.size(14.dp),tint=Muted);Text(text,color=Muted,fontSize=11.sp)}}
@Composable private fun OpenHero(open:()->Unit,demo:()->Unit){
    Box(Modifier.fillMaxWidth().clip(RoundedCornerShape(24.dp)).background(Brush.linearGradient(listOf(Color(0xFF28243E),Color(0xFF1D2030)))).border(1.dp,Color(0xFF3C354F),RoundedCornerShape(24.dp))){
        Canvas(Modifier.matchParentSize()){for(j in 0..40){val x=size.width*.5f+j*size.width/55;val h=(sin(j*.75)*.28+.38).toFloat()*size.height;drawLine(Violet.copy(alpha=.08f),Offset(x,size.height*.5f-h/2),Offset(x,size.height*.5f+h/2),4f)}}
        Column(Modifier.padding(24.dp)){Eyebrow("ТВОЯ КАРМАННАЯ СТУДИЯ",Violet);Spacer(Modifier.height(12.dp));Text("Твой звук.\nВ лучшей форме.",fontSize=30.sp,lineHeight=34.sp,fontWeight=FontWeight.Bold,letterSpacing=(-1).sp);Spacer(Modifier.height(10.dp));Text("Мастеринг, который всегда под рукой.",color=Color(0xFFB3ADC7),fontSize=13.sp);Spacer(Modifier.height(23.dp));Button(onClick=open,shape=RoundedCornerShape(12.dp),modifier=Modifier.fillMaxWidth().height(48.dp)){Icon(Icons.Outlined.FileUpload,null,Modifier.size(19.dp));Spacer(Modifier.width(9.dp));Text("Загрузить аудио",fontWeight=FontWeight.Bold)};TextButton(onClick=demo,modifier=Modifier.align(Alignment.CenterHorizontally).testTag("demo")){Icon(Icons.Outlined.PlayCircle,null,Modifier.size(16.dp),tint=Violet);Spacer(Modifier.width(6.dp));Text("Попробовать демотрек",color=Violet,fontSize=12.sp)}}
    }
}
@Composable private fun TrackCard(s:StudioState,vm:StudioViewModel,open:()->Unit){
    Surface(color=Panel,shape=RoundedCornerShape(20.dp),border=BorderStroke(1.dp,Line)){
        Column(Modifier.padding(18.dp),verticalArrangement=Arrangement.spacedBy(12.dp)){
            Row(verticalAlignment=Alignment.CenterVertically){Box(Modifier.size(36.dp).background(Violet.copy(alpha=.12f),RoundedCornerShape(10.dp)),contentAlignment=Alignment.Center){Icon(Icons.Outlined.AudioFile,null,tint=Violet,modifier=Modifier.size(20.dp))};Spacer(Modifier.width(10.dp));Column(Modifier.weight(1f)){Text(s.trackName,fontWeight=FontWeight.SemiBold,fontSize=14.sp,maxLines=1,overflow=TextOverflow.Ellipsis);Text("44,1 кГц · стерео · ${clock(s.audio?.seconds?:0.0)}",fontSize=11.sp,color=Muted)};IconButton(onClick=open,modifier=Modifier.size(30.dp)){Icon(Icons.Outlined.FolderOpen,"Заменить аудио",tint=Muted,modifier=Modifier.size(20.dp))}}
            Waveform(s.audio!!,s.position,Lime,Modifier.fillMaxWidth().height(74.dp)){vm.seek(it)}
            Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween){Metric("ГРОМКОСТЬ",s.analysis?.lufs?.let{"%.1f".format(it)}?:"—","LUFS");Metric("ПИК",s.analysis?.peak?.let{"%.1f".format(it)}?:"—","dBFS");Metric("СТЕРЕО",s.analysis?.correlation?.let{"%.2f".format(it)}?:"—","CORR")}
        }
    }
}
@Composable private fun Metric(label:String,value:String,unit:String,color:Color=Color.White){Column{Text(label,fontSize=8.sp,letterSpacing=1.sp,color=Muted);Row(verticalAlignment=Alignment.Bottom,modifier=Modifier.padding(top=4.dp)){Text(value,fontSize=21.sp,fontWeight=FontWeight.SemiBold,color=color);Spacer(Modifier.width(4.dp));Text(unit,fontSize=8.sp,color=Muted,modifier=Modifier.padding(bottom=3.dp))}}}
@Composable private fun Waveform(a:Audio,position:Float,color:Color,modifier:Modifier,onSeek:(Float)->Unit){val peaks=remember(a){FloatArray(160){b->val start=b.toLong()*a.frames/160;val end=((b+1).toLong()*a.frames/160).toInt();var p=0f;for(i in start.toInt() until end step max(1,(end-start.toInt())/96))p=max(p,max(abs(a.samples[i*2]),abs(a.samples[i*2+1])));p}};Canvas(modifier.pointerInput(a){detectTapGestures{onSeek((it.x/size.width).coerceIn(0f,1f))}}){val step=size.width/peaks.size;peaks.forEachIndexed{i,p->val h=max(3f,p.coerceAtMost(1f)*size.height*.9f);drawRoundRect(if(i.toFloat()/peaks.size<=position)color else color.copy(alpha=.28f),Offset(i*step,(size.height-h)/2),androidx.compose.ui.geometry.Size(max(1f,step*.55f),h),androidx.compose.ui.geometry.CornerRadius(step*.3f))};drawLine(color,Offset(position*size.width,0f),Offset(position*size.width,size.height),1.5f)}}

@Composable private fun MasterPage(s:StudioState,vm:StudioViewModel,modifier:Modifier,open:()->Unit,export:()->Unit,savePreset:()->Unit){
    val listState=rememberLazyListState()
    LaunchedEffect(s.master){if(s.master!=null)listState.animateScrollToItem(2)}
    val all=Presets.all+s.customs
    val filtered=all.filter{(s.category=="Все"||(s.category=="Избранное"&&it.id in s.favorites)||it.category==s.category)&&(s.query.isBlank()||"${it.name} ${it.description} ${it.tag}".contains(s.query,ignoreCase=true))}
    LazyColumn(modifier.fillMaxSize(),state=listState,contentPadding=PaddingValues(start=22.dp,end=22.dp,bottom=28.dp),verticalArrangement=Arrangement.spacedBy(20.dp)){
        item{if(s.audio==null)OpenHero(open,{vm.demo()})else TrackCard(s,vm,open)}
        if(s.audio==null)item{Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween){Hint(Icons.Outlined.Lock,"Аудио остаётся у тебя");Hint(Icons.Outlined.OfflineBolt,"Без подписки")}}
        if(s.audio!=null){
            item{Surface(shape=RoundedCornerShape(18.dp),color=Panel){Column(Modifier.padding(18.dp),verticalArrangement=Arrangement.spacedBy(9.dp)){
                Row(verticalAlignment=Alignment.CenterVertically){Column(Modifier.weight(1f)){Eyebrow("ТВОЙ МАСТЕР",Lime);Text(all.firstOrNull{it.id==s.presetId}?.name?:"Ручные настройки",fontSize=18.sp,fontWeight=FontWeight.Bold,modifier=Modifier.padding(top=5.dp))};IconButton(onClick=savePreset){Icon(Icons.Outlined.BookmarkAdd,"Сохранить свои настройки",tint=Muted)}}
                ControlSlider("Интенсивность",s.settings.amount,0.0..1.0,"${(s.settings.amount*100).toInt()}%",enabled=!s.busy){vm.settings(s.settings.copy(amount=it))}
                Row(verticalAlignment=Alignment.CenterVertically){TextButton(onClick={vm.autoPreset()},contentPadding=PaddingValues(0.dp)){Icon(Icons.Outlined.AutoFixHigh,null,Modifier.size(15.dp));Spacer(Modifier.width(5.dp));Text("Автоанализ",fontSize=12.sp)};Spacer(Modifier.weight(1f));TextButton(onClick={vm.advanced()}){Text(if(s.advanced)"Скрыть настройки"else"Точная настройка",fontSize=12.sp);Icon(if(s.advanced)Icons.Default.ExpandLess else Icons.Default.ExpandMore,null,Modifier.size(18.dp))}}
                if(s.advanced){
                    ControlSlider("Целевая громкость",s.settings.target,-23.0..-9.0,"%.1f LUFS".format(s.settings.target)){vm.settings(s.settings.copy(target=it))}
                    ControlSlider("Низ",s.settings.bass,-4.0..4.0,"%+.1f dB".format(s.settings.bass)){vm.settings(s.settings.copy(bass=it))}
                    ControlSlider("Нижняя середина",s.settings.body,-4.0..4.0,"%+.1f dB".format(s.settings.body)){vm.settings(s.settings.copy(body=it))}
                    ControlSlider("Присутствие",s.settings.presence,-4.0..4.0,"%+.1f dB".format(s.settings.presence)){vm.settings(s.settings.copy(presence=it))}
                    ControlSlider("Воздух",s.settings.air,-4.0..4.0,"%+.1f dB".format(s.settings.air)){vm.settings(s.settings.copy(air=it))}
                    ControlSlider("Компрессия",s.settings.ratio,1.0..3.5,"%.1f:1".format(s.settings.ratio)){vm.settings(s.settings.copy(ratio=it))}
                    ControlSlider("Порог компрессора",s.settings.threshold,-30.0..-8.0,"%.1f dB".format(s.settings.threshold)){vm.settings(s.settings.copy(threshold=it))}
                    ControlSlider("Тепло",s.settings.warmth,0.0..0.5,"${(s.settings.warmth*100).toInt()}%"){vm.settings(s.settings.copy(warmth=it))}
                    ControlSlider("Потолок пиков",s.settings.ceiling,-3.0..-.3,"%.1f dBFS".format(s.settings.ceiling)){vm.settings(s.settings.copy(ceiling=it))}
                    ControlSlider("Ширина стерео",s.settings.width,.6..1.4,"${(s.settings.width*100).toInt()}% "){vm.settings(s.settings.copy(width=it))}
                    ControlSlider("Шумоподавление",s.settings.denoise,0.0..1.0,"${(s.settings.denoise*100).toInt()}%"){vm.settings(s.settings.copy(denoise=it))}
                    Text("Умеренное спектральное шумоподавление. Сильные значения могут затронуть тихие детали. Изменения применяются кнопкой ниже.",color=Muted,fontSize=10.sp)
                }
                Button(onClick={vm.render()},modifier=Modifier.fillMaxWidth().height(50.dp).testTag("render"),shape=RoundedCornerShape(12.dp),enabled=!s.busy){Icon(Icons.Outlined.GraphicEq,null,Modifier.size(19.dp));Spacer(Modifier.width(8.dp));Text(if(s.master==null)"Сделать мастер"else"Пересчитать мастер",fontWeight=FontWeight.Bold)}
            }}}
            if(s.master!=null)item{Surface(shape=RoundedCornerShape(18.dp),color=Lime.copy(alpha=.055f),border=BorderStroke(1.dp,Lime.copy(alpha=.24f))){Column(Modifier.padding(18.dp),verticalArrangement=Arrangement.spacedBy(13.dp)){
                Row(verticalAlignment=Alignment.CenterVertically){Icon(Icons.Outlined.CheckCircle,null,tint=Lime,modifier=Modifier.size(19.dp));Spacer(Modifier.width(8.dp));Text("Готовый мастер",fontWeight=FontWeight.Bold,color=Lime)}
                Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween){Metric("ДО","%.1f".format(s.analysis?.lufs?:-70.0),"LUFS");Metric("ПОСЛЕ","%.1f".format(s.masteredAnalysis?.lufs?:-70.0),"LUFS",Lime);Metric("ПИК","%.1f".format(s.masteredAnalysis?.peak?:-70.0),"dBFS")}
                Row(horizontalArrangement=Arrangement.spacedBy(8.dp)){FilterChip(selected=s.source=="original",onClick={vm.chooseSource("original")},label={Text("A · Исходник")});FilterChip(selected=s.source=="master",onClick={vm.chooseSource("master")},label={Text("B · Мастер")})}
                OutlinedButton(onClick=export,modifier=Modifier.fillMaxWidth().testTag("export"),shape=RoundedCornerShape(12.dp),border=BorderStroke(1.dp,Lime.copy(alpha=.5f))){Icon(Icons.Outlined.FileDownload,null,Modifier.size(18.dp));Spacer(Modifier.width(8.dp));Text("Экспортировать")}
                Text("LUFS — измеренная громкость. На очень плотном миксе цель может отличаться: оценивайте не только цифры, но и звук.",color=Muted,fontSize=10.sp)
            }}}
        }
        item{SectionTitle("Найди свой характер","${Presets.all.size} пресета · от прозрачного до насыщенного")}
        item{OutlinedTextField(value=s.query,onValueChange={vm.query(it)},placeholder={Text("Найти пресет",fontSize=13.sp)},leadingIcon={Icon(Icons.Outlined.Search,null,Modifier.size(19.dp),tint=Muted)},singleLine=true,shape=RoundedCornerShape(12.dp),modifier=Modifier.fillMaxWidth().height(52.dp),textStyle=LocalTextStyle.current.copy(fontSize=13.sp),colors=OutlinedTextFieldDefaults.colors(unfocusedBorderColor=Line,focusedBorderColor=Lime,unfocusedContainerColor=Panel))}
        item{LazyRow(horizontalArrangement=Arrangement.spacedBy(8.dp)){items(listOf("Все","Избранное","Базовые","Жанры","Вокал","Площадки","Восстановление","Мои")){c->FilterChip(selected=s.category==c,onClick={vm.category(c)},label={Text(c,fontSize=11.sp)},shape=CircleShape,colors=FilterChipDefaults.filterChipColors(selectedContainerColor=Lime,selectedLabelColor=Bg,containerColor=Panel,labelColor=Muted))}}}
        if(filtered.isEmpty())item{Text("Здесь пока ничего нет. Выберите другую категорию или добавьте пресет в избранное.",color=Muted,fontSize=13.sp,modifier=Modifier.padding(vertical=20.dp))}
        items(filtered.chunked(2)){row->Row(horizontalArrangement=Arrangement.spacedBy(12.dp),modifier=Modifier.fillMaxWidth()){row.forEach{p->PresetCard(p,s.presetId==p.id,p.id in s.favorites,Modifier.weight(1f),{vm.select(p)},{vm.favorite(p.id)})};if(row.size==1)Spacer(Modifier.weight(1f))}}
        item{Hint(Icons.Outlined.Headphones,"Лучше слушать в наушниках. До 5 минут на трек.")}
    }
}
@Composable private fun PresetCard(p:Preset,selected:Boolean,favorite:Boolean,modifier:Modifier,onClick:()->Unit,onFavorite:()->Unit){
    val color=if(selected)Lime else if(p.category=="Вокал")Violet else Color(0xFFB9BBC6)
    Surface(onClick=onClick,shape=RoundedCornerShape(16.dp),color=if(selected)Color(0xFF242C1D) else Panel,border=BorderStroke(1.dp,if(selected)Lime.copy(alpha=.7f)else Line),modifier=modifier.heightIn(min=151.dp)){
        Column(Modifier.padding(14.dp),verticalArrangement=Arrangement.spacedBy(9.dp)){
            Row(verticalAlignment=Alignment.CenterVertically){Canvas(Modifier.size(24.dp)){val h=listOf(.35f,.75f,.5f,1f,.45f);h.forEachIndexed{i,v->drawLine(color,Offset(i*size.width/5,size.height*(1-v)/2),Offset(i*size.width/5,size.height*(1+v)/2),3f,StrokeCap.Round)}};Spacer(Modifier.weight(1f));IconButton(onClick=onFavorite,modifier=Modifier.size(25.dp)){Icon(if(favorite)Icons.Default.Favorite else Icons.Outlined.FavoriteBorder,"В избранное: ${p.name}",tint=if(favorite)Violet else Muted,modifier=Modifier.size(17.dp))}}
            Text(p.name,fontSize=14.sp,fontWeight=FontWeight.SemiBold,lineHeight=18.sp,minLines=2,maxLines=2,overflow=TextOverflow.Ellipsis)
            Text(p.description,fontSize=10.sp,color=Muted,lineHeight=14.sp,minLines=2,maxLines=2,overflow=TextOverflow.Ellipsis)
            Row(verticalAlignment=Alignment.CenterVertically){Text(p.tag,fontSize=8.sp,color=color,letterSpacing=.7.sp,fontWeight=FontWeight.Bold,modifier=Modifier.weight(1f));if(selected)Icon(Icons.Default.CheckCircle,null,tint=Lime,modifier=Modifier.size(13.dp))}
        }
    }
}
@Composable private fun ControlSlider(label:String,value:Double,range:ClosedFloatingPointRange<Double>,display:String,enabled:Boolean=true,onChange:(Double)->Unit){Column{Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween){Text(label,color=Color(0xFFC3C5D0),fontSize=12.sp);Text(display,color=Lime,fontSize=11.sp,fontWeight=FontWeight.SemiBold)};Slider(value=value.toFloat(),onValueChange={onChange(it.toDouble())},valueRange=range.start.toFloat()..range.endInclusive.toFloat(),enabled=enabled,modifier=Modifier.height(32.dp),colors=SliderDefaults.colors(thumbColor=Lime,activeTrackColor=Lime,inactiveTrackColor=Line))}}

@Composable private fun StemsPage(s:StudioState,vm:StudioViewModel,modifier:Modifier,open:()->Unit,split:()->Unit,export:(String)->Unit){LazyColumn(modifier.fillMaxSize(),contentPadding=PaddingValues(start=22.dp,end=22.dp,bottom=28.dp),verticalArrangement=Arrangement.spacedBy(20.dp)){
    item{Column(verticalArrangement=Arrangement.spacedBy(10.dp)){Eyebrow("AI STEM SPLITTER",Violet);Text("Две дорожки.\nПолный контроль.",fontSize=30.sp,lineHeight=34.sp,fontWeight=FontWeight.Bold,letterSpacing=(-1).sp);Text("Отдели голос от музыки — для минусовки, ремикса или отдельного мастеринга.",fontSize=13.sp,lineHeight=20.sp,color=Muted)}}
    item{Surface(shape=RoundedCornerShape(20.dp),color=Color(0xFF272238),border=BorderStroke(1.dp,Color(0xFF433858))){Column(Modifier.padding(20.dp),verticalArrangement=Arrangement.spacedBy(14.dp)){
        Row(verticalAlignment=Alignment.CenterVertically){Icon(Icons.Outlined.Memory,null,tint=Violet,modifier=Modifier.size(27.dp));Spacer(Modifier.width(12.dp));Column{Text("UVR · MDX-Net",fontSize=16.sp,fontWeight=FontWeight.Bold);Text(if(s.modelReady)"Модель установлена · готово офлайн"else"Модель ~67 МБ · первая загрузка",color=Violet,fontSize=11.sp)}}
        Text("Реальная нейросеть на устройстве. Интернет нужен только для загрузки модели; ваша запись остаётся на телефоне.",fontSize=12.sp,lineHeight=18.sp,color=Color(0xFFBAB2CC))
        if(s.modelReady)TextButton(onClick={vm.removeModel()},contentPadding=PaddingValues(0.dp)){Text("Освободить память: удалить модель",fontSize=10.sp,color=Muted)}
    }}}
    if(s.audio==null)item{Button(onClick=open,modifier=Modifier.fillMaxWidth().height(52.dp),shape=RoundedCornerShape(12.dp)){Icon(Icons.Outlined.Add,null);Spacer(Modifier.width(8.dp));Text("Сначала выбери трек")}}
    else{
        item{Surface(shape=RoundedCornerShape(16.dp),color=Panel){Row(Modifier.padding(16.dp),verticalAlignment=Alignment.CenterVertically){Icon(Icons.Outlined.AudioFile,null,tint=Lime);Spacer(Modifier.width(12.dp));Column(Modifier.weight(1f)){Text(s.trackName,maxLines=1,overflow=TextOverflow.Ellipsis,fontSize=14.sp,fontWeight=FontWeight.SemiBold);Text("Исходник · ${clock(s.audio.seconds)}",color=Muted,fontSize=11.sp)};IconButton(onClick=open){Icon(Icons.Outlined.FolderOpen,"Другой файл",tint=Muted)}}}}
        item{Button(onClick=split,modifier=Modifier.fillMaxWidth().height(54.dp).testTag("split"),shape=RoundedCornerShape(13.dp),colors=ButtonDefaults.buttonColors(containerColor=Violet,contentColor=Color(0xFF201A33))){Icon(Icons.Outlined.CallSplit,null,Modifier.size(21.dp));Spacer(Modifier.width(9.dp));Text(if(s.stems==null)"Разделить на дорожки"else"Разделить заново",fontWeight=FontWeight.Bold)}}
        if(s.stems!=null){
            item{SectionTitle("Дорожки готовы","Прослушай и сохрани каждую отдельно")}
            item{StemCard("Вокал","Голос и бэк-вокал",Icons.Outlined.Mic,Violet,s.source=="vocals",{val was=s.playing;vm.chooseSource("vocals");if(!was)vm.togglePlay()},{export("vocals")})}
            item{StemCard("Инструментал","Музыка без основного голоса",Icons.Outlined.Piano,Lime,s.source=="instrumental",{val was=s.playing;vm.chooseSource("instrumental");if(!was)vm.togglePlay()},{export("instrumental")})}
            item{OutlinedButton(onClick={vm.chooseSource("original")},modifier=Modifier.fillMaxWidth()){Text("Вернуться к исходнику")}}
        }
    }
    item{Surface(color=Panel,shape=RoundedCornerShape(16.dp)){Column(Modifier.padding(18.dp),verticalArrangement=Arrangement.spacedBy(12.dp)){Hint(Icons.Outlined.Lock,"Без загрузки аудио на сервер");Hint(Icons.Outlined.Headphones,"Вокал + инструментал, не четыре стема");Text("Возможны остатки голоса и музыкальные артефакты. На длинном треке разделение может занять несколько минут и заметно нагрузить телефон.",fontSize=11.sp,lineHeight=17.sp,color=Muted)}}}
}}
@Composable private fun StemCard(title:String,detail:String,icon:ImageVector,color:Color,selected:Boolean,play:()->Unit,export:()->Unit){Surface(shape=RoundedCornerShape(18.dp),color=Panel,border=BorderStroke(1.dp,if(selected)color else Line)){Column(Modifier.padding(18.dp),verticalArrangement=Arrangement.spacedBy(16.dp)){Row(verticalAlignment=Alignment.CenterVertically){Box(Modifier.size(43.dp).background(color.copy(alpha=.13f),RoundedCornerShape(13.dp)),contentAlignment=Alignment.Center){Icon(icon,null,tint=color)};Spacer(Modifier.width(13.dp));Column(Modifier.weight(1f)){Text(title,fontSize=18.sp,fontWeight=FontWeight.SemiBold);Text(detail,fontSize=11.sp,color=Muted)}};Row(horizontalArrangement=Arrangement.spacedBy(9.dp)){OutlinedButton(onClick=play,modifier=Modifier.weight(1f),shape=RoundedCornerShape(10.dp)){Icon(Icons.Default.PlayArrow,null,Modifier.size(16.dp));Spacer(Modifier.width(4.dp));Text("Слушать",fontSize=12.sp)};Button(onClick=export,modifier=Modifier.weight(1f),shape=RoundedCornerShape(10.dp),colors=ButtonDefaults.buttonColors(containerColor=color,contentColor=Bg)){Icon(Icons.Outlined.FileDownload,null,Modifier.size(16.dp));Spacer(Modifier.width(4.dp));Text("Сохранить",fontSize=12.sp)}}}}}

@Composable private fun LibraryPage(s:StudioState,vm:StudioViewModel,modifier:Modifier,open:()->Unit){LazyColumn(modifier.fillMaxSize(),contentPadding=PaddingValues(start=22.dp,end=22.dp,bottom=28.dp),verticalArrangement=Arrangement.spacedBy(22.dp)){
    item{Column(verticalArrangement=Arrangement.spacedBy(8.dp)){Eyebrow("ТВОЯ КОЛЛЕКЦИЯ",Lime);Text("Библиотека",fontSize=32.sp,fontWeight=FontWeight.Bold,letterSpacing=(-1).sp);Text("Любимые настройки и история экспорта.",color=Muted,fontSize=13.sp)}}
    item{Row(horizontalArrangement=Arrangement.spacedBy(12.dp)){Button(onClick=open,modifier=Modifier.weight(1f),shape=RoundedCornerShape(12.dp)){Icon(Icons.Default.Add,null,Modifier.size(17.dp));Spacer(Modifier.width(5.dp));Text("Открыть трек",fontSize=12.sp)};OutlinedButton(onClick={vm.demo();vm.tab(0)},modifier=Modifier.weight(1f),shape=RoundedCornerShape(12.dp)){Text("Демотрек",fontSize=12.sp)}}}
    item{SectionTitle("Мои пресеты","Сохраняются между запусками")}
    if(s.customs.isEmpty())item{EmptyCard(Icons.Outlined.Bookmarks,"Пока нет своих пресетов","Настрой мастеринг и нажми значок закладки рядом с названием пресета.")}
    else items(s.customs){p->Surface(onClick={vm.select(p);vm.tab(0)},color=Panel,shape=RoundedCornerShape(14.dp)){Row(Modifier.padding(18.dp),verticalAlignment=Alignment.CenterVertically){Icon(Icons.Outlined.Bookmark,null,tint=Violet);Spacer(Modifier.width(13.dp));Column(Modifier.weight(1f)){Text(p.name,fontWeight=FontWeight.SemiBold);Text("${p.settings.target} LUFS · ${p.settings.width.let{(it*100).toInt()}}% стерео",fontSize=11.sp,color=Muted)};Icon(Icons.AutoMirrored.Filled.ArrowForward,null,tint=Muted)}}}
    item{SectionTitle("Экспорты","Файлы находятся в выбранных вами папках")}
    if(s.history.isEmpty())item{EmptyCard(Icons.Outlined.LibraryMusic,"Первый мастер впереди","После экспорта здесь появится запись о сохранённом файле.")}
    else items(s.history){entry->Surface(shape=RoundedCornerShape(14.dp),color=Panel){Row(Modifier.padding(16.dp),verticalAlignment=Alignment.CenterVertically){Icon(Icons.Outlined.AudioFile,null,tint=Lime);Spacer(Modifier.width(12.dp));Column(Modifier.weight(1f)){Text(entry.name,fontSize=13.sp,fontWeight=FontWeight.Medium,maxLines=2,overflow=TextOverflow.Ellipsis);Text(entry.detail,fontSize=10.sp,color=Muted,modifier=Modifier.padding(top=4.dp));Text(SimpleDateFormat("dd MMM, HH:mm",Locale("ru")).format(Date(entry.date)),fontSize=9.sp,color=Muted,modifier=Modifier.padding(top=4.dp))};Icon(Icons.Outlined.CheckCircle,null,Modifier.size(17.dp),tint=Lime)}}}
    item{Hint(Icons.Outlined.VerifiedUser,"Без аккаунта. Без рекламы. Твои файлы — твои.")}
}}
@Composable private fun EmptyCard(icon:ImageVector,title:String,description:String){Surface(color=Panel,shape=RoundedCornerShape(18.dp),border=BorderStroke(1.dp,Line)){Column(Modifier.fillMaxWidth().padding(25.dp),horizontalAlignment=Alignment.CenterHorizontally,verticalArrangement=Arrangement.spacedBy(11.dp)){Icon(icon,null,Modifier.size(30.dp),tint=Muted);Text(title,fontWeight=FontWeight.SemiBold,fontSize=15.sp);Text(description,fontSize=12.sp,lineHeight=18.sp,color=Muted,textAlign=androidx.compose.ui.text.style.TextAlign.Center)}}}
@Composable private fun Player(s:StudioState,vm:StudioViewModel){var drag by remember{mutableStateOf<Float?>(null)};var volume by remember{mutableStateOf(false)};val source=when(s.source){"master"->"МАСТЕР";"vocals"->"ВОКАЛ";"instrumental"->"ИНСТРУМЕНТАЛ";else->"ИСХОДНИК"}
    Surface(color=Color(0xFF1D2028),shadowElevation=12.dp){Column(Modifier.fillMaxWidth().padding(horizontal=18.dp,vertical=8.dp)){
        Row(verticalAlignment=Alignment.CenterVertically){FilledIconButton(onClick={vm.togglePlay()},enabled=!s.busy,modifier=Modifier.size(39.dp),colors=IconButtonDefaults.filledIconButtonColors(containerColor=Lime,contentColor=Bg)){Icon(if(s.playing)Icons.Default.Pause else Icons.Default.PlayArrow,if(s.playing)"Пауза"else"Воспроизвести",Modifier.size(23.dp))};Spacer(Modifier.width(12.dp));Column(Modifier.weight(1f)){Text(s.trackName,fontSize=12.sp,fontWeight=FontWeight.SemiBold,maxLines=1,overflow=TextOverflow.Ellipsis);Text(source,color=if(s.source=="master")Lime else Violet,fontSize=8.sp,letterSpacing=1.2.sp,modifier=Modifier.padding(top=3.dp))};Text("${clock((s.audio?.seconds?:0.0)*s.position)} / ${clock(s.audio?.seconds?:0.0)}",color=Muted,fontSize=10.sp);IconButton(onClick={volume=!volume},modifier=Modifier.size(32.dp)){Icon(Icons.AutoMirrored.Filled.VolumeUp,"Громкость",Modifier.size(17.dp),tint=Muted)}}
        Slider(value=drag?:s.position,onValueChange={drag=it},onValueChangeFinished={drag?.let{vm.seek(it)};drag=null},enabled=!s.busy,modifier=Modifier.fillMaxWidth().height(22.dp),colors=SliderDefaults.colors(thumbColor=Lime,activeTrackColor=Lime,inactiveTrackColor=Line))
        if(volume)ControlSlider("Громкость прослушивания",s.volume.toDouble(),0.0..1.0,"${(s.volume*100).toInt()}%"){vm.volume(it.toFloat())}
    }}
}
private fun clock(seconds:Double):String {val s=seconds.toInt().coerceAtLeast(0);return "%d:%02d".format(s/60,s%60)}
