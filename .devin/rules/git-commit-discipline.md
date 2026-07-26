---
trigger: model_decision
description: Quand Cascade s'apprete a faire un git commit ou a terminer une feature/milestone
---

<git_commit_discipline>
Un commit = une feature ou un milestone. Jamais grouper deux milestones dans un seul commit.

Regles :
1. **Un commit par milestone** : des qu'un milestone est complete (code + tests passants), committer immediatement — ne pas attendre la fin de session
2. **Un commit par feature** : si une feature est ajoutee apres un milestone (ex: enrichissement de champs, sync()), c'est un commit separe
3. **Tests avant commit** : `pytest tests/test_<module>.py -v` doit passer avant de commit
4. **Message de commit** : format `feat(<scope>): <description courte>` ou `fix(<scope>): <description>`
5. **Pas de commit en bloc** : si plusieurs milestones sont termines en meme temps, faire des commits separens dans l'ordre chronologique
6. **Chacun commit ses propres modifications** : ne jamais committer les changements d'un autre contributeur dans son propre commit — utiliser `git add -p` ou `git stash` pour isoler ses hunks
7. **Docs dans le commit du milestone** : les updates de `progress.md`, `docs/architecture.md`, etc. font partie du commit du milestone correspondant
</git_commit_discipline>
