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
        let photo = Data([1, 2, 3])
        let noTerms = await refusal {
            try await repo.applyAsProvider(services: ["nettoyage"], communes: ["Limete"], idDocument: photo,
                                           selfie: photo, acceptedTermsVersion: nil)
        }
        XCTAssertEqual(noTerms, "provider_application_invalid")
        let noPhoto = await refusal {
            try await repo.applyAsProvider(services: ["nettoyage"], communes: ["Limete"], idDocument: Data(),
                                           selfie: photo, acceptedTermsVersion: repo.providerTermsVersion)
        }
        XCTAssertEqual(noPhoto, "provider_application_invalid")
        try await repo.applyAsProvider(services: ["nettoyage"], communes: ["Limete"], idDocument: photo,
                                       selfie: photo, acceptedTermsVersion: repo.providerTermsVersion)
        let profile = try await repo.profile()
        XCTAssertEqual(profile.providerStatus, .pending)
        XCTAssertFalse(profile.isProvider)
        let documents = try await repo.legalDocuments()
        XCTAssertEqual(documents.map(\.key), [.cgu, .providerTerms])
    }
}

final class CodeRulesTests: XCTestCase {
    func testWeakCodesAreRefused() {
        for code in ["000000", "111111", "121212", "123456", "654321", "123123", "12345", "12a456", "1234567"] {
            XCTAssertTrue(CodeRules.isWeak(code), code)
        }
        for code in ["482916", "190573", "112233", "250489"] {
            XCTAssertFalse(CodeRules.isWeak(code), code)
        }
    }

    func testLocksAfterOneMinuteAway() {
        let left = Date(timeIntervalSince1970: 1_000)
        XCTAssertFalse(CodeRules.shouldLock(leftAt: nil, now: left))
        XCTAssertFalse(CodeRules.shouldLock(leftAt: left, now: left.addingTimeInterval(59)))
        XCTAssertTrue(CodeRules.shouldLock(leftAt: left, now: left.addingTimeInterval(60)))
    }

    func testDigestDependsOnSalt() {
        let a = CodeRules.digest("482916", salt: Data(repeating: 1, count: 16))
        let b = CodeRules.digest("482916", salt: Data(repeating: 2, count: 16))
        XCTAssertNotEqual(a, b)
        XCTAssertTrue(CodeRules.same(a, CodeRules.digest("482916", salt: Data(repeating: 1, count: 16))))
    }
}

@MainActor
final class AppSecurityTests: XCTestCase {
    func testCodeIsStoredOnlyAsSaltedDigest() throws {
        let vault = MemoryCodeVault()
        let security = AppSecurity(vault: vault)
        security.setCode("482916")
        let record = try XCTUnwrap(vault.load())
        XCTAssertEqual(record.salt.count, 16)
        XCTAssertFalse(String(decoding: try JSONEncoder().encode(record), as: UTF8.self).contains("482916"))
        XCTAssertEqual(security.check("482916"), .ok)
    }

    func testFiveWrongCodesBlockEvenAfterRestart() {
        let vault = MemoryCodeVault()
        let security = AppSecurity(vault: vault)
        security.setCode("482916")
        XCTAssertEqual(security.check("111222"), .wrong(left: 4))
        XCTAssertEqual(security.check("482916"), .ok)
        for left in [4, 3, 2, 1] { XCTAssertEqual(security.check("111222"), .wrong(left: left)) }
        // Une nouvelle ouverture de l'app relit le compteur.
        let reopened = AppSecurity(vault: vault)
        XCTAssertEqual(reopened.check("111222"), .blocked)
        XCTAssertEqual(reopened.check("482916"), .blocked)
    }

    func testSignOutErasesCodeAndCancelsPendingPayment() async {
        let app = AppModel(repository: DemoRepository(), security: AppSecurity(vault: MemoryCodeVault()), language: "fr")
        app.signIn()
        XCTAssertTrue(app.needsProtection)
        app.security.setCode("482916")
        XCTAssertFalse(app.needsProtection)
        async let confirmed = app.confirmMoneyOut("Payer 25 000 FC à Prisca")
        for _ in 0..<50 where app.gate == nil { await Task.yield() }
        XCTAssertNotNil(app.gate)
        app.signOut()
        let result = await confirmed
        XCTAssertFalse(result)
        XCTAssertFalse(app.security.hasCode)
        XCTAssertNil(app.gate)
    }

    func testMoneyOutWaitsForConfirmation() async {
        let app = AppModel(repository: DemoRepository(), security: AppSecurity(vault: MemoryCodeVault()), language: "fr")
        app.signIn()
        app.security.setCode("482916")
        async let confirmed = app.confirmMoneyOut("Verser l'argent à Nadia")
        for _ in 0..<50 where app.gate == nil { await Task.yield() }
        app.finishGate(true)
        let result = await confirmed
        XCTAssertTrue(result)
    }

    func testLockOnlyAfterAMinuteInBackground() {
        let app = AppModel(repository: DemoRepository(), security: AppSecurity(vault: MemoryCodeVault()), language: "fr")
        app.signIn()
        app.security.setCode("482916")
        let start = Date(timeIntervalSince1970: 5_000)
        app.left(at: start)
        XCTAssertTrue(app.covered)
        app.came(back: start.addingTimeInterval(20))
        XCTAssertFalse(app.covered)
        XCTAssertFalse(app.locked)
        app.left(at: start)
        app.came(back: start.addingTimeInterval(90))
        XCTAssertTrue(app.locked)
    }

    func testNoMoneyOutWithoutCode() async {
        let app = AppModel(repository: DemoRepository(), security: AppSecurity(vault: MemoryCodeVault()), language: "fr")
        app.signIn()
        let result = await app.confirmMoneyOut("Payer")
        XCTAssertFalse(result)
    }
}
