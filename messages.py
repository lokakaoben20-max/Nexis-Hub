# ═══════════════════════════════════════════════════════
# NEXIS HUB — Messages Système Officiels
# Français / Lingala / English
# ═══════════════════════════════════════════════════════

MESSAGES = {
    "fr": {
        # ── Accueil ────────────────────────────────────
        "welcome": (
            "👋 Bienvenue sur <b>NEXIS HUB</b> !\n"
            "<i>WHERE TRUST MEETS SERVICE</i>\n\n"
            "Choisissez votre langue :"
        ),
        "choose_profile": (
            "Vous êtes :"
        ),

        # ── Client ─────────────────────────────────────
        "client_menu": (
            "🏠 <b>Espace Client — {prenom}</b>\n\n"
            "Que souhaitez-vous faire ?"
        ),
        "choose_service": (
            "🔍 <b>Quel service vous faut-il ?</b>\n\n"
            "Choisissez une catégorie :"
        ),
        "is_urgent": (
            "✅ Service choisi : <b>{service}</b>\n\n"
            "⚡ Est-ce urgent ?"
        ),
        "choose_commune": (
            "📍 Dans quelle <b>commune</b> êtes-vous ?"
        ),
        "choose_currency": (
            "💵 Quelle devise préférez-vous pour le paiement ?"
        ),
        "describe_problem": (
            "✏️ Décrivez votre problème.\n\n"
            "Vous pouvez envoyer un <b>texte</b>, une <b>note vocale</b> "
            "ou une/des <b>photos</b>.\n\n"
            "Quand tout est ajouté, appuyez sur <b>Terminer</b>."
        ),
        "mission_summary": (
            "📋 <b>Récapitulatif de votre demande</b>\n\n"
            "Service : <b>{service}</b>\n"
            "Urgence : <b>{urgent}</b>\n"
            "Commune : <b>{commune}</b>\n"
            "Devise : <b>{currency}</b>\n"
            "Description : <b>{description}</b>\n\n"
            "Confirmez-vous cette demande ?"
        ),
        "searching_providers": (
            "🔍 Recherche des meilleurs prestataires "
            "disponibles dans votre zone...\n\n"
            "⏳ Veuillez patienter."
        ),
        "no_providers": (
            "😔 <b>Aucun prestataire disponible</b>\n\n"
            "Aucun prestataire n'est disponible dans votre "
            "commune pour ce service actuellement.\n\n"
            "Réessayez plus tard ou contactez-nous :\n"
            "📱 +243 852 638 209"
        ),
        "providers_found": (
            "✅ <b>{count} prestataire(s) disponible(s) !</b>\n\n"
            "Comparez les profils et choisissez :"
        ),
        "provider_card": (
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "👤 <b>{nom}</b>  |  🏅 {badge}\n"
            "⭐ {note}/5  —  {missions} missions\n"
            "📍 Zone : <b>{commune}</b>\n"
            "🗣 Langues : <b>{langues}</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━"
        ),

        # ── Paiement ───────────────────────────────────
        "payment_summary": (
            "💳 <b>Récapitulatif du paiement</b>\n\n"
            "Prestataire : <b>{prestataire}</b>\n"
            "Service : <b>{service}</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "Devis prestataire  : <b>{devis} {currency}</b>\n"
            "Frais techniques   : <b>{frais} {currency}</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "💳 TOTAL À PAYER   : <b>{total} {currency}</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "🛡 <i>Vos fonds sont sécurisés. Ne traitez "
            "jamais en dehors de ce bot.</i>"
        ),
        "payment_confirmed": (
            "✅ <b>Paiement reçu et sécurisé !</b>\n\n"
            "Mission : <b>NXH-{mission_id:04d}</b>\n"
            "Prestataire : <b>{prestataire}</b>\n\n"
            "Votre prestataire a été notifié. "
            "Suivez l'avancement ici."
        ),

        # ── Anti-désintermédiation ──────────────────────
        "anti_bypass_warning": (
            "🛡 <b>Rappel important</b>\n\n"
            "Pour conserver votre <b>Garantie NEXIS HUB</b>, "
            "effectuez toujours vos transactions via ce bot.\n\n"
            "Sortir de la plateforme annule votre protection."
        ),
        "bypass_signal": (
            "🚨 <b>Le prestataire vous propose de payer "
            "ailleurs ?</b>\n\n"
            "Signalez-le pour recevoir un <b>bonus</b> "
            "sur votre Wallet NEXIS HUB.\n\n"
            "Votre signalement sera traité dans les "
            "15 minutes."
        ),

        # ── Mission en cours ────────────────────────────
        "mission_started": (
            "▶️ <b>Mission démarrée !</b>\n\n"
            "Mission : <b>NXH-{mission_id:04d}</b>\n"
            "Le prestataire a commencé le travail."
        ),
        "mission_finished_client": (
            "✅ <b>Le prestataire indique avoir terminé</b>\n\n"
            "Mission : <b>NXH-{mission_id:04d}</b>\n\n"
            "Le travail est-il bien terminé et satisfaisant ?\n"
            "Le paiement sera libéré après votre confirmation."
        ),
        "payment_released_client": (
            "✅ <b>Mission confirmée !</b>\n\n"
            "Mission : <b>NXH-{mission_id:04d}</b>\n"
            "Le paiement a été libéré au prestataire.\n\n"
            "Merci d'avoir utilisé NEXIS HUB ! 🙏"
        ),
        "dispute_opened": (
            "⚠️ <b>Problème signalé</b>\n\n"
            "Mission : <b>NXH-{mission_id:04d}</b>\n\n"
            "Le paiement reste bloqué en escrow.\n"
            "Notre équipe vous contacte dans les 48h."
        ),

        # ── Notation ───────────────────────────────────
        "rate_provider": (
            "⭐ <b>Évaluez votre prestataire</b>\n\n"
            "Mission : <b>NXH-{mission_id:04d}</b>\n"
            "Prestataire : <b>{prestataire}</b>\n\n"
            "💡 Votre avis aide les autres clients "
            "à choisir en confiance."
        ),

        # ── Prestataire ─────────────────────────────────
        "provider_menu": (
            "🔧 <b>Tableau de bord — {prenom}</b>\n\n"
            "🏅 Badge : <b>{badge}</b>\n"
            "⭐ Note : <b>{note}/5</b>\n"
            "📊 Missions : <b>{missions}</b>\n"
            "🟢 Statut : <b>{statut}</b>"
        ),
        "new_mission_alert": (
            "🔔 <b>Nouvelle demande !</b>\n\n"
            "Mission : <b>NXH-{mission_id:04d}</b>\n"
            "Service : <b>{service}</b>\n"
            "Commune : <b>{commune}</b>\n"
            "Urgence : <b>{urgent}</b>\n\n"
            "⏰ Vous avez <b>20 minutes</b> pour répondre."
        ),
        "quote_accepted_provider": (
            "🎉 <b>Votre devis a été accepté !</b>\n\n"
            "Mission : <b>NXH-{mission_id:04d}</b>\n"
            "Client : <b>{client}</b>\n"
            "Commune : <b>{commune}</b>\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "Montant brut     : <b>{brut} {currency}</b>\n"
            "Commission NEXIS : <b>{commission} {currency}</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "💳 Votre net     : <b>{net} {currency}</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "🛡 <i>Ne demandez jamais au client de payer "
            "en dehors du bot.</i>"
        ),
        "payment_released_provider": (
            "💸 <b>Paiement libéré !</b>\n\n"
            "Mission : <b>NXH-{mission_id:04d}</b>\n"
            "Montant ajouté à votre wallet : "
            "<b>{net} {currency}</b>\n\n"
            "Continuez comme ça ! 💪"
        ),
        "provider_ignored_warning": (
            "⏰ <b>Demande expirée</b>\n\n"
            "Vous n'avez pas répondu à temps.\n"
            "La demande a été transmise à un autre prestataire.\n\n"
            "Restez réactif pour ne pas manquer "
            "vos opportunités !"
        ),
        "provider_paused": (
            "⚠️ <b>Votre profil est en pause</b>\n\n"
            "Vous n'avez pas répondu à 3 demandes consécutives.\n\n"
            "Êtes-vous disponible ?"
        ),
    },

    "ln": {
        "welcome": (
            "👋 <b>Boyei malamu na NEXIS HUB !</b>\n"
            "<i>WHERE TRUST MEETS SERVICE</i>\n\n"
            "Pona elobeli na yo :"
        ),
        "choose_profile": "Ozali nani ?",
        "client_menu": (
            "🏠 <b>Esika ya mosengi mosala — {prenom}</b>\n\n"
            "Olingi kosala nini ?"
        ),
        "ask_client_phone": (
            "📱 Tinda numéro WhatsApp na yo.\n\n"
            "Okoki kofina bouton awa na se to kokoma numéro na format +243..."
        ),
        "phone_required": (
            "Tinda to koma numéro WhatsApp na yo mpo tokoba."
        ),
        "client_registered": (
            "✅ Inscription client na yo esili."
        ),
        "ask_provider_phone": (
            "🔧 Tosala profil na yo ya prestataire.\n\n"
            "Tinda numéro WhatsApp na yo."
        ),
        "provider_phone_saved": (
            "✅ Numéro ekotisami.\n\n"
            "Koma kombo na yo mobimba to kombo ya activité na yo."
        ),
        "provider_choose_services": (
            "🧰 Services nini opesaka ?\n\n"
            "Okoki kopona ebele, sima fina Continuer."
        ),
        "choose_one_service": (
            "Pona ata service moko."
        ),
        "provider_choose_communes": (
            "📍 Na communes nini okoki kosala ?\n\n"
            "Okoki kopona ebele."
        ),
        "choose_one_commune": (
            "Pona ata commune moko."
        ),
        "provider_registered": (
            "✅ <b>Profil prestataire esalemi.</b>\n\n"
            "Statut : <b>{status}</b>\n"
            "Badge : <b>{badge}</b>\n\n"
            "Profil na yo ebombami. Validation admin mpe matching ekoya sima."
        ),
        "choose_service": (
            "🔍 <b>Mosala nini ozoluka ?</b>\n\n"
            "Pona kategorie :"
        ),
        "is_urgent": (
            "✅ Service oponi : <b>{service}</b>\n\n"
            "⚡ Ezali likambo ya lombangu ?"
        ),
        "choose_commune": (
            "📍 Ozali na commune nini ?"
        ),
        "choose_currency": (
            "💵 Olingi kofuta na devise nini ?"
        ),
        "describe_problem": (
            "✏️ Limbola problème na yo.\n\n"
            "Okoki kotinda <b>texte</b>, <b>note vocale</b> "
            "to <b>photo</b> moko to ebele.\n\n"
            "Soki osilisi, fina <b>Nasilisi</b>."
        ),
        "explanation_saved_photo_prompt": (
            "✅ Explication ebombami.\n\n"
            "📷 Okoki kotinda photo ya problème soki esengeli.\n\n"
            "Soki te, koba sans photo."
        ),
        "photo_required_or_skip": (
            "Tinda photo to koba sans photo."
        ),
        "mission_saved": (
            "✅ <b>Demande ebombami.</b>\n\n"
            "Référence mission : <b>NXH-{mission_id:04d}</b>\n\n"
            "{matching_text}"
        ),
        "mission_summary": (
            "📋 <b>Na mokuse na yo</b>\n\n"
            "Service : <b>{service}</b>\n"
            "Urgence : <b>{urgent}</b>\n"
            "Commune : <b>{commune}</b>\n"
            "Devise : <b>{currency}</b>\n"
            "Description : <b>{description}</b>\n\n"
            "Ondimi bosengi oyo ?"
        ),
        "no_providers": (
            "😔 <b>Moto te oyo akoki kosalela yo</b>\n\n"
            "Benga biso : 📱 +243 852 638 209"
        ),
        "payment_summary": (
            "💳 <b>Recap ya lisusu</b>\n\n"
            "Mosali : <b>{prestataire}</b>\n"
            "Mosala : <b>{service}</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "Devis    : <b>{devis} {currency}</b>\n"
            "Frais    : <b>{frais} {currency}</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "💳 TOTAL : <b>{total} {currency}</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━"
        ),
        "provider_menu": (
            "🔧 <b>Tableau ya mosali — {prenom}</b>\n\n"
            "🏅 Badge : <b>{badge}</b>\n"
            "⭐ Note : <b>{note}/5</b>\n"
            "📊 Misala : <b>{missions}</b>\n"
            "🟢 Statut : <b>{statut}</b>"
        ),
        "anti_bypass_warning": (
            "🛡 <b>Tika kozwa mbongo libanda ya bot oyo</b>\n\n"
            "Soki ozali kosala bongo, okobungisa garantie "
            "ya NEXIS HUB."
        ),
    },

    "en": {
        "welcome": (
            "👋 Welcome to <b>NEXIS HUB</b>!\n"
            "<i>WHERE TRUST MEETS SERVICE</i>\n\n"
            "Choose your language:"
        ),
        "choose_profile": "You are:",
        "client_menu": (
            "🏠 <b>Client Space — {prenom}</b>\n\n"
            "What would you like to do?"
        ),
        "choose_service": (
            "🔍 <b>What service do you need?</b>\n\n"
            "Choose a category:"
        ),
        "is_urgent": (
            "✅ Selected service: <b>{service}</b>\n\n"
            "⚡ Is it urgent?"
        ),
        "choose_commune": (
            "📍 Which <b>commune</b> are you in?"
        ),
        "choose_currency": (
            "💵 Which payment currency do you prefer?"
        ),
        "describe_problem": (
            "✏️ Describe your issue.\n\n"
            "You can send <b>text</b>, a <b>voice note</b> "
            "or one/more <b>photos</b>.\n\n"
            "When everything is added, press <b>Finish</b>."
        ),
        "mission_summary": (
            "📋 <b>Request summary</b>\n\n"
            "Service: <b>{service}</b>\n"
            "Urgent: <b>{urgent}</b>\n"
            "Commune: <b>{commune}</b>\n"
            "Currency: <b>{currency}</b>\n"
            "Description: <b>{description}</b>\n\n"
            "Do you confirm this request?"
        ),
        "no_providers": (
            "😔 <b>No provider available</b>\n\n"
            "No provider is available in your area "
            "for this service.\n\n"
            "Contact us: 📱 +243 852 638 209"
        ),
        "payment_summary": (
            "💳 <b>Payment Summary</b>\n\n"
            "Provider: <b>{prestataire}</b>\n"
            "Service: <b>{service}</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "Quote     : <b>{devis} {currency}</b>\n"
            "Tech fees : <b>{frais} {currency}</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "💳 TOTAL  : <b>{total} {currency}</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━"
        ),
        "provider_menu": (
            "🔧 <b>Provider Dashboard — {prenom}</b>\n\n"
            "🏅 Badge: <b>{badge}</b>\n"
            "⭐ Rating: <b>{note}/5</b>\n"
            "📊 Missions: <b>{missions}</b>\n"
            "🟢 Status: <b>{statut}</b>"
        ),
        "anti_bypass_warning": (
            "🛡 <b>Important reminder</b>\n\n"
            "To keep your <b>NEXIS HUB Guarantee</b>, "
            "always transact through this bot."
        ),
    }
}


def get_message(key: str, lang: str = "fr", **kwargs) -> str:
    """
    Récupère un message dans la bonne langue.
    Si la clé n'existe pas dans la langue choisie,
    retourne le message en français par défaut.
    """
    msg = MESSAGES.get(lang, MESSAGES["fr"]).get(
        key,
        MESSAGES["fr"].get(key, f"[Message manquant : {key}]")
    )
    if kwargs:
        try:
            return msg.format(**kwargs)
        except KeyError:
            return msg
    return msg
