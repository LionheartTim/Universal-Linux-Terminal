"""Release icon smoke tests (do not require GTK or a display)."""
import unittest
from pathlib import Path
from PIL import Image
from app_icon import APP_ID, icon_fallback_path

ROOT = Path(__file__).resolve().parents[1]

class ApplicationIconTests(unittest.TestCase):
    def test_icon_name_matches_desktop_and_manifest(self):
        desk = (ROOT/'flatpak'/f'{APP_ID}.desktop').read_text()
        self.assertIn('Icon='+APP_ID+'\n', desk)
        self.assertIn('StartupWMClass='+APP_ID+'\n',desk)
        manifest = (ROOT/f'{APP_ID}.yml').read_text()
        self.assertIn('id: '+APP_ID,manifest)
        self.assertNotIn(f'{APP_ID}.svg', manifest)
        for size in (16,24,32,48,64,128,256,512):
            expected=f'flatpak/icons/{size}x{size}/{APP_ID}.png'
            self.assertIn(expected, manifest)
            data=(ROOT/expected).read_bytes()
            self.assertEqual(data[:8], bytes.fromhex('89504e470d0a1a0a'))
            from struct import unpack
            self.assertEqual(unpack('>II', data[16:24]), (size,size))
            self.assertEqual(data[25],6)  # RGBA PNG

    def test_window_app_id_set_before_initialization(self):
        source=(ROOT/'app.py').read_text()
        self.assertLess(source.index('configure_application_identity(Gtk, GLib, Gdk)'),
                        source.index('    window = Window()'))
        self.assertIn('apply_window_icon(self)',source)
        self.assertIsNotNone(icon_fallback_path())
        self.assertTrue((ROOT/'artwork'/'ULT-approved-original.png').exists())

if __name__ == '__main__':
    unittest.main()
