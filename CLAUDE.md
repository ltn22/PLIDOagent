# PLIDOagent — cours Agentic AI

Ce dépôt contient les notebooks du cours sur l'agentic AI, construits autour de l'exemple filé du
"philosophy professor" (un professeur qui rédige un sujet, le fait traiter par plusieurs LLMs, puis
corrige les réponses).

Le cours est découpé en parties (`Part_1_philosopher.ipynb`, puis `Part_2_...`, etc.), chaque partie
introduisant de nouveaux outils/concepts d'agentic AI en s'appuyant sur les parties précédentes.

## Règle importante

`Part_1_philosopher.ipynb` contient une cellule d'introduction ("Welcome to the AI Agentics Course")
qui décrit le déroulé global du cours et annonce le contenu de la partie du jour.

**Chaque fois qu'un nouveau chapitre/partie est ajouté au cours, cette introduction doit être mise à
jour** pour refléter les parties déjà vues et annoncer correctement le contenu de la nouvelle séance.

Cette section prend la forme d'une liste uniforme ("Course roadmap") où chaque partie est une puce
`**Part N — titre**: description`, y compris la partie du jour. Ne pas isoler la dernière partie
dans une section séparée type "## Today: Part N" : ça casse la cohérence de la liste et n'a plus de
sens dès que cette partie n'est plus "aujourd'hui".

## Google Colab vs machine locale

`Part_1_philosopher.ipynb` est volontairement local-only : son but est justement d'apprendre à
installer `uv` et à faire tourner Ollama sur sa propre machine, ce que Colab ne permet pas de
reproduire correctement (pas de serveur local persistant, pas de "votre machine" à comparer).

Pour les parties suivantes qui ne dépendent pas d'Ollama ou d'un outil local, une variante Google
Colab peut être proposée en plus de la version locale pour réduire la friction d'installation.
Mais ne pas le faire par défaut : ça double la gestion des secrets (fichier `.env` en local vs
`userdata` de Colab) et le code à maintenir. Ne proposer Colab que si la contrainte "machine locale"
de la partie a disparu.
