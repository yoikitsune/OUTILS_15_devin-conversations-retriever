---
trigger: model_decision
description: Quand Cascade implemente une phase multi-taches (ex: M8 Phase 1A) pour eviter qu'elle aille trop vite et que le LLM prenne des decisions non validees
---

<task_sequencing>
Quand une phase est decomposee en taches numerotees (ex: 1A.1, 1A.2, ...), l'agent doit :

1. **Executer les taches sequentiellement dans l'ordre du tableau** — ne pas paralleliser des taches qui touchent au meme module (ex: 1A.2 et 1A.3 modifient toutes deux `indexer.py`). Le parallelisme sur un meme fichier cree des conflits et des regressions silencieuses.
2. **Valider avant de passer a la suivante** : apres chaque tache, lancer `pytest tests/ -v` (suite complete) et presenter le resultat a l'utilisateur. Ne passer a la tache suivante qu'apres validation explicite.
3. **Ne pas anticiper** : ne pas commencer 1A.3 pendant que l'utilisateur valide 1A.2. Attendre le feu vert.

Pourquoi :
- Un agent qui va trop vite prend des decisions non validees qui s'accumulent et deviennent difficiles a deboguer.
- Le comportement d'un agent depend fortement du LLM sous-jacent — un changement de modele peut faire deriver l'execution. Les points de validation sont des occasions de corriger la derive avant qu'elle ne s'amplifie.
- Les taches d'une phase sont ordonnees pour une raison (dependances de schema, de module, de tests). Les sauter ou les inverser casse cette logique.

Exception : si l'utilisateur demande explicitement d'aller plus vite ou de paralleliser, suivre son instruction. Cette rule est un garde-fou par defaut, pas une contrainte absolue.
</task_sequencing>
