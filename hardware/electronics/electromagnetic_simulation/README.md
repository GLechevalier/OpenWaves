Plan : 

- Coder l'émission (donc simuler le processus électrique d'émission)
- Coder la PROPAGATION
- Coder la REFLEXION
- Coder la Réception (Donc simuler le processus électrique de réception des OEM sur le capteur)
- Recoder le traitement du signal dans la machine.


## Emission

Définition : Quel courant est transmis aux Patch antennas ?
Inputs : Durée des chirps, taille des chirps, espacement entre les chirps


### Challenges : 
- Coder un processus d'émission qui soit le plus fidèle possible à la réalité électronique de ce qui est émis. On ne pourra sûrement pas avoir accès aux vraies données de courant qui transitent dans les antennes.

### Roadmap
- Coder d'abord juste la fonction en dent de scie
- Coder la retransmission de ça en fonctions sinusoidales (quelle amplitude de courant transite ????)
- Chercher comment le chirp est réalisé électroniquement
- Recoder une simulation de ce circuit électronique


### Architecture

- Il faut une classe qui permette de tenir une time series, on l'utilisera peut être tout le temps pour stocker une variable physique qui évolue dans le temps (courant dans un fil, tension, valeur d'une composante d'un champ électrique à un point dans l'espace...). Par défaut on utilise la liste Python, quels sont les contraintes sur cette time series ?
    - Il faut pouvoir ajouter des éléments à la liste facilement
    - La physique est toujours causale, donc c'est inutile de devoir modifier les premiers éléments de la liste après avoir modifié ceux d'après
    - Il faut pouvoir toujours définit le pas de temps, parce que dans l'idée toutes les time series de la simu ont le même pas de temps.
    - Dans ce cas on créé un objet Time Series# blackwaves_simulation


