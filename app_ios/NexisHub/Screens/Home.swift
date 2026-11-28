import SwiftUI

/// Accueil client, d'après la maquette validée du 22 novembre : salutation,
/// une seule carte de portefeuille, quatre actions rapides, puis les
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
    @State private var notifications: [AppNotification] = []
    @State private var showingNotifications = false
    @State private var flow = MissionFlow()

    /// Missions montrées ici ; le reste est dans l'onglet Missions.
    private let shown = 2

    var body: some View {
        NavigationStack(path: $flow.path) {
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
            // « Bonjour, Ben » reste à gauche, même quand on fait défiler
            // (choix de Ben) : une barre à nous à la place du grand titre.
            .greetingHeader(greeting) {
                if !ShellView.hasAccessory {
                    HeaderIconButton(systemImage: "plus", label: app.t("requestService"), action: onPickService)
                }
                // La cloche : un point rouge quand une notification n'a pas été lue.
                HeaderIconButton(systemImage: "bell", label: app.t("notifications"),
                                 dot: notifications.contains(where: { !$0.read })) {
                    showingNotifications = true
                }
                // Le rond du profil (initiales tant qu'il n'y a pas de photo).
                if let profile {
                    Button { onTab(.profile) } label: {
                        InitialsAvatar(initials: profile.initials, size: 38, photoKey: "me")
                    }
                    .buttonStyle(.plain)
                    .accessibilityLabel(app.t("navProfile"))
                }
            }
            .navigationDestination(isPresented: $showingNotifications) {
                NotificationsView(items: notifications)
            }
            .sheet(item: $comingSoon) { item in ComingSoonView(title: item.id) }
            .missionDestinations()
            .task(id: app.revision) { await load() }
        }
        .missionFlow(flow, tab: .home)
    }

    private var greeting: String {
        guard let profile else { return "NexisHub" }
        let hour = Calendar.current.component(.hour, from: .now)
        return app.t(hour < 12 ? "helloHome" : "eveningHome", ["name": profile.firstName])
    }

    private func load() async {
        let repo = app.repository
        profile = try? await repo.profile()
        wallet = (try? await repo.wallet()) ?? .empty
        missions = (try? await repo.missions()) ?? []
        notifications = (try? await repo.notifications()) ?? []
    }

    private var quickActions: some View {
        HStack(alignment: .top, spacing: 0) {
            QuickAction(symbol: "square.grid.2x2.fill", label: app.t("actionServices"),
                        action: onPickService)
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
                        Button { flow.open(mission, app: app) } label: {
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

struct QuickAction: View {
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
    /// Légende au-dessus du montant (« Disponible » par défaut).
    var title: String? = nil
    /// Dans l'espace entreprise, la carte est marine au lieu de bleue.
    var org = false
    @State private var explaining = false

    var body: some View {
        @Bindable var model = app
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                Text(title ?? app.t("available"))
                    .font(.body(14, .medium, relativeTo: .subheadline))
                    .foregroundStyle(.white.opacity(0.85))
                Spacer()
                CurrencySwitch(selection: $model.walletCurrency, label: app.t("currency"))
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
                    .nxOnBrandPill(in: RoundedRectangle(cornerRadius: 14, style: .continuous))
                    .contentShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
                }
                .buttonStyle(.plain)
                .accessibilityHint(app.t("heldWhy"))
            }
        }
        .padding(20)
        .background(org ? Nexis.orgGradient : Nexis.brandGradient,
                    in: RoundedRectangle(cornerRadius: 28, style: .continuous))
        .shadow(color: (org ? Nexis.navy : Nexis.brand).opacity(0.35), radius: 18, y: 10)
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

/// Les notifications : la liste, ou un écran vide tant qu'il n'y en a pas.
struct NotificationsView: View {
    @Environment(AppModel.self) private var app
    let items: [AppNotification]

    var body: some View {
        Group {
            if items.isEmpty {
                ContentUnavailableView {
                    Label(app.t("notifications"), systemImage: "bell")
                } description: {
                    Text(app.t("noMissions"))
                }
            } else {
                List {
                    ForEach(items) { (item: AppNotification) in
                        NotificationRow(item: item)
                            .listRowBackground(item.read ? Nexis.surface : Nexis.soft)
                    }
                }
                .scrollContentBackground(.hidden)
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Nexis.bg)
        .navigationTitle(app.t("notifications"))
        .navigationBarTitleDisplayMode(.inline)
    }
}

private struct NotificationRow: View {
    @Environment(AppModel.self) private var app
    let item: AppNotification

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(item.title).font(.body(15, .semibold, relativeTo: .headline))
            Text(item.message).font(.body(14, relativeTo: .subheadline)).foregroundStyle(Nexis.muted)
            Text(app.day(item.when)).font(.body(12, relativeTo: .caption1)).foregroundStyle(Nexis.muted)
        }
        .padding(.vertical, 4)
    }
}

/// Choix FC / USD sur la carte bleue : la devise choisie en blanc avec le
/// texte bleu, l'autre en blanc sur le fond assombri (le contrôle segmenté
/// du système devenait pâle sur ce bleu).
private struct CurrencySwitch: View {
    @Binding var selection: Currency
    let label: String

    var body: some View {
        HStack(spacing: 2) {
            ForEach(Currency.allCases, id: \.self) { currency in
                let isOn = selection == currency
                Button { selection = currency } label: {
                    Text(currency == .cdf ? "FC" : "USD")
                        .font(.body(13, .semibold, relativeTo: .footnote))
                        .foregroundStyle(isOn ? Nexis.brand : Color.white)
                        .padding(.horizontal, 12)
                        .frame(minHeight: 30)
                        .background(Capsule().fill(isOn ? Color.white : Color.clear))
                        .contentShape(Capsule())
                }
                .buttonStyle(.plain)
                .accessibilityAddTraits(isOn ? .isSelected : [])
            }
        }
        .padding(3)
        .nxOnBrandPill()
        .fixedSize()
        .animation(.snappy(duration: 0.2), value: selection)
        .accessibilityElement(children: .contain)
        .accessibilityLabel(label)
    }
}

/// Barre du haut des accueils : la salutation à gauche, toujours à la même
/// place, et les boutons à droite. Elle remplace le grand titre d'iOS, qui
/// se centre quand on fait défiler.
private struct GreetingHeader<Trailing: View>: ViewModifier {
    let title: String
    @ViewBuilder var trailing: Trailing

    func body(content: Content) -> some View {
        content
            .navigationTitle(title)
            .toolbar(.hidden, for: .navigationBar)
            .safeAreaInset(edge: .top, spacing: 0) {
                HStack(spacing: 10) {
                    Text(title)
                        .font(.title(24, .semibold, relativeTo: .title1))
                        .foregroundStyle(Nexis.ink)
                        .lineLimit(1)
                        .minimumScaleFactor(0.7)
                        .accessibilityAddTraits(.isHeader)
                    Spacer(minLength: 8)
                    trailing
                }
                .padding(.horizontal, 18)
                .padding(.top, 6)
                .padding(.bottom, 10)
                .background(Nexis.bg.opacity(0.96).ignoresSafeArea(edges: .top))
            }
    }
}

extension View {
    func greetingHeader(_ title: String, @ViewBuilder trailing: () -> some View = { EmptyView() }) -> some View {
        modifier(GreetingHeader(title: title, trailing: trailing))
    }
}

/// Bouton rond de la barre des accueils (cloche, « + »).
struct HeaderIconButton: View {
    let systemImage: String
    let label: String
    var dot = false
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Image(systemName: systemImage)
                .font(.system(size: 17, weight: .semibold))
                .foregroundStyle(Nexis.ink)
                .frame(width: 40, height: 40)
                .background(Nexis.surface, in: Circle())
                .overlay(Circle().strokeBorder(Nexis.line, lineWidth: 0.5))
                .overlay(alignment: .topTrailing) {
                    if dot {
                        Circle().fill(Nexis.danger).frame(width: 9, height: 9).offset(x: -8, y: 8)
                    }
                }
        }
        .buttonStyle(.plain)
        .accessibilityLabel(label)
    }
}
