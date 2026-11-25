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
) {
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
    val isProvider: Boolean,
    val termsVersion: LocalDate?,
) {
    val initials: String get() = (firstName.take(1) + lastName.take(1)).uppercase()
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
