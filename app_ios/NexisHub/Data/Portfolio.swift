import Foundation

// Preuves de réalisations du prestataire (décisions de Ben, 2026-11-26) :
// facultatives ; l'équipe NexisHub les revoit d'abord, puis les photos et la
// phrase d'un service approuvé sont montrées aux clients. Les diplômes et
// attestations restent vus par l'équipe seulement : le client voit
// « Diplôme vérifié par NexisHub », jamais le document. L'équipe peut en
// demander plus tard. Ici, et seulement ici, la galerie est permise : ce sont
// des travaux déjà faits. La pièce d'identité et la vidéo restent sans galerie.

/// La décision de l'équipe sur les photos d'un service.
enum ProofReview: String {
    /// Pas encore revues : seule l'équipe les voit.
    case pending
    /// Montrées aux clients.
    case approved
    /// Refusées : jamais montrées. De nouvelles photos repassent par l'équipe.
    case rejected
}

/// Les photos d'un service, et une phrase pour dire ce qui a été fait.
struct WorkProof: Equatable {
    var serviceId: String
    /// JPEG réduits, sans métadonnées (ni lieu ni appareil).
    var photos: [Data]
    var note: String
    /// Donnée par l'équipe (le serveur) ; l'app ne la choisit jamais.
    var review: ProofReview = .pending

    /// Mêmes photos et même phrase : rien à revoir.
    func sameContent(as other: WorkProof) -> Bool {
        serviceId == other.serviceId && photos == other.photos && note == other.note
    }
}

struct Portfolio: Equatable {
    static let maxPhotos = 5
    static let maxCertificates = 3
    static let maxNote = 200

    var works: [WorkProof] = []
    /// Diplômes ou attestations (INPP, centre de formation, ancien patron…).
    var certificates: [Data] = []
    /// L'équipe a vérifié les diplômes ; le client voit seulement ce fait.
    var certificatesVerified = false

    var isEmpty: Bool { works.isEmpty && certificates.isEmpty }

    /// Les mêmes règles que le serveur : un service choisi par la personne,
    /// une fois chacun, 1 à 5 photos, une phrase de 200 signes au plus,
    /// 3 attestations au plus, aucun fichier vide.
    func isValid(services: Set<String>) -> Bool {
        certificates.count <= Self.maxCertificates && certificates.allSatisfy { !$0.isEmpty }
            && Set(works.map(\.serviceId)).count == works.count
            && works.allSatisfy { work in
                services.contains(work.serviceId) && (1...Self.maxPhotos).contains(work.photos.count)
                    && work.photos.allSatisfy { !$0.isEmpty } && work.note.count <= Self.maxNote
            }
    }

    /// Retire les services sans photo (une phrase seule ne montre rien) et
    /// les espaces en trop.
    var cleaned: Portfolio {
        Portfolio(works: works.compactMap { work in
            guard !work.photos.isEmpty else { return nil }
            return WorkProof(serviceId: work.serviceId, photos: work.photos,
                             note: work.note.trimmingCharacters(in: .whitespacesAndNewlines), review: work.review)
        }, certificates: certificates, certificatesVerified: certificatesVerified)
    }

    /// Pendant que l'équipe vérifie le prestataire, ses réalisations sont
    /// figées (décision de Ben, 2026-11-26) : l'équipe regarde ce qui a été
    /// envoyé avec la demande. Seule une demande de l'équipe les rouvre.
    /// Après l'accord, elles redeviennent modifiables (un service modifié
    /// repasse par l'équipe).
    static func isEditable(status: ProviderStatus?, requested: Bool) -> Bool {
        guard let status else { return false }
        return status == .verified || requested
    }

    /// Ce que le serveur garde quand le prestataire renvoie ses preuves : un
    /// service inchangé garde la décision de l'équipe ; un service nouveau ou
    /// modifié repasse en attente (il disparaît des clients jusqu'au nouvel
    /// accord) ; des diplômes changés ne sont plus vérifiés.
    func resubmitted(over previous: Portfolio) -> Portfolio {
        Portfolio(works: works.map { work in
            var kept = work
            kept.review = previous.works.first { $0.sameContent(as: work) }?.review ?? .pending
            return kept
        }, certificates: certificates,
        certificatesVerified: previous.certificatesVerified && certificates == previous.certificates)
    }

    /// Ce que voient les clients : seulement les services approuvés par
    /// l'équipe, et le fait que les diplômes sont vérifiés (jamais le
    /// document). Rien tant qu'aucun service n'est approuvé.
    var showcase: ProviderShowcase? {
        let shown = works.filter { $0.review == .approved && !$0.photos.isEmpty }
            .map { ShowcaseWork(serviceId: $0.serviceId, photos: $0.photos, note: $0.note) }
        guard !shown.isEmpty else { return nil }
        return ProviderShowcase(works: shown, certificateVerified: certificatesVerified)
    }
}

/// Un service montré aux clients.
struct ShowcaseWork: Equatable {
    let serviceId: String
    let photos: [Data]
    let note: String
}

/// Les réalisations d'un prestataire, telles que les clients les voient.
struct ProviderShowcase: Equatable {
    let works: [ShowcaseWork]
    let certificateVerified: Bool
}

/// L'équipe demande des preuves pour certains services.
struct PortfolioRequest: Equatable {
    let services: [String]
    let askedAt: Date
}
