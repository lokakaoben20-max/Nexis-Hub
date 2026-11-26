import UIKit
import XCTest
@testable import NexisHub

final class MoneyTests: XCTestCase {
    func testFrancsWithoutDecimals() {
        XCTAssertEqual(Money(25_000, .cdf).formatted("fr"), "25\u{202F}000 FC")
        XCTAssertEqual(Money(25_000, .cdf).formatted("en"), "25,000 FC")
    }

    func testDollarsAlwaysTwoDecimals() {
        XCTAssertEqual(Money(1_250, .usd).formatted("fr"), "12,50 USD")
        XCTAssertEqual(Money(1_250, .usd).formatted("en"), "12.50 USD")
        XCTAssertEqual(Money(5, .usd).formatted("ln"), "0,05 USD")
        XCTAssertEqual(Money(123_456_700, .usd).formatted("en"), "1,234,567.00 USD")
    }

    func testNegativeAmounts() {
        XCTAssertEqual(Money(-4_500, .usd).formatted("fr"), "−45,00 USD")
    }
}

final class DrcPhoneTests: XCTestCase {
    func testStripsCountryCodeAndTrunkZero() {
        XCTAssertEqual(DrcPhone.parse("+243 812 345 412").digits, "812345412")
        XCTAssertEqual(DrcPhone.parse("00243812345412").digits, "812345412")
        XCTAssertEqual(DrcPhone.parse("0812345412").digits, "812345412")
    }

    func testValidityAndFormat() {
        let phone = DrcPhone.parse("812345412")
        XCTAssertTrue(phone.isValid)
        XCTAssertEqual(phone.formatted, "81 234 5412")
        XCTAssertEqual(phone.e164, "+243812345412")
        XCTAssertFalse(DrcPhone.parse("11").prefixKnown)
        XCTAssertFalse(DrcPhone.parse("8123").isValid)
    }
}

final class TextsTests: XCTestCase {
    private var texts: Texts {
        let url = Bundle(for: NexisHub.AppModel.self).url(forResource: "textes", withExtension: "json")!
        return Texts(json: try! Data(contentsOf: url))
    }

    func testEveryKeyUsedByTheAppExistsInThreeLanguages() {
        let keys = ["slogan", "start", "haveAccount", "navHome", "navMissions", "navWallet",
                    "navProfile", "requestService", "whichService", "helloHome", "eveningHome",
                    "heldForMissions", "signupTitle", "signupAcceptTerms", "serviceRequestSaved"]
        for key in keys {
            for language in ["fr", "ln", "en"] {
                XCTAssertNotEqual(texts.text(key, language), key, "\(key) manque en \(language)")
            }
        }
    }

    func testPlaceholdersAndPlurals() {
        XCTAssertEqual(texts.text("helloHome", "fr", ["name": "Grâce"]), "Bonjour, Grâce")
        XCTAssertEqual(texts.plural("devicesCount", "fr", count: 1), "1 appareil connecté")
        XCTAssertEqual(texts.plural("devicesCount", "fr", count: 3), "3 appareils connectés")
    }
}

@MainActor
final class DemoRepositoryTests: XCTestCase {
    func testSignupRequiresCurrentTerms() {
        let repo = DemoRepository()
        XCTAssertFalse(repo.registerClient(phone: "+243991112222", firstName: "Ana", lastName: "K",
                                           commune: "Gombe", acceptedTermsVersion: nil))
        XCTAssertTrue(repo.registerClient(phone: "+243991112222", firstName: "Ana", lastName: "K",
                                          commune: "Gombe",
                                          acceptedTermsVersion: repo.signupTermsVersion))
    }

    func testServiceRequestBecomesPendingMission() async throws {
        let repo = DemoRepository()
        try await repo.requestService(serviceId: "jardinage", commune: "Limete",
                                      description: "Tailler la haie du jardin")
        let first = try await repo.missions().first
        XCTAssertEqual(first?.status, .pending)
        XCTAssertEqual(first?.catalogService?.id, "jardinage")
    }

    func testDemoHasNoNotificationsYet() async throws {
        let notifications = try await DemoRepository().notifications()
        XCTAssertTrue(notifications.isEmpty)
    }

    func testSendCodeAcceptsValidNumberOnOfferedChannel() async throws {
        let repo = DemoRepository()
        try await repo.sendCode(phone: "+243812345678", channel: .whatsapp)
    }

    func testSendCodeRejectsIncompleteNumber() async {
        let repo = DemoRepository()
        do {
            try await repo.sendCode(phone: "+24381234", channel: .sms)
            XCTFail("un numéro incomplet ne doit pas recevoir de code")
        } catch {}
    }

    func testServiceRequestRejectsShortDescription() async {
        let repo = DemoRepository()
        do {
            try await repo.requestService(serviceId: "jardinage", commune: "Limete", description: "court")
            XCTFail("une demande trop courte doit être refusée")
        } catch {}
    }
}

final class PictogrammesTests: XCTestCase {
    func testEveryServiceHasItsPictogramsInTheAppBundle() {
        let bundle = Bundle(for: NexisHub.AppModel.self)
        for service in Service.allCases {
            let icons = Pictogrammes.icons(for: service)
            XCTAssertFalse(icons.isEmpty, "\(service) sans pictogramme")
            for name in icons {
                XCTAssertNotNil(UIImage(named: name, in: bundle, with: nil), "\(name) absent du catalogue")
            }
        }
        for name in Pictogrammes.byService.values.flatMap({ $0 }) {
            XCTAssertNotNil(UIImage(named: name, in: bundle, with: nil), "\(name) absent du catalogue")
        }
    }

    func testLoaderAndLogoAreInTheAppBundle() {
        let bundle = Bundle(for: NexisHub.AppModel.self)
        for name in PictoLoader.icons {
            XCTAssertNotNil(UIImage(named: name, in: bundle, with: nil), "\(name) absent du catalogue")
        }
        XCTAssertNotNil(UIImage(named: "LogoBlanc", in: bundle, with: nil), "logo écrit absent")
    }

    func testOtherServiceStaysStill() {
        XCTAssertEqual(Pictogrammes.icons(for: .autre).count, 1)
    }
}

@MainActor
final class FlowsTests: XCTestCase {
    private func refusal(_ block: () async throws -> Void) async -> String? {
        do { try await block(); return nil } catch let refusal as NexisRefusal { return refusal.code } catch { return "\(error)" }
    }

    func testQuotesComeBestRatedFirst() async throws {
        let quotes = try await DemoRepository().quotes(missionId: 52)
        XCTAssertEqual(quotes.map(\.providerName), ["Prisca K.", "Joël M.", "Aline L."])
    }

    func testPayingSecuresTheQuotedAmount() async throws {
        let repo = DemoRepository()
        let paid = try await repo.pay(missionId: 52, quoteId: 522, mobileOperator: .mpesa)
        XCTAssertEqual(paid.status, .confirmed)
        XCTAssertEqual(paid.payment, .secured)
        XCTAssertEqual(paid.amount, Money(22_000, .cdf))
        XCTAssertEqual(paid.providerFirstName, "Joël")
        let stored = try await repo.mission(52)
        XCTAssertEqual(stored.status, .confirmed)
    }

    func testCannotPayWithoutARegisteredNumber() async {
        let repo = DemoRepository()
        let code = await refusal { _ = try await repo.pay(missionId: 52, quoteId: 521, mobileOperator: .airtel) }
        XCTAssertEqual(code, "payment_refused")
    }

    func testConfirmingReleasesTheMoney() async throws {
        let repo = DemoRepository()
        let done = try await repo.confirmDone(missionId: 49)
        XCTAssertEqual(done.status, .completed)
        XCTAssertEqual(done.payment, .released)
        let code = await refusal { _ = try await repo.confirmDone(missionId: 51) }
        XCTAssertEqual(code, "mission_not_awaiting_confirmation")
    }

    func testReportingBlocksSecuredMoneyOnly() async throws {
        let repo = DemoRepository()
        let noMoney = await refusal { _ = try await repo.reportProblem(missionId: 52, reason: .noShow, text: "Personne.") }
        XCTAssertEqual(noMoney, "dispute_not_allowed")
        let empty = await refusal { _ = try await repo.reportProblem(missionId: 51, reason: .noShow, text: "   ") }
        XCTAssertEqual(empty, "dispute_not_allowed")
        _ = try await repo.reportProblem(missionId: 51, reason: .noShow, text: "Personne n'est venu.")
        let blocked = try await repo.mission(51)
        XCTAssertEqual(blocked.payment, .blocked)
        let dispute = try await repo.dispute(missionId: 51)
        XCTAssertNotNil(dispute)
    }

    func testDecidedDisputeShowsServerAmounts() async throws {
        let dispute = try await DemoRepository().dispute(missionId: 44)
        XCTAssertEqual(dispute?.decided, true)
        XCTAssertEqual(dispute?.clientAmount, Money(30_000, .cdf))
    }

    func testQuoteMustBePositiveAndSentOnce() async throws {
        let repo = DemoRepository()
        let slot = try await repo.providerRequest(missionId: 71).slotChoices[0]
        let zero = await refusal { try await repo.sendQuote(missionId: 71, price: Money(0, .cdf), slot: slot) }
        XCTAssertEqual(zero, "price_must_be_positive")
        try await repo.sendQuote(missionId: 71, price: Money(25_000, .cdf), slot: slot)
        let quoted = try await repo.providerRequest(missionId: 71).quoted
        XCTAssertTrue(quoted)
        let twice = await refusal { try await repo.sendQuote(missionId: 71, price: Money(25_000, .cdf), slot: slot) }
        XCTAssertEqual(twice, "quote_already_sent")
    }

    func testPresenceCodeLocksAfterFiveWrongTries() async throws {
        let repo = DemoRepository()
        let early = await refusal { _ = try await repo.enterPresenceCode(missionId: 61, code: "0000") }
        XCTAssertEqual(early, "arrival_not_signaled")
        _ = try await repo.signalArrival(missionId: 61)
        for _ in 0..<4 {
            let result = try await repo.enterPresenceCode(missionId: 61, code: "0000")
            XCTAssertEqual(result, .wrongCode)
        }
        let fifth = try await repo.enterPresenceCode(missionId: 61, code: "0000")
        XCTAssertEqual(fifth, .locked)
        let after = try await repo.enterPresenceCode(missionId: 61, code: DemoRepository.demoPresenceCode)
        XCTAssertEqual(after, .locked)
    }

    func testRightCodeConfirmsArrivalThenJobCanFinish() async throws {
        let repo = DemoRepository()
        let early = await refusal { _ = try await repo.finishJob(missionId: 61) }
        XCTAssertEqual(early, "arrival_not_confirmed")
        _ = try await repo.signalArrival(missionId: 61)
        let result = try await repo.enterPresenceCode(missionId: 61, code: " 2580 ")
        XCTAssertEqual(result, .confirmed)
        let job = try await repo.finishJob(missionId: 61)
        XCTAssertNotNil(job.steps[.finished])
        let home = try await repo.providerHome()
        XCTAssertEqual(home.secured, Money(0, .cdf))
    }
}

@MainActor
final class PriceInputTests: XCTestCase {
    func testFrancsAreWholeAndPositive() {
        XCTAssertEqual(PriceInput.parse("25 000", .cdf), Money(25_000, .cdf))
        XCTAssertNil(PriceInput.parse("0", .cdf))
        XCTAssertNil(PriceInput.parse("12,5", .cdf))
        XCTAssertNil(PriceInput.parse("", .cdf))
    }

    func testDollarsKeepAtMostTwoDecimals() {
        XCTAssertEqual(PriceInput.parse("12,5", .usd), Money(1_250, .usd))
        XCTAssertEqual(PriceInput.parse("45", .usd), Money(4_500, .usd))
        XCTAssertEqual(PriceInput.parse("0.05", .usd), Money(5, .usd))
        XCTAssertNil(PriceInput.parse("1.234", .usd))
        XCTAssertNil(PriceInput.parse("0,00", .usd))
        XCTAssertNil(PriceInput.parse("1.2.3", .usd))
    }

    func testFrancsAreGroupedWhileTyping() {
        XCTAssertEqual(PriceInput.typed("25000", .cdf), "25 000")
        XCTAssertEqual(PriceInput.typed("1 2345 67", .cdf), "1 234 567")
        XCTAssertEqual(PriceInput.typed("12a,5", .usd), "12,5")
    }
}

@MainActor
final class DatesTests: XCTestCase {
    func testClockReadsLikeKinshasa() {
        let app = AppModel(repository: DemoRepository(), language: "fr")
        let calendar = Calendar.current
        let nine = calendar.date(bySettingHour: 9, minute: 0, second: 0, of: .now)!
        let late = calendar.date(bySettingHour: 20, minute: 41, second: 0, of: .now)!
        XCTAssertEqual(app.clock(nine), "9 h")
        XCTAssertEqual(app.clock(late), "20 h 41")
        app.language = "en"
        XCTAssertEqual(app.clock(late), "8:41 pm")
    }

    func testDaysLeftCountsWholeDays() {
        let now = Date.now
        XCTAssertEqual(daysLeft(until: now.addingTimeInterval(70 * 3600), now: now), 3)
        XCTAssertEqual(daysLeft(until: now.addingTimeInterval(-60), now: now), 0)
    }
}

@MainActor
final class AccountTests: XCTestCase {
    private func refusal(_ block: () async throws -> Void) async -> String? {
        do { try await block(); return nil } catch let refusal as NexisRefusal { return refusal.code } catch { return "\(error)" }
    }

    func testProfileUpdateKeepsPhoneAndChecksCommune() async throws {
        let repo = DemoRepository()
        let before = try await repo.profile()
        let updated = try await repo.updateProfile(firstName: " Grâce ", lastName: "Mbuyi", commune: "Gombe")
        XCTAssertEqual(updated.firstName, "Grâce")
        XCTAssertEqual(updated.commune, "Gombe")
        XCTAssertEqual(updated.phone, before.phone)
        let bad = await refusal { _ = try await repo.updateProfile(firstName: "Grâce", lastName: "Mbuyi", commune: "Paris") }
        XCTAssertEqual(bad, "profile_invalid")
    }

    func testOnlyOtherPhonesCanBeSignedOut() async throws {
        let repo = DemoRepository()
        let devices = try await repo.devices()
        let current = try XCTUnwrap(devices.first(where: \.isCurrent))
        let other = try XCTUnwrap(devices.first(where: { !$0.isCurrent }))
        XCTAssertGreaterThan(other.moneyHoursLeft(), 0)
        let own = await refusal { try await repo.signOutDevice(id: current.id) }
        XCTAssertEqual(own, "use_sign_out")
        try await repo.signOutDevice(id: other.id)
        let after = try await repo.devices()
        XCTAssertEqual(after.map(\.id), [current.id])
    }

    func testProviderApplicationNeedsEveryStep() async throws {
        let repo = DemoRepository()
        XCTAssertTrue(repo.registerClient(phone: "+243810000001", firstName: "Esther", lastName: "M",
                                          commune: "Limete", acceptedTermsVersion: repo.signupTermsVersion))
        let identity = IdentityCapture(document: .voterCard, recto: Data([1]), verso: Data([2]), video: Data([3]),
                                       videoSeconds: 7, headTurns: [.right, .left])
        let noTerms = await refusal {
            try await repo.applyAsProvider(services: ["nettoyage"], communes: ["Limete"], identity: identity, portfolio: Portfolio(),
                                           acceptedTermsVersion: nil)
        }
        XCTAssertEqual(noTerms, "provider_application_invalid")
        var noVerso = identity
        noVerso.verso = Data()
        let missingVerso = await refusal {
            try await repo.applyAsProvider(services: ["nettoyage"], communes: ["Limete"], identity: noVerso, portfolio: Portfolio(),
                                           acceptedTermsVersion: repo.providerTermsVersion)
        }
        XCTAssertEqual(missingVerso, "provider_application_invalid")
        var noVideo = identity
        noVideo.video = Data()
        let missingVideo = await refusal {
            try await repo.applyAsProvider(services: ["nettoyage"], communes: ["Limete"], identity: noVideo, portfolio: Portfolio(),
                                           acceptedTermsVersion: repo.providerTermsVersion)
        }
        XCTAssertEqual(missingVideo, "provider_application_invalid")
        // Passeport : une seule page, jamais de verso.
        var passportWithVerso = identity
        passportWithVerso.document = .passport
        let versoOnPassport = await refusal {
            try await repo.applyAsProvider(services: ["nettoyage"], communes: ["Limete"], identity: passportWithVerso, portfolio: Portfolio(),
                                           acceptedTermsVersion: repo.providerTermsVersion)
        }
        XCTAssertEqual(versoOnPassport, "provider_application_invalid")
        var passport = passportWithVerso
        passport.verso = nil
        XCTAssertTrue(passport.isComplete)
        var cardWithoutVerso = identity
        cardWithoutVerso.verso = nil
        XCTAssertFalse(cardWithoutVerso.isComplete)
        var oneTurn = identity
        oneTurn.headTurns = [.left, .left]
        let missingTurn = await refusal {
            try await repo.applyAsProvider(services: ["nettoyage"], communes: ["Limete"], identity: oneTurn, portfolio: Portfolio(),
                                           acceptedTermsVersion: repo.providerTermsVersion)
        }
        XCTAssertEqual(missingTurn, "provider_application_invalid")
        try await repo.applyAsProvider(services: ["nettoyage"], communes: ["Limete"], identity: identity, portfolio: Portfolio(),
                                       acceptedTermsVersion: repo.providerTermsVersion)
        let profile = try await repo.profile()
        XCTAssertEqual(profile.providerStatus, .pending)
        XCTAssertFalse(profile.isProvider)
        let documents = try await repo.legalDocuments()
        XCTAssertEqual(documents.map(\.key), [.cgu, .providerTerms])
    }
}

@MainActor
@MainActor
final class PortfolioTests: XCTestCase {
    private func work(_ service: String, photos: Int = 1, note: String = "") -> WorkProof {
        WorkProof(serviceId: service, photos: Array(repeating: Data([1]), count: photos), note: note)
    }

    func testPortfolioRules() {
        let services: Set<String> = ["plomberie", "electricite"]
        XCTAssertTrue(Portfolio().isValid(services: services))
        XCTAssertTrue(Portfolio(works: [work("plomberie", photos: 5)], certificates: [Data([2])]).isValid(services: services))
        // Plus de 5 photos, un service non choisi, deux fois le même service.
        XCTAssertFalse(Portfolio(works: [work("plomberie", photos: 6)]).isValid(services: services))
        XCTAssertFalse(Portfolio(works: [work("coiffure")]).isValid(services: services))
        XCTAssertFalse(Portfolio(works: [work("plomberie"), work("plomberie")]).isValid(services: services))
        // Une phrase trop longue, 4 attestations, un fichier vide.
        XCTAssertFalse(Portfolio(works: [work("plomberie", note: String(repeating: "a", count: 201))]).isValid(services: services))
        XCTAssertFalse(Portfolio(certificates: Array(repeating: Data([2]), count: 4)).isValid(services: services))
        XCTAssertFalse(Portfolio(certificates: [Data()]).isValid(services: services))
    }

    func testCleanedDropsServicesWithoutPhotos() {
        let portfolio = Portfolio(works: [work("plomberie", photos: 0, note: "Fuite"), work("electricite", note: "  Tableau  ")])
        XCTAssertEqual(portfolio.cleaned.works.map(\.serviceId), ["electricite"])
        XCTAssertEqual(portfolio.cleaned.works.first?.note, "Tableau")
        XCTAssertTrue(Portfolio(works: [work("plomberie", photos: 0)]).cleaned.isEmpty)
    }

    func testPortfolioIsSentWithTheApplicationAndLater() async throws {
        let repo = DemoRepository()
        XCTAssertTrue(repo.registerClient(phone: "+243810000002", firstName: "Jean", lastName: "K",
                                          commune: "Limete", acceptedTermsVersion: repo.signupTermsVersion))
        // Un client seulement ne peut pas envoyer de preuves.
        do {
            try await repo.sendPortfolio(Portfolio(works: [work("plomberie")]))
            XCTFail("refus attendu")
        } catch let refusal as NexisRefusal {
            XCTAssertEqual(refusal.code, "portfolio_invalid")
        }
        let identity = IdentityCapture(document: .passport, recto: Data([1]), verso: nil, video: Data([3]),
                                       videoSeconds: 7, headTurns: [.left, .right])
        try await repo.applyAsProvider(services: ["plomberie"], communes: ["Limete"], identity: identity,
                                       portfolio: Portfolio(works: [work("plomberie", photos: 2)]),
                                       acceptedTermsVersion: repo.providerTermsVersion)
        let sentCount = try await repo.portfolio().works.first?.photos.count
        XCTAssertEqual(sentCount, 2)
        let services = try await repo.providerServices()
        XCTAssertEqual(services, ["plomberie"])
        // L'équipe demande des preuves ; l'envoi y répond.
        repo.demoAskPortfolio(services: ["plomberie"])
        let asked = try await repo.portfolioRequest()
        XCTAssertEqual(asked?.services, ["plomberie"])
        try await repo.sendPortfolio(Portfolio(works: [work("plomberie", photos: 3)], certificates: [Data([4])]))
        let after = try await repo.portfolioRequest()
        XCTAssertNil(after)
        let certificates = try await repo.portfolio().certificates.count
        XCTAssertEqual(certificates, 1)
        // Un service qui n'est pas dans la demande est refusé.
        do {
            try await repo.sendPortfolio(Portfolio(works: [work("coiffure")]))
            XCTFail("refus attendu")
        } catch let refusal as NexisRefusal {
            XCTAssertEqual(refusal.code, "portfolio_invalid")
        }
    }

    func testClientsSeeOnlyApprovedWorksAndNeverCertificates() {
        var approved = work("plomberie", photos: 2, note: "Cuisine")
        approved.review = .approved
        var rejected = work("electricite")
        rejected.review = .rejected
        let portfolio = Portfolio(works: [approved, rejected, work("coiffure")],
                                  certificates: [Data([9])], certificatesVerified: true)
        let showcase = portfolio.showcase
        XCTAssertEqual(showcase?.works.map(\.serviceId), ["plomberie"])
        XCTAssertEqual(showcase?.works.first?.note, "Cuisine")
        XCTAssertEqual(showcase?.certificateVerified, true)
        // Rien d'approuvé : rien chez le client, même avec un diplôme vérifié.
        XCTAssertNil(Portfolio(works: [work("plomberie")], certificates: [Data([9])], certificatesVerified: true).showcase)
    }

    func testChangedWorksGoBackToTheTeam() {
        var approved = work("plomberie", photos: 2, note: "Cuisine")
        approved.review = .approved
        var rejected = work("electricite")
        rejected.review = .rejected
        let previous = Portfolio(works: [approved, rejected], certificates: [Data([9])], certificatesVerified: true)
        // Rien de changé : les décisions restent.
        let same = Portfolio(works: [work("plomberie", photos: 2, note: "Cuisine"), work("electricite")],
                             certificates: [Data([9])]).resubmitted(over: previous)
        XCTAssertEqual(same.works.map(\.review), [.approved, .rejected])
        XCTAssertTrue(same.certificatesVerified)
        // Une photo ajoutée, une phrase changée, un diplôme changé : tout repasse par l'équipe.
        let changed = Portfolio(works: [work("plomberie", photos: 3, note: "Cuisine"), work("electricite", note: "Tableau")],
                                certificates: [Data([8])]).resubmitted(over: previous)
        XCTAssertEqual(changed.works.map(\.review), [.pending, .pending])
        XCTAssertFalse(changed.certificatesVerified)
        XCTAssertNil(changed.showcase)
    }

    func testProviderSeesTheTeamDecision() async throws {
        let repo = DemoRepository()
        XCTAssertTrue(repo.registerClient(phone: "+243810000003", firstName: "Jean", lastName: "K",
                                          commune: "Limete", acceptedTermsVersion: repo.signupTermsVersion))
        let identity = IdentityCapture(document: .passport, recto: Data([1]), verso: nil, video: Data([3]),
                                       videoSeconds: 7, headTurns: [.left, .right])
        // L'app ne peut pas se donner l'accord de l'équipe.
        var forged = work("plomberie", photos: 2)
        forged.review = .approved
        try await repo.applyAsProvider(services: ["plomberie"], communes: ["Limete"], identity: identity,
                                       portfolio: Portfolio(works: [forged], certificatesVerified: true),
                                       acceptedTermsVersion: repo.providerTermsVersion)
        var sent = try await repo.portfolio()
        XCTAssertEqual(sent.works.first?.review, .pending)
        XCTAssertFalse(sent.certificatesVerified)
        repo.demoReview(serviceId: "plomberie", .approved)
        sent = try await repo.portfolio()
        XCTAssertEqual(sent.works.first?.review, .approved)
        // Renvoyé sans changement : toujours approuvé.
        try await repo.sendPortfolio(Portfolio(works: [work("plomberie", photos: 2)]))
        sent = try await repo.portfolio()
        XCTAssertEqual(sent.works.first?.review, .approved)
    }

    func testQuoteShowsOnlyTheApprovedShowcase() async throws {
        let repo = DemoRepository()
        let prisca = try await repo.providerShowcase(quoteId: 521)
        XCTAssertEqual(prisca?.works.map(\.serviceId), ["nettoyage"])
        XCTAssertEqual(prisca?.certificateVerified, true)
        // Joël attend encore l'équipe ; Aline n'a rien envoyé.
        let joel = try await repo.providerShowcase(quoteId: 522)
        XCTAssertNil(joel)
        let aline = try await repo.providerShowcase(quoteId: 523)
        XCTAssertNil(aline)
    }
}

final class IdentityGuideTests: XCTestCase {
    private func quad(_ dx: CGFloat = 0) -> CardQuad {
        CardQuad(topLeft: CGPoint(x: 0.1 + dx, y: 0.7), topRight: CGPoint(x: 0.9 + dx, y: 0.7),
                 bottomRight: CGPoint(x: 0.9 + dx, y: 0.2), bottomLeft: CGPoint(x: 0.1 + dx, y: 0.2))
    }

    func testCardMustStayStillBeforeThePhoto() {
        var tracker = StableCardTracker(needed: 4, tolerance: 0.02)
        XCTAssertFalse(tracker.add(quad()))
        XCTAssertFalse(tracker.add(quad(0.005)))
        XCTAssertFalse(tracker.add(quad(0.01)))
        XCTAssertTrue(tracker.add(quad(0.01)))
        // La carte bouge : on recommence à compter.
        XCTAssertFalse(tracker.add(quad(0.2)))
        XCTAssertFalse(tracker.add(nil))
        XCTAssertFalse(tracker.isHolding)
    }

    func testRectoNeedsAFace() {
        XCTAssertEqual(CardCheck.verdict(expected: .recto, faceFound: true, hashes: [1], rectoHash: nil), .accepted)
        XCTAssertEqual(CardCheck.verdict(expected: .recto, faceFound: false, hashes: [1], rectoHash: nil), .showRectoFirst)
    }

    func testVersoMustDifferFromRecto() {
        let recto: UInt64 = 0xF0F0_F0F0_F0F0_F0F0
        let same = recto ^ 0b111 // 3 bits d'écart
        let other: UInt64 = 0x0F0F_0F0F_0F0F_0F0F
        XCTAssertEqual(CardCheck.verdict(expected: .verso, faceFound: false, hashes: [same], rectoHash: recto), .stillRecto)
        XCTAssertEqual(CardCheck.verdict(expected: .verso, faceFound: false, hashes: [other], rectoHash: recto), .accepted)
        // Carte à l'envers : l'une des deux lectures ressemble au recto.
        XCTAssertEqual(CardCheck.verdict(expected: .verso, faceFound: false, hashes: [other, same], rectoHash: recto), .stillRecto)
        // Avec un visage visible, un écart moyen suffit à dire « encore le recto ».
        let medium = recto ^ 0xFFFF // 16 bits d'écart
        XCTAssertEqual(CardCheck.verdict(expected: .verso, faceFound: true, hashes: [medium], rectoHash: recto), .stillRecto)
        XCTAssertEqual(CardCheck.verdict(expected: .verso, faceFound: false, hashes: [medium], rectoHash: recto), .accepted)
    }

    func testPassportNeedsFaceAndMachineZone() {
        XCTAssertEqual(IdentityDocument.passport.sides, [.passportPage])
        XCTAssertEqual(IdentityDocument.drivingLicence.sides, [.recto, .verso])
        XCTAssertEqual(CardCheck.verdict(expected: .passportPage, faceFound: true, hashes: [], rectoHash: nil,
                                         machineZone: true), .accepted)
        XCTAssertEqual(CardCheck.verdict(expected: .passportPage, faceFound: true, hashes: [], rectoHash: nil,
                                         machineZone: false), .showPhotoPage)
        XCTAssertEqual(CardCheck.verdict(expected: .passportPage, faceFound: false, hashes: [], rectoHash: nil,
                                         machineZone: true), .showPhotoPage)
    }

    func testMachineZoneIsRecognised() {
        let zone = ["REPUBLIQUE DEMOCRATIQUE DU CONGO",
                    "P<CODMUKENDI<<GRACE<<<<<<<<<<<<<<<<<<<<<<<<",
                    "OP12345674COD9001014F3001019<<<<<<<<<<<<<<06"]
        XCTAssertTrue(MachineZone.found(in: zone))
        // Lu avec des espaces et des minuscules.
        XCTAssertTrue(MachineZone.found(in: ["p<cod mukendi<<grace<<<<<<<<<<<<<<<<<<<<", "OP1234567 4COD9001014F3001019<<<<<<<<<06"]))
        // Une seule ligne, ou une page de visas : pas la page photo.
        XCTAssertFalse(MachineZone.found(in: ["P<CODMUKENDI<<GRACE<<<<<<<<<<<<<<<<<<<<<<<<"]))
        XCTAssertFalse(MachineZone.found(in: ["VISAS", "Page 12", "ENTREE ARRIVAL 12/05/2025 KINSHASA NDJILI"]))
    }

    func testDifferenceHash() {
        let rising = (0..<72).map { UInt8(($0 % 9) * 20) }
        XCTAssertEqual(ImageHash.dHash(rising), UInt64.max)
        XCTAssertEqual(ImageHash.dHash(ImageHash.halfTurn(rising)), 0)
        XCTAssertEqual(ImageHash.distance(0, UInt64.max), 64)
    }

    func testHeadPoseUsesTheNoseForTheDirection() {
        // Nez vers la droite de l'image (non inversée) : la personne tourne vers sa gauche.
        XCTAssertEqual(HeadPose.position(FaceSample(faceCount: 1, turnDegrees: 28, noseOffset: 0.12)), .turned(.left))
        XCTAssertEqual(HeadPose.position(FaceSample(faceCount: 1, turnDegrees: 28, noseOffset: -0.12)), .turned(.right))
        XCTAssertEqual(HeadPose.position(FaceSample(faceCount: 1, turnDegrees: 4, noseOffset: 0.01)), .ahead)
        XCTAssertEqual(HeadPose.position(FaceSample(faceCount: 1, turnDegrees: 15, noseOffset: 0.05)), .between)
        XCTAssertEqual(HeadPose.position(FaceSample(faceCount: 1, turnDegrees: nil, noseOffset: -0.2)), .turned(.right))
    }

    private func run(_ script: inout SelfieScript, _ sample: FaceSample, frames: Int, from time: inout TimeInterval) -> [SelfieScript.Event] {
        (0..<frames).map { _ in time += 0.1; return script.feed(sample, at: time) }
    }

    func testSelfieStepsComeInOrder() {
        var script = SelfieScript(turns: [.right, .left])
        script.holdNeeded = 3
        var time: TimeInterval = 0
        let framed = FaceSample(faceCount: 1, turnDegrees: 2, noseOffset: 0)
        let left = FaceSample(faceCount: 1, turnDegrees: 30, noseOffset: 0.15)
        let right = FaceSample(faceCount: 1, turnDegrees: 30, noseOffset: -0.15)
        XCTAssertEqual(script.number, 1)
        XCTAssertEqual(run(&script, framed, frames: 3, from: &time).last, .startRecording)
        XCTAssertEqual(script.step, .turn(.right))
        // Tourner du mauvais côté ne fait pas avancer.
        XCTAssertFalse(run(&script, left, frames: 5, from: &time).contains(.advanced))
        XCTAssertEqual(run(&script, right, frames: 3, from: &time).last, .advanced)
        XCTAssertEqual(script.step, .turn(.left))
        XCTAssertEqual(run(&script, left, frames: 3, from: &time).last, .advanced)
        XCTAssertEqual(script.step, .lookAhead)
        XCTAssertEqual(script.number, 4)
        XCTAssertEqual(run(&script, framed, frames: 3, from: &time).last, .finished)
        XCTAssertEqual(script.step, .done)
        XCTAssertGreaterThan(script.seconds, 0)
    }

    func testSelfieRestartsWhenTooSlowOrFaceLost() {
        var script = SelfieScript(turns: [.left, .right])
        script.holdNeeded = 1
        script.timeLimit = 5
        script.lostLimit = 2
        XCTAssertEqual(script.feed(FaceSample(faceCount: 1, turnDegrees: 0), at: 0), .startRecording)
        XCTAssertEqual(script.feed(FaceSample(faceCount: 1, turnDegrees: 0), at: 6), .restart)
        XCTAssertEqual(script.step, .faceIn)
        XCTAssertEqual(script.feed(FaceSample(faceCount: 1, turnDegrees: 0), at: 7), .startRecording)
        XCTAssertEqual(script.feed(FaceSample(faceCount: 0), at: 7.1), SelfieScript.Event.none)
        XCTAssertEqual(script.feed(FaceSample(faceCount: 0), at: 7.2), SelfieScript.Event.none)
        XCTAssertEqual(script.feed(FaceSample(faceCount: 0), at: 7.3), .restart)
        // Deux visages : rien n'avance, et l'écran le dit.
        _ = script.feed(FaceSample(faceCount: 2), at: 8)
        XCTAssertTrue(script.severalFaces)
        XCTAssertEqual(script.step, .faceIn)
    }

    func testFaceMustBeCenteredToStart() {
        XCTAssertTrue(HeadPose.isFramed(FaceSample(faceCount: 1, turnDegrees: 3)))
        XCTAssertFalse(HeadPose.isFramed(FaceSample(faceCount: 1, centerX: 0.8, turnDegrees: 3)))
        XCTAssertFalse(HeadPose.isFramed(FaceSample(faceCount: 1, width: 0.1, turnDegrees: 3)))
        XCTAssertFalse(HeadPose.isFramed(FaceSample(faceCount: 2, turnDegrees: 3)))
    }
}
