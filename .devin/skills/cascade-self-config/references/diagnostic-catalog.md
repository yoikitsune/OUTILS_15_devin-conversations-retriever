# Catalogue d'erreurs diagnostiquées et corrections appliquées

> Projet: Devin Conversations Retriever (DCR)
> Ce fichier s'enrichit à chaque utilisation du skill `cascade-self-config`.

## ERR-001 : Dossier artifacts/ non créé avant décryptage

**Catégorie** : missing-prerequisite
**Date** : 2026-07-24
**Conversation source** : "Conversation Retrieval and Decryption"

### Erreur
`decrypt_pb.py` a échoué avec `FileNotFoundError` car le dossier `artifacts/decrypted/` n'existait pas.

### Correction appliquée
Création des dossiers avec `mkdir -p` avant lancement du script. Pas d'artifact créé — c'est un prérequis d'exécution.

### Artifact créé
- Aucun (prérequis d'environnement)

## ERR-002 : Documentation vivante non maintenue (progress.md périmé)

**Catégorie** : process-gap
**Date** : 2026-07-24
**Conversation source** : "Vibe Coding Project Setup"

### Erreur
Cascade a créé `progress.md` comme "living status board" mais n'a créé aucune règle pour garantir sa mise à jour. Le fichier était immédiatement périmé — M1 affiché "In Progress" alors que tout était terminé et committé.

### Correction appliquée
Rule `model_decision` : `.devin/rules/update-docs.md` — se déclenche quand un milestone est complété ou en fin de session.

### Artifact créé
- `.devin/rules/update-docs.md`

## ERR-003 : Pas de Definition of Done pour les milestones

**Catégorie** : process-gap
**Date** : 2026-07-24
**Conversation source** : "Vibe Coding Project Setup"

### Erreur
8 milestones définis sans critères d'acceptation. Un agent reprenant le projet ne peut pas savoir quand un milestone est réellement "done".

### Correction appliquée
Rule `model_decision` : `.devin/rules/definition-of-done.md` — se déclenche quand Cascade s'apprête à marquer un milestone comme terminé.

### Artifact créé
- `.devin/rules/definition-of-done.md`

## ERR-004 : Tests repoussés à la fin (M8 séparé)

**Catégorie** : efficiency
**Date** : 2026-07-24
**Conversation source** : "Vibe Coding Project Setup"

### Erreur
M8 (Tests) isolé à la fin du plan. Les 7 modules précédents auraient été implémentés sans tests, puis un rush final sur M8.

### Correction appliquée
Rule `model_decision` : `.devin/rules/test-with-code.md` — exige un test par module avant de passer au milestone suivant. M8 supprimé, tests intégrés dans M2–M7.

### Artifact créé
- `.devin/rules/test-with-code.md`

## ERR-005 : Pas de protocole de fin de session

**Catégorie** : process-gap
**Date** : 2026-07-24
**Conversation source** : "Vibe Coding Project Setup"

### Erreur
`progress.md` contenait une section "AI Handoff Notes" statique, écrite une fois. Aucun mécanisme pour la mettre à jour à chaque fin de session.

### Correction appliquée
Workflow `/end-session` : `.devin/workflows/end-session.md` — procédure structurée de handoff.

### Artifact créé
- `.devin/workflows/end-session.md`

## ERR-006 : `docs/index.md` jamais mis à jour

**Catégorie** : process-gap (non-respect de rule existante)
**Date** : 2026-07-26
**Conversation source** : "Enhance Indexer with Metadata"

### Erreur
La rule `update-docs.md` exigeait la mise à jour de `docs/index.md` lors de l'ajout de fichiers. `docs/index.md` est resté à la date du 2026-07-24 (M1) malgré l'ajout de 3 modules source (`decrypt.py`, `parser.py`, `indexer.py`) et l'enrichissement du schéma. La Documentation Map ne mentionne aucun fichier source.

### Correction appliquée
Renforcement de la rule `update-docs.md` : checklist ordonnée explicite, `docs/index.md` mentionné avec instruction de mettre à jour la date et la Documentation Map. Correction immédiate de `docs/index.md`.

### Artifact créé
- Modification de `.devin/rules/update-docs.md`

## ERR-007 : `.devin/AGENTS.md` — inventaire incomplet

**Catégorie** : process-gap (non-respect de rule existante)
**Date** : 2026-07-26
**Conversation source** : "Enhance Indexer with Metadata"

### Erreur
La rule `update-docs.md` exigeait que `AGENTS.md` reflète la structure réelle du projet. La section "Key Files" de `.devin/AGENTS.md` ne mentionnait aucun fichier source (`src/dcr/decrypt.py`, `src/dcr/parser.py`, `src/dcr/indexer.py`).

### Correction appliquée
Renforcement de la rule `update-docs.md` : instruction explicite d'inclure les fichiers source `src/dcr/*.py` dans la section Key Files. Correction immédiate de `.devin/AGENTS.md`.

### Artifact créé
- Modification de `.devin/rules/update-docs.md`

## ERR-008 : Commits groupés au lieu d'être par feature

**Catégorie** : process-gap (absence de rule)
**Date** : 2026-07-26
**Conversation source** : "Enhance Indexer with Metadata"

### Erreur
Aucune rule n'encadrait la stratégie de commits. M2+M3 ont été combinés en un seul commit (`f0ed6a6`). L'enrichissement des champs et le `sync()` ont été combinés en un seul commit (`0200079`). Les commits ont été faits en bloc à la fin de la session, pas après chaque milestone.

### Correction appliquée
Rule `model_decision` : `.devin/rules/git-commit-discipline.md` — un commit par feature/milestone, tests avant commit, pas de commit en bloc, format de message standardisé.

### Artifact créé
- `.devin/rules/git-commit-discipline.md`

## ERR-009 : `docs/architecture.md` mis à jour tardivement

**Catégorie** : process-gap (rule imprécise)
**Date** : 2026-07-26
**Conversation source** : "Enhance Indexer with Metadata"

### Erreur
`docs/architecture.md` n'a été mis à jour qu'une seule fois — après l'enrichissement des champs (step ~208), pas après la completion initiale de M4 (step ~132). Le schéma intermédiaire n'a jamais été documenté. La rule `update-docs.md` ne mentionnait pas explicitement `docs/architecture.md`.

### Correction appliquée
Renforcement de la rule `update-docs.md` : `docs/architecture.md` ajouté explicitement dans la checklist (point 2), avec instruction de mettre à jour si le schema, les modules ou les champs ont changé.

### Artifact créé
- Modification de `.devin/rules/update-docs.md`

## ERR-010 : Workflow `/end-session` non exécuté

**Catégorie** : process-gap (non-respect de workflow existant)
**Date** : 2026-07-26
**Conversation source** : "Enhance Indexer with Metadata"

### Erreur
Le workflow `/end-session` existe (créé pour ERR-005) mais n'a pas été invoqué à la fin de la conversation. Les "AI Handoff Notes" ont été mises à jour manuellement dans `progress.md` mais pas via le workflow structuré.

### Correction appliquée
Ajout d'un rappel dans la rule `update-docs.md` (point 6) : invoquer `/end-session` en fin de session pour un handoff structuré.

### Artifact créé
- Modification de `.devin/rules/update-docs.md`

## ERR-011 : Agent qui va trop vite sans validation — config stale sur les tests/commits

**Catégorie** : practice-adoption + process-gap (rule stale)
**Date** : 2026-07-31
**Conversation source** : "Validation phase projet et approche agent" (session apple-pomelo)

### Erreur
Lors de la planification de M8 Phase 1A, l'utilisateur a ressenti le besoin d'écrire manuellement un prompt recommandant « tâche par tâche, tests après chaque module, commit après chaque tâche réussie ». Trois gaps expliquent ce besoin :

1. `test-with-code.md` listait encore `server.py` (rejeté par ADR-0004), ne listait pas `devin_local.py` (nouveau module M8), et ne disait pas de lancer la **suite complète** sur modification d'un module existant — or Phase 1A modifie `indexer.py` et `cli.py` qui ont déjà 24+31 tests (risque de régression).
2. `git-commit-discipline.md` disait « committer dès qu'un milestone est terminé » **sans demander validation utilisateur** — l'agent pouvait committer sans approbation.
3. Aucune rule n'imposait l'exécution séquentielle tâche-par-tâche avec validation avant la suivante — un agent pouvait aller trop vite, d'autant que le comportement varie selon le LLM sous-jacent.

### Correction appliquée
1. MAJ `test-with-code.md` : retrait de `server.py`, ajout de `devin_local.py` et `cli.py`, ajout de l'instruction « suite complète `pytest tests/ -v` sur modification d'un module existant ».
2. MAJ `git-commit-discipline.md` : granularité au cas par cas (ne pas durcir), ajout de « validation utilisateur explicite avant tout commit ».
3. Nouvelle rule `task-sequencing.md` (`model_decision`) : exécution séquentielle des tâches d'une phase, validation tests + utilisateur avant de passer à la suivante, pas d'anticipation.

### Artifacts créés/modifiés
- Modification de `.devin/rules/test-with-code.md`
- Modification de `.devin/rules/git-commit-discipline.md`
- Création de `.devin/rules/task-sequencing.md`
