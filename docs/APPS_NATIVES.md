# Apps natives Nexis Hub (iOS et Android)

Deux apps natives, une par système, qui reprennent l'interface de
l'app Flutter (`app_mobile/`, toujours la référence fonctionnelle de
l'aperçu) avec les composants de chaque plateforme :

| | iOS | Android |
| --- | --- | --- |
| Dossier | `app_ios/` | `app_android/` |
| Langage | Swift, SwiftUI | Kotlin, Jetpack Compose |
| Design | Liquid Glass d'iOS 26 et 27 (barre d'onglets, accessoire « Demander un service », feuilles, boutons en verre) ; repli translucide sur iOS 18 à 25 | Material 3 (barre de navigation, bouton flottant, feuilles, grands titres) |
| Minimum | iOS 18 | Android 8 (API 26) |

Identité commune (AGENTS.md) : bleu vif `#0A63F0`, marine `#021937`,
icône bleu uni et monogramme blanc, **Unbounded** pour les titres et les
montants, **Inter** pour tout le texte (graisses posées sur l'axe `wght`
des polices variables, comme Flutter).

## Pictogrammes de services

Phosphor Icons en duotone, bleu Nexis, sur carré blanc bordé (choix de Ben
du 2026-11-25), plus la tondeuse de Tabler Icons pour la coiffure. Les deux
bibliothèques sont sous licence MIT. Pour chaque service, une icône
principale et trois objets : à la première ouverture de « Quel service ? »
sur l'appareil, chaque carré fait un tour de ses objets puis se fixe ; ensuite
un seul carré refait de temps en temps un tour discret. Rien ne bouge avec
« Réduire les animations » (iOS) ou « Supprimer les animations » (Android),
ni dans la liste des missions. « Autre service » reste fixe.

La liste vit dans `outils/pictogrammes_apps_natives.py`, qui écrit
`app_ios/NexisHub/Resources/Pictogrammes.xcassets` et
`app_android/app/src/main/res/drawable/` :

    npm install @phosphor-icons/core @tabler/icons
    python outils/pictogrammes_apps_natives.py node_modules

Les mêmes listes sont dans `Pictogrammes.swift` et `Pictogrammes.kt` :
les garder synchronisées.

## État

Interface seulement, avec les données fictives de l'aperçu Flutter
(`DemoRepository`) : aucun appel réseau, aucun argent. Écrans construits :
lancement, bienvenue, numéro, code, inscription (CGU obligatoires),
accueil (portefeuille, actions rapides, prestations), missions,
portefeuille (mouvements), profil (langue), « Quel service ? »,
demande de service, « Décrire mon besoin ». Les écrans pas encore
portés (suivi de mission, devis, paiement, litige, espace prestataire)
affichent « Bientôt dans l'app ».

## Textes

Aucun texte n'est écrit dans les apps natives : ils viennent des fichiers
`app_mobile/lib/l10n/app_{fr,ln,en}.arb`. Après toute modification :

    python outils/textes_apps_natives.py

La CI vérifie que les deux `textes.json` sont à jour.

## Lancer

- **iOS** (Mac avec Xcode 26 ou plus) : `brew install xcodegen`, puis
  `cd app_ios && xcodegen generate && open NexisHub.xcodeproj`.
- **Android** (Android Studio) : ouvrir le dossier `app_android/`.

## CI

`.github/workflows/apps-natives.yml` compile les deux apps, lance leurs
tests, puis photographie les écrans principaux sur un simulateur iPhone et
un émulateur Android (clair, sombre, français, lingala, anglais). Les
captures sont dans les artefacts `captures-ios` et `captures-android` de
l'exécution. Le mode capture (`-capture home`, `--es capture home`)
n'existe que dans les versions de débogage.
