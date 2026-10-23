"""Run actual ACE-Step 1.5 Cover inference on an isolated CPU worker.

No SoundFont/MIDI layering, no fallback that substitutes the original as output.
Only generated outputs and technical metadata go into the encrypted artifact.
Run from the checked-out, pinned ACE-Step project with this repository on disk.
"""
import argparse
import gc
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

os.environ['ACESTEP_INIT_LLM'] = 'false'
os.environ['TOKENIZERS_PARALLELISM'] = 'false'
os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
os.environ['HF_HUB_DISABLE_PROGRESS_BARS'] = '1'

import numpy as np
import soundfile as sf
import torch
import torchaudio
from huggingface_hub import snapshot_download
from loguru import logger

# The native audio saver calls torchaudio.save; soundfile is sufficient for
# lossless output and avoids an unnecessary torchcodec dependency on CPU.
def save_lossless(uri, src, sample_rate, **kwargs):
    sf.write(str(uri), src.detach().cpu().float().numpy().T, sample_rate, subtype='PCM_24')
torchaudio.save = save_lossless


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--mode', choices=['preview','full'],default='preview')
    args = parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    torch.set_num_threads(min(4,os.cpu_count() or 2))
    torch.set_num_interop_threads(1)
    logger.remove()
    logger.add(lambda m: print(m,end='',flush=True),level='WARNING')
    root = Path.cwd()
    ckpt = root/'checkpoints'
    print('Downloading only DiT, VAE and text encoder; no planning LM.',flush=True)
    snapshot_download('ACE-Step/Ace-Step1.5',local_dir=str(ckpt),
        allow_patterns=['acestep-v15-turbo/**','vae/**','Qwen3-Embedding-0.6B/**'],
        ignore_patterns=['*.bin','*.msgpack','*.onnx'],max_workers=3)

    from acestep.handler import AceStepHandler
    from acestep.inference import GenerationParams,GenerationConfig,generate_music

    class CpuCoverHandler(AceStepHandler):
        def _ensure_models_present(self,*,checkpoint_path,config_path,prefer_source,vae_variant=None):
            # All required inference components were explicitly downloaded above.
            # Do not fetch the unused 1.7B LM just to satisfy main-model checks.
            for name in (config_path,'vae','Qwen3-Embedding-0.6B'):
                if not (checkpoint_path/name).is_dir():
                    return f'Missing required component: {name}',False
            return None
        def _load_main_model_from_checkpoint(self,**kwargs):
            # Reduced-memory inference for a 16 GB hosted CPU worker.
            self.dtype = torch.bfloat16
            return super()._load_main_model_from_checkpoint(**kwargs)

    handler = CpuCoverHandler()
    print('Initializing ACE-Step 1.5 Turbo on CPU.',flush=True)
    status,okay = handler.initialize_service(project_root=str(root),config_path='acestep-v15-turbo',
        device='cpu',compile_model=False,offload_to_cpu=False,
        use_flash_attention=False,use_mlx_dit=False,prefer_source='huggingface')
    if not okay:
        raise RuntimeError(status)
    print('Model loaded; generating a real audio-conditioned cover.',flush=True)
    raw,sr = sf.read(args.source,dtype='float32',always_2d=True)
    duration = len(raw)/sr
    start = 40.0
    clip_duration = min(24.,duration-start)
    if clip_duration<10:
        raise ValueError('Source is too short for the selected test region.')
    preview_source = args.source.parent/'cover_reference.wav'
    sf.write(preview_source,raw[int(start*sr):int((start+clip_duration)*sr)],sr,subtype='PCM_24')
    del raw
    gc.collect()
    jobs = [('preview',preview_source,clip_duration)]
    if args.mode=='full':
        jobs.append(('full',args.source,duration))
    reports=[]
    for name,path,seconds in jobs:
        t0=time.monotonic()
        params=GenerationParams(
            task_type='cover',src_audio=str(path),reference_audio=None,
            caption=('A polished intimate Russian lullaby with natural expressive lead vocals, '
                     'a coherent warm acoustic pop arrangement, soft acoustic guitar, '
                     'warm electric piano, restrained bass and delicate brushed percussion. '
                     'Gentle flowing dynamics, spacious clean stereo production, clear vocals. '
                     'No celesta, no violin, no heavy drums, no distortion.'),
            lyrics='',vocal_language='ru',duration=seconds,bpm=76,keyscale='C minor',
            audio_cover_strength=.75,inference_steps=8,shift=3.0,seed=129,
            thinking=False,use_cot_metas=False,use_cot_caption=False,use_cot_language=False,
            enable_normalization=True,normalization_db=-1.5,
        )
        config=GenerationConfig(batch_size=1,audio_format='wav',use_random_seed=False)
        with torch.inference_mode():
            result=generate_music(handler,None,params,config,save_dir=str(args.output/name))
        if not result.success or not result.audios:
            raise RuntimeError(f'ACE-Step generation failed: {result.error or result.status_message}')
        generated=Path(result.audios[0]['path'])
        dest=args.output/f'ace_step_{name}.wav'
        shutil.copyfile(generated,dest)
        y,rate=sf.read(dest,always_2d=True)
        if not np.isfinite(y).all() or np.sqrt(np.mean(y*y))<1e-5:
            raise RuntimeError('Generated audio is invalid or silent.')
        subprocess.run(['ffmpeg','-y','-v','error','-i',str(dest),'-c:a','libmp3lame',
                        '-b:a','320k',str(dest.with_suffix('.mp3'))],check=True)
        reports.append(dict(name=name,duration_seconds=len(y)/rate,
                            generation_seconds=round(time.monotonic()-t0,1),
                            model='ACE-Step 1.5 Turbo',task='cover',seed=129,
                            source_start_seconds=start if name=='preview' else 0,
                            note='Generated cover, not restoration: vocal timbre, pronunciation and arrangement may change.'))
        # Keep only final standardized files. Do not publish source-side captions,
        # latent caches, or copies of the supplied input recording.
        shutil.rmtree(args.output/name)
        (args.output/'report.json').write_text(json.dumps(reports,indent=2)+'\n')
        print(f'{name}: inference finished in {reports[-1]["generation_seconds"]} s.',flush=True)
        del y,result
        gc.collect()
    print('Generation completed successfully.',flush=True)


if __name__=='__main__':
    main()
