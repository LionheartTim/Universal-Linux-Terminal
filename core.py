"""Command construction: no GUI, no mutations."""
import os
import re
import shlex
import shutil
import json
import pwd
from pathlib import Path
from dataclasses import dataclass
from distro_support import detect_profile, native_recipe
from host_bridge import in_flatpak, account_shell, host_which

@dataclass
class Command:
    title: str
    argv: list
    explanation: str
    changes: bool = False
    cwd: str = str(Path.home())

    @property
    def preview(self):
        return shlex.join(self.argv)

def user_shell():
    """Use the account login shell; fall back to an installed POSIX shell."""
    if in_flatpak():
        return account_shell()
    try:
        login_shell = pwd.getpwuid(os.getuid()).pw_shell
    except KeyError:
        login_shell = ''
    candidates = (login_shell, os.environ.get('SHELL', ''),
                  shutil.which('bash'), shutil.which('sh'),
                  '/bin/bash', '/bin/sh')
    for shell in candidates:
        if (shell and Path(shell).is_file() and os.access(shell, os.X_OK)
                and Path(shell).name not in ('false', 'nologin')):
            return shell
    raise RuntimeError('Geen uitvoerbare Linux-shell gevonden.')

def validate_text(value):
    if not value or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValueError('Vul tekst in zonder besturingstekens of nieuwe regels.')
    return value

def scope_option(scope):
    if scope in ('user', 'system'): return '--'+scope
    if re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.-]*', scope): return '--installation='+scope
    raise ValueError('Ongeldige Flatpak-installatie.')

def flatpak_action(action, ref, scope):
    if not re.fullmatch(r'app/[A-Za-z_][A-Za-z0-9_.-]*/[A-Za-z0-9_]+/[A-Za-z0-9_.-]+', ref):
        raise ValueError('Ongeldige volledige Flatpak-ref.')
    descriptions = {'uninstall':'Verwijdert uitsluitend deze app/branch/installatie; appgegevens blijven behouden.',
                    'update':'Werkt deze specifieke app bij vanuit de bestaande installatiebron.',
                    'info':'Toont informatie over deze specifieke installatie.',
                    'permissions':'Toont de gedeclareerde rechten van deze app.'}
    if action not in descriptions: raise ValueError('Onbekende Flatpak-actie.')
    argv = ['flatpak', 'info' if action == 'permissions' else action, scope_option(scope)]
    if action == 'permissions': argv.append('--show-permissions')
    argv.append(ref)
    return Command('Flatpak: '+action, argv, descriptions[action], action in ('uninstall','update'))

def parse_apps(text):
    rows = []
    for line in text.splitlines():
        cells = line.split('\t')
        if not line.strip(): continue
        if len(cells) != 5: raise ValueError('Onverwacht Flatpak-lijstformaat; er wordt geen actie voorbereid.')
        ref, name, version, origin, scope = cells
        if not ref.startswith('app/'): ref = 'app/'+ref
        flatpak_action('info', ref, scope)
        rows.append((name or ref.split('/')[1], ref, version, origin, scope))
    return rows

def manifest_info(filename):
    path = Path(filename)
    if path.stat().st_size > 2_000_000: raise ValueError('Manifest is te groot.')
    text = path.read_text()
    if path.suffix == '.json':
        data = json.loads(text)
    else:
        try: import yaml
        except ImportError: raise ValueError('Voor YAML-uitlezen is python3-pyyaml nodig; bouwen blijft mogelijk.')
        data = yaml.safe_load(text)
    if not isinstance(data, dict): raise ValueError('Manifest moet een object zijn.')
    return {key: str(data.get(key, '')) for key in ('app-id','id','runtime','runtime-version','sdk','branch')}

def parameter_command(kind, value, extra=''):
    value = validate_text(value.strip())
    if kind == 'search':
        return Command('Flatpak zoeken', ['flatpak','search','--',value], 'Zoekt in de ingestelde Flatpak-bronnen.')
    if kind == 'install':
        if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.-]*',value) or not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.-]*',extra):
            raise ValueError('Vul een app-ID en een bestaande bronnaam in.')
        return Command('Flatpak installeren', ['flatpak','install','--user',extra,value], 'Installeert voor de huidige gebruiker vanuit de gekozen bron.', True)
    if kind == 'ping':
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.:%_-]*',value): raise ValueError('Vul een hostnaam of IP-adres in.')
        return Command('Verbinding testen', ['ping','-c','4','-W','3',value], 'Stuurt vier pingverzoeken; sommige servers blokkeren ping.')
    if kind in ('service','logs'):
        if not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.@:-]*',value): raise ValueError('Ongeldige servicenaam.')
        argv = ['systemctl','--no-pager','status',value] if kind == 'service' else ['journalctl','--no-pager','-n','200','-u',value]
        return Command('Service '+value, argv, 'Bekijkt systeemstatus of recente logs; verandert niets.')
    if kind == 'hash':
        path = Path(value).expanduser().resolve()
        if not path.is_file(): raise ValueError('Kies een bestaand bestand.')
        return Command('SHA256 berekenen',['sha256sum','--',str(path)], 'Berekent de SHA256-controlesom.')
    if kind == 'container':
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*',value): raise ValueError('Ongeldige containernaam.')
        return Command('Containerterminal', ['distrobox','enter','--name',value], 'Opent een interactieve shell in deze bestaande container. Sluit met exit.')
    raise ValueError('Onbekende functie.')

def detect():
    """Compatibility mapping; the detailed profile lives in distro_support."""
    profile = detect_profile()
    return {'ID': profile.ident, 'PRETTY_NAME': profile.name,
            'VERSION_ID': profile.version, 'family': profile.family,
            'backend': profile.backend, 'atomic': profile.atomic,
            'desktop': profile.desktop, 'bazzite': profile.ident == 'bazzite',
            'sandbox': profile.sandbox}


def native_command(action, package=None, profile=None):
    """Translate a detected native recipe into the existing Command model."""
    recipe = native_recipe(profile or detect_profile(), action, package)
    return Command(recipe.title, list(recipe.argv), recipe.description, recipe.changes)

def app_remove(app_id, scope):
    if scope not in ('user', 'system') or not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.-]*', app_id):
        raise ValueError('Ongeldige app of installatiebron.')
    return Command('Flatpak verwijderen', ['flatpak', 'uninstall', '--'+scope, app_id],
                   'Verwijdert deze installatie. Flatpak vraagt nog om bevestiging. Appgegevens worden niet expliciet gewist.', True)

def bundle(repo, output, app_id, branch):
    repo = str(Path(repo).expanduser().resolve())
    output = str(Path(output).expanduser().resolve())
    if not Path(repo, 'config').is_file() or not Path(repo, 'objects').is_dir():
        raise ValueError('Kies een gebouwde OSTree-repository (met config en objects), niet alleen een projectmap.')
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_-]*(\.[A-Za-z_][A-Za-z0-9_-]*){2,}', app_id):
        raise ValueError('Vul een geldige app-ID in, bijvoorbeeld io.github.naam.App.')
    if not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.-]*', branch):
        raise ValueError('Ongeldige branch.')
    if not Path(output).parent.is_dir() or Path(output).exists():
        raise ValueError('Kies een bestaand uitvoerpad met een nieuwe bestandsnaam.')
    return Command('Flatpak-bundle maken', ['flatpak', 'build-bundle', repo, output, app_id, branch],
                   'Exporteert een al gebouwde app uit de lokale repository. Bouwt geen broncode.', True)

def build(project, manifest, repo, builddir=None):
    project = Path(project).expanduser().resolve()
    manifest = Path(manifest).expanduser().resolve()
    if not project.is_dir() or not manifest.is_file() or manifest.suffix not in ('.json', '.yaml', '.yml'):
        raise ValueError('Kies een projectmap en een bestaand JSON/YAML-manifest.')
    if not manifest.is_relative_to(project):
        raise ValueError('Het manifest moet binnen de projectmap staan.')
    target = Path(builddir).resolve() if builddir else project / 'ult-build'
    if not target.is_relative_to(project) or target == project:
        raise ValueError('De buildmap moet een nieuwe submap van het project zijn.')
    if target.exists():
        raise ValueError('ult-build bestaat al. Gebruik een nieuwe projectkopie of beheer deze map eerst zelf.')
    repo = str(Path(repo).expanduser().resolve())
    return Command('Flatpak-project bouwen', ['flatpak-builder', '--user', '--repo='+repo, str(target), str(manifest)],
                   'Bouwt naar '+str(target)+' en exporteert naar de repository. Runtime/SDK moeten al aanwezig zijn. Een manifest kan scripts uitvoeren: gebruik vertrouwde broncode.', True, str(project))

def catalog():
    rows = [
        ('Systeem', 'USB-apparaten', ['lsusb'], 'Verbonden USB-apparaten bekijken.', False),
        ('Systeem', 'PCI-apparaten en drivers', ['lspci', '-k'], 'PCI-apparaten met actieve kernelmodules.', False),
        ('Systeem', 'Opstarttijd', ['systemd-analyze'], 'Tijd die het systeem nodig had om op te starten.', False),
        ('Flatpak', 'Actieve Flatpak-processen', ['flatpak', 'ps'], 'Lopende Flatpak-apps bekijken.', False),
        ('Flatpak', 'Installatiegeschiedenis', ['flatpak', 'history'], 'Installaties en updates bekijken.', False),
        ('Flatpak', 'Ongebruikte gebruikersruntimes opruimen', ['flatpak', 'uninstall', '--user', '--unused'], 'Toont ongebruikte onderdelen en vraagt bevestiging voordat ze worden verwijderd.', True),
        ('Flatpak', 'Gebruikersinstallatie controleren', ['flatpak', 'repair', '--user', '--dry-run'], 'Controleert de gebruikersinstallatie zonder reparaties toe te passen.', False),
        ('Netwerk', 'Netwerkroutes', ['ip', 'route'], 'Routes en standaardgateway bekijken.', False),
        ('Netwerk', 'Luisterende poorten', ['ss', '-tuln'], 'Lokale TCP- en UDP-luisterpoorten bekijken.', False),
        ('Diagnose', 'Vorige boot: waarschuwingen', ['journalctl', '-b', '-1', '-p', 'warning', '--no-pager', '-n', '200'], 'Waarschuwingen van de vorige boot, indien bewaard.', False),
        ('Diagnose', 'Audio-apparaten', ['wpctl', 'status'], 'PipeWire/WirePlumber-audioapparaten bekijken.', False),
        ('Systeem', 'Systeeminformatie', ['uname', '-a'], 'Kernel en architectuur bekijken.', False),
        ('Systeem', 'Schijfruimte', ['df', '-h'], 'Vrije ruimte per aangekoppeld bestandssysteem.', False),
        ('Systeem', 'Schijven en partities', ['lsblk', '-f'], 'Schijven en bestandssystemen bekijken.', False),
        ('Systeem', 'Geheugen', ['free', '-h'], 'Geheugen- en swapgebruik bekijken.', False),
        ('Systeem', 'Processen', ['top'], 'Interactief procesoverzicht. Druk q om af te sluiten.', False),
        ('Flatpak', 'Geïnstalleerde apps', ['flatpak', 'list', '--app'], 'Alle Flatpak-apps bekijken.', False),
        ('Flatpak', 'Runtimes en SDK’s', ['flatpak', 'list', '--runtime'], 'Geïnstalleerde bouw- en uitvoeromgevingen.', False),
        ('Flatpak', 'Bronnen bekijken', ['flatpak', 'remotes', '--show-details'], 'Ingestelde Flatpak-bronnen.', False),
        ('Flatpak', 'Apps bijwerken', ['flatpak', 'update'], 'Updates bekijken en na bevestiging installeren.', True),
        ('Netwerk', 'IP-adressen', ['ip', '-brief', 'address'], 'Lokale interfaces en adressen.', False),
        ('Netwerk', 'Netwerkstatus', ['nmcli', 'device', 'status'], 'Status van NetworkManager-apparaten.', False),
        ('Netwerk', 'DNS-status', ['resolvectl', 'status'], 'DNS-configuratie bekijken.', False),
        ('Diagnose', 'Mislukte services', ['systemctl', '--failed'], 'Systeemservices met fouten.', False),
        ('Diagnose', 'Gebruikersservices met fouten', ['systemctl', '--user', '--failed'], 'Services in je gebruikerssessie.', False),
        ('Diagnose', 'Waarschuwingen huidige boot', ['journalctl', '-b', '-p', 'warning', '--no-pager', '-n', '200'], 'Laatste 200 waarschuwingen; toegang kan beperkt zijn.', False),
        ('Containers', 'Distrobox-overzicht', ['distrobox', 'list'], 'Geïnstalleerde Distrobox-containers.', False),
        ('Containers', 'Podman-overzicht', ['podman', 'ps', '-a'], 'Containers van de huidige gebruiker.', False),
        ('Homebrew', 'Pakketten bekijken', ['brew', 'list'], 'Geïnstalleerde Homebrew-pakketten.', False),
        ('Homebrew', 'Beschikbare updates', ['brew', 'outdated'], 'Verouderde Homebrew-pakketten.', False),
        ('Bazzite', 'Deployment-status', ['rpm-ostree', 'status'], 'Actieve, vorige en klaargezette systeemversies.', False),
        ('Bazzite', 'Beschikbare ujust-functies', ['ujust'], 'Opdrachten uit jouw geïnstalleerde Bazzite-versie.', False),
        ('Bazzite', 'Alles bijwerken', ['ujust', 'update'], 'Officiële Bazzite-updateprocedure. Een systeemupdate wordt na herstart actief.', True),
        ('Bazzite', 'Audio herstarten', ['ujust', 'restart-pipewire'], 'Onderbreekt audio en herstart PipeWire.', True),
    ]
    env = detect()
    results = [(group, Command(title, argv, desc, changes))
               for group, title, argv, desc, changes in rows
               if group != 'Bazzite' or env['bazzite']]
    profile = detect_profile()
    if profile.backend != 'none':
        for action, label in [('installed', 'Installed native packages'),
                              ('updates', 'Check native package updates')]:
            try:
                results.append(('Native packages', native_command(action, profile=profile)))
                results[-1][1].title = label
            except ValueError:
                continue
        if profile.backend == 'rpm-ostree':
            results.append(('Native packages', native_command('status', profile=profile)))
    return results

def availability(command):
    if detect()['sandbox'] and command.changes:
        return 'Systeemwijzigende commandohulp is in een container/sandbox geblokkeerd.'
    if command.argv[0] != 'cd' and not host_which(command.argv[0]):
        # The command browser also finds Bash builtins, which are never
        # independent executables on PATH. Only allow these for Bash.
        shell = Path(user_shell()).name
        if shell == 'bash':
            from command_discovery import installed_commands
            builtins = {entry.name for entry in installed_commands()
                        if entry.kind == 'bash builtin'}
            if command.argv[0] in builtins:
                return ''
        return 'Ontbrekend hulpmiddel: ' + command.argv[0]
    return ''


def terminal_line(command):
    for arg in command.argv:
        validate_text(arg)
    if command.argv[0] == 'flatpak-builder':
        validate_text(command.cwd)
        return 'cd -- '+shlex.quote(command.cwd)+' && '+command.preview
    return command.preview
