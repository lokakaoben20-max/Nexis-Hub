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
            let model = AppModel(repository: DemoRepository(),
                                 language: defaults.string(forKey: "language"))
            model.capture = capture
            if !["welcome", "phone", "code", "signup"].contains(capture) { model.signIn() }
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
    @State private var launched = false

    var body: some View {
        ZStack {
            if app.signedIn {
                ShellView().transition(.opacity)
            } else {
                WelcomeView().transition(.opacity)
            }
            if !launched {
                LaunchView().transition(.opacity).zIndex(1)
            }
        }
        .animation(reduceMotion ? nil : .smooth(duration: 0.35), value: app.signedIn)
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
