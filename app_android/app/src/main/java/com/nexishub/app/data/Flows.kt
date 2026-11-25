package com.nexishub.app.data

import java.time.Instant

/** Les étapes du suivi d'une mission payée. */
enum class TrackStep { PAID, ON_THE_WAY, ON_SITE, WORK_DONE, CONFIRMED }

/** Un devis reçu : le prix et le créneau viennent du serveur tels quels. */
data class Quote(
    val id: Int,
    val providerName: String,
    val initials: String,
    /** Couleur de l'avatar, donnée par le serveur. */
    val avatarColor: Long,
    val rating: Double,
    val reviews: Int,
    val price: Money,
    val slot: Instant,
) {
    /** Prénom seul, pour « Choisir Prisca ». */
    val firstName: String get() = providerName.split(" ").first()
}

/** Les trois opérateurs Mobile Money. */
enum class MobileOperator(val displayName: String) {
    MPESA("M-Pesa"), ORANGE("Orange Money"), AIRTEL("Airtel Money")
}

/** Un numéro Mobile Money du client (masqué), ou rien d'enregistré. */
data class PayAccount(val operator: MobileOperator, val maskedNumber: String?)

/** Ce qui s'est mal passé, choisi par le client. */
enum class DisputeReason { NOT_FINISHED, BAD_WORK, NO_SHOW, OTHER }

/** Les trois fins possibles d'un litige, décidées par NexisHub. */
enum class DisputeOutcome { RELEASE, REFUND, SPLIT }

/** Un litige : l'argent de la mission reste bloqué jusqu'à la décision,
 * puis encore 3 jours (le temps de contester). Les montants de la décision
 * sont calculés par le serveur ; l'app ne fait que les montrer. */
data class Dispute(
    val missionId: Int,
    val reason: DisputeReason,
    val text: String,
    val photos: Int,
    val openedAt: Instant,
    val providerReply: String? = null,
    val providerRepliedAt: Instant? = null,
    val outcome: DisputeOutcome? = null,
    val decidedAt: Instant? = null,
    val clientAmount: Money? = null,
    val providerAmount: Money? = null,
    val contestUntil: Instant? = null,
) {
    val decided: Boolean get() = outcome != null
}

/** Une demande de client reçue par le prestataire. */
data class ProviderRequest(
    val missionId: Int,
    val service: Service,
    val commune: String,
    /** « Samedi matin · 3 pièces ». */
    val summary: String,
    val description: String,
    /** Le moment souhaité par le client, en mots. */
    val wanted: String,
    val photos: Int,
    val receivedAt: Instant,
    /** Créneaux proposés d'après le souhait du client ; « Autre » en plus. */
    val slotChoices: List<Instant>,
    /** Le devis est déjà parti : le client le compare aux autres. */
    val quoted: Boolean = false,
)

/** Les étapes d'une mission vue par le prestataire. */
enum class ProviderStep { CLIENT_PAID, LEFT_HOME, ARRIVED, FINISHED }

/** Une mission payée, du côté du prestataire. */
data class ProviderJob(
    val missionId: Int,
    val service: Service,
    val commune: String,
    val clientName: String,
    val clientInitials: String,
    val clientColor: Long,
    /** Le lieu exact, donné seulement une fois la mission payée. */
    val place: String,
    /** L'argent sécurisé du client pour cette mission. */
    val amount: Money,
    val steps: Map<ProviderStep, Instant>,
    val sharing: Boolean = false,
    /** « Je suis arrivé » envoyé ; l'arrivée attend la preuve du client. */
    val arrivalSignaled: Boolean = false,
    val codeAttemptsLeft: Int = 5,
) {
    val clientFirstName: String get() = clientName.split(" ").first()
}

/** L'accueil prestataire : en service ou non, l'argent, les demandes. */
data class ProviderHome(
    val inService: Boolean,
    val communes: List<String>,
    val available: Money,
    val secured: Money,
    val requests: List<ProviderRequest>,
    val jobs: List<ProviderJob>,
)

/** Réponse au code de présence tapé par le prestataire. */
enum class PresenceResult { CONFIRMED, WRONG_CODE, LOCKED }

/** Ce que le serveur refuse, avec son code (le même que celui du serveur). */
class NexisRefusal(val code: String) : Exception(code)
