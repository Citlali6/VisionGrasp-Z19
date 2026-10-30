"""Isolated PS/PL VM records and the existing read-only dashboard widget.

Preview uses the PS capture side channel, never a local camera or detector.
Import/construction opens no device, process, output directory or Qt window.
"""
from pathlib import Path
import argparse
import hashlib
import json
import math
import os
import sys
import threading
import time

from preview_publisher import ArmObserver, PreviewPublisher


def runtime_root(path):
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        raise ValueError('runtime_root must be an explicit absolute directory')
    candidate = candidate.resolve()
    original = Path(__file__).resolve().parent
    legacy_records = (original/'records').resolve()
    legacy_preview = (Path('/run/user')/str(os.getuid())/'dofbot-voice-preview').resolve()
    destinations = [path.resolve() for path in
                    (candidate,candidate/'records',candidate/'preview',candidate/'sessions')]
    source_roots = [original]
    source_roots += [parent for parent in (original,*original.parents) if (parent/'.git').exists()]
    protected_roots = (legacy_records,legacy_preview,*source_roots)
    if any(path == protected or protected in path.parents
            for path in destinations for protected in protected_roots):
        raise ValueError('runtime output must be outside source/deployment directories and legacy records/preview')
    return candidate


def process_identity(proc=Path('/proc'), pid=None):
    pid = os.getpid() if pid is None else int(pid)
    directory = Path(proc)/str(pid)
    stat = (directory/'stat').read_text()
    fields = stat[stat.rfind(')')+2:].split()
    if fields[0] in ('Z', 'X'):
        raise RuntimeError('runtime process has exited')
    command = [part.decode() for part in (directory/'cmdline').read_bytes().split(b'\0') if part]
    return dict(pid=pid, start_ticks=int(fields[19]), command=command,
                python_executable=str((directory/'exe').resolve()),
                boot_id=(Path(proc)/'sys/kernel/random/boot_id').read_text().strip())


def pspl_runtime_alive(root, boot, proc=Path('/proc')):
    """Separate explicit identity policy; the legacy runtime predicate is intact."""
    try:
        root = Path(root).resolve()
        entry = Path(__file__).resolve().with_name('pspl_entry.py')
        if (boot.get('schema') != 'visiongrasp.pspl-vm-runtime/1' or boot.get('exited_at') or
                boot.get('runtime_root') != str(root) or boot.get('entry_script') != str(entry)):
            return False
        actual = process_identity(proc, boot['pid'])
        if any(actual[key] != boot.get(key) for key in
               ('pid', 'start_ticks', 'command', 'python_executable', 'boot_id')):
            return False
        command = actual['command']
        index = 2 if len(command)>1 and command[1]=='-B' else 1
        script = Path(command[index])
        if not script.is_absolute():
            script = (Path(proc)/str(actual['pid'])/'cwd').resolve()/script
        if script.resolve() != entry:
            return False
        from dashboard_model import read_json
        status = read_json(root/'records/status.json')
        return (status.get('pid') == actual['pid'] and
                status.get('runtime_session_id') == boot.get('runtime_session_id') and
                type(status.get('generation')) is int and status['generation'] >= 0)
    except (OSError, ValueError, TypeError, KeyError, IndexError, RuntimeError):
        return False


def load_pspl_view(root, now=None, proc=Path('/proc')):
    from dashboard_model import load_view, read_json
    view = load_view(root, now=now, proc=proc, runtime_check=pspl_runtime_alive)
    boot = read_json(Path(root)/'records/bootstrap.json')
    live = read_json(Path(boot.get('preview_dir') or Path(root)/'preview')/'live.json')
    if (not view.get('status_runtime_session_id') or
            live.get('runtime_session_id') != view.get('status_runtime_session_id') or
            boot.get('runtime_session_id') != view.get('status_runtime_session_id') or
            live.get('pid') != view.get('runtime_pid') or
            live.get('generation') != view.get('status_generation') or
            live.get('preview_source') != 'ps_camera_preview' or live.get('pl_processed') is not False):
        view.update(camera_live=False, image_key=None)
    view['camera_message'] = '等待 Z19 相机旁路画面' if view['online'] else '等待 PS/PL 任务程序连接'
    return view


class RemotePreviewPublisher(PreviewPublisher):
    def __init__(self, owner):
        self.owner = owner
        self.publish_lock = threading.RLock()
        self.pending_image_metadata = self.published_image_metadata = {}
        super().__init__(owner.preview, self._snapshot, pid=owner.boot['pid'],
                         session_started_at=owner.boot['started_at'], observer=owner.observer,
                         control_status_path=owner.records/'status.json')

    def _snapshot(self):
        value = self.owner.preview_snapshot()
        # Frame, source ID and generation came from the SAME locked cache read.
        # Encoding may overlap another remote frame or a Session transition.
        self.pending_image_metadata = dict(source=value['source'],generation=value['generation'])
        return value

    def _atomic(self, name, payload):
        super()._atomic(name,payload)
        if name=='latest.jpg':
            self.published_image_metadata = self.pending_image_metadata

    def publish_once(self):
        # Network polling uses a separate thread and never holds this lock.
        with self.publish_lock:
            return super().publish_once()

    def _metadata(self):
        value = super()._metadata()
        metadata = self.published_image_metadata
        value.update(runtime_session_id=self.owner.boot['runtime_session_id'],
                     generation=metadata.get('generation'),preview_source='ps_camera_preview',
                     pl_processed=False,source=dict(metadata.get('source',{})),
                     source_image_sequence=self.image_sequence)
        return value

    def close(self):
        self.stop_event.set()
        self.active = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=.5)
        try:
            with self.publish_lock:
                self._write_metadata()
        except Exception as exc:
            self.preview_error = repr(exc)[-1000:]


class RemoteDisplay:
    def __init__(self, directory, client, boot):
        self.root = runtime_root(directory)
        self.records, self.preview = self.root/'records', self.root/'preview'
        self.archive = self.root/'sessions'/boot['runtime_session_id']
        self.client, self.boot = client, boot
        self.observer = ArmObserver()
        self.lock = threading.RLock()
        self.stopping = threading.Event()
        self.thread = self.publisher = None
        self.generation = self.last_event_count = self.sequence = 0
        self.source = {}
        self.frame = self.frame_at = self.preview_error = None

    @staticmethod
    def atomic(path, payload):
        path = Path(path)
        temporary = path.with_name(path.name+'.%s.tmp'%os.getpid())
        with temporary.open('wb') as output:
            output.write(payload)
        temporary.replace(path)

    def write_json(self, path, value):
        self.atomic(path,json.dumps(value,ensure_ascii=False,allow_nan=False,indent=2).encode('utf-8'))

    def start(self):
        self.root.mkdir(parents=True,exist_ok=True)
        marker = self.root/'.pspl-runtime-output'
        if marker.exists():
            if marker.read_text(encoding='utf-8').strip() != 'visiongrasp.pspl-vm-output/1':
                raise RuntimeError('runtime_root belongs to an unknown output format')
        else:
            if any(self.root.iterdir()):
                raise RuntimeError('runtime_root must initially be empty or already owned by this entry')
            marker.write_text('visiongrasp.pspl-vm-output/1\n',encoding='utf-8')
        self.records.mkdir(exist_ok=True)
        self.archive.mkdir(parents=True,exist_ok=False)
        self.boot.update(schema='visiongrasp.pspl-vm-runtime/1',runtime_root=str(self.root),
                         preview_dir=str(self.preview),entry_script=str(Path(__file__).with_name('pspl_entry.py').resolve()))
        self.save_boot()
        self.publisher = RemotePreviewPublisher(self)
        if not self.publisher.start():
            self.boot['preview_error'] = self.publisher.preview_error
            self.save_boot()
        self.thread = threading.Thread(target=self._poll_preview,name='pspl-remote-display',daemon=True)
        self.thread.start()

    def save_boot(self):
        with self.lock:
            self.write_json(self.records/'bootstrap.json',self.boot)
            self.write_json(self.archive/'bootstrap.json',self.boot)

    def save(self, status):
        """Session's real event stream, with per-run archive and current UI view."""
        with self.lock:
            self.generation = status['generation']
            value = dict(status,pid=self.boot['pid'],runtime_session_id=self.boot['runtime_session_id'],
                         preview_source='ps_camera_preview',perception_source='Z19_PS_PL')
            self.write_json(self.records/'status.json',value)
            self.write_json(self.archive/'status.json',value)
            event_count = status['event_count']
            count = max(0,event_count-self.last_event_count)
            if count:
                with (self.archive/'events.jsonl').open('a',encoding='utf-8') as output:
                    for index,event in enumerate(status['events'][-count:]):
                        item = dict(event,pid=self.boot['pid'],runtime_session_id=self.boot['runtime_session_id'],
                                    generation=self.generation,event_count=event_count-count+index+1,
                                    ps_task_id=status.get('ps_task_id'),ps_session_id=status.get('ps_session_id'))
                        output.write(json.dumps(item,ensure_ascii=False,allow_nan=False)+'\n')
            self.last_event_count = event_count

    def recognized(self, frame, label, xy, cycle, result):
        import cv2
        okay,jpeg = cv2.imencode('.jpg',frame,[cv2.IMWRITE_JPEG_QUALITY,90])
        if not okay:
            raise RuntimeError('could not encode the received PS recognition image')
        payload = jpeg.tobytes()
        name = 'cycle-%03d-detection'%cycle
        evidence = {key:result.get(key) for key in
                    ('schema','camera_id','session_id','task_id','frame_id','transform_id','image_space',
                     'model_id','input_source','config_version','pl_frame_id','selection_policy',
                     'raw_reference','processed_reference',
                     'candidate','association','detections')}
        evidence.update(runtime_session_id=self.boot['runtime_session_id'],generation=self.generation,
                        label=label,legacy_stability_proxy=list(xy),image_source='received_ps_preview',
                        physical_grasp_verified=False,image_sha256=hashlib.sha256(payload).hexdigest())
        with self.lock:
            for directory in (self.records,self.archive):
                self.atomic(directory/(name+'.jpg'),payload)
                self.write_json(directory/(name+'.json'),evidence)
        return self.records/(name+'.jpg')

    def record_arm_write(self, stage, packet, written):
        item = dict(at=time.time(),stage=stage,hex=packet.hex(),written=written,
                    pid=self.boot['pid'],runtime_session_id=self.boot['runtime_session_id'],
                    generation=self.generation,evidence='serial_write_returned',complete=written==len(packet))
        with self.lock:
            with (self.archive/'arm-tx.jsonl').open('a',encoding='utf-8') as output:
                output.write(json.dumps(item,allow_nan=False)+'\n')

    def preview_snapshot(self):
        with self.lock:
            return dict(frame=None if self.frame is None else self.frame.copy(),sequence=self.sequence,
                        frame_at=self.frame_at,camera_error=self.preview_error,
                        source=dict(self.source),generation=self.generation)

    def _poll_preview(self):
        after = -1
        while not self.stopping.is_set():
            started = time.monotonic()
            try:
                result = self.client.preview(after)
                if result is not None:
                    stamp = result['captured_monotonic']  # constructed on THIS VM by the HTTP client
                    age = time.monotonic()-stamp
                    if not math.isfinite(age) or age<0:
                        raise RuntimeError('invalid VM preview age')
                    with self.lock:
                        after = result['sequence']
                        self.sequence += 1
                        self.frame = result['frame'].copy()
                        self.frame_at = time.time()-age
                        self.source = dict(camera_id=self.client.camera_id,session_id=result['session_id'],
                                           frame_id=after,source=result['source'])
                        self.preview_error = None
            except Exception as exc:
                with self.lock:
                    self.preview_error = str(exc)[-1000:]
            self.stopping.wait(max(0,.125-(time.monotonic()-started)))

    def close(self):
        self.stopping.set()
        if self.thread:
            self.thread.join(timeout=self.client.timeout_s+.5)
        if self.publisher:
            self.publisher.close()


def main():
    parser = argparse.ArgumentParser(description='Read-only dashboard for the isolated PS/PL entry')
    parser.add_argument('--runtime-root',required=True)
    args = parser.parse_args()
    directory = runtime_root(args.runtime_root)
    # Qt is loaded only by this explicit viewer entry. The original widget and
    # model keep their defaults; this window supplies its own process predicate.
    from PyQt5.QtCore import Qt, QLockFile
    from PyQt5.QtWidgets import QApplication
    from dashboard import Dashboard, font
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling,True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps,True)
    app = QApplication(sys.argv[:1])
    app.setFont(font(13))
    lock = QLockFile(str(directory/'records/pspl-dashboard.lock'))
    lock.setStaleLockTime(0)
    if not lock.tryLock(0):
        raise RuntimeError('this PS/PL output already has a dashboard instance')
    window = Dashboard(root=directory,view_loader=load_pspl_view)
    window.setWindowTitle('Z19 PS/PL · DOFBOT 分拣任务')
    window.show()
    try:
        return app.exec_()
    finally:
        lock.unlock()


if __name__=='__main__':
    raise SystemExit(main())
