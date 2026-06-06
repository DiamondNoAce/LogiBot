# seed_data.py
# ============================================================
# Alte Startdaten für die Service-Ansicht. Die aktuelle Wissensbasis liegt im Ordner Rule Engine/.
# Diese Daten bilden die Start-Wissensbasis.
# ============================================================

DEFAULT_KNOWLEDGE_BASE = {
    "services": [
        {
            "key": "eduroam",
            "name": "eduroam",
            "description": "WLAN-Zugang über eduroam für Universität Hohenheim.",
            "systems": [
                {
                    "key": "windows",
                    "name": "Windows 10/11",
                    "prerequisite": "Für die Windows-Konfiguration wird eine aktive WLAN- oder Ethernetverbindung benötigt.",
                    "guide_url": "https://www.uni-hohenheim.de/fileadmin/einrichtungen/kim-relaunch/dateien/anleitungen/eduroam_win11-CAT-dt-engl.pdf",
                    "steps": [
                        {
                            "number": 1,
                            "phase": "vorbereitung",
                            "title": "Internetverbindung prüfen",
                            "instruction": "Sicherstellen, dass eine WLAN- oder Ethernetverbindung vorhanden ist.",
                            "keywords": ["internet", "wlan", "lan", "ethernet", "hotspot", "vorbereitung"],
                            "solution": {
                                "problem_title": "Problem bei Vorbereitung / Internet",
                                "summary": "Für die Installation wird zunächst eine aktive Internetverbindung benötigt.",
                                "actions": [
                                    "Prüfe, ob eine WLAN- oder Ethernetverbindung besteht.",
                                    "Falls kein Internet verfügbar ist: vorübergehend LAN, Hotspot oder anderes WLAN nutzen.",
                                    "Danach cat.eduroam.org erneut öffnen."
                                ]
                            },
                            "rules": [
                                {"intent": "internet", "keywords": ["kein internet", "keine verbindung", "wlan aus", "lan", "hotspot"]}
                            ]
                        },
                        {
                            "number": 2,
                            "phase": "cat_webseite",
                            "title": "cat.eduroam.org öffnen",
                            "instruction": "Webseite cat.eduroam.org im Browser öffnen und auf die Installer-Schaltfläche klicken.",
                            "keywords": ["cat.eduroam.org", "cat eduroam", "webseite", "browser", "installer-button"],
                            "solution": {
                                "problem_title": "Problem beim CAT-Download oder bei der Organisationsauswahl",
                                "summary": "Die CAT-Webseite muss direkt geöffnet werden, bevor die Organisation ausgewählt wird.",
                                "actions": [
                                    "Öffne cat.eduroam.org direkt im Browser.",
                                    "Suche manuell nach \"Universität Hohenheim\", falls die Organisation nicht automatisch erscheint.",
                                    "Wähle das Installationsprogramm für Windows aus.",
                                    "Falls der Download nicht sichtbar ist: Downloads-Ordner öffnen oder den Download-Link erneut anklicken."
                                ]
                            },
                            "rules": [
                                {"intent": "cat_webseite", "keywords": ["cat", "cat.eduroam", "webseite", "browser", "seite geht nicht"]}
                            ]
                        },
                        {
                            "number": 3,
                            "phase": "organisation",
                            "title": "Organisation auswählen",
                            "instruction": "Als Organisation \"Universität Hohenheim\" auswählen oder manuell danach suchen.",
                            "keywords": ["organisation", "universität hohenheim", "uni hohenheim", "hohenheim", "suchen"],
                            "solution": {
                                "problem_title": "Problem beim CAT-Download oder bei der Organisationsauswahl",
                                "summary": "Die Organisation muss auf der CAT-Webseite korrekt ausgewählt werden.",
                                "actions": [
                                    "Öffne cat.eduroam.org direkt im Browser.",
                                    "Suche manuell nach \"Universität Hohenheim\", falls die Organisation nicht automatisch erscheint.",
                                    "Wähle das Installationsprogramm für Windows aus.",
                                    "Falls der Download nicht sichtbar ist: Downloads-Ordner öffnen oder den Download-Link erneut anklicken."
                                ]
                            },
                            "rules": [
                                {"intent": "organisation", "keywords": ["organisation", "hohenheim", "uni", "universität", "universitaet", "finde hohenheim nicht"]}
                            ]
                        },
                        {
                            "number": 4,
                            "phase": "installer_download",
                            "title": "Installer herunterladen",
                            "instruction": "Passendes Installationsprogramm für Windows herunterladen.",
                            "keywords": ["download", "herunterladen", "installer", "installationsprogramm", "downloads"],
                            "solution": {
                                "problem_title": "Problem beim CAT-Download oder bei der Organisationsauswahl",
                                "summary": "Der richtige Windows-Installer muss heruntergeladen werden.",
                                "actions": [
                                    "Öffne cat.eduroam.org direkt im Browser.",
                                    "Suche manuell nach \"Universität Hohenheim\", falls die Organisation nicht automatisch erscheint.",
                                    "Wähle das Installationsprogramm für Windows aus.",
                                    "Falls der Download nicht sichtbar ist: Downloads-Ordner öffnen oder den Download-Link erneut anklicken."
                                ]
                            },
                            "rules": [
                                {"intent": "installer_download", "keywords": ["download", "herunterladen", "installer", "installationsprogramm", "downloads"]}
                            ]
                        },
                        {
                            "number": 5,
                            "phase": "datei_starten",
                            "title": "Datei ausführen",
                            "instruction": "Heruntergeladene Datei öffnen bzw. doppelklicken und im Installer auf \"Weiter\" klicken.",
                            "keywords": ["datei", "doppelklick", "starten", "ausführen", "weiter", "öffnet nicht"],
                            "solution": {
                                "problem_title": "Problem beim Starten des Installers",
                                "summary": "Die heruntergeladene Datei muss gestartet und der Installer geöffnet werden.",
                                "actions": [
                                    "Öffne die heruntergeladene Datei per Doppelklick.",
                                    "Falls Windows nachfragt, die Ausführung erlauben.",
                                    "Im Installer auf \"Weiter\" klicken.",
                                    "Falls nichts passiert: Downloads-Ordner prüfen und Datei erneut starten."
                                ]
                            },
                            "rules": [
                                {"intent": "datei_starten", "keywords": ["datei", "doppelklick", "startet nicht", "ausführen", "ausfuehren", "weiter"]}
                            ]
                        },
                        {
                            "number": 6,
                            "phase": "hinweis_bestaetigen",
                            "title": "Hinweisfenster bestätigen",
                            "instruction": "Hinweisfenster mit \"OK\" bestätigen.",
                            "keywords": ["ok", "hinweis", "hinweisfenster", "bestätigen", "bestaetigen"],
                            "solution": {
                                "problem_title": "Problem beim Hinweisfenster",
                                "summary": "Das Hinweisfenster muss bestätigt werden, damit die Installation fortgesetzt wird.",
                                "actions": [
                                    "Das Hinweisfenster mit \"OK\" bestätigen.",
                                    "Wenn das Fenster nicht erscheint, Installer schließen und erneut starten."
                                ]
                            },
                            "rules": [
                                {"intent": "hinweis_bestaetigen", "keywords": ["ok", "hinweis", "hinweisfenster", "fenster erscheint nicht"]}
                            ]
                        },
                        {
                            "number": 7,
                            "phase": "benutzerdaten",
                            "title": "Benutzerdaten eingeben",
                            "instruction": "Hohenheimer Benutzername im Format benutzername@uni-hohenheim.de und Hohenheimer Passwort eingeben. Nicht die E-Mail-Adresse verwenden.",
                            "keywords": ["benutzername", "passwort", "login", "kennwort", "email", "e-mail", "anmelden"],
                            "solution": {
                                "problem_title": "Problem mit Benutzername oder Passwort",
                                "summary": "Für eduroam wird der Hohenheimer Benutzername im speziellen Format benötigt.",
                                "actions": [
                                    "Verwende den Benutzernamen im Format benutzername@uni-hohenheim.de.",
                                    "Verwende nicht die Uni-E-Mail-Adresse.",
                                    "Das Passwort ist das Passwort des Hohenheimer Benutzerkontos, z. B. wie bei ILIAS, VPN oder Webmail.",
                                    "Passwort zweimal korrekt eingeben, falls Windows dies verlangt."
                                ]
                            },
                            "rules": [
                                {"intent": "benutzerdaten", "keywords": ["login", "benutzername", "passwort", "kennwort", "email", "e-mail", "anmeldung"]}
                            ]
                        },
                        {
                            "number": 8,
                            "phase": "zertifikat",
                            "title": "Sicherheitswarnung bestätigen",
                            "instruction": "Sicherheitswarnung bzw. Zertifikatsabfrage mit \"Ja\" bestätigen.",
                            "keywords": ["sicherheitswarnung", "zertifikat", "warnung", "ja", "bestätigen"],
                            "solution": {
                                "problem_title": "Problem mit Sicherheitswarnung / Zertifikat",
                                "summary": "Die Sicherheitswarnung gehört zur Installation und muss nach Prüfung bestätigt werden.",
                                "actions": [
                                    "Die Sicherheitswarnung mit \"Ja\" bestätigen.",
                                    "Falls du unsicher bist, prüfe, ob der Installer wirklich von cat.eduroam.org kommt und Universität Hohenheim ausgewählt wurde."
                                ]
                            },
                            "rules": [
                                {"intent": "zertifikat", "keywords": ["zertifikat", "sicherheitswarnung", "warnung", "ja bestätigen"]}
                            ]
                        },
                        {
                            "number": 9,
                            "phase": "fertigstellen",
                            "title": "Installation fertigstellen",
                            "instruction": "Auf \"Fertigstellen\" klicken.",
                            "keywords": ["fertigstellen", "fertig", "abschließen", "abschluss"],
                            "solution": {
                                "problem_title": "Problem nach Installation / Verbindung",
                                "summary": "Nach dem Fertigstellen sollte die Verbindung zu eduroam geprüft werden.",
                                "actions": [
                                    "Auf \"Fertigstellen\" klicken und anschließend mit eduroam verbinden.",
                                    "Wenn der Login nicht funktioniert: Windows neu starten.",
                                    "Prüfe, ob alle Windows-Updates inklusive Funktionsupdates installiert sind.",
                                    "Updates können auch Netzwerkkarten-Treiber aktualisieren und Verbindungsprobleme lösen.",
                                    "Bei weiteren Problemen den KIM-IT-Service-Desk kontaktieren: kim-it@uni-hohenheim.de."
                                ]
                            },
                            "rules": [
                                {"intent": "fertigstellen", "keywords": ["fertigstellen", "fertig", "installation abgeschlossen"]}
                            ]
                        },
                        {
                            "number": 10,
                            "phase": "verbinden",
                            "title": "Mit eduroam verbinden",
                            "instruction": "Mit eduroam verbinden. Falls der Login nicht funktioniert, Neustart und Windows-Updates prüfen.",
                            "keywords": ["verbinden", "verbindung", "eduroam geht nicht", "login funktioniert nicht", "windows update", "neustart"],
                            "solution": {
                                "problem_title": "Problem nach Installation / Verbindung",
                                "summary": "Wenn die Verbindung nach der Installation nicht funktioniert, helfen Neustart und Updates häufig weiter.",
                                "actions": [
                                    "Auf \"Fertigstellen\" klicken und anschließend mit eduroam verbinden.",
                                    "Wenn der Login nicht funktioniert: Windows neu starten.",
                                    "Prüfe, ob alle Windows-Updates inklusive Funktionsupdates installiert sind.",
                                    "Updates können auch Netzwerkkarten-Treiber aktualisieren und Verbindungsprobleme lösen.",
                                    "Bei weiteren Problemen den KIM-IT-Service-Desk kontaktieren: kim-it@uni-hohenheim.de."
                                ]
                            },
                            "rules": [
                                {"intent": "verbinden", "keywords": ["verbinden", "verbindung", "keine verbindung", "eduroam geht nicht", "login funktioniert nicht"]}
                            ]
                        }
                    ]
                },
                {
                    "key": "mac",
                    "name": "macOS",
                    "prerequisite": "Für die macOS-Konfiguration wird eine aktive Internetverbindung benötigt. Außerdem sollte macOS vorher aktualisiert werden.",
                    "guide_url": "https://www.uni-hohenheim.de/fileadmin/einrichtungen/kim-relaunch/dateien/anleitungen/eduroam_macOS-CAT-dt-engl.pdf",
                    "steps": [
                        {
                            "number": 1,
                            "phase": "vorbereitung",
                            "title": "Mac vorbereiten",
                            "instruction": "Mac aktualisieren und sicherstellen, dass eine Internetverbindung vorhanden ist.",
                            "keywords": ["mac aktualisieren", "internet", "wlan", "vorbereitung", "update"],
                            "solution": {
                                "problem_title": "Problem bei Vorbereitung / Internet",
                                "summary": "Vor der Einrichtung sollte der Mac aktuell sein und eine Internetverbindung haben.",
                                "actions": [
                                    "Prüfe, ob eine Internetverbindung besteht.",
                                    "Aktualisiere macOS, bevor du mit der Installation beginnst.",
                                    "Falls du kein Internet hast: nutze vorübergehend Mobilfunk-Hotspot, LAN oder ein anderes WLAN."
                                ]
                            },
                            "rules": [
                                {"intent": "vorbereitung", "keywords": ["kein internet", "mac update", "mac aktualisieren", "wlan", "hotspot"]}
                            ]
                        },
                        {
                            "number": 2,
                            "phase": "cat_webseite",
                            "title": "cat.eduroam.org öffnen",
                            "instruction": "Webseite cat.eduroam.org öffnen und auf die Installer-Schaltfläche klicken.",
                            "keywords": ["cat.eduroam", "webseite", "browser", "installer"],
                            "solution": {
                                "problem_title": "Problem beim CAT-Download oder bei der Organisationsauswahl",
                                "summary": "Die CAT-Webseite muss direkt im Browser geöffnet werden.",
                                "actions": [
                                    "Öffne cat.eduroam.org direkt im Browser.",
                                    "Suche manuell nach \"Universität Hohenheim\", falls die Organisation nicht automatisch erscheint.",
                                    "Achte darauf, den Installer für Apple/macOS auszuwählen.",
                                    "Prüfe den Downloads-Ordner, falls der Download im Browser nicht sichtbar ist."
                                ]
                            },
                            "rules": [
                                {"intent": "cat_webseite", "keywords": ["cat", "cat.eduroam", "webseite", "browser"]}
                            ]
                        },
                        {
                            "number": 3,
                            "phase": "organisation",
                            "title": "Organisation auswählen",
                            "instruction": "Als Organisation \"Universität Hohenheim\" auswählen oder manuell danach suchen.",
                            "keywords": ["organisation", "hohenheim", "universität", "universitaet", "uni"],
                            "solution": {
                                "problem_title": "Problem beim CAT-Download oder bei der Organisationsauswahl",
                                "summary": "Die Organisation muss korrekt ausgewählt werden.",
                                "actions": [
                                    "Öffne cat.eduroam.org direkt im Browser.",
                                    "Suche manuell nach \"Universität Hohenheim\", falls die Organisation nicht automatisch erscheint.",
                                    "Achte darauf, den Installer für Apple/macOS auszuwählen.",
                                    "Prüfe den Downloads-Ordner, falls der Download im Browser nicht sichtbar ist."
                                ]
                            },
                            "rules": [
                                {"intent": "organisation", "keywords": ["organisation", "hohenheim", "finde hohenheim nicht", "universität", "universitaet"]}
                            ]
                        },
                        {
                            "number": 4,
                            "phase": "installer_download",
                            "title": "Installer herunterladen",
                            "instruction": "Passenden eduroam-Installer für Apple/macOS herunterladen.",
                            "keywords": ["download", "herunterladen", "installer", "macos", "apple"],
                            "solution": {
                                "problem_title": "Problem beim CAT-Download oder bei der Organisationsauswahl",
                                "summary": "Der passende Installer für macOS muss heruntergeladen werden.",
                                "actions": [
                                    "Öffne cat.eduroam.org direkt im Browser.",
                                    "Suche manuell nach \"Universität Hohenheim\", falls die Organisation nicht automatisch erscheint.",
                                    "Achte darauf, den Installer für Apple/macOS auszuwählen.",
                                    "Prüfe den Downloads-Ordner, falls der Download im Browser nicht sichtbar ist."
                                ]
                            },
                            "rules": [
                                {"intent": "installer_download", "keywords": ["download", "herunterladen", "installer", "downloads"]}
                            ]
                        },
                        {
                            "number": 5,
                            "phase": "datei_oeffnen",
                            "title": "mobileconfig-Datei öffnen",
                            "instruction": "Die heruntergeladene mobileconfig-Datei im Browser oder im Downloads-Ordner öffnen und den Hinweis bestätigen.",
                            "keywords": ["mobileconfig", "datei öffnen", "downloads", "hinweis", "öffnen"],
                            "solution": {
                                "problem_title": "Problem beim CAT-Download oder bei der Organisationsauswahl",
                                "summary": "Die mobileconfig-Datei muss geöffnet werden, damit macOS das Profil erkennt.",
                                "actions": [
                                    "Öffne cat.eduroam.org direkt im Browser.",
                                    "Suche manuell nach \"Universität Hohenheim\", falls die Organisation nicht automatisch erscheint.",
                                    "Achte darauf, den Installer für Apple/macOS auszuwählen.",
                                    "Prüfe den Downloads-Ordner, falls der Download im Browser nicht sichtbar ist."
                                ]
                            },
                            "rules": [
                                {"intent": "datei_oeffnen", "keywords": ["mobileconfig", "datei", "öffnen", "oeffnen", "downloads"]}
                            ]
                        },
                        {
                            "number": 6,
                            "phase": "geraeteverwaltung",
                            "title": "Geräteverwaltung öffnen",
                            "instruction": "macOS-Einstellungen öffnen und unter Allgemein die Geräteverwaltung bzw. Profile öffnen.",
                            "keywords": ["geräteverwaltung", "geraeteverwaltung", "profile", "einstellungen", "allgemein"],
                            "solution": {
                                "problem_title": "Problem bei Profil / Geräteverwaltung",
                                "summary": "Das eduroam-Profil muss in den macOS-Einstellungen gefunden werden.",
                                "actions": [
                                    "Öffne die macOS-Einstellungen.",
                                    "Gehe zu Allgemein und dann zu Geräteverwaltung bzw. Profile.",
                                    "Wähle das Profil \"eduroam\" aus.",
                                    "Klicke auf \"Installieren\".",
                                    "Falls kein Profil sichtbar ist, öffne die heruntergeladene mobileconfig-Datei erneut."
                                ]
                            },
                            "rules": [
                                {"intent": "geraeteverwaltung", "keywords": ["geräteverwaltung", "geraeteverwaltung", "profile", "profil nicht sichtbar", "einstellungen"]}
                            ]
                        },
                        {
                            "number": 7,
                            "phase": "profil_auswaehlen",
                            "title": "Profil installieren",
                            "instruction": "Das Profil \"eduroam\" per Doppelklick auswählen und auf \"Installieren\" klicken.",
                            "keywords": ["profil", "installieren", "doppelklick", "eduroam profil", "profile"],
                            "solution": {
                                "problem_title": "Problem bei Profil / Geräteverwaltung",
                                "summary": "Das eduroam-Profil muss ausgewählt und installiert werden.",
                                "actions": [
                                    "Öffne die macOS-Einstellungen.",
                                    "Gehe zu Allgemein und dann zu Geräteverwaltung bzw. Profile.",
                                    "Wähle das Profil \"eduroam\" aus.",
                                    "Klicke auf \"Installieren\".",
                                    "Falls kein Profil sichtbar ist, öffne die heruntergeladene mobileconfig-Datei erneut."
                                ]
                            },
                            "rules": [
                                {"intent": "profil_auswaehlen", "keywords": ["profil", "installieren", "doppelklick", "profile"]}
                            ]
                        },
                        {
                            "number": 8,
                            "phase": "benutzerdaten",
                            "title": "Benutzerdaten eingeben",
                            "instruction": "Benutzername im Format benutzername@uni-hohenheim.de und das Hohenheimer Passwort eingeben. Nicht die E-Mail-Adresse verwenden.",
                            "keywords": ["benutzername", "passwort", "login", "kennwort", "email", "e-mail"],
                            "solution": {
                                "problem_title": "Problem mit Benutzername oder Passwort",
                                "summary": "Für eduroam wird der Hohenheimer Benutzername im speziellen Format benötigt.",
                                "actions": [
                                    "Verwende den Benutzernamen im Format benutzername@uni-hohenheim.de.",
                                    "Verwende nicht die Uni-E-Mail-Adresse.",
                                    "Das Passwort ist das Passwort des Hohenheimer Benutzerkontos, z. B. wie bei ILIAS, VPN oder Webmail.",
                                    "Prüfe Tippfehler und ob das Passwort aktuell ist."
                                ]
                            },
                            "rules": [
                                {"intent": "benutzerdaten", "keywords": ["login", "benutzername", "passwort", "kennwort", "email", "e-mail"]}
                            ]
                        },
                        {
                            "number": 9,
                            "phase": "systempasswort",
                            "title": "Systempasswort bestätigen",
                            "instruction": "Installation mit dem Betriebssystem-Passwort bestätigen. Falls WLAN deaktiviert ist, WLAN aktivieren und erneut installieren.",
                            "keywords": ["systempasswort", "mac passwort", "betriebssystem-passwort", "wlan deaktiviert", "wlan aktivieren"],
                            "solution": {
                                "problem_title": "Problem bei Systempasswort oder deaktiviertem WLAN",
                                "summary": "macOS verlangt hier das Passwort des Macs, nicht das Uni-Passwort.",
                                "actions": [
                                    "Wenn die Meldung \"WLAN ist anscheinend deaktiviert\" erscheint: WLAN aktivieren.",
                                    "Danach erneut auf \"Installieren\" klicken.",
                                    "Falls macOS ein Passwort verlangt: das Passwort des Macs bzw. Betriebssystems eingeben, nicht das Uni-Passwort."
                                ]
                            },
                            "rules": [
                                {"intent": "systempasswort", "keywords": ["systempasswort", "mac passwort", "betriebssystem passwort", "wlan deaktiviert"]}
                            ]
                        },
                        {
                            "number": 10,
                            "phase": "verbinden",
                            "title": "Mit eduroam verbinden",
                            "instruction": "Mit eduroam verbinden. Danach sollte sich das Gerät automatisch verbinden, sobald eduroam in Reichweite ist.",
                            "keywords": ["verbinden", "verbindung", "eduroam geht nicht", "keine verbindung", "reichweite"],
                            "solution": {
                                "problem_title": "Problem beim Verbinden mit eduroam",
                                "summary": "Nach der Installation sollte sich der Mac automatisch mit eduroam verbinden.",
                                "actions": [
                                    "Prüfe, ob eduroam in Reichweite ist.",
                                    "WLAN einmal aus- und wieder einschalten.",
                                    "Falls weiterhin keine Verbindung möglich ist: eduroam-Profil entfernen und Installation erneut durchführen.",
                                    "Bei unerwarteten Problemen den KIM-IT-Service-Desk kontaktieren: kim-it@uni-hohenheim.de."
                                ]
                            },
                            "rules": [
                                {"intent": "verbinden", "keywords": ["verbinden", "verbindung", "keine verbindung", "eduroam geht nicht", "wlan"]}
                            ]
                        }
                    ]
                }
            ]
        },
        {
            "key": "vpn",
            "name": "VPN",
            "description": "Platzhalter für eine spätere VPN-Anleitung. Kann in der Adminoberfläche erweitert werden.",
            "systems": []
        },
        {
            "key": "mfa_2fa",
            "name": "MFA / 2FA",
            "description": "Platzhalter für eine spätere MFA-/2FA-Anleitung. Kann in der Adminoberfläche erweitert werden.",
            "systems": []
        }
    ]
}
