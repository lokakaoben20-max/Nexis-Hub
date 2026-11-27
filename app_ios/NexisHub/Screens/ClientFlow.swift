import SwiftUI
import UIKit

// Parcours client d'une mission, repris des écrans Flutter
// (app_mobile/lib/screens/client) : devis, paiement, attente de
// l'opérateur, suivi, confirmation, signalement et litige.

// MARK: - Navigation

/// Les écrans qu'on ouvre depuis une mission ou depuis le profil. Ils ne
/// portent que des numéros : chaque écran relit le dépôt, jamais une copie
/// gardée.
enum MissionRoute: Hashable {
    case quotes(Int)
    case pay(mission: Int, quote: Int)
    case pending(mission: Int, quote: Int, via: MobileOperator)
    case tracking(Int)
    case confirm(Int)
    case report(Int)
    case dispute(Int)
    case sendQuote(Int)
    case job(Int)
    // Écrans ouverts depuis le profil.
    case profileInfo
    case devices
    case notificationSettings
    case help
    case legal
    case becomeProvider
    case security
    case portfolio
    // Espace entreprise.
    case orgCreate
    case orgStatus(Int)
    case orgInvitation(Int)
    case orgIdentity
    case orgTeam(Int)
    case orgInvite(Int)
    case orgRoles
    case orgNumbers(Int)
    case orgNumberAdd(Int)
    case orgWithdraw(Int)
    case orgMember(org: Int, member: Int)
    // Photo de profil (« me » ou « org-<numéro> ») et À propos.
    case photo(String)
    case about

    /// Écrans ouverts d'emblée pour les captures de la CI.
    static func forCapture(_ capture: String?) -> [MissionRoute]? {
        switch capture {
        case "tracking": return [.tracking(51)]
        case "quotes", ShowcaseDemo.capture: return [.quotes(52)]
        case "pay": return [.quotes(52), .pay(mission: 52, quote: 521)]
        case "pending": return [.pending(mission: 52, quote: 521, via: .mpesa)]
        case "confirm": return [.tracking(49), .confirm(49)]
        case "report": return [.report(51)]
        case "dispute": return [.dispute(47)]
        case "decision": return [.dispute(44)]
        case "request": return [.sendQuote(71)]
        case "job": return [.job(61)]
        case "info": return [.profileInfo]
        case "devices": return [.devices]
        case "alerts": return [.notificationSettings]
        case "help": return [.help]
        case "legal": return [.legal]
        case "become", PortfolioDemo.step: return [.becomeProvider]
        case PortfolioDemo.profile, PortfolioDemo.locked: return [.portfolio]
        case let capture? where IdentityDemo.captures.contains(capture): return [.becomeProvider]
        case "security": return [.security]
        case "org-intro", "org-step1", "org-rep-verified", "org-rep-unverified", "org-docs", "org-terms":
            return [.orgCreate]
        case "org-pending", "org-correction", "org-approved": return [.orgStatus(1)]
        case "org-invited-verified", "org-invited-unverified": return [.orgInvitation(1)]
        case "org-team": return [.orgTeam(1)]
        case "org-invite": return [.orgInvite(1)]
        case "org-roles": return [.orgRoles]
        case "org-numbers": return [.orgNumbers(1)]
        case "org-number-add": return [.orgNumberAdd(1)]
        case "org-withdraw": return [.orgWithdraw(1)]
        case "org-member": return [.orgTeam(1), .orgMember(org: 1, member: 3)]
        case "org-photo": return [.photo("org-1")]
        case "photo": return [.photo("me")]
        case "about": return [.about]
        default: return nil
        }
    }

    /// Captures qui se font dans l'espace prestataire.
    static let providerCaptures: Set<String> = ["provider", "request", "job"]

    /// Captures qui se font depuis l'onglet Profil.
    static let profileCaptures: Set<String> = Set(["info", "devices", "alerts", "help", "legal", "become",
                                                   "photo", "about",
                                                   PortfolioDemo.step, PortfolioDemo.profile, PortfolioDemo.locked,
                                                   "security"])
        .union(IdentityDemo.captures)
        .union(OrgDemo.profileCaptures)
}

/// La pile d'écrans d'un onglet, et ce qu'elle montre par-dessus
/// (message bref, « Bientôt dans l'app », mission en attente de devis).
@MainActor
@Observable
final class MissionFlow {
    var path: [MissionRoute] = []
    var toast: String?
    var comingSoon: SheetTitle?
    var pendingNotice: Mission?

    /// Comme l'app Flutter (`openMission`) : l'écran qui suit l'état réel.
    func open(_ mission: Mission, app: AppModel) {
        switch mission.status {
        case .pending: pendingNotice = mission
        case .quoted: path.append(.quotes(mission.id))
        case .confirmed, .inProgress, .awaitingConfirmation: path.append(.tracking(mission.id))
        case .disputed: path.append(.dispute(mission.id))
        case .completed, .cancelled: comingSoon = SheetTitle(app.place(mission))
        }
    }

    func push(_ route: MissionRoute) { path.append(route) }

    /// Revient à la racine de l'onglet, puis ouvre `route` s'il y en a une.
    func restart(at route: MissionRoute?) { path = route.map { [$0] } ?? [] }

    func say(_ text: String) { toast = text }
}

extension View {
    /// Les écrans de mission, à poser sur la racine d'une NavigationStack.
    func missionDestinations() -> some View {
        navigationDestination(for: MissionRoute.self) { route in
            MissionScreen(route: route)
        }
    }

    /// À poser sur la NavigationStack : partage `flow` avec ses écrans et
    /// affiche ses messages.
    func missionFlow(_ flow: MissionFlow, tab: AppTab) -> some View {
        modifier(MissionFlowHost(flow: flow, tab: tab))
    }
}

private struct MissionFlowHost: ViewModifier {
    @Environment(AppModel.self) private var app
    @Bindable var flow: MissionFlow
    let tab: AppTab

    func body(content: Content) -> some View {
        content
            .environment(flow)
            .onChange(of: flow.path.isEmpty, initial: true) { _, empty in
                if empty { app.openFlowTabs.remove(tab) } else { app.openFlowTabs.insert(tab) }
            }
            .sheet(item: $flow.comingSoon) { item in ComingSoonView(title: item.id) }
            .alert(flow.pendingNotice?.serviceName(app.language) ?? "",
                   isPresented: Binding(get: { flow.pendingNotice != nil },
                                        set: { if !$0 { flow.pendingNotice = nil } }),
                   presenting: flow.pendingNotice) { _ in
                Button(app.t("close"), role: .cancel) {}
            } message: { mission in
                Text([mission.commune, app.t("statusPending"), mission.detail]
                        .compactMap { $0 }.joined(separator: "\n"))
            }
            .overlay(alignment: .bottom) {
                if let text = flow.toast {
                    Toast(text: text)
                        .padding(.bottom, 96)
                        .transition(.move(edge: .bottom).combined(with: .opacity))
                }
            }
            .animation(.snappy, value: flow.toast)
            .task(id: flow.toast) {
                guard let text = flow.toast else { return }
                AccessibilityNotification.Announcement(text).post()
                try? await Task.sleep(for: .seconds(3.5))
                if flow.toast == text { flow.toast = nil }
            }
    }
}

private struct MissionScreen: View {
    let route: MissionRoute

    var body: some View {
        switch route {
        case .quotes(let id): QuotesView(missionId: id)
        case .pay(let mission, let quote): PayView(missionId: mission, quoteId: quote)
        case .pending(let mission, let quote, let via):
            PaymentPendingView(missionId: mission, quoteId: quote, mobileOperator: via)
        case .tracking(let id): TrackingView(missionId: id)
        case .confirm(let id): ConfirmView(missionId: id)
        case .report(let id): ReportView(missionId: id)
        case .dispute(let id): DisputeView(missionId: id)
        case .sendQuote(let id): SendQuoteView(missionId: id)
        case .job(let id): ProviderJobView(missionId: id)
        case .profileInfo: ProfileInfoView()
        case .devices: DevicesView()
        case .notificationSettings: NotificationSettingsView()
        case .help: HelpView()
        case .legal: LegalView()
        case .becomeProvider: BecomeProviderView()
        case .security: SecuritySettingsView()
        case .portfolio: PortfolioView()
        case .orgCreate: OrgCreateView()
        case .orgStatus(let id): OrgStatusView(orgId: id)
        case .orgInvitation(let id): OrgInvitationView(invitationId: id)
        case .orgIdentity: OrgIdentityView()
        case .orgTeam(let id): OrgTeamView(orgId: id)
        case .orgInvite(let id): OrgInviteView(orgId: id)
        case .orgRoles: OrgRolesView()
        case .orgNumbers(let id): OrgNumbersView(orgId: id)
        case .orgNumberAdd(let id): OrgNumberAddView(orgId: id)
        case .orgWithdraw(let id): OrgWithdrawView(orgId: id)
        case .orgMember(let org, let member): OrgMemberView(orgId: org, memberId: member)
        case .photo(let key): PhotoEditView(key: key)
        case .about: AboutView()
        }
    }
}

extension View {
    /// Titre court d'un écran de mission, avec le service et la commune
    /// dessous. La barre d'onglets se range : l'écran a toute la place.
    func flowTitle(_ title: String, subtitle: String? = nil) -> some View {
        self.navigationTitle(title)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar(.hidden, for: .tabBar)
            .toolbar {
                if let subtitle {
                    ToolbarItem(placement: .principal) {
                        VStack(spacing: 1) {
                            Text(title).font(.body(16, .semibold, relativeTo: .headline)).foregroundStyle(Nexis.ink)
                            Text(subtitle).font(.body(12, relativeTo: .caption1)).foregroundStyle(Nexis.muted)
                        }
                        .accessibilityElement(children: .combine)
                    }
                }
            }
            .background(Nexis.bg)
    }
}

/// Attente de lecture : les pictogrammes se relaient au milieu de l'écran.
struct FlowLoading: View {
    let label: String

    var body: some View {
        PictoLoader(size: 40, color: Nexis.accent, label: label)
            .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

// MARK: - 6. Suivi

struct TrackingView: View {
    @Environment(AppModel.self) private var app
    @Environment(MissionFlow.self) private var flow
    let missionId: Int
    @State private var mission: Mission?

    var body: some View {
        Group {
            if let mission { content(mission) } else { FlowLoading(label: app.t("trackTitle")) }
        }
        .flowTitle(app.t("trackTitle"), subtitle: mission.map(app.place))
        .task(id: app.revision) { mission = try? await app.repository.mission(missionId) }
    }

    @ViewBuilder
    private func content(_ mission: Mission) -> some View {
        let name = mission.providerFirstName
        let reached = TrackStep.allCases.filter { mission.steps[$0] != nil }
        let current = reached.last
        let sharing = mission.distanceKm != nil && current == .onTheWay
        let scroll = ScrollView {
            VStack(spacing: 14) {
                MapSketch(sharing: sharing)
                    .frame(height: 190)
                    .clipShape(RoundedRectangle(cornerRadius: 22, style: .continuous))
                    .overlay(alignment: .topLeading) {
                        Label(sharing ? app.t("distanceAway", ["name": name, "km": km(mission.distanceKm)])
                                      : app.t("trackingOff"),
                              systemImage: sharing ? "location.north.fill" : "mappin")
                            .font(.body(12.5, .semibold, relativeTo: .caption1))
                            .foregroundStyle(Nexis.navy)
                            .padding(.horizontal, 11).padding(.vertical, 6)
                            .background(.white, in: Capsule())
                            .shadow(color: Nexis.navy.opacity(0.12), radius: 2, y: 1)
                            .padding(12)
                    }
                    .accessibilityElement(children: .combine)
                if let quote = mission.chosen {
                    PersonHeader(initials: quote.initials, color: quote.avatarColor, name: quote.providerName,
                                 rating: quote.rating, reviews: quote.reviews) {
                        RoundIconButton(systemImage: "phone.fill", label: app.t("callLabel")) {
                            flow.comingSoon = SheetTitle(app.t("callLabel"))
                        }
                        RoundIconButton(systemImage: "ellipsis.message.fill", label: app.t("messageLabel")) {
                            flow.comingSoon = SheetTitle(app.t("messageLabel"))
                        }
                    }
                    .nxCard(padding: 14)
                }
                StepList(items: [
                    step(app.t("stepPaid"), sub: app.t("paySecured"), .paid, mission, current),
                    step(app.t("stepOnTheWay"), sub: sharing ? app.t("stepOnTheWaySub") : nil, .onTheWay, mission, current),
                    step(app.t("stepOnSite"), .onSite, mission, current),
                    step(app.t("stepWorkDone"), .workDone, mission, current),
                    step(app.t("stepConfirm", ["name": name]), .confirmed, mission, current),
                ])
                .nxCard()
            }
            .flowScreen()
        }
        if mission.status == .awaitingConfirmation {
            scroll.bottomActions {
                Button { flow.push(.confirm(mission.id)) } label: { WideLabel(text: app.t("confirmAction")) }
                    .nxProminentButton()
            }
        } else {
            scroll
        }
    }

    /// Comme la maquette : la dernière étape atteinte est « en cours »,
    /// celles d'avant sont faites ; la confirmation, une fois là, est faite.
    private func step(_ title: String, sub: String? = nil, _ step: TrackStep,
                      _ mission: Mission, _ current: TrackStep?) -> StepItem {
        let state: StepState = mission.steps[step] == nil ? .todo
            : (step == current && step != .confirmed ? .now : .done)
        return StepItem(title: title, sub: sub, time: mission.steps[step].map(app.clock), state: state)
    }

    private func km(_ value: Double?) -> String {
        guard let value else { return "" }
        let text = String(format: "%.1f", value)
        return app.language == "en" ? text : text.replacingOccurrences(of: ".", with: ",")
    }
}

/// Le petit plan de la maquette, dessiné (la vraie carte viendra avec le
/// suivi en direct). Il reste clair dans les deux thèmes, comme une carte.
struct MapSketch: View {
    let sharing: Bool

    var body: some View {
        Canvas { context, size in
            let scale = max(size.width / 350, size.height / 190)
            context.translateBy(x: (size.width - 350 * scale) / 2, y: (size.height - 190 * scale) / 2)
            context.scaleBy(x: scale, y: scale)
            context.fill(Path(CGRect(x: 0, y: 0, width: 350, height: 190)), with: .color(Color(hex: 0xEAF1F8)))
            var river = Path()
            river.move(to: CGPoint(x: -10, y: 150))
            river.addCurve(to: CGPoint(x: 160, y: 160), control1: CGPoint(x: 60, y: 140), control2: CGPoint(x: 90, y: 170))
            river.addCurve(to: CGPoint(x: 360, y: 130), control1: CGPoint(x: 230, y: 150), control2: CGPoint(x: 280, y: 120))
            context.stroke(river, with: .color(Color(hex: 0xCFE3F5)), style: StrokeStyle(lineWidth: 16, lineCap: .round))
            let big: [[CGFloat]] = [[-10, 40, 360, 70], [40, -10, 70, 200], [150, -10, 170, 200],
                                    [260, -10, 240, 200], [-10, 110, 360, 100]]
            for l in big {
                context.stroke(Self.road(l), with: .color(.white), style: Self.round(9))
            }
            let small: [[CGFloat]] = [[100, -10, 115, 200], [-10, 75, 360, 88], [205, -10, 205, 200], [310, -10, 300, 200]]
            for l in small {
                context.stroke(Self.road(l), with: .color(.white), style: StrokeStyle(lineWidth: 4, lineCap: .butt))
            }
            let park = Color(hex: 0xDDEBD6)
            context.fill(Path(roundedRect: CGRect(x: 210, y: 16, width: 42, height: 40), cornerRadius: 6), with: .color(park))
            context.fill(Path(roundedRect: CGRect(x: 76, y: 118, width: 30, height: 26), cornerRadius: 6), with: .color(park))
            if sharing {
                context.stroke(Self.route([CGPoint(x: 62, y: 128), CGPoint(x: 58, y: 104), CGPoint(x: 160, y: 98),
                                           CGPoint(x: 166, y: 70), CGPoint(x: 250, y: 64)]),
                               with: .color(Nexis.brand), style: Self.round(5))
                context.stroke(Self.route([CGPoint(x: 62, y: 128), CGPoint(x: 58, y: 104), CGPoint(x: 120, y: 100)]),
                               with: .color(Color(hex: 0x9FC2F7)), style: Self.round(5))
            }
            // Chez le client.
            context.fill(Path(ellipseIn: CGRect(x: 238, y: 52, width: 24, height: 24)), with: .color(Nexis.navy))
            context.fill(Path(ellipseIn: CGRect(x: 245.5, y: 59.5, width: 9, height: 9)), with: .color(.white))
            if sharing {
                // Le prestataire, en route.
                context.fill(Path(ellipseIn: CGRect(x: 104, y: 84, width: 32, height: 32)), with: .color(Nexis.brand.opacity(0.15)))
                context.fill(Path(ellipseIn: CGRect(x: 111, y: 91, width: 18, height: 18)), with: .color(Nexis.brand))
                context.stroke(Path(ellipseIn: CGRect(x: 111, y: 91, width: 18, height: 18)), with: .color(.white), lineWidth: 3)
            }
        }
        .accessibilityHidden(true)
    }

    private static func road(_ l: [CGFloat]) -> Path {
        route([CGPoint(x: l[0], y: l[1]), CGPoint(x: l[2], y: l[3])])
    }

    private static func route(_ points: [CGPoint]) -> Path {
        var path = Path()
        path.addLines(points)
        return path
    }

    private static func round(_ width: CGFloat) -> StrokeStyle {
        StrokeStyle(lineWidth: width, lineCap: .round, lineJoin: .round)
    }
}

// MARK: - 3. Comparer les devis

struct QuotesView: View {
    @Environment(AppModel.self) private var app
    @Environment(MissionFlow.self) private var flow
    let missionId: Int
    @State private var mission: Mission?
    @State private var quotes: [Quote] = []
    @State private var showcases: [Int: ProviderShowcase] = [:]
    @State private var shown: ShownShowcase?

    var body: some View {
        Group {
            if let mission {
                ScrollView {
                    VStack(alignment: .leading, spacing: 16) {
                        WrapLayout {
                            if let wanted = mission.wanted {
                                Pill(tone: .wait, systemImage: "calendar", text: wanted)
                            }
                            Pill(tone: .wait, systemImage: "mappin",
                                 text: ([mission.commune] + [mission.detail].compactMap { $0 }).joined(separator: ", "))
                        }
                        ForEach(Array(quotes.enumerated()), id: \.element.id) { index, quote in
                            QuoteCard(quote: quote, best: index == 0 && quotes.count > 1,
                                      onShowcase: showcases[quote.id].map { showcase -> () -> Void in
                                          { shown = ShownShowcase(quote: quote, showcase: showcase) }
                                      }) {
                                flow.push(.pay(mission: mission.id, quote: quote.id))
                            }
                        }
                        InfoNote(text: app.t("securedUntilDone"), systemImage: "lock.shield.fill")
                    }
                    .flowScreen()
                    .padding(.top, 4)
                }
            } else {
                FlowLoading(label: app.t("compareQuotes"))
            }
        }
        .flowTitle(app.t("compareQuotes"), subtitle: mission.map(app.place))
        .sheet(item: $shown) { item in ShowcaseView(quote: item.quote, showcase: item.showcase) }
        .task(id: app.revision) {
            mission = try? await app.repository.mission(missionId)
            quotes = (try? await app.repository.quotes(missionId: missionId)) ?? []
            var found: [Int: ProviderShowcase] = [:]
            for quote in quotes {
                if let showcase = try? await app.repository.providerShowcase(quoteId: quote.id) { found[quote.id] = showcase }
            }
            showcases = found
            if app.capture == ShowcaseDemo.capture, shown == nil, let quote = quotes.first(where: { found[$0.id] != nil }),
               let showcase = found[quote.id] {
                shown = ShownShowcase(quote: quote, showcase: showcase)
            }
        }
    }
}

private struct ShownShowcase: Identifiable {
    let quote: Quote
    let showcase: ProviderShowcase
    var id: Int { quote.id }
}

/// Capture de la CI : les réalisations de Prisca, ouvertes depuis les devis.
enum ShowcaseDemo {
    static let capture = "showcase"
}

private struct QuoteCard: View {
    @Environment(AppModel.self) private var app
    let quote: Quote
    let best: Bool
    var onShowcase: (() -> Void)?
    let onChoose: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            PersonHeader(initials: quote.initials, color: quote.avatarColor, name: quote.providerName,
                         rating: quote.rating, reviews: quote.reviews) {
                VStack(alignment: .trailing, spacing: 2) {
                    Text(app.money(quote.price))
                        .font(.title(16, .semibold, relativeTo: .headline))
                        .foregroundStyle(Nexis.ink)
                        .monospacedDigit()
                    Text(app.slot(quote.slot, capital: true))
                        .font(.body(12.5, relativeTo: .caption1))
                        .foregroundStyle(Nexis.muted)
                }
            }
            if let onShowcase {
                Button(action: onShowcase) {
                    Label(app.t("showcaseOpen"), systemImage: "photo.on.rectangle")
                        .font(.body(14, .semibold))
                        .foregroundStyle(Nexis.accent)
                }
                .buttonStyle(.plain)
            }
            if best {
                Button(action: onChoose) { WideLabel(text: app.t("chooseProvider", ["name": quote.firstName])) }
                    .nxProminentButton()
            } else {
                Button(action: onChoose) { WideLabel(text: app.t("chooseProvider", ["name": quote.firstName])) }
                    .nxSecondaryButton()
            }
        }
        .padding(16)
        .background(Nexis.surface, in: RoundedRectangle(cornerRadius: 22, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 22, style: .continuous)
            .strokeBorder(best ? Nexis.brand : Nexis.line, lineWidth: best ? 2 : 0.5))
        .overlay(alignment: .topLeading) {
            if best {
                Text(app.t("bestRated"))
                    .font(.body(11, .bold, relativeTo: .caption2))
                    .foregroundStyle(.white)
                    .padding(.horizontal, 9).padding(.vertical, 3)
                    .background(Nexis.brand, in: Capsule())
                    .offset(x: 14, y: -10)
            }
        }
        .padding(.top, best ? 6 : 0)
    }
}

/// Les réalisations approuvées par l'équipe, vues par le client. Jamais les
/// diplômes : seulement « Diplôme vérifié par NexisHub ».
private struct ShowcaseView: View {
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    let quote: Quote
    let showcase: ProviderShowcase
    @State private var catalog: [CatalogService] = []

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 14) {
                    PersonHeader(initials: quote.initials, color: quote.avatarColor, name: quote.providerName,
                                 rating: quote.rating, reviews: quote.reviews) { EmptyView() }
                    WrapLayout {
                        Pill(tone: .secured, systemImage: "checkmark.shield.fill", text: app.t("showcaseChecked"))
                        if showcase.certificateVerified {
                            Pill(tone: .ok, systemImage: "checkmark.seal.fill", text: app.t("showcaseCertificate"))
                        }
                    }
                    ForEach(showcase.works, id: \.serviceId) { work in
                        VStack(alignment: .leading, spacing: 10) {
                            HStack(spacing: 10) {
                                if let service = catalog.first(where: { $0.id == work.serviceId }) {
                                    ServiceTile(service, size: 34)
                                    Text(service.name(app.language)).font(.body(15.5, .bold)).foregroundStyle(Nexis.ink)
                                }
                            }
                            ScrollView(.horizontal, showsIndicators: false) {
                                HStack(spacing: 8) {
                                    ForEach(Array(work.photos.enumerated()), id: \.offset) { _, data in
                                        if let image = UIImage(data: data) {
                                            Image(uiImage: image).resizable().scaledToFill()
                                                .frame(width: 168, height: 168)
                                                .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
                                                .accessibilityLabel(app.t("showcasePhoto"))
                                        }
                                    }
                                }
                            }
                            if !work.note.isEmpty {
                                Text(work.note).font(.body(14.5)).foregroundStyle(Nexis.ink)
                            }
                        }
                        .nxCard(padding: 14)
                    }
                }
                .flowScreen()
            }
            .navigationTitle(app.t("showcaseTitle", ["name": quote.firstName]))
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button(app.t("close")) { dismiss() }
                }
            }
        }
        .task { catalog = (try? await app.repository.serviceCatalog()) ?? [] }
    }
}

// MARK: - 4. Payer

struct PayView: View {
    @Environment(AppModel.self) private var app
    @Environment(MissionFlow.self) private var flow
    let missionId: Int
    let quoteId: Int
    @State private var mission: Mission?
    @State private var quote: Quote?
    @State private var accounts: [PayAccount] = []
    @State private var picked: MobileOperator?

    var body: some View {
        Group {
            if let mission, let quote { content(mission, quote) } else { FlowLoading(label: app.t("payTitle")) }
        }
        .flowTitle(app.t("payTitle"))
        .task(id: app.revision) {
            mission = try? await app.repository.mission(missionId)
            quote = (try? await app.repository.quotes(missionId: missionId))?.first { $0.id == quoteId }
            accounts = (try? await app.repository.payAccounts()) ?? []
        }
    }

    private func content(_ mission: Mission, _ quote: Quote) -> some View {
        let chosen = picked ?? accounts.first { $0.maskedNumber != nil }?.mobileOperator
        let amount = app.money(quote.price)
        return ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                VStack(spacing: 6) {
                    ServiceTile(mission, size: 54)
                    Text(app.place(mission))
                        .font(.body(15.5, .bold)).foregroundStyle(Nexis.ink).padding(.top, 6)
                    Text("\(quote.providerName) · \(app.slot(quote.slot))")
                        .font(.body(13.5, relativeTo: .footnote)).foregroundStyle(Nexis.muted)
                    Text(amount)
                        .font(.title(30, .semibold, relativeTo: .largeTitle))
                        .foregroundStyle(Nexis.accent)
                        .monospacedDigit()
                        .minimumScaleFactor(0.6)
                        .lineLimit(1)
                        .padding(.top, 4)
                }
                .frame(maxWidth: .infinity)
                .nxCard(padding: 20)
                .accessibilityElement(children: .combine)
                Text(app.t("payWith"))
                    .font(.body(16, .semibold, relativeTo: .headline)).foregroundStyle(Nexis.ink)
                    .padding(.top, 4)
                ForEach(accounts, id: \.mobileOperator) { account in
                    ChoiceRow(title: account.mobileOperator.displayName,
                              subtitle: account.maskedNumber ?? app.t("addNumber"),
                              selected: account.mobileOperator == chosen) {
                        OperatorBadge(mobileOperator: account.mobileOperator)
                    } action: {
                        if account.maskedNumber == nil {
                            flow.comingSoon = SheetTitle(app.t("addNumber"))
                        } else {
                            picked = account.mobileOperator
                        }
                    }
                }
                InfoNote(text: app.t("paySecuredNote", ["name": quote.firstName]), systemImage: "lock.shield.fill")
            }
            .flowScreen()
        }
        .bottomActions {
            Button {
                guard let chosen else { return }
                // Le code ou Face ID d'abord : sans lui, rien ne part.
                Task {
                    if await app.confirmMoneyOut(app.t("guardPay", ["amount": amount, "name": quote.firstName])) {
                        flow.push(.pending(mission: mission.id, quote: quote.id, via: chosen))
                    }
                }
            } label: {
                WideLabel(text: app.t("payAmount", ["amount": amount]))
            }
            .nxProminentButton()
            .disabled(chosen == nil)
        }
    }
}

// MARK: - En attente de l'opérateur

/// L'app attend la réponse réelle de l'opérateur ; quand il a confirmé,
/// on passe au suivi de la mission.
struct PaymentPendingView: View {
    @Environment(AppModel.self) private var app
    @Environment(MissionFlow.self) private var flow
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    let missionId: Int
    let quoteId: Int
    let mobileOperator: MobileOperator
    @State private var quote: Quote?
    @State private var failed = false
    @State private var started = false
    @State private var pulse = false
    @State private var sentAt = Date.now

    var body: some View {
        ScrollView {
            VStack(spacing: 16) {
                ZStack {
                    Circle().fill(RadialGradient(colors: [Nexis.halo.opacity(0.22), Nexis.halo.opacity(0)],
                                                 center: .center, startRadius: 0, endRadius: 90))
                    Circle()
                        .fill(Nexis.halo.opacity(0.10))
                        .overlay(Circle().strokeBorder(Nexis.halo.opacity(0.25), lineWidth: 1.5))
                        .padding(28)
                        .scaleEffect(pulse ? 1.08 : 0.94)
                        .opacity(pulse ? 0.6 : 1)
                    RoundedRectangle(cornerRadius: 28, style: .continuous)
                        .fill(Nexis.heroGradient)
                        .frame(width: 84, height: 84)
                        .shadow(color: Nexis.gradientEnd.opacity(0.45), radius: 18, y: 12)
                        .overlay(Image(systemName: "iphone.gen3").font(.system(size: 36)).foregroundStyle(.white))
                }
                .frame(width: 180, height: 180)
                .accessibilityHidden(true)
                Text(app.t("pendingTitle"))
                    .font(.title(21)).foregroundStyle(Nexis.ink).multilineTextAlignment(.center)
                Text(failed ? app.t("actionFailed")
                            : app.t("pendingText", ["operator": mobileOperator.displayName,
                                                    "amount": quote.map { app.money($0.price) } ?? ""]))
                    .font(.body(15)).foregroundStyle(failed ? Nexis.danger : Nexis.muted)
                    .multilineTextAlignment(.center).lineSpacing(3)
                StepList(items: [
                    StepItem(title: app.t("pendingSent", ["operator": mobileOperator.displayName]),
                             time: app.clock(sentAt), state: .done),
                    StepItem(title: app.t("pendingWaiting"), sub: app.t("pendingWithin"), state: .now),
                    StepItem(title: app.t("pendingSecured"),
                             sub: app.t("pendingNotify", ["name": quote?.firstName ?? ""]), state: .todo),
                ])
                .nxCard()
            }
            .flowScreen()
        }
        .bottomActions {
            Button { flow.comingSoon = SheetTitle(app.t("nothingReceived")) } label: {
                Text(app.t("nothingReceived")).font(.body(16, .semibold))
            }
            .buttonStyle(OutlineButtonStyle())
        }
        .flowTitle(app.t("paymentTitle"))
        .navigationBarBackButtonHidden(!failed)
        .onAppear {
            guard !reduceMotion else { return }
            withAnimation(.easeInOut(duration: 1.2).repeatForever(autoreverses: true)) { pulse = true }
        }
        .task {
            quote = (try? await app.repository.quotes(missionId: missionId))?.first { $0.id == quoteId }
            // Un seul envoi par écran ; la capture de la CI montre l'attente.
            guard !started, app.capture != "pending" else { return }
            started = true
            sentAt = .now
            do {
                let paid = try await app.repository.pay(missionId: missionId, quoteId: quoteId,
                                                        mobileOperator: mobileOperator)
                app.dataChanged()
                flow.restart(at: .tracking(paid.id))
            } catch {
                failed = true
            }
        }
    }
}

// MARK: - 7. Confirmer que c'est fait

struct ConfirmView: View {
    @Environment(AppModel.self) private var app
    @Environment(MissionFlow.self) private var flow
    let missionId: Int
    @State private var mission: Mission?
    @State private var busy = false

    var body: some View {
        Group {
            if let mission { content(mission) } else { FlowLoading(label: app.t("confirmAction")) }
        }
        .flowTitle(app.t("confirmAction"))
        .task(id: app.revision) { if !busy { mission = try? await app.repository.mission(missionId) } }
    }

    private func content(_ mission: Mission) -> some View {
        let name = mission.providerFirstName
        return ScrollView {
            VStack(spacing: 16) {
                VStack(spacing: 8) {
                    ServiceTile(mission, size: 56)
                        .frame(width: 88, height: 88)
                        .background(Circle().fill(Nexis.soft))
                        .background(Circle().fill(Color(light: 0xF1F6FE, dark: 0x121E33)).padding(-10))
                        .padding(.vertical, 12)
                    Text(app.t("confirmQuestion", ["name": name]))
                        .font(.title(20)).foregroundStyle(Nexis.ink)
                        .multilineTextAlignment(.center).lineSpacing(4)
                    Text(app.t("confirmText", ["name": name]))
                        .font(.body(14.5)).foregroundStyle(Nexis.muted)
                        .multilineTextAlignment(.center).lineSpacing(3)
                }
                VStack(alignment: .leading, spacing: 10) {
                    HStack {
                        Text(app.place(mission)).font(.body(14)).foregroundStyle(Nexis.muted)
                        Spacer()
                        if let slot = mission.chosen?.slot {
                            Text(app.slot(slot)).font(.body(14, .semibold)).foregroundStyle(Nexis.ink)
                        }
                    }
                    Divider()
                    HStack {
                        Text(app.t("paidTo", ["name": name])).font(.body(16, .bold)).foregroundStyle(Nexis.ink)
                        Spacer()
                        if let amount = mission.amount {
                            Text(app.money(amount)).font(.title(16, .semibold)).foregroundStyle(Nexis.accent)
                                .monospacedDigit()
                        }
                    }
                    Label(app.t("amountFixed"), systemImage: "checkmark.shield.fill")
                        .font(.body(12.5, relativeTo: .caption1)).foregroundStyle(Nexis.muted)
                }
                .nxCard()
                .accessibilityElement(children: .combine)
                InfoNote(text: app.t("report48h"), kind: .violet)
            }
            .flowScreen()
        }
        .bottomActions {
            Button {
                // Verser l'argent au prestataire : le code ou Face ID d'abord.
                Task {
                    if await app.confirmMoneyOut(app.t("guardRelease", ["name": name])) { await confirm(mission, name) }
                }
            } label: {
                BusyLabel(text: app.t("yesDone"), systemImage: "checkmark", busy: busy)
            }
            .nxProminentButton()
            .disabled(busy)
            Button { flow.push(.report(mission.id)) } label: {
                Text(app.t("reportProblem")).font(.body(16, .semibold))
            }
            .buttonStyle(OutlineButtonStyle())
            .disabled(busy)
        }
    }

    private func confirm(_ mission: Mission, _ name: String) async {
        busy = true
        do {
            _ = try await app.repository.confirmDone(missionId: mission.id)
            app.dataChanged()
            flow.restart(at: nil)
            flow.say(app.t("confirmedToast", ["name": name]))
        } catch {
            busy = false
            flow.say(app.t("actionFailed"))
        }
    }
}

// MARK: - 25. Signaler un problème

extension AppModel {
    func reasonText(_ reason: DisputeReason) -> String {
        switch reason {
        case .notFinished: return t("reasonNotFinished")
        case .badWork: return t("reasonBadWork")
        case .noShow: return t("reasonNoShow")
        case .other: return t("reasonOther")
        }
    }
}

struct ReportView: View {
    @Environment(AppModel.self) private var app
    @Environment(MissionFlow.self) private var flow
    let missionId: Int
    @State private var mission: Mission?
    @State private var reason: DisputeReason?
    @State private var text = ""
    @State private var busy = false
    @FocusState private var writing: Bool

    private static let maxLength = 500

    var body: some View {
        Group {
            if let mission { content(mission) } else { FlowLoading(label: app.t("reportProblem")) }
        }
        .flowTitle(app.t("reportProblem"), subtitle: mission.map(app.place))
        .task(id: app.revision) { if !busy { mission = try? await app.repository.mission(missionId) } }
    }

    private func content(_ mission: Mission) -> some View {
        let ready = reason != nil && !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
        return ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                Text(app.t("whatHappened"))
                    .font(.body(16, .semibold, relativeTo: .headline)).foregroundStyle(Nexis.ink)
                ForEach(DisputeReason.allCases, id: \.self) { item in
                    ChoiceRow(title: app.reasonText(item), selected: reason == item) {
                        EmptyView()
                    } action: {
                        reason = item
                    }
                    .disabled(busy)
                }
                TextField(app.t("reportHint"), text: $text, axis: .vertical)
                    .font(.body(15))
                    .lineLimit(3...6)
                    .focused($writing)
                    .disabled(busy)
                    .padding(14)
                    .background(Nexis.surface, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
                    .overlay(RoundedRectangle(cornerRadius: 16, style: .continuous)
                        .strokeBorder(writing ? Nexis.brand : Nexis.line, lineWidth: writing ? 2 : 1))
                    .onChange(of: text) { _, value in
                        if value.count > Self.maxLength { text = String(value.prefix(Self.maxLength)) }
                    }
                HStack(spacing: 10) {
                    PhotoSlot(systemImage: "camera", label: app.t("addPhoto")) {
                        flow.comingSoon = SheetTitle(app.t("addPhoto"))
                    }
                    PhotoSlot(systemImage: "photo", label: app.t("addPhoto")) {
                        flow.comingSoon = SheetTitle(app.t("addPhoto"))
                    }
                }
                if let amount = mission.amount {
                    InfoNote(text: app.t("reportFrozen", ["amount": app.money(amount)]),
                             kind: .danger, systemImage: "lock.fill")
                }
            }
            .flowScreen()
        }
        .scrollDismissesKeyboard(.interactively)
        .bottomActions {
            Button { Task { await send() } } label: {
                BusyLabel(text: app.t("sendReport"), busy: busy)
            }
            .nxProminentButton()
            .disabled(!ready || busy)
        }
    }

    private func send() async {
        guard let reason else { return }
        busy = true
        writing = false
        do {
            _ = try await app.repository.reportProblem(missionId: missionId, reason: reason, text: text)
            app.dataChanged()
            flow.restart(at: .dispute(missionId))
        } catch {
            busy = false
            flow.say(app.t("reportFailed"))
        }
    }
}

// MARK: - 26 et 27. Litige

struct DisputeView: View {
    @Environment(AppModel.self) private var app
    let missionId: Int
    @State private var mission: Mission?
    @State private var dispute: Dispute?
    @State private var loaded = false

    var body: some View {
        Group {
            if let mission, loaded {
                if let dispute {
                    if dispute.decided {
                        DisputeDecisionView(mission: mission, dispute: dispute)
                    } else {
                        DisputeOpenView(mission: mission, dispute: dispute)
                    }
                } else {
                    Color.clear.flowTitle(app.t("disputeTitle"))
                }
            } else {
                FlowLoading(label: app.t("disputeTitle")).flowTitle(app.t("disputeTitle"))
            }
        }
        .task(id: app.revision) {
            mission = try? await app.repository.mission(missionId)
            dispute = try? await app.repository.dispute(missionId: missionId)
            loaded = true
        }
    }
}

private struct DisputeOpenView: View {
    @Environment(AppModel.self) private var app
    @Environment(MissionFlow.self) private var flow
    let mission: Mission
    let dispute: Dispute

    var body: some View {
        let name = mission.providerFirstName
        ScrollView {
            VStack(spacing: 14) {
                if let amount = mission.amount {
                    HStack(spacing: 12) {
                        Image(systemName: "lock.fill")
                            .font(.system(size: 17, weight: .semibold))
                            .foregroundStyle(Color(hex: 0xA1261B))
                            .frame(width: 44, height: 44)
                            .background(Circle().fill(Color(light: 0xFDE8E6, dark: 0x3A1715)))
                        VStack(alignment: .leading, spacing: 2) {
                            Text(app.money(amount)).font(.title(16, .semibold)).foregroundStyle(Nexis.ink)
                                .monospacedDigit()
                            Text(app.t("nobodyTouches"))
                                .font(.body(13, relativeTo: .footnote))
                                .foregroundStyle(Color(light: 0x7A3A33, dark: 0xFFB4AB))
                        }
                        Spacer(minLength: 8)
                        PaymentPill(state: .blocked)
                    }
                    .padding(14)
                    .background(Color(light: 0xFFF6F5, dark: 0x2A1513), in: RoundedRectangle(cornerRadius: 20, style: .continuous))
                    .overlay(RoundedRectangle(cornerRadius: 20, style: .continuous)
                        .strokeBorder(Color(light: 0xF6D3CF, dark: 0x5A2A25), lineWidth: 1))
                    .accessibilityElement(children: .combine)
                }
                StepList(items: steps(name)).nxCard()
                InfoNote(text: app.t("settleHint", ["name": name]), kind: .violet)
            }
            .flowScreen()
        }
        .bottomActions {
            Button { flow.comingSoon = SheetTitle(app.t("writeNexis")) } label: {
                WideLabel(text: app.t("writeNexis"), systemImage: "bubble.left.and.bubble.right")
            }
            .nxProminentButton()
            Button { flow.comingSoon = SheetTitle(app.t("weSettled")) } label: {
                Text(app.t("weSettled")).font(.body(16, .semibold))
            }
            .buttonStyle(OutlineButtonStyle())
        }
        .flowTitle(app.t("disputeTitle"), subtitle: app.place(mission))
    }

    private func steps(_ name: String) -> [StepItem] {
        var items = [StepItem(title: app.t("youReported"),
                              sub: "\(app.reasonText(dispute.reason)) · \(app.plural("photosCount", count: dispute.photos))",
                              time: app.stamp(dispute.openedAt), state: .done)]
        if let reply = dispute.providerReply {
            items.append(StepItem(title: app.t("providerReplied", ["name": name]),
                                  sub: app.language == "en" ? "“\(reply)”" : "« \(reply) »",
                                  time: dispute.providerRepliedAt.map(app.stamp), state: .done))
        }
        items.append(StepItem(title: app.t("nexisLooking"), sub: app.t("nexisLookingSub"), state: .now))
        items.append(StepItem(title: app.t("decisionStep"), sub: app.t("decisionStepSub"), state: .todo))
        return items
    }
}

/// Décision : remboursé, versé au prestataire ou partagé. Les montants
/// viennent du serveur ; l'argent reste bloqué 3 jours pour contester.
private struct DisputeDecisionView: View {
    @Environment(AppModel.self) private var app
    @Environment(MissionFlow.self) private var flow
    let mission: Mission
    let dispute: Dispute

    private let violet = Color(light: 0x494C95, dark: 0xB3B5F2)

    var body: some View {
        let name = mission.providerFirstName
        let outcome = dispute.outcome ?? .refund
        let left = dispute.contestUntil.map { daysLeft(until: $0) } ?? 0
        let shown = words(outcome, name)
        ScrollView {
            VStack(spacing: 16) {
                VStack(spacing: 8) {
                    Image(systemName: shown.symbol)
                        .font(.system(size: 34, weight: .medium))
                        .foregroundStyle(violet)
                        .frame(width: 88, height: 88)
                        .background(Circle().fill(Color(light: 0xECECF8, dark: 0x22234A)))
                        .background(Circle().fill(Color(light: 0xF4F4FB, dark: 0x121E33)).padding(-10))
                        .padding(.vertical, 12)
                        .accessibilityHidden(true)
                    Text(shown.heading).font(.title(20)).foregroundStyle(Nexis.ink).multilineTextAlignment(.center)
                    Text(shown.text).font(.body(14.5)).foregroundStyle(Nexis.muted)
                        .multilineTextAlignment(.center).lineSpacing(3)
                }
                VStack(alignment: .leading, spacing: 10) {
                    HStack {
                        Text(app.place(mission)).font(.body(14)).foregroundStyle(Nexis.muted)
                        Spacer()
                        if let slot = mission.chosen?.slot {
                            Text(app.slot(slot)).font(.body(14, .semibold)).foregroundStyle(Nexis.ink)
                        }
                    }
                    Divider()
                    if outcome != .release, let client = dispute.clientAmount {
                        amountRow(app.t("toRefundYou"), client)
                    }
                    if outcome == .split, let provider = dispute.providerAmount {
                        amountRow(app.t("forProvider", ["name": name]), provider)
                    }
                    if outcome == .release, let provider = dispute.providerAmount {
                        amountRow(app.t("paidTo", ["name": name]), provider)
                    }
                    Group {
                        if left > 0 {
                            Pill(tone: .bad, systemImage: "lock.fill", text: app.plural("blockedDaysLeft", count: left))
                        } else {
                            PaymentPill(state: outcome == .release ? .released : .refunded)
                        }
                    }
                    .padding(.top, 2)
                }
                .nxCard()
                if left > 0 {
                    InfoNote(text: app.plural("contestHint", count: left), kind: .violet)
                }
            }
            .flowScreen()
        }
        .bottomActions {
            Button {
                app.requestedTab = .wallet
                flow.restart(at: nil)
            } label: {
                WideLabel(text: app.t("seeWallet"))
            }
            .nxProminentButton()
        }
        .flowTitle(app.t("disputeOver"))
    }

    private func words(_ outcome: DisputeOutcome, _ name: String) -> (symbol: String, heading: String, text: String) {
        switch outcome {
        case .refund:
            return ("arrow.counterclockwise", app.t("outcomeRefundTitle"), app.t("outcomeRefundText", ["name": name]))
        case .release:
            return ("checkmark.circle", app.t("outcomeReleaseTitle", ["name": name]),
                    app.t("outcomeReleaseText", ["name": name]))
        case .split:
            return ("scale.3d", app.t("outcomeSplitTitle"), app.t("outcomeSplitText", ["name": name]))
        }
    }

    private func amountRow(_ label: String, _ money: Money) -> some View {
        HStack {
            Text(label).font(.body(16, .bold)).foregroundStyle(Nexis.ink)
            Spacer()
            Text(app.money(money)).font(.title(16, .semibold)).foregroundStyle(violet).monospacedDigit()
        }
        .accessibilityElement(children: .combine)
    }
}
