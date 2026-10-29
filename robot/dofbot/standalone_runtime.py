"""Load the exact installed APP classifier/camera/action without the APP server."""
from pathlib import Path
from types import SimpleNamespace
import argparse, fcntl, hashlib, json, os, signal, subprocess, sys, threading, time

ROOT=Path(__file__).resolve().parent
RECORD=ROOT/'records'
RECORD.mkdir(exist_ok=True)
parser=argparse.ArgumentParser()
parser.add_argument('--execute',action='store_true')
args=parser.parse_args()
lock=open('/tmp/dofbot-standalone-voice.lock','w')
fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
for dev in ('/dev/myserial','/dev/myspeech'):
    if not Path(dev).exists():raise RuntimeError('Device missing: '+dev)
    if subprocess.run(['fuser',dev],capture_output=True).returncode!=1:
        raise RuntimeError('Device occupied: '+dev)
vendor=Path('/home/yahboom/colcon_ws/src/dofbot_garbage_yolov11')
hashes={'single_garbage_identify.py':'60b414d3f02237b303222c6dcc85e048d66d584842b003d52af743814915649e',
        'garbage_identify.py':'37716efc78d87e84be0cdf0231b82284079c25a7f682a0abd7b0d62e6518d741',
        'garbage_grap.py':'7be829d73138a11fdb19f347bd3c0c1bedd543836c4c24681598684f72301d5b'}
for name,digest in hashes.items():
    if hashlib.sha256((vendor/name).read_bytes()).hexdigest()!=digest:
        raise RuntimeError('Vendor source identity changed: '+name)
sys.path[:0]=[str(ROOT),str(vendor),'/home/yahboom/rosmaster']
import serial
native_write=serial.Serial.write
arm_path=str(Path('/dev/myserial').resolve())
stage='bootstrap'
allow_motion=False
audit_lock=threading.Lock()
tx_success_seq=0
boot={'pid':os.getpid(),'official_sources':hashes,'phone_required':False,'execute':args.execute,
      'started_at':time.time(),'suppressed_boot_writes':[]}
def save_boot():
    (RECORD/'bootstrap.json').write_text(json.dumps(boot,ensure_ascii=False,indent=2))
def audited_write(port,data):
    global tx_success_seq
    if os.path.realpath(str(port.port))!=arm_path:return native_write(port,data)
    packet=bytes(data)
    if stage=='bootstrap':
        boot['suppressed_boot_writes'].append(packet.hex());save_boot()
        return len(packet)
    if not allow_motion:raise RuntimeError('Arm write outside an authorized voice cycle')
    written=native_write(port,data)
    with audit_lock:
        with (RECORD/'arm-tx.jsonl').open('a') as log:
            log.write(json.dumps({'at':time.time(),'stage':stage,'hex':packet.hex(),'written':written})+'\n')
    if written!=len(packet):raise RuntimeError('Short arm serial write')
    tx_success_seq+=1
    return written
serial.Serial.write=audited_write
camera=None
preview=None
arm_observer=None

def preview_note(method,*values):
    # Display observation must never change whether official control proceeds.
    if arm_observer is not None:
        try:getattr(arm_observer,method)(*values)
        except Exception as exc:arm_observer.error=repr(exc)[-1000:]
try:
    import Arm_Lib
    sdk=Path(Arm_Lib.__file__).parent/'Arm_Lib.py'
    if hashlib.sha256(sdk.read_bytes()).hexdigest()!='c5ffe6b11d7ab18cbf5e4d6760d40f678db504884d6eb757c11a231cf8270d2f':
        raise RuntimeError('Not the verified serial SDK used by the APP')
    from single_garbage_identify import single_garbage_identify
    single=single_garbage_identify()
    import cv2 as cv
    camera_device='/dev/v4l/by-id/usb-Sonix_Technology_Co.__Ltd._USB_2.0_Camera-video-index0'
    if not Path(camera_device).exists():raise RuntimeError('Expected camera missing')
    native_capture=cv.VideoCapture
    def stable_capture(source=0,*a,**kw):
        return native_capture(camera_device if source==0 else source,*a,**kw)
    cv.VideoCapture=stable_capture
    from camera import VideoCamera
    native_camera=VideoCamera()
    cv.VideoCapture=native_capture

    class LatestCamera:
        # Keep capture fresh while idle; YOLO inference starts only after 108.
        def __init__(self):
            self.cv=threading.Condition();self.seq=0;self.consumed=0
            self.frame=None;self.at=0;self.frame_at=None;self.error=None;self.stop=False
            self.thread=threading.Thread(target=self.capture,daemon=True)
            self.thread.start()
        def capture(self):
            try:
                while not self.stop:
                    frame=native_camera.get_frame()
                    if getattr(frame,'ndim',None)!=3:raise RuntimeError('Camera frame unavailable')
                    captured_at=time.time()
                    with self.cv:
                        self.frame=frame;self.at=time.monotonic();self.frame_at=captured_at;self.seq+=1;self.cv.notify_all()
            except Exception as exc:
                with self.cv:self.error=repr(exc);self.cv.notify_all()
        def get_frame(self):
            with self.cv:
                if not self.cv.wait_for(lambda:self.seq>self.consumed or self.error,timeout=2):
                    raise RuntimeError('Camera timed out')
                if self.error:raise RuntimeError(self.error)
                if time.monotonic()-self.at>1.5:raise RuntimeError('Camera frame is stale')
                self.consumed=self.seq
                return self.frame.copy()
        def preview_snapshot(self):
            # A display reader must not consume a control frame or wait for its lock.
            if not self.cv.acquire(blocking=False):return None
            try:
                return {'frame':None if self.frame is None else self.frame.copy(),
                        'sequence':self.seq,'frame_at':self.frame_at,'camera_error':self.error}
            finally:self.cv.release()
        def close(self):
            self.stop=True;self.thread.join(timeout=2);native_camera.video.release()
    camera=LatestCamera()
    frame=camera.get_frame()
    try:
        from preview_publisher import PreviewPublisher,ArmObserver,observe_sdk
        preview_dir=Path('/run/user')/str(os.getuid())/'dofbot-voice-preview'
        boot['preview_dir']=str(preview_dir)
        arm_observer=ArmObserver()
        observe_sdk(single.arm,arm_observer,lambda:tx_success_seq)
        preview=PreviewPublisher(preview_dir,camera.preview_snapshot,pid=os.getpid(),
                                 session_started_at=boot['started_at'],observer=arm_observer,
                                 control_status_path=RECORD/'status.json')
        if not preview.start():boot['preview_error']=preview.preview_error
    except Exception as exc:
        boot['preview_error']=repr(exc)[-1000:]
    boot.update(camera_device=camera_device,camera_shape=list(frame.shape),sdk=str(sdk),
                state='ready_for_standalone_voice',ready_at=time.time())
    save_boot()
    def prepare():
        global stage,allow_motion
        stage='official_app_observation_pose';allow_motion=True
        preview_note('set_phase','preparing')
        try:
            # Exact YahboomArm.pyc line 271 / Analysis page entry, 1000 ms.
            single.arm.Arm_serial_servo_write6_array([90,125,0,0,90,0],1000)
            time.sleep(1.2)
            camera.get_frame()
        finally:
            allow_motion=False;stage='idle'
            preview_note('set_phase','idle')
    def grasp(category):
        global stage,allow_motion
        stage='official_single_garbage_grap';allow_motion=True
        preview_note('begin',category,single.grap_joint)
        try:return single.single_garbage_grap(category)
        finally:
            allow_motion=False;stage='idle'
            preview_note('finish')
    def terminate(signum,frame):raise SystemExit(0)
    signal.signal(signal.SIGTERM,terminate)
    signal.signal(signal.SIGINT,terminate)
    stage='idle'
    from standalone_voice import run
    proxy=SimpleNamespace(garbage_identify=single.garbage_identify,single_garbage_grap=grasp)
    run(proxy,camera,prepare,RECORD,enable_motion=args.execute)
except BaseException as exc:
    boot['exit']=repr(exc);boot['exited_at']=time.time();save_boot()
    raise
finally:
    allow_motion=False
    if preview is not None:
        try:preview.close()
        except Exception:pass
    if camera is not None:camera.close()
    serial.Serial.write=native_write
    lock.close()
