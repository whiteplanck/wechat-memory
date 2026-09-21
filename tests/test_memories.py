import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from wechat_memory.storage import ArchiveStore
from wechat_memory.memories import MemoryStore
from wechat_memory.relationships import RelationshipStore, build_report
from wechat_memory.bundles import create_bundle


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.archives=ArchiveStore(self.root/'archives')
        self.rows=[{"id":"1","conversation":"C","sender":"A","timestamp":"2026-01-01T10:00:00+08:00","text":"[语音]","type":"audio","media":["voice.wav"]},
                   {"id":"2","conversation":"C","sender":"B","timestamp":"2026-01-01T10:01:00+08:00","text":"合照","type":"image","media":[]}]
        self.id=self.archives.save(self.rows,'Test')['id'];self.store=MemoryStore(self.archives)

    def test_annotations_original_immutable_history_conflict(self):
        original=(self.archives.directory/(self.id+'.json')).read_bytes()
        data=self.store.annotate(self.id,'C','1',['小白'],'旅行','我很开心',0)
        self.assertEqual(data['revision'],1)
        with self.assertRaises(ValueError):self.store.annotate(self.id,'C','1',[],'','覆盖',0)
        data=self.store.annotate(self.id,'C','1',['小白'],'旅行','我很开心！',1)
        self.assertEqual(data['items'][0]['history'][-1]['transcript'],'我很开心')
        self.assertEqual(original,(self.archives.directory/(self.id+'.json')).read_bytes())
        self.assertIn('用户核对的语音转写',self.store.enriched(self.id)[0]['text'])
        self.assertEqual(MemoryStore(self.archives).view(self.id)['people'][0]['name'],'小白')
        self.assertEqual(len(self.store.view(self.id)['memories']),1)

    def test_speech_path_guard_and_missing_model(self):
        outside=self.root/'outside.wav';outside.write_bytes(b'RIFF')
        media=self.root/'media';media.mkdir()
        model=self.root/'model';model.mkdir()
        with self.assertRaises(ValueError):self.store.transcribe(self.id,'C','1',str(media),'../outside.wav',str(model))
        with self.assertRaises(ValueError):self.store.transcribe(self.id,'C','1',str(media),'voice.wav',str(model))
        self.assertEqual(self.store.load(self.id)['revision'],0)

    def test_bundle_v2_has_integrity_annotations_and_events(self):
        self.store.annotate(self.id,'C','1',['A'],'说明','你好',0)
        reports=RelationshipStore(self.archives.directory)
        report=build_report(self.store.enriched(self.id),'C');reports.create(report)
        bundle=Path(create_bundle(self.archives,self.id)['path'])
        self.assertEqual(json.loads((bundle/'annotations.json').read_text(encoding='utf-8'))['items'][0]['transcript'],'你好')
        self.assertEqual(len(json.loads((bundle/'relationships.json').read_text(encoding='utf-8'))['reports']),1)
        manifest=json.loads((bundle/'bundle-manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['schema'],'wechat-memory.bundle.v2')
        for file in manifest['files']:
            self.assertEqual(hashlib.sha256((bundle/file['path']).read_bytes()).hexdigest(),file['sha256'])
        self.assertNotIn('api_key',(bundle/'annotations.json').read_text(encoding='utf-8'))


if __name__=='__main__':unittest.main()
