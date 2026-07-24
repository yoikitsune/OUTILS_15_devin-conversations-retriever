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
