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
        "new_quote_received_client": (
            "💬 <b>Nouveau devis reçu</b>\n\n"
            "Mission : <b>NXH-{mission_id:04d}</b>\n"
            "Prestataire : <b>{prestataire}</b>\n"
            "{trust_line}\n"
            "Montant : <b>{amount:.2f} {currency}</b>\n"
            "Délai : <b>{delay} h</b>\n"
            "Message : {message}"
        ),
        "quote_accept_confirmation": (
            "✅ <b>Devis accepté.</b>\n\n"
            "Mission : <b>NXH-{mission_id:04d}</b>\n"
            "Prestataire : <b>{prestataire}</b>\n"
            "Devis : <b>{devis:.2f} {currency}</b>\n"
            "Frais Tola / techniques : <b>{frais:.2f} {currency}</b>\n"
            "Total à payer : <b>{total:.2f} {currency}</b>\n\n"
            "👛 Solde wallet disponible : <b>{wallet_balance:.2f} {currency}</b>\n\n"
            "Choisissez un mode de paiement pour sécuriser la mission."
        ),
        "quote_accept_provider_notify": (
            "✅ <b>Votre devis a été accepté</b>\n\n"
            "Mission : <b>NXH-{mission_id:04d}</b>\n"
            "Montant : <b>{amount:.2f} {currency}</b>\n\n"
            "En attente du paiement escrow du client."
        ),
        "quote_rejected_client": (
            "❌ <b>Devis refusé.</b>\n\n"
            "Mission : <b>NXH-{mission_id:04d}</b>\n"
            "Prestataire : <b>{prestataire}</b>"
        ),
        "quote_rejected_provider_notify": (
            "❌ <b>Votre devis a été refusé</b>\n\n"
            "Mission : <b>NXH-{mission_id:04d}</b>"
        ),
        "payment_mobile_confirmed_client": (
            "✅ <b>Paiement escrow confirmé</b>\n\n"
            "Mission : <b>NXH-{mission_id:04d}</b>\n"
            "Référence paiement : <b>{ref}</b>\n"
            "Total payé : <b>{total:.2f} {currency}</b>\n"
            "Frais Tola / techniques : <b>{frais:.2f} {currency}</b>\n\n"
            "Le montant du devis est maintenant sécurisé. Le prestataire peut commencer."
        ),
        "payment_confirmed_provider_notify": (
            "💰 <b>Paiement sécurisé reçu</b>\n\n"
            "Mission : <b>NXH-{mission_id:04d}</b>\n"
            "Montant brut : <b>{brut:.2f} {currency}</b>\n"
            "Commission NEXIS HUB : <b>{commission:.2f} {currency}</b>\n"
            "Net prestataire : <b>{net:.2f} {currency}</b>\n\n"
            "Vous pouvez commencer la mission."
        ),
        "payment_wallet_confirmed_client": (
            "✅ <b>Paiement wallet confirmé</b>\n\n"
            "Mission : <b>NXH-{mission_id:04d}</b>\n"
            "Référence paiement : <b>{ref}</b>\n"
            "Total payé : <b>{total:.2f} {currency}</b>\n"
            "Frais Tola / techniques : <b>{frais:.2f} {currency}</b>\n\n"
            "Le montant du devis est maintenant sécurisé. Le prestataire peut commencer."
        ),
        "payment_wallet_confirmed_provider_notify": (
            "💰 <b>Paiement sécurisé reçu via wallet</b>\n\n"
            "Mission : <b>NXH-{mission_id:04d}</b>\n"
            "Montant brut : <b>{brut:.2f} {currency}</b>\n"
            "Commission NEXIS HUB : <b>{commission:.2f} {currency}</b>\n"
            "Net prestataire : <b>{net:.2f} {currency}</b>\n\n"
            "Vous pouvez commencer la mission."
        ),

        # ── Client : Wallet / Profil / Historique / Aide ─
        "wallet_title": (
            "👛 <b>Mon Wallet Client</b>\n\n"
            "Solde USD : <b>{usd:.2f} USD</b>\n"
            "Solde CDF : <b>{cdf:.2f} CDF</b>\n\n"
            "Le rechargement wallet sera ajouté avec la vraie API Mobile Money."
        ),
        "profile_title": (
            "👤 <b>Mon profil client</b>\n\n"
            "Nom : <b>{name}</b>\n"
            "Téléphone : <b>{phone}</b>\n"
            "Langue : <b>{lang_label}</b>\n"
            "Missions totales : <b>{missions}</b>"
        ),
        "missions_title": "📋 <b>Mes dernières missions</b>",
        "missions_empty": (
            "📋 <b>Mes missions en cours</b>\n\n"
            "Vous n'avez pas encore de mission enregistrée."
        ),
        "mission_history_title": "🗂️ <b>Historique de mes missions</b>",
        "mission_history_empty": (
            "🗂️ <b>Historique de mes missions</b>\n\n"
            "Aucune mission terminée pour le moment."
        ),
        "help_content": (
            "❓ <b>Aide & Support</b>\n\n"
            "🔹 <b>Comment ça marche ?</b>\n"
            "Décrivez votre besoin, recevez des devis de prestataires vérifiés, "
            "payez en toute sécurité via l'escrow NEXIS HUB — l'argent n'est "
            "libéré au prestataire qu'après votre confirmation.\n\n"
            "🔹 <b>Le paiement est-il sécurisé ?</b>\n"
            "Oui. Vos fonds restent bloqués tant que vous n'avez pas confirmé "
            "que la mission est bien terminée.\n\n"
            "🔹 <b>Un problème avec une mission ?</b>\n"
            "Utilisez le bouton de signalement depuis la mission concernée, "
            "ou contactez-nous directement.\n\n"
            "📱 Contactez-nous : +243 852 638 209"
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
        "rate_comment_prompt": (
            "✍️ Voulez-vous ajouter un commentaire ?\n\n"
            "Envoyez votre commentaire, ou appuyez sur le bouton pour l'envoyer sans commentaire."
        ),
        "rate_skipped": "👍 D'accord, merci quand même d'avoir utilisé NEXIS HUB !",
        "rate_thanks": "🙏 Merci pour votre évaluation !",

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

        # ── Mission en cours ────────────────────────────
        "mission_started": (
            "▶️ <b>Mission ebandi !</b>\n\n"
            "Mission : <b>NXH-{mission_id:04d}</b>\n"
            "Mosali abandi mosala."
        ),
        "mission_finished_client": (
            "✅ <b>Mosali alobi asilisi</b>\n\n"
            "Mission : <b>NXH-{mission_id:04d}</b>\n\n"
            "Mosala esili malamu mpe olingi yango ?\n"
            "Paiement ekokoma epai ya mosali soki ondimi."
        ),
        "payment_released_client": (
            "✅ <b>Mission endimami !</b>\n\n"
            "Mission : <b>NXH-{mission_id:04d}</b>\n"
            "Paiement ekomi epai ya mosali.\n\n"
            "Matondi mpo osaleli NEXIS HUB ! 🙏"
        ),
        "payment_released_provider": (
            "💸 <b>Paiement ekomi !</b>\n\n"
            "Mission : <b>NXH-{mission_id:04d}</b>\n"
            "Mbongo ebakisami na wallet na yo : "
            "<b>{net} {currency}</b>\n\n"
            "Koba boye ! 💪"
        ),
        "dispute_opened": (
            "⚠️ <b>Problème esakolami</b>\n\n"
            "Mission : <b>NXH-{mission_id:04d}</b>\n\n"
            "Paiement ekotikala na escrow.\n"
            "Ekipe na biso ekobenga yo na se ya 48h."
        ),

        # ── Devis & Paiement (client) ───────────────────
        "new_quote_received_client": (
            "💬 <b>Devis ya sika eyei</b>\n\n"
            "Mission : <b>NXH-{mission_id:04d}</b>\n"
            "Mosali : <b>{prestataire}</b>\n"
            "{trust_line}\n"
            "Mbongo : <b>{amount:.2f} {currency}</b>\n"
            "Délai : <b>{delay} h</b>\n"
            "Message : {message}"
        ),
        "quote_accept_confirmation": (
            "✅ <b>Devis endimami.</b>\n\n"
            "Mission : <b>NXH-{mission_id:04d}</b>\n"
            "Mosali : <b>{prestataire}</b>\n"
            "Devis : <b>{devis:.2f} {currency}</b>\n"
            "Frais Tola : <b>{frais:.2f} {currency}</b>\n"
            "Total ya kofuta : <b>{total:.2f} {currency}</b>\n\n"
            "👛 Solde ya wallet : <b>{wallet_balance:.2f} {currency}</b>\n\n"
            "Pona ndenge ya kofuta mpo na kobatela mission."
        ),
        "quote_accept_provider_notify": (
            "✅ <b>Devis na yo endimami</b>\n\n"
            "Mission : <b>NXH-{mission_id:04d}</b>\n"
            "Mbongo : <b>{amount:.2f} {currency}</b>\n\n"
            "Ozali kozela paiement escrow ya client."
        ),
        "quote_rejected_client": (
            "❌ <b>Devis eboyami.</b>\n\n"
            "Mission : <b>NXH-{mission_id:04d}</b>\n"
            "Mosali : <b>{prestataire}</b>"
        ),
        "quote_rejected_provider_notify": (
            "❌ <b>Devis na yo eboyami</b>\n\n"
            "Mission : <b>NXH-{mission_id:04d}</b>"
        ),
        "payment_mobile_confirmed_client": (
            "✅ <b>Paiement escrow endimami</b>\n\n"
            "Mission : <b>NXH-{mission_id:04d}</b>\n"
            "Référence : <b>{ref}</b>\n"
            "Total efutami : <b>{total:.2f} {currency}</b>\n"
            "Frais Tola : <b>{frais:.2f} {currency}</b>\n\n"
            "Mbongo ya devis ebombami sikoyo. Mosali akoki kobanda."
        ),
        "payment_confirmed_provider_notify": (
            "💰 <b>Paiement eyei na sécurité</b>\n\n"
            "Mission : <b>NXH-{mission_id:04d}</b>\n"
            "Mbongo brut : <b>{brut:.2f} {currency}</b>\n"
            "Commission NEXIS HUB : <b>{commission:.2f} {currency}</b>\n"
            "Net na yo : <b>{net:.2f} {currency}</b>\n\n"
            "Okoki kobanda mission."
        ),
        "payment_wallet_confirmed_client": (
            "✅ <b>Paiement wallet endimami</b>\n\n"
            "Mission : <b>NXH-{mission_id:04d}</b>\n"
            "Référence : <b>{ref}</b>\n"
            "Total efutami : <b>{total:.2f} {currency}</b>\n"
            "Frais Tola : <b>{frais:.2f} {currency}</b>\n\n"
            "Mbongo ya devis ebombami sikoyo. Mosali akoki kobanda."
        ),
        "payment_wallet_confirmed_provider_notify": (
            "💰 <b>Paiement eyei na sécurité na wallet</b>\n\n"
            "Mission : <b>NXH-{mission_id:04d}</b>\n"
            "Mbongo brut : <b>{brut:.2f} {currency}</b>\n"
            "Commission NEXIS HUB : <b>{commission:.2f} {currency}</b>\n"
            "Net na yo : <b>{net:.2f} {currency}</b>\n\n"
            "Okoki kobanda mission."
        ),

        # ── Client : Wallet / Profil / Historique / Aide ─
        "wallet_title": (
            "👛 <b>Wallet na yo ya client</b>\n\n"
            "Solde USD : <b>{usd:.2f} USD</b>\n"
            "Solde CDF : <b>{cdf:.2f} CDF</b>\n\n"
            "Kotia mbongo na wallet ekoya na API Mobile Money ya solo."
        ),
        "profile_title": (
            "👤 <b>Profil na yo ya client</b>\n\n"
            "Kombo : <b>{name}</b>\n"
            "Numéro : <b>{phone}</b>\n"
            "Monoko : <b>{lang_label}</b>\n"
            "Misala nyonso : <b>{missions}</b>"
        ),
        "missions_title": "📋 <b>Misala na ngai ya sika</b>",
        "missions_empty": (
            "📋 <b>Misala na ngai</b>\n\n"
            "Ozali naino na mission te."
        ),
        "mission_history_title": "🗂️ <b>Istware ya misala na ngai</b>",
        "mission_history_empty": (
            "🗂️ <b>Istware ya misala na ngai</b>\n\n"
            "Mission moko te esili naino."
        ),
        "help_content": (
            "❓ <b>Lisungi & Support</b>\n\n"
            "🔹 <b>Ezali kosala ndenge nini ?</b>\n"
            "Limbola bosengi na yo, zwa ba devis ya ba prestataire ba vérifié, "
            "futa na sécurité na système escrow ya NEXIS HUB — mbongo ekokoma "
            "epai ya mosali kaka soki ondimi mission esili.\n\n"
            "🔹 <b>Paiement ezali sûr ?</b>\n"
            "Iyo. Mbongo na yo ekotikala kino okondima que mission esili malamu.\n\n"
            "🔹 <b>Problème na mission ?</b>\n"
            "Salela bouton ya kosakola litige na mission wana, "
            "to benga biso directement.\n\n"
            "📱 Benga biso : +243 852 638 209"
        ),

        # ── Notation ───────────────────────────────────
        "rate_provider": (
            "⭐ <b>Pesa note na mosali na yo</b>\n\n"
            "Mosala : <b>NXH-{mission_id:04d}</b>\n"
            "Mosali : <b>{prestataire}</b>\n\n"
            "💡 Avis na yo esungaka baklienti mosusu "
            "kopona na confiance."
        ),
        "rate_comment_prompt": (
            "✍️ Olingi kobakisa commentaire ?\n\n"
            "Tinda commentaire na yo, to finá bouton mpo na kotinda sans commentaire."
        ),
        "rate_skipped": "👍 Malamu, matondi mpo osaleli NEXIS HUB !",
        "rate_thanks": "🙏 Matondi mpo na note na yo !",

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

        # ── Mission in progress ──────────────────────────
        "mission_started": (
            "▶️ <b>Mission started!</b>\n\n"
            "Mission: <b>NXH-{mission_id:04d}</b>\n"
            "The provider has started the work."
        ),
        "mission_finished_client": (
            "✅ <b>The provider marked this as finished</b>\n\n"
            "Mission: <b>NXH-{mission_id:04d}</b>\n\n"
            "Is the work properly done and satisfactory?\n"
            "Payment will be released after your confirmation."
        ),
        "payment_released_client": (
            "✅ <b>Mission confirmed!</b>\n\n"
            "Mission: <b>NXH-{mission_id:04d}</b>\n"
            "The payment has been released to the provider.\n\n"
            "Thank you for using NEXIS HUB! 🙏"
        ),
        "payment_released_provider": (
            "💸 <b>Payment released!</b>\n\n"
            "Mission: <b>NXH-{mission_id:04d}</b>\n"
            "Amount added to your wallet: "
            "<b>{net} {currency}</b>\n\n"
            "Keep it up! 💪"
        ),
        "dispute_opened": (
            "⚠️ <b>Issue reported</b>\n\n"
            "Mission: <b>NXH-{mission_id:04d}</b>\n\n"
            "The payment stays held in escrow.\n"
            "Our team will contact you within 48h."
        ),

        # ── Quote & Payment (client) ─────────────────────
        "new_quote_received_client": (
            "💬 <b>New quote received</b>\n\n"
            "Mission: <b>NXH-{mission_id:04d}</b>\n"
            "Provider: <b>{prestataire}</b>\n"
            "{trust_line}\n"
            "Amount: <b>{amount:.2f} {currency}</b>\n"
            "Delay: <b>{delay} h</b>\n"
            "Message: {message}"
        ),
        "quote_accept_confirmation": (
            "✅ <b>Quote accepted.</b>\n\n"
            "Mission: <b>NXH-{mission_id:04d}</b>\n"
            "Provider: <b>{prestataire}</b>\n"
            "Quote: <b>{devis:.2f} {currency}</b>\n"
            "Tola / technical fees: <b>{frais:.2f} {currency}</b>\n"
            "Total to pay: <b>{total:.2f} {currency}</b>\n\n"
            "👛 Available wallet balance: <b>{wallet_balance:.2f} {currency}</b>\n\n"
            "Choose a payment method to secure the mission."
        ),
        "quote_accept_provider_notify": (
            "✅ <b>Your quote was accepted</b>\n\n"
            "Mission: <b>NXH-{mission_id:04d}</b>\n"
            "Amount: <b>{amount:.2f} {currency}</b>\n\n"
            "Waiting for the client's escrow payment."
        ),
        "quote_rejected_client": (
            "❌ <b>Quote rejected.</b>\n\n"
            "Mission: <b>NXH-{mission_id:04d}</b>\n"
            "Provider: <b>{prestataire}</b>"
        ),
        "quote_rejected_provider_notify": (
            "❌ <b>Your quote was rejected</b>\n\n"
            "Mission: <b>NXH-{mission_id:04d}</b>"
        ),
        "payment_mobile_confirmed_client": (
            "✅ <b>Escrow payment confirmed</b>\n\n"
            "Mission: <b>NXH-{mission_id:04d}</b>\n"
            "Payment reference: <b>{ref}</b>\n"
            "Total paid: <b>{total:.2f} {currency}</b>\n"
            "Tola / technical fees: <b>{frais:.2f} {currency}</b>\n\n"
            "The quote amount is now secured. The provider can start."
        ),
        "payment_confirmed_provider_notify": (
            "💰 <b>Secure payment received</b>\n\n"
            "Mission: <b>NXH-{mission_id:04d}</b>\n"
            "Gross amount: <b>{brut:.2f} {currency}</b>\n"
            "NEXIS HUB commission: <b>{commission:.2f} {currency}</b>\n"
            "Your net: <b>{net:.2f} {currency}</b>\n\n"
            "You can start the mission."
        ),
        "payment_wallet_confirmed_client": (
            "✅ <b>Wallet payment confirmed</b>\n\n"
            "Mission: <b>NXH-{mission_id:04d}</b>\n"
            "Payment reference: <b>{ref}</b>\n"
            "Total paid: <b>{total:.2f} {currency}</b>\n"
            "Tola / technical fees: <b>{frais:.2f} {currency}</b>\n\n"
            "The quote amount is now secured. The provider can start."
        ),
        "payment_wallet_confirmed_provider_notify": (
            "💰 <b>Secure payment received via wallet</b>\n\n"
            "Mission: <b>NXH-{mission_id:04d}</b>\n"
            "Gross amount: <b>{brut:.2f} {currency}</b>\n"
            "NEXIS HUB commission: <b>{commission:.2f} {currency}</b>\n"
            "Your net: <b>{net:.2f} {currency}</b>\n\n"
            "You can start the mission."
        ),

        # ── Client: Wallet / Profile / History / Help ────
        "wallet_title": (
            "👛 <b>My Client Wallet</b>\n\n"
            "USD balance: <b>{usd:.2f} USD</b>\n"
            "CDF balance: <b>{cdf:.2f} CDF</b>\n\n"
            "Wallet top-up will be added with the real Mobile Money API."
        ),
        "profile_title": (
            "👤 <b>My Client Profile</b>\n\n"
            "Name: <b>{name}</b>\n"
            "Phone: <b>{phone}</b>\n"
            "Language: <b>{lang_label}</b>\n"
            "Total missions: <b>{missions}</b>"
        ),
        "missions_title": "📋 <b>My recent missions</b>",
        "missions_empty": (
            "📋 <b>My missions</b>\n\n"
            "You don't have any registered mission yet."
        ),
        "mission_history_title": "🗂️ <b>My mission history</b>",
        "mission_history_empty": (
            "🗂️ <b>My mission history</b>\n\n"
            "No completed mission yet."
        ),
        "help_content": (
            "❓ <b>Help & Support</b>\n\n"
            "🔹 <b>How does it work?</b>\n"
            "Describe your need, receive quotes from verified providers, "
            "pay securely through the NEXIS HUB escrow — funds are only "
            "released to the provider after your confirmation.\n\n"
            "🔹 <b>Is payment secure?</b>\n"
            "Yes. Your funds stay held until you confirm the mission is "
            "properly completed.\n\n"
            "🔹 <b>Problem with a mission?</b>\n"
            "Use the report button on the mission in question, "
            "or contact us directly.\n\n"
            "📱 Contact us: +243 852 638 209"
        ),

        # ── Rating ───────────────────────────────────
        "rate_provider": (
            "⭐ <b>Rate your provider</b>\n\n"
            "Mission: <b>NXH-{mission_id:04d}</b>\n"
            "Provider: <b>{prestataire}</b>\n\n"
            "💡 Your feedback helps other clients "
            "choose with confidence."
        ),
        "rate_comment_prompt": (
            "✍️ Would you like to add a comment?\n\n"
            "Send your comment, or tap the button to send without one."
        ),
        "rate_skipped": "👍 Alright, thanks anyway for using NEXIS HUB!",
        "rate_thanks": "🙏 Thank you for your rating!",

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
