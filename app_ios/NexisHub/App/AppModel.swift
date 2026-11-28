import Observation
import SwiftUI
import UIKit

/// État partagé de l'app : langue, session, réglages d'affichage du
/// portefeuille, et accès aux données.
@MainActor
@Observable
final class AppModel {
    let repository: NexisRepository
    /// Code NexisHub et Face ID de ce téléphone.
    let security: AppSecurity
    private let texts: Texts

    /// « fr », « ln » ou « en ». Le français est la langue par défaut.
    var language: String
    var signedIn = false
    var walletCurrency: Currency = .cdf
    var amountsHidden = false
    /// Espace prestataire ouvert (seulement pour un compte prestataire).
    var providerSpace = false
    /// Espace entreprise ouvert (numéro de l'entreprise) ; `nil` = espace
    /// personnel. Jamais en même temps que l'espace prestataire.
    var orgSpaceId: Int?
    /// Photos de profil (clé « me » ou « org-<numéro> »), gardées sur ce
    /// téléphone en attendant le serveur.
    var photos: [String: Data] = [:]

    func photo(_ key: String?) -> UIImage? {
        guard let key, let data = photos[key] else { return nil }
        return UIImage(data: data)
    }
    /// Onglet demandé par un écran (« Voir mon portefeuille ») ; le cadre
    /// l'ouvre puis l'efface.
    var requestedTab: AppTab?
    /// Onglets dont un écran de mission est ouvert : l'accessoire « Demander
    /// un service » s'y range, comme la barre d'onglets.
    var openFlowTabs: Set<AppTab> = []
    /// L'app demande le code (ou Face ID) avant de montrer quoi que ce soit.
    var locked = false
    /// Cache posé quand l'app passe en arrière-plan : la liste des apps
    /// ouvertes ne montre ni solde ni mission.
    var covered = false
    /// Sortie d'argent en attente de confirmation par le code ou Face ID.
    var gate: MoneyGate?
    /// Écran de protection encore ouvert après la création du code (Face ID,
    /// puis « Votre compte est protégé »).
    var finishingProtection = false
    private var leftAt: Date?

    /// Écran ouvert d'emblée pour les captures de la CI (versions de
    /// débogage seulement) : welcome, phone, signup, home, missions,
    /// wallet, profile, services, et les écrans de mission (tracking,
    /// quotes, pay, pending, confirm, report, dispute, decision, provider,
    /// request, job).
    var capture: String?

    /// Change quand des données changent : les écrans relisent alors le dépôt.
    private(set) var revision = 0

    static let languages = ["fr", "ln", "en"]

    init(repository: NexisRepository, security: AppSecurity? = nil, texts: Texts = .shared, language: String? = nil) {
        self.repository = repository
        self.security = security ?? AppSecurity(vault: KeychainCodeVault())
        self.texts = texts
        let device = Locale.preferredLanguages.first.map { String($0.prefix(2)) }
        self.language = language ?? (device.flatMap { Self.languages.contains($0) ? $0 : nil } ?? "fr")
        // Le code part avec la session : l'app s'ouvre sans session, donc un
        // code resté d'une session précédente ne sert plus.
        self.security.erase()
    }

    var locale: Locale { Locale(identifier: language == "ln" ? "fr" : language) }

    func t(_ key: String, _ args: [String: String] = [:]) -> String {
        texts.text(key, language, args)
    }

    func plural(_ key: String, count: Int, _ args: [String: String] = [:]) -> String {
        texts.plural(key, language, count: count, args)
    }

    func money(_ value: Money) -> String { value.formatted(language) }

    func dataChanged() { revision += 1 }

    func signIn() { signedIn = true }

    /// Le compte est ouvert mais ce téléphone n'a pas encore de code.
    var needsProtection: Bool { signedIn && !security.hasCode }

    /// L'app passe en arrière-plan.
    func left(at date: Date = .now) {
        guard signedIn else { return }
        leftAt = date
        covered = true
    }

    /// L'app revient : verrou si elle est restée fermée au moins une minute.
    func came(back date: Date = .now) {
        covered = false
        if signedIn, security.hasCode, CodeRules.shouldLock(leftAt: leftAt, now: date) {
            locked = true
            finishGate(false)
        }
        leftAt = nil
    }

    /// Demande le code ou Face ID avant une sortie d'argent. Faux si la
    /// personne annule : rien ne part.
    func confirmMoneyOut(_ reason: String) async -> Bool {
        guard security.hasCode else { return false }
        finishGate(false)
        return await withCheckedContinuation { continuation in
            gate = MoneyGate(reason: reason) { continuation.resume(returning: $0) }
        }
    }

    /// Termine la demande en cours, une seule fois.
    func finishGate(_ confirmed: Bool) {
        guard let pending = gate else { return }
        gate = nil
        pending.resume(confirmed)
    }

    func signOut() {
        finishGate(false)
        security.erase()
        locked = false
        covered = false
        finishingProtection = false
        leftAt = nil
        signedIn = false
        amountsHidden = false
        walletCurrency = .cdf
        providerSpace = false
        orgSpaceId = nil
        photos = [:]
        requestedTab = nil
        openFlowTabs = []
    }
}

/// Une sortie d'argent qui attend le code ou Face ID.
struct MoneyGate: Identifiable {
    let id = UUID()
    let reason: String
    let resume: (Bool) -> Void
}

