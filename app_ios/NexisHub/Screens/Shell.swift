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
                HomeView(onPickService: { picking = true }, onTab: { tab = $0 })
            }
            Tab(app.t("navMissions"), systemImage: "list.bullet.clipboard", value: AppTab.missions) {
                MissionsView()
            }
            Tab(app.t("navWallet"), systemImage: "wallet.bifold", value: AppTab.wallet) {
                WalletView()
            }
            Tab(app.t("navProfile"), systemImage: "person.crop.circle", value: AppTab.profile) {
                ProfileView()
            }
        }
        .modifier(RequestServiceAccessory(open: $picking))
        .onAppear {
            switch app.capture {
            case "missions": tab = .missions
            case "wallet": tab = .wallet
            case "profile": tab = .profile
            case "services": picking = true
            default: break
            }
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

    func body(content: Content) -> some View {
        if #available(iOS 26.0, *) {
            content
                .tabBarMinimizeBehavior(.onScrollDown)
                .tabViewBottomAccessory {
                    Button { open = true } label: {
                        Label(app.t("requestService"), systemImage: "plus")
                            .font(.body(15, .semibold, relativeTo: .subheadline))
                            .foregroundStyle(Nexis.accent)
                            .frame(maxWidth: .infinity)
                    }
                }
        } else {
            content
        }
    }
}
