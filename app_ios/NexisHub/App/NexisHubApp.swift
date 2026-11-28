import SwiftUI
import UIKit

@main
struct NexisHubApp: App {
    @State private var app = AppModel(repository: DemoRepository())

    init() {
        #if DEBUG
        // Captures d'écran de la CI : -capture home -language fr
        let defaults = UserDefaults.standard
        if let capture = defaults.string(forKey: "capture") {
            let repository = DemoRepository()
            repository.demoPreset(capture)
            let model = AppModel(repository: repository,
                                 security: AppSecurity(vault: MemoryCodeVault()),
                                 language: defaults.string(forKey: "language"))
            model.capture = capture
            // Espace entreprise ouvert d'emblée pour ses écrans.
            if OrgDemo.spaceCaptures.contains(capture) { model.orgSpaceId = 1 }
            if !["welcome", "phone", "code", "signup"].contains(capture) { model.signIn() }
            // Le simulateur n'a pas Face ID : les captures font comme si.
            switch capture {
            case "protect": break
            case "protect-bio":
                model.security.presetForCapture(code: "482916", biometry: .faceID, on: false)
                model.finishingProtection = true
            case "lock":
                model.security.presetForCapture(code: "482916", biometry: .faceID, on: true)
                model.locked = true
            default:
                model.security.presetForCapture(code: "482916", biometry: .faceID, on: true)
            }
            _app = State(initialValue: model)
        }
        #endif
        // Titres des barres de navigation en Unbounded, comme les maquettes.
        let bar = UINavigationBar.appearance()
        bar.largeTitleTextAttributes = [
            .font: NexisFont.ui("Unbounded", 30, .semibold, relativeTo: .largeTitle),
        ]
        bar.titleTextAttributes = [
            .font: NexisFont.ui("Unbounded", 17, .semibold, relativeTo: .headline),
        ]
    }

    var body: some Scene {
        WindowGroup {
            RootView()
                .environment(app)
                .environment(\.locale, app.locale)
                .tint(Nexis.accent)
        }
    }
}

/// Lancement, puis l'accueil ou la bienvenue selon la session. Le
/// lancement ne revient pas quand la langue ou la session change.
struct RootView: View {
    @Environment(AppModel.self) private var app
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.scenePhase) private var scenePhase
    @State private var launched = false

    var body: some View {
        ZStack {
            if app.signedIn {
                if app.needsProtection || app.finishingProtection {
                    ProtectView().transition(.opacity)
                } else {
                    // Derrière le verrou, VoiceOver ne lit rien.
                    ShellView().transition(.opacity).accessibilityHidden(app.locked || app.covered)
                }
            } else {
                WelcomeView().transition(.opacity)
            }
            if app.signedIn && app.locked {
                LockView().transition(.opacity).zIndex(2)
            }
            if app.covered {
                LaunchView().zIndex(3)
            }
            if !launched {
                LaunchView().transition(.opacity).zIndex(4)
            }
        }
        .animation(reduceMotion ? nil : .smooth(duration: 0.35), value: app.signedIn)
        .animation(reduceMotion ? nil : .smooth(duration: 0.3), value: app.locked)
        .animation(reduceMotion ? nil : .smooth(duration: 0.3), value: app.needsProtection || app.finishingProtection)
        .sheet(item: Binding(get: { app.gate }, set: { if $0 == nil { app.finishGate(false) } })) { gate in
            GateSheet(gate: gate)
        }
        .onChange(of: scenePhase) { _, phase in
            switch phase {
            case .background: app.left()
            case .active: app.came()
            default: break
            }
        }
        .task {
            if app.capture != nil { launched = true; return }
            try? await Task.sleep(for: .milliseconds(reduceMotion ? 300 : 1400))
            withAnimation(reduceMotion ? nil : .smooth(duration: 0.45)) { launched = true }
        }
    }
}

/// Prolonge l'écran de lancement du système (bleu Nexis uni) : les
/// pictogrammes des services se relaient, en blanc sur le bleu.
struct LaunchView: View {
    var body: some View {
        ZStack {
            Nexis.heroGradient.ignoresSafeArea()
            PictoLoader(size: 84, color: .white, label: "Nexis Hub")
        }
    }
}
