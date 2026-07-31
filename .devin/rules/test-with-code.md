---
trigger: model_decision
description: Quand Cascade implemente un module dans src/dcr/ ou modifie du code Python
---

<test_with_code>
Chaque module implemente doit avoir son fichier de test avant de passer au milestone suivant :

- `src/dcr/decrypt.py` → `tests/test_decrypt.py`
- `src/dcr/parser.py` → `tests/test_parser.py`
- `src/dcr/indexer.py` → `tests/test_indexer.py`
- `src/dcr/search.py` → `tests/test_search.py`
- `src/dcr/cli.py` → `tests/test_cli.py`
- `src/dcr/devin_local.py` → `tests/test_devin_local.py`

(`src/dcr/server.py` est rejete — voir ADR-0004. Ne pas creer de test pour lui.)

Les tests doivent couvrir au minimum :
- Un test nominal (cas normal qui doit reussir)
- Un test erreur (cas d'echec gere proprement)

Quand on MODIFIE un module existant (pas seulement quand on en cree un nouveau), lancer la suite complete `pytest tests/ -v` avant de committer — pas seulement le test du module modifie. Un changement dans `indexer.py` peut casser `search.py` ou `cli.py` ; seul l'execution de toute la suite detecte les regressions.

M8 (Tests) n'est pas un milestone separe. Les tests sont integres dans chaque milestone M2-M7.
Le milestone M8 est supprime — sa fonction est distribuee dans M2 a M7.
</test_with_code>
