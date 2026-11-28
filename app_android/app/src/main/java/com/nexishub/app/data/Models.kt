package com.nexishub.app.data

import java.time.Instant
import java.time.LocalDate

/** Les neuf services de Nexis (mêmes clés que le serveur et le bot). */
enum class Service(private val fr: String, private val ln: String, private val en: String, val color: Long) {
    PLOMBERIE("Plomberie", "Plomberie", "Plumbing", 0xFF0350E6),
    ELECTRICITE("Électricité", "Kokotisa mwinda", "Electrical", 0xFFC98200),
    CLIMATISATION("Climatisation", "Climatisation", "Air conditioning", 0xFF0A84D6),
    INFORMATIQUE("Informatique", "Informatique", "IT", 0xFF021937),
    GRAPHISME("Graphisme", "Graphisme", "Graphic design", 0xFF494C95),
    COIFFURE("Coiffure", "Kosala nsuki", "Hairdressing", 0xFFC2416B),
    NETTOYAGE("Nettoyage", "Kopetola", "Cleaning", 0xFF1E8A4C),
    JARDINAGE("Jardinage", "Jardin", "Gardening", 0xFF4F8A10),
    AUTRE("Autre service", "Mosala mosusu", "Other service", 0xFF5B667A);

    /** Noms des services : les mêmes que dans le bot (FR / LN / EN). */
    fun label(language: String): String = when (language) {
        "ln" -> ln
        "en" -> en
        else -> fr
    }
}

/** États d'une mission vus par le client (mêmes valeurs que le serveur). */
enum class MissionStatus { PENDING, QUOTED, CONFIRMED, IN_PROGRESS, AWAITING_CONFIRMATION, COMPLETED, CANCELLED, DISPUTED }

/** Les six états de l'argent de la charte. */
enum class PaymentState { NONE, SECURED, RELEASED, REFUNDED, BLOCKED, AVAILABLE }

data class Mission(
    val id: Int,
    val service: Service,
    val catalogService: CatalogService? = null,
    val commune: String,
    val status: MissionStatus,
    val payment: PaymentState,
    val amount: Money? = null,
    val providerName: String? = null,
    val quotesCount: Int = 0,
    val at: Instant? = null,
    val rated: Boolean = false,
    val detail: String? = null,
    /** Le moment souhaité par le client, tel qu'il l'a écrit (« Samedi matin »). */
    val wanted: String? = null,
    /** Le devis choisi et payé (prestataire, prix, créneau). */
    val chosen: Quote? = null,
    /** Distance du prestataire en route, seulement s'il partage sa position. */
    val distanceKm: Double? = null,
    /** Heure de chaque étape franchie du suivi. */
    val steps: Map<TrackStep, Instant> = emptyMap(),
    /** Note et nombre d'avis du prestataire, tels que le serveur les donne. */
    val providerRating: Double? = null,
    val providerReviews: Int? = null,
) {
    val rating: Double? get() = chosen?.rating ?: providerRating
    val reviews: Int? get() = chosen?.reviews ?: providerReviews

    /** Prénom du prestataire, pour « Vous confirmez, Jean reçoit l'argent ». */
    val providerFirstName: String get() = chosen?.firstName ?: providerName?.split(" ")?.first().orEmpty()

    val isActive: Boolean
        get() = status !in setOf(MissionStatus.COMPLETED, MissionStatus.CANCELLED)

    val reference: String get() = "NXH-" + id.toString().padStart(4, '0')

    fun serviceName(language: String): String = catalogService?.label(language) ?: service.label(language)
}

data class Wallet(
    /** Solde disponible, par devise. */
    val available: Map<Currency, Money>,
    /** Argent payé pour des missions en cours, protégé par Nexis. */
    val secured: Map<Currency, Money>,
) {
    companion object {
        val EMPTY = Wallet(emptyMap(), emptyMap())
    }
}

enum class MovementKind { PAYMENT, REFUND, RELEASE, DEPOSIT, WITHDRAWAL }

/** Une notification de l'app : devis reçu, prestataire en route, argent
 * libéré… Le serveur les enverra ; l'aperçu n'en a aucune. */
data class AppNotification(
    val id: String,
    val title: String,
    val message: String,
    val at: Instant,
    val read: Boolean,
)

data class Movement(
    val kind: MovementKind,
    val label: String,
    val amount: Money,
    val at: Instant,
    val state: PaymentState,
)

data class Profile(
    val firstName: String,
    val lastName: String,
    val phone: String,
    val commune: String,
    /** Profil prestataire : nul pour un client seulement. */
    val providerStatus: ProviderStatus? = null,
    val termsVersion: LocalDate?,
    /** Identité déjà vérifiée (pièce et vidéo) : la personne n'est jamais revérifiée. */
    val identityVerified: Boolean = false,
) {
    /** Un prestataire vérifié, ou une personne vérifiée pour une entreprise : jamais revérifiée. */
    val isIdentityVerified: Boolean get() = providerStatus == ProviderStatus.VERIFIED || identityVerified

    val initials: String get() = (firstName.take(1) + lastName.take(1)).uppercase()

    /** Prestataire vérifié : il ouvre l'espace prestataire. */
    val isProvider: Boolean get() = providerStatus == ProviderStatus.VERIFIED
}

/** Un service du catalogue tel que le serveur le publie. L'app ne décide
 * ni de la liste, ni de qui est « nouveau », ni de l'ordre. */
data class CatalogService(
    val id: String,
    /** Nom d'origine du catalogue (français). */
    val baseName: String,
    /** Couleur du carré du service (série B), donnée par le serveur. */
    val color: Long,
    val translations: Map<String, String> = emptyMap(),
    /** Service connu de l'app (pictogramme de la police Nexis). */
    val service: Service? = null,
    val isNew: Boolean = false,
    val lastRequested: Instant? = null,
    val recommended: Boolean = false,
) {
    fun label(language: String): String =
        translations[language]?.takeIf { it.isNotBlank() } ?: service?.label(language) ?: baseName
}

/** Canal par lequel le serveur envoie le code de vérification. */
enum class CodeChannel { WHATSAPP, TELEGRAM, SMS }
