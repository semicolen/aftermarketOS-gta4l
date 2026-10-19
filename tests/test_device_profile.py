from pathlib import Path
import unittest

from debport.profiles import import_deviceinfo, load


class DeviceProfile(unittest.TestCase):
    def test_boot_metadata_matches_pinned_original_port(self):
        repo = Path(__file__).resolve().parents[1]
        original = import_deviceinfo(repo / 'upstream/2gta4l/port/device-samsung-gta4l/deviceinfo')
        profile = load(str(repo / 'profiles/samsung-gta4l.json'))
        self.assertEqual(original['architecture'], profile['architecture'])
        self.assertEqual(original['boot'], profile['boot'])
