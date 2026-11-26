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

- **Bouton « + » (Android)** : « Demander un service » est un « + » compact.
  Il s'ouvre 3,5 s pour se présenter quand la personne a déjà des missions
  (5 s après l'arrivée, puis toutes les 90 s, au plus 4 fois par ouverture
  de l'app) et quand elle tape trois fois dans le vide en moins de 4 s
  (`ConfusedTapDetector`). Sans mission, la carte de l'accueil porte déjà
  le bouton. Sur iOS 26 et plus, l'action reste dans l'accessoire en verre
  au-dessus des onglets.
- **Accueil** : cloche des notifications (point rouge si une notification
  n'est pas lue) et rond du profil (initiales) en haut à droite ; le rond
  mène à l'onglet Profil. `notifications()` dans le dépôt de données ; la
  démonstration n'en a aucune, l'écran montre alors « Rien ici pour
  l'instant ».

## État

Interface seulement, avec les données fictives de l'aperçu Flutter
(`DemoRepository`) : aucun appel réseau, aucun argent. Écrans construits :
lancement, bienvenue, numéro, code, inscription (CGU obligatoires),
accueil (portefeuille, actions rapides, prestations), missions,
portefeuille (mouvements), profil (langue), « Quel service ? »,
demande de service, « Décrire mon besoin », et depuis le 2026-11-26 tous
les écrans de mission repris de Flutter :

- client : comparer les devis, payer (choix de l'opérateur), attente de
  l'opérateur, suivi (plan dessiné et étapes), confirmer, signaler un
  problème, litige en cours et décision ;
- prestataire (compte prestataire, interrupteur Client / Prestataire dans
  le profil et sur l'accueil prestataire) : accueil « En service », missions,
  envoyer un devis (prix en FC ou USD, créneaux proposés ou « Autre »),
  déroulé d'une mission (départ, arrivée confirmée par le client ou par
  son code de présence, cinq essais au plus, fin).

Une mission ouvre l'écran qui suit son état réel, comme Flutter
(`openMission`). Les écrans ne gardent que des numéros et relisent le
dépôt. Les montants viennent tous du dépôt ; l'app ne calcule pas
d'argent (le prix tapé est seulement lu, `PriceInput`, et le serveur le
revérifie). Dans un écran de mission, la barre d'onglets et l'accessoire
« Demander un service » se rangent (iOS 26.1 et plus).

Écrans du profil (2026-11-26) : mes informations (prénom, nom, commune ;
le numéro, vérifié, ne change pas ici), mes téléphones (ce téléphone, les
autres avec leur délai de 72 h avant une sortie d'argent, et « Déconnecter
ce téléphone », définitif), notifications (l'autorisation réelle du
téléphone et ce que NexisHub envoie), aide et litiges (mes litiges, questions
fréquentes tirées des règles de `CONCEPTION_ARGENT.md`), conditions
d'utilisation (versions en vigueur, date d'acceptation, lecture du texte
publié) et devenir prestataire (services, communes, pièce d'identité recto
et verso puis vidéo du visage, conditions des prestataires ; le profil reste
« en vérification » jusqu'à la décision de l'équipe).

### Preuves de réalisations (2026-11-26)

Choix de Ben : **facultatives**, et l'équipe peut en demander plus tard. La
galerie est permise pour cette étape seulement. Deuxième choix du même jour
(« c'est mieux que ces photos soient partagées aussi aux clients ») :
**l'équipe d'abord**, puis les photos d'un service approuvé et la phrase sont
montrées aux clients ; les **diplômes restent à l'équipe**, le client voit
seulement « Diplôme vérifié par NexisHub ».

- « Devenir prestataire » passe à **5 étapes** : services, **vos
  réalisations** (facultatif, « Passer cette étape »), communes, pièce
  d'identité, conditions.
- Pour chaque service choisi : 1 à 5 photos de travaux déjà faits et une
  phrase de 200 signes au plus (« Pose d'un chauffe-eau, Limete, 2025 ») ;
  plus 3 diplômes ou attestations au plus. Règles dans `Portfolio`
  (`Data/Portfolio.swift`, `data/Portfolio.kt`), testées des deux côtés.
- Choix des photos par le sélecteur du système (`PhotosPicker` sur iOS,
  Photo Picker `PickMultipleVisualMedia` sur Android, sans autorisation de
  lecture de la galerie). Chaque photo est remise à l'endroit, réduite à
  1 600 px et réencodée en JPEG : les métadonnées (lieu, appareil) partent.
- Profil → **« Mes réalisations »** (prestataire en vérification ou vérifié) :
  revoir, compléter et renvoyer. Si l'équipe a demandé des preuves, l'écran
  le dit (« L'équipe NexisHub vous demande des photos de vos travaux : … »)
  et la ligne du profil aussi.
- Décision de l'équipe par service (`ProofReview` : en attente, approuvé,
  refusé), donnée par le serveur et jamais par l'app. « Mes réalisations »
  l'affiche sur chaque service (« En attente de l'équipe », « Visible par les
  clients », « Refusé par l'équipe : envoyez d'autres photos ») et
  « Vérifié par l'équipe » sur les diplômes. Un service dont les photos ou la
  phrase changent repasse en attente et disparaît des clients jusqu'au nouvel
  accord ; des diplômes changés ne sont plus vérifiés
  (`Portfolio.resubmitted(over:)`).
- Côté client : sur la comparaison des devis, **« Voir ses réalisations »**
  quand le prestataire a au moins un service approuvé. La feuille montre ces
  services (photos, phrase), « Photos vérifiées par l'équipe NexisHub » et,
  si c'est le cas, « Diplôme vérifié par NexisHub ». Ce que voit le client
  vient de `Portfolio.showcase` (`ProviderShowcase`) : seulement l'approuvé,
  jamais un diplôme. Testé des deux côtés.
- **Figées pendant la vérification du prestataire** (choix de Ben, même
  jour) : tant que le profil est « en vérification », « Mes réalisations »
  montre ce qui a été envoyé, sans ajout, retrait ni phrase modifiable, et
  sans bouton d'envoi (« L'équipe NexisHub vérifie votre profil… »). Seule
  une demande de l'équipe rouvre l'écran. Après l'accord, elles redeviennent
  modifiables. Règle `Portfolio.isEditable`, refus `portfolio_locked` dans
  le dépôt, testés des deux côtés ; capture `portfolio-locked`.
- Conseil affiché au prestataire : éviter les visages, les adresses et les
  plaques sur les photos.
- Dépôt de données : `applyAsProvider(… portfolio:)`, `providerServices()`,
  `portfolio()`, `portfolioRequest()`, `sendPortfolio(_:)`,
  `providerShowcase(quoteId:)`.
- Captures de la CI : `become-portfolio`, `portfolio` (avec une demande de
  l'équipe et un service déjà visible), `showcase` (réalisations de Prisca
  depuis les devis), images dessinées. Textes lingala nouveaux à relire.

### Pièce d'identité et vidéo du visage (2026-11-26)

Demande de Ben : la pièce (carte d'électeur, permis…) est prise **recto puis
verso par un scanner**, et le prestataire se filme au lieu d'envoyer une
photo. **Jamais de galerie**, ni pour la pièce ni pour la vidéo. L'analyse
d'image se fait sur le téléphone et **guide seulement la prise** : c'est
l'équipe NexisHub qui vérifie la personne (exception notée dans `AGENTS.md`).

- **iOS** (`Screens/IdentityStep.swift`, `Design/IdentityCamera.swift`) :
  caméra arrière (AVFoundation), carte cherchée sur chaque image
  (`VNDetectRectanglesRequest`, format ID-1). Quand elle reste immobile
  12 images de suite (`StableCardTracker`), la photo se prend seule, la carte
  est redressée (`CIPerspectiveCorrection`) et remise à l'endroit.
- **Android** (`screens/IdentityStep.kt`) : scanner de documents de ML Kit
  (`setGalleryImportAllowed(false)`, une page, mode de base sans filtres) ;
  il détecte la carte, la cadre et la prend seul. Après le recto, l'écran dit
  « Retournez la carte » et rouvre le scanner pour le verso. Le scanner passe
  par les services Google Play : un téléphone sans eux (certains Huawei) ne
  peut pas faire cette étape, l'écran le dit.
- **Choix de la pièce** (ajouté le 2026-11-26 à 11 h 20, demande de Ben) :
  carte d'électeur, permis de conduire ou passeport, choisi avant la prise.
  Une carte se prend recto puis verso ; un **passeport, seulement la page
  avec la photo** (pas de verso). Changer de pièce efface les faces prises.
  La page du passeport est reconnue à un visage **et** à sa zone de lecture
  automatique (deux lignes de 44 signes, la première commence par `P`,
  `MachineZone`, testé), lue sur le téléphone (`VNRecognizeTextRequest` sur
  iOS, ML Kit Text Recognition sur Android). Le texte lu n'est ni gardé ni
  envoyé. Sinon : « Ce n'est pas la bonne page… ».
- **Passeport sur iPhone, revu après l'essai de Ben sur son iPhone 12**
  (2026-11-26, 21 h) : la photo ne se prenait jamais et le cadre était aussi
  petit que celui d'une carte. La page d'un passeport n'a pas de bords nets
  (pli, couverture, film brillant), donc son contour n'est plus cherché.
  Le cadre est la page **tenue sur le côté** (88 × 125), aussi grand que
  l'écran le permet, avec le contour de la page dessiné en transparence.
  La photo est prise quand un visage reste immobile dans le cadre
  (`PassportTrigger`, testé) : tout de suite si la zone de lecture est déjà
  lue, sinon après environ 2 secondes. La photo en pleine résolution est
  recadrée sur le cadre (`imageRegion`, testé), mise à l'endroit d'après le
  visage, puis revérifiée (visage et zone de lecture). Android garde le
  scanner ML Kit (non essayé par Ben pour le passeport).
- **Recto ou verso** (`CardCheck`, testé des deux côtés) : le recto porte la
  photo de la personne, donc un visage doit être vu sur la carte (Vision ou
  ML Kit, dans les quatre sens). Sinon : « C'est le verso. Montrez d'abord le
  recto… ». Le verso ne doit pas être la même image que le recto (empreinte
  `dHash` de 64 bits, comparée à l'endroit et retournée) ; sinon : « C'est
  encore le recto. Retournez la carte. ». Aperçu de chaque face avec
  « Reprendre ».
- **Vidéo du visage** (`SelfieScript`, testé des deux côtés) : caméra avant,
  **sans micro** (iOS : aucune entrée audio ; Android : pas de
  `withAudioEnabled()`, et `RECORD_AUDIO` retiré du manifeste fusionné). Les
  consignes viennent l'une après l'autre : visage dans le cercle (début de
  l'enregistrement), tourner la tête d'un côté puis de l'autre (ordre tiré au
  sort, envoyé avec la vidéo pour que l'équipe le compare), regarder devant
  soi (fin). Chaque consigne doit être tenue sur 5 images analysées. Le sens
  se lit à la position du nez dans l'image non inversée, l'angle de la tête
  sert pour l'amplitude (20° au moins). Plus de 20 s, ou visage perdu plus de
  30 images : on recommence. Deux visages : « Une seule personne… ». Vidéo
  H.264 de 2 Mbit/s, 720p au plus.
- Tout reste en mémoire jusqu'à l'envoi ; les fichiers temporaires (vidéo,
  page scannée) sont effacés dès qu'ils sont lus. Dans l'aperçu, rien ne part.
- Le dépôt de données reçoit `IdentityCapture` (type de pièce, recto ou page
  photo, verso pour une carte seulement, vidéo, durée, ordre des consignes) à
  la place de `idDocument` / `selfie`.
- **Sans appareil photo** : le simulateur iOS (et donc Appetize) joue le
  parcours avec des images dessinées, marqué « Simulateur : démonstration sans
  appareil photo ». Captures de la CI : `become-identity` (recto),
  `become-wrong-side`, `become-verso`, `become-selfie`, `become-review`,
  `become-passport`, `become-wrong-page`.
- Conception côté serveur (fichiers, conservation, suppression) : à valider
  par Ben, la durée de conservation de la vidéo est à voir avec le juriste.

Code NexisHub, Face ID et empreinte (2026-11-26, demandé par Ben) :

- juste après l'inscription, et après chaque connexion sur un téléphone,
  l'écran « Protégez votre compte » fait créer un code de 6 chiffres (tapé
  deux fois ; 111111, 123456, 121212 ou 123123 sont refusés), puis propose
  Face ID ou Touch ID (iOS) ou l'empreinte (Android) ;
- le code est demandé quand l'app revient après au moins une minute hors de
  l'écran, et **avant chaque sortie d'argent** : « Payer » et « Oui, c'est
  bien fait » (l'argent est versé au prestataire). Annuler n'envoie rien ;
- 5 codes faux de suite : le téléphone est déconnecté du compte, il faut se
  reconnecter avec un code reçu par SMS, WhatsApp ou Telegram. Le compteur
  est gardé avec le code, fermer l'app ne le remet pas à zéro. « Code
  oublié ? » déconnecte de la même façon ;
- Face ID et l'empreinte : c'est le téléphone qui reconnaît la personne,
  l'app ne reçoit qu'un oui ou un non, et rien ne sort du téléphone. Si un
  visage ou une empreinte est ajouté au téléphone après l'activation, Face ID
  ou l'empreinte est coupé et le code est redemandé (iOS : état de
  `LAContext.domainState` ; Android : clé du Keystore invalidée par tout
  ajout d'empreinte, capteurs de classe forte seulement) ;
- le code n'est jamais gardé : seulement son empreinte salée (iOS :
  PBKDF2-SHA256 dans le trousseau, lisible seulement sur ce téléphone ;
  Android : HMAC fait par une clé du Keystore qui ne sort pas du téléphone,
  fichier exclu des sauvegardes). Il part avec la session à la déconnexion ;
- quand l'app passe en arrière-plan, un cache bleu cache l'écran (et sur
  Android 13 et plus, la liste des apps ne montre pas d'image) ;
- Profil → « Code et sécurité » : Face ID ou l'empreinte, changer de code
  (l'actuel d'abord).

Reste à faire côté serveur : relier la clé du téléphone (`app_sessions.py`)
à Face ID ou à l'empreinte, pour que le serveur sache qu'une demande
d'argent a été validée par la personne.

Restent « Bientôt dans l'app » : la messagerie dans l'app (choix de Ben :
pas de numéro affiché ; elle servira à « Appeler », « Écrire » et « Écrire à
NexisHub »), photos d'une mission, ajouter un numéro Mobile Money, « Je n'ai
rien reçu », « Nous nous sommes arrangés », dépôt, retrait, mouvements et
politique de confidentialité (pas encore de document côté serveur).

### Textes

Le nom s'écrit **NexisHub** dans les textes (`.arb` de `app_mobile`, choix
de Ben du 2026-11-26). Les libellés lus par VoiceOver et TalkBack gardent
« Nexis Hub » pour être bien prononcés. Le bot Telegram et la Mini App
écrivent encore « Nexis Hub » : étape à part.

Les textes des écrans du profil ont été ajoutés aux `.arb` (puis copiés par
`outils/textes_apps_natives.py`). **Lingala à faire relire** par une
personne de Kinshasa : `nextStep`, et les clés qui commencent par `info`,
`devices`, `notif`, `help`, `faq`, `legal` (sauf `legalTerms`,
`legalPrivacy`), `become`, `providerPending`, `scan`, `camera` et `selfie`, puis `cancel`, `bioFingerprint`
et les clés qui commencent par `protect`, `lock`, `guard` et `security`. Les fichiers
`app_localizations*.dart` ne contiennent pas encore ces clés : Flutter les
régénère à la compilation (`generate: true`).

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
