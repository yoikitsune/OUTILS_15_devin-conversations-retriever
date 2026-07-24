# Outils disponibles pour ce projet — Capacités et Limites

## CLI Python / venv

### Commandes valides
| Commande | Usage | Notes |
|---|---|---|
| `.venv/bin/python3` | Exécuter Python dans le venv | venv déjà créé avec cryptography + protobuf |
| `.venv/bin/pip install -e ".[dev]"` | Installer le projet en mode dev | Pas encore fait (pyproject.toml à créer) |
| `.venv/bin/pytest tests/ -v` | Lancer les tests | Tests à créer |
| `.venv/bin/dcr decrypt-all` | Décrypter tous les .pb | CLI à créer |
| `.venv/bin/dcr index` | Indexer dans SQLite FTS5 | CLI à créer |

### Pièges connus
- Le venv existe mais n'a pas encore `mcp` ni `pydantic` installés
- Les outils de décryptage sont à `/tmp/windsurf-decrypt/tools/` (temporaire, à copier dans `src/dcr/`)

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
| `/tmp/windsurf-decrypt/tools/decrypt_pb.py` | Décryptage AES-256-GCM | À adapter dans `src/dcr/decrypt.py` |
| `/tmp/windsurf-decrypt/tools/scan_trajectory.py` | Parsing protobuf CortexTrajectory | À adapter dans `src/dcr/parser.py` |
| `/tmp/windsurf-decrypt/tools/export_md.py` | Export Markdown | À adapter pour `get_conversation` tool |
| `~/.codeium/windsurf/cascade/*.pb` | 50 fichiers de conversation | Source de données |
