package com.nexishub.app.data

import java.time.Duration
import java.time.Instant
import java.time.LocalDate

// Le compte vu depuis le profil : téléphones reliés, documents acceptés,
// demande pour devenir prestataire. Mêmes règles que le serveur
// (backend/app/app_sessions.py, conditions.py, profils.py).

/** Où en est le profil prestataire. Seul un prestataire vérifié reçoit des
 * demandes et ouvre l'espace prestataire. */
enum class ProviderStatus { PENDING, VERIFIED, REJECTED, SUSPENDED }

enum class DevicePlatform { IOS, ANDROID }

/** Un téléphone relié au compte par l'app. */
data class AppDevice(
    val id: Int,
    /** Nom donné par le téléphone à la connexion (« Samsung Galaxy A14 »). */
    val label: String,
    val platform: DevicePlatform,
    val addedAt: Instant,
    val lastSeenAt: Instant?,
    /** Un téléphone ajouté à un compte existant attend 72 h avant toute
     * sortie d'argent ; la date vient du serveur. */
    val moneyUnlockedAt: Instant,
    /** Le téléphone qui affiche l'écran. */
    val isCurrent: Boolean,
) {
    /** Heures entières qui restent avant une sortie d'argent (0 si c'est
     * déjà possible). */
    fun moneyHoursLeft(now: Instant = Instant.now()): Int {
        val left = Duration.between(now, moneyUnlockedAt)
        if (left.isNegative || left.isZero) return 0
        return Math.ceil(left.toMinutes() / 60.0).toInt()
    }
}

/** Les documents à accepter, comme le serveur les nomme. */
enum class LegalDocumentKey(val serverKey: String) {
    CGU("cgu"), PROVIDER_TERMS("conditions_prestataires"), ORG_TERMS("conditions_entreprises")
}

/** Un document en vigueur, et quand la personne l'a accepté. */
data class LegalDocument(val key: LegalDocumentKey, val version: LocalDate, val acceptedAt: LocalDate?)

/** Le texte exact d'une version. `text` est nul tant que la version n'est
 * pas publiée (aperçu) : l'écran le dit au lieu d'inventer un texte. */
data class LegalText(val key: LegalDocumentKey, val version: LocalDate, val text: String?)
