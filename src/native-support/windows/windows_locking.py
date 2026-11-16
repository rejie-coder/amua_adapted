"""Narrow flock compatibility for Windows; shared locks conservatively use exclusivity."""
import errno,os,time
LOCK_SH=1;LOCK_EX=2;LOCK_NB=4;LOCK_UN=8
try:import msvcrt
except ImportError:msvcrt=None
def flock(file,operation):
 if msvcrt is None:raise OSError(errno.ENOSYS,'Windows file locking unavailable')
 fd=file if isinstance(file,int) else file.fileno()
 if operation&~(LOCK_SH|LOCK_EX|LOCK_NB|LOCK_UN) or not operation&(LOCK_SH|LOCK_EX|LOCK_UN):raise ValueError('Unsupported lock operation')
 previous=os.lseek(fd,0,os.SEEK_CUR);deadline=time.monotonic()+30
 try:
  while True:
   os.lseek(fd,0,os.SEEK_SET)
   try:msvcrt.locking(fd,msvcrt.LK_UNLCK if operation&LOCK_UN else msvcrt.LK_NBLCK,1);return
   except OSError as error:
    if operation&LOCK_UN or error.errno not in (errno.EACCES,errno.EAGAIN,errno.EDEADLK):raise
    if operation&LOCK_NB:raise BlockingIOError(errno.EACCES,'Another operation is using this state') from None
    if time.monotonic()>=deadline:raise TimeoutError('State lock wait timed out') from None
    time.sleep(.05)
 finally:os.lseek(fd,previous,os.SEEK_SET)
