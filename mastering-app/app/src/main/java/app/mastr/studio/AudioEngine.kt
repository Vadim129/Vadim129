package app.mastr.studio

import kotlin.math.*
import org.jtransforms.fft.FloatFFT_1D

/** Interleaved stereo PCM. The app processes at 44.1 kHz, never uploads audio. */
data class Audio(val samples: FloatArray, val rate: Int = 44100) {
    val frames get() = samples.size / 2
    val seconds get() = frames.toDouble() / rate
}
data class Analysis(val lufs: Double, val peak: Double, val rms: Double, val correlation: Double, val lowRatio: Double)
data class Settings(
    val bass: Double = 0.0, val body: Double = -0.6, val presence: Double = 0.0,
    val air: Double = 0.0, val ratio: Double = 1.5, val threshold: Double = -18.0,
    val width: Double = 1.0, val warmth: Double = 0.0, val target: Double = -14.0,
    val ceiling: Double = -1.0, val denoise: Double = 0.0, val amount: Double = 1.0
)
data class Preset(val id: String, val name: String, val category: String, val description: String, val tag: String, val settings: Settings)
object Presets {
    val all = listOf(
        Preset("balanced", "Автоматический баланс", "Базовые", "Настройки по анализу вашего трека", "НА КАЖДЫЙ ДЕНЬ", Settings()),
        Preset("warm", "Аналоговое тепло", "Базовые", "Мягкая середина, округлый низ", "ТЁПЛЫЙ", Settings(bass=1.3, air=-0.5, warmth=.3, target=-14.5)),
        Preset("clarity", "Кристальная ясность", "Базовые", "Больше деталей без резкого верха", "ЧИСТЫЙ", Settings(body=-1.4,presence=.8,air=1.4,ratio=1.35)),
        Preset("punch", "Удар и плотность", "Базовые", "Собранный бас и упругий грув", "ПЛОТНЫЙ", Settings(bass=1.7,body=-1.2,ratio=2.4,threshold=-21.0,target=-12.0)),
        Preset("natural", "Без окрашивания", "Базовые", "Только уровень и защита пиков", "ПРОЗРАЧНЫЙ", Settings(body=0.0,ratio=1.0,target=-16.0,amount=1.0)),
        Preset("wide", "Широкая сцена", "Базовые", "Пространство сверху, низ в центре", "СТЕРЕО", Settings(width=1.3,air=.7,target=-14.5)),
        Preset("pop", "Современный поп", "Жанры", "Яркий вокал и ровная плотность", "POP", Settings(bass=.8,body=-1.0,presence=.9,air=1.0,ratio=2.0,target=-12.0)),
        Preset("hiphop", "Хип-хоп / R&B", "Жанры", "Весомый низ, голос впереди", "HIP-HOP", Settings(bass=2.4,body=-1.1,presence=.6,ratio=2.2,target=-11.5)),
        Preset("electronic", "Электроника", "Жанры", "Контрастный бас и широкие синты", "ELECTRONIC", Settings(bass=1.9,body=-1.4,air=1.2,width=1.2,ratio=2.6,target=-10.5)),
        Preset("rock", "Рок", "Жанры", "Энергия гитар, собранная середина", "ROCK", Settings(bass=.7,body=-.5,presence=1.0,ratio=2.4,target=-11.5)),
        Preset("acoustic", "Акустика", "Жанры", "Натуральные струны и дыхание", "ACOUSTIC", Settings(body=-.4,air=.6,ratio=1.2,target=-16.0)),
        Preset("jazz", "Джаз", "Жанры", "Бережно к атакам и пространству", "JAZZ", Settings(bass=.4,body=0.0,air=.3,ratio=1.15,target=-17.0)),
        Preset("classical", "Классика", "Жанры", "Максимум естественной динамики", "CLASSICAL", Settings(body=0.0,ratio=1.0,target=-18.0)),
        Preset("ambient", "Эмбиент", "Жанры", "Мягкие края и широкая атмосфера", "AMBIENT", Settings(body=-.3,presence=-.5,air=.5,width=1.22,ratio=1.2,target=-17.0)),
        Preset("lofi", "Lo-fi / Chill", "Жанры", "Тёплый характер и спокойный верх", "LO-FI", Settings(bass=.9,body=.4,presence=-.6,air=-2.0,warmth=.45,ratio=1.7,target=-15.0)),
        Preset("lullaby", "Колыбельная", "Жанры", "Без гонки громкости, мягко и близко", "SOFT", Settings(body=-.5,presence=-.6,air=-.7,ratio=1.15,target=-18.0)),
        Preset("dance", "Танцевальный", "Жанры", "Плотный ритм и подчёркнутый низ", "DANCE", Settings(bass=1.5,body=-1.0,air=.8,width=1.12,ratio=2.5,target=-11.0)),
        Preset("cinema", "Кинематографичный", "Жанры", "Глубина, масштаб и запас динамики", "CINEMATIC", Settings(bass=1.0,body=-.4,air=.4,width=1.18,ratio=1.3,target=-17.0)),
        Preset("voice", "Чистый голос", "Вокал", "Разборчивость без лишней тяжести", "VOICE", Settings(bass=-1.4,body=-1.4,presence=1.1,air=.4,ratio=2.0,target=-16.0,denoise=.25)),
        Preset("podcast", "Подкаст", "Вокал", "Ровная речь для наушников", "SPEECH", Settings(bass=-1.7,body=-.8,presence=.8,ratio=2.8,threshold=-22.0,width=.8,target=-16.0,denoise=.4)),
        Preset("warmvoice", "Тёплый вокал", "Вокал", "Мягкость и присутствие в середине", "INTIMATE", Settings(bass=.4,body=-.5,presence=.5,air=-.3,warmth=.18,ratio=1.7,target=-15.0)),
        Preset("spoken", "Аудиокнига", "Вокал", "Спокойный голос и тишина в паузах", "NARRATION", Settings(bass=-.7,body=-.7,presence=.5,ratio=2.0,width=.6,target=-18.0,denoise=.35)),
        Preset("stream", "Streaming −14", "Площадки", "Умеренная громкость и запас по пикам", "−14 LUFS", Settings(target=-14.0,ceiling=-1.2)),
        Preset("video", "Видео / YouTube", "Площадки", "Разборчивый микс для видео", "VIDEO", Settings(body=-.7,presence=.6,ratio=1.8,target=-14.0,ceiling=-1.2)),
        Preset("dynamic", "Dynamic −16", "Площадки", "Свободная динамика для стриминга", "−16 LUFS", Settings(ratio=1.2,target=-16.0,ceiling=-1.2)),
        Preset("broadcast", "Broadcast −23", "Площадки", "Тихий мастер с широким запасом", "−23 LUFS", Settings(ratio=1.3,target=-23.0,ceiling=-2.0)),
        Preset("loud", "Громкий мастер", "Площадки", "Повышенная плотность. Сравнивайте на слух", "LOUD", Settings(bass=.6,body=-1.0,ratio=3.0,threshold=-22.0,target=-9.5,ceiling=-1.0)),
        Preset("demo", "Демо → релиз", "Восстановление", "Убрать мутность и собрать баланс", "REFINE", Settings(body=-1.8,presence=.6,air=.7,ratio=1.8,denoise=.2)),
        Preset("dark", "Тёмный микс", "Восстановление", "Открыть приглушённую запись", "BRIGHTEN", Settings(bass=-.5,body=-.7,presence=1.3,air=2.2,ratio=1.4)),
        Preset("harsh", "Резкий микс", "Восстановление", "Приглушить колкость и сухой верх", "SMOOTH", Settings(body=.2,presence=-1.6,air=-1.1,warmth=.12,ratio=1.35,target=-15.0)),
        Preset("thin", "Тонкий микс", "Восстановление", "Добавить тела без перегруза", "BODY", Settings(bass=2.0,body=.8,air=-.4,warmth=.2,ratio=1.5,target=-14.5)),
        Preset("mono", "Моно-совместимый", "Восстановление", "Более устойчивая стереокартина", "FOCUS", Settings(width=.65,ratio=1.3,target=-15.0))
    )
}

class Biquad(private val b0:Double,private val b1:Double,private val b2:Double,private val a1:Double,private val a2:Double) {
    private var z1=0.0; private var z2=0.0
    fun sample(x:Double):Double { val y=x*b0+z1; z1=x*b1+z2-a1*y; z2=x*b2-a2*y; return y }
    companion object {
        fun highpass(f:Double,rate:Int=44100,q:Double=.707):Biquad { val w=2*PI*f/rate; val c=cos(w); val a=sin(w)/(2*q); return Biquad((1+c)/2/(1+a),-(1+c)/(1+a),(1+c)/2/(1+a),-2*c/(1+a),(1-a)/(1+a)) }
        fun lowpass(f:Double,rate:Int=44100):Biquad { val w=2*PI*f/rate; val c=cos(w); val a=sin(w)/sqrt(2.0); return Biquad((1-c)/2/(1+a),(1-c)/(1+a),(1-c)/2/(1+a),-2*c/(1+a),(1-a)/(1+a)) }
        fun peak(f:Double,gain:Double,q:Double=.75,rate:Int=44100):Biquad { val w=2*PI*f/rate; val a=sin(w)/(2*q); val g=10.0.pow(gain/40); val d=1+a/g; return Biquad((1+a*g)/d,-2*cos(w)/d,(1-a*g)/d,-2*cos(w)/d,(1-a/g)/d) }
        fun shelf(f:Double,gain:Double,high:Boolean,rate:Int=44100):Biquad {
            val a=10.0.pow(gain/40); val w=2*PI*f/rate; val c=cos(w); val b=sin(w)*sqrt(2*a)
            val d=if(high) (a+1)-(a-1)*c+b else (a+1)+(a-1)*c+b
            return if(high) Biquad(a*((a+1)+(a-1)*c+b)/d,-2*a*((a-1)+(a+1)*c)/d,a*((a+1)+(a-1)*c-b)/d,2*((a-1)-(a+1)*c)/d,((a+1)-(a-1)*c-b)/d)
            else Biquad(a*((a+1)-(a-1)*c+b)/d,2*a*((a-1)-(a+1)*c)/d,a*((a+1)-(a-1)*c-b)/d,-2*((a-1)+(a+1)*c)/d,((a+1)+(a-1)*c-b)/d)
        }
        fun kShelf()=Biquad(1.530841230050348,-2.650979995154729,1.169079079921587,-1.663655113256020,.712595428073225)
        fun kHighpass()=Biquad(1.0,-2.0,1.0,-1.989169673629796,.989199035787039)
    }
}
object AudioEngine {
    private fun db(x:Double)=20*log10(max(x,1e-12))
    fun analyze(a:Audio):Analysis {
        if(a.frames==0) return Analysis(-70.0,-120.0,-120.0,1.0,0.0)
        val shelf=Array(2){Biquad.kShelf()};val hp=Array(2){Biquad.kHighpass()}; val low=Array(2){Biquad.lowpass(180.0)}
        val hop=4410; val energies=ArrayList<Double>();var e=0.0;var num=0
        var peak=0.0;var energy=0.0;var lowE=0.0;var cross=0.0;var le=0.0;var re=0.0
        for(i in 0 until a.frames) {
            for(c in 0..1) { val x=a.samples[2*i+c].toDouble(); peak=max(peak,abs(x));energy+=x*x;val l=low[c].sample(x);lowE+=l*l;val k=hp[c].sample(shelf[c].sample(x));e+=k*k }
            val l=a.samples[2*i].toDouble();val r=a.samples[2*i+1].toDouble();cross+=l*r;le+=l*l;re+=r*r
            if(++num==hop){energies.add(e/hop);e=0.0;num=0}
        }
        if(num>0) energies.add(e/num)
        val blocks=if(energies.size>=4) (0..energies.size-4).map { j-> (0..3).sumOf { energies[j+it] }/4 } else energies
        val absGate=blocks.filter { -.691+10*log10(max(it,1e-12)) > -70 }
        val preliminary=if(absGate.isEmpty()) 0.0 else absGate.average()
        val gate=absGate.filter { it > preliminary*.1 }
        val integrated=if(gate.isEmpty()) -70.0 else max(-70.0,-.691+10*log10(gate.average()))
        return Analysis(integrated,db(peak),db(sqrt(energy/a.samples.size)),cross/sqrt(max(le*re,1e-20)),lowE/max(energy,1e-12))
    }
    fun master(a:Audio,s:Settings,progress:(Float,String)->Unit):Audio {
        val amount=s.amount.coerceIn(0.0,1.0); var x=a.samples.copyOf()
        if(s.denoise>0.01) x=denoise(x,s.denoise*amount) { p->progress(p*.22f,"Мягкое шумоподавление") }
        val transparent=amount<.0001 || (s.bass==0.0 && s.body==0.0 && s.presence==0.0 && s.air==0.0 && s.ratio==1.0 && s.warmth==0.0 && s.width==1.0)
        val filters=Array(2){ if(transparent) emptyArray<Biquad>() else arrayOf(Biquad.highpass(27.0),Biquad.shelf(105.0,s.bass*amount,false),Biquad.peak(285.0,s.body*amount),Biquad.peak(2600.0,s.presence*amount),Biquad.shelf(9000.0,s.air*amount,true)) }
        val sideLow=Biquad.lowpass(140.0); var env=0.0;var gain=1.0
        val attack=exp(-1.0/(.022*a.rate));val release=exp(-1.0/(.17*a.rate));val ga=exp(-1.0/(.014*a.rate));val gr=exp(-1.0/(.16*a.rate))
        val ratio=1+(s.ratio-1)*amount;val width=1+(s.width-1)*amount
        for(i in 0 until a.frames) {
            var l=x[i*2].toDouble();var r=x[i*2+1].toDouble()
            filters[0].forEach { l=it.sample(l) };filters[1].forEach { r=it.sample(r) }
            val power=(l*l+r*r)*.5;val c=if(power>env) attack else release;env=c*env+(1-c)*power
            val over=max(0.0,10*log10(max(env,1e-12))-s.threshold);val target=10.0.pow(-over*(1-1/ratio)/20)
            val g=if(target<gain)ga else gr;gain=g*gain+(1-g)*target;l*=gain;r*=gain
            val warmth=s.warmth*amount
            if(warmth>0){ val drive=1+warmth*1.3;l=(1-warmth)*l+warmth*tanh(l*drive)/drive;r=(1-warmth)*r+warmth*tanh(r*drive)/drive }
            val mid=(l+r)*.5;val side=(l-r)*.5;val low=sideLow.sample(side);val wide=(side-low)*width+low*(if(transparent)1.0 else 1-.15*amount)
            x[2*i]=(mid+wide).toFloat();x[2*i+1]=(mid-wide).toFloat()
            if(i%44100==0)progress(.22f+.35f*i/a.frames,"Эквалайзер · компрессор · стерео")
        }
        progress(.59f,"Расчёт громкости LUFS")
        // Never select a quieter target than the actual source, even for quiet presets.
        val source = analyze(a)
        val target = max(source.lufs, s.target)
        progress(.72f,"Контроль итоговой громкости и пиков")
        matchLoudness(x, target, 10.0.pow(s.ceiling / 20), a.rate)
        // Short fades avoid filter-start clicks without changing the track length.
        val fade=min(220,a.frames/2);for(i in 0 until fade){val g=i.toFloat()/max(1,fade);x[2*i]*=g;x[2*i+1]*=g}
        require(x.all { it.isFinite() }) { "Некорректные отсчёты после обработки" }
        progress(1f,"Готово")
        return Audio(x)
    }
    /** Conservative, deterministic starting values; no user intensity knob needed. */
    fun automaticSettings(a: Analysis, preset: Settings = Settings()): Settings {
        val crest = a.peak - a.rms
        return preset.copy(
            amount = 1.0,
            target = max(a.lufs, preset.target),
            ratio = min(preset.ratio, if (crest < 7) 1.0 else if (crest < 11) 1.35 else 2.0),
            threshold = (a.rms + 3.0).coerceIn(-30.0, -8.0),
            bass = if (a.lowRatio > .57) min(preset.bass, -.8) else preset.bass,
            denoise = 0.0 // Do not remove musical detail automatically.
        )
    }

    /** Closed-loop, measured post-limiter LUFS. Safety always wins over an impossible target. */
    fun matchLoudness(x: FloatArray, target: Double, ceiling: Double, rate: Int = 44100) {
        if (x.none { abs(it) > 1e-10f }) return
        for (pass in 0 until 10) {
            val measured = analyze(Audio(x, rate)).lufs
            val delta = (target - measured).coerceIn(-18.0, 12.0)
            if (pass > 0 && abs(delta) < .08) break
            val gain = 10.0.pow(delta / 20)
            for (i in x.indices) x[i] = (x[i] * gain).toFloat()
            limiter(x, ceiling, rate)
        }
    }

    fun limiter(x:FloatArray,ceiling:Double,rate:Int=44100) {
        val n=x.size/2;val look=max(1,(rate*.005).toInt())
        // Only the lookahead window is needed, not two track-length arrays.
        // A 5-minute master now uses ~2 KiB for the queue, instead of ~106 MiB.
        var capacity=1;while(capacity<look+2)capacity*=2
        val mask=capacity-1;val indices=IntArray(capacity);val peaks=FloatArray(capacity)
        var head=0;var tail=0;var count=0;var scan=0;var gain=1.0
        val release=exp(-1.0/(rate*.09))
        for(i in 0 until n){
            while(count>0&&indices[head]<i){head=(head+1) and mask;count--}
            while(scan<min(n,i+look+1)){
                val peak=max(abs(x[scan*2]),abs(x[scan*2+1]))
                while(count>0&&peaks[(tail-1) and mask]<=peak){tail=(tail-1) and mask;count--}
                indices[tail]=scan++;peaks[tail]=peak;tail=(tail+1) and mask;count++
            }
            val wanted=min(1.0,ceiling/max(1e-12,peaks[head].toDouble()))
            gain=if(wanted<gain)wanted else release*gain+(1-release)*wanted
            x[2*i]=(x[2*i]*gain).coerceIn(-ceiling,ceiling).toFloat();x[2*i+1]=(x[2*i+1]*gain).coerceIn(-ceiling,ceiling).toFloat()
        }
    }

    private fun denoise(input:FloatArray,strength:Double,progress:(Float)->Unit):FloatArray {
        val fft=FloatFFT_1D(2048);val n=2048;val hop=512;val frames=input.size/2
        val window=FloatArray(n){(.5-.5*cos(2*PI*it/n)).toFloat()};val samples=96;val powers=Array(n/2+1){FloatArray(samples)};val temp=FloatArray(n*2)
        for(j in 0 until samples) {
            val start=if(frames>n) ((frames-n).toLong()*j/max(1,samples-1)).toInt() else 0
            temp.fill(0f);for(i in 0 until n) if(start+i<frames)temp[i]=(input[2*(start+i)]+input[2*(start+i)+1])*.5f*window[i]
            fft.realForwardFull(temp);for(k in powers.indices)powers[k][j]=temp[2*k]*temp[2*k]+temp[2*k+1]*temp[2*k+1]
        }
        val noise=FloatArray(powers.size){k->powers[k].sort();powers[k][samples/12]}
        val out=FloatArray(input.size);val weights=FloatArray(frames)
        for(start in -n/2 until frames step hop) {
            for(c in 0..1) {
                temp.fill(0f);for(i in 0 until n)if(start+i in 0 until frames)temp[i]=input[2*(start+i)+c]*window[i]
                fft.realForwardFull(temp)
                for(k in 0..n/2) {val p=temp[2*k]*temp[2*k]+temp[2*k+1]*temp[2*k+1];val g=max(10.0.pow(-6*strength/20),1-strength*.8*noise[k]/max(p,1e-12f)).toFloat();temp[2*k]*=g;temp[2*k+1]*=g;if(k>0&&k<n/2){temp[2*(n-k)]=temp[2*k];temp[2*(n-k)+1]=-temp[2*k+1]}}
                fft.complexInverse(temp,true)
                for(i in 0 until n)if(start+i in 0 until frames){out[2*(start+i)+c]+=temp[2*i]*window[i];if(c==0)weights[start+i]+=window[i]*window[i]}
            }
            if(start%(hop*32)==0)progress(max(0f,start.toFloat()/frames))
        }
        for(i in 0 until frames)if(weights[i]>1e-6){out[2*i]/=weights[i];out[2*i+1]/=weights[i]}
        return out
    }
    fun resample(a:Audio,target:Int=44100):Audio {
        if(a.rate==target)return a
        val ratio=target.toDouble()/a.rate;val count=(a.frames*ratio).toInt();val phases=512;val taps=24
        val cutoff=min(1.0,ratio)*.94
        val table=Array(phases){p->
            val weights=DoubleArray(taps){j->val t=j-(taps/2-1)-p.toDouble()/phases;val sinc=if(abs(t)<1e-10)cutoff else sin(PI*t*cutoff)/(PI*t);sinc*(.5+.5*cos(PI*t/(taps/2)))}
            val sum=weights.sum();FloatArray(taps){(weights[it]/sum).toFloat()}
        }
        val out=FloatArray(count*2)
        for(i in 0 until count){val src=i/ratio;val base=floor(src).toInt();val phase=((src-base)*phases).toInt().coerceIn(0,phases-1);for(c in 0..1){var y=0.0;for(j in 0 until taps){val pos=(base+j-(taps/2-1)).coerceIn(0,a.frames-1);y+=a.samples[pos*2+c]*table[phase][j]};out[i*2+c]=y.toFloat()}}
        return Audio(out,target)
    }
    fun demo():Audio {
        val sr=44100;val frames=sr*12;val x=FloatArray(frames*2);val notes=doubleArrayOf(261.626,311.127,391.995,349.228)
        for(i in 0 until frames){val t=i.toDouble()/sr;val bar=(t/1.5).toInt();val f=notes[bar%notes.size];val beat=t%(.75);val chord=(sin(2*PI*f*t)+.45*sin(2*PI*f*1.5*t)+.25*sin(2*PI*f*2*t))*.13*exp(-(t%1.5)*2);val bass=sin(2*PI*f/4*t)*.16*exp(-(t%1.5)*4);val kick=sin(2*PI*(52*beat+4*(1-exp(-beat*30))))*.2*exp(-beat*25);val fade=min(1.0,min(t/.03,(12-t)/.5));x[2*i]=((chord+bass+kick)*fade).toFloat();x[2*i+1]=((chord*.85+bass+kick+.015*sin(2*PI*f*2*t))*fade).toFloat()}
        return Audio(x)
    }
}
