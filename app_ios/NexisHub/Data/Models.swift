import Foundation

/// Les neuf services de Nexis (mêmes clés que le serveur et le bot).
enum Service: String, CaseIterable, Hashable {
    case plomberie, electricite, climatisation, informatique, graphisme
    case coiffure, nettoyage, jardinage, autre

    /// Noms des services : les mêmes que dans le bot (FR / LN / EN).
    func name(_ language: String) -> String {
        let names: [Service: (fr: String, ln: String, en: String)] = [
            .plomberie: ("Plomberie", "Plomberie", "Plumbing"),
            .electricite: ("Électricité", "Kokotisa mwinda", "Electrical"),
            .climatisation: ("Climatisation", "Climatisation", "Air conditioning"),
            .informatique: ("Informatique", "Informatique", "IT"),
            .graphisme: ("Graphisme", "Graphisme", "Graphic design"),
            .coiffure: ("Coiffure", "Kosala nsuki", "Hairdressing"),
            .nettoyage: ("Nettoyage", "Kopetola", "Cleaning"),
            .jardinage: ("Jardinage", "Jardin", "Gardening"),
            .autre: ("Autre service", "Mosala mosusu", "Other service"),
        ]
        let entry = names[self]!
        switch language {
        case "ln": return entry.ln
        case "en": return entry.en
        default: return entry.fr
        }
    }
}

/// États d'une mission vus par le client (mêmes valeurs que le serveur).
enum MissionStatus: Hashable {
    case pending, quoted, confirmed, inProgress, awaitingConfirmation
    case completed, cancelled, disputed
}

/// Les six états de l'argent de la charte.
enum PaymentState: Hashable {
    case none, secured, released, refunded, blocked, available
}

struct Mission: Identifiable, Hashable {
    let id: Int
    let service: Service
    var catalogService: CatalogService? = nil
    let commune: String
    var status: MissionStatus
    var payment: PaymentState
    var amount: Money? = nil
    var providerName: String? = nil
    var quotesCount: Int = 0
    var when: Date? = nil
    var rated: Bool = false
    var detail: String? = nil
    /// Le moment souhaité par le client, tel qu'il l'a écrit (« Samedi matin »).
    var wanted: String? = nil
    /// Le devis choisi et payé (prestataire, prix, créneau).
    var chosen: Quote? = nil
    /// Distance du prestataire en route, seulement s'il partage sa position.
    var distanceKm: Double? = nil
    /// Heure de chaque étape franchie du suivi.
    var steps: [TrackStep: Date] = [:]
    /// Note et nombre d'avis du prestataire, tels que le serveur les donne.
    var providerRating: Double? = nil
    var providerReviews: Int? = nil

    var rating: Double? { chosen?.rating ?? providerRating }
    var reviews: Int? { chosen?.reviews ?? providerReviews }
    /// Prénom du prestataire, pour « Vous confirmez, Jean reçoit l'argent ».
    var providerFirstName: String {
        chosen?.firstName ?? providerName.map { String($0.split(separator: " ").first ?? "") } ?? ""
    }

    var isActive: Bool {
        switch status {
        case .pending, .quoted, .confirmed, .inProgress, .awaitingConfirmation, .disputed:
            return true
        case .completed, .cancelled:
            return false
        }
    }

    var reference: String {
        let digits = String(id)
        return "NXH-" + String(repeating: "0", count: max(0, 4 - digits.count)) + digits
    }

    func serviceName(_ language: String) -> String {
        catalogService?.name(language) ?? service.name(language)
    }
}

struct Wallet: Hashable {
    /// Solde disponible, par devise.
    let available: [Currency: Money]
    /// Argent payé pour des missions en cours, protégé par Nexis.
    let secured: [Currency: Money]

    static let empty = Wallet(available: [:], secured: [:])
}

enum MovementKind: Hashable {
    case payment, refund, release, deposit, withdrawal
}

/// Une notification de l'app : devis reçu, prestataire en route, argent
/// libéré… Le serveur les enverra ; l'aperçu n'en a aucune.
struct AppNotification: Identifiable, Hashable {
    let id: String
    let title: String
    let message: String
    let when: Date
    let read: Bool
}

struct Movement: Identifiable, Hashable {
    let id = UUID()
    let kind: MovementKind
    let label: String
    let amount: Money
    let when: Date
    let state: PaymentState
}

struct Profile: Hashable {
    let firstName: String
    let lastName: String
    let phone: String
    let commune: String
    /// Profil prestataire : `nil` pour un client seulement.
    var providerStatus: ProviderStatus? = nil
    let termsVersion: Date?
    /// Client dont l'identité (pièce et vidéo) a été vérifiée par l'équipe,
    /// sans être prestataire. Donnée du serveur.
    var identityVerified: Bool = false

    /// Prestataire vérifié : il ouvre l'espace prestataire.
    var isProvider: Bool { providerStatus == .verified }

    /// Identité déjà vérifiée (prestataire vérifié ou client vérifié) : elle
    /// n'est JAMAIS revérifiée, ni pour créer un espace entreprise ni pour
    /// rejoindre une équipe.
    var isIdentityVerified: Bool { providerStatus == .verified || identityVerified }

    var initials: String {
        (String(firstName.prefix(1)) + String(lastName.prefix(1))).uppercased()
    }
}

/// Un service du catalogue tel que le serveur le publie. L'app ne décide
/// ni de la liste, ni de qui est « nouveau », ni de l'ordre.
struct CatalogService: Identifiable, Hashable {
    let id: String
    /// Nom d'origine du catalogue (français).
    let baseName: String
    /// Couleur du carré du service (série B), donnée par le serveur.
    let color: UInt32
    var translations: [String: String] = [:]
    /// Service connu de l'app (pictogramme de la police Nexis).
    var service: Service? = nil
    var isNew: Bool = false
    var lastRequested: Date? = nil
    var recommended: Bool = false

    func name(_ language: String) -> String {
        if let translated = translations[language],
           !translated.trimmingCharacters(in: .whitespaces).isEmpty {
            return translated
        }
        return service?.name(language) ?? baseName
    }
}

/// Canal par lequel le serveur envoie le code de vérification.
enum CodeChannel: String, CaseIterable, Hashable {
    case whatsapp, telegram, sms
}
