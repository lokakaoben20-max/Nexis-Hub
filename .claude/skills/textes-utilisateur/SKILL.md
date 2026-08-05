---
name: textes-utilisateur
description: À utiliser dès qu'un texte visible par un utilisateur est ajouté ou modifié dans le bot Telegram ou la Mini App — message, titre d'écran, libellé de bouton, confirmation, message d'erreur, notification. Le bot est trilingue (français, lingala, anglais) et le piège récurrent est d'écrire le texte en dur dans main.py au lieu de passer par les fichiers de traduction, ou de figer "fr" alors que la langue de l'utilisateur est disponible.
---

# Textes visibles par l'utilisateur — Nexis Hub

Le bot parle **français, lingala et anglais**. Un texte écrit en dur s'affiche en
français à tout le monde — et personne ne s'en plaint, parce que les
utilisateurs supposent que c'est normal. C'est l'erreur la plus fréquente sur ce
projet.

## Où vivent les textes

- `translations/fr.json`, `translations/ln.json`, `translations/en.json` — le
  contenu. **Éditables à la main par l'utilisateur** (il est locuteur lingala
  natif et corrige lui-même ces fichiers).
- `messages.py` — charge simplement les JSON et expose `get_message()`. Ne pas y
  remettre de texte.

## La règle

```python
# NON — invisible pour un utilisateur lingala ou anglophone
await callback.message.edit_text("✅ Devis accepté.")

# NON — la langue est disponible mais ignorée
lang = await get_user_language(callback.from_user.id)
await callback.message.edit_text(get_message("quote_accepted", "fr"))

# OUI
lang = await get_user_language(callback.from_user.id)
await callback.message.edit_text(get_message("quote_accepted", lang))
```

Résoudre la langue avec la bonne fonction selon le destinataire :

- client → `await get_user_language(telegram_id)`
- prestataire → `await get_provider_language(telegram_id)`

Attention aux handlers qui notifient **deux personnes** : le client et le
prestataire n'ont pas forcément la même langue, il faut résoudre les deux
séparément (piège déjà rencontré dans `client_accepte_devis`,
`paiement_mobile_money`, `client_confirme_mission_terminee`).

## Ajouter une clé

Ajouter la clé dans **les trois** fichiers, pas seulement `fr.json`. Une clé
absente ne provoque aucune erreur : `get_message()` retombe silencieusement sur
le français.

Vérifier la parité après coup :

```bash
.venv/Scripts/python.exe -c "
import json
langs={l:set(json.load(open(f'translations/{l}.json',encoding='utf-8'))) for l in ('fr','ln','en')}
for l in ('ln','en'):
    manquant=sorted(langs['fr']-langs[l])
    print(l,':',len(manquant),'manquante(s)',manquant if manquant else '')
"
```

Contraintes de format à respecter en éditant les JSON :

- ne pas renommer les clés
- garder les `{placeholders}` intacts, y compris leur format
  (`{montant:.2f}`, `{mission_id:04d}`)
- `\n` = saut de ligne, `<b></b>` = gras (Telegram HTML)

## Traductions lingala

Écrire une proposition raisonnable en suivant le ton des clés voisines, puis
**signaler à l'utilisateur** que la traduction lingala est à relire — il est
natif, pas moi. Ne pas présenter une traduction inventée comme validée.

## Ce qui reste volontairement non traduit

- Les libellés de `SERVICES`, `STATUS_LABELS`, `PAYMENT_STATUS_LABELS`
  (`main.py`) — partagés avec les écrans prestataire et admin, chantier séparé.
- Les 5 toasts admin (`callback.answer(...)` dans les handlers `admin_*`) — il
  n'existe pas de préférence de langue par administrateur.

Ne pas « corriger » ces cas sans le demander : ce sont des décisions prises, pas
des oublis.
