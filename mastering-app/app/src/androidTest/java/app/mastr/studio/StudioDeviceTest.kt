package app.mastr.studio
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.Assert.*
import java.io.File

@RunWith(AndroidJUnit4::class)
class StudioDeviceTest {
    @Test fun wavFormatsAndAacRoundTrip(){val ctx=InstrumentationRegistry.getInstrumentation().targetContext;val a=Audio(AudioEngine.demo().samples.copyOf(44100*2));for(bits in listOf(16,24)){val f=File(ctx.cacheDir,"test-$bits.wav");AudioIO.writeWav(a,f,bits);val b=AudioIO.readWav(f);assertEquals(a.frames,b.frames);assertEquals(a.samples[100].toDouble(),b.samples[100].toDouble(),.0001);f.delete()};val float=File(ctx.cacheDir,"test-float.wav");AudioIO.WavWriter(float,floating=true).use{it.append(a.samples)};assertEquals(a.frames,AudioIO.readWav(float).frames);val aac=File(ctx.cacheDir,"test.m4a");AudioIO.writeAac(a,aac);assertTrue(aac.length()>1000);val b=AudioIO.decode(ctx,android.net.Uri.fromFile(aac)){_,_->};assertTrue(kotlin.math.abs(b.seconds-a.seconds)<.1)}
    @Test fun realOnnxSeparationProducesComplementaryStems(){val ctx=InstrumentationRegistry.getInstrumentation().targetContext;val splitter=StemSeparator(ctx);assertTrue("CI must stage the verified model",splitter.isReady);val source=Audio(AudioEngine.demo().samples.copyOf(44100*2));val stems=splitter.separate(source){_,_->};val v=AudioIO.readWav(stems.vocals);val i=AudioIO.readWav(stems.instrumental);assertEquals(source.frames,v.frames);assertEquals(source.frames,i.frames);val error=source.samples.indices.maxOf{kotlin.math.abs(source.samples[it]-v.samples[it]-i.samples[it])};assertTrue("Recombination error $error",error<.00001);assertTrue(v.samples.any{kotlin.math.abs(it)>.0001})}
}
