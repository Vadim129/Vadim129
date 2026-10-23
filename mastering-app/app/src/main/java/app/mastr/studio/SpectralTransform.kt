package app.mastr.studio

import org.jtransforms.fft.FloatFFT_1D
import kotlin.math.*

/** Torch-compatible periodic-Hann STFT, center=true, reflect padding.
 * Tensor layout [1, 4, frequency, time]: L real/imag, R real/imag.
 * Inverse uses conjugate symmetry and exact weighted overlap/add.
 */
class SpectralTransform(val nfft:Int,val frequencies:Int,val times:Int,val hop:Int=1024) {
    val chunk=hop*(times-1)
    private val fft=FloatFFT_1D(nfft.toLong())
    private val window=FloatArray(nfft){(.5-.5*cos(2*PI*it/nfft)).toFloat()}
    private val weights=FloatArray(chunk+nfft).also { w->for(t in 0 until times)for(i in 0 until nfft)w[t*hop+i]+=window[i]*window[i] }
    init{require(frequencies<=nfft/2+1&&chunk>nfft)}
    private fun reflect(index:Int):Int {var i=index;while(i<0||i>=chunk)i=if(i<0)-i else 2*chunk-2-i;return i}
    fun forward(audio:FloatArray):FloatArray {
        require(audio.size==chunk*2)
        val result=FloatArray(4*frequencies*times);val buffer=FloatArray(nfft*2)
        for(c in 0..1)for(t in 0 until times){buffer.fill(0f);for(i in 0 until nfft)buffer[i]=audio[2*reflect(t*hop+i-nfft/2)+c]*window[i];fft.realForwardFull(buffer)
            for(f in 0 until frequencies){result[((c*2)*frequencies+f)*times+t]=buffer[f*2];result[((c*2+1)*frequencies+f)*times+t]=buffer[f*2+1]}
        }
        return result
    }
    fun inverse(spectrum:FloatArray):FloatArray {
        require(spectrum.size==4*frequencies*times)
        val output=FloatArray(chunk*2);val buffer=FloatArray(nfft*2);val accum=FloatArray(chunk+nfft)
        for(c in 0..1){accum.fill(0f)
            for(t in 0 until times){buffer.fill(0f);for(f in 0 until frequencies){val re=spectrum[(c*2*frequencies+f)*times+t];val im=spectrum[((c*2+1)*frequencies+f)*times+t];buffer[f*2]=re;buffer[f*2+1]=im;if(f>0&&f<nfft/2){buffer[(nfft-f)*2]=re;buffer[(nfft-f)*2+1]=-im}};fft.complexInverse(buffer,true);for(i in 0 until nfft)accum[t*hop+i]+=buffer[2*i]*window[i]}
            for(i in 0 until chunk){val p=i+nfft/2;output[2*i+c]=accum[p]/max(1e-8f,weights[p])}
        }
        return output
    }
}
