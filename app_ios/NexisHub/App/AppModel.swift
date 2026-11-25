import Observation
import SwiftUI

/// État partagé de l'app : langue, session, réglages d'affichage du
/// portefeuille, et accès aux données.
@MainActor
@Observable
final class AppModel {
    let repository: NexisRepository
    private let texts: Texts

    /// « fr », « ln » ou « en ». Le français est la langue par défaut.
    var language: String
    var signedIn = false
    var walletCurrency: Currency = .cdf
    var amountsHidden = false

    /// Écran ouvert d'emblée pour les captures de la CI (versions de
    /// débogage seulement) : welcome, phone, signup, home, missions,
    /// wallet, profile, services.
    var capture: String?

    /// Change quand des données changent : les écrans relisent alors le dépôt.
    private(set) var revision = 0

    static let languages = ["fr", "ln", "en"]

    init(repository: NexisRepository, texts: Texts = .shared, language: String? = nil) {
        self.repository = repository
        self.texts = texts
        let device = Locale.preferredLanguages.first.map { String($0.prefix(2)) }
        self.language = language ?? (device.flatMap { Self.languages.contains($0) ? $0 : nil } ?? "fr")
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

    func signOut() {
        signedIn = false
        amountsHidden = false
        walletCurrency = .cdf
    }
}
