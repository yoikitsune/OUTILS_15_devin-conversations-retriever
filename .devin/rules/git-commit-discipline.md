---
trigger: model_decision
description: Quand Cascade s'apprete a faire un git commit ou a terminer une feature/milestone
---

<git_commit_discipline>
Un commit = une feature ou un milestone. Jamais grouper deux milestones dans un seul commit.

Regles :
1. **Granularite au cas par cas** : la frequence de commit (par tache, par phase, ou par milestone) depend du contexte — taille de la tache, dependances, risque de regression. L'agent juge, mais ne groupe jamais deux milestones dans un seul commit.
2. **Validation utilisateur avant commit** : avant tout commit, presenter le diff (ou le resume des changements) a l'utilisateur et attendre sa validation explicite. Ne jamais committer sans approbation. Un commit est une action irreversible qui entre dans l'historique — l'utilisateur est le seul juge de ce qui merite d'y entrer.
3. **Tests avant commit** : `pytest tests/ -v` (suite complete) doit passer avant de commit — pas seulement le test du module modifie. Voir la rule `test-with-code`.
4. **Message de commit** : format `feat(<scope>): <description courte>` ou `fix(<scope>): <description>`
5. **Pas de commit en bloc** : si plusieurs unites sont termines en meme temps, faire des commits separes dans l'ordre chronologique
6. **Chacun commit ses propres modifications** : ne jamais committer les changements d'un autre contributeur dans son propre commit — utiliser `git add -p` ou `git stash` pour isoler ses hunks
7. **Docs dans le commit du milestone** : les updates de `progress.md`, `docs/architecture.md`, etc. font partie du commit du milestone correspondant
</git_commit_discipline>
