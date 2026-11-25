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
