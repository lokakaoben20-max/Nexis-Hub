import XCTest
@testable import NexisHub

/// Droits affichés par rôle : le serveur reste seul juge, l'app ne fait
/// que cacher ce qui est interdit.
final class OrgRightsTests: XCTestCase {
    func testOnlyTheRepresentativeTouchesMoneyAndTeam() {
        for right in [OrgRight.manageMembers, .manageNumbers, .withdraw] {
            XCTAssertTrue(OrgRole.representative.can(right))
            for role in [OrgRole.manager, .accountant, .worker] {
                XCTAssertFalse(role.can(right), "\(role) ne doit pas avoir \(right)")
            }
        }
    }

    func testOnlyTheFieldWorkerCannotSeeTheBalance() {
        for role in OrgRole.allCases {
            XCTAssertTrue(role.can(.seeMissions))
            XCTAssertEqual(role.can(.seeBalance), role != .worker)
        }
    }

    func testInvitableRolesNeverIncludeTheRepresentative() {
        XCTAssertEqual(OrgRole.invitable, [.manager, .accountant, .worker])
    }

    func testShortNameDropsTheLegalForm() {
        XCTAssertEqual(Organization.shortName(of: "Kasa Services SARLU"), "Kasa Services")
        XCTAssertEqual(Organization.shortName(of: "Kasa SA"), "Kasa")
        XCTAssertEqual(Organization.shortName(of: "SARL"), "SARL")
    }

    func testNewNumberWaitsThenBecomesActive() {
        let now = Date()
        let waiting = WithdrawNumber(id: 1, mobileOperator: .orange, number: "897654321",
                                     usableAt: now.addingTimeInterval(71 * 3600 - 600))
        XCTAssertEqual(waiting.hoursLeft(now: now), 71)
        XCTAssertFalse(waiting.isActive(now: now))
        let ready = WithdrawNumber(id: 2, mobileOperator: .airtel, number: "991234567",
                                   usableAt: now.addingTimeInterval(-60))
        XCTAssertTrue(ready.isActive(now: now))
    }

    func testDraftNeedsEveryFieldAndAllThreeDocuments() {
        var draft = OrgDraft()
        XCTAssertFalse(draft.step1Ready)
        draft = OrgDemo.draft(documents: false)
        XCTAssertTrue(draft.step1Ready)
        XCTAssertFalse(draft.step3Ready)
        draft.documents = [.rccm, .idnat]
        XCTAssertFalse(draft.step3Ready)
        draft.documents.insert(.nif)
        XCTAssertTrue(draft.step3Ready)
        draft.nif = " "
        XCTAssertFalse(draft.step1Ready)
    }

    func testRepresentativeStepNeedsIdentityOnlyWhenNotAlreadyVerified() {
        var draft = OrgDemo.draft(documents: true)
        XCTAssertTrue(draft.step2Ready(identityVerified: true, identityTaken: false))
        XCTAssertFalse(draft.step2Ready(identityVerified: false, identityTaken: false))
        XCTAssertTrue(draft.step2Ready(identityVerified: false, identityTaken: true))
        draft.representativeIsMe = false
        XCTAssertFalse(draft.step2Ready(identityVerified: true, identityTaken: true))
        draft.representativePhone = "81 234 5678"
        XCTAssertTrue(draft.step2Ready(identityVerified: false, identityTaken: false))
    }
}

@MainActor
final class OrgRepositoryTests: XCTestCase {
    private func refusal(_ block: () async throws -> Void) async -> String? {
        do { try await block(); return nil } catch let refusal as NexisRefusal { return refusal.code } catch { return "\(error)" }
    }

    /// Un compte tout juste créé : client jamais vérifié.
    private func newClient() -> DemoRepository {
        let repo = DemoRepository()
        XCTAssertTrue(repo.registerClient(phone: "+243810000010", firstName: "Ana", lastName: "Kasa",
                                          commune: "Gombe", acceptedTermsVersion: repo.signupTermsVersion))
        return repo
    }

    private let capture = IdentityCapture(document: .passport, recto: Data([1]), verso: nil, video: Data([3]),
                                          videoSeconds: 7, headTurns: [.left, .right])

    func testVerifiedPersonOpensAnOrganizationWithoutNewIdentity() async throws {
        let repo = DemoRepository()
        let profile = try await repo.profile()
        XCTAssertTrue(profile.isIdentityVerified)
        let org = try await repo.createOrganization(OrgDemo.draft(documents: true),
                                                    acceptedTermsVersion: repo.orgTermsVersion, identity: nil)
        XCTAssertEqual(org.status, .reviewing)
        XCTAssertEqual(org.myRole, .representative)
        XCTAssertEqual(org.name, "Kasa Services SARLU")
        XCTAssertEqual(org.members.first?.status, .verified)
        let listed = try await repo.organizations()
        XCTAssertEqual(listed.map(\.id), [org.id])
    }

    func testNeverVerifiedPersonNeedsPieceAndVideoOnce() async throws {
        let repo = newClient()
        let draft = OrgDemo.draft(documents: true)
        let missing = await refusal {
            _ = try await repo.createOrganization(draft, acceptedTermsVersion: repo.orgTermsVersion, identity: nil)
        }
        XCTAssertEqual(missing, "identity_required")
        let org = try await repo.createOrganization(draft, acceptedTermsVersion: repo.orgTermsVersion,
                                                    identity: capture)
        // Envoyée, pas vérifiée : la personne ne travaille pas avant la décision de l'équipe.
        XCTAssertEqual(org.members.first?.status, .toVerify)
        // Une seconde entreprise ne redemande rien : la vérification est déjà partie.
        let second = try await repo.createOrganization(draft, acceptedTermsVersion: repo.orgTermsVersion, identity: nil)
        XCTAssertEqual(second.status, .reviewing)
    }

    func testCreationNeedsCurrentTermsAndAllDocuments() async throws {
        let repo = DemoRepository()
        let noTerms = await refusal {
            _ = try await repo.createOrganization(OrgDemo.draft(documents: true), acceptedTermsVersion: nil, identity: nil)
        }
        XCTAssertEqual(noTerms, "organization_invalid")
        let noDocuments = await refusal {
            _ = try await repo.createOrganization(OrgDemo.draft(documents: false),
                                                  acceptedTermsVersion: repo.orgTermsVersion, identity: nil)
        }
        XCTAssertEqual(noDocuments, "organization_invalid")
        let orgs = try await repo.organizations()
        XCTAssertTrue(orgs.isEmpty)
    }

    func testOnlyTheRepresentativeInvites() async throws {
        let accountant = DemoRepository()
        accountant.demoPreset("org-accountant")
        let refused = await refusal {
            try await accountant.inviteMember(orgId: 1, phone: "82 000 1122", role: .worker)
        }
        XCTAssertEqual(refused, "invitation_refused")

        let representative = DemoRepository()
        representative.demoPreset("org-team")
        let badPhone = await refusal {
            try await representative.inviteMember(orgId: 1, phone: "11 000", role: .worker)
        }
        XCTAssertEqual(badPhone, "invitation_refused")
        let badRole = await refusal {
            try await representative.inviteMember(orgId: 1, phone: "82 000 1122", role: .representative)
        }
        XCTAssertEqual(badRole, "invitation_refused")
        try await representative.inviteMember(orgId: 1, phone: "82 000 1122", role: .worker)
        let org = try await representative.organization(id: 1)
        XCTAssertEqual(org.members.last?.status, .invited)
        XCTAssertEqual(org.members.last?.role, .worker)
    }

    func testNewNumberWaits72HoursAndFourIsTheLimit() async throws {
        let repo = DemoRepository()
        repo.demoPreset("org-numbers")
        try await repo.addWithdrawNumber(orgId: 1, mobileOperator: .mpesa, number: "81 234 5678")
        var org = try await repo.organization(id: 1)
        let added = try XCTUnwrap(org.numbers.last)
        XCTAssertFalse(added.isActive())
        XCTAssertEqual(added.hoursLeft(), 72)
        let duplicate = await refusal {
            try await repo.addWithdrawNumber(orgId: 1, mobileOperator: .mpesa, number: "81 234 5678")
        }
        XCTAssertEqual(duplicate, "number_refused")
        try await repo.addWithdrawNumber(orgId: 1, mobileOperator: .orange, number: "84 000 1111")
        org = try await repo.organization(id: 1)
        XCTAssertEqual(org.numbers.count, 4)
        let fifth = await refusal {
            try await repo.addWithdrawNumber(orgId: 1, mobileOperator: .airtel, number: "99 888 7777")
        }
        XCTAssertEqual(fifth, "number_refused")
    }

    func testOnlyTheRepresentativeManagesNumbers() async {
        let repo = DemoRepository()
        repo.demoPreset("org-accountant")
        let refused = await refusal {
            try await repo.addWithdrawNumber(orgId: 1, mobileOperator: .mpesa, number: "81 234 5678")
        }
        XCTAssertEqual(refused, "number_refused")
    }

    func testWithdrawalGoesOnlyToAnActiveNumberAndWithinTheBalance() async throws {
        let repo = DemoRepository()
        repo.demoPreset("org-withdraw")
        let before = try await repo.organization(id: 1)
        let waiting = try XCTUnwrap(before.numbers.first { !$0.isActive() })
        let active = try XCTUnwrap(before.numbers.first { $0.isActive() })
        let toWaiting = await refusal {
            try await repo.requestOrgWithdrawal(orgId: 1, amount: Money(1_000, .cdf), numberId: waiting.id)
        }
        XCTAssertEqual(toWaiting, "withdrawal_refused")
        let tooMuch = await refusal {
            try await repo.requestOrgWithdrawal(orgId: 1, amount: Money(9_000_000, .cdf), numberId: active.id)
        }
        XCTAssertEqual(tooMuch, "withdrawal_refused")
        let unknown = await refusal {
            try await repo.requestOrgWithdrawal(orgId: 1, amount: Money(1_000, .cdf), numberId: 999)
        }
        XCTAssertEqual(unknown, "withdrawal_refused")
        let zero = await refusal {
            try await repo.requestOrgWithdrawal(orgId: 1, amount: Money(0, .cdf), numberId: active.id)
        }
        XCTAssertEqual(zero, "withdrawal_refused")
        let unchanged = try await repo.organization(id: 1)
        XCTAssertEqual(unchanged.wallet, before.wallet)

        try await repo.requestOrgWithdrawal(orgId: 1, amount: Money(500_000, .cdf), numberId: active.id)
        let after = try await repo.organization(id: 1)
        XCTAssertEqual(after.wallet.available[.cdf], Money(740_000, .cdf))
        let movements = try await repo.orgMovements(orgId: 1)
        XCTAssertEqual(movements.first?.kind, .withdrawal)
        XCTAssertEqual(movements.first?.amount, Money(-500_000, .cdf))
    }

    func testAccountantCannotWithdrawAndWorkerSeesNoMoney() async throws {
        let accountant = DemoRepository()
        accountant.demoPreset("org-accountant")
        let org = try await accountant.organization(id: 1)
        XCTAssertFalse(org.wallet.available.isEmpty)
        let number = try XCTUnwrap(org.numbers.first { $0.isActive() })
        let refused = await refusal {
            try await accountant.requestOrgWithdrawal(orgId: 1, amount: Money(1_000, .cdf), numberId: number.id)
        }
        XCTAssertEqual(refused, "withdrawal_refused")

        let worker = DemoRepository()
        worker.demoPreset("org-worker")
        let workerOrg = try await worker.organization(id: 1)
        XCTAssertEqual(workerOrg.wallet, .empty)
        let movements = try await worker.orgMovements(orgId: 1)
        XCTAssertTrue(movements.isEmpty)
    }

    func testVerifiedInvitedPersonJoinsWithoutNewVerification() async throws {
        let repo = DemoRepository()
        repo.demoPreset("org-invited-verified")
        let invitations = try await repo.invitations()
        XCTAssertEqual(invitations.count, 1)
        try await repo.answerInvitation(id: 1, accept: true)
        let after = try await repo.invitations()
        XCTAssertTrue(after.isEmpty)
        let joined = try await repo.organizations()
        let org = try XCTUnwrap(joined.first)
        XCTAssertEqual(org.myRole, .worker)
        XCTAssertEqual(org.members.first?.status, .verified)
        let notNeeded = await refusal { try await repo.submitIdentity(capture) }
        XCTAssertEqual(notNeeded, "identity_not_needed")
    }

    func testUnverifiedInvitedPersonVerifiesOnce() async throws {
        let repo = DemoRepository()
        repo.demoPreset("org-invited-unverified")
        try await repo.answerInvitation(id: 1, accept: true)
        let joined = try await repo.organizations()
        var org = try XCTUnwrap(joined.first)
        XCTAssertEqual(org.members.first?.status, .toVerify)
        try await repo.submitIdentity(capture)
        org = try await repo.organization(id: org.id)
        // Envoyée : l'équipe décide ; la personne ne prend pas de mission avant.
        XCTAssertEqual(org.members.first?.status, .toVerify)
    }

    func testRefusedInvitationJoinsNothing() async throws {
        let repo = DemoRepository()
        repo.demoPreset("org-invited-verified")
        try await repo.answerInvitation(id: 1, accept: false)
        let orgs = try await repo.organizations()
        XCTAssertTrue(orgs.isEmpty)
        let again = await refusal { try await repo.answerInvitation(id: 1, accept: true) }
        XCTAssertEqual(again, "invitation_not_found")
    }

    func testReplacingTheRefusedDocumentReopensTheReview() async throws {
        let repo = DemoRepository()
        repo.demoPreset("org-correction")
        let wrong = await refusal { try await repo.replaceDocument(orgId: 1, kind: .idnat) }
        XCTAssertEqual(wrong, "document_not_requested")
        try await repo.replaceDocument(orgId: 1, kind: .nif)
        let org = try await repo.organization(id: 1)
        XCTAssertEqual(org.status, .reviewing)
        XCTAssertNil(org.correctionNote)
        XCTAssertTrue(org.documents.allSatisfy { $0.state == .received })
    }
}
