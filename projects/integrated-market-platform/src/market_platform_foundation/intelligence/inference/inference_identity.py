"""Whitelisted engine identity; credentials and transport objects are never cache material."""
from __future__ import annotations


def provider_identity(provider):
    engine = getattr(provider,'_provider',provider)
    identity = {'provider_class':type(engine).__module__+'.'+type(engine).__qualname__}
    for name in ('provider_id','model_id','runtime','reasoning_effort','reasoning_headroom','base_url','_request_model'):
        identity[name] = getattr(engine,name,None)
    manifest = getattr(getattr(engine,'_server',None),'manifest',None)
    if manifest is not None:
        identity['manifest'] = {key:str(getattr(manifest,key,None)) for key in
                               ('model_id','revision','runtime_version','context','gpu_layers','model_path','runtime_path')}
        for name in ('model_path','runtime_path'):
            path = getattr(manifest,name,None)
            try:
                stat = path.stat()
                identity[name+'_stat'] = [stat.st_size,stat.st_mtime_ns]
            except (AttributeError,OSError):
                identity[name+'_stat'] = None
    return identity


def reusable_engine(provider):
    engine = getattr(provider,'_provider',provider)
    if getattr(engine,'runtime',None) != 'LOCAL_MODEL':
        return True
    manifest = getattr(getattr(engine,'_server',None),'manifest',None)
    return bool(manifest is not None and manifest.revision and manifest.runtime_version)
