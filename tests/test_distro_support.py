"""Pure multi-distro tests: no host package operations or GTK."""
import shlex
import unittest
from unittest.mock import patch
from distro_support import parse_os_release, detect_profile, native_recipe
from core import native_command

TOOLS = {'apt','apt-cache','dnf','dnf5','pacman','zypper','rpm-ostree',
         'flatpak','ujust','sudo','rpm','transactional-update'}


def profile(raw, installed=TOOLS, *, ostree=False, sandbox=False):
    paths = {'/run/ostree-booted'} if ostree else set()
    if sandbox: paths.add('/.flatpak-info')
    return detect_profile(release=parse_os_release(raw),
                          which=lambda name: '/usr/bin/' + name if name in installed else None,
                          exists=lambda path: path in paths,
                          environ={'XDG_CURRENT_DESKTOP':'KDE'})


class DetectionTests(unittest.TestCase):
    def test_parses_quoted_os_release_without_shell_execution(self):
        props = parse_os_release('''ID=ubuntu\nPRETTY_NAME="Ubuntu 24.04 LTS"\nID_LIKE="debian"\nVARIANT_ID=desktop\nBAD-KEY=ignored\n''')
        self.assertEqual(props['PRETTY_NAME'], 'Ubuntu 24.04 LTS')
        self.assertNotIn('BAD-KEY', props)

    def test_debian_family_derivatives(self):
        for ident, likes in [('debian',''),('ubuntu','debian'),('linuxmint','ubuntu debian'),
                             ('pop','ubuntu debian'),('neon','ubuntu debian')]:
            with self.subTest(ident=ident):
                p = profile(f'ID={ident}\nID_LIKE="{likes}"\n')
                self.assertEqual((p.family,p.backend,p.atomic),('debian','apt',False))

    def test_fedora_mutable_and_bazzite_atomic(self):
        p = profile('ID=fedora\nPRETTY_NAME="Fedora Linux 44"\n')
        self.assertEqual((p.backend,p.atomic),('dnf',False))
        p = profile('ID=bazzite\nID_LIKE="fedora"\n')
        self.assertEqual((p.backend,p.atomic),('rpm-ostree',True))
        with self.assertRaisesRegex(ValueError, 'Atomic'):
            native_recipe(p,'install','firefox')
        self.assertEqual(native_recipe(p,'updates').argv,('rpm-ostree','upgrade','--check'))
        p = profile('ID=fedora\nVARIANT_ID=silverblue\n', ostree=True, installed={'dnf','rpm-ostree'})
        self.assertEqual(p.backend,'rpm-ostree')

    def test_arch_derivatives(self):
        for ident in ('arch','manjaro','endeavouros','cachyos'):
            p=profile('ID='+ident)
            self.assertEqual(p.backend,'pacman')
            self.assertEqual(native_recipe(p,'updates').argv,('pacman','-Qu'))

    def test_suse_normal_vs_transactional(self):
        p=profile('ID=opensuse-tumbleweed\nID_LIKE="opensuse suse"\n')
        self.assertEqual((p.family,p.backend,p.atomic),('suse','zypper',False))
        p=profile('ID=opensuse-microos\nID_LIKE="opensuse suse"\n')
        self.assertTrue(p.transactional)
        with self.assertRaisesRegex(ValueError,'Atomic'):
            native_recipe(p,'remove','firefox')

    def test_missing_package_manager_is_not_fabricated(self):
        p=profile('ID=ubuntu\n',installed={'dnf','pacman'})
        self.assertEqual(p.backend,'none')
        with self.assertRaises(ValueError): native_recipe(p,'updates')
        p=profile('ID=unknown\n',installed={'apt','apt-cache'})
        self.assertEqual(p.backend,'none')

    def test_container_wont_stage_host_mutations(self):
        p=profile('ID=fedora\n', sandbox=True)
        self.assertTrue(p.sandbox)
        self.assertEqual(native_recipe(p,'search','firefox').argv,('dnf','search','firefox'))
        with self.assertRaisesRegex(ValueError,'containers'):
            native_recipe(p,'remove','firefox')

    def test_dnf5_fallback_and_no_sudo(self):
        p=profile('ID=fedora\n',installed={'dnf5'})
        self.assertEqual(native_recipe(p,'search','vim').argv,('dnf5','search','vim'))
        with self.assertRaisesRegex(ValueError,'sudo'):
            native_recipe(p,'install','vim')

    def test_safe_package_arguments_and_expected_backend(self):
        for ident, mgr, name in [('ubuntu','apt','firefox'),('fedora','dnf','vim'),
                                  ('arch','pacman','steam'),('opensuse-leap','zypper','krita')]:
            p = profile('ID='+ident)
            for action in ('search','info','installed','updates','install','remove'):
                with self.subTest(mgr=mgr,action=action):
                    cmd=native_command(action,name,p)
                    self.assertEqual(shlex.split(cmd.preview),cmd.argv)
                    self.assertEqual(cmd.changes,action in ('install','remove'))
            self.assertEqual(p.backend, mgr)

    def test_reject_shell_flags_and_injection(self):
        p=profile('ID=ubuntu')
        for name in ('--help','-r','x;touch /tmp/file','hello world','x\nrm',''):
            for action in ('search','install','remove'):
                with self.subTest(name=name,action=action), self.assertRaises(ValueError):
                    native_recipe(p,action,name)

    def test_existing_catalog_keeps_bazzite_filter(self):
        from core import catalog
        with patch('core.detect_profile',return_value=profile('ID=bazzite\n')):
            with patch('core.detect',return_value={'bazzite':True}):
                cats=[group for group,_ in catalog()]
                self.assertIn('Bazzite',cats)
                self.assertIn('Native packages',cats)
        with patch('core.detect_profile',return_value=profile('ID=debian\n')):
            with patch('core.detect',return_value={'bazzite':False}):
                self.assertNotIn('Bazzite',[g for g,_ in catalog()])


if __name__ == '__main__':
    unittest.main()

class NativeEngineTests(unittest.TestCase):
    def test_native_package_uses_existing_rule_engine(self):
        from composition_engine import default_engine, register_native_rules, Subject
        p=profile('ID=ubuntu')
        engine=register_native_rules(default_engine(),p)
        engine.choose(Subject('package','steam'))
        with patch('composition_engine.shutil.which',lambda _: '/usr/bin/apt-cache'):
            suggestions={s.key for s in engine.suggestions()}
            self.assertIn('package.info', suggestions)
            self.assertIn('package.search', suggestions)
            self.assertIn('package.install', suggestions)
            command, note=engine.compose('package.search')
            self.assertEqual(command.argv, ['apt-cache','search','steam'])
            self.assertFalse(command.changes)
            self.assertTrue(note)
        # Package context never silently combines with unrelated service context.
        engine.choose(Subject('service','NetworkManager'))
        self.assertNotIn('package',engine.selected)

    def test_atomic_profile_has_no_native_install_rule(self):
        from composition_engine import default_engine, register_native_rules, Subject
        engine=register_native_rules(default_engine(),profile('ID=bazzite'))
        self.assertFalse(any(k.startswith('package.') for k in engine.rules))
        p=profile('ID=ubuntu',sandbox=True)
        engine=register_native_rules(default_engine(),p)
        self.assertNotIn('package.install',engine.rules)
        for bad in ('--help','a;id','foo bar',''):
            with self.assertRaises(ValueError): Subject('package',bad)
