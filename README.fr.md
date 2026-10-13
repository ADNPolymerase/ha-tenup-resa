<img src="https://raw.githubusercontent.com/ADNPolymerase/ha-tenup-resa/main/custom_components/tenup/brand/logo.png" alt="Ten'Up" width="420">

# Ten'Up pour Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz/docs/faq/custom_repositories/)
[![GitHub Release](https://badgen.net/github/release/ADNPolymerase/ha-tenup-resa)](https://github.com/ADNPolymerase/ha-tenup-resa/releases)
[![Hassfest](https://github.com/ADNPolymerase/ha-tenup-resa/actions/workflows/hassfest.yml/badge.svg)](https://github.com/ADNPolymerase/ha-tenup-resa/actions/workflows/hassfest.yml)
[![HACS Action](https://github.com/ADNPolymerase/ha-tenup-resa/actions/workflows/hacs.yml/badge.svg)](https://github.com/ADNPolymerase/ha-tenup-resa/actions/workflows/hacs.yml)
[![Tests](https://github.com/ADNPolymerase/ha-tenup-resa/actions/workflows/tests.yml/badge.svg)](https://github.com/ADNPolymerase/ha-tenup-resa/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-support-yellow.svg?logo=buy-me-a-coffee)](https://buymeacoffee.com/adnpolymerase)

<a href="https://buymeacoffee.com/adnpolymerase" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-orange.png" alt="Buy Me A Coffee" height="60"></a>
<a href="https://adnpolymerase.github.io/HA/" target="_blank"><img src="https://raw.githubusercontent.com/ADNPolymerase/HA/main/assets/site-button.svg" alt="Lien vers mon github.io pour mes autres projets" height="60"></a>

Voir les courts libres de votre club de tennis sur [Ten'Up](https://tenup.fft.fr) (FFT) et réserver ou annuler un court depuis Home Assistant.

> 🇬🇧 [Read in English](README.md)

## Ce que vous obtenez

- **Capteurs** : créneaux libres aujourd'hui, créneaux libres sur les prochains jours, prochain créneau libre, prochaine réservation, nombre de réservations.
- **Calendrier** : vos réservations au club.
- **Services** : `tenup.book` et `tenup.cancel`.
- **Une carte Lovelace**, livrée avec l'intégration : le tableau du club, réserver et annuler d'un clic.
- **Commande websocket** `tenup/planning` avec la grille complète (courts x créneaux x jours).

L'intégration lit le tableau de réservation des adhérents (« Réserver dans mon club »), pas la location horaire payante.

## Prérequis

- Un compte Ten'Up adhérent du club (licence avec une formule de réservation).
- Home Assistant 2025.3 ou plus récent.

## Installation

1. HACS > trois points > Dépôts personnalisés > `https://github.com/ADNPolymerase/ha-tenup-resa`, type Intégration.
2. Chercher `tenup` dans HACS, télécharger **Ten'Up**, redémarrer Home Assistant.
3. Paramètres > Appareils et services > Ajouter une intégration > **Ten'Up**.

Un dépôt tout juste ajouté apparaît comme « Nouveau » et peut être masqué par le filtre de statut : cherchez-le.

La carte vient avec : rien d'autre à télécharger, aucune ressource Lovelace à ajouter à la main.

> **Vous venez d'une 1.0.x ?** La carte vivait dans son propre dépôt. Retirez **Ten'Up Card** de HACS : l'intégration sert sa propre copie et retire l'ancienne ressource de tableau de bord au redémarrage suivant. Vos cartes continuent de fonctionner, leur configuration ne change pas.

## Configuration

1. **Votre club** : tapez son nom et choisissez-le dans la liste (ou collez son code Ten'Up à 8 chiffres, visible dans l'URL du tableau de réservation).
2. **Votre session** : Ten'Up n'autorise pas la connexion par mot de passe depuis un outil tiers (la page de connexion est protégée contre les connexions automatisées). L'intégration utilise donc la session de votre navigateur :
   **Dans les outils de développement.** Connectez-vous sur tenup.fft.fr et ouvrez **« Réserver dans mon club »**. Appuyez sur **F12** (⌥⌘I sur Mac), onglet **Application** (**Stockage** sous Firefox), rubrique **Cookies** > `https://tenup.fft.fr`, et copiez la valeur de la ligne **`SHARED_SESSION_JAVA`** :

   <img src="https://raw.githubusercontent.com/ADNPolymerase/ha-tenup-resa/main/docs/cookie-devtools.fr.png" alt="La ligne du cookie de session dans les cookies" width="760">

   **Encore plus simple si vous préférez :** onglet **Réseau**, clic droit sur n'importe quelle requête, **Copier > Copier comme cURL**, et collez le tout dans le champ : la session y est retrouvée toute seule.

   Ce cookie est `HttpOnly` depuis la refonte d'octobre 2026 : aucun script de page ne peut le lire, et le marque-page des versions précédentes ne fonctionne plus.

   Au choix aussi : onglet Réseau > clic droit sur une ligne > Copier > **Copier en tant que cURL**, et collez le tout. L'intégration ne retient que le cookie utile : adresses, en-têtes et autres cookies sont ignorés et ne sont jamais enregistrés.

Quand la session expire, Home Assistant affiche une réparation qui demande un cookie frais. Aucun mot de passe n'est jamais stocké.

Options : nombre de jours à charger (7 par défaut, l'horizon du club) et intervalle de rafraîchissement (15 minutes par défaut).

## La carte

Ajoutez **Ten'Up Card** depuis le sélecteur de cartes, ou :

```yaml
type: custom:ha-tenup-card
days: 3
```

- **Le tableau du club** : un onglet par jour, les courts en colonnes, les créneaux à leur vraie taille.
- **Couleurs** : vert libre, jaune 2 joueurs requis, rouge pris, violet un ami, bleu à vous, gris passé.
- **Réserver et annuler** d'un clic, après confirmation.
- **Courts à 2 joueurs** : cherchez votre partenaire et réservez depuis la carte. Aucun numéro d'adhérent à connaître.
- **Éditeur visuel**, français et anglais.

| Option | Défaut | |
|---|---|---|
| `name` | nom du club | Titre |
| `entry_id` | premier club | Club affiché |
| `days` | `3` | Onglets de jours, 1 à 7 |
| `start_hour`, `end_hour` | grille du club | Heures affichées |
| `courts` | tous | Courts affichés |
| `next_booking` | `true` | Annoncer votre prochaine réservation au-dessus de la grille |
| `show_names` | `true` | Afficher qui a réservé. Désactivé : ni noms, ni suivi depuis la grille |
| `confirm` | `true` | Confirmer avant de réserver ou d'annuler |
| `compact` | `false` | Cellules plus petites |
| `language` | `auto` | `auto`, `en` ou `fr` |

L'annulation est immédiate sur Ten'Up : gardez `confirm` activé.

### Amis

Leurs réservations passent en violet. Touchez une réservation pour suivre un joueur avec son initiale (lui seul) ou avec **Tous les NOM** (famille et homonymes), ou gérez la liste depuis le bouton de l'en-tête.

Un partenaire avec qui vous réservez peut être retenu depuis la fenêtre de réservation, puis proposé en un clic la fois suivante.

Ten'Up n'affiche que l'initiale du prénom dans le tableau : deux joueurs avec la même initiale et le même nom sont donc colorés pareil. La réservation, elle, n'est pas concernée : le partenaire choisi est identifié précisément.

## Services

```yaml
service: tenup.book
data:
  court_id: "21100"          # voir les attributs des capteurs ou la commande planning
  start: "2026-09-10 21:00:00"
  partner: "John DOE"   # seulement pour un court qui demande deux joueurs
```

```yaml
service: tenup.cancel
data:
  reservation_id: "123456789"   # ou court_id + start
```

Les deux services renvoient une réponse (`response_variable`) et lèvent une erreur lisible quand Ten'Up refuse (par exemple la règle du club sur les réservations simultanées).

Les courts qui demandent deux joueurs sont réservables également. Indiquez `partner` avec un nom : l'intégration cherche parmi les adhérents du club, refuse de trancher entre homonymes et vous demande alors le prénom, puis choisit son abonnement. Un carnet de tickets ou un ticket à l'unité n'est jamais sélectionné : seul un abonnement ne coûte rien, et Ten'Up affiche le tarif d'un ticket du club sur l'abonnement aussi, donc c'est la nature de la formule qui décide, jamais le prix annoncé.

## À savoir

- Ten'Up annule une réservation sans demander de confirmation. Le service fait exactement cela : prévoyez une confirmation dans vos automatisations ou vos cartes.
- L'API publique de recherche sert à trouver le club, tout le reste passe par votre session.

## Support

Bugs et idées : [GitHub issues](https://github.com/ADNPolymerase/ha-tenup-resa/issues).

---

Ten'Up et le logo Ten'Up sont des marques de la Fédération Française de Tennis. Ce projet non officiel n'est ni affilié à la FFT ni approuvé par elle.
