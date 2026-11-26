import SwiftUI

// MARK: - Missions

struct MissionsView: View {
    @Environment(AppModel.self) private var app
    @State private var missions: [Mission] = []
    @State private var showDone = false
    @State private var flow = MissionFlow()

    var body: some View {
        let list = showDone ? missions.filter { $0.status == .completed } : missions.filter(\.isActive)
        NavigationStack(path: $flow.path) {
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
                        Text(app.t("noMissions"))
                            .font(.body(15)).foregroundStyle(Nexis.muted)
                    }
                    ForEach(list) { mission in
                        Button { flow.open(mission, app: app) } label: {
                            MissionRow(mission: mission)
                        }
                        .buttonStyle(.plain)
                    }
                }
            }
            .scrollContentBackground(.hidden)
            .background(Nexis.bg)
            .navigationTitle(app.t("myMissions"))
            .missionDestinations()
            .task(id: app.revision) { missions = (try? await app.repository.missions()) ?? [] }
        }
        .missionFlow(flow, tab: .missions)
        .onAppear {
            if let routes = MissionRoute.forCapture(app.capture), flow.path.isEmpty,
               !MissionRoute.providerCaptures.contains(app.capture ?? "") {
                flow.path = routes
            }
        }
    }
}

// MARK: - Portefeuille

struct WalletView: View {
    @Environment(AppModel.self) private var app
    @State private var wallet: Wallet = .empty
    @State private var movements: [Movement] = []

    var body: some View {
        NavigationStack {
            List {
                Section {
                    WalletCard(wallet: wallet)
                        .listRowBackground(Color.clear)
                        .listRowInsets(EdgeInsets())
                }
                Section {
                    if movements.isEmpty {
                        Text(app.t("noMissions"))
                            .font(.body(15)).foregroundStyle(Nexis.muted)
                    }
                    ForEach(movements) { movement in
                        MovementRow(movement: movement)
                    }
                } header: {
                    Text(app.t("recentMovements")).font(.body(13, .semibold))
                }
            }
            .scrollContentBackground(.hidden)
            .background(Nexis.bg)
            .navigationTitle(app.t("navWallet"))
            .task(id: app.revision) {
                wallet = (try? await app.repository.wallet()) ?? .empty
                movements = (try? await app.repository.movements()) ?? []
            }
        }
    }
}

private struct MovementRow: View {
    @Environment(AppModel.self) private var app
    let movement: Movement

    var body: some View {
        HStack(spacing: 14) {
            Image(systemName: symbol)
                .font(.system(size: 16, weight: .semibold))
                .foregroundStyle(tint)
                .frame(width: 40, height: 40)
                .background(tint.opacity(0.12), in: Circle())
            VStack(alignment: .leading, spacing: 3) {
                Text(movement.label)
                    .font(.body(15, .semibold)).foregroundStyle(Nexis.ink)
                Text([app.day(movement.when), app.paymentLabel(movement.state)]
                        .compactMap { $0 }.joined(separator: " · "))
                    .font(.body(13, relativeTo: .footnote)).foregroundStyle(Nexis.muted)
            }
            Spacer()
            Text(app.amountsHidden ? "•••" : (movement.amount.minorUnits > 0 ? "+" : "")
                 + app.money(movement.amount))
                .font(.title(14, .semibold, relativeTo: .subheadline))
                .foregroundStyle(movement.amount.minorUnits > 0 ? Nexis.ok : Nexis.ink)
                .monospacedDigit()
        }
        .accessibilityElement(children: .combine)
    }

    private var symbol: String {
        switch movement.kind {
        case .payment: return "lock.shield.fill"
        case .refund: return "arrow.uturn.backward"
        case .release: return "checkmark.seal.fill"
        case .deposit: return "arrow.down.to.line"
        case .withdrawal: return "arrow.up.to.line"
        }
    }

    private var tint: Color {
        switch movement.state {
        case .secured: return Nexis.accent
        case .refunded, .available: return Nexis.ok
        case .blocked: return Nexis.danger
        case .released, .none: return Nexis.muted
        }
    }
}

// MARK: - Profil

struct ProfileView: View {
    @Environment(AppModel.self) private var app
    @State private var profile: Profile?
    @State private var devicesCount = 1
    @State private var worksAsked = false
    @State private var flow = MissionFlow()

    var body: some View {
        NavigationStack(path: $flow.path) {
            List {
                if let profile {
                    Section {
                        HStack(spacing: 16) {
                            InitialsAvatar(initials: profile.initials)
                            VStack(alignment: .leading, spacing: 4) {
                                Text("\(profile.firstName) \(profile.lastName)")
                                    .font(.title(19)).foregroundStyle(Nexis.ink)
                                Text("+243 \(DrcPhone.parse(profile.phone).formatted) · \(profile.commune)")
                                    .font(.body(14)).foregroundStyle(Nexis.muted)
                                Text(app.t(profile.providerStatus == .pending ? "providerPending"
                                           : app.providerSpace ? "spaceProvider" : "clientBadge"))
                                    .font(.body(12, .semibold, relativeTo: .caption1))
                                    .foregroundStyle(Nexis.softInk)
                                    .padding(.horizontal, 10).padding(.vertical, 3)
                                    .background(Nexis.soft, in: Capsule())
                            }
                        }
                        .padding(.vertical, 6)
                    }
                    if profile.providerStatus == .pending {
                        Section {
                            InfoNote(text: app.t("providerPendingHint"), systemImage: "hourglass")
                                .listRowBackground(Color.clear)
                                .listRowInsets(EdgeInsets())
                        }
                    }
                    if profile.isProvider {
                        Section {
                            SpaceSwitch()
                                .listRowBackground(Color.clear)
                                .listRowInsets(EdgeInsets())
                        }
                    }
                }
                Section {
                    row("person.text.rectangle", app.t("myInfo"), app.t("myInfoSub"), .profileInfo)
                    Picker(selection: Binding(get: { app.language }, set: { app.language = $0 })) {
                        Text("Français").tag("fr")
                        Text("Lingála").tag("ln")
                        Text("English").tag("en")
                    } label: {
                        Label { Text(app.t("language")).font(.body(16)) } icon: {
                            Image(systemName: "globe")
                        }
                    }
                    row("bell.badge", app.t("notifications"), app.t("notificationsSub"), .notificationSettings)
                    row("iphone", app.t("myDevices"), app.plural("devicesCount", count: devicesCount), .devices)
                    row("lock.shield", app.t("securityRow"), app.t("securityRowSub"), .security)
                    row("questionmark.bubble", app.t("helpDisputes"), app.t("helpDisputesSub"), .help)
                }
                if let profile, profile.providerStatus == nil {
                    Section {
                        row("briefcase", app.t("becomeProvider"), app.t("becomeProviderSub"), .becomeProvider)
                    }
                } else if profile != nil {
                    Section {
                        // Preuves de réalisations : vues seulement par l'équipe ; un point si elle en demande.
                        row("photo.stack", app.t("myWorks"), app.t(worksAsked ? "worksAskedShort" : "myWorksSub"), .portfolio)
                            .badge(worksAsked ? 1 : 0)
                    }
                }
                Section {
                    row("doc.text", app.t("legalTerms"), nil, .legal)
                    Button { flow.comingSoon = SheetTitle(app.t("legalPrivacy")) } label: {
                        rowLabel("hand.raised", app.t("legalPrivacy"), nil)
                    }
                }
                Section {
                    Button(role: .destructive) { app.signOut() } label: {
                        Text(app.t("signOut")).font(.body(16, .semibold))
                            .frame(maxWidth: .infinity)
                    }
                }
            }
            .scrollContentBackground(.hidden)
            .background(Nexis.bg)
            .navigationTitle(app.t("navProfile"))
            .missionDestinations()
            .task(id: app.revision) {
                profile = try? await app.repository.profile()
                devicesCount = (try? await app.repository.devices())?.count ?? 1
                worksAsked = ((try? await app.repository.portfolioRequest()) ?? nil) != nil
            }
        }
        .missionFlow(flow, tab: .profile)
        .onAppear {
            if let capture = app.capture, MissionRoute.profileCaptures.contains(capture), flow.path.isEmpty,
               let routes = MissionRoute.forCapture(capture) {
                flow.path = routes
            }
        }
    }

    private func row(_ symbol: String, _ title: String, _ subtitle: String?, _ route: MissionRoute) -> some View {
        Button { flow.push(route) } label: {
            HStack {
                rowLabel(symbol, title, subtitle)
                Spacer()
                Image(systemName: "chevron.right")
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundStyle(Color(light: 0xC4CAD4, dark: 0x4A5A75))
            }
            .contentShape(Rectangle())
        }
    }

    private func rowLabel(_ symbol: String, _ title: String, _ subtitle: String?) -> some View {
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
    }
}
