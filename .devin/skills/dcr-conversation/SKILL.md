---
name: dcr-conversation
description: Retrieve and inject past conversation context from the dcr archive. Search by keyword, project, or source type, then inject a summary or full export into the current conversation. Use when the user says "@conversation", "cherche dans mes conversations", "qu'est-ce que j'ai dit sur", "retrouve la conversation sur", or references a past discussion by topic.
---

# @conversation — DCR Conversation Retrieval

## Objectif

Permettre à Cascade de **retrouver et injecter du contexte** depuis l'archive permanente des conversations (`dcr`). L'archive contient **toutes** les conversations Cascade (`.pb`) et Devin Local (`sessions.db`) — y compris celles supprimées par Windsurf/Devin Desktop.

## Quand utiliser ce skill

- L'utilisateur écrit `@conversation: <sujet>` ou `@conversation` dans son prompt
- L'utilisateur dit "qu'est-ce que j'ai dit sur X dans une conversation précédente ?"
- L'utilisateur dit "retrouve la conversation où on a parlé de Y"
- L'utilisateur dit "cherche dans mes conversations passées"
- L'utilisateur référence une discussion passée par sujet ou mot-clé
- L'utilisateur veut comparer une décision actuelle avec un contexte passé

## Ce que ce skill N'EST PAS

- ❌ Ce skill **n'est pas** `@cascade-self-config` — il ne modifie pas la configuration
- ❌ Ce skill **n'est pas** un outil de résumé de la conversation courante
- ❌ Ce skill **ne crée pas** de nouvelles conversations — il récupère du contexte passé
- ✅ Ce skill **recherche** dans l'archive et **injecte** un résumé ou export dans le contexte courant

## Procédure

### Étape 1 : Identifier la requête

Quand l'utilisateur écrit `@conversation: <sujet>` ou demande de retrouver une conversation :

1. Extraire le **sujet/mots-clés** de la requête
2. Si l'utilisateur donne un **ID numérique** ou **UUID** → aller directement à l'étape 3 (show/export)

### Étape 2 : Rechercher avec `dcr search`

```bash
# Recherche simple par mots-clés
dcr search "mots-clés extraits" --no-sync

# Recherche filtrée par projet
dcr search "mots-clés" -p /home/julien/Sources/mon-projet --no-sync

# Recherche filtrée par source (cascade ou devin_local)
dcr search "mots-clés" --source-type devin_local --no-sync

# Recherche dans une table spéciale (tool_calls, checkpoints, rounds)
dcr search "file_path" -s tool_calls --no-sync
```

**Important** : Toujours utiliser `--no-sync` pour éviter un sync complet (qui peut prendre 30-60s). L'auto-sync se fera naturellement si l'utilisateur lance d'autres commandes `dcr` sans `--no-sync`.

### Étape 3 : Récupérer le détail

Une fois la conversation identifiée (par son ID numérique dans la liste de résultats) :

```bash
# Aperçu rapide (main chain only, 20 steps)
dcr show <ID> --no-sync

# Aperçu avec branches latérales (regenerations, prompts édités)
dcr show <ID> --no-sync --full-tree --steps 50

# Export complet en markdown (thinking + tool_calls + checkpoints)
dcr export <ID> --no-sync

# Export avec branches
dcr export <ID> --no-sync --full-tree
```

### Étape 4 : Injecter le contexte

Selon la demande de l'utilisateur :

- **Résumé court** : injecter le titre + les 3-5 premiers résultats de `dcr search` (snippets)
- **Contexte complet** : injecter le `dcr export` (markdown avec thinking, tool_calls, checkpoints)
- **Conversation spécifique** : injecter le `dcr show` (aperçu structuré)

**Format d'injection** :

```
<retrieved_conversation>
**Source**: dcr archive — conversation "<title>" (ID: <id>, source: <cascade|devin_local>)
**Date**: <created_at>
**Project**: <project_path>

<contenu récupéré — résumé ou export>
</retrieved_conversation>
```

## Commandes `dcr` disponibles

| Commande | Usage | Quand l'utiliser |
|---|---|---|
| `dcr search "<query>"` | Recherche full-text FTS5 | Étape 2 — trouver par mots-clés |
| `dcr search "<query>" -p <path>` | Filtrer par projet | Étape 2 — restreindre à un projet |
| `dcr search "<query>" --source-type <src>` | Filtrer par source | Étape 2 — cascade vs devin_local |
| `dcr search "<query>" -s <table>` | Filtrer par table | Étape 2 — tool_calls, checkpoints, rounds |
| `dcr list -l <N>` | Lister les N plus récentes | Voir les conversations récentes |
| `dcr list --source-type devin_local` | Lister par source | Filtrer par source |
| `dcr show <ID>` | Aperçu d'une conversation | Étape 3 — aperçu rapide |
| `dcr show <ID> --full-tree` | Toutes les steps (branches) | Étape 3 — voir les regenerations |
| `dcr export <ID>` | Export markdown complet | Étape 3 — thinking + tool_calls + checkpoints |
| `dcr export <ID> --full-tree` | Export avec branches | Étape 3 — tout inclure |
| `dcr status` | Stats de l'archive | Vérifier l'état de l'archive |

## IDs : ce qu'il faut savoir

- `dcr` utilise des **IDs numériques** (1, 2, 3...) pour `show` et `export`
- Les UUIDs Cascade (format `586311a4-...`) fonctionnent aussi avec `show`/`export`
- Les slugs Devin Local (format `apple-pomelo`) fonctionnent aussi
- **Ne jamais** passer un ID numérique `dcr` à `trajectory_search` — confusion fréquente

## Limites

- L'archive `dcr` est à `~/.local/share/dcr/dcr.db` — elle est **permanente** (les conversations supprimées restent)
- Les conversations Cascade (`.pb`) n'ont pas de `thinking`/`tool_calls` (enrichissement annulé — Phase 1B)
- Les conversations Devin Local ont `thinking` et `tool_calls` (capturés en Phase 1A)
- `--full-tree` peut générer beaucoup de contenu (branches latérales) — utiliser avec parcimonie dans le contexte

## Exemples

### Exemple 1 : "Qu'est-ce que j'ai dit sur les ADR ?"

```bash
dcr search "ADR architecture decision" --no-sync
```

→ Injecter les 3-5 meilleurs résultats avec snippets.

### Exemple 2 : "@conversation: validation phase projet"

```bash
dcr search "validation phase projet" --no-sync
# → trouve ID 313
dcr show 313 --no-sync --steps 10
```

→ Injecter l'aperçu de la conversation 313.

### Exemple 3 : "Retrouve la conversation où j'ai utilisé l'outil read sur le fichier progress.md"

```bash
dcr search "progress.md" -s tool_calls --no-sync
```

→ Cherche dans les arguments des tool_calls.

### Exemple 4 : "Montre-moi toutes mes conversations sur le projet devin-conversations-retriever"

```bash
dcr list -p /home/julien/Sources/devin-conversations-retriever --no-sync -l 20
```

→ Liste les 20 conversations les plus récentes sur ce projet.
