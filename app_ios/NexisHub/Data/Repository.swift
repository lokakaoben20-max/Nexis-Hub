import Foundation

/// Ce que les écrans lisent. Une seule source : le serveur Nexis.
///
/// Aujourd'hui seule l'implémentation de démonstration existe (données
/// fictives, aucun appel réseau, aucun argent). La connexion au serveur
/// (/api/app/v1) la remplacera sans changer les écrans.
@MainActor
protocol NexisRepository: AnyObject {
    /// Canaux par lesquels le serveur envoie réellement un code. Un canal
    /// absent n'est pas montré : jamais d'option qui fait semblant.
    var codeChannels: [CodeChannel] { get }
    var communes: [String] { get }
    var signupTermsVersion: Date { get }

    /// Démonstration : ouvre le compte du numéro s'il existe.
    func openAccount(phone: String) -> Bool
    /// Crée le profil seulement si les conditions en vigueur sont acceptées.
    func registerClient(phone: String, firstName: String, lastName: String,
                        commune: String, acceptedTermsVersion: Date?) -> Bool

    func profile() async throws -> Profile
    func wallet() async throws -> Wallet
    func missions() async throws -> [Mission]
    func movements() async throws -> [Movement]
    /// Le catalogue des services, dans l'ordre voulu par le serveur.
    func serviceCatalog() async throws -> [CatalogService]
    /// Crée une mission en attente de devis pour un service du catalogue.
    func requestService(serviceId: String, commune: String, description: String) async throws
    /// « Décrire mon besoin » : une demande libre transmise à l'équipe.
    func sendFreeRequest(title: String, text: String) async throws
}

struct InvalidRequest: Error {}

/// Données FICTIVES de l'aperçu, reprises de l'app Flutter
/// (app_mobile/lib/data/demo_repository.dart).
@MainActor
final class DemoRepository: NexisRepository {
    private let now: Date
    private static let samplePhone = "+243812345412"
    private var activePhone = DemoRepository.samplePhone
    private var registered: [String: Profile] = [:]
    private var requested: [String: [Mission]] = [:]
    private var nextRequestId = 1000

    init(now: Date = .now) { self.now = now }

    let codeChannels: [CodeChannel] = [.whatsapp, .telegram, .sms]

    let communes = [
        "Bandalungwa", "Barumbu", "Bumbu", "Gombe", "Kalamu", "Kasa-Vubu",
        "Kimbanseke", "Kinshasa", "Kintambo", "Kisenso", "Lemba", "Limete",
        "Lingwala", "Makala", "Maluku", "Masina", "Matete", "Mont-Ngafula",
        "N'djili", "Ngaba", "Ngaliema", "Ngiri-Ngiri", "N'sele", "Selembao",
    ]

    let signupTermsVersion = DateComponents(
        calendar: Calendar(identifier: .gregorian), year: 2026, month: 11, day: 20
    ).date!

    private var isSample: Bool { activePhone == Self.samplePhone }

    func openAccount(phone: String) -> Bool {
        guard phone == Self.samplePhone || registered[phone] != nil else { return false }
        activePhone = phone
        return true
    }

    func registerClient(phone: String, firstName: String, lastName: String,
                        commune: String, acceptedTermsVersion: Date?) -> Bool {
        let first = firstName.trimmingCharacters(in: .whitespacesAndNewlines)
        let last = lastName.trimmingCharacters(in: .whitespacesAndNewlines)
        guard phone != Self.samplePhone, registered[phone] == nil,
              !first.isEmpty, !last.isEmpty, communes.contains(commune),
              acceptedTermsVersion == signupTermsVersion else { return false }
        registered[phone] = Profile(firstName: first, lastName: last, phone: phone,
                                    commune: commune, isProvider: false,
                                    termsVersion: acceptedTermsVersion)
        activePhone = phone
        return true
    }

    func profile() async throws -> Profile {
        registered[activePhone] ?? Profile(
            firstName: "Grâce", lastName: "Nsimba", phone: Self.samplePhone,
            commune: "Limete", isProvider: true, termsVersion: signupTermsVersion)
    }

    func wallet() async throws -> Wallet {
        guard isSample else { return .empty }
        return Wallet(
            available: [.cdf: Money(45_000, .cdf), .usd: Money(1_250, .usd)],
            secured: [.cdf: Money(35_000, .cdf), .usd: Money(500, .usd)])
    }

    private func ago(minutes: Double = 0, hours: Double = 0, days: Double = 0) -> Date {
        now.addingTimeInterval(-(minutes * 60 + hours * 3600 + days * 86_400))
    }

    private lazy var sampleMissions: [Mission] = [
        Mission(id: 51, service: .plomberie, commune: "Gombe", status: .inProgress,
                payment: .secured, amount: Money(500, .usd), providerName: "Jean M.",
                when: ago(hours: 1)),
        Mission(id: 52, service: .nettoyage, commune: "Limete", status: .quoted,
                payment: .none, quotesCount: 3, when: ago(hours: 3), detail: "3 pièces"),
        Mission(id: 49, service: .coiffure, commune: "Limete", status: .awaitingConfirmation,
                payment: .secured, amount: Money(15_000, .cdf), providerName: "Nadia K.",
                when: ago(hours: 5)),
        Mission(id: 47, service: .climatisation, commune: "Bandal", status: .disputed,
                payment: .blocked, amount: Money(6_000, .usd), providerName: "Rodrigue T.",
                when: ago(days: 1)),
        Mission(id: 53, service: .electricite, commune: "Ngaliema", status: .pending,
                payment: .none, when: ago(minutes: 30)),
        Mission(id: 41, service: .plomberie, commune: "Gombe", status: .completed,
                payment: .released, amount: Money(4_500, .usd), providerName: "Jean M.",
                when: ago(days: 2), rated: true),
        Mission(id: 38, service: .nettoyage, commune: "Limete", status: .completed,
                payment: .released, amount: Money(25_000, .cdf), providerName: "Prisca K.",
                when: ago(days: 6), rated: true),
        Mission(id: 33, service: .electricite, commune: "Limete", status: .completed,
                payment: .released, amount: Money(18_000, .cdf), providerName: "Alain L.",
                when: ago(days: 12)),
    ]

    func missions() async throws -> [Mission] {
        (requested[activePhone] ?? []) + (isSample ? sampleMissions : [])
    }

    func movements() async throws -> [Movement] {
        guard isSample else { return [] }
        return [
            Movement(kind: .payment, label: "Plomberie · Gombe", amount: Money(-500, .usd),
                     when: ago(hours: 1), state: .secured),
            Movement(kind: .refund, label: "Visite annulée", amount: Money(10_000, .cdf),
                     when: ago(days: 1), state: .refunded),
            Movement(kind: .release, label: "Plomberie · Gombe", amount: Money(-4_500, .usd),
                     when: ago(days: 2), state: .released),
            Movement(kind: .release, label: "Nettoyage · Limete", amount: Money(-25_000, .cdf),
                     when: ago(days: 6), state: .released),
        ]
    }

    /// Fictif : « Peinture » et « Déménagement » montrent seulement comment
    /// un service tout juste approuvé apparaît.
    func serviceCatalog() async throws -> [CatalogService] {
        [
            CatalogService(id: "plomberie", baseName: "Plomberie", color: 0x0350E6,
                           service: .plomberie, lastRequested: isSample ? ago(days: 2) : nil),
            CatalogService(id: "nettoyage", baseName: "Nettoyage", color: 0x1E8A4C,
                           service: .nettoyage, lastRequested: isSample ? ago(days: 6) : nil),
            CatalogService(id: "electricite", baseName: "Électricité", color: 0xC98200,
                           service: .electricite, recommended: true),
            CatalogService(id: "climatisation", baseName: "Climatisation", color: 0x0A84D6,
                           service: .climatisation),
            CatalogService(id: "informatique", baseName: "Informatique", color: 0x021937,
                           service: .informatique),
            CatalogService(id: "peinture", baseName: "Peinture", color: 0xB4531A,
                           translations: ["en": "Painting", "ln": "Kopakola langi"],
                           isNew: true),
            CatalogService(id: "coiffure", baseName: "Coiffure", color: 0xC2416B,
                           service: .coiffure),
            CatalogService(id: "graphisme", baseName: "Graphisme", color: 0x494C95,
                           service: .graphisme),
            CatalogService(id: "jardinage", baseName: "Jardinage", color: 0x4F8A10,
                           service: .jardinage),
            CatalogService(id: "demenagement", baseName: "Déménagement", color: 0x2B6CB0,
                           translations: ["en": "Moving", "ln": "Kokende kofanda esika mosusu"],
                           isNew: true),
        ]
    }

    func requestService(serviceId: String, commune: String, description: String) async throws {
        let detail = description.trimmingCharacters(in: .whitespacesAndNewlines)
        guard let item = try await serviceCatalog().first(where: { $0.id == serviceId }),
              communes.contains(commune), (10...500).contains(detail.count) else {
            throw InvalidRequest()
        }
        let mission = Mission(id: nextRequestId, service: item.service ?? .autre,
                              catalogService: item, commune: commune, status: .pending,
                              payment: .none, when: .now, detail: detail)
        nextRequestId += 1
        requested[activePhone, default: []].insert(mission, at: 0)
    }

    /// Aperçu : la demande n'est envoyée nulle part.
    func sendFreeRequest(title: String, text: String) async throws {}
}
