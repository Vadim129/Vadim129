package app.mastr.studio
import org.junit.Test
import org.junit.Assert.*
import kotlin.math.*

class AudioEngineTest {
    @Test fun limiterPreventsOverload(){val x=FloatArray(30000){if(it%1024<4)3f else .05f};AudioEngine.limiter(x,.8);assertTrue(x.all{it.isFinite()&&abs(it)<=.80001f})}
    @Test fun silenceIsFinite(){val a=Audio(FloatArray(44100*2));val stats=AudioEngine.analyze(a);assertEquals(-70.0,stats.lufs,.01);val result=AudioEngine.master(a,Settings()){_,_->};assertTrue(result.samples.all{it==0f})}
    @Test fun knownStereoSineHasExpectedLoudness(){val a=Audio(FloatArray(44100*4){(.1*sin(2*PI*(it/2)*1000/44100)).toFloat()});val stats=AudioEngine.analyze(a);assertEquals(-20.0,stats.lufs,.25);assertEquals(-20.0,stats.peak,.01)}
    @Test fun allPresetsAreDistinctAndFinite(){assertEquals(32,Presets.all.size);assertEquals(32,Presets.all.map{it.id}.distinct().size);assertEquals(32,Presets.all.map{it.settings}.distinct().size);val short=Audio(AudioEngine.demo().samples.copyOf(44100));for(p in Presets.all){val a=AudioEngine.master(short,p.settings){_,_->};assertEquals(short.samples.size,a.samples.size);assertTrue(p.id,a.samples.all{it.isFinite()&&abs(it)<=10.0.pow(p.settings.ceiling/20)+.00001})}}
    @Test fun sincResamplingPreservesDuration(){val a=Audio(FloatArray(48000*2){(.2*sin(2*PI*(it/2)*1000/48000)).toFloat()},48000);val b=AudioEngine.resample(a);assertEquals(44100,b.rate);assertEquals(44100,b.frames);assertEquals(.2,b.samples.maxOrNull()!!.toDouble(),.005)}

    @Test fun automaticSettingsUseFullStrengthAndNeverLowerTheTarget() {
        for (level in listOf(-23.0, -14.0, -9.0)) for (p in Presets.all) {
            val s = AudioEngine.automaticSettings(Analysis(level, -.5, -12.0, .8, .65), p.settings)
            assertEquals(1.0, s.amount, 0.0); assertTrue(s.target >= level); assertEquals(0.0, s.denoise, 0.0)
        }
    }
    @Test fun finishedMastersNeverLoseSourceLoudnessAcrossAllPresets() {
        for (scale in listOf(.4, 1.0, 2.2)) {
            val source = Audio(AudioEngine.demo().samples.map { (it * scale).toFloat() }.toFloatArray())
            val before = AudioEngine.analyze(source)
            for (p in Presets.all) {
                val settings = AudioEngine.automaticSettings(before, p.settings)
                val result = AudioEngine.master(source, settings) { _, _ -> }
                val after = AudioEngine.analyze(result)
                assertTrue("${p.id}: ${before.lufs} -> ${after.lufs}", after.lufs >= before.lufs - .15)
                assertTrue("${p.id}: target ${settings.target}, got ${after.lufs}", abs(after.lufs - settings.target) < .25)
                assertTrue(result.samples.all { abs(it) <= 10.0.pow(settings.ceiling / 20) + .00001 })
            }
        }
    }
    @Test fun transientHeavySourceRetainsLoudnessAfterLimiter() {
        val x = FloatArray(44100 * 2 * 4) { i ->
            val frame = i / 2
            ((.02 * sin(2 * PI * frame * 220 / 44100)) + if (frame % 11025 < 30) .8 else 0.0).toFloat()
        }
        val a = Audio(x); val before = AudioEngine.analyze(a)
        val result = AudioEngine.master(a, AudioEngine.automaticSettings(before)) { _, _ -> }
        assertTrue(AudioEngine.analyze(result).lufs >= before.lufs - .15)
        assertTrue(abs(AudioEngine.analyze(result).lufs - max(before.lufs, -14.0)) < .25)
    }
}
