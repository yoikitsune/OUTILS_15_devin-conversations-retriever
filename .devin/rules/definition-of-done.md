---
trigger: model_decision
description: Quand Cascade s'apprete a marquer un milestone comme termine dans progress.md
---

<definition_of_done>
Un milestone n'est "Completed" que si TOUS ces criteres sont remplis :

1. **Code implante** : le module fonctionne et peut etre importe sans erreur
2. **Tests passants** : `pytest tests/test_<module>.py -v` passe sans echec
3. **progress.md a jour** : le milestone est marque Completed avec la date du jour
4. **ADR si besoin** : si une decision architecturale a ete prise pendant le milestone, un ADR est cree dans `docs/decisions/`
5. **Handoff notes** : la section "AI Handoff Notes" de `progress.md` est mise a jour avec l'etat actuel

Ne jamais marquer un milestone "Completed" si les tests n'existent pas encore ou echouent.
</definition_of_done>
