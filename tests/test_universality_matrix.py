"""Regression profiles from the v0.3.8 universality audit.

These test os-release and PATH *fixtures*, not real distro desktops; no
host installation/upgrade/removal is performed by this suite.
"""
import re
import unittest
from distro_support import detect_profile, native_recipe, parse_os_release

TOOLS = frozenset(('apt','apt-cache','dnf','dnf5','pacman','zypper',
                   'rpm-ostree','sudo','flatpak','snap',
                   'transactional-update','rpm','ujust'))


def profile(raw, installed=TOOLS, *, sandbox=False):
    return detect_profile(
        release=parse_os_release(raw),
        which=lambda name: '/usr/bin/' + name if name in installed else None,
        exists=lambda path: sandbox and path == '/.flatpak-info',
        environ={'XDG_CURRENT_DESKTOP': 'KDE'},
    )


def proposed_install(profile_value):
    try:
        return native_recipe(profile_value, 'install', 'testpackage')
    except ValueError:
        return None


class DistroMatrixTests(unittest.TestCase):
    """Each fingerprint is a separate discoverable unittest."""


CASES = [('Debian 13', 'ID=debian\nVERSION_ID=13', 'debian', 'apt', False), ('Ubuntu 24.04', 'ID=ubuntu\nID_LIKE=debian', 'debian', 'apt', False), ('Xubuntu', 'ID=ubuntu\nID_LIKE=debian\nVARIANT_ID=xubuntu', 'debian', 'apt', False), ('Kubuntu', 'ID=ubuntu\nID_LIKE=debian\nVARIANT_ID=kubuntu', 'debian', 'apt', False), ('Linux Mint', 'ID=linuxmint\nID_LIKE="ubuntu debian"', 'debian', 'apt', False), ('Pop!_OS', 'ID=pop\nID_LIKE="ubuntu debian"', 'debian', 'apt', False), ('KDE neon', 'ID=neon\nID_LIKE="ubuntu debian"', 'debian', 'apt', False), ('Zorin', 'ID=zorin\nID_LIKE=ubuntu', 'debian', 'apt', False), ('Debian-like custom', 'ID=debianfork\nID_LIKE=debian', 'debian', 'apt', False), ('Fedora Workstation', 'ID=fedora\nVARIANT_ID=workstation', 'fedora', 'dnf', False), ('Fedora KDE Spin', 'ID=fedora\nVARIANT_ID=kde', 'fedora', 'dnf', False), ('Nobara', 'ID=nobara\nID_LIKE=fedora', 'fedora', 'dnf', False), ('Rocky Linux', 'ID=rocky\nID_LIKE="rhel centos fedora"', 'fedora', 'dnf', False), ('RHEL', 'ID=rhel\nID_LIKE=fedora', 'fedora', 'dnf', False), ('CentOS Stream', 'ID=centos\nID_LIKE="rhel fedora"', 'fedora', 'dnf', False), ('Bazzite', 'ID=bazzite\nID_LIKE=fedora\nVARIANT_ID=bazzite', 'fedora', 'rpm-ostree', True), ('Bluefin', 'ID=bluefin\nID_LIKE=fedora\nVARIANT_ID=bluefin-dx-nvidia', 'fedora', 'rpm-ostree', True), ('Fedora Silverblue', 'ID=fedora\nID_LIKE=fedora\nVARIANT_ID=silverblue', 'fedora', 'rpm-ostree', True), ('Fedora Kinoite', 'ID=fedora\nID_LIKE=fedora\nVARIANT_ID=kinoite', 'fedora', 'rpm-ostree', True), ('Arch Linux', 'ID=arch\nID_LIKE=archlinux', 'arch', 'pacman', False), ('Manjaro', 'ID=manjaro\nID_LIKE=arch', 'arch', 'pacman', False), ('EndeavourOS', 'ID=endeavouros\nID_LIKE=arch', 'arch', 'pacman', False), ('CachyOS', 'ID=cachyos\nID_LIKE=arch', 'arch', 'pacman', False), ('Garuda', 'ID=garuda\nID_LIKE=arch', 'arch', 'pacman', False), ('SteamOS 3', 'ID=steamos\nID_LIKE=arch', 'arch', 'pacman', True), ('openSUSE Leap', 'ID=opensuse-leap\nID_LIKE="suse opensuse"', 'suse', 'zypper', False), ('openSUSE Tumbleweed', 'ID=opensuse-tumbleweed\nID_LIKE="suse opensuse"', 'suse', 'zypper', False), ('openSUSE MicroOS', 'ID=opensuse-microos\nID_LIKE="suse opensuse"', 'suse', 'zypper', True), ('openSUSE Aeon', 'ID=aeon\nID_LIKE="suse opensuse"', 'suse', 'zypper', True), ('openSUSE Kalpa', 'ID=kalpa\nID_LIKE="suse opensuse"', 'suse', 'zypper', True), ('SLES regular', 'ID=sles\nID_LIKE="suse opensuse"\nVARIANT_ID=server', 'suse', 'zypper', False), ('SLES immutable', 'ID=sles\nID_LIKE="suse opensuse"\nVARIANT_ID=transactional', 'suse', 'zypper', True), ('SLES for SAP immutable', 'ID=sles\nID_LIKE="suse opensuse"\nVARIANT_ID=server-sap-transactional', 'suse', 'zypper', True), ('SUSE derivative (ID_LIKE=suse)', 'ID=susefork\nID_LIKE=suse', 'suse', 'zypper', False), ('Unknown derivative Fedora', 'ID=customfed\nID_LIKE=fedora', 'fedora', 'dnf', False), ('Unknown distribution', 'ID=unknownlinux', 'unknown', 'none', False), ('Alpine (unsupported native)', 'ID=alpine', 'unknown', 'none', False), ('Gentoo (unsupported native)', 'ID=gentoo', 'unknown', 'none', False), ('NixOS (unsupported native)', 'ID=nixos', 'unknown', 'none', False), ('Void (unsupported native)', 'ID=void', 'unknown', 'none', False)]

def _make_distro_test(title, raw, family, backend, atomic):
    def test(self):
        p = profile(raw)
        self.assertEqual((p.family, p.backend, p.atomic),
                         (family, backend, atomic), title)
        self.assertEqual(bool(proposed_install(p)),
                         not atomic and backend not in ('none', 'rpm-ostree'), title)
        if atomic:
            self.assertIsNone(proposed_install(p))
    return test


for index, case in enumerate(CASES, start=1):
    setattr(DistroMatrixTests,
            'test_%02d_%s' % (index, re.sub(r'[^a-z0-9]+', '_', case[0].lower()).strip('_')),
            _make_distro_test(*case))


class AdditionalSafetyMatrixTests(unittest.TestCase):
    """Sixteen non-mutating safety transitions from the original audit."""


def _make_sandbox_test(distro, action):
    def test(self):
        p = profile('ID='+distro, sandbox=True)
        if action == 'install':
            self.assertIsNone(proposed_install(p))
        else:
            self.assertFalse(native_recipe(p, 'search', 'vim').changes)
    return test


def _make_foreign_manager_test(distro, installed):
    def test(self):
        p = profile('ID='+distro, installed=installed)
        self.assertEqual(p.backend, 'none')
        self.assertIsNone(proposed_install(p))
    return test


def _make_shell_injection_test(distro):
    def test(self):
        p = profile('ID='+distro)
        with self.assertRaises(ValueError):
            native_recipe(p, 'install', 'pkg;rm -rf /')
    return test


for distro in ('ubuntu','fedora','arch','opensuse-leap'):
    for action in ('install', 'search'):
        setattr(AdditionalSafetyMatrixTests, 'test_sandbox_'+distro.replace('-', '_')+'_'+action,
                _make_sandbox_test(distro, action))

for distro, installed in (('ubuntu', frozenset()), ('fedora', {'apt'}),
                          ('opensuse-leap', {'pacman'}), ('arch', {'dnf'})):
    setattr(AdditionalSafetyMatrixTests, 'test_foreign_'+distro.replace('-', '_'),
            _make_foreign_manager_test(distro, installed))

for distro in ('ubuntu','fedora','arch','opensuse-leap'):
    setattr(AdditionalSafetyMatrixTests, 'test_injection_'+distro.replace('-', '_'),
            _make_shell_injection_test(distro))


class SpecificRegressionTests(unittest.TestCase):
    def test_steamos_does_not_become_ostree_even_if_binary_is_available(self):
        p = profile('ID=steamos\nID_LIKE=arch')
        self.assertEqual(p.backend, 'pacman')
        self.assertTrue(p.atomic)
        self.assertFalse(p.transactional)
        self.assertEqual(native_recipe(p, 'installed').argv, ('pacman', '-Qe'))
        with self.assertRaisesRegex(ValueError, 'SteamOS'):
            native_recipe(p, 'updates')

    def test_steamos_excludes_mutating_composition_engine_rules(self):
        from composition_engine import default_engine, register_native_rules
        p = profile('ID=steamos\nID_LIKE=arch')
        engine = register_native_rules(default_engine(), p)
        self.assertNotIn('package.install', engine.rules)
        self.assertNotIn('package.remove', engine.rules)

    def test_transactional_suse_variants_including_sap(self):
        for variant in ('transactional','server-sap-transactional',
                        'custom-transactional'):
            with self.subTest(variant=variant):
                p = profile('ID=sles\nID_LIKE="suse opensuse"\nVARIANT_ID='+variant)
                self.assertTrue(p.transactional)
                self.assertEqual(p.backend,'zypper')
                self.assertIsNone(proposed_install(p))

    def test_old_and_new_suse_micro_product_ids(self):
        for ident in ('sl-micro','sle-micro'):
            with self.subTest(ident=ident):
                p = profile('ID='+ident+'\nID_LIKE="suse opensuse"')
                self.assertEqual((p.family,p.backend,p.atomic,p.transactional),
                                 ('suse','zypper',True,True))
                self.assertIsNone(proposed_install(p))

    def test_steamos_catalog_does_not_offer_pacman_update_as_os_update(self):
        from unittest.mock import patch
        from core import catalog
        p = profile('ID=steamos\nID_LIKE=arch')
        with patch('core.detect_profile', return_value=p), \
                patch('core.detect', return_value={'bazzite': False}):
            rows = catalog()
        labels = [cmd.title for category, cmd in rows if category == 'Native packages']
        self.assertIn('Installed native packages', labels)
        self.assertNotIn('Check native package updates', labels)

    def test_unknown_suse_derivative_respects_actual_zypper_presence(self):
        raw = 'ID=susefork\nID_LIKE=suse'
        p = profile(raw)
        self.assertEqual((p.family,p.backend,p.atomic), ('suse','zypper',False))
        absent = profile(raw, installed={'pacman','apt'})
        self.assertEqual((absent.family,absent.backend), ('suse','none'))
        self.assertIsNone(proposed_install(absent))


if __name__ == '__main__':
    unittest.main()
