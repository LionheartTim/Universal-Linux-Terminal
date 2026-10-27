"""Built-in English/Dutch translations, with no external gettext dependency.

Source strings remain Dutch for compatibility with existing command builders.
English is the fallback for every other system language.  Only user-visible
labels and explanations pass through tr(); shell commands stay unchanged.
"""
import os


def preferred_language(environ=None):
    """Respect POSIX locale category precedence; no global locale mutation."""
    env = os.environ if environ is None else environ
    # LC_ALL always overrides all categories, including LANGUAGE.
    chosen = env.get('LC_ALL') or env.get('LC_MESSAGES')
    if not chosen:
        language_list = env.get('LANGUAGE', '').split(':')
        chosen = next((item for item in language_list if item), None) or env.get('LANG', 'en')
    normalized = chosen.split('.')[0].split('@')[0].replace('-', '_').lower()
    return 'nl' if normalized.split('_')[0] == 'nl' else 'en'


UI_LANGUAGE = preferred_language()


EN = {
    'Version': 'Version',
    'Made by': 'Made by',
    'Native packages': 'Native packages',
    'Installed native packages': 'Installed native packages',
    'Check native package updates': 'Check native package updates',
    'Status (rpm-ostree)': 'Status (rpm-ostree)',
    'List native packages installed on this system.': 'List native packages installed on this system.',
    'Check available native package updates without installing anything.': 'Check available native package updates without installing anything.',
    'Show OS deployment status without changing anything. OSTree deployments may require reboot; use Flatpak or Distrobox for apps.':
        'Show OS deployment status without changing anything. OSTree deployments may require reboot; use Flatpak or Distrobox for apps.',
    'List native packages installed on this system. OSTree deployments may require reboot; use Flatpak or Distrobox for apps.':
        'List native packages installed on this system. OSTree deployments may require reboot; use Flatpak or Distrobox for apps.',
    'Check available native package updates without installing anything. OSTree deployments may require reboot; use Flatpak or Distrobox for apps.':
        'Check available native package updates without installing anything. OSTree deployments may require reboot; use Flatpak or Distrobox for apps.',
    # Dynamic command documentation in the sidebar (v0.3.8)
    'Reading command information…': 'Reading command information…',
    'What it does:': 'What it does:',
    'Usage:': 'Usage:',
    'Selected options:': 'Selected options:',
    'Available options (examples):': 'Available options (examples):',
    'Documented options:': 'Documented options:',
    'Choose command options to select flags.': 'Choose command options to select flags.',
    'No description available in this program’s help text.': 'No description available in this program’s help text.',
    'No description found in installed help, manual or package information.': 'No description found in installed help, manual or package information.',
    'Package description:': 'Package description:',
    'No recognizable options were found.': 'No recognizable options were found.',
    'Command help is unavailable:': 'Command help is unavailable:',
    'You can still enter options manually.': 'You can still enter options manually.',
    # Dynamic command options (v0.3.4)
    'Select a command to see its options below. You can also type arguments manually.': 'Select a command to see its options below. You can also type arguments manually.',
    'Show available options…': 'Show available options…',
    'Select a command, then request its options. You can also type arguments manually.': 'Select a command, then request its options. You can also type arguments manually.',
    'Filter options…': 'Filter options…',
    'Use': 'Use',
    'Option': 'Option',
    'Description': 'Description',
    'Value': 'Value',
    'Additional arguments (optional; no shell pipes):': 'Additional arguments (optional; no shell pipes):',
    'Select a command first.': 'Select a command first.',
    'Reading command help…': 'Reading command help…',
    'Options found: ': 'Options found: ',
    'Tick options, then enter values where needed.': 'Tick options, then enter values where needed.',
    'No recognizable options found. You can still type arguments manually.': 'No recognizable options found. You can still type arguments manually.',
    'Option values must be on one line': 'Option values must be on one line',
    'This option needs a value': 'This option needs a value',
    'Selected executable is no longer available': 'Selected executable is no longer available',
    'Help request timed out': 'Help request timed out',
    'Could not read command help': 'Could not read command help',
    'Choose command options…': 'Choose command options…',
    'Zoek functies of commando’s…': 'Search functions or commands…',
    'Shows programs on your PATH and Bash builtins. Aliases and shell functions defined in the current terminal cannot always be discovered. Selecting a program loads its options using --help; select trusted programs only. A prepared command is never run automatically.': 'Shows programs on your PATH and Bash builtins. Aliases and shell functions defined in the current terminal cannot always be discovered. Selecting a program loads its options using --help; select trusted programs only. A prepared command is never run automatically.',
    # Main window / sidebar
    'Zoek een functie…': 'Search for a function…',
    'Functie': 'Function', 'Kies een functie': 'Select a function',
    'Kies links een functie': 'Select a function on the left',
    'Typ rechts zoals in elke terminal. Kies links een taak om een commando samen te stellen. Zet het in de terminal en druk zelf op Enter.':
        'Type in the terminal on the right as usual. Choose a task on the left to prepare a command, insert it into the terminal, then press Enter yourself.',
    'In terminal zetten': 'Insert into terminal',
    'Commando kopiëren': 'Copy command', 'Terminal openen': 'Open terminal',
    'Invoegen op een lege opdrachtregel; daarna zelf Enter drukken.':
        'Insert at an empty shell prompt, then press Enter yourself.',
    'Commandoregel voorbereid': 'Command line prepared',
    'Open eerst de terminal.': 'Open the terminal first.',
    'De shell wordt nog gestart. Probeer het opnieuw zodra de prompt verschijnt.':
        'The shell is starting. Try again once the prompt appears.',
    'Een programma gebruikt momenteel de terminal. Sluit dit programma of ga terug naar de shellprompt. Dan kun je het commando invoegen.':
        'Another program is using the terminal. Close it or return to the shell prompt before inserting a command.',
    'Niet vast te stellen of de shellprompt actief is.\n\nVoeg alleen in wanneer je bij een lege shellprompt staat. Toch invoegen?':
        'Cannot determine whether the shell prompt is active.\n\nOnly insert at an empty shell prompt. Insert anyway?',
    'Deze shell heeft mogelijk andere aanhalingstekens. Controleer de syntaxis voordat je de opdracht uitvoert.':
        'This shell may use different quoting rules. Check command syntax before running it.',
    'Commando ingevoegd. Controleer de hele opdrachtregel en druk zelf op Enter.':
        'Command inserted. Check the full line and press Enter yourself.',
    'De werkmap bestaat niet meer.': 'The working directory no longer exists.',
    'Terminal afgesloten. Gebruik Terminal opnieuw openen voor een nieuwe sessie.':
        'Terminal closed. Use Reopen terminal for a new session.',
    'Terminal afsluiten? Eventuele lopende programma’s kunnen hierdoor stoppen.':
        'Close the terminal? Any running programs may be stopped.',
    'Nog geen begeleide opdrachten uitgevoerd.': 'No guided commands have been used yet.',
    'Werkmap wijzigen': 'Change working directory',
    'Zet cd klaar; druk in de terminal op Enter om van map te wisselen.':
        'Prepares cd. Press Enter in the terminal to change directories.',
    'Werkmap kiezen': 'Choose working directory',
    'Opdracht opnieuw voorbereiden': 'Prepare command again',
    'Annuleren': 'Cancel', 'Voorbereiden': 'Prepare', 'Kiezen': 'Choose',
    'Bestand voor SHA256': 'File for SHA256',
    'Zoekterm': 'Search term', 'App-ID': 'App ID', 'Hostnaam of IP': 'Hostname or IP address',
    'Systeemservice': 'System service', 'Bestaande containernaam': 'Existing container name',
    'Bestaande Flatpak-bron': 'Existing Flatpak remote',
    'Kies een gebouwde Flatpak-repository': 'Choose an existing Flatpak repository',
    'Bundle exporteren': 'Export bundle', 'Nieuwe .flatpak-bundle opslaan': 'Save new .flatpak bundle',
    'Kies de vertrouwde projectmap': 'Choose the trusted project folder',
    'Kies het JSON/YAML-manifest': 'Choose JSON/YAML manifest',
    'Manifest: ': 'Manifest: ',
    'Controleer of runtime en SDK geïnstalleerd zijn.': 'Verify that the runtime and SDK are installed.',
    'Manifestgegevens niet uitgelezen: ': 'Failed to read manifest metadata: ',
    'Kies een .flatpak of .flatpakref': 'Choose a .flatpak or .flatpakref',
    'Kies een .flatpak- of .flatpakref-bestand.': 'Choose a .flatpak or .flatpakref file.',
    'Lokale Flatpak installeren': 'Install local Flatpak',
    'Installeert voor de huidige gebruiker. Flatpak toont de benodigde onderdelen.':
        'Installs for the current user. Flatpak will display required components.',
    'Flatpak-apps worden geladen…': 'Loading Flatpak apps…',
    'App-lijst geladen': 'App list loaded', 'Ophalen mislukt': 'Failed to load',
    'Geen Flatpak-apps gevonden.': 'No Flatpak apps found.',
    'Commando voorbereiden': 'Prepare command',
    'Zoek app, branch of installatie…': 'Search app, branch, or installation…',
    'Versie': 'Version', 'Bron': 'Source', 'Installatie': 'Installation',
    'App/architectuur/branch': 'App/architecture/branch',
    'Branch': 'Branch',
    # Sidebar groups / action titles
    'Systeem': 'System', 'Netwerk': 'Network', 'Diagnose': 'Diagnostics',
    'Bestanden': 'Files', 'Bouwen': 'Build',
    'USB-apparaten': 'USB devices', 'PCI-apparaten en drivers': 'PCI devices and drivers',
    'Opstarttijd': 'Boot time', 'Systeeminformatie': 'System information',
    'Schijfruimte': 'Disk space', 'Schijven en partities': 'Disks and partitions',
    'Geheugen': 'Memory', 'Processen': 'Processes',
    'Actieve Flatpak-processen': 'Active Flatpak processes',
    'Installatiegeschiedenis': 'Installation history',
    'Ongebruikte gebruikersruntimes opruimen': 'Clean unused user runtimes',
    'Gebruikersinstallatie controleren': 'Check user installation',
    'Geïnstalleerde apps': 'Installed apps', 'Runtimes en SDK’s': 'Runtimes and SDKs',
    'Bronnen bekijken': 'View remotes', 'Apps bijwerken': 'Update apps',
    'Netwerkroutes': 'Network routes', 'Luisterende poorten': 'Listening ports',
    'IP-adressen': 'IP addresses', 'Netwerkstatus': 'Network status', 'DNS-status': 'DNS status',
    'Vorige boot: waarschuwingen': 'Previous boot: warnings',
    'Audio-apparaten': 'Audio devices', 'Mislukte services': 'Failed services',
    'Gebruikersservices met fouten': 'Failed user services',
    'Waarschuwingen huidige boot': 'Current boot warnings',
    'Distrobox-overzicht': 'Distrobox overview', 'Podman-overzicht': 'Podman overview',
    'Pakketten bekijken': 'View packages', 'Beschikbare updates': 'Available updates',
    'Deployment-status': 'Deployment status',
    'Beschikbare ujust-functies': 'Available ujust commands',
    'Alles bijwerken': 'Update all', 'Audio herstarten': 'Restart audio',
    'App verwijderen…': 'Remove app…',
    'Lokale bundle installeren…': 'Install local bundle…',
    'Project bouwen…': 'Build project…', 'Bundle exporteren…': 'Export bundle…',
    'Werkmap kiezen…': 'Choose working directory…',
    'Opdrachtgeschiedenis…': 'Command history…',
    'Apps zoeken…': 'Search apps…', 'App-ID installeren…': 'Install app ID…',
    'App-informatie…': 'App information…', 'App bijwerken…': 'Update app…',
    'App-rechten bekijken…': 'View app permissions…',
    'Verbinding testen…': 'Test connection…',
    'Service bekijken…': 'View service…', 'Servicelogboek…': 'Service logs…',
    'SHA256 berekenen…': 'Calculate SHA256…',
    'Container openen…': 'Open container…',
    # Command descriptions in catalog
    'Verbonden USB-apparaten bekijken.': 'Show connected USB devices.',
    'PCI-apparaten met actieve kernelmodules.': 'Show PCI devices and active kernel drivers.',
    'Tijd die het systeem nodig had om op te starten.': 'Show system boot time.',
    'Lopende Flatpak-apps bekijken.': 'List running Flatpak apps.',
    'Installaties en updates bekijken.': 'View installations and updates.',
    'Toont ongebruikte onderdelen en vraagt bevestiging voordat ze worden verwijderd.':
        'Shows unused components and asks for confirmation before removing them.',
    'Controleert de gebruikersinstallatie zonder reparaties toe te passen.':
        'Check the user installation without making changes.',
    'Routes en standaardgateway bekijken.': 'Show routes and the default gateway.',
    'Lokale TCP- en UDP-luisterpoorten bekijken.': 'Show local TCP and UDP listening ports.',
    'Waarschuwingen van de vorige boot, indien bewaard.': 'Show previous boot warnings, if available.',
    'PipeWire/WirePlumber-audioapparaten bekijken.': 'Show PipeWire/WirePlumber audio devices.',
    'Kernel en architectuur bekijken.': 'Show kernel and architecture.',
    'Vrije ruimte per aangekoppeld bestandssysteem.': 'Show disk space on mounted file systems.',
    'Schijven en bestandssystemen bekijken.': 'Show disks and file systems.',
    'Geheugen- en swapgebruik bekijken.': 'Show memory and swap usage.',
    'Interactief procesoverzicht. Druk q om af te sluiten.':
        'Interactive process monitor. Press q to quit.',
    'Alle Flatpak-apps bekijken.': 'List all Flatpak apps.',
    'Geïnstalleerde bouw- en uitvoeromgevingen.': 'List installed runtimes and SDKs.',
    'Ingestelde Flatpak-bronnen.': 'View configured Flatpak remotes.',
    'Updates bekijken en na bevestiging installeren.': 'View updates and install after confirmation.',
    'Lokale interfaces en adressen.': 'Show local interfaces and addresses.',
    'Status van NetworkManager-apparaten.': 'Show NetworkManager device status.',
    'DNS-configuratie bekijken.': 'Show DNS configuration.',
    'Systeemservices met fouten.': 'Show failed system services.',
    'Services in je gebruikerssessie.': 'Show services in your user session.',
    'Laatste 200 waarschuwingen; toegang kan beperkt zijn.':
        'Show the latest 200 warnings; access may be restricted.',
    'Geïnstalleerde Distrobox-containers.': 'Show installed Distrobox containers.',
    'Containers van de huidige gebruiker.': 'Show containers for the current user.',
    'Geïnstalleerde Homebrew-pakketten.': 'Show installed Homebrew packages.',
    'Verouderde Homebrew-pakketten.': 'Show outdated Homebrew packages.',
    'Actieve, vorige en klaargezette systeemversies.':
        'Show active, previous, and pending OS deployments.',
    'Opdrachten uit jouw geïnstalleerde Bazzite-versie.':
        'Show commands available in your installed Bazzite version.',
    'Officiële Bazzite-updateprocedure. Een systeemupdate wordt na herstart actief.':
        'Official Bazzite update process. An OS update takes effect after reboot.',
    'Onderbreekt audio en herstart PipeWire.': 'Interrupts audio and restarts PipeWire.',
    # Extra command-builder results/errors
    'Verwijdert uitsluitend deze app/branch/installatie; appgegevens blijven behouden.':
        'Removes only this app/branch/installation; app data is kept.',
    'Werkt deze specifieke app bij vanuit de bestaande installatiebron.':
        'Updates this specific app from its original installation source.',
    'Toont informatie over deze specifieke installatie.':
        'Shows information about this specific installation.',
    'Toont de gedeclareerde rechten van deze app.':
        'Shows declared permissions for this app.',
    'Flatpak verwijderen': 'Remove Flatpak',
    'Verwijdert deze installatie. Flatpak vraagt nog om bevestiging. Appgegevens worden niet expliciet gewist.':
        'Removes this installation. Flatpak asks for confirmation. App data is not explicitly deleted.',
    'Flatpak zoeken': 'Search Flatpak apps',
    'Zoekt in de ingestelde Flatpak-bronnen.': 'Searches configured Flatpak remotes.',
    'Flatpak installeren': 'Install Flatpak',
    'Installeert voor de huidige gebruiker vanuit de gekozen bron.':
        'Installs for the current user from the selected remote.',
    'Verbinding testen': 'Test connection',
    'Stuurt vier pingverzoeken; sommige servers blokkeren ping.':
        'Sends four ping requests; some servers block ping.',
    'Bekijkt systeemstatus of recente logs; verandert niets.':
        'Shows system status or recent logs without making changes.',
    'SHA256 berekenen': 'Calculate SHA256',
    'Berekent de SHA256-controlesom.': 'Calculates the SHA256 checksum.',
    'Containerterminal': 'Container shell',
    'Opent een interactieve shell in deze bestaande container. Sluit met exit.':
        'Opens an interactive shell in the existing container. Exit using exit.',
    'Flatpak-bundle maken': 'Create Flatpak bundle',
    'Exporteert een al gebouwde app uit de lokale repository. Bouwt geen broncode.':
        'Exports a previously built app from the local repository. Does not build source code.',
    'Flatpak-project bouwen': 'Build Flatpak project',
    'Systeemwijzigende commandohulp is in een container/sandbox geblokkeerd.':
        'System-changing command helpers are disabled inside containers/sandboxes.',
    'Ontbrekend hulpmiddel: ': 'Missing tool: ',
    'Geen uitvoerbare Linux-shell gevonden.': 'No executable Linux shell found.',
    'Vul tekst in zonder besturingstekens of nieuwe regels.':
        'Enter text without control characters or newlines.',
    'Ongeldige Flatpak-installatie.': 'Invalid Flatpak installation.',
    'Ongeldige volledige Flatpak-ref.': 'Invalid full Flatpak ref.',
    'Onbekende Flatpak-actie.': 'Unknown Flatpak action.',
    'Onverwacht Flatpak-lijstformaat; er wordt geen actie voorbereid.':
        'Unexpected Flatpak list format; no command is prepared.',
    'Manifest is te groot.': 'Manifest is too large.',
    'Manifest moet een object zijn.': 'Manifest must be an object.',
    'Vul een app-ID en een bestaande bronnaam in.':
        'Enter an app ID and an existing remote name.',
    'Vul een hostnaam of IP-adres in.': 'Enter a hostname or IP address.',
    'Ongeldige servicenaam.': 'Invalid service name.',
    'Kies een bestaand bestand.': 'Choose an existing file.',
    'Ongeldige containernaam.': 'Invalid container name.',
    'Onbekende functie.': 'Unknown function.',
    'Ongeldige app of installatiebron.': 'Invalid app or installation source.',
    'Kies een gebouwde OSTree-repository (met config en objects), niet alleen een projectmap.':
        'Choose a built OSTree repository (with config and objects), not just a project folder.',
    'Vul een geldige app-ID in, bijvoorbeeld io.github.naam.App.':
        'Enter a valid app ID, e.g. io.github.example.App.',
    'Ongeldige branch.': 'Invalid branch.',
    'Kies een bestaand uitvoerpad met een nieuwe bestandsnaam.':
        'Choose an existing output directory and a new filename.',
    'Kies een projectmap en een bestaand JSON/YAML-manifest.':
        'Choose a project folder and an existing JSON/YAML manifest.',
    'Het manifest moet binnen de projectmap staan.': 'The manifest must be inside the project folder.',
    'De buildmap moet een nieuwe submap van het project zijn.':
        'The build directory must be a new subfolder of the project.',
    'ult-build bestaat al. Gebruik een nieuwe projectkopie of beheer deze map eerst zelf.':
        'ult-build already exists. Use a new project copy or manage this folder yourself.',
    'Voor YAML-uitlezen is python3-pyyaml nodig; bouwen blijft mogelijk.':
        'python3-pyyaml is needed to read YAML; building is still possible.',
    # Terminal action strip, menus and status
    'Kopiëren': 'Copy', 'Plakken…': 'Paste…',
    'Uitvoer opslaan': 'Save output',
    'Terminal opnieuw openen': 'Reopen terminal',
    'Reset Terminal': 'Reset Terminal', 'Stop': 'Stop',
    'Onderbreek opdracht (Ctrl+C)': 'Interrupt command (Ctrl+C)',
    'Sluit de applicatie na bevestiging.': 'Close the application after confirmation.',
    'Extra': 'Extra',
    'HDD/SSD-map kiezen…': 'Choose HDD/SSD folder…',
    'Browse installed commands…': 'Browse installed commands…',
    'All installed commands': 'All installed commands',
    'Steam → Mount → Disk → Folder…': 'Steam → Mount → Disk → Folder…',
    'All installed commands…': 'All installed commands…',

    'starten…': 'starting…', 'shell actief': 'shell active',
    'actief': 'active', 'geslaagd': 'completed',
    'gestopt door signaal': 'stopped by signal',
    'Startfout: ': 'Startup error: ',
    'proces kon niet starten': 'process failed to start',
    'Deze tekst gaat naar de actieve terminal. Nieuwe regels kunnen opdrachten uitvoeren.':
        'This text will be pasted into the active terminal. New lines may execute commands.',
    'Controleer de tekst. Bij Bash met bracketed paste worden alle regels eerst ingevoegd; druk daarna zelf op Enter. Zonder die ondersteuning kunnen nieuwe regels direct opdrachten uitvoeren.':
        'Review this text. With Bash bracketed paste, all lines are inserted first; press Enter yourself to run them. Without that support, pasted newlines may execute commands immediately.',
    'Terminaluitvoer opslaan (kan persoonlijke gegevens bevatten)':
        'Save terminal output (may contain private information)',
    'Kopiëren (Ctrl+Shift+C)': 'Copy (Ctrl+Shift+C)',
    'Plakken (Ctrl+Shift+V)': 'Paste (Ctrl+Shift+V)',
    'Deze plakwaarschuwing niet meer tonen': "Don't show this warning again",
    'Je kunt de plakwaarschuwing opnieuw inschakelen via het rechtermuisknopmenu van de terminal.':
        'You can re-enable this warning from the terminal right-click menu.',
    'Plakwaarschuwing tonen': 'Show paste confirmation',
    'Kon de plakvoorkeur niet opslaan: ': 'Could not save paste preference: ',
    'Alles selecteren': 'Select all',
}


NL = {
    'Version': 'Versie',
    'Made by': 'Gemaakt door',
    'Zoek functies of commando’s…': 'Zoek functies of commando’s…',
    'Shows programs on your PATH and Bash builtins. Aliases and shell functions defined in the current terminal cannot always be discovered. Selecting a program loads its options using --help; select trusted programs only. A prepared command is never run automatically.': 'Toont programma’s uit PATH en Bash-ingebouwde commando’s. Aliassen en shellfuncties uit de actieve terminal zijn mogelijk niet zichtbaar. Bij de selectie haalt de app automatisch de opties op via --help. Kies alleen vertrouwde programma’s. De samengestelde opdracht wordt niet automatisch uitgevoerd.',

    'Choose command options…': 'Commando-opties kiezen…',

    # Dynamic command documentation in the sidebar (v0.3.8)
    'Reading command information…': 'Reading command information…',
    'What it does:': 'What it does:',
    'Usage:': 'Usage:',
    'Selected options:': 'Selected options:',
    'Available options (examples):': 'Available options (examples):',
    'Documented options:': 'Documented options:',
    'Choose command options to select flags.': 'Choose command options to select flags.',
    'No description available in this program’s help text.': 'No description available in this program’s help text.',
    'No recognizable options were found.': 'No recognizable options were found.',
    'Command help is unavailable:': 'Command help is unavailable:',
    'You can still enter options manually.': 'You can still enter options manually.',
    # Dynamic command options (v0.3.4)
    'Select a command to see its options below. You can also type arguments manually.': 'Kies een commando om de opties hieronder te zien. Je kunt ook argumenten zelf typen.',
    'Show available options…': 'Beschikbare opties tonen…',
    'Select a command, then request its options. You can also type arguments manually.': 'Kies een commando en vraag vervolgens de opties op. Je kunt argumenten ook zelf typen.',
    'Filter options…': 'Opties filteren…',
    'Use': 'Gebruik',
    'Option': 'Optie',
    'Description': 'Uitleg',
    'Value': 'Waarde',
    'Additional arguments (optional; no shell pipes):': 'Extra argumenten (optioneel; geen shell-pipes):',
    'Select a command first.': 'Kies eerst een commando.',
    'Reading command help…': 'Commando-opties ophalen…',
    'Options found: ': 'Gevonden opties: ',
    'Tick options, then enter values where needed.': 'Vink opties aan en vul zo nodig een waarde in.',
    'No recognizable options found. You can still type arguments manually.': 'Geen herkenbare opties gevonden. Je kunt argumenten wel zelf typen.',
    'Option values must be on one line': 'Optiewaarden moeten op één regel staan',
    'This option needs a value': 'Deze optie heeft een waarde nodig',
    'Selected executable is no longer available': 'Het geselecteerde programma is niet meer beschikbaar',
    'Help request timed out': 'Het ophalen van help duurde te lang',
    'Could not read command help': 'Kon de hulptekst van het commando niet lezen',
    # Distro detection and native package support (English fallback for other locales).
    'On Arch, avoid partial upgrades: perform a full pacman -Syu system update first.':
        'Voorkom gedeeltelijke updates op Arch: werk eerst het hele systeem bij met pacman -Syu.',
    'This is a transactional OS: do not use ordinary package changes on the host.':
        'Dit is een transactioneel systeem: wijzig hostpakketten niet via gewone pakketcommando’s.',
    'OSTree deployments may require reboot; use Flatpak or Distrobox for apps.':
        'OSTree-deployments vereisen mogelijk een herstart; gebruik Flatpak of Distrobox voor apps.',
    'Detected system: ': 'Herkend systeem: ',
    'no native manager detected': 'geen native pakketbeheerder gevonden',
    'atomic system': 'atomair systeem',
    'container/sandbox': 'container/sandbox',
    'Native packages': 'Distributiepakketten',
    'Search this native package': 'Dit distributiepakket zoeken',
    'Show this package information': 'Pakketinformatie tonen',
    'Prepare installation of this package': 'Installatie van dit pakket voorbereiden',
    'Build a command for the detected package manager.': 'Stel een opdracht samen voor de herkende pakketbeheerder.',
    'Review the command and package manager confirmation before running.':
        'Controleer de opdracht en de bevestiging van de pakketbeheerder vóór uitvoering.',
    'Status (rpm-ostree)': 'Status (rpm-ostree)',
    'Installed native packages': 'Geïnstalleerde distributiepakketten',
    'Check native package updates': 'Updates voor distributiepakketten bekijken',
    'Search native packages…': 'Distributiepakketten zoeken…',
    'Native package information…': 'Pakketinformatie bekijken…',
    'Prepare native package installation…': 'Pakketinstallatie voorbereiden…',
    'Prepare native package removal…': 'Pakketverwijdering voorbereiden…',
    'Native package name': 'Distributiepakket',
    'Package name': 'Pakketnaam',
    'Host package changes are unavailable in this environment.':
        'Systeempakketten wijzigen is in deze omgeving niet beschikbaar.',
    'This may remove dependencies or system components. Review every change in the terminal. Prepare a removal command?':
        'Dit kan afhankelijkheden of systeemonderdelen verwijderen. Controleer alle wijzigingen in de terminal. Verwijderopdracht voorbereiden?',
    'Search repositories for a native package; no changes.': 'Zoek een distributiepakket in bronnen; verandert niets.',
    'Show information about the named native package; no changes.': 'Toon informatie over dit distributiepakket; verandert niets.',
    'List native packages installed on this system.': 'Toon geïnstalleerde distributiepakketten.',
    'Check available native package updates without installing anything.': 'Controleer distributie-updates zonder iets te installeren.',
    'Show OS deployment status without changing anything.': 'Toon systeemdeployments zonder wijzigingen.',
    'Show OS deployment status without changing anything. OSTree deployments may require reboot; use Flatpak or Distrobox for apps.':
        'Bekijk systeemdeployments zonder wijzigingen. OSTree-wijzigingen vereisen mogelijk een herstart; gebruik Flatpak of Distrobox voor apps.',
    'List native packages installed on this system. OSTree deployments may require reboot; use Flatpak or Distrobox for apps.':
        'Bekijk systeemdeployments en pakketten. OSTree-wijzigingen vereisen mogelijk een herstart; gebruik Flatpak of Distrobox voor apps.',
    'Check available native package updates without installing anything. OSTree deployments may require reboot; use Flatpak or Distrobox for apps.':
        'Controleer updates zonder te installeren. OSTree-wijzigingen vereisen mogelijk een herstart; gebruik Flatpak of Distrobox voor apps.',
    'Review the package and dependencies before confirming installation in the terminal.':
        'Controleer pakket en afhankelijkheden voordat je de installatie in de terminal bevestigt.',
    'Review the removal and all dependencies before confirming in the terminal.':
        'Controleer verwijdering en afhankelijkheden voordat je in de terminal bevestigt.',
    # Contextual composition, shown when the user picks an actual app.
    'Selected app: ': 'Gekozen app: ',
    'Install this app first, then you can choose an HDD/SSD folder.':
        'Installeer deze app eerst; daarna kun je een HDD/SSD-map kiezen.',
    'Next: choose Disks & partitions to select an HDD/SSD folder.':
        'Volgende stap: kies Schijven en partities of HDD/SSD-map om een map te kiezen.',
    'Start a new command': 'Nieuwe opdracht beginnen',
    'Select a function on the left': 'Kies links een functie',
    'Choose a function to prepare a command.': 'Kies een functie om een opdracht voor te bereiden.',
    'What would you like to do next?': 'Wat wil je hierna doen?',
    'App selected: ': 'Gekozen app: ',
    'Suggestion: select an HDD/SSD folder to grant this Flatpak access. This does not relocate the app or configure its internal library.':
        'Suggestie: kies een HDD/SSD-map om deze Flatpak toegang te geven. Dit verplaatst de app niet en stelt geen interne opslagbibliotheek in.',
    'Steam library default must still be set in Steam Settings > Storage.':
        'Stel de standaard Steam-bibliotheek daarna in via Steam > Instellingen > Opslag.',
    'Not now': 'Nu niet', 'Choose HDD/SSD…': 'HDD/SSD kiezen…',
    'Search apps': 'Apps zoeken', 'Search term': 'Zoekterm',
    'Could not load search results: ': 'Zoekresultaten konden niet worden geladen: ',
    'No apps found; the search command remains in the preview.':
        'Geen apps gevonden; de zoekopdracht blijft in het voorbeeld staan.',
    'Choose an app': 'Kies een app', 'Select app': 'App kiezen',
    'Cancel': 'Annuleren', 'Filter apps…': 'Apps filteren…',
    'Name': 'Naam', 'App ID': 'App-ID', 'Version': 'Versie', 'Remote': 'Bron',
    'No suitable data partitions found.': 'Geen geschikte datapartities gevonden.',
    'Choose HDD/SSD folder for ': 'HDD/SSD-map kiezen voor ',
    'Prepare command': 'Opdracht voorbereiden',
    'Select the disk, then an existing folder. Unmounted disks receive a mount command first.':
        'Kies eerst de schijf en daarna een bestaande map. Voor een niet-gekoppelde schijf wordt eerst een mountcommando voorbereid.',
    'Choose folder…': 'Map kiezen…', 'not mounted': 'niet gekoppeld',
    'This disk is not mounted. First prepare a mount command.':
        'Deze schijf is niet gekoppeld. Bereid eerst een mountcommando voor.',
    'This app is not installed. Install it before granting folder access.':
        'Deze app is niet geïnstalleerd. Installeer deze voordat je maptoegang geeft.',
    'This command grants folder access; it does not move the app.':
        'Dit commando geeft maptoegang; het verplaatst de app niet.',
    'Choose': 'Kiezen',
    'Review the command before inserting it.':
        'Controleer de opdracht voordat je deze invoegt.',
    'Invalid Flatpak app ID': 'Ongeldig Flatpak-app-ID',
    'Invalid Flatpak remote': 'Ongeldige Flatpak-bron',
    'Selected app: ': 'Gekozen app: ',
    'Installed app selected. Choose HDD/SSD next to prepare folder access.':
        'Geïnstalleerde app geselecteerd. Kies nu HDD/SSD om maptoegang voor te bereiden.',
    'App is not installed. You can inspect it, but install it before granting disk access.':
        'App niet geïnstalleerd. Bekijk de informatie, maar installeer de app voordat je schijftoegang geeft.',
    'Select an installed app before preparing folder access.':
        'Kies een geïnstalleerde app voordat je maptoegang voorbereidt.',
    'Select a supported data partition': 'Kies een ondersteunde datapartitie',
    'Mount this partition first. Then select the app and the drive again and choose a folder. This does not format the disk.':
        'Koppel deze partitie eerst. Kies daarna dezelfde app, schijf en map opnieuw. Er wordt niets geformatteerd.',
    'Install this Flatpak app first, then choose the drive again.':
        'Installeer de Flatpak eerst en kies daarna de schijf opnieuw.',
    'Choose an existing folder on the selected drive.':
        'Kies een bestaande map op de gekozen schijf.',
    'Grant this installed Flatpak app access to the selected folder. This does NOT move the app or change its own download/library settings.':
        'Geef deze geïnstalleerde Flatpak-app toegang tot de gekozen map. Dit verplaatst de app NIET en wijzigt de eigen download-/bibliotheekinstellingen NIET.',
    'Review the permission command and press Enter yourself. Restart the app afterward. If the app has its own storage/library settings, set the folder there as well.':
        'Controleer het toegangscommando en druk zelf op Enter. Herstart de app daarna. Als de app eigen opslaginstellingen heeft, kies je daar ook de map.',
    'Review the permission command and press Enter yourself. Restart the app afterward. If the app has its own storage/library settings, set the folder there as well. For Steam: open Settings > Storage, add this folder, and set the default library inside Steam. This command cannot change that setting.':
        'Controleer het toegangscommando en druk zelf op Enter. Herstart de app daarna. Als de app eigen opslaginstellingen heeft, kies je daar ook de map. Voor Steam: open Instellingen > Opslag, voeg deze map toe en stel daar de standaardbibliotheek in. Dit commando kan die instelling niet wijzigen.',
    'Disks & partitions': 'Schijven en partities',
    'Show drives, mount points and file systems.':
        'Toon schijven, koppellocaties en bestandssystemen.',
    'Stop': 'Stop',
    'Extra': 'Extra',
    'HDD/SSD-map kiezen…': 'HDD/SSD-map kiezen…',
    'Browse installed commands…': 'Geïnstalleerde commando’s bekijken…',
    'Steam storage helper': 'Steam-opslaghulp',
    'Steam → Mount → Disk → Folder…': 'Steam → Mount → Schijf → Map…',
    'All installed commands…': 'Alle geïnstalleerde commando’s…',
    'All installed commands': 'Alle geïnstalleerde commando’s',
    'Shows programs on your PATH and Bash builtins. Aliases and shell functions defined in the current terminal cannot always be discovered. No commands are executed here.':
        'Toont programma’s uit PATH en ingebouwde Bash-commando’s. Aliassen en functies uit de actieve shell zijn niet altijd zichtbaar. Er wordt niets uitgevoerd.',
    'No installed commands found in PATH.': 'Geen geïnstalleerde commando’s gevonden in PATH.',
    'Search installed commands…': 'Zoek geïnstalleerde commando’s…',
    'Command': 'Commando', 'Type': 'Type', 'Location': 'Locatie',
    'Arguments (optional; add flags or values, not shell pipes):': 'Argumenten (optioneel; opties en waarden, geen shell-pipes):',
    'Mix & Match: Steam storage': 'Mix & Match: Steam-opslag',
    '1. Steam  →  Mount / storage  →  Volume  →  Folder': '1. Steam → Koppelen/opslag → Schijfpartitie → Map',
    'Goal: use a Steam game library on another Linux drive.': 'Doel: een Steam-spellenbibliotheek op een andere Linux-schijf gebruiken.',
    'How is Steam installed?': 'Hoe is Steam geïnstalleerd?',
    'Steam Flatpak': 'Steam Flatpak',
    'Steam native (RPM, DEB, Arch, etc.)': 'Steam normaal (RPM, DEB, Arch, enz.)',
    'The builder detects real volumes and never formats disks. You review the final command before using it.':
        'De bouwer detecteert echte schijfpartities en formatteert nooit. Je controleert het commando voor gebruik.',
    'Steam and action': 'Steam en handeling',
    '2. Select a real data volume (not the entire disk).': '2. Kies een echte datapartitie (niet de volledige schijf).',
    'Refresh volumes': 'Schijven vernieuwen', 'Choose drive': 'Schijf kiezen',
    '3. Choose an existing folder on the selected volume.': '3. Kies een bestaande map op de geselecteerde schijf.',
    'Choose library folder': 'Bibliotheekmap kiezen', 'Library folder': 'Bibliotheekmap',
    '4. Review your generated command and the next steps.': '4. Controleer je commando en de volgende stappen.',
    'Review command': 'Commando controleren',
    'not mounted': 'niet gekoppeld', 'No suitable data partitions found. Attach a disk and refresh.':
        'Geen geschikte datapartities gevonden. Sluit een schijf aan en vernieuw.',
    'Mounted at: ': 'Gekoppeld op: ',
    'This volume must be mounted before browsing folders.': 'Deze schijf moet eerst gekoppeld worden voor je mappen kunt kiezen.',
    'Select a volume first.': 'Selecteer eerst een schijfpartitie.',
    'Not mounted: prepare the mount command first, then come back to choose a folder.':
        'Niet gekoppeld: stel eerst het mountcommando samen en kies daarna de map.',
    'Folder must be on: ': 'Map moet staan op: ',
    'Command to prepare (you press Enter yourself):': 'Voor te bereiden commando (je drukt zelf op Enter):',
    'No terminal command needed.': 'Geen terminalcommando nodig.',
}

# Guided workflow messages are kept as complete translatable strings so the
# command builder can remain UI/toolkit independent.
NL.update({
    'Mount storage volume': 'Opslagpartitie koppelen',
    'Allow Steam library folder': 'Steam-bibliotheekmap toegankelijk maken',
    'Discovered on this system. Review all flags and arguments before pressing Enter.':
        'Op dit systeem gevonden. Controleer alle opties en argumenten voor je op Enter drukt.',
    'Mount this partition with your desktop authorization. No formatting is performed.':
        'Koppel deze partitie met de autorisatie van je bureaublad. Er wordt niet geformatteerd.',
    'Give only Steam (Flatpak) read/write access to this exact folder.':
        'Geef uitsluitend Steam (Flatpak) lees- en schrijftoegang tot precies deze map.',
    '1. Review and run the mount command.\n2. Return to this wizard and select the now-mounted volume and folder.\n3. Then add the folder in Steam Settings > Storage.':
        '1. Controleer en voer het mountcommando uit.\n2. Open deze wizard opnieuw en kies de gekoppelde schijf en map.\n3. Voeg de map daarna toe in Steam > Instellingen > Opslag.',
    '1. Steam must have write access to the chosen folder.\n2. Fully quit and restart Steam after changing Flatpak permissions.\n3. In Steam, open Settings > Storage, add the selected folder, then set the desired default library there.\n4. Mounting at login may need a separate persistent-mount setup.':
        '1. Steam moet schrijfrechten hebben op de gekozen map.\n2. Sluit Steam volledig en start het opnieuw na wijziging van Flatpak-rechten.\n3. Open Steam > Instellingen > Opslag, voeg de gekozen map toe en maak die daar standaard.\n4. Mogelijk is een permanente mount bij het inloggen apart nodig.',
    "The disk and folder are ready. No terminal command can reliably set Steam's default library. Open Steam > Settings > Storage, add the selected folder and set it as the default. Ensure the folder stays mounted after reboot.":
        'De schijf en map zijn klaar. Er is geen betrouwbare terminalopdracht die de standaard Steam-bibliotheek instelt. Open Steam > Instellingen > Opslag, voeg de map toe en kies die als standaard. Controleer of de schijf ook na een herstart gekoppeld blijft.',
    'Mount this volume before selecting a library folder': 'Koppel deze schijf voordat je een bibliotheekmap kiest.',
    'Select an existing accessible folder on the mounted disk': 'Kies een bestaande, toegankelijke map op de gekoppelde schijf.',
    'Select an existing folder': 'Kies een bestaande map.',
    'Folder must be on the selected volume': 'De map moet op de geselecteerde schijf staan.',
    'Select a separate mounted data volume': 'Kies een aparte gekoppelde datapartitie.',
    'You need write permission for the selected folder': 'Je hebt schrijfrechten nodig voor de geselecteerde map.',
    'Select a supported disk partition': 'Kies een ondersteunde schijfpartitie.',
    'Unknown Steam installation type': 'Onbekende Steam-installatiemethode.',
    'udisksctl is not installed; mount this drive with your file manager first':
        'udisksctl is niet geïnstalleerd; koppel de schijf eerst met je bestandsbeheerder.',
    'Select the intended Steam library folder': 'Kies de gewenste Steam-bibliotheekmap.',
    'Flatpak is not installed': 'Flatpak is niet geïnstalleerd.',
    'lsblk is not installed': 'lsblk is niet geïnstalleerd.',
    'Invalid command name': 'Ongeldige commandonaam.',
    'The selected command is no longer available': 'Het geselecteerde commando is niet langer beschikbaar.',
    'Arguments must be on one line': 'Argumenten moeten op één regel staan.',
    'Invalid quotation marks in arguments': 'Ongeldige aanhalingstekens in argumenten.',
    'Invalid control character': 'Ongeldig besturingsteken.',
})

NL.update({
    'Reading command information…': 'Commando-informatie ophalen…',
    'What it does:': 'Wat doet dit commando:',
    'Usage:': 'Gebruik:',
    'Selected options:': 'Geselecteerde opties:',
    'Available options (examples):': 'Beschikbare opties (voorbeelden):',
    'Documented options:': 'Gedocumenteerde opties:',
    'Choose command options to select flags.': 'Open Commando-opties om opties te kiezen.',
    'No description available in this program’s help text.': 'Geen beschrijving gevonden in de hulptekst van dit programma.',
    'No description found in installed help, manual or package information.': 'Geen beschrijving gevonden in de hulptekst, manpagina of pakketgegevens.',
    'Package description:': 'Pakketbeschrijving:',
    'No recognizable options were found.': 'Geen herkenbare opties gevonden.',
    'Command help is unavailable:': 'Commandohulp is niet beschikbaar:',
    'You can still enter options manually.': 'Je kunt de opties nog handmatig invoeren.',
})

# Typed composition engine (v0.3.2): translations affect UI only, never argv.
NL.update({
    'Choose folder actions…': 'Mapacties kiezen…',
    'Choose network interface…': 'Netwerkadapter kiezen…',
    'Choose Podman container…': 'Podman-container kiezen…',
    'Choose an existing folder': 'Bestaande map kiezen',
    'Choose network interface': 'Netwerkadapter kiezen',
    'Choose Podman container': 'Podman-container kiezen',
    'Existing Podman container name or ID': 'Bestaande Podman-containernaam of -ID',
    'Choose HDD/SSD': 'HDD/SSD kiezen',
    'Network interfaces': 'Netwerkinterfaces',
    'Show the selected network interface.': 'Toon de geselecteerde netwerkadapter.',
    'Suggested next actions': 'Voorgestelde vervolgstappen',
    'Prepare suggestion': 'Voorstel voorbereiden',
    'Choose what you want to do next; nothing runs automatically.':
        'Kies wat je hierna wilt doen. Er wordt niets automatisch uitgevoerd.',
    'Selected: ': 'Geselecteerd: ',
    'No suitable items found.': 'Geen geschikte onderdelen gevonden.',
    'Show app information': 'App-informatie bekijken',
    'Show app permissions': 'App-rechten bekijken',
    'Allow app access to folder on selected disk': 'App toegang geven tot map op gekozen schijf',
    'Show disk partition details': 'Schijfpartitiegegevens bekijken',
    'Show free space on disk': 'Vrije schijfruimte bekijken',
    'Prepare mounting the disk': 'Schijfkoppeling voorbereiden',
    'Calculate folder size': 'Mapgrootte berekenen',
    'List folder contents': 'Mapinhoud bekijken',
    'Calculate SHA256 hash': 'SHA256-controlesom berekenen',
    'Show file details': 'Bestandsgegevens bekijken',
    'Show service status': 'Servicestatus bekijken',
    'Show service logs': 'Servicelogs bekijken',
    'Show service errors': 'Servicefouten bekijken',
    'Ping host (four packets)': 'Host pingen (vier pakketten)',
    'Look up host addresses': 'Hostadressen opzoeken',
    'Inspect container': 'Containerdetails bekijken',
    'Show container logs': 'Containerlogs bekijken',
    'Show network interface addresses': 'Netwerkadapteradressen bekijken',
    'Show network interface statistics': 'Netwerkadapterstatistieken bekijken',
    'Flatpak app information': 'Flatpak-appinformatie',
    'Flatpak app permissions': 'Flatpak-apprechten',
    'Disk details': 'Schijfgegevens',
    'Disk free space': 'Vrije schijfruimte',
    'Folder size': 'Mapgrootte',
    'Folder contents': 'Mapinhoud',
    'File SHA256': 'Bestands-SHA256',
    'File metadata': 'Bestandsmetadata',
    'Service status': 'Servicestatus',
    'Service logs': 'Servicelogs',
    'Service errors': 'Servicefouten',
    'Ping host': 'Host pingen',
    'DNS lookup': 'DNS-opzoeking',
    'Container details': 'Containergegevens',
    'Container logs': 'Containerlogs',
    'Network interface addresses': 'Netwerkadapteradressen',
    'Network interface statistics': 'Netwerkadapterstatistieken',
    'Show details of this Flatpak app.': 'Toon details van deze Flatpak-app.',
    'Show which access this Flatpak app declares.': 'Toon de opgegeven toegangsrechten van deze Flatpak-app.',
    'Review a Flatpak permission change for an existing folder.':
        'Controleer een Flatpak-rechtenwijziging voor een bestaande map.',
    'Inspect the selected volume without writing anything.':
        'Onderzoek de geselecteerde schijfpartitie zonder gegevens te wijzigen.',
    'Show free space on the selected mounted volume.':
        'Toon de vrije ruimte op de geselecteerde gekoppelde schijfpartitie.',
    'Prepare a desktop mount command; never format or modify partitions.':
        'Bereid een koppelopdracht voor; formatteer of wijzig nooit partities.',
    'This may ask for desktop authorization. Mounting is never automatic.':
        'Dit kan om bureaubladautorisatie vragen. Koppelen gebeurt nooit automatisch.',
    'Review the command before inserting it.':
        'Controleer het commando voordat je het invoegt.',
})

# Texts with command-specific suffixes, such as "Missing tool: curl".
PREFIXES = ('Ontbrekend hulpmiddel: ', 'Startfout: ', 'Manifestgegevens niet uitgelezen: ',
            'Bouwt naar ', 'Manifest: ', 'Service ')


def tr(text, language=None):
    """Translate a user-visible string; never use this for shell argv."""
    if not isinstance(text, str):
        return text
    if (UI_LANGUAGE if language is None else language) == 'nl':
        for source, translated in (('Selected app: ', 'Gekozen app: '),
                                   ('Allow folder access for ', 'Maptoegang geven aan '),
                                   ('Choose HDD/SSD folder for ', 'HDD/SSD-map kiezen voor ')):
            if text.startswith(source):
                return translated + text[len(source):]
        if text in NL:
            return NL[text]
        for suffix in (
            ' On Arch, avoid partial upgrades: perform a full pacman -Syu system update first.',
            ' This is a transactional OS: do not use ordinary package changes on the host.',
            ' OSTree deployments may require reboot; use Flatpak or Distrobox for apps.',
        ):
            if text.endswith(suffix):
                base = text[:-len(suffix)]
                return NL.get(base, base) + ' ' + NL.get(suffix.strip(), suffix.strip())
        for source, translation in (
            ('Search (', 'Zoeken ('), ('Info (', 'Informatie ('),
            ('Installed (', 'Geïnstalleerd ('), ('Install (', 'Installeren ('),
            ('Remove (', 'Verwijderen ('), ('Updates (', 'Updates ('),
        ):
            if text.startswith(source) and text.endswith(')'):
                return translation + text[len(source):]
        return text
    if text in EN:
        return EN[text]
    if text.startswith('Bouwt naar '):
        return 'Builds into ' + text[len('Bouwt naar '):].replace(
            ' en exporteert naar de repository. Runtime/SDK moeten al aanwezig zijn. Een manifest kan scripts uitvoeren: gebruik vertrouwde broncode.',
            ' and exports to the repository. Runtime/SDK must already be installed. A manifest can execute scripts: use trusted source code.')
    if text.startswith('Service '):
        return 'Service ' + text[8:]
    for prefix in PREFIXES:
        if prefix in EN and text.startswith(prefix):
            return EN[prefix] + text[len(prefix):]
    return text
