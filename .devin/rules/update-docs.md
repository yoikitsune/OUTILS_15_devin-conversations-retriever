---
trigger: model_decision
description: Quand un milestone est complete, quand des fichiers sont ajoutes ou supprimes, ou en fin de session
---

<documentation_updates>
Quand un milestone est complete ou en fin de session :
- Mettre a jour `progress.md` : statut du milestone (Not Started / In Progress / Completed), date, notes de handoff
- Mettre a jour `docs/index.md` si de nouveaux fichiers de documentation ont ete ajoutes ou supprimes
- Verifier que `AGENTS.md` reflete la structure reelle du projet (arbre de fichiers)
- Si une decision architecturale a ete prise, creer un ADR dans `docs/decisions/`

Un milestone est "In Progress" uniquement si du code est en cours d'ecriture. 
Si tout le code d'un milestone est ecrit et teste, il est "Completed" — pas "In Progress".
</documentation_updates>
