---
trigger: model_decision
description: Quand un milestone est complete, quand des fichiers sont ajoutes ou supprimes, ou en fin de session
---

<documentation_updates>
Quand un milestone est complete ou en fin de session, executer cette checklist DANS L'ORDRE :

1. **`progress.md`** : statut du milestone (Not Started / In Progress / Completed), date du jour, notes de handoff a jour
2. **`docs/architecture.md`** : si le schema, les modules, ou les champs ont change, mettre a jour la section correspondante (tables, champs, data flow)
3. **`docs/index.md`** : mettre a jour la date (`Last updated`) et la Documentation Map si des fichiers ont ete ajoutes, supprimes, ou si de nouveaux modules source existent
4. **`AGENTS.md`** (racine) et **`.devin/AGENTS.md`** : verifier que l'arbre de fichiers et la section Key Files refletent la structure reelle du projet (inclure les fichiers source `src/dcr/*.py`)
5. **`docs/decisions/`** : si une decision architecturale a ete prise, creer un ADR
6. **Workflow `/end-session`** : en fin de session, l'invoquer pour un handoff structure

Un milestone est "In Progress" uniquement si du code est en cours d'ecriture.
Si tout le code d'un milestone est ecrit et teste, il est "Completed" — pas "In Progress".
</documentation_updates>
