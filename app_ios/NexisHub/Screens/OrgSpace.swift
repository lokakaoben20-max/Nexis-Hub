import SwiftUI

// L'espace entreprise ouvert : changer d'espace, accueil, missions,
// portefeuille, équipe, invitations, rôles, numéros de retrait et retrait.
// Chaque rôle ne voit que ce que le serveur lui permet : l'app cache ce qui
// est interdit, le serveur le refuse de toute façon.

// MARK: - Mots communs

extension AppModel {
    func rightText(_ right: OrgRight) -> String {
        switch right {
        case .seeMissions: return t("orgRightMissions")
        case .seeBalance: return t("orgRightBalance")
        case .seeTeam: return t("orgRightTeam")
        case .assignMissions: return t("orgRightAssign")
        case .manageMembers: return t("orgRightMembers")
        case .manageNumbers: return t("orgRightNumbers")
        case .withdraw: return t("orgRightWithdraw")
        }
    }

    /// Ce qu'un rôle peut faire, ligne par ligne. Un intervenant a ses trois
    /// phrases ; les autres rôles montrent le tableau des droits.
    func rightLines(_ role: OrgRole) -> [(text: String, allowed: Bool)] {
        if role == .worker {
            return [(t("orgRightDoMissions"), true), (t("orgRightOwnMissions"), true), (t("orgRightNoMoney"), false)]
        }
        return OrgRight.allCases.map { (rightText($0), role.can($0)) }
    }

    func roleShort(_ role: OrgRole) -> String {
        switch role {
        case .representative: return t("orgRoleRepShort")
        case .manager: return t("orgRoleMgrShort")
        case .accountant: return t("orgRoleAccShort")
        case .worker: return t("orgRoleWrkShort")
        }
    }

    /// « Jean Kalala » devient « Jean K. ».
    func shortPerson(_ name: String) -> String {
        let words = name.split(separator: " ")
        guard words.count > 1, let last = words.last?.first else { return name }
        return "\(words[0]) \(last)."
    }

    /// « 99 123 4567 ».
    func numberText(_ number: String) -> String { DrcPhone(digits: number).formatted }

    func memberSubtitle(_ member: OrgMember) -> String {
        if member.role == .worker, let service = member.service { return service.name(language) }
        return roleName(member.role)
    }

    func openClientSpace() {
        providerSpace = false
        orgSpaceId = nil
    }

    func openProviderSpace() {
        orgSpaceId = nil
        providerSpace = true
    }

    func openOrgSpace(_ id: Int) {
        providerSpace = false
        orgSpaceId = id
    }
}

/// Le monogramme d'une entreprise : ses initiales sur le bleu Nexis.
struct OrgMark: View {
    @Environment(AppModel.self) private var app
    let name: String
    var size: CGFloat = 44
    /// « org-<numéro> » : la photo de l'entreprise, quand elle en a une.
    var photoKey: String? = nil

    private var initials: String {
        let words = Organization.shortName(of: name).split(separator: " ")
        return words.prefix(2).map { String($0.prefix(1)) }.joined().uppercased()
    }

    var body: some View {
        if let image = app.photo(photoKey) {
            Image(uiImage: image)
                .resizable().scaledToFill()
                .frame(width: size, height: size)
                .clipShape(RoundedRectangle(cornerRadius: size * 0.3, style: .continuous))
                .accessibilityHidden(true)
        } else {
            Text(initials)
                .font(.title(size * 0.34, .semibold))
                .foregroundStyle(.white)
                .frame(width: size, height: size)
                .background(Nexis.brandGradient, in: RoundedRectangle(cornerRadius: size * 0.3, style: .continuous))
                .accessibilityHidden(true)
        }
    }
}

// MARK: - 12. Changer d'espace

struct SpacePickerSheet: View {
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    @State private var profile: Profile?
    @State private var orgs: [Organization] = []

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 10) {
                    ChoiceRow(title: app.t("orgSwitchPersonal"), subtitle: app.t("spaceClient"),
                              selected: app.orgSpaceId == nil && !app.providerSpace) {
                        InitialsAvatar(initials: profile?.initials ?? "", size: 40, photoKey: "me")
                    } action: {
                        app.openClientSpace()
                        dismiss()
                    }
                    if profile?.isProvider == true {
                        ChoiceRow(title: app.t("spaceProvider"), subtitle: app.t("orgSwitchPersonal"),
                                  selected: app.orgSpaceId == nil && app.providerSpace) {
                            Image(systemName: "briefcase.fill")
                                .font(.system(size: 18, weight: .semibold)).foregroundStyle(Nexis.softInk)
                                .frame(width: 40, height: 40).background(Nexis.soft, in: Circle())
                        } action: {
                            app.openProviderSpace()
                            dismiss()
                        }
                    }
                    ForEach(orgs.filter(\.isOpen)) { org in
                        ChoiceRow(title: org.name, subtitle: app.roleName(org.myRole),
                                  selected: app.orgSpaceId == org.id) {
                            OrgMark(name: org.name, size: 40)
                        } action: {
                            app.openOrgSpace(org.id)
                            dismiss()
                        }
                    }
                }
                .padding(18)
            }
            .background(Nexis.bg)
            .navigationTitle(app.t("orgSwitchTitle"))
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) { Button(app.t("close")) { dismiss() } }
            }
            .task {
                profile = try? await app.repository.profile()
                orgs = (try? await app.repository.organizations()) ?? []
            }
        }
        .presentationDetents([.medium, .large])
    }
}

// MARK: - 13. Accueil de l'espace

struct OrgHomeView: View {
    @Environment(AppModel.self) private var app
    let orgId: Int
    let onTab: (AppTab) -> Void
    @State private var flow = MissionFlow()
    @State private var org: Organization?
    @State private var missions: [Mission] = []
    @State private var switching = false

    var body: some View {
        NavigationStack(path: $flow.path) {
            Group {
                if let org { content(org) } else { FlowLoading(label: app.t("orgTitle")) }
            }
            .background(Nexis.bg)
            .greetingHeader(org?.shortName ?? "NexisHub") {
                Button { switching = true } label: {
                    Label(app.t("orgChange"), systemImage: "arrow.left.arrow.right")
                        .font(.body(14, .semibold, relativeTo: .subheadline))
                        .foregroundStyle(Nexis.softInk)
                        .padding(.horizontal, 12).padding(.vertical, 8)
                        .background(Nexis.soft, in: Capsule())
                }
                .buttonStyle(.plain)
            }
            .missionDestinations()
        }
        .missionFlow(flow, tab: .home)
        .sheet(isPresented: $switching) { SpacePickerSheet() }
        .task(id: app.revision) {
            org = try? await app.repository.organization(id: orgId)
            missions = (try? await app.repository.orgMissions(orgId: orgId)) ?? []
        }
        .onAppear {
            if let capture = app.capture, OrgDemo.spaceCaptures.contains(capture), flow.path.isEmpty,
               let routes = MissionRoute.forCapture(capture) {
                flow.path = routes
            }
        }
    }

    private struct QuickItem: Identifiable {
        let id: String
        let symbol: String
        let label: String
        let run: () -> Void
    }

    private func items(_ org: Organization) -> [QuickItem] {
        var list: [QuickItem] = []
        list.append(QuickItem(id: "services", symbol: "square.grid.2x2.fill", label: app.t("actionServices")) {
            flow.comingSoon = SheetTitle(app.t("actionServices"))
        })
        if org.myRole.can(.withdraw) {
            list.append(QuickItem(id: "withdraw", symbol: "arrow.up.to.line", label: app.t("actionWithdraw")) {
                flow.push(.orgWithdraw(org.id))
            })
        }
        if org.can(.seeBalance) {
            list.append(QuickItem(id: "history", symbol: "clock.arrow.circlepath", label: app.t("actionHistory")) {
                onTab(.wallet)
            })
        }
        if org.can(.seeTeam) {
            list.append(QuickItem(id: "team", symbol: "person.2.fill", label: app.t("orgQuickTeam")) {
                flow.push(.orgTeam(org.id))
            })
        }
        list.append(QuickItem(id: "more", symbol: "ellipsis", label: app.t("actionMore")) {
            flow.comingSoon = SheetTitle(app.t("actionMore"))
        })
        return list
    }

    private func content(_ org: Organization) -> some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 22) {
                if org.can(.seeBalance) {
                    WalletCard(wallet: org.wallet, title: app.t("orgAvailableCaption"), org: true)
                    HStack(alignment: .top, spacing: 0) {
                        ForEach(items(org)) { item in
                            QuickAction(symbol: item.symbol, label: item.label, action: item.run)
                        }
                    }
                } else {
                    InfoNote(text: app.t("orgWorkerPays"), systemImage: "info.circle.fill")
                }
                ongoing(org)
            }
            .padding(.horizontal, 18)
            .padding(.bottom, 24)
        }
    }

    private func ongoing(_ org: Organization) -> some View {
        let list = org.visible(missions).filter(\.isActive)
        return VStack(alignment: .leading, spacing: 12) {
            Text(app.t("orgOngoing")).font(.title(18)).foregroundStyle(Nexis.ink)
            if list.isEmpty {
                Text(app.t("noMissions")).font(.body(15)).foregroundStyle(Nexis.muted).padding(.vertical, 12)
            } else {
                VStack(spacing: 0) {
                    ForEach(list) { mission in
                        MissionRow(mission: mission)
                            .padding(.horizontal, 16)
                            .padding(.vertical, 10)
                        if mission.id != list.last?.id { Divider().padding(.leading, 74) }
                    }
                }
                .background(Nexis.surface, in: RoundedRectangle(cornerRadius: 22, style: .continuous))
            }
        }
    }
}

// MARK: - Missions de l'espace (19)

struct OrgMissionsView: View {
    @Environment(AppModel.self) private var app
    let orgId: Int
    @State private var org: Organization?
    @State private var missions: [Mission] = []
    @State private var showDone = false
    @State private var assigning: Mission?

    var body: some View {
        let seen = org?.visible(missions) ?? missions
        let list = showDone ? seen.filter { $0.status == .completed } : seen.filter(\.isActive)
        let all = org?.can(.seeMissions) ?? true
        NavigationStack {
            List {
                Section {
                    Picker(app.t("myMissions"), selection: $showDone) {
                        Text(app.t("tabOngoing")).tag(false)
                        Text(app.t("tabDone")).tag(true)
                    }
                    .pickerStyle(.segmented)
                    .listRowBackground(Color.clear)
                    .listRowInsets(EdgeInsets())
                }
                Section {
                    if list.isEmpty {
                        Text(app.t("noMissions")).font(.body(15)).foregroundStyle(Nexis.muted)
                    }
                    ForEach(list) { mission in
                        if !all {
                            WorkerMissionRow(mission: mission, orgName: org?.shortName ?? "")
                        } else if let org, org.can(.assignMissions), mission.isActive {
                            VStack(alignment: .leading, spacing: 10) {
                                MissionRow(mission: mission)
                                assignLine(mission, org)
                            }
                        } else {
                            MissionRow(mission: mission)
                        }
                    }
                }
                if !all {
                    Section {
                        InfoNote(text: app.t("orgMineOnly"), systemImage: "person.fill")
                            .listRowBackground(Color.clear)
                            .listRowInsets(EdgeInsets())
                    }
                }
                if !(org?.can(.seeBalance) ?? true) {
                    Section {
                        InfoNote(text: app.t("orgWorkerPays"), systemImage: "info.circle.fill")
                            .listRowBackground(Color.clear)
                            .listRowInsets(EdgeInsets())
                    }
                }
            }
            .scrollContentBackground(.hidden)
            .background(Nexis.bg)
            .navigationTitle(app.t(all ? "orgMissionsTitle" : "myMissions"))
            .sheet(item: $assigning) { mission in
                if let org { OrgAssignSheet(org: org, mission: mission) }
            }
            .task(id: app.revision) {
                org = try? await app.repository.organization(id: orgId)
                missions = (try? await app.repository.orgMissions(orgId: orgId)) ?? []
                if app.capture == "org-assign", assigning == nil {
                    assigning = missions.first(where: \.isActive)
                }
            }
        }
    }

    /// « Intervenants : Jean K., Paul I. » ; un toucher ouvre le choix.
    private func assignLine(_ mission: Mission, _ org: Organization) -> some View {
        let names = (org.assignments[mission.id] ?? [])
            .compactMap { id in org.members.first(where: { $0.id == id })?.name }
            .map(app.shortPerson)
        return Button { assigning = mission } label: {
            HStack(spacing: 8) {
                Image(systemName: "person.2.fill").font(.system(size: 13, weight: .semibold))
                Text(names.isEmpty ? app.t("orgAssignNone")
                                   : app.t("orgAssignedLine", ["names": names.joined(separator: ", ")]))
                    .lineLimit(2)
                    .multilineTextAlignment(.leading)
                Spacer(minLength: 4)
                Text(app.t("orgAssignAction")).font(.body(13, .bold))
            }
            .font(.body(13, .medium, relativeTo: .footnote))
            .foregroundStyle(Nexis.softInk)
            .padding(.horizontal, 12).padding(.vertical, 9)
            .background(Nexis.soft, in: RoundedRectangle(cornerRadius: 12, style: .continuous))
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
    }
}

/// Choisit qui va sur une mission. Plusieurs personnes possibles, toutes
/// vérifiées ; le client voit le nom de chacune.
private struct OrgAssignSheet: View {
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    let org: Organization
    let mission: Mission
    @State private var picked: Set<Int> = []
    @State private var busy = false
    @State private var failed = false

    private var candidates: [OrgMember] {
        org.members.filter { $0.role == .worker || $0.service != nil }
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 14) {
                    VStack(alignment: .leading, spacing: 3) {
                        Text(app.place(mission)).font(.body(16, .bold)).foregroundStyle(Nexis.ink)
                        Text(app.t("orgAssignWho")).font(.body(13.5)).foregroundStyle(Nexis.muted)
                    }
                    VStack(spacing: 0) {
                        ForEach(candidates) { member in
                            row(member)
                            if member.id != candidates.last?.id { Divider().padding(.leading, 70) }
                        }
                    }
                    .background(Nexis.surface, in: RoundedRectangle(cornerRadius: 20, style: .continuous))
                    InfoNote(text: app.t("orgAssignHint"), systemImage: "person.2.fill")
                    InfoNote(text: app.t("orgAssignOnlyVerified"), systemImage: "checkmark.seal.fill")
                    if failed {
                        Text(app.t("orgFailed")).font(.body(14)).foregroundStyle(Nexis.danger)
                    }
                }
                .padding(18)
            }
            .background(Nexis.bg)
            .navigationTitle(app.t("orgAssignTitle"))
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button(app.t("cancel")) { dismiss() } }
                ToolbarItem(placement: .confirmationAction) {
                    Button(app.t("orgAssignSave")) { Task { await save() } }
                        .disabled(picked.isEmpty || busy)
                }
            }
            .onAppear { picked = Set(org.assignments[mission.id] ?? []) }
        }
        .presentationDetents([.large])
    }

    private func row(_ member: OrgMember) -> some View {
        let ready = member.status == .verified
        return Button {
            guard ready else { return }
            if picked.contains(member.id) { picked.remove(member.id) } else { picked.insert(member.id) }
        } label: {
            HStack(spacing: 12) {
                PersonAvatar(initials: member.initials, color: member.color, size: 44)
                VStack(alignment: .leading, spacing: 3) {
                    Text(member.name).font(.body(15.5, .bold)).foregroundStyle(Nexis.ink).lineLimit(1)
                    Text(app.memberSubtitle(member)).font(.body(13, relativeTo: .footnote))
                        .foregroundStyle(Nexis.muted).lineLimit(1)
                }
                Spacer(minLength: 8)
                if ready {
                    Image(systemName: picked.contains(member.id) ? "checkmark.circle.fill" : "circle")
                        .font(.system(size: 22))
                        .foregroundStyle(picked.contains(member.id) ? Nexis.accent : Color(light: 0xC9D0DB, dark: 0x3A4A66))
                } else {
                    Pill(tone: .warn, systemImage: "exclamationmark", text: app.t("orgMemberToVerify"))
                }
            }
            .padding(.horizontal, 14).padding(.vertical, 12)
            .contentShape(Rectangle())
            .opacity(ready ? 1 : 0.65)
        }
        .buttonStyle(.plain)
        .accessibilityAddTraits(picked.contains(member.id) ? .isSelected : [])
    }

    private func save() async {
        busy = true
        failed = false
        do {
            try await app.repository.assignMembers(orgId: org.id, missionId: mission.id,
                                                   memberIds: org.members.map(\.id).filter { picked.contains($0) })
            app.dataChanged()
            dismiss()
        } catch {
            failed = true
        }
        busy = false
    }
}

/// La mission d'un intervenant : le service, l'état et le créneau.
private struct WorkerMissionRow: View {
    @Environment(AppModel.self) private var app
    let mission: Mission
    let orgName: String

    private var when: String {
        guard let date = mission.when else { return orgName }
        let day = Calendar.current.isDateInToday(date) ? "\(app.t("today")) \(app.clock(date))" : app.slot(date, capital: true)
        return "\(day) · \(orgName)"
    }

    var body: some View {
        HStack(alignment: .top, spacing: 14) {
            ServiceTile(mission, size: 44)
            VStack(alignment: .leading, spacing: 4) {
                Text(app.place(mission)).font(.body(16, .semibold, relativeTo: .headline)).foregroundStyle(Nexis.ink)
                HStack(spacing: 6) {
                    Circle().fill(mission.status.tint).frame(width: 7, height: 7)
                    Text(app.t(mission.status == .inProgress ? "tabOngoing" : mission.status == .completed ? "tabDone" : "orgUpcoming"))
                        .font(.body(13, .medium, relativeTo: .footnote)).foregroundStyle(mission.status.tint)
                }
                Text(when).font(.body(13, relativeTo: .footnote)).foregroundStyle(Nexis.muted)
            }
        }
        .padding(.vertical, 4)
        .accessibilityElement(children: .combine)
    }
}

// MARK: - Portefeuille de l'espace (18)

struct OrgWalletView: View {
    @Environment(AppModel.self) private var app
    let orgId: Int
    @State private var flow = MissionFlow()
    @State private var org: Organization?
    @State private var movements: [Movement] = []

    var body: some View {
        NavigationStack(path: $flow.path) {
            List {
                if let org {
                    if org.can(.seeBalance) {
                        Section {
                            WalletCard(wallet: org.wallet, title: app.t("orgAvailableCaption"), org: true)
                                .listRowBackground(Color.clear)
                                .listRowInsets(EdgeInsets())
                        }
                        Section {
                            if org.myRole.can(.withdraw) {
                                VStack(spacing: 10) {
                                    Button { flow.push(.orgWithdraw(org.id)) } label: {
                                        WideLabel(text: app.t("orgWithdrawCta"), systemImage: "arrow.up.to.line")
                                    }
                                    .nxProminentButton()
                                    Button { flow.push(.orgNumbers(org.id)) } label: {
                                        WideLabel(text: app.t("orgNumbersTitle"))
                                    }
                                    .nxSecondaryButton()
                                }
                                .listRowBackground(Color.clear)
                                .listRowInsets(EdgeInsets())
                            } else {
                                InfoNote(text: app.t("orgWalletRepOnly"), systemImage: "lock.fill")
                                    .listRowBackground(Color.clear)
                                    .listRowInsets(EdgeInsets())
                            }
                        }
                        Section {
                            if movements.isEmpty {
                                Text(app.t("noMissions")).font(.body(15)).foregroundStyle(Nexis.muted)
                            }
                            ForEach(movements) { movement in MovementRow(movement: movement) }
                        } header: {
                            Text(app.t("recentMovements")).font(.body(13, .semibold))
                        }
                    } else {
                        Section {
                            InfoNote(text: app.t("orgWalletLocked"), systemImage: "lock.fill")
                                .listRowBackground(Color.clear)
                                .listRowInsets(EdgeInsets())
                        }
                    }
                }
            }
            .scrollContentBackground(.hidden)
            .background(Nexis.bg)
            .navigationTitle(app.t("navWallet"))
            .missionDestinations()
        }
        .missionFlow(flow, tab: .wallet)
        .task(id: app.revision) {
            org = try? await app.repository.organization(id: orgId)
            movements = (try? await app.repository.orgMovements(orgId: orgId)) ?? []
        }
    }
}

// MARK: - 14. L'équipe

struct OrgTeamView: View {
    @Environment(AppModel.self) private var app
    @Environment(MissionFlow.self) private var flow
    let orgId: Int

    var body: some View {
        OrgLoader(orgId: orgId) { org in
            ScrollView {
                VStack(alignment: .leading, spacing: 14) {
                    if org.can(.seeTeam) {
                        VStack(spacing: 0) {
                            ForEach(org.members) { member in
                                if org.myRole.can(.manageMembers), member.role != .representative {
                                    Button { flow.push(.orgMember(org: org.id, member: member.id)) } label: {
                                        memberRow(member, editable: true)
                                    }
                                    .buttonStyle(.plain)
                                } else {
                                    memberRow(member, editable: false)
                                }
                                if member.id != org.members.last?.id { Divider().padding(.leading, 70) }
                            }
                        }
                        .background(Nexis.surface, in: RoundedRectangle(cornerRadius: 20, style: .continuous))
                        InfoNote(text: app.t("orgTeamHint"), systemImage: "person.badge.shield.checkmark.fill")
                    } else {
                        InfoNote(text: app.t("orgTeamHidden"), systemImage: "lock.fill")
                    }
                }
                .flowScreen()
            }
            .bottomActions {
                if org.myRole.can(.manageMembers) {
                    Button { flow.push(.orgInvite(org.id)) } label: {
                        WideLabel(text: app.t("orgInviteAction"), systemImage: "person.badge.plus")
                    }
                    .nxProminentButton()
                }
                Button { flow.push(.orgRoles) } label: { WideLabel(text: app.t("orgRolesLink")) }
                    .nxSecondaryButton()
            }
        }
        .flowTitle(app.t("orgQuickTeam"))
    }

    private func memberRow(_ member: OrgMember, editable: Bool) -> some View {
        HStack(spacing: 12) {
            PersonAvatar(initials: member.initials, color: member.color, size: 44)
            VStack(alignment: .leading, spacing: 3) {
                Text(member.name).font(.body(15.5, .bold)).foregroundStyle(Nexis.ink).lineLimit(1)
                Text(app.memberSubtitle(member)).font(.body(13, relativeTo: .footnote))
                    .foregroundStyle(Nexis.muted).lineLimit(1)
            }
            Spacer(minLength: 8)
            VStack(alignment: .trailing, spacing: 5) {
                if member.role == .representative {
                    Pill(tone: .info, text: app.t("orgRoleRepresentative"))
                }
                if member.role != .representative || member.status != .verified {
                    statusPill(member.status)
                }
            }
            if editable {
                Image(systemName: "chevron.right")
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundStyle(Color(light: 0xC4CAD4, dark: 0x4A5A75))
            }
        }
        .padding(.horizontal, 14).padding(.vertical, 12)
        .accessibilityElement(children: .combine)
    }

    @ViewBuilder
    private func statusPill(_ status: OrgMemberStatus) -> some View {
        switch status {
        case .verified: Pill(tone: .ok, systemImage: "checkmark.seal.fill", text: app.t("orgMemberVerified"))
        case .toVerify: Pill(tone: .warn, systemImage: "exclamationmark", text: app.t("orgMemberToVerify"))
        case .invited: Pill(tone: .wait, systemImage: "envelope", text: app.t("orgMemberInvited"))
        }
    }
}

// MARK: - 15. Inviter quelqu'un

struct OrgInviteView: View {
    @Environment(AppModel.self) private var app
    @Environment(MissionFlow.self) private var flow
    let orgId: Int
    @State private var phone = ""
    @State private var role: OrgRole = .worker
    @State private var busy = false
    @State private var failed = false

    private var ready: Bool { DrcPhone.parse(phone).isValid }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                OrgFieldCard {
                    OrgFieldRow(label: app.t("phone")) {
                        Text("+243").foregroundStyle(Nexis.muted)
                        TextField("82 000 1122", text: $phone).keyboardType(.numberPad)
                    }
                }
                OrgGroupLabel(text: app.t("orgInviteRole"))
                WrapLayout {
                    ForEach(OrgRole.invitable, id: \.self) { item in
                        ToggleChip(label: app.roleName(item), selected: role == item) { role = item }
                    }
                }
                VStack(alignment: .leading, spacing: 12) {
                    Text(app.t("orgCanTitle")).font(.body(15.5, .bold)).foregroundStyle(Nexis.ink)
                    ForEach(Array(app.rightLines(role).enumerated()), id: \.offset) { _, line in
                        HStack(alignment: .top, spacing: 10) {
                            Image(systemName: line.allowed ? "checkmark.circle.fill" : "lock.fill")
                                .font(.system(size: 16, weight: .semibold))
                                .foregroundStyle(line.allowed ? Nexis.ok : Nexis.muted)
                                .frame(width: 20)
                            Text(line.text).font(.body(14.5)).foregroundStyle(line.allowed ? Nexis.ink : Nexis.muted)
                        }
                        .accessibilityElement(children: .combine)
                    }
                }
                .nxCard(padding: 16)
                if role == .manager {
                    InfoNote(text: app.t("orgRolesManagerNote"), systemImage: "info.circle.fill")
                }
                if failed {
                    Text(app.t("orgFailed")).font(.body(14)).foregroundStyle(Nexis.danger)
                }
            }
            .flowScreen()
        }
        .flowTitle(app.t("orgInviteAction"))
        .bottomActions {
            Button { Task { await send() } } label: {
                BusyLabel(text: app.t("orgInviteSend"), systemImage: "paperplane.fill", busy: busy)
            }
            .nxProminentButton()
            .disabled(!ready || busy)
            Button { if !flow.path.isEmpty { flow.path.removeLast() } } label: { WideLabel(text: app.t("cancel")) }
                .nxSecondaryButton()
                .disabled(busy)
        }
        .onAppear {
            if app.capture == "org-invite" {
                phone = "82 000 1122"
                role = .worker
            }
        }
    }

    private func send() async {
        busy = true
        failed = false
        do {
            try await app.repository.inviteMember(orgId: orgId, phone: phone, role: role)
            app.dataChanged()
            if !flow.path.isEmpty { flow.path.removeLast() }
            flow.say(app.t("orgInviteSent"))
        } catch {
            failed = true
        }
        busy = false
    }
}

// MARK: - 20. Rôles et droits

struct OrgRolesView: View {
    @Environment(AppModel.self) private var app

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                Text(app.t("orgRolesHint")).font(.body(15)).foregroundStyle(Nexis.muted).lineSpacing(3)
                VStack(spacing: 0) {
                    HStack(spacing: 0) {
                        Spacer(minLength: 0)
                        ForEach(OrgRole.allCases, id: \.self) { role in
                            Text(app.roleShort(role))
                                .font(.body(11.5, .bold, relativeTo: .caption2)).foregroundStyle(Nexis.muted)
                                .frame(width: 50)
                        }
                    }
                    .padding(.bottom, 8)
                    ForEach(OrgRight.allCases, id: \.self) { right in
                        Divider()
                        HStack(spacing: 0) {
                            Text(app.rightText(right)).font(.body(14, .medium)).foregroundStyle(Nexis.ink)
                                .frame(maxWidth: .infinity, alignment: .leading)
                            ForEach(OrgRole.allCases, id: \.self) { role in
                                Group {
                                    if role.can(right) {
                                        Image(systemName: "checkmark.circle.fill").foregroundStyle(Nexis.accent)
                                    } else {
                                        Text("–").foregroundStyle(Nexis.muted)
                                    }
                                }
                                .font(.system(size: 17, weight: .semibold))
                                .frame(width: 50)
                            }
                        }
                        .padding(.vertical, 12)
                        .accessibilityElement(children: .combine)
                    }
                }
                .nxCard(padding: 14)
                InfoNote(text: app.t("orgRolesManagerNote"), systemImage: "info.circle.fill")
                InfoNote(text: app.t("orgRolesCustomHint"), systemImage: "slider.horizontal.3")
            }
            .flowScreen()
        }
        .flowTitle(app.t("orgRolesTitle"))
    }
}

// MARK: - 21. Numéros de retrait

struct OrgNumbersView: View {
    @Environment(AppModel.self) private var app
    @Environment(MissionFlow.self) private var flow
    let orgId: Int

    var body: some View {
        OrgLoader(orgId: orgId) { org in
            ScrollView {
                VStack(alignment: .leading, spacing: 14) {
                    Text(app.t("orgNumbersHint")).font(.body(15)).foregroundStyle(Nexis.muted)
                    VStack(spacing: 0) {
                        ForEach(org.numbers) { number in
                            row(number)
                            if number.id != org.numbers.last?.id { Divider().padding(.leading, 66) }
                        }
                    }
                    .background(Nexis.surface, in: RoundedRectangle(cornerRadius: 20, style: .continuous))
                    InfoNote(text: app.t("orgNumbersNote"), systemImage: "clock.badge.checkmark.fill")
                }
                .flowScreen()
            }
            .bottomActions {
                if org.myRole.can(.manageNumbers) {
                    if org.numbers.count < 4 {
                        Button { flow.push(.orgNumberAdd(org.id)) } label: {
                            WideLabel(text: app.t("orgNumberAdd"), systemImage: "plus")
                        }
                        .nxProminentButton()
                    } else {
                        Text(app.t("orgNumberLimit")).font(.body(13.5)).foregroundStyle(Nexis.muted)
                    }
                }
            }
        }
        .flowTitle(app.t("orgNumbersTitle"))
    }

    private func row(_ number: WithdrawNumber) -> some View {
        HStack(spacing: 12) {
            OperatorBadge(mobileOperator: number.mobileOperator)
            VStack(alignment: .leading, spacing: 3) {
                Text(number.mobileOperator.displayName).font(.body(15.5, .bold)).foregroundStyle(Nexis.ink)
                Text(app.t("orgNumberMerchant", ["number": app.numberText(number.number)]))
                    .font(.body(13, relativeTo: .footnote)).foregroundStyle(Nexis.muted).monospacedDigit()
            }
            Spacer(minLength: 8)
            if number.isActive() {
                Pill(tone: .ok, systemImage: "checkmark", text: app.t("orgNumberActive"))
            } else {
                Pill(tone: .wait, systemImage: "clock", text: app.t("orgNumberWaiting", ["hours": String(number.hoursLeft())]))
            }
        }
        .padding(.horizontal, 14).padding(.vertical, 12)
        .accessibilityElement(children: .combine)
    }
}

/// Ajoute un numéro marchand : choisir l'opérateur, taper le numéro, puis
/// confirmer avec le code ou Face ID. Le numéro attend 72 h.
struct OrgNumberAddView: View {
    @Environment(AppModel.self) private var app
    @Environment(MissionFlow.self) private var flow
    let orgId: Int
    @State private var mobileOperator: MobileOperator = .airtel
    @State private var number = ""
    @State private var busy = false
    @State private var failed = false

    private var parsed: DrcPhone { DrcPhone.parse(number) }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                OrgGroupLabel(text: app.t("orgNumberOperator"))
                ForEach(MobileOperator.allCases, id: \.self) { item in
                    ChoiceRow(title: item.displayName, selected: mobileOperator == item) {
                        OperatorBadge(mobileOperator: item)
                    } action: {
                        mobileOperator = item
                    }
                }
                OrgFieldCard {
                    OrgFieldRow(label: app.t("phone")) {
                        Text("+243").foregroundStyle(Nexis.muted)
                        TextField("99 123 4567", text: $number).keyboardType(.numberPad)
                    }
                }
                if !number.isEmpty && !parsed.isValid && parsed.isComplete {
                    Text(app.t("orgNumberInvalid")).font(.body(14)).foregroundStyle(Nexis.danger)
                }
                InfoNote(text: app.t("orgNumbersNote"), systemImage: "clock.badge.checkmark.fill")
                if failed {
                    Text(app.t("orgFailed")).font(.body(14)).foregroundStyle(Nexis.danger)
                }
            }
            .flowScreen()
        }
        .flowTitle(app.t("orgNumberAddTitle"))
        .bottomActions {
            Button { Task { await add() } } label: {
                BusyLabel(text: app.t("orgNumberAdd"), busy: busy)
            }
            .nxProminentButton()
            .disabled(!parsed.isValid || busy)
        }
        .onAppear {
            if app.capture == "org-number-add" { number = "99 123 4567" }
        }
    }

    private func add() async {
        busy = true
        failed = false
        // Ajouter un numéro de retrait : code NexisHub ou Face ID d'abord.
        guard await app.confirmMoneyOut(app.t("orgNumberGuard", ["number": "+243 \(parsed.formatted)"])) else {
            busy = false
            return
        }
        do {
            try await app.repository.addWithdrawNumber(orgId: orgId, mobileOperator: mobileOperator,
                                                       number: parsed.digits)
            app.dataChanged()
            if !flow.path.isEmpty { flow.path.removeLast() }
            flow.say(app.t("orgNumberDone"))
        } catch {
            failed = true
        }
        busy = false
    }
}

// MARK: - 22. Retirer de l'argent

struct OrgWithdrawView: View {
    @Environment(AppModel.self) private var app
    let orgId: Int

    var body: some View {
        OrgLoader(orgId: orgId) { org in OrgWithdrawBody(org: org) }
            .flowTitle(app.t("actionWithdraw"))
    }
}

private struct OrgWithdrawBody: View {
    @Environment(AppModel.self) private var app
    @Environment(MissionFlow.self) private var flow
    let org: Organization
    @State private var currency: Currency = .cdf
    @State private var amountText = ""
    @State private var chosen: Int?
    @State private var busy = false
    @State private var failed = false

    private var amount: Money? { PriceInput.parse(amountText, currency) }
    private var usable: [WithdrawNumber] { org.numbers.filter { $0.isActive() } }
    private var ready: Bool { amount != nil && chosen != nil }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                VStack(alignment: .leading, spacing: 4) {
                    Text(app.t("orgWithdrawAvail")).font(.body(14)).foregroundStyle(Nexis.muted)
                    Text(app.money(org.wallet.available[currency] ?? Money(0, currency)))
                        .font(.title(26)).foregroundStyle(Nexis.ink).monospacedDigit()
                }
                Picker(app.t("currency"), selection: $currency) {
                    Text("FC").tag(Currency.cdf)
                    Text("USD").tag(Currency.usd)
                }
                .pickerStyle(.segmented)
                OrgFieldCard {
                    OrgFieldRow(label: app.t("orgWithdrawAmount")) {
                        TextField("0", text: $amountText)
                            .keyboardType(currency == .usd ? .decimalPad : .numberPad)
                            .monospacedDigit()
                        Text(currency == .cdf ? "FC" : "USD").foregroundStyle(Nexis.muted)
                    }
                }
                OrgGroupLabel(text: app.t("orgWithdrawTo"))
                if usable.isEmpty {
                    InfoNote(text: app.t("orgWithdrawNoNumber"), systemImage: "clock.badge.exclamationmark.fill")
                }
                ForEach(usable) { number in
                    ChoiceRow(title: number.mobileOperator.displayName,
                              subtitle: app.t("orgNumberMerchant", ["number": app.numberText(number.number)]),
                              selected: chosen == number.id) {
                        OperatorBadge(mobileOperator: number.mobileOperator)
                    } action: {
                        chosen = number.id
                    }
                }
                InfoNote(text: app.t("orgWithdrawConfirm"), systemImage: "faceid")
                if failed {
                    Text(app.t("orgFailed")).font(.body(14)).foregroundStyle(Nexis.danger)
                }
            }
            .flowScreen()
        }
        .bottomActions {
            Button { Task { await withdraw() } } label: {
                BusyLabel(text: app.t("orgWithdrawGo", ["amount": amount.map { app.money($0) } ?? ""]), busy: busy)
            }
            .nxProminentButton()
            .disabled(!ready || busy)
        }
        .onChange(of: amountText) { _, text in
            let typed = PriceInput.typed(text, currency)
            if typed != text { amountText = typed }
        }
        .onChange(of: currency) { amountText = "" }
        .onAppear {
            chosen = usable.first?.id
            if app.capture == "org-withdraw" { amountText = "500 000" }
        }
    }

    private func withdraw() async {
        guard let amount, let chosen, let number = usable.first(where: { $0.id == chosen }) else { return }
        busy = true
        failed = false
        // Une sortie d'argent : code NexisHub ou Face ID d'abord.
        let reason = app.t("orgWithdrawGuard", ["amount": app.money(amount), "name": org.shortName,
                                                "operator": number.mobileOperator.displayName])
        guard await app.confirmMoneyOut(reason) else {
            busy = false
            return
        }
        do {
            try await app.repository.requestOrgWithdrawal(orgId: org.id, amount: amount, numberId: number.id)
            app.dataChanged()
            if !flow.path.isEmpty { flow.path.removeLast() }
            flow.say(app.t("orgWithdrawDone", ["amount": app.money(amount)]))
        } catch {
            failed = true
        }
        busy = false
    }
}

// MARK: - Droits d'une personne

/// Ce que le représentant laisse voir et faire à une personne de l'équipe.
/// On part des droits proposés pour son rôle, puis on les adapte.
struct OrgMemberView: View {
    @Environment(AppModel.self) private var app
    let orgId: Int
    let memberId: Int

    var body: some View {
        OrgLoader(orgId: orgId) { org in
            if let member = org.members.first(where: { $0.id == memberId }) {
                OrgMemberBody(org: org, member: member)
            } else {
                FlowLoading(label: app.t("orgMemberRightsTitle"))
            }
        }
        .flowTitle(app.t("orgMemberRightsTitle"))
    }
}

private struct OrgMemberBody: View {
    @Environment(AppModel.self) private var app
    @Environment(MissionFlow.self) private var flow
    let org: Organization
    let member: OrgMember
    @State private var rights: Set<OrgRight> = []
    @State private var busy = false
    @State private var failed = false

    private var current: Set<OrgRight> { member.effectiveRights.filter(\.isEditable) }
    private var editable: Bool { org.myRole.can(.manageMembers) && member.role != .representative }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                HStack(spacing: 12) {
                    PersonAvatar(initials: member.initials, color: member.color, size: 52)
                    VStack(alignment: .leading, spacing: 4) {
                        Text(member.name).font(.title(17)).foregroundStyle(Nexis.ink).lineLimit(1)
                        Text(app.memberSubtitle(member)).font(.body(13.5)).foregroundStyle(Nexis.muted)
                    }
                    Spacer(minLength: 0)
                }
                Text(app.t("orgMemberRightsHint", ["name": app.shortPerson(member.name)]))
                    .font(.body(14.5)).foregroundStyle(Nexis.muted).lineSpacing(3)
                VStack(spacing: 0) {
                    ForEach(OrgRight.allCases, id: \.self) { right in
                        if right.isEditable {
                            Toggle(isOn: binding(right)) {
                                Text(app.rightText(right)).font(.body(15, .medium)).foregroundStyle(Nexis.ink)
                            }
                            .tint(Nexis.brand)
                            .disabled(!editable || busy)
                            .padding(.horizontal, 14).padding(.vertical, 10)
                        } else {
                            HStack(spacing: 10) {
                                Image(systemName: "lock.fill").font(.system(size: 14, weight: .semibold))
                                    .foregroundStyle(Nexis.muted)
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(app.rightText(right)).font(.body(15, .medium)).foregroundStyle(Nexis.muted)
                                    Text(app.t("orgMemberFixed")).font(.body(12.5, relativeTo: .caption1))
                                        .foregroundStyle(Nexis.muted)
                                }
                                Spacer(minLength: 0)
                            }
                            .padding(.horizontal, 14).padding(.vertical, 12)
                            .accessibilityElement(children: .combine)
                        }
                        if right != OrgRight.allCases.last { Divider().padding(.leading, 14) }
                    }
                }
                .background(Nexis.surface, in: RoundedRectangle(cornerRadius: 20, style: .continuous))
                if failed {
                    Text(app.t("orgFailed")).font(.body(14)).foregroundStyle(Nexis.danger)
                }
            }
            .flowScreen()
        }
        .bottomActions {
            if editable {
                Button { Task { await save() } } label: {
                    BusyLabel(text: app.t("orgAssignSave"), busy: busy)
                }
                .nxProminentButton()
                .disabled(rights == current || busy)
                Button { rights = member.role.defaultRights.filter(\.isEditable) } label: {
                    WideLabel(text: app.t("orgMemberDefaults"))
                }
                .nxSecondaryButton()
                .disabled(busy)
            }
        }
        .onAppear { rights = current }
    }

    private func binding(_ right: OrgRight) -> Binding<Bool> {
        Binding(get: { rights.contains(right) },
                set: { on in if on { rights.insert(right) } else { rights.remove(right) } })
    }

    private func save() async {
        busy = true
        failed = false
        do {
            try await app.repository.setMemberRights(orgId: org.id, memberId: member.id, rights: rights)
            app.dataChanged()
            if !flow.path.isEmpty { flow.path.removeLast() }
            flow.say(app.t("orgMemberSaved"))
        } catch {
            failed = true
        }
        busy = false
    }
}

// MARK: - Profil de l'espace

/// Le 4e onglet de l'espace entreprise : l'entreprise elle-même (photo,
/// représentant, e-mail), son équipe, ses numéros, À propos, et le retour
/// au compte personnel.
struct OrgProfileView: View {
    @Environment(AppModel.self) private var app
    let orgId: Int
    @State private var flow = MissionFlow()
    @State private var org: Organization?
    @State private var switching = false

    var body: some View {
        NavigationStack(path: $flow.path) {
            List {
                if let org {
                    Section {
                        HStack(spacing: 16) {
                            Button { flow.push(.photo("org-\(org.id)")) } label: {
                                OrgMark(name: org.name, size: 64, photoKey: "org-\(org.id)")
                                    .overlay(alignment: .bottomTrailing) {
                                        Image(systemName: "camera.fill")
                                            .font(.system(size: 11, weight: .bold))
                                            .foregroundStyle(.white)
                                            .frame(width: 24, height: 24)
                                            .background(Nexis.navy, in: Circle())
                                            .overlay(Circle().strokeBorder(Nexis.surface, lineWidth: 2))
                                            .offset(x: 3, y: 3)
                                    }
                            }
                            .buttonStyle(.plain)
                            .accessibilityLabel(app.t("photoEdit"))
                            VStack(alignment: .leading, spacing: 4) {
                                Text(org.name).font(.title(18)).foregroundStyle(Nexis.ink)
                                Text("RCCM \(org.rccm)").font(.body(13.5)).foregroundStyle(Nexis.muted)
                                Text(app.t("orgSpaceLabel"))
                                    .font(.body(12, .semibold, relativeTo: .caption1))
                                    .foregroundStyle(.white)
                                    .padding(.horizontal, 10).padding(.vertical, 3)
                                    .background(Nexis.navy, in: Capsule())
                            }
                        }
                        .padding(.vertical, 6)
                    }
                    Section {
                        info(app.t("orgProfileRep"), org.representative)
                        if !org.email.isEmpty { info(app.t("orgProfileEmail"), org.email) }
                    }
                    Section {
                        if org.can(.seeTeam) {
                            row("person.2", app.t("orgQuickTeam"), app.roleName(org.myRole), .orgTeam(org.id))
                        }
                        if org.myRole.can(.manageNumbers) {
                            row("phone.badge.checkmark", app.t("orgNumbersTitle"), nil, .orgNumbers(org.id))
                        }
                        row("slider.horizontal.3", app.t("orgRolesTitle"), nil, .orgRoles)
                    }
                    Section {
                        row("info.circle", app.t("aboutRow"), app.t("aboutRowSub"), .about)
                        row("doc.text", app.t("legalTerms"), nil, .legal)
                    }
                    Section {
                        Button { switching = true } label: {
                            Label { Text(app.t("orgSwitchRow")).font(.body(16)).foregroundStyle(Nexis.ink) } icon: {
                                Image(systemName: "arrow.left.arrow.right").foregroundStyle(Nexis.accent)
                            }
                        }
                        Button { app.openClientSpace() } label: {
                            Label { Text(app.t("orgBackPersonal")).font(.body(16)).foregroundStyle(Nexis.ink) } icon: {
                                Image(systemName: "person.crop.circle").foregroundStyle(Nexis.accent)
                            }
                        }
                    }
                }
            }
            .scrollContentBackground(.hidden)
            .background(Nexis.bg)
            .navigationTitle(app.t("orgProfileCompany"))
            .missionDestinations()
            .task(id: app.revision) { org = try? await app.repository.organization(id: orgId) }
        }
        .missionFlow(flow, tab: .profile)
        .sheet(isPresented: $switching) { SpacePickerSheet() }
    }

    private func info(_ label: String, _ value: String) -> some View {
        HStack {
            Text(label).font(.body(14)).foregroundStyle(Nexis.muted)
            Spacer(minLength: 12)
            Text(value).font(.body(15, .medium)).foregroundStyle(Nexis.ink).multilineTextAlignment(.trailing)
        }
        .accessibilityElement(children: .combine)
    }

    private func row(_ symbol: String, _ title: String, _ subtitle: String?, _ route: MissionRoute) -> some View {
        Button { flow.push(route) } label: {
            HStack {
                Label {
                    VStack(alignment: .leading, spacing: 2) {
                        Text(title).font(.body(16)).foregroundStyle(Nexis.ink)
                        if let subtitle {
                            Text(subtitle).font(.body(13, relativeTo: .footnote)).foregroundStyle(Nexis.muted)
                        }
                    }
                } icon: {
                    Image(systemName: symbol).foregroundStyle(Nexis.accent)
                }
                Spacer()
                Image(systemName: "chevron.right")
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundStyle(Color(light: 0xC4CAD4, dark: 0x4A5A75))
            }
            .contentShape(Rectangle())
        }
    }
}
