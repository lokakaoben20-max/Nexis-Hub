package com.nexishub.app.data

import java.time.LocalDate

// Preuves de réalisations du prestataire (décision de Ben, 2026-11-26) :
// facultatives, vues seulement par l'équipe NexisHub, jamais par les clients.
// L'équipe peut en demander plus tard. Ici, et seulement ici, la galerie est
// permise : ce sont des travaux déjà faits. La pièce d'identité et la vidéo
// restent sans galerie.

/** Les photos d'un service, et une phrase pour dire ce qui a été fait. */
class WorkProof(
    val serviceId: String,
    /** JPEG réduits, sans métadonnées (ni lieu ni appareil). */
    val photos: List<ByteArray>,
    val note: String,
)

class Portfolio(
    val works: List<WorkProof> = emptyList(),
    /** Diplômes ou attestations (INPP, centre de formation, ancien patron…). */
    val certificates: List<ByteArray> = emptyList(),
) {
    val isEmpty: Boolean get() = works.isEmpty() && certificates.isEmpty()

    /** Les mêmes règles que le serveur : un service choisi par la personne,
     * une fois chacun, 1 à 5 photos, une phrase de 200 signes au plus,
     * 3 attestations au plus, aucun fichier vide. */
    fun isValid(services: Set<String>): Boolean =
        certificates.size <= MAX_CERTIFICATES && certificates.all { it.isNotEmpty() } &&
            works.map { it.serviceId }.toSet().size == works.size &&
            works.all { work ->
                work.serviceId in services && work.photos.size in 1..MAX_PHOTOS &&
                    work.photos.all { it.isNotEmpty() } && work.note.length <= MAX_NOTE
            }

    /** Retire les services sans photo (une phrase seule ne montre rien) et les espaces en trop. */
    val cleaned: Portfolio
        get() = Portfolio(
            works.filter { it.photos.isNotEmpty() }.map { WorkProof(it.serviceId, it.photos, it.note.trim()) },
            certificates,
        )

    companion object {
        const val MAX_PHOTOS = 5
        const val MAX_CERTIFICATES = 3
        const val MAX_NOTE = 200
    }
}

/** L'équipe demande des preuves pour certains services. */
data class PortfolioRequest(val services: List<String>, val askedAt: LocalDate)
