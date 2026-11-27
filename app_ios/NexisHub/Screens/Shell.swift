import SwiftUI

enum AppTab: Hashable {
    case home, missions, wallet, profile
}

/// Les quatre onglets dans la barre Liquid Glass du système. « Demander
/// un service » est l'action principale de l'app : sur iOS 26 et 27 elle
/// vit dans l'accessoire en verre posé au-dessus de la barre, la barre se
/// réduit quand on fait défiler ; avant iOS 26, l'accueil la porte.
struct ShellView: View {
    @Environment(AppModel.self) private var app
    @State private var tab: AppTab = .home
    @State private var picking = false

    var body: some View {
        TabView(selection: $tab) {
            Tab(app.t("navHome"), systemImage: "house", value: AppTab.home) {
                if let orgId = app.orgSpaceId {
                    OrgHomeView(orgId: orgId, onTab: { tab = $0 })
                } else if app.providerSpace {
                    ProviderHomeView(onTab: { tab = $0 })
                } else {
                    HomeView(onPickService: { picking = true }, onTab: { tab = $0 })
                }
            }
            Tab(app.t("navMissions"), systemImage: "list.bullet.clipboard", value: AppTab.missions) {
                if let orgId = app.orgSpaceId {
                    OrgMissionsView(orgId: orgId)
                } else if app.providerSpace {
                    ProviderMissionsView()
                } else {
                    MissionsView()
                }
            }
            Tab(app.t("navWallet"), systemImage: "wallet.bifold", value: AppTab.wallet) {
                if let orgId = app.orgSpaceId { OrgWalletView(orgId: orgId) } else { WalletView() }
            }
            Tab(app.t("navProfile"), systemImage: "person.crop.circle", value: AppTab.profile) {
                ProfileView()
            }
        }
        .modifier(RequestServiceAccessory(open: $picking, tab: tab))
        .onAppear {
            switch app.capture {
            case "missions": tab = .missions
            case "wallet": tab = .wallet
            case "profile": tab = .profile
            case "org-accountant": tab = .wallet
            case "org-worker": tab = .missions
            case "org-switch", "org-profile": tab = .profile
            // Écrans de l'espace entreprise : l'accueil de l'espace les ouvre.
            case let capture? where OrgDemo.spaceCaptures.contains(capture): break
            case "services": picking = true
            case let capture? where MissionRoute.profileCaptures.contains(capture): tab = .profile
            case let capture? where MissionRoute.providerCaptures.contains(capture):
                app.providerSpace = true
            case let capture? where MissionRoute.forCapture(capture) != nil: tab = .missions
            default: break
            }
        }
        // Changer d'espace ramène à son accueil.
        .onChange(of: app.providerSpace) { tab = .home }
        .onChange(of: app.orgSpaceId) { tab = .home }
        .onChange(of: app.requestedTab) { _, requested in
            guard let requested else { return }
            tab = requested
            app.requestedTab = nil
        }
        .sheet(isPresented: $picking) {
            ServicePickerView(onRequested: {
                picking = false
                tab = .missions
            })
        }
    }

    /// Vrai quand l'accessoire de la barre porte « Demander un service ».
    static var hasAccessory: Bool {
        if #available(iOS 26.0, *) { return true }
        return false
    }
}

private struct RequestServiceAccessory: ViewModifier {
    @Environment(AppModel.self) private var app
    @Binding var open: Bool
    let tab: AppTab

    /// Côté prestataire, rien à demander ; dans un écran de mission (paiement,
    /// suivi…), l'accessoire se range avec la barre d'onglets.
    private var shown: Bool {
        !app.providerSpace && app.orgSpaceId == nil && !app.openFlowTabs.contains(tab)
    }

    func body(content: Content) -> some View {
        if #available(iOS 26.1, *) {
            content
                .tabBarMinimizeBehavior(.onScrollDown)
                .tabViewBottomAccessory(isEnabled: shown) { button }
        } else if #available(iOS 26.0, *) {
            if app.providerSpace || app.orgSpaceId != nil {
                content.tabBarMinimizeBehavior(.onScrollDown)
            } else {
                content
                    .tabBarMinimizeBehavior(.onScrollDown)
                    .tabViewBottomAccessory { button }
            }
        } else {
            content
        }
    }

    private var button: some View {
        Button { open = true } label: {
            Label(app.t("requestService"), systemImage: "plus")
                .font(.body(15, .semibold, relativeTo: .subheadline))
                .foregroundStyle(Nexis.accent)
                .frame(maxWidth: .infinity)
        }
    }
}
