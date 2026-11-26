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
    /// Version en vigueur des conditions des prestataires.
    var providerTermsVersion: Date { get }

    /// Demande au serveur d'envoyer le code de connexion par ce canal.
    func sendCode(phone: String, channel: CodeChannel) async throws
    /// Démonstration : ouvre le compte du numéro s'il existe.
    func openAccount(phone: String) -> Bool
    /// Crée le profil seulement si les conditions en vigueur sont acceptées.
    func registerClient(phone: String, firstName: String, lastName: String,
                        commune: String, acceptedTermsVersion: Date?) -> Bool

    func profile() async throws -> Profile
    func wallet() async throws -> Wallet
    func missions() async throws -> [Mission]
    func movements() async throws -> [Movement]
    /// Les notifications de la personne, les plus récentes d'abord.
    func notifications() async throws -> [AppNotification]
    /// Le catalogue des services, dans l'ordre voulu par le serveur.
    func serviceCatalog() async throws -> [CatalogService]
    /// Crée une mission en attente de devis pour un service du catalogue.
    func requestService(serviceId: String, commune: String, description: String) async throws
    /// « Décrire mon besoin » : une demande libre transmise à l'équipe.
    func sendFreeRequest(title: String, text: String) async throws

    // --- Profil et compte ---

    /// Prénom, nom et commune. Le numéro ne change pas ici : il sert à se
    /// connecter.
    func updateProfile(firstName: String, lastName: String, commune: String) async throws -> Profile
    /// Les téléphones reliés au compte, celui-ci d'abord.
    func devices() async throws -> [AppDevice]
    /// Coupe un autre téléphone, pour toujours : il devra se reconnecter par
    /// code. Ce téléphone-ci se déconnecte par « Se déconnecter ».
    func signOutDevice(id: Int) async throws
    /// Les documents en vigueur pour les rôles de la personne.
    func legalDocuments() async throws -> [LegalDocument]
    func legalText(_ key: LegalDocumentKey) async throws -> LegalText
    /// Demande à devenir prestataire. Le profil reste en vérification jusqu'à
    /// la décision de l'équipe NexisHub. Le recto, le verso et la vidéo ne
    /// servent qu'à cette vérification. Les preuves de réalisations sont
    /// facultatives (`Portfolio()` si aucune) et revues par l'équipe avant
    /// d'être montrées aux clients.
    func applyAsProvider(services: [String], communes: [String], identity: IdentityCapture,
                         portfolio: Portfolio, acceptedTermsVersion: Date?) async throws
    /// Les services de la demande prestataire (vide pour un client seulement).
    func providerServices() async throws -> [String]
    /// Les preuves de réalisations envoyées, avec la décision de l'équipe
    /// pour chaque service.
    func portfolio() async throws -> Portfolio
    /// Une demande de preuves faite par l'équipe, s'il y en a une en cours.
    func portfolioRequest() async throws -> PortfolioRequest?
    /// Remplace les preuves envoyées (prestataire en vérification ou
    /// vérifié). Répond aussi à la demande de l'équipe, s'il y en a une. Un
    /// service modifié repasse par l'équipe avant d'être remontré.
    func sendPortfolio(_ portfolio: Portfolio) async throws

    // --- Client : devis, paiement, suivi, litige ---

    func mission(_ id: Int) async throws -> Mission
    /// Les devis reçus pour une mission, le mieux noté en premier.
    func quotes(missionId: Int) async throws -> [Quote]
    /// Les réalisations approuvées du prestataire d'un devis (`nil` s'il n'en
    /// a pas). Jamais ses diplômes : seulement le fait qu'ils sont vérifiés.
    func providerShowcase(quoteId: Int) async throws -> ProviderShowcase?
    func payAccounts() async throws -> [PayAccount]
    /// Demande le paiement du devis choisi à l'opérateur. Le montant est celui
    /// du devis enregistré sur le serveur, jamais un calcul de l'app.
    func pay(missionId: Int, quoteId: Int, mobileOperator: MobileOperator) async throws -> Mission
    /// Le client confirme que le travail est fait : le serveur verse l'argent
    /// sécurisé au prestataire.
    func confirmDone(missionId: Int) async throws -> Mission
    /// Le litige de la mission, s'il y en a un.
    func dispute(missionId: Int) async throws -> Dispute?
    /// Le client signale un problème : le serveur ouvre le litige et bloque
    /// l'argent sécurisé jusqu'à la décision. Refusé si la mission n'a pas
    /// d'argent sécurisé.
    func reportProblem(missionId: Int, reason: DisputeReason, text: String) async throws -> Dispute

    // --- Espace prestataire ---

    func providerHome() async throws -> ProviderHome
    /// « En service » : reçoit ou non les nouvelles demandes.
    func setInService(_ value: Bool) async throws
    func providerRequest(missionId: Int) async throws -> ProviderRequest
    /// Envoie un devis. Le serveur refuse un prix nul ou négatif, ou une
    /// mission qui n'est plus ouverte.
    func sendQuote(missionId: Int, price: Money, slot: Date) async throws
    func providerJob(missionId: Int) async throws -> ProviderJob
    func setSharing(missionId: Int, _ value: Bool) async throws -> ProviderJob
    /// « Je suis parti ».
    func leaveForJob(missionId: Int) async throws -> ProviderJob
    /// « Je suis arrivé » : prévient le client, ne confirme rien seul.
    func signalArrival(missionId: Int) async throws -> ProviderJob
    /// Le code de présence du client, tapé par le prestataire. Cinq essais au
    /// plus ; ensuite seul l'appui du client confirme.
    func enterPresenceCode(missionId: Int, code: String) async throws -> PresenceResult
    /// « J'ai terminé » : le client a 48 h pour confirmer ou signaler.
    func finishJob(missionId: Int) async throws -> ProviderJob
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

    /// Démonstration : aucun message ne part. L'envoi réel prend un moment ;
    /// ce délai le reproduit pour que l'attente (pictogrammes qui se relaient)
    /// se voie et se teste dans l'aperçu.
    func sendCode(phone: String, channel: CodeChannel) async throws {
        guard DrcPhone.parse(phone).isValid, codeChannels.contains(channel) else { throw InvalidRequest() }
        try await Task.sleep(for: .milliseconds(1500))
    }

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
                                    commune: commune, termsVersion: acceptedTermsVersion)
        activePhone = phone
        return true
    }

    private lazy var sampleProfile = Profile(
        firstName: "Grâce", lastName: "Nsimba", phone: Self.samplePhone,
        commune: "Limete", providerStatus: .verified, termsVersion: signupTermsVersion)

    func profile() async throws -> Profile {
        registered[activePhone] ?? sampleProfile
    }

    private func store(_ profile: Profile) {
        if isSample { sampleProfile = profile } else { registered[activePhone] = profile }
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

    private func quote(_ id: Int, _ name: String, _ initials: String, _ color: UInt32,
                       _ rating: Double, _ reviews: Int, _ price: Money, _ slot: Date) -> Quote {
        Quote(id: id, providerName: name, initials: initials, avatarColor: color,
              rating: rating, reviews: reviews, price: price, slot: slot)
    }

    private lazy var sampleMissions: [Mission] = [
        Mission(id: 51, service: .plomberie, commune: "Gombe", status: .inProgress,
                payment: .secured, amount: Money(500, .usd), providerName: "Jean M.",
                when: ago(hours: 1),
                chosen: quote(511, "Jean M.", "JM", 0x1E7A5C, 4.8, 92, Money(500, .usd),
                              now.addingTimeInterval(40 * 60)),
                distanceKm: 2.4,
                steps: [.paid: ago(minutes: 30), .onTheWay: ago(minutes: 19)]),
        Mission(id: 52, service: .nettoyage, commune: "Limete", status: .quoted,
                payment: .none, quotesCount: 3, when: ago(hours: 3), detail: "3 pièces",
                wanted: "Samedi matin"),
        Mission(id: 49, service: .coiffure, commune: "Limete", status: .awaitingConfirmation,
                payment: .secured, amount: Money(15_000, .cdf), providerName: "Nadia K.",
                when: ago(hours: 5),
                chosen: quote(491, "Nadia K.", "NK", 0xC2416B, 4.9, 57, Money(15_000, .cdf),
                              ago(hours: 3)),
                steps: [.paid: ago(hours: 5), .onTheWay: ago(hours: 3.5), .onSite: ago(hours: 3),
                        .workDone: ago(minutes: 20)]),
        Mission(id: 47, service: .climatisation, commune: "Bandal", status: .disputed,
                payment: .blocked, amount: Money(6_000, .usd), providerName: "Rodrigue T.",
                when: ago(days: 1)),
        Mission(id: 44, service: .jardinage, commune: "Ngaliema", status: .disputed,
                payment: .blocked, amount: Money(30_000, .cdf), providerName: "Patrick B.",
                when: ago(days: 4)),
        Mission(id: 53, service: .electricite, commune: "Ngaliema", status: .pending,
                payment: .none, when: ago(minutes: 30)),
        Mission(id: 41, service: .plomberie, commune: "Gombe", status: .completed,
                payment: .released, amount: Money(4_500, .usd), providerName: "Jean M.",
                when: ago(days: 2), rated: true, providerRating: 4.8, providerReviews: 92),
        Mission(id: 38, service: .nettoyage, commune: "Limete", status: .completed,
                payment: .released, amount: Money(25_000, .cdf), providerName: "Prisca K.",
                when: ago(days: 6), rated: true, providerRating: 4.9, providerReviews: 212),
        Mission(id: 33, service: .electricite, commune: "Limete", status: .completed,
                payment: .released, amount: Money(18_000, .cdf), providerName: "Alain L.",
                when: ago(days: 12), providerRating: 4.6, providerReviews: 58),
    ]

    private lazy var sampleMovements: [Movement] = [
        Movement(kind: .payment, label: "Plomberie · Gombe", amount: Money(-500, .usd),
                 when: ago(hours: 1), state: .secured),
        Movement(kind: .refund, label: "Visite annulée", amount: Money(10_000, .cdf),
                 when: ago(days: 1), state: .refunded),
        Movement(kind: .release, label: "Plomberie · Gombe", amount: Money(-4_500, .usd),
                 when: ago(days: 2), state: .released),
        Movement(kind: .release, label: "Nettoyage · Limete", amount: Money(-25_000, .cdf),
                 when: ago(days: 6), state: .released),
    ]

    private lazy var disputes: [Int: Dispute] = [
        47: Dispute(missionId: 47, reason: .badWork, text: "Le climatiseur coule encore dans la chambre.",
                    photos: 2, openedAt: ago(hours: 20),
                    providerReply: "Je peux repasser demain matin.", providerRepliedAt: ago(hours: 17)),
        44: Dispute(missionId: 44, reason: .notFinished, text: "La haie du fond n'a pas été taillée.",
                    photos: 1, openedAt: ago(days: 3), outcome: .refund, decidedAt: ago(hours: 2),
                    clientAmount: Money(30_000, .cdf), providerAmount: Money(0, .cdf),
                    contestUntil: ago(hours: 2).addingTimeInterval(3 * 86_400)),
    ]

    /// Le prochain jour de la semaine (1 = dimanche … 7 = samedi) à cette heure.
    private func next(weekday: Int, hour: Int) -> Date {
        let calendar = Calendar(identifier: .gregorian)
        let today = calendar.component(.weekday, from: now)
        var days = (weekday - today + 7) % 7
        if days == 0 { days = 7 }
        let day = calendar.date(byAdding: .day, value: days, to: now)!
        return calendar.date(bySettingHour: hour, minute: 0, second: 0, of: day)!
    }

    private lazy var quotesByMission: [Int: [Quote]] = [
        52: [
            quote(521, "Prisca K.", "PK", 0x494C95, 4.9, 128, Money(25_000, .cdf), next(weekday: 7, hour: 9)),
            quote(522, "Joël M.", "JM", 0x1E7A5C, 4.7, 64, Money(22_000, .cdf), next(weekday: 7, hour: 10)),
            quote(523, "Aline L.", "AL", 0xC98200, 4.6, 31, Money(28_000, .cdf), next(weekday: 7, hour: 8)),
        ],
    ]

    func missions() async throws -> [Mission] {
        (requested[activePhone] ?? []) + (isSample ? sampleMissions : [])
    }

    /// Démonstration : aucune notification. La liste se remplira quand
    /// l'app sera branchée au serveur.
    func notifications() async throws -> [AppNotification] { [] }

    func movements() async throws -> [Movement] {
        isSample ? sampleMovements : []
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

    // MARK: Profil et compte

    let providerTermsVersion = DateComponents(
        calendar: Calendar(identifier: .gregorian), year: 2026, month: 11, day: 20
    ).date!

    func updateProfile(firstName: String, lastName: String, commune: String) async throws -> Profile {
        let first = firstName.trimmingCharacters(in: .whitespacesAndNewlines)
        let last = lastName.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !first.isEmpty, first.count <= 60, !last.isEmpty, last.count <= 60,
              communes.contains(commune) else { throw NexisRefusal(code: "profile_invalid") }
        let current = try await profile()
        let updated = Profile(firstName: first, lastName: last, phone: current.phone, commune: commune,
                              providerStatus: current.providerStatus, termsVersion: current.termsVersion)
        store(updated)
        return updated
    }

    private lazy var sampleDevices: [AppDevice] = [
        AppDevice(id: 1, label: "iPhone 12", platform: .ios, addedAt: ago(days: 58), lastSeenAt: now,
                  moneyUnlockedAt: ago(days: 58), isCurrent: true),
        AppDevice(id: 2, label: "Tecno Spark 10", platform: .android, addedAt: ago(hours: 20),
                  lastSeenAt: ago(hours: 3), moneyUnlockedAt: ago(hours: 20).addingTimeInterval(72 * 3600),
                  isCurrent: false),
    ]

    func devices() async throws -> [AppDevice] {
        guard isSample else {
            return [AppDevice(id: 1, label: "iPhone", platform: .ios, addedAt: now, lastSeenAt: now,
                              moneyUnlockedAt: now, isCurrent: true)]
        }
        return sampleDevices
    }

    func signOutDevice(id: Int) async throws {
        guard let device = try await devices().first(where: { $0.id == id }) else {
            throw NexisRefusal(code: "device_not_found")
        }
        guard !device.isCurrent else { throw NexisRefusal(code: "use_sign_out") }
        sampleDevices.removeAll { $0.id == id }
    }

    func legalDocuments() async throws -> [LegalDocument] {
        let profile = try await profile()
        var documents = [LegalDocument(key: .cgu, version: signupTermsVersion,
                                       acceptedAt: profile.termsVersion.map { _ in signupTermsVersion })]
        if profile.providerStatus != nil {
            documents.append(LegalDocument(key: .providerTerms, version: providerTermsVersion,
                                           acceptedAt: providerTermsAcceptedAt ?? providerTermsVersion))
        }
        return documents
    }

    private var providerTermsAcceptedAt: Date?

    /// Aperçu : aucune version n'est publiée, donc pas de texte.
    func legalText(_ key: LegalDocumentKey) async throws -> LegalText {
        LegalText(key: key, version: key == .cgu ? signupTermsVersion : providerTermsVersion, text: nil)
    }

    private var chosenServices: [String] = []
    private var sentPortfolio = Portfolio()
    private var pendingPortfolioRequest: PortfolioRequest?

    func applyAsProvider(services: [String], communes chosen: [String], identity: IdentityCapture,
                         portfolio: Portfolio, acceptedTermsVersion: Date?) async throws {
        let current = try await profile()
        let catalog = Set(try await serviceCatalog().map(\.id))
        guard current.providerStatus == nil,
              !services.isEmpty, services.count <= 50, Set(services).isSubset(of: catalog),
              !chosen.isEmpty, chosen.count <= 50, Set(chosen).isSubset(of: Set(communes)),
              identity.isComplete,
              portfolio.isValid(services: Set(services)),
              acceptedTermsVersion == providerTermsVersion
        else { throw NexisRefusal(code: "provider_application_invalid") }
        // Aperçu : le recto, le verso et la vidéo ne sont gardés nulle part ;
        // les preuves restent en mémoire, sur ce téléphone.
        try await Task.sleep(for: .seconds(1))
        providerTermsAcceptedAt = .now
        chosenServices = services
        sentPortfolio = portfolio.resubmitted(over: Portfolio())
        store(Profile(firstName: current.firstName, lastName: current.lastName, phone: current.phone,
                      commune: current.commune, providerStatus: .pending, termsVersion: current.termsVersion))
    }

    func providerServices() async throws -> [String] { chosenServices }

    func portfolio() async throws -> Portfolio { sentPortfolio }

    func portfolioRequest() async throws -> PortfolioRequest? { pendingPortfolioRequest }

    func sendPortfolio(_ portfolio: Portfolio) async throws {
        guard try await profile().providerStatus != nil, portfolio.isValid(services: Set(chosenServices)) else {
            throw NexisRefusal(code: "portfolio_invalid")
        }
        try await Task.sleep(for: .seconds(1))
        sentPortfolio = portfolio.resubmitted(over: sentPortfolio)
        pendingPortfolioRequest = nil
    }

    /// Démonstration et tests : la décision de l'équipe sur un service.
    func demoReview(serviceId: String, _ review: ProofReview) {
        sentPortfolio.works = sentPortfolio.works.map { work in
            var reviewed = work
            if work.serviceId == serviceId { reviewed.review = review }
            return reviewed
        }
    }

    /// Démonstration et tests : l'équipe a vérifié les diplômes.
    func demoVerifyCertificates() {
        sentPortfolio.certificatesVerified = !sentPortfolio.certificates.isEmpty
    }

    /// Démonstration et tests : l'équipe demande des preuves.
    func demoAskPortfolio(services: [String]) {
        pendingPortfolioRequest = PortfolioRequest(services: services, askedAt: .now)
    }

    // MARK: Client : devis, paiement, suivi, litige

    func mission(_ id: Int) async throws -> Mission {
        guard let found = try await missions().first(where: { $0.id == id }) else {
            throw NexisRefusal(code: "mission_not_found")
        }
        return found
    }

    func quotes(missionId: Int) async throws -> [Quote] {
        (quotesByMission[missionId] ?? []).sorted { $0.rating > $1.rating }
    }

    func providerShowcase(quoteId: Int) async throws -> ProviderShowcase? {
        demoPortfolios[quoteId]?.showcase
    }

    /// Ce que l'équipe a reçu de Prisca et de Joël : un service approuvé, un
    /// refusé, un en attente. Seul l'approuvé arrive chez le client ; les
    /// diplômes ne quittent jamais l'équipe.
    private lazy var demoPortfolios: [Int: Portfolio] = [
        521: Portfolio(works: [
            WorkProof(serviceId: "nettoyage",
                      photos: ["sparkles", "bubbles.and.sparkles.fill", "sofa.fill"].map { DemoPictures.jpeg(symbol: $0) },
                      note: "Salon et cuisine après travaux, Limete, 2025", review: .approved),
            WorkProof(serviceId: "jardinage", photos: [DemoPictures.jpeg(symbol: "leaf.fill")],
                      note: "", review: .rejected),
        ], certificates: [DemoPictures.jpeg(symbol: "doc.text.fill")], certificatesVerified: true),
        522: Portfolio(works: [
            WorkProof(serviceId: "nettoyage", photos: [DemoPictures.jpeg(symbol: "sparkles")],
                      note: "", review: .pending),
        ]),
    ]

    func payAccounts() async throws -> [PayAccount] {
        [
            PayAccount(mobileOperator: .mpesa, maskedNumber: "+243 81 •• •• 412"),
            PayAccount(mobileOperator: .orange, maskedNumber: "+243 89 •• •• 207"),
            PayAccount(mobileOperator: .airtel, maskedNumber: nil),
        ]
    }

    private func replace(_ mission: Mission) {
        guard let index = sampleMissions.firstIndex(where: { $0.id == mission.id }) else { return }
        sampleMissions[index] = mission
    }

    func pay(missionId: Int, quoteId: Int, mobileOperator: MobileOperator) async throws -> Mission {
        var mission = try await mission(missionId)
        guard mission.status == .quoted,
              let quote = quotesByMission[missionId]?.first(where: { $0.id == quoteId }),
              try await payAccounts().contains(where: { $0.mobileOperator == mobileOperator && $0.maskedNumber != nil })
        else { throw NexisRefusal(code: "payment_refused") }
        // Démonstration : l'opérateur accepte après quelques secondes.
        try await Task.sleep(for: .seconds(3))
        mission.status = .confirmed
        mission.payment = .secured
        mission.amount = quote.price
        mission.providerName = quote.providerName
        mission.chosen = quote
        mission.steps = [.paid: .now]
        replace(mission)
        sampleMovements.insert(
            Movement(kind: .payment, label: "\(mission.service.name("fr")) · \(mission.commune)",
                     amount: Money(-quote.price.minorUnits, quote.price.currency),
                     when: .now, state: .secured), at: 0)
        return mission
    }

    func confirmDone(missionId: Int) async throws -> Mission {
        var mission = try await mission(missionId)
        guard mission.status == .awaitingConfirmation, mission.payment == .secured else {
            throw NexisRefusal(code: "mission_not_awaiting_confirmation")
        }
        mission.status = .completed
        mission.payment = .released
        mission.steps[.confirmed] = .now
        replace(mission)
        return mission
    }

    func dispute(missionId: Int) async throws -> Dispute? { disputes[missionId] }

    func reportProblem(missionId: Int, reason: DisputeReason, text: String) async throws -> Dispute {
        var mission = try await mission(missionId)
        let words = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard [.confirmed, .inProgress, .awaitingConfirmation].contains(mission.status),
              mission.payment == .secured, !words.isEmpty, words.count <= 500 else {
            throw NexisRefusal(code: "dispute_not_allowed")
        }
        let dispute = Dispute(missionId: missionId, reason: reason, text: words,
                              photos: 0, openedAt: .now)
        disputes[missionId] = dispute
        mission.status = .disputed
        mission.payment = .blocked
        replace(mission)
        return dispute
    }

    // MARK: Espace prestataire (fictif)

    private var inService = true

    /// Code de présence de la cliente dans l'aperçu. Sur le vrai serveur, il
    /// n'est donné qu'au client et n'est jamais enregistré.
    static let demoPresenceCode = "2580"

    private lazy var requests: [ProviderRequest] = [
        ProviderRequest(missionId: 71, service: .nettoyage, commune: "Limete",
                        summary: "Samedi matin · 3 pièces",
                        description: "Appartement de 3 pièces, cuisine et salle de bain comprises. Produits à apporter.",
                        wanted: "Samedi matin", photos: 3, receivedAt: ago(minutes: 3),
                        slotChoices: [next(weekday: 7, hour: 8), next(weekday: 7, hour: 9),
                                      next(weekday: 7, hour: 10)]),
        ProviderRequest(missionId: 72, service: .jardinage, commune: "Ngaliema",
                        summary: "Dimanche · petit jardin",
                        description: "Petit jardin devant la maison : tondre et tailler la haie.",
                        wanted: "Dimanche", photos: 1, receivedAt: ago(minutes: 12),
                        slotChoices: [next(weekday: 1, hour: 9), next(weekday: 1, hour: 14)]),
    ]

    private lazy var jobs: [ProviderJob] = [
        ProviderJob(missionId: 61, service: .nettoyage, commune: "Limete", clientName: "Esther M.",
                    clientInitials: "EM", clientColor: 0xC2416B,
                    place: "Limete, 7e rue · près de l'école", amount: Money(25_000, .cdf),
                    steps: [.clientPaid: ago(minutes: 40), .leftHome: ago(minutes: 12)],
                    sharing: true),
    ]

    func providerHome() async throws -> ProviderHome {
        let securedFrancs = jobs
            .filter { $0.steps[.finished] == nil && $0.amount.currency == .cdf }
            .reduce(0) { $0 + $1.amount.minorUnits }
        return ProviderHome(inService: inService, communes: ["Limete", "Gombe"],
                            available: Money(120_000, .cdf), secured: Money(securedFrancs, .cdf),
                            requests: requests, jobs: jobs)
    }

    func setInService(_ value: Bool) async throws { inService = value }

    func providerRequest(missionId: Int) async throws -> ProviderRequest {
        guard let request = requests.first(where: { $0.missionId == missionId }) else {
            throw NexisRefusal(code: "mission_not_open")
        }
        return request
    }

    func sendQuote(missionId: Int, price: Money, slot: Date) async throws {
        guard let index = requests.firstIndex(where: { $0.missionId == missionId }) else {
            throw NexisRefusal(code: "mission_not_open")
        }
        guard !requests[index].quoted else { throw NexisRefusal(code: "quote_already_sent") }
        guard price.minorUnits > 0 else { throw NexisRefusal(code: "price_must_be_positive") }
        guard slot > .now else { throw NexisRefusal(code: "slot_in_the_past") }
        requests[index].quoted = true
    }

    func providerJob(missionId: Int) async throws -> ProviderJob {
        guard let job = jobs.first(where: { $0.missionId == missionId }) else {
            throw NexisRefusal(code: "mission_not_found")
        }
        return job
    }

    @discardableResult
    private func save(_ job: ProviderJob) -> ProviderJob {
        if let index = jobs.firstIndex(where: { $0.missionId == job.missionId }) { jobs[index] = job }
        return job
    }

    func setSharing(missionId: Int, _ value: Bool) async throws -> ProviderJob {
        var job = try await providerJob(missionId: missionId)
        job.sharing = value
        return save(job)
    }

    func leaveForJob(missionId: Int) async throws -> ProviderJob {
        var job = try await providerJob(missionId: missionId)
        guard job.steps[.leftHome] == nil else { return job }
        job.steps[.leftHome] = .now
        return save(job)
    }

    func signalArrival(missionId: Int) async throws -> ProviderJob {
        var job = try await providerJob(missionId: missionId)
        guard job.steps[.leftHome] != nil else { throw NexisRefusal(code: "not_on_the_way") }
        job.arrivalSignaled = true
        return save(job)
    }

    func enterPresenceCode(missionId: Int, code: String) async throws -> PresenceResult {
        var job = try await providerJob(missionId: missionId)
        if job.steps[.arrived] != nil { return .confirmed }
        guard job.arrivalSignaled else { throw NexisRefusal(code: "arrival_not_signaled") }
        guard job.codeAttemptsLeft > 0 else { return .locked }
        guard code.trimmingCharacters(in: .whitespaces) == Self.demoPresenceCode else {
            job.codeAttemptsLeft -= 1
            save(job)
            return job.codeAttemptsLeft == 0 ? .locked : .wrongCode
        }
        job.steps[.arrived] = .now
        save(job)
        return .confirmed
    }

    func finishJob(missionId: Int) async throws -> ProviderJob {
        var job = try await providerJob(missionId: missionId)
        guard job.steps[.arrived] != nil else { throw NexisRefusal(code: "arrival_not_confirmed") }
        guard job.steps[.finished] == nil else { return job }
        job.steps[.finished] = .now
        return save(job)
    }
}
