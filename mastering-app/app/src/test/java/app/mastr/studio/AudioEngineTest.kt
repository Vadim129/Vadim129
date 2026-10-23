package app.mastr.studio
import org.junit.Test
import org.junit.Assert.*
import kotlin.math.*

class AudioEngineTest {
    @Test fun stftRoundTripMatchesPcm(){val f=SpectralTransform(512,257,32,128);val source=FloatArray(f.chunk*2){i->(.3*sin(2*PI*(i/2)*440/44100)+.1*cos(2*PI*(i/2)*1200/44100)).toFloat()};val restored=f.inverse(f.forward(source));val error=source.indices.maxOf{abs(source[it]-restored[it])};assertTrue("Reconstruction error: $error",error<.00001)}
    @Test fun limiterPreventsOverload(){val x=FloatArray(30000){if(it%1024<4)3f else .05f};AudioEngine.limiter(x,.8);assertTrue(x.all{it.isFinite()&&abs(it)<=.80001f})}
    @Test fun silenceIsFinite(){val a=Audio(FloatArray(44100*2));val stats=AudioEngine.analyze(a);assertEquals(-70.0,stats.lufs,.01);val result=AudioEngine.master(a,Settings()){_,_->};assertTrue(result.samples.all{it==0f})}
    @Test fun knownStereoSineHasExpectedLoudness(){val a=Audio(FloatArray(44100*4){(.1*sin(2*PI*(it/2)*1000/44100)).toFloat()});val stats=AudioEngine.analyze(a);assertEquals(-20.0,stats.lufs,.25);assertEquals(-20.0,stats.peak,.01)}
    @Test fun allPresetsAreDistinctAndFinite(){assertEquals(32,Presets.all.size);assertEquals(32,Presets.all.map{it.id}.distinct().size);assertEquals(32,Presets.all.map{it.settings}.distinct().size);val short=Audio(AudioEngine.demo().samples.copyOf(44100));for(p in Presets.all){val a=AudioEngine.master(short,p.settings){_,_->};assertEquals(short.samples.size,a.samples.size);assertTrue(p.id,a.samples.all{it.isFinite()&&abs(it)<=10.0.pow(p.settings.ceiling/20)+.00001})}}
    @Test fun sincResamplingPreservesDuration(){val a=Audio(FloatArray(48000*2){(.2*sin(2*PI*(it/2)*1000/48000)).toFloat()},48000);val b=AudioEngine.resample(a);assertEquals(44100,b.rate);assertEquals(44100,b.frames);assertEquals(.2,b.samples.maxOrNull()!!.toDouble(),.005)}
}
