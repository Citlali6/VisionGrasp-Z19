"""Ensure the vendor's pure IK service is ready; never opens camera or arm."""
from pathlib import Path
import fcntl,json,os,subprocess,time

ROOT=Path(__file__).resolve().parent
SERVER='/home/yahboom/dofbot_ws/install/dofbot_info/lib/dofbot_info/dofbot_server'

def matching_servers(domain):
    found=[]
    for item in Path('/proc').iterdir():
        if not item.name.isdigit():continue
        try:
            cmd=(item/'cmdline').read_bytes().split(b'\0')
            if not cmd or cmd[0].decode()!=SERVER:continue
            env=dict(x.split('=',1) for x in (item/'environ').read_bytes().decode().split('\0') if '=' in x)
            if env.get('ROS_DOMAIN_ID','0')==domain:found.append(int(item.name))
        except (OSError,ValueError,UnicodeError):continue
    return found

def main():
    records=ROOT/'records';records.mkdir(exist_ok=True)
    with (records/'kinematics-launch.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        import rclpy
        from dofbot_interface.srv import Kinemarics
        rclpy.init()
        node=rclpy.create_node('voice_startup_probe_'+str(os.getpid()))
        client=node.create_client(Kinemarics,'/dofbot_kinemarics')
        child=None
        result={'checked_at':time.time(),'domain':os.environ.get('ROS_DOMAIN_ID','0'),
                'service':'/dofbot_kinemarics','started_server':False}
        try:
            if client.wait_for_service(timeout_sec=1.5):
                result['ready']=True
            else:
                candidates=matching_servers(result['domain'])
                result['existing_pids']=candidates
                if not candidates:
                    if not Path(SERVER).is_file():raise RuntimeError('缺少官方逆解服务程序：'+SERVER)
                    with (records/'kinematics.log').open('ab',buffering=0) as log:
                        child=subprocess.Popen([SERVER],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
                    result.update(started_server=True,pid=child.pid)
                result['ready']=client.wait_for_service(timeout_sec=15)
                if not result['ready']:
                    raise RuntimeError('官方逆解服务未就绪，请查看 records/kinematics.log；未打开机械臂或相机。')
            print('官方逆解服务已就绪。',flush=True)
        except Exception as exc:
            result['error']=str(exc)
            if child is not None and child.poll() is None:
                child.terminate()
                try:child.wait(timeout=3)
                except subprocess.TimeoutExpired:child.kill();child.wait(timeout=3)
            raise
        finally:
            (records/'kinematics-ready.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
            node.destroy_node();rclpy.shutdown()

if __name__=='__main__':main()
