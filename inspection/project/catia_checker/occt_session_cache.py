"""Content-addressed OCCT caches. Display meshes never provide verdicts."""
import copy
import hashlib
import json
import os
import time
import tempfile
from pathlib import Path
import OCP

CACHE_VERSION='occt-session-v1'
def digest(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def atomic_json(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    # Independent writers must never share a .pending file. Windows readers
    # may also briefly deny replacement while the dashboard reads a snapshot.
    descriptor,name=tempfile.mkstemp(prefix=path.name+'.',suffix='.pending',dir=path.parent)
    temporary=Path(name)
    try:
        with os.fdopen(descriptor,'w',encoding='utf-8') as stream:
            json.dump(value,stream,ensure_ascii=False)
        for attempt in range(8):
            try:
                temporary.replace(path);return
            except PermissionError:
                if attempt==7:raise
                time.sleep(min(.02*(2**attempt),.25))
    finally:
        temporary.unlink(missing_ok=True)

def identity(paths, mapping=None):
    return hashlib.sha256(json.dumps({'version':CACHE_VERSION,'ocp':getattr(OCP,'__version__','unknown'),
        'sources':[(str(Path(p).resolve()),digest(p)) for p in paths],'mapping':mapping},
        sort_keys=True,ensure_ascii=False).encode()).hexdigest()

def load_batch(model,path,directory,progress=None):
    key=identity([path]);root=Path(directory)/key;receipt=root/'manifest.json'
    root.mkdir(parents=True,exist_ok=True)
    try:
        saved=json.loads(receipt.read_text(encoding='utf-8'))
        if saved['identity']!=key:raise ValueError('Cache identity mismatch')
        for item in saved['files']:
            filename=root/item['file']
            if filename.parent.resolve()!=root.resolve() or digest(filename)!=item['sha256']:
                raise ValueError('Invalid BREP cache')
        for item in saved['files']:model.load_brep(item['shape_id'],root/item['file'])
        model.source_file=str(Path(path).resolve())
        if progress:progress({'stage':'OCCT_BREP_CACHE_HIT','operation':'校验并读取持久 BREP；跳过 STEP 转换'})
        return copy.deepcopy(saved['manifest'])
    except (OSError,ValueError,KeyError,RuntimeError):
        model._shapes.clear()
    manifest=model.load_step(path,lightweight=True,progress=progress)
    files=[]
    for index,record in enumerate(manifest['shapes']):
        if record['shape_id']==manifest['root_shape_id']:continue
        filename=root/f'shape-{index:06d}.brep'
        model.write_brep(record['shape_id'],filename)
        files.append({'shape_id':record['shape_id'],'file':filename.name,'sha256':digest(filename)})
    atomic_json(receipt,{'identity':key,'manifest':manifest,'files':files})
    if progress:progress({'stage':'OCCT_BREP_CACHE_SAVED','operation':'已建立持久 BREP 缓存'})
    return manifest

def pair_file(model,shape_id,path):
    path=Path(path);receipt=path.with_suffix('.sha256')
    try:
        if digest(path)==receipt.read_text(encoding='ascii').strip():return
    except OSError:pass
    path.parent.mkdir(parents=True,exist_ok=True);model.write_brep(shape_id,path)
    receipt.write_text(digest(path),encoding='ascii')

def preview_valid(directory,key):
    root=Path(directory)
    try:
        saved=json.loads((root/'preview-cache.json').read_text(encoding='utf-8'))
        return saved['identity']==key and digest(root/'preview.json')==saved['sha256']
    except (OSError,ValueError,KeyError):return False

def mark_preview(directory,key):
    root=Path(directory)
    atomic_json(root/'preview-cache.json',{'identity':key,'sha256':digest(root/'preview.json')})

class ResidentControl:
    def __init__(self,directory,emit,verify,sleep=time.sleep):
        self.root=Path(directory);self.emit=emit;self.verify=verify;self.sleep=sleep
        self.marker=self.root/'pause-request.json';self.state=self.root/'resident-state.json'
    def publish(self,status,workers):
        atomic_json(self.state,{'pid':os.getpid(),'status':status,'workers':workers,'protocol':1})
    def hold(self,workers,save_checkpoint):
        save_checkpoint(force=True);self.publish('PAUSED',workers)
        self.emit({'stage':'PAUSED','resident':True,'max_workers':workers,
                   'operation':'已暂停；几何及 OCCT 工作进程保留在内存，可调整并发后直接恢复'})
        while self.marker.exists():self.sleep(0.2)
        settings=json.loads((self.root/'resume-settings.json').read_text(encoding='utf-8'))
        count=int(settings['workers']);budget=int(settings['budget_minutes'])
        if not 1<=count<=min(32,os.cpu_count() or 1) or not 1<=budget<=240:raise ValueError('Invalid resident resume settings')
        if not self.verify():raise RuntimeError('Export snapshot changed while paused; cold reload required')
        self.publish('RUNNING',count)
        self.emit({'stage':'RESIDENT_RESUMED','max_workers':count,'operation':'同进程恢复；未重新导入几何或生成网格'})
        return count,budget
