import subprocess, numpy as np, imageio_ffmpeg, json
FF = imageio_ffmpeg.get_ffmpeg_exe()
W=H=960; FPS=24
cmd=[FF,'-hide_banner','-loglevel','error','-i','google_drive/VID_20261031_004245_984.mp4',
     '-vf',f'fps={FPS},scale={W}:{H}','-pix_fmt','rgb24','-f','rawvideo','-']
buf = subprocess.run(cmd, capture_output=True, check=True).stdout
arr = np.frombuffer(buf, np.uint8).reshape(-1,H,W,3)
print(arr.shape, arr.nbytes/1e6,'MB')
np.save('work/src.npy', arr)
