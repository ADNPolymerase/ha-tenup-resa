# Ten'Up pour Home Assistant

Voir les courts libres de votre club de tennis sur [Ten'Up](https://tenup.fft.fr) (FFT) et réserver ou annuler un court depuis Home Assistant.

> 🇬🇧 [Read in English](README.md)

## Ce que vous obtenez

- **Capteurs** : créneaux libres aujourd'hui, créneaux libres sur les prochains jours, prochain créneau libre, prochaine réservation, nombre de réservations.
- **Calendrier** : vos réservations au club.
- **Services** : `tenup.book` et `tenup.cancel`.
- **Commande websocket** `tenup/planning` avec la grille complète (courts x créneaux x jours) pour une carte dédiée.

L'intégration lit le tableau de réservation des adhérents (« Réserver dans mon club »), pas la location horaire payante.

## Prérequis

- Un compte Ten'Up adhérent du club (licence avec une formule de réservation).
- Home Assistant 2024.12 ou plus récent.

## Installation

1. HACS > Intégrations > trois points > Dépôts personnalisés > ajouter `https://github.com/ADNPolymerase/ha-tenup-resa` (catégorie Intégration).
2. Installer **Ten'Up**, redémarrer Home Assistant.
3. Paramètres > Appareils et services > Ajouter une intégration > **Ten'Up**.

## Configuration

1. **Votre club** : tapez son nom et choisissez-le dans la liste (ou collez son code Ten'Up à 8 chiffres, visible dans l'URL du tableau de réservation).
2. **Votre session** : Ten'Up n'autorise pas la connexion par mot de passe depuis un outil tiers (la page de connexion est protégée contre les connexions automatisées). L'intégration utilise donc la session de votre navigateur :
   - connectez-vous sur tenup.fft.fr,
   - ouvrez les outils de développement (F12) > Application (Chrome) ou Stockage (Firefox) > Cookies > `https://tenup.fft.fr`,
   - copiez le cookie dont le nom commence par `SESS` et collez-le sous la forme `SESSxxxx=valeur`.

Quand la session expire, Home Assistant affiche une réparation qui demande un cookie frais. Aucun mot de passe n'est jamais stocké.

Options : nombre de jours à charger (7 par défaut, l'horizon du club) et intervalle de rafraîchissement (15 minutes par défaut).

## Services

```yaml
service: tenup.book
data:
  court_id: "21100"          # voir les attributs des capteurs ou la commande planning
  start: "2026-09-10 21:00:00"
```

```yaml
service: tenup.cancel
data:
  reservation_id: "165841846"   # ou court_id + start
```

Les deux services renvoient une réponse (`response_variable`) et lèvent une erreur lisible quand Ten'Up refuse (par exemple la règle du club sur les réservations simultanées).

Seuls les créneaux à un joueur sont réservables pour l'instant. Les courts qui demandent deux joueurs (partenaire) renvoient une erreur explicite.

## À savoir

- Ten'Up annule une réservation sans demander de confirmation. Le service fait exactement cela : prévoyez une confirmation dans vos automatisations ou vos cartes.
- L'API publique de recherche sert à trouver le club, tout le reste passe par votre session.

## Support

Bugs et idées : [GitHub issues](https://github.com/ADNPolymerase/ha-tenup-resa/issues).
