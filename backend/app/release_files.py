"""Exclusive immutable ZIP storage; file presence alone never authorizes download."""
from pathlib import Path
from uuid import UUID
from hashlib import sha256
import os
import re
import stat
from .sdm_files import _directory
from .release_bundle import MAX_BUNDLE_BYTES


def path_for(root,project_id,run_id,identity,*,create=False):
    folder=Path(root)
    if not folder.is_absolute():raise ValueError('RELEASE_STORAGE_ABSOLUTE_ROOT_REQUIRED')
    _directory(folder)
    for segment in ('release',str(UUID(str(project_id))),str(UUID(str(run_id)))):
        folder=folder/segment
        if create:folder.mkdir(mode=0o700,exist_ok=True)
        _directory(folder)
    return folder/(str(UUID(str(identity)))+'.zip')


def save(root,project_id,run_id,identity,content):
    if type(content) is not bytes or not 0<len(content)<=MAX_BUNDLE_BYTES:raise ValueError('RELEASE_SIZE_INVALID')
    path=path_for(root,project_id,run_id,identity,create=True)
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_BINARY',0),0o600)
    with os.fdopen(fd,'wb') as stream:
        stream.write(content);stream.flush();os.fsync(stream.fileno())
    return {'checksum':sha256(content).hexdigest(),'file_size':len(content)}


def read(root,project_id,run_id,identity,checksum,file_size):
    if not isinstance(checksum,str) or not re.fullmatch('[a-f0-9]{64}',checksum) or type(file_size) is not int or not 0<file_size<=MAX_BUNDLE_BYTES:
        raise ValueError('RELEASE_STORAGE_METADATA_INVALID')
    try:
        path=path_for(root,project_id,run_id,identity);before=path.lstat()
        if not stat.S_ISREG(before.st_mode) or getattr(before,'st_file_attributes',0)&0x400:raise ValueError()
        with path.open('rb') as stream:
            after=os.fstat(stream.fileno())
            if (after.st_dev,after.st_ino,after.st_size)!=(before.st_dev,before.st_ino,file_size):raise ValueError()
            content=stream.read(file_size+1)
        if len(content)!=file_size or sha256(content).hexdigest()!=checksum:raise ValueError()
        return content
    except (OSError,ValueError):raise ValueError('RELEASE_FILE_CHANGED_OR_UNAVAILABLE') from None
