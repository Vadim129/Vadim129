package app.mastr.studio

import android.content.Context
import android.media.*
import android.net.Uri
import android.provider.OpenableColumns
import java.io.*
import java.nio.ByteBuffer
import java.nio.ByteOrder
import kotlin.math.*

object AudioIO {
    const val MAX_SECONDS=300
    fun name(context:Context,uri:Uri):String = runCatching {
        context.contentResolver.query(uri,arrayOf(OpenableColumns.DISPLAY_NAME),null,null,null)?.use { if(it.moveToFirst())it.getString(0) else null }
    }.getOrNull()?.takeIf {it.isNotBlank()} ?: uri.lastPathSegment?.substringAfterLast('/')?.takeIf {it.isNotBlank()} ?: "Мой трек"

    fun decode(context:Context,uri:Uri,progress:(Float,String)->Unit):Audio {
        val temp=File(context.cacheDir,"import-${System.nanoTime()}")
        try {
            context.contentResolver.openInputStream(uri).use { input->requireNotNull(input){"Не удалось открыть файл"};temp.outputStream().use { out->val block=ByteArray(65536);var total=0L;while(true){val n=input.read(block);if(n<0)break;out.write(block,0,n);total+=n;require(total<250_000_000){"Файл слишком большой. Максимум 250 МБ."};progress(.02f,"Чтение файла")}} }
            val header=temp.inputStream().use { val b=ByteArray(12); val n=it.read(b); b.copyOf(max(0,n)) }
            val audio=if(header.size==12 && String(header,0,4)=="RIFF" && String(header,8,4)=="WAVE") readWav(temp) else decodeCodec(context,temp,progress)
            require(audio.seconds<=MAX_SECONDS+.1){"В этой версии — до 5 минут на трек"}
            progress(.85f,"Подготовка 44,1 кГц")
            return AudioEngine.resample(audio)
        } finally {temp.delete()}
    }
    fun readWav(file:File):Audio {
        RandomAccessFile(file,"r").use { f->
            require(f.length()>=44){"Повреждённый WAV"};val header=ByteArray(12);f.readFully(header);require(String(header,0,4)=="RIFF"&&String(header,8,4)=="WAVE")
            var format=1;var channels=2;var rate=44100;var bits=16;var dataAt=0L;var dataSize=0L
            while(f.filePointer+8<=f.length()) {
                val id=ByteArray(4);f.readFully(id);val size=Integer.reverseBytes(f.readInt()).toLong() and 0xffffffffL;val next=f.filePointer+size
                require(next<=f.length()+1){"Повреждённый WAV: неверный размер блока"}
                when(String(id)) {
                    "fmt "->{require(size>=16);format=java.lang.Short.reverseBytes(f.readShort()).toInt() and 65535;channels=java.lang.Short.reverseBytes(f.readShort()).toInt() and 65535;rate=Integer.reverseBytes(f.readInt());f.skipBytes(6);bits=java.lang.Short.reverseBytes(f.readShort()).toInt() and 65535;if(format==65534&&size>=40){f.skipBytes(8);format=java.lang.Short.reverseBytes(f.readShort()).toInt() and 65535}}
                    "data"->{dataAt=f.filePointer;dataSize=size}
                }
                f.seek(min(f.length(),next+(size and 1)))
            }
            require(format in listOf(1,3) && channels in 1..8 && bits in listOf(8,16,24,32) && rate in 8000..192000){"Этот формат WAV не поддерживается"}
            require(dataAt>0&&dataSize>0){"В WAV нет аудио"}
            val bytes=bits/8;val frames=(dataSize/(channels*bytes)).toInt();require(frames.toDouble()/rate<=MAX_SECONDS+.1){"Максимум 5 минут на трек"}
            val result=FloatArray(frames*2);f.seek(dataAt)
            val buffer=ByteArray(4096*channels*bytes);var frame=0
            while(frame<frames){val count=min(4096,frames-frame);f.readFully(buffer,0,count*channels*bytes);val b=ByteBuffer.wrap(buffer).order(ByteOrder.LITTLE_ENDIAN)
                repeat(count){var l=0f;var r=0f;repeat(channels){c->val x=when {format==3&&bits==32->b.float;bits==8->((b.get().toInt() and 255)-128)/128f;bits==16->b.short/32768f;bits==24->{val v=(b.get().toInt() and 255) or ((b.get().toInt() and 255) shl 8) or (b.get().toInt() shl 16);v/8388608f};else->b.int/2147483648f};if(c==0)l=x;if(c==1)r=x};result[frame*2]=l;result[frame*2+1]=if(channels==1)l else r;frame++}
            }
            require(result.all { it.isFinite() }){"Некорректные отсчёты в файле"}
            return Audio(result,rate)
        }
    }
    private fun decodeCodec(context:Context,file:File,progress:(Float,String)->Unit):Audio {
        val extractor=MediaExtractor();var codec:MediaCodec?=null;val pcm=File(context.cacheDir,"decode-${System.nanoTime()}.pcm")
        try {
            extractor.setDataSource(file.absolutePath);val track=(0 until extractor.trackCount).firstOrNull {extractor.getTrackFormat(it).getString(MediaFormat.KEY_MIME)?.startsWith("audio/")==true} ?: error("В файле нет аудиодорожки")
            extractor.selectTrack(track);val fmt=extractor.getTrackFormat(track);val duration=if(fmt.containsKey(MediaFormat.KEY_DURATION))fmt.getLong(MediaFormat.KEY_DURATION) else 0L
            require(duration<=MAX_SECONDS*1_000_000L+100_000){"Максимум 5 минут на трек"}
            val mime=fmt.getString(MediaFormat.KEY_MIME)?:error("Неизвестный кодек");var rate=fmt.getInteger(MediaFormat.KEY_SAMPLE_RATE);var channels=fmt.getInteger(MediaFormat.KEY_CHANNEL_COUNT);var encoding=AudioFormat.ENCODING_PCM_16BIT
            fmt.setInteger(MediaFormat.KEY_PCM_ENCODING,AudioFormat.ENCODING_PCM_16BIT)
            val decoder=MediaCodec.createDecoderByType(mime);codec=decoder;decoder.configure(fmt,null,null,0);decoder.start()
            var inDone=false;var outDone=false;var frames=0L;val info=MediaCodec.BufferInfo()
            BufferedOutputStream(pcm.outputStream(),65536).use { output->
                val floatBytes=ByteBuffer.allocate(8).order(ByteOrder.LITTLE_ENDIAN)
                while(!outDone) {
                    progress(if(duration>0)(frames.toFloat()/rate/(duration/1_000_000.0)).toFloat().coerceIn(0f,.8f) else .3f,"Декодирование аудио")
                    if(!inDone){val index=decoder.dequeueInputBuffer(10000);if(index>=0){val b=decoder.getInputBuffer(index)!!;val n=extractor.readSampleData(b,0);if(n<0){decoder.queueInputBuffer(index,0,0,0,MediaCodec.BUFFER_FLAG_END_OF_STREAM);inDone=true}else{decoder.queueInputBuffer(index,0,n,extractor.sampleTime,0);extractor.advance()}}}
                    when(val index=decoder.dequeueOutputBuffer(info,10000)) {
                        MediaCodec.INFO_OUTPUT_FORMAT_CHANGED->{val f=decoder.outputFormat;rate=f.getInteger(MediaFormat.KEY_SAMPLE_RATE);channels=f.getInteger(MediaFormat.KEY_CHANNEL_COUNT);encoding=if(f.containsKey(MediaFormat.KEY_PCM_ENCODING))f.getInteger(MediaFormat.KEY_PCM_ENCODING) else AudioFormat.ENCODING_PCM_16BIT}
                        else->if(index>=0){val b=decoder.getOutputBuffer(index)!!.order(ByteOrder.LITTLE_ENDIAN);b.position(info.offset);b.limit(info.offset+info.size)
                            val bytes=if(encoding==AudioFormat.ENCODING_PCM_FLOAT)4 else 2;while(b.remaining()>=channels*bytes){var l=0f;var r=0f;repeat(channels){c->val x=if(bytes==4)b.float else b.short/32768f;if(c==0)l=x;if(c==1)r=x};floatBytes.clear();floatBytes.putFloat(l);floatBytes.putFloat(if(channels==1)l else r);output.write(floatBytes.array());frames++;require(frames<=MAX_SECONDS.toLong()*rate){"Максимум 5 минут на трек"}}
                            outDone=info.flags and MediaCodec.BUFFER_FLAG_END_OF_STREAM!=0;decoder.releaseOutputBuffer(index,false)}
                    }
                }
            }
            require(frames>0){"Не удалось декодировать запись"};val data=FloatArray(frames.toInt()*2);pcm.inputStream().buffered().use { input->val block=ByteArray(65536);var at=0;while(at<data.size){val need=min(block.size,(data.size-at)*4);var got=0;while(got<need){val n=input.read(block,got,need-got);require(n>0);got+=n};val b=ByteBuffer.wrap(block,0,got).order(ByteOrder.LITTLE_ENDIAN);while(b.remaining()>=4)data[at++]=b.float} }
            return Audio(data,rate)
        }finally{try{codec?.stop()}catch(_:Exception){};codec?.release();extractor.release();pcm.delete()}
    }
    class WavWriter(val file:File,val rate:Int=44100,val bits:Int=24,val floating:Boolean=false):Closeable {
        private val stream=BufferedOutputStream(file.outputStream(),65536);private var count=0L
        init {stream.write(ByteArray(44))}
        fun append(values:FloatArray,offset:Int=0,size:Int=values.size-offset){val bytes=if(floating)4 else bits/8;val block=ByteBuffer.allocate(min(4096,size)*bytes).order(ByteOrder.LITTLE_ENDIAN);var at=offset
            while(at<offset+size){block.clear();val n=min(4096,offset+size-at);repeat(n){val x=values[at++];require(x.isFinite());if(floating)block.putFloat(x) else if(bits==16)block.putShort((x.coerceIn(-1f,1f)*32767).roundToInt().toShort()) else {val v=(x.coerceIn(-1f,1f)*8388607).roundToInt();block.put(v.toByte());block.put((v shr 8).toByte());block.put((v shr 16).toByte())}};stream.write(block.array(),0,n*bytes);count+=n*bytes}
        }
        override fun close(){stream.close();RandomAccessFile(file,"rw").use { f->val b=ByteBuffer.allocate(44).order(ByteOrder.LITTLE_ENDIAN);val bytes=if(floating)4 else bits/8;b.put("RIFF".toByteArray());b.putInt((count+36).toInt());b.put("WAVEfmt ".toByteArray());b.putInt(16);b.putShort(if(floating)3 else 1);b.putShort(2);b.putInt(rate);b.putInt(rate*2*bytes);b.putShort((2*bytes).toShort());b.putShort((bytes*8).toShort());b.put("data".toByteArray());b.putInt(count.toInt());f.seek(0);f.write(b.array())} }
    }
    fun writeWav(a:Audio,file:File,bits:Int=24){WavWriter(file,a.rate,bits).use {it.append(a.samples)}}
    fun writeAac(a:Audio,file:File) {
        val codec=MediaCodec.createEncoderByType(MediaFormat.MIMETYPE_AUDIO_AAC);val mux=MediaMuxer(file.absolutePath,MediaMuxer.OutputFormat.MUXER_OUTPUT_MPEG_4);var muxStarted=false
        try{val fmt=MediaFormat.createAudioFormat(MediaFormat.MIMETYPE_AUDIO_AAC,a.rate,2);fmt.setInteger(MediaFormat.KEY_AAC_PROFILE,MediaCodecInfo.CodecProfileLevel.AACObjectLC);fmt.setInteger(MediaFormat.KEY_BIT_RATE,256000);fmt.setInteger(MediaFormat.KEY_MAX_INPUT_SIZE,16384);codec.configure(fmt,null,null,MediaCodec.CONFIGURE_FLAG_ENCODE);codec.start();var pos=0;var done=false;var inputDone=false;var track=-1;val info=MediaCodec.BufferInfo()
            while(!done){if(!inputDone){val idx=codec.dequeueInputBuffer(10000);if(idx>=0){val b=codec.getInputBuffer(idx)!!.order(ByteOrder.LITTLE_ENDIAN);b.clear();val n=min((b.remaining()/4)*2,a.samples.size-pos);for(i in 0 until n)b.putShort((a.samples[pos+i].coerceIn(-1f,1f)*32767).toInt().toShort());val pts=(pos/2)*1_000_000L/a.rate;pos+=n;inputDone=pos>=a.samples.size;codec.queueInputBuffer(idx,0,n*2,pts,if(inputDone)MediaCodec.BUFFER_FLAG_END_OF_STREAM else 0)}}
                when(val idx=codec.dequeueOutputBuffer(info,10000)){MediaCodec.INFO_OUTPUT_FORMAT_CHANGED->{track=mux.addTrack(codec.outputFormat);mux.start();muxStarted=true};else->if(idx>=0){val b=codec.getOutputBuffer(idx)!!;if(info.flags and MediaCodec.BUFFER_FLAG_CODEC_CONFIG!=0)info.size=0;if(info.size>0&&muxStarted){b.position(info.offset);b.limit(info.offset+info.size);mux.writeSampleData(track,b,info)};done=info.flags and MediaCodec.BUFFER_FLAG_END_OF_STREAM!=0;codec.releaseOutputBuffer(idx,false)}}
            }
        }finally{try{codec.stop()}catch(_:Exception){};codec.release();if(muxStarted)mux.stop();mux.release()}
    }
}
