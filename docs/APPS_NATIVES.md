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

## Logo écrit, bienvenue et attente

Choix de Ben du 2026-11-25 (planche « Nexis Hub — connexion et accueil ») :

- **Logo écrit** : « NEXIS » en Unbounded 700, dont le E est celui de
  l'icône de l'app (trois barres biseautées), puis « HUB » en Unbounded 300,
  collé : **NexisHub s'écrit en un mot** (choix de Ben du 2026-11-25,
  version A ; c'est le passage du gras au léger qui sépare les deux
  parties). Le nom sous l'icône est aussi « NexisHub ». Les textes de l'app
  viennent des `.arb` Flutter et écrivent encore « Nexis Hub » : à changer
  avec l'app Flutter et le bot, pour que tout reste d'accord. Les libellés
  lus par VoiceOver / TalkBack gardent « Nexis Hub » pour être prononcés
  correctement. L'icône de l'app ne change pas. Le logo est vectorisé
  depuis la police de l'app par `outils/logo_nexis.py` (demande `fonttools`
  et `uharfbuzz`), qui écrit `docs/marque/` (SVG blanc et bleu),
  `LogoBlanc.imageset` (iOS) et `drawable/logo_blanc.xml` (Android).
- **Bienvenue « Constellation »** : huit carrés de services blancs, penchés,
  qui flottent lentement sur le bleu. À l'ouverture de l'app, chacun fait une
  fois le tour de ses objets (même rythme que « Quel service ? »). Les
  positions de la maquette (écran de 390 de large) sont mises à l'échelle de
  l'écran. Rien ne bouge avec Réduire / Supprimer les animations.
- **Attente** : au lieu d'un rond qui tourne, les icônes principales des
  dix services se relaient (0,7 s chacune, fondu flou) : `PictoLoader`
  (iOS et Android). À l'ouverture de l'app (en blanc sur le bleu) et dans les
  boutons qui attendent le serveur (Recevoir le code, envoi des demandes).
  Avec Réduire les animations, une seule icône reste fixe.
- **Recevoir le code** appelle `sendCode` : l'écran n'avance qu'une fois
  l'envoi confirmé et affiche « Cela n'a pas fonctionné… » sinon. En
  démonstration, l'envoi prend 1,5 s pour que l'attente se voie.
- À faire : le texte « Envoi du code… » demandé par Ben pendant l'attente
  n'existe pas encore dans les traductions (source : les `.arb` de l'app
  Flutter) ; en attendant, le bouton montre seulement les pictogrammes,
  annoncés par VoiceOver / TalkBack avec le libellé du bouton.

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
