import SwiftUI

/// Accueil client, d'après la maquette validée du 22 novembre : salutation,
/// une seule carte de portefeuille, cinq actions rapides, puis les
/// prestations (En cours d'abord, Terminées ensuite).
struct HomeView: View {
    @Environment(AppModel.self) private var app
    let onPickService: () -> Void
    let onTab: (AppTab) -> Void

    @State private var profile: Profile?
    @State private var wallet: Wallet = .empty
    @State private var missions: [Mission] = []
    @State private var showDone = false
    @State private var comingSoon: SheetTitle?

    /// Missions montrées ici ; le reste est dans l'onglet Missions.
    private let shown = 2

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 22) {
                    WalletCard(wallet: wallet)
                    quickActions
                    if missions.isEmpty {
                        firstRequest
                    } else {
                        lastServices
                    }
                }
                .padding(.horizontal, 18)
                .padding(.bottom, 24)
            }
            .background(Nexis.bg)
            .navigationTitle(greeting)
            .toolbar {
                if !ShellView.hasAccessory {
                    ToolbarItem(placement: .topBarTrailing) {
                        Button(action: onPickService) {
                            Image(systemName: "plus")
                        }
                        .accessibilityLabel(app.t("requestService"))
                    }
                }
            }
            .sheet(item: $comingSoon) { item in ComingSoonView(title: item.id) }
            .task(id: app.revision) { await load() }
        }
    }

    private var greeting: String {
        guard let profile else { return "Nexis Hub" }
        let hour = Calendar.current.component(.hour, from: .now)
        return app.t(hour < 12 ? "helloHome" : "eveningHome", ["name": profile.firstName])
    }

    private func load() async {
        let repo = app.repository
        profile = try? await repo.profile()
        wallet = (try? await repo.wallet()) ?? .empty
        missions = (try? await repo.missions()) ?? []
    }

    private var quickActions: some View {
        HStack(alignment: .top, spacing: 0) {
            QuickAction(symbol: "square.grid.2x2.fill", label: app.t("actionServices"),
                        action: onPickService)
            QuickAction(symbol: "arrow.down.to.line", label: app.t("actionDeposit")) {
                comingSoon = SheetTitle(app.t("actionDeposit"))
            }
            QuickAction(symbol: "arrow.up.to.line", label: app.t("actionWithdraw")) {
                comingSoon = SheetTitle(app.t("actionWithdraw"))
            }
            QuickAction(symbol: "clock.arrow.circlepath", label: app.t("actionHistory")) {
                onTab(.wallet)
            }
            QuickAction(symbol: "ellipsis", label: app.t("actionMore")) {
                comingSoon = SheetTitle(app.t("actionMore"))
            }
        }
        .accessibilityElement(children: .contain)
        .accessibilityLabel(app.t("quickActions"))
    }

    private var firstRequest: some View {
        VStack(spacing: 14) {
            Text(app.t("firstRequestTitle"))
                .font(.title(20))
                .foregroundStyle(Nexis.ink)
                .multilineTextAlignment(.center)
            Text(app.t("pickServiceHint"))
                .font(.body(15)).foregroundStyle(Nexis.muted)
                .multilineTextAlignment(.center)
            Button(action: onPickService) {
                WideLabel(text: app.t("requestService"), systemImage: "plus")
            }
            .nxProminentButton()
        }
        .frame(maxWidth: .infinity)
        .nxCard(padding: 22)
    }

    private var lastServices: some View {
        let ongoing = missions.filter(\.isActive)
        let done = missions.filter { $0.status == .completed }
        let list = showDone ? done : ongoing
        return VStack(alignment: .leading, spacing: 12) {
            Text(app.t("lastServices"))
                .font(.title(18)).foregroundStyle(Nexis.ink)
            Picker(app.t("lastServices"), selection: $showDone) {
                Text(app.t("tabOngoing")).tag(false)
                Text(app.t("tabDone")).tag(true)
            }
            .pickerStyle(.segmented)
            if list.isEmpty {
                Text(app.t("noMissions"))
                    .font(.body(15)).foregroundStyle(Nexis.muted)
                    .padding(.vertical, 12)
            } else {
                VStack(spacing: 0) {
                    ForEach(list.prefix(shown)) { mission in
                        Button { comingSoon = SheetTitle(app.t("followMission")) } label: {
                            MissionRow(mission: mission)
                                .padding(.horizontal, 16)
                                .padding(.vertical, 10)
                                .contentShape(Rectangle())
                        }
                        .buttonStyle(.plain)
                        if mission.id != list.prefix(shown).last?.id {
                            Divider().padding(.leading, 74)
                        }
                    }
                }
                .background(Nexis.surface, in: RoundedRectangle(cornerRadius: 22, style: .continuous))
                if list.count > shown {
                    Button(app.t("seeMissions", ["count": String(list.count)])) { onTab(.missions) }
                        .font(.body(15, .semibold))
                        .frame(maxWidth: .infinity)
                }
            }
        }
    }
}

private struct QuickAction: View {
    let symbol: String
    let label: String
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            VStack(spacing: 8) {
                Image(systemName: symbol)
                    .font(.system(size: 19, weight: .semibold))
                    .foregroundStyle(Nexis.accent)
                    .frame(width: 54, height: 54)
                    .nxGlass(tint: Nexis.brand.opacity(0.10), interactive: true,
                             in: RoundedRectangle(cornerRadius: 18, style: .continuous))
                Text(label)
                    .font(.body(12, .medium, relativeTo: .caption1))
                    .foregroundStyle(Nexis.ink)
                    .lineLimit(2)
                    .multilineTextAlignment(.center)
                    .minimumScaleFactor(0.85)
            }
            .frame(maxWidth: .infinity)
        }
        .buttonStyle(.plain)
        .accessibilityLabel(label)
    }
}

/// La carte du portefeuille, partagée par l'accueil et l'onglet
/// Portefeuille : devise au choix, montants masquables, et l'explication
/// de l'argent bloqué pour les missions en cours.
struct WalletCard: View {
    @Environment(AppModel.self) private var app
    let wallet: Wallet
    @State private var explaining = false

    var body: some View {
        @Bindable var model = app
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                Text(app.t("available"))
                    .font(.body(14, .medium, relativeTo: .subheadline))
                    .foregroundStyle(.white.opacity(0.85))
                Spacer()
                Picker(app.t("currency"), selection: $model.walletCurrency) {
                    Text("FC").tag(Currency.cdf)
                    Text("USD").tag(Currency.usd)
                }
                .pickerStyle(.segmented)
                .fixedSize()
                .environment(\.colorScheme, .dark)
                Button {
                    app.amountsHidden.toggle()
                } label: {
                    Image(systemName: app.amountsHidden ? "eye.slash" : "eye")
                        .font(.system(size: 16, weight: .semibold))
                        .foregroundStyle(.white)
                        .frame(width: 34, height: 34)
                }
                .accessibilityLabel(app.amountsHidden ? app.t("showAmounts") : app.t("hideAmounts"))
            }
            Text(shown(wallet.available[app.walletCurrency]))
                .font(.title(32, .semibold, relativeTo: .largeTitle))
                .foregroundStyle(.white)
                .monospacedDigit()
                .contentTransition(.numericText())
                .lineLimit(1)
                .minimumScaleFactor(0.6)
            if let secured = wallet.secured[app.walletCurrency], !secured.isZero {
                Button { explaining = true } label: {
                    HStack(spacing: 6) {
                        Image(systemName: "lock.shield.fill")
                        Text(app.t("heldForMissions", ["amount": shown(secured)]))
                            .multilineTextAlignment(.leading)
                        Image(systemName: "info.circle")
                    }
                    .font(.body(13, .medium, relativeTo: .footnote))
                    .foregroundStyle(.white)
                    .padding(.horizontal, 12)
                    .padding(.vertical, 8)
                    .nxGlass(tint: .white.opacity(0.12), interactive: true)
                }
                .buttonStyle(.plain)
                .accessibilityHint(app.t("heldWhy"))
            }
        }
        .padding(20)
        .background(Nexis.brandGradient, in: RoundedRectangle(cornerRadius: 28, style: .continuous))
        .shadow(color: Nexis.brand.opacity(0.35), radius: 18, y: 10)
        .sheet(isPresented: $explaining) {
            VStack(alignment: .leading, spacing: 12) {
                Label(app.t("heldWhy"), systemImage: "lock.shield.fill")
                    .font(.title(18)).foregroundStyle(Nexis.ink)
                Text(app.t("heldTip")).font(.body(16)).foregroundStyle(Nexis.ink)
                Text(app.t("walletExplanation")).font(.body(14)).foregroundStyle(Nexis.muted)
                Spacer()
                Button { explaining = false } label: { WideLabel(text: app.t("ok")) }
                    .nxProminentButton()
            }
            .padding(24)
            .presentationDetents([.medium])
        }
    }

    private func shown(_ money: Money?) -> String {
        if app.amountsHidden { return "••••" }
        return app.money(money ?? Money(0, app.walletCurrency))
    }
}
