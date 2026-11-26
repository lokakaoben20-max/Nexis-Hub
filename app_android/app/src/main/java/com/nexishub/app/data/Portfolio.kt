package com.nexishub.app.data

import java.time.LocalDate

// Preuves de réalisations du prestataire (décisions de Ben, 2026-11-26) :
// facultatives ; l'équipe NexisHub les revoit d'abord, puis les photos et la
// phrase d'un service approuvé sont montrées aux clients. Les diplômes et
// attestations restent vus par l'équipe seulement : le client voit
// « Diplôme vérifié par NexisHub », jamais le document. L'équipe peut en
// demander plus tard. Ici, et seulement ici, la galerie est permise : ce sont
// des travaux déjà faits. La pièce d'identité et la vidéo restent sans galerie.

/** La décision de l'équipe sur les photos d'un service. */
enum class ProofReview {
    /** Pas encore revues : seule l'équipe les voit. */
    PENDING,
    /** Montrées aux clients. */
    APPROVED,
    /** Refusées : jamais montrées. De nouvelles photos repassent par l'équipe. */
    REJECTED,
}

/** Les photos d'un service, et une phrase pour dire ce qui a été fait. */
class WorkProof(
    val serviceId: String,
    /** JPEG réduits, sans métadonnées (ni lieu ni appareil). */
    val photos: List<ByteArray>,
    val note: String,
    /** Donnée par l'équipe (le serveur) ; l'app ne la choisit jamais. */
    val review: ProofReview = ProofReview.PENDING,
) {
    /** Mêmes photos et même phrase : rien à revoir. */
    fun sameContent(other: WorkProof): Boolean =
        serviceId == other.serviceId && note == other.note && samePhotos(photos, other.photos)

    fun withReview(review: ProofReview) = WorkProof(serviceId, photos, note, review)
}

fun samePhotos(a: List<ByteArray>, b: List<ByteArray>): Boolean =
    a.size == b.size && a.indices.all { a[it].contentEquals(b[it]) }

class Portfolio(
    val works: List<WorkProof> = emptyList(),
    /** Diplômes ou attestations (INPP, centre de formation, ancien patron…). */
    val certificates: List<ByteArray> = emptyList(),
    /** L'équipe a vérifié les diplômes ; le client voit seulement ce fait. */
    val certificatesVerified: Boolean = false,
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
            works.filter { it.photos.isNotEmpty() }.map { WorkProof(it.serviceId, it.photos, it.note.trim(), it.review) },
            certificates,
            certificatesVerified,
        )

    /** Ce que le serveur garde quand le prestataire renvoie ses preuves : un
     * service inchangé garde la décision de l'équipe ; un service nouveau ou
     * modifié repasse en attente (il disparaît des clients jusqu'au nouvel
     * accord) ; des diplômes changés ne sont plus vérifiés. */
    fun resubmitted(previous: Portfolio): Portfolio = Portfolio(
        works.map { work ->
            work.withReview(previous.works.firstOrNull { it.sameContent(work) }?.review ?: ProofReview.PENDING)
        },
        certificates,
        previous.certificatesVerified && samePhotos(certificates, previous.certificates),
    )

    /** Ce que voient les clients : seulement les services approuvés par
     * l'équipe, et le fait que les diplômes sont vérifiés (jamais le
     * document). Rien tant qu'aucun service n'est approuvé. */
    val showcase: ProviderShowcase?
        get() {
            val shown = works.filter { it.review == ProofReview.APPROVED && it.photos.isNotEmpty() }
                .map { ShowcaseWork(it.serviceId, it.photos, it.note) }
            return if (shown.isEmpty()) null else ProviderShowcase(shown, certificatesVerified)
        }

    companion object {
        /** Pendant que l'équipe vérifie le prestataire, ses réalisations sont
         * figées (décision de Ben, 2026-11-26) : l'équipe regarde ce qui a été
         * envoyé avec la demande. Seule une demande de l'équipe les rouvre.
         * Après l'accord, elles redeviennent modifiables (un service modifié
         * repasse par l'équipe). */
        fun isEditable(status: ProviderStatus?, requested: Boolean): Boolean =
            status != null && (status == ProviderStatus.VERIFIED || requested)

        const val MAX_PHOTOS = 5
        const val MAX_CERTIFICATES = 3
        const val MAX_NOTE = 200
    }
}

/** Un service montré aux clients. */
class ShowcaseWork(val serviceId: String, val photos: List<ByteArray>, val note: String)

/** Les réalisations d'un prestataire, telles que les clients les voient. */
class ProviderShowcase(val works: List<ShowcaseWork>, val certificateVerified: Boolean)

/** L'équipe demande des preuves pour certains services. */
data class PortfolioRequest(val services: List<String>, val askedAt: LocalDate)
