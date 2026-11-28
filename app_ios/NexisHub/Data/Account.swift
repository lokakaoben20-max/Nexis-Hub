import Foundation

// Le compte vu depuis le profil : téléphones reliés, documents acceptés,
// demande pour devenir prestataire. Mêmes règles que le serveur
// (backend/app/app_sessions.py, conditions.py, profils.py).

/// Où en est le profil prestataire. Seul un prestataire vérifié reçoit des
/// demandes et ouvre l'espace prestataire.
enum ProviderStatus: String, Hashable {
    case pending, verified, rejected, suspended
}

enum DevicePlatform: String, Hashable {
    case ios, android
}

/// Un téléphone relié au compte par l'app.
struct AppDevice: Identifiable, Hashable {
    let id: Int
    /// Nom donné par le téléphone à la connexion (« iPhone 12 »).
    let label: String
    let platform: DevicePlatform
    let addedAt: Date
    let lastSeenAt: Date?
    /// Un téléphone ajouté à un compte existant attend 72 h avant toute
    /// sortie d'argent ; la date vient du serveur.
    let moneyUnlockedAt: Date
    /// Le téléphone qui affiche l'écran.
    let isCurrent: Bool

    /// Heures entières qui restent avant une sortie d'argent (0 si c'est
    /// déjà possible).
    func moneyHoursLeft(now: Date = .now) -> Int {
        let left = moneyUnlockedAt.timeIntervalSince(now)
        return left > 0 ? Int((left / 3600).rounded(.up)) : 0
    }
}

/// Les documents à accepter, comme le serveur les nomme.
enum LegalDocumentKey: String, Hashable, CaseIterable {
    case cgu
    case providerTerms = "conditions_prestataires"
    case orgTerms = "conditions_entreprises"
}

/// Un document en vigueur, et quand la personne l'a accepté.
struct LegalDocument: Identifiable, Hashable {
    let key: LegalDocumentKey
    /// Date d'entrée en vigueur de la version.
    let version: Date
    let acceptedAt: Date?
    var id: String { key.rawValue }
}

/// Le texte exact d'une version. `text` est vide tant que la version n'est
/// pas publiée (aperçu) : l'écran le dit au lieu d'inventer un texte.
struct LegalText: Hashable {
    let key: LegalDocumentKey
    let version: Date
    let text: String?
}
