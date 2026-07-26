# Outils disponibles pour ce projet — Capacités et Limites

## CLI Python / venv

### Commandes valides
| Commande | Usage | Notes |
|---|---|---|
| `.venv/bin/python3` | Exécuter Python dans le venv | venv avec cryptography, protobuf, pydantic, pytest |
| `.venv/bin/pip install -e ".[dev]"` | Installer le projet en mode dev | Déjà fait |
| `.venv/bin/pytest tests/ -v` | Lancer les tests | 116 tests, tous passants |
| `.venv/bin/dcr sync` | Synchroniser la BDD avec les .pb (archive les stale, jamais supprime) | CLI opérationnel |
| `.venv/bin/dcr search "query"` | Recherche full-text (FTS5, BM25) | CLI opérationnel |
| `.venv/bin/dcr list` | Lister les conversations indexées | CLI opérationnel |
| `.venv/bin/dcr show <cascade_id>` | Afficher une conversation (préfixe OK) | CLI opérationnel |
| `.venv/bin/dcr export <cascade_id>` | Exporter une conversation en markdown | CLI opérationnel |
| `.venv/bin/dcr status` | Statistiques de la BDD (active + archived) | CLI opérationnel |
| `.venv/bin/dcr html` | Générer un aperçu HTML triable | CLI opérationnel |

### Pièges connus
- La BDD SQLite (`~/.local/share/dcr/dcr.db`) est l'**archive permanente** — les conversations ne sont jamais supprimées, même si le `.pb` source disparaît
- Les outils de décryptage ont été adaptés depuis `windsurf-local-user-data-decryption` dans `src/dcr/decrypt.py` et `src/dcr/parser.py`

## Outils Cascade internes

| Tool | Ce qu'il fait |
|---|---|
| `run_command` | Exécuter une commande CLI |
| `read_file` | Lire un fichier |
| `write_to_file` | Créer un fichier |
| `edit` / `multi_edit` | Modifier un fichier existant |
| `grep_search` | Rechercher dans le code |
| `code_search` | Recherche sémantique dans le code |
| `trajectory_search` | Rechercher dans une conversation passée |
| `search_web` | Recherche web |
| `read_url_content` | Lire le contenu d'une URL |

## Fichiers de référence externes

| Fichier | Contenu | Statut |
|---|---|---|
| `~/.codeium/windsurf/cascade/*.pb` | Fichiers de conversation chiffrés | Source de données initiale — la BDD SQLite est l'archive permanente |
| [windsurf-local-user-data-decryption](https://github.com/dayearleo/windsurf-local-user-data-decryption) | Décryptage + parsing (MIT) | Adapté dans `src/dcr/decrypt.py` et `src/dcr/parser.py` |
