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
- `src/dcr/server.py` → `tests/test_server.py`

Les tests doivent couvrir au minimum :
- Un test nominal (cas normal qui doit reussir)
- Un test erreur (cas d'echec gere proprement)

M8 (Tests) n'est pas un milestone separe. Les tests sont integres dans chaque milestone M2-M7.
Le milestone M8 est supprime — sa fonction est distribuee dans M2 a M7.
</test_with_code>
