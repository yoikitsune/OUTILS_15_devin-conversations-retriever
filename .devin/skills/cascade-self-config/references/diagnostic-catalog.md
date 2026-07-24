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
