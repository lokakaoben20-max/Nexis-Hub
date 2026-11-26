import Foundation

// Preuves de réalisations du prestataire (décision de Ben, 2026-11-26) :
// facultatives, vues seulement par l'équipe NexisHub, jamais par les
// clients. L'équipe peut en demander plus tard. Ici, et seulement ici, la
// galerie est permise : ce sont des travaux déjà faits. La pièce d'identité
// et la vidéo restent sans galerie.

/// Les photos d'un service, et une phrase pour dire ce qui a été fait.
struct WorkProof: Equatable {
    var serviceId: String
    /// JPEG réduits, sans métadonnées (ni lieu ni appareil).
    var photos: [Data]
    var note: String
}

struct Portfolio: Equatable {
    static let maxPhotos = 5
    static let maxCertificates = 3
    static let maxNote = 200

    var works: [WorkProof] = []
    /// Diplômes ou attestations (INPP, centre de formation, ancien patron…).
    var certificates: [Data] = []

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
                             note: work.note.trimmingCharacters(in: .whitespacesAndNewlines))
        }, certificates: certificates)
    }
}

/// L'équipe demande des preuves pour certains services.
struct PortfolioRequest: Equatable {
    let services: [String]
    let askedAt: Date
}
