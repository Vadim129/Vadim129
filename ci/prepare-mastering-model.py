"""Resolve the upstream MDX model metadata, hash and validate a real inference."""
import hashlib,json,os,urllib.request
from pathlib import Path
import numpy as np
import onnxruntime as ort
root=Path(__file__).resolve().parents[1]
work=root/'runtime/mastering';work.mkdir(parents=True,exist_ok=True)
url='https://github.com/TRvlvr/model_repo/releases/download/all_public_uvr_models/UVR_MDXNET_Main.onnx'
model=work/'UVR_MDXNET_Main.onnx'
if not model.exists(): urllib.request.urlretrieve(url,model)
blob=model.read_bytes();key=hashlib.md5(blob[-10000*1024:]).hexdigest()
meta=json.load(urllib.request.urlopen('https://raw.githubusercontent.com/Anjok07/ultimatevocalremovergui/master/models/MDX_Net_Models/model_data/model_data.json'))[key]
assert meta['primary_stem']=='Vocals',meta
sess=ort.InferenceSession(str(model),providers=['CPUExecutionProvider'])
dimf=meta['mdx_dim_f_set'];dimt=2**meta['mdx_dim_t_set'];shape=[1,4,dimf,dimt]
x=np.zeros(shape,dtype=np.float32);x[:,:,30:60,:]=.1
pred=sess.run(None,{sess.get_inputs()[0].name:x})[0]
assert pred.shape==tuple(shape) and np.isfinite(pred).all()
info=dict(filename=model.name,url=url,size=len(blob),sha256=hashlib.sha256(blob).hexdigest(),n_fft=meta['mdx_n_fft_scale_set'],dim_f=dimf,dim_t=dimt,compensate=meta['compensate'],primary_stem='Vocals')
(root/'mastering-app/app/src/main/assets/model_info.json').write_text(json.dumps(info,indent=2)+'\n')
print(json.dumps(info,indent=2))
