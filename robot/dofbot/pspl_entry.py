"""Optional one-task VM entry. Default installed startup remains unchanged.

Uses the existing Session for wake/start/busy/audio ordering and an explicit
new cycle accepting a consumed PS/PL permit. No local camera/model is opened.
"""
import argparse
import ast
import fcntl
import hashlib
import json
import queue
import signal
import subprocess
import threading
import time
from pathlib import Path

from pspl_client import PsplClient
from standalone_voice import Session, BlockingPlayer, CycleCancelled
from voice_bridge import FrameParser, SINGLE_AUDIO, SINGLE_CLASSES


class RemoteSession(Session):
    def __init__(self, client, **kwargs):
        self.client = client
        super().__init__(detect=client.detect, **kwargs)

    def _cycle(self):
        self._check()
        self.transition('preparing')
        if self.enable_motion:
            self.prepare()
        else:
            self.event('dry_run_prepare_skipped')
        self._check()
        # New remote task starts after the observation move completes, so all
        # accepted PS frames are newer than the task's producer-local boundary.
        self.client.begin(timeout_s=20)
        self.transition('recognizing')
        deadline = self.clock()+20
        selected = None
        try:
            while self.clock()<deadline:
                self._check()
                frame,msg = self.client.detect()
                self._check()
                self.recognition_frames += 1
                if len(msg)==1:
                    label = next(iter(msg))
                    result = self.client.last_result
                    if label not in SINGLE_CLASSES or result['detections'][0]['category_code']!=SINGLE_CLASSES[label][1]:
                        raise RuntimeError('PS business mapping differs from audited VM mapping')
                    selected=(frame,label,msg[label])
                    break
                self.sleep(.05)
            if selected is None:
                self.last_result='no_stable_target_timeout'
                self.event('recognition_timeout',timeout_seconds=20,grasp_started=False)
                return
            frame,self.label,xy = selected
            self.category = SINGLE_CLASSES[self.label][1]
            self.recognized(frame,self.label,xy)
            self._check()
            self.transition('announcing',audio_id=SINGLE_AUDIO[self.label],label=self.label,category=self.category)
            self.play(SINGLE_AUDIO[self.label],self.language)
            self.event('classification_audio_completed',audio_id=SINGLE_AUDIO[self.label])
            self._check()
            if self.enable_motion:
                self.transition('grasping',category=self.category)
                self.grasp_calls += 1
                self.grasp(self.category)
                self.sleep(1)
                self.last_result='official_grasp_callback_completed'
                self.event('grasp_callback_completed',physical_success_claimed=False)
            else:
                self.last_result='dry_run_completed'
                self.event('dry_run_grasp_skipped',category=self.category)
        finally:
            self.client.cancel()


def load_vendor_action(vendor_file, arm_device):
    """Read only two hash-pinned vendor methods, avoiding model/ROS import.

    The unchanged move and single_garbage_grap method ASTs are bound to the
    current SDK. No class initializer, module import or detection code executes.
    The vendor file is external and is not redistributed by this repository.
    """
    raw=Path(vendor_file).read_bytes()
    if hashlib.sha256(raw).hexdigest()!='60b414d3f02237b303222c6dcc85e048d66d584842b003d52af743814915649e':
        raise RuntimeError('vendor action source identity changed')
    tree=ast.parse(raw.decode('utf-8'))
    source=next(node for node in tree.body if isinstance(node,ast.ClassDef) and node.name=='single_garbage_identify')
    methods=[node for node in source.body if isinstance(node,ast.FunctionDef) and node.name in ('move','single_garbage_grap')]
    if len(methods)!=2:
        raise RuntimeError('audited vendor action methods missing')
    isolated=ast.Module(body=[ast.ClassDef(name='VendorAction',bases=[],keywords=[],body=methods,decorator_list=[])],type_ignores=[])
    namespace={'sleep':time.sleep}
    exec(compile(ast.fix_missing_locations(isolated),str(vendor_file),'exec'),namespace)
    action=namespace['VendorAction']()
    action.arm,action.grap_joint,action.status=arm_device,135,'waiting'
    return action


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',required=True)
    parser.add_argument('--execute',action='store_true')
    args=parser.parse_args()
    config=json.loads(Path(args.config).read_text(encoding='utf-8'))
    if config.get('voice_source','serial_id') not in ('serial_id','usb_pcm_pl'):
        raise ValueError('select exactly one voice source')
    token=Path(config['token_file']).read_text(encoding='utf-8').strip()
    client=PsplClient(endpoint=config['endpoint'],token=token,camera_id=config['camera_id'],
                      transform_id=config['transform_id'],timeout_s=config.get('timeout_s',1.),
                      voice_source=config.get('voice_source','serial_id'))
    lock=Path('/tmp/dofbot-standalone-voice.lock').open('w')
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    stop=threading.Event()
    incoming=queue.Queue(maxsize=64)
    serial_port=arm=None
    reader=None
    handlers={}
    def motion_disabled(*values):
        raise RuntimeError('motion callback reached without --execute')
    prepare=grasp=motion_disabled
    if args.execute:
        # Explicit future runtime only; reuse the same verified SDK and poses.
        import serial
        import Arm_Lib
        sdk=Path(Arm_Lib.__file__).parent/'Arm_Lib.py'
        if hashlib.sha256(sdk.read_bytes()).hexdigest()!='c5ffe6b11d7ab18cbf5e4d6760d40f678db504884d6eb757c11a231cf8270d2f':
            raise RuntimeError('installed Arm SDK differs from audited source')
        if not Path('/dev/myserial').exists() or subprocess.run(['fuser','/dev/myserial'],capture_output=True).returncode!=1:
            raise RuntimeError('arm serial missing/occupied or owner check failed')
        native_write=serial.Serial.write
        def suppress_boot(port,data):
            if str(Path(str(port.port)).resolve())==str(Path('/dev/myserial').resolve()):
                return len(data)
            return native_write(port,data)
        serial.Serial.write=suppress_boot
        try:
            arm=Arm_Lib.Arm_Device(com='/dev/myserial')
        finally:
            serial.Serial.write=native_write
        action=load_vendor_action(config['vendor_single_file'],arm)
        def prepare():
            arm.Arm_serial_servo_write6_array([90,125,0,0,90,0],1000)
            time.sleep(1.2)
        grasp=action.single_garbage_grap
    frame_parser=FrameParser()
    def clear_input():
        frame_parser.buffer.clear()
        while True:
            try:incoming.get_nowait()
            except queue.Empty:break
        if serial_port:
            serial_port.reset_input_buffer()
    session=RemoteSession(client,prepare=prepare,play=BlockingPlayer(),grasp=grasp,
                           enable_motion=args.execute,clear_input=clear_input)
    try:
        if config.get('voice_source','serial_id')=='serial_id':
            import serial
            from serial.tools import list_ports
            device=Path('/dev/myspeech')
            if not device.exists() or device.resolve()==Path('/dev/myserial').resolve():
                raise RuntimeError('speech alias missing or aliases arm')
            ports=[p for p in list_ports.comports() if p.device==str(device.resolve())]
            if len(ports)!=1 or (ports[0].vid,ports[0].pid)!=(0x1a86,0x7522):
                raise RuntimeError('unexpected speech USB identity')
            if subprocess.run(['fuser',str(device)],capture_output=True).returncode!=1:
                raise RuntimeError('speech serial occupied')
            serial_port=serial.Serial(str(device),115200,timeout=.05,exclusive=True)
        def receive():
            try:
                while not stop.is_set():
                    with session.lock:generation=session.generation
                    if serial_port:
                        raw_data=serial_port.read(min(max(serial_port.in_waiting,1),4096))
                        events=[]
                    else:
                        event=client.voice_event()
                        events=[]
                        if event:
                            kind=event['command']
                            if kind in ('cancel','stop'):
                                session.request_stop()
                                stop.set()
                                continue
                            events=[(event['wake_id'],event['legacy_command_id'],'usb_pcm_pl')]
                        stop.wait(.1)
                    with session.lock:
                        if session.busy or generation!=session.generation:
                            frame_parser.buffer.clear()
                            continue
                        if serial_port:
                            events=frame_parser.feed(raw_data)
                        for event in events:
                            try:incoming.put_nowait((event,time.monotonic(),generation))
                            except queue.Full:session.event('input_dropped_queue_full')
            except Exception as exc:
                session.fail('voice_input: '+str(exc))
                stop.set()
        reader=threading.Thread(target=receive,daemon=True)
        reader.start()
        def request_stop(signum,frame):
            session.request_stop()
            stop.set()
        for signum in (signal.SIGINT,signal.SIGTERM):
            handlers[signum]=signal.signal(signum,request_stop)
        while not stop.is_set():
            try:event,stamp,generation=incoming.get(timeout=.1)
            except queue.Empty:continue
            session.handle(*event,received_at=stamp,generation=generation)
    finally:
        stop.set()
        session.request_stop()
        try:
            client.cancel()
        finally:
            if serial_port:serial_port.close()
            if reader:reader.join(timeout=2)
            if arm and getattr(arm,'ser',None):arm.ser.close()
            for signum,handler in handlers.items():signal.signal(signum,handler)
            lock.close()


if __name__=='__main__':
    main()
