# Repository Map - Root Folder Structure

# Repository Map - Root Folder Structure

```
.                                    # PatchRaptor root directory
├── AGENTS.md                        # Agent operation guidelines
├── bin/                             # Compiled assets (Steam service DLLs)
│   └── steamservice.exe             # Steam service executable
├── config.example.json              # Configuration template
├── commands.md                      # Discord command documentation
├── config/                          # Application configuration
│   ├── config.vdf                  # Server config (generated)
│   └── libraryfolders.vdf          # Library folders (generated)
├── Configurator.py                  # Executable generator utility
├── cloudflared.exe                  # Cloudflare tunnel client
├── discord_setup.md                 # Discord bot setup guide
├── dist/                            # Compiled executables output
│   ├── Configurator.exe            # Self-extracting config app
│   ├── Instinct.exe                # Installer builder
│   ├── PatchRaptor.exe             # Main application executable
│   ├── RaptorChat.exe              # Chat module executable
│   └── WebPanel.exe                # Web panel executable
├── docs/                            # System documentation
│   └── repository_map.md           # ← This file
├── features.md                      # System features list
├── LICENSE                          # License information
├── main.py                          # Main application entry point
├── MASTER_MESSAGE_FLOW.md           # Message flow architecture
├── PatchRaptor.ico                  # Application icon
├── PatchRaptor.py                   # Core PatchRaptor module
├── pr40.png                         # Version 40 logo
├── pr_live.py                       # Live web interface (Subscribes to cluster_live.json)
├── pr_style/                       # Official Brand Identity Reference (patchraptor.online)
│   ├── index.html                  # Source-available layout reference
│   └── style.css                   # Brand palette and typography authority
├── pytest.ini                       # Pytest configuration
├── readme.md                        # Main README
├── readme_release.md                # Release notes
├── RaptorChat/                      # RaptorChat module directory
│   ├── __pycache__
│   ├── logs/
│   └── RaptorChat.py                # RaptorChat main module
├── requirements-dev.txt             # Development dependencies
├── requirements.txt                 # Runtime dependencies
├── run_tests.bat                    # Test runner script
├── run_tests_with_coverage.bat      # Coverage-enabled tests
├── setup.iss                        # Inno Setup installer script
├── siteserverui/                    # UI server (deprecated)
│   ├── css/
│   ├── images/
│   ├── js/
│   └── win32/
├── static/                          # Static web assets (Brand-Aligned)
│   ├── cherries.png                # Visual asset
│   ├── cherries.ico                # Asset icon
│   ├── dashboard.js                # Dashboard logic (Polling & DOM mapping)
│   ├── favicon.ico                 # Website favicon
│   ├── index.html                  # Web panel entry (Hero-wrapper layout)
│   ├── style.css                   # Brand-synced CSS (Consolas/5B83C9)
│   ├── maps/                       # ARK game maps (10+ maps)
│   │   ├── aberration.jpg          # Aberration
│   │   ├── astraeos.jpg            # Astraeos
│   │   ├── bobsmissions.jpg        # Bobs Mis
│   │   ├── clubark.jpg             # Club demo
│   │   ├── default.jpg             # Default (Valguero)
│   │   ├── extinction.jpg          # Extinction
│   │   ├── lostcolony.png          # Lost Colony
│   │   ├── ragnarok.jpg            # Ragnarok
│   │   ├── scorchedearth.jpg       # Scorched Earth
│   │   ├── thecenter.jpg           # The Center (Valguero)
│   │   ├── theisland.jpg           # The Island
│   │   └── valguero.jpg            # Valguero
├── static/maps/                    # Duplicate map references (deprecated)
├── testing.md                       # Testing documentation
├── test_runner.py                   # Automated test runner
├── test_schedule.json               # Test execution schedule
├── tools/                           # Utility scripts
│   ├── __pycache__
│   └── security_scanner.py          # Security analysis tool
└── update_cloudflared.bat           # Cloudflare updater script
```
