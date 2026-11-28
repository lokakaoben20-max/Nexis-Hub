import Foundation

/// Les étapes du suivi d'une mission payée.
enum TrackStep: Int, CaseIterable, Hashable {
    case paid, onTheWay, onSite, workDone, confirmed
}

/// Un devis reçu : le prix et le créneau viennent du serveur tels quels.
struct Quote: Identifiable, Hashable {
    let id: Int
    let providerName: String
    let initials: String
    /// Couleur de l'avatar, donnée par le serveur.
    let avatarColor: UInt32
    let rating: Double
    let reviews: Int
    let price: Money
    let slot: Date

    /// Prénom seul, pour « Choisir Prisca ».
    var firstName: String { String(providerName.split(separator: " ").first ?? "") }
}

/// Les opérateurs Mobile Money.
enum MobileOperator: String, CaseIterable, Hashable {
    case mpesa, orange, airtel, africell

    var displayName: String {
        switch self {
        case .mpesa: return "M-Pesa"
        case .orange: return "Orange Money"
        case .airtel: return "Airtel Money"
        case .africell: return "Africell Money"
        }
    }
}

/// Un numéro Mobile Money du client (masqué), ou rien d'enregistré.
struct PayAccount: Hashable {
    let mobileOperator: MobileOperator
    let maskedNumber: String?
}

/// Ce qui s'est mal passé, choisi par le client.
enum DisputeReason: CaseIterable, Hashable {
    case notFinished, badWork, noShow, other
}

/// Les trois fins possibles d'un litige, décidées par NexisHub.
enum DisputeOutcome: Hashable {
    case release, refund, split
}

/// Un litige : l'argent de la mission reste bloqué jusqu'à la décision,
/// puis encore 3 jours (le temps de contester). Les montants de la décision
/// sont calculés par le serveur ; l'app ne fait que les montrer.
struct Dispute: Hashable {
    let missionId: Int
    let reason: DisputeReason
    let text: String
    let photos: Int
    let openedAt: Date
    var providerReply: String? = nil
    var providerRepliedAt: Date? = nil
    var outcome: DisputeOutcome? = nil
    var decidedAt: Date? = nil
    var clientAmount: Money? = nil
    var providerAmount: Money? = nil
    var contestUntil: Date? = nil

    var decided: Bool { outcome != nil }
}

/// Une demande de client reçue par le prestataire.
struct ProviderRequest: Identifiable, Hashable {
    let missionId: Int
    let service: Service
    let commune: String
    /// « Samedi matin · 3 pièces ».
    let summary: String
    let description: String
    /// Le moment souhaité par le client, en mots.
    let wanted: String
    let photos: Int
    let receivedAt: Date
    /// Créneaux proposés d'après le souhait du client ; « Autre » en plus.
    let slotChoices: [Date]
    /// Le devis est déjà parti : le client le compare aux autres.
    var quoted: Bool = false

    var id: Int { missionId }
}

/// Les étapes d'une mission vue par le prestataire.
enum ProviderStep: Int, CaseIterable, Hashable {
    case clientPaid, leftHome, arrived, finished
}

/// Une mission payée, du côté du prestataire.
struct ProviderJob: Identifiable, Hashable {
    let missionId: Int
    let service: Service
    let commune: String
    let clientName: String
    let clientInitials: String
    let clientColor: UInt32
    /// Le lieu exact, donné seulement une fois la mission payée.
    let place: String
    /// L'argent sécurisé du client pour cette mission.
    let amount: Money
    var steps: [ProviderStep: Date]
    var sharing: Bool = false
    /// « Je suis arrivé » envoyé ; l'arrivée attend la preuve du client.
    var arrivalSignaled: Bool = false
    var codeAttemptsLeft: Int = 5

    var id: Int { missionId }
    var clientFirstName: String { String(clientName.split(separator: " ").first ?? "") }
}

/// L'accueil prestataire : en service ou non, l'argent, les demandes.
struct ProviderHome: Hashable {
    let inService: Bool
    let communes: [String]
    let available: Money
    let secured: Money
    let requests: [ProviderRequest]
    let jobs: [ProviderJob]
}

/// Réponse au code de présence tapé par le prestataire.
enum PresenceResult: Hashable {
    case confirmed, wrongCode, locked
}

/// Ce que le serveur refuse, avec son code (le même que celui du serveur).
struct NexisRefusal: Error, Hashable {
    let code: String
}
