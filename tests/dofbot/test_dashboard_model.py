import json,os,tempfile,unittest
from pathlib import Path
from dashboard_model import load_view

class DisplayEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve();self.records=self.root/'records';self.records.mkdir()
        self.proc=self.root/'proc';(self.proc/'12').mkdir(parents=True)
        (self.proc/'stat').write_text('btime 900\n')
        hz=os.sysconf('SC_CLK_TCK') if hasattr(os,'sysconf') else 100
        fields=['S','1']+['0']*18;fields[19]=str(100*hz)
        (self.proc/'12/stat').write_text('12 (python3) '+' '.join(fields))
        (self.proc/'12/cmdline').write_bytes(('\0'.join(['/usr/bin/python3','-B',str(self.root/'standalone_runtime.py'),'--execute'])+'\0').encode())
        self.preview=self.root/'preview';self.preview.mkdir();(self.preview/'latest.jpg').write_bytes(b'jpeg')
        self.boot={'pid':12,'started_at':1000,'preview_dir':str(self.preview)}
        self.status={'state':'waiting_wake','busy':False,'cycles':0,'grasp_calls':0,'events':[]}
        self.live={'pid':12,'session_started_at':1000,'updated_at':1050,'frame_at':1049.8,'sequence':10,'image_sequence':10,'active':True,'camera_live':True}
    def view(self):
        for path,value in [(self.records/'bootstrap.json',self.boot),(self.records/'status.json',self.status),(self.preview/'live.json',self.live)]:
            path.write_text(json.dumps(value));os.utime(path,(1050,1050))
        return load_view(self.root,now=1050,proc=self.proc)
    def test_current_fresh_frame_is_live(self):self.assertTrue(self.view()['camera_live'])
    def test_failed_new_image_cannot_relabel_old_jpeg_live(self):
        self.live.update(sequence=11,image_sequence=10,camera_live=False,preview_error='encoding failed')
        self.assertFalse(self.view()['camera_live'])
    def test_stale_frame_is_offline(self):
        self.live['frame_at']=1047;self.assertFalse(self.view()['camera_live'])
    def test_old_runtime_generation_is_rejected(self):
        self.live['session_started_at']=999;self.assertFalse(self.view()['camera_live'])
    def test_process_reuse_is_rejected(self):
        self.boot['started_at']=500;self.assertFalse(self.view()['online'])
    def test_expired_wake_returns_waiting_wake(self):
        self.status.update(state='waiting_start',events=[{'event':'wake_received','at':1020}])
        self.assertEqual(self.view()['state'],'waiting_wake')
    def test_candidate_is_not_a_confirmed_classification(self):
        self.status.update(state='recognizing',labelChinese='易拉罐',category='01',events=[{'event':'start_accepted','at':1049}])
        self.assertFalse(self.view()['confirmed']);self.assertIsNone(self.view()['category'])
    def test_new_cycle_drops_previous_confirmation(self):
        self.status.update(state='recognizing',labelChinese='易拉罐',category='01',events=[{'event':'announcing','at':1040},{'event':'start_accepted','at':1049}])
        self.assertFalse(self.view()['confirmed'])
    def test_official_broadcast_text_is_displayed(self):
        self.status['events']=[{'event':'announcing','at':1049,'audio_id':102}]
        self.assertIn('这是鱼骨，属于湿垃圾',self.view()['timeline'][0]['text'])

if __name__=='__main__':unittest.main()
