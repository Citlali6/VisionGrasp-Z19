import ast
import hashlib
import json
from pathlib import Path
import unittest

from voice_bridge import FrameParser, SINGLE_AUDIO, SINGLE_CLASSES

SOURCE = Path(__file__).resolve().parents[2]/'robot/dofbot'


def canonical(node):
    if isinstance(node, ast.AST):
        return {'node': type(node).__name__, **{key: canonical(value) for key, value in ast.iter_fields(node)
                if key not in ('type_params', 'type_comment') or value}}
    if isinstance(node, list):
        return [canonical(item) for item in node]
    if isinstance(node, bytes):
        return {'bytes': node.hex()}
    return node


class ProtocolTests(unittest.TestCase):
    def test_extracted_definitions_match_validated_ast(self):
        manifest = json.loads((SOURCE/'deployment_manifest.json').read_text(encoding='utf-8'))
        expected = manifest['transformations']['voice_bridge.py']['definitions_ast_sha256']
        source = (SOURCE/'voice_bridge.py').read_text(encoding='utf-8')
        tree = ast.parse(source)
        definitions = {}
        source_hashes = {}
        for node in tree.body:
            name = node.name if isinstance(node, ast.ClassDef) else node.targets[0].id if isinstance(node, ast.Assign) else None
            if name in expected:
                definitions[name] = hashlib.sha256(json.dumps(canonical(node), sort_keys=True, separators=(',', ':')).encode()).hexdigest()
                source_hashes[name] = hashlib.sha256(ast.get_source_segment(source, node).replace('\r\n', '\n').encode()).hexdigest()
        self.assertEqual(definitions, expected)
        self.assertEqual(source_hashes, manifest['transformations']['voice_bridge.py']['definitions_source_sha256'])
        self.assertEqual([n.name for n in tree.body if isinstance(n, ast.ClassDef)], ['FrameParser'])

    def test_split_and_combined_frames_keep_wake_and_both_start_aliases(self):
        data = bytes.fromhex('aa550100fbaa55005cfbaa55006cfb')
        expected = [(1, 0, 'aa550100fb'), (0, 92, 'aa55005cfb'), (0, 108, 'aa55006cfb')]
        for split in range(len(data)+1):
            parser = FrameParser()
            self.assertEqual(parser.feed(data[:split])+parser.feed(data[split:]), expected)

    def test_corrupt_noise_is_discarded_without_losing_following_wake(self):
        parser = FrameParser()
        self.assertEqual(parser.feed(bytes.fromhex('001122aa550700fbaa55015cfbaa550100eeaa')), [])
        self.assertEqual(parser.feed(bytes.fromhex('550100fb')), [(1, 0, 'aa550100fb')])

    def test_all_sixteen_labels_have_expected_audio_ids(self):
        self.assertEqual(len(SINGLE_CLASSES), 16)
        self.assertEqual(set(SINGLE_AUDIO), set(SINGLE_CLASSES))
        self.assertEqual(set(SINGLE_AUDIO.values()), set(range(94, 110)))
        self.assertEqual({x[1] for x in SINGLE_CLASSES.values()}, {'01', '02', '03', '04'})


if __name__ == '__main__':
    unittest.main()
