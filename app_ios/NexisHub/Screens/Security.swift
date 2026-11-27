import SwiftUI

// Code NexisHub et Face ID / Touch ID : création juste après l'inscription
// (ou la connexion sur un nouveau téléphone), verrou à l'ouverture, et
// confirmation avant chaque sortie d'argent. C'est le téléphone qui
// reconnaît la personne : l'app ne reçoit qu'un oui ou un non.

// MARK: - Création du code

struct ProtectView: View {
    @Environment(AppModel.self) private var app
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    private enum Phase { case create, confirm, biometrics, done }

    @State private var phase: Phase = .create
    @State private var first = ""
    @State private var entry = ""
    @State private var message: String?
    @State private var shakes = 0
    @State private var enabling = false

    var body: some View {
        ZStack {
            Nexis.bg.ignoresSafeArea()
            switch phase {
            case .create, .confirm: codeStep
            case .biometrics: biometricsStep
            case .done: doneStep
            }
        }
        .onAppear {
            // Code déjà créé (capture de la CI) : on reprend à Face ID.
            if app.security.hasCode { phase = app.security.biometry == .none ? .done : .biometrics }
        }
        .task(id: phase) {
            guard phase == .done else { return }
            AccessibilityNotification.Announcement(app.t("protectDone")).post()
            try? await Task.sleep(for: .seconds(1.2))
            app.finishingProtection = false
        }
    }

    private var codeStep: some View {
        VStack(spacing: 0) {
            CodeHeader(symbol: "lock.shield",
                       title: app.t(phase == .create ? "protectTitle" : "protectConfirmTitle"),
                       text: app.t(phase == .create ? "protectIntro" : "protectConfirmIntro"))
                .padding(.top, 28)
            CodeDots(filled: entry.count, failed: message != nil && entry.isEmpty)
                .modifier(Shake(animatableData: CGFloat(shakes)))
                .padding(.top, 28)
            CodeMessage(text: message)
            Spacer(minLength: 12)
            if phase == .create {
                Text(app.t("protectAdvice"))
                    .font(.body(13, relativeTo: .footnote))
                    .foregroundStyle(Nexis.muted)
                    .multilineTextAlignment(.center)
                    .fixedSize(horizontal: false, vertical: true)
                    .padding(.horizontal, 28)
                    .padding(.bottom, 18)
            }
            CodePad(entry: $entry, onComplete: typed)
                .padding(.bottom, 20)
        }
        .padding(.horizontal, 20)
    }

    private var biometricsStep: some View {
        let name = app.security.biometryName
        return VStack(spacing: 0) {
            Spacer()
            Image(systemName: app.security.biometrySymbol)
                .font(.system(size: 56, weight: .light))
                .foregroundStyle(Nexis.brand)
                .frame(width: 112, height: 112)
                .background(Nexis.soft, in: RoundedRectangle(cornerRadius: 32, style: .continuous))
                .accessibilityHidden(true)
            Text(app.t("protectBioTitle", ["method": name]))
                .font(.title(26, .semibold, relativeTo: .title1))
                .foregroundStyle(Nexis.ink)
                .multilineTextAlignment(.center)
                .accessibilityAddTraits(.isHeader)
                .padding(.top, 28)
            Text(app.t("protectBioText"))
                .font(.body(15))
                .foregroundStyle(Nexis.muted)
                .multilineTextAlignment(.center)
                .lineSpacing(3)
                .fixedSize(horizontal: false, vertical: true)
                .padding(.top, 12)
            Spacer()
            VStack(spacing: 12) {
                Button {
                    enabling = true
                    Task {
                        _ = await app.security.enableBiometrics(reason: app.t("protectBioTitle", ["method": name]),
                                                                fallback: app.t("lockUseCode"))
                        enabling = false
                        phase = .done
                    }
                } label: {
                    BusyLabel(text: app.t("protectBioOn", ["method": name]), systemImage: app.security.biometrySymbol, busy: enabling)
                }
                .nxProminentButton()
                .disabled(enabling)
                Button(app.t("protectBioLater")) { phase = .done }
                    .font(.body(16, .semibold))
                    .tint(Nexis.accent)
                    .frame(minHeight: 44)
                    .disabled(enabling)
            }
            .padding(.bottom, 16)
        }
        .padding(.horizontal, 24)
    }

    private var doneStep: some View {
        VStack(spacing: 18) {
            Image(systemName: "checkmark.shield.fill")
                .font(.system(size: 64))
                .foregroundStyle(Nexis.ok)
                .accessibilityHidden(true)
            Text(app.t("protectDone"))
                .font(.title(22, .semibold, relativeTo: .title2))
                .foregroundStyle(Nexis.ink)
                .multilineTextAlignment(.center)
        }
        .padding(24)
    }

    private func typed(_ code: String) {
        entry = ""
        switch phase {
        case .create:
            if CodeRules.isWeak(code) {
                refuse(app.t("protectWeak"))
            } else {
                first = code
                message = nil
                phase = .confirm
            }
        case .confirm:
            if code == first {
                app.finishingProtection = true
                app.security.setCode(code)
                first = ""
                message = nil
                phase = app.security.biometry == .none ? .done : .biometrics
            } else {
                first = ""
                phase = .create
                refuse(app.t("protectMismatch"))
            }
        default:
            break
        }
    }

    private func refuse(_ text: String) {
        message = text
        withAnimation(reduceMotion ? nil : .linear(duration: 0.4)) { shakes += 1 }
    }
}

// MARK: - Verrou

/// Posé sur toute l'app quand elle revient après au moins une minute.
struct LockView: View {
    @Environment(AppModel.self) private var app
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var profile: Profile?
    @State private var entry = ""
    @State private var message: String?
    @State private var shakes = 0
    @State private var forgot = false
    @State private var blocked = false

    var body: some View {
        let security = app.security
        VStack(spacing: 0) {
            VStack(spacing: 10) {
                InitialsAvatar(initials: profile?.initials ?? "", size: 64, photoKey: "me")
                Text(profile.map { app.t("hello", ["name": $0.firstName]) } ?? "NexisHub")
                    .font(.title(24, .semibold, relativeTo: .title1))
                    .foregroundStyle(Nexis.ink)
                    .accessibilityAddTraits(.isHeader)
                Text(app.t("lockPrompt"))
                    .font(.body(15))
                    .foregroundStyle(Nexis.muted)
            }
            .padding(.top, 36)
            CodeDots(filled: entry.count, failed: message != nil && entry.isEmpty)
                .modifier(Shake(animatableData: CGFloat(shakes)))
                .padding(.top, 28)
            CodeMessage(text: message)
            Spacer(minLength: 12)
            CodePad(entry: $entry,
                    bioSymbol: security.biometricsOn ? security.biometrySymbol : nil,
                    bioLabel: app.t("lockUseBio", ["method": security.biometryName]),
                    onBio: { Task { await tryBiometrics() } },
                    onComplete: typed)
            Button(app.t("lockForgot")) { forgot = true }
                .font(.body(15, .semibold))
                .tint(Nexis.accent)
                .frame(minHeight: 44)
                .padding(.top, 8)
                .padding(.bottom, 12)
        }
        .padding(.horizontal, 20)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Nexis.bg.ignoresSafeArea())
        .task {
            profile = try? await app.repository.profile()
            if security.failures >= CodeRules.maxFailures {
                blocked = true
            } else if app.capture == nil, security.biometricsOn {
                await tryBiometrics()
            }
        }
        .confirmationDialog(app.t("lockForgot"), isPresented: $forgot, titleVisibility: .visible) {
            Button(app.t("lockForgotAction"), role: .destructive) { app.signOut() }
        } message: {
            Text(app.t("lockForgotText"))
        }
        .alert(app.t("lockBlockedTitle"), isPresented: $blocked) {
            Button(app.t("ok")) { app.signOut() }
        } message: {
            Text(app.t("lockBlockedText"))
        }
    }

    private func tryBiometrics() async {
        let security = app.security
        switch await security.unlockWithBiometrics(reason: app.t("lockPrompt"), fallback: app.t("lockUseCode")) {
        case .ok: app.locked = false
        case .changed: message = app.t("lockBioChanged", ["method": security.biometryName])
        case .failed: break
        }
    }

    private func typed(_ code: String) {
        entry = ""
        switch app.security.check(code) {
        case .ok:
            message = nil
            app.locked = false
        case .wrong(let left):
            message = app.plural("lockWrong", count: left)
            withAnimation(reduceMotion ? nil : .linear(duration: 0.4)) { shakes += 1 }
        case .blocked:
            blocked = true
        }
    }
}

// MARK: - Avant une sortie d'argent

struct GateSheet: View {
    @Environment(AppModel.self) private var app
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    let gate: MoneyGate
    @State private var entry = ""
    @State private var message: String?
    @State private var shakes = 0

    var body: some View {
        let security = app.security
        NavigationStack {
            VStack(spacing: 0) {
                VStack(spacing: 8) {
                    Text(app.t("guardTitle"))
                        .font(.title(22, .semibold, relativeTo: .title2))
                        .foregroundStyle(Nexis.ink)
                        .multilineTextAlignment(.center)
                        .accessibilityAddTraits(.isHeader)
                    Text(gate.reason)
                        .font(.body(16, .semibold))
                        .foregroundStyle(Nexis.accent)
                        .multilineTextAlignment(.center)
                }
                .padding(.top, 8)
                CodeDots(filled: entry.count, failed: message != nil && entry.isEmpty)
                    .modifier(Shake(animatableData: CGFloat(shakes)))
                    .padding(.top, 26)
                CodeMessage(text: message)
                Spacer(minLength: 12)
                CodePad(entry: $entry,
                        bioSymbol: security.biometricsOn ? security.biometrySymbol : nil,
                        bioLabel: app.t("lockUseBio", ["method": security.biometryName]),
                        onBio: { Task { await tryBiometrics() } },
                        onComplete: typed)
                    .padding(.bottom, 16)
            }
            .padding(.horizontal, 20)
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .background(Nexis.bg.ignoresSafeArea())
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button(app.t("cancel")) { app.finishGate(false) }
                }
            }
        }
        .presentationDetents([.large])
        .task {
            if app.capture == nil, security.biometricsOn { await tryBiometrics() }
        }
    }

    private func tryBiometrics() async {
        let security = app.security
        switch await security.unlockWithBiometrics(reason: gate.reason, fallback: app.t("lockUseCode")) {
        case .ok: app.finishGate(true)
        case .changed: message = app.t("lockBioChanged", ["method": security.biometryName])
        case .failed: break
        }
    }

    private func typed(_ code: String) {
        entry = ""
        switch app.security.check(code) {
        case .ok:
            app.finishGate(true)
        case .wrong(let left):
            message = app.plural("lockWrong", count: left)
            withAnimation(reduceMotion ? nil : .linear(duration: 0.4)) { shakes += 1 }
        case .blocked:
            // Le verrou montre « Trop d'essais » puis déconnecte.
            app.finishGate(false)
            app.locked = true
        }
    }
}

// MARK: - Réglages (profil)

struct SecuritySettingsView: View {
    @Environment(AppModel.self) private var app
    @State private var biometricsOn = false
    @State private var busy = false

    var body: some View {
        let security = app.security
        Form {
            if security.biometry == .none {
                Section {
                    Label(app.t("securityNoBio"), systemImage: "lock.shield")
                        .font(.body(15)).foregroundStyle(Nexis.muted)
                }
            } else {
                Section {
                    Toggle(isOn: Binding(get: { biometricsOn }, set: switchBiometrics)) {
                        Label { Text(app.t("lockUseBio", ["method": security.biometryName])).font(.body(16)) } icon: {
                            Image(systemName: security.biometrySymbol).foregroundStyle(Nexis.accent)
                        }
                    }
                    .tint(Nexis.brand)
                    .disabled(busy)
                } footer: {
                    Text(app.t("securityBioHint", ["method": security.biometryName])).font(.body(13, relativeTo: .footnote))
                }
            }
            Section {
                NavigationLink {
                    ChangeCodeView()
                } label: {
                    Label { Text(app.t("securityChangeCode")).font(.body(16)) } icon: {
                        Image(systemName: "circle.grid.3x3").foregroundStyle(Nexis.accent)
                    }
                }
            } footer: {
                Text(app.t("securityLockNote")).font(.body(13, relativeTo: .footnote))
            }
        }
        .scrollContentBackground(.hidden)
        .background(Nexis.bg)
        .flowTitle(app.t("securityRow"))
        .onAppear { biometricsOn = security.biometricsOn }
    }

    private func switchBiometrics(_ on: Bool) {
        let security = app.security
        if !on {
            security.disableBiometrics()
            biometricsOn = false
            return
        }
        busy = true
        Task {
            biometricsOn = await security.enableBiometrics(
                reason: app.t("lockUseBio", ["method": security.biometryName]), fallback: app.t("lockUseCode"))
            busy = false
        }
    }
}

/// Changer de code : l'actuel d'abord, puis le nouveau deux fois.
private struct ChangeCodeView: View {
    @Environment(AppModel.self) private var app
    @Environment(MissionFlow.self) private var flow
    @Environment(\.dismiss) private var dismiss
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    private enum Phase { case current, create, confirm }

    @State private var phase: Phase = .current
    @State private var first = ""
    @State private var entry = ""
    @State private var message: String?
    @State private var shakes = 0

    var body: some View {
        VStack(spacing: 0) {
            CodeHeader(symbol: phase == .current ? "lock" : "lock.rotation", title: title,
                       text: phase == .create ? app.t("protectAdvice") : nil)
                .padding(.top, 20)
            CodeDots(filled: entry.count, failed: message != nil && entry.isEmpty)
                .modifier(Shake(animatableData: CGFloat(shakes)))
                .padding(.top, 26)
            CodeMessage(text: message)
            Spacer(minLength: 12)
            CodePad(entry: $entry, onComplete: typed)
                .padding(.bottom, 20)
        }
        .padding(.horizontal, 20)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Nexis.bg.ignoresSafeArea())
        .flowTitle(app.t("securityChangeCode"))
    }

    private var title: String {
        switch phase {
        case .current: return app.t("securityCurrentCode")
        case .create: return app.t("securityNewCode")
        case .confirm: return app.t("protectConfirmTitle")
        }
    }

    private func typed(_ code: String) {
        entry = ""
        switch phase {
        case .current:
            switch app.security.check(code) {
            case .ok: message = nil; phase = .create
            case .wrong(let left): refuse(app.plural("lockWrong", count: left))
            case .blocked: app.locked = true
            }
        case .create:
            if CodeRules.isWeak(code) { refuse(app.t("protectWeak")) } else { first = code; message = nil; phase = .confirm }
        case .confirm:
            if code == first {
                app.security.setCode(code)
                flow.say(app.t("securityCodeChanged"))
                dismiss()
            } else {
                first = ""
                phase = .create
                refuse(app.t("protectMismatch"))
            }
        }
    }

    private func refuse(_ text: String) {
        message = text
        withAnimation(reduceMotion ? nil : .linear(duration: 0.4)) { shakes += 1 }
    }
}

// MARK: - Pièces communes

private struct CodeHeader: View {
    let symbol: String
    let title: String
    let text: String?

    var body: some View {
        VStack(spacing: 12) {
            Image(systemName: symbol)
                .font(.system(size: 26, weight: .medium))
                .foregroundStyle(Nexis.brand)
                .frame(width: 60, height: 60)
                .background(Nexis.soft, in: RoundedRectangle(cornerRadius: 18, style: .continuous))
                .accessibilityHidden(true)
            Text(title)
                .font(.title(24, .semibold, relativeTo: .title1))
                .foregroundStyle(Nexis.ink)
                .multilineTextAlignment(.center)
                .accessibilityAddTraits(.isHeader)
            if let text {
                Text(text)
                    .font(.body(15))
                    .foregroundStyle(Nexis.muted)
                    .multilineTextAlignment(.center)
                    .lineSpacing(2)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
        .frame(maxWidth: .infinity)
    }
}

/// Six points : pleins pour les chiffres tapés, rouges après une erreur.
struct CodeDots: View {
    let filled: Int
    var failed = false

    var body: some View {
        HStack(spacing: 18) {
            ForEach(0..<CodeRules.length, id: \.self) { index in
                Circle()
                    .fill(index < filled ? Nexis.brand : (failed ? Nexis.danger.opacity(0.18) : Color.clear))
                    .overlay(Circle().strokeBorder(index < filled ? Color.clear : (failed ? Nexis.danger : Nexis.muted.opacity(0.55)),
                                                   lineWidth: 1.5))
                    .frame(width: 14, height: 14)
            }
        }
        .accessibilityElement()
        .accessibilityLabel("\(filled) / \(CodeRules.length)")
    }
}

private struct CodeMessage: View {
    let text: String?

    var body: some View {
        Text(text ?? " ")
            .font(.body(14, .medium))
            .foregroundStyle(Nexis.danger)
            .multilineTextAlignment(.center)
            .fixedSize(horizontal: false, vertical: true)
            .frame(minHeight: 40)
            .padding(.top, 14)
            .accessibilityHidden(text == nil)
            .onChange(of: text) { _, value in
                if let value { AccessibilityNotification.Announcement(value).post() }
            }
    }
}

/// Le pavé de chiffres. Le clavier du système n'est pas utilisé : il
/// proposerait de remplir le code à partir des messages.
struct CodePad: View {
    @Environment(AppModel.self) private var app
    @Binding var entry: String
    var bioSymbol: String? = nil
    var bioLabel = ""
    var onBio: () -> Void = {}
    let onComplete: (String) -> Void

    private static let rows = [["1", "2", "3"], ["4", "5", "6"], ["7", "8", "9"]]
    private static let key: CGFloat = 74

    var body: some View {
        VStack(spacing: 14) {
            ForEach(Self.rows, id: \.self) { row in
                HStack(spacing: 24) { ForEach(row, id: \.self) { digit($0) } }
            }
            HStack(spacing: 24) {
                if let bioSymbol {
                    Button(action: onBio) {
                        Image(systemName: bioSymbol)
                            .font(.system(size: 30, weight: .regular))
                            .foregroundStyle(Nexis.accent)
                            .frame(width: Self.key, height: Self.key)
                            .contentShape(Circle())
                    }
                    .accessibilityLabel(bioLabel)
                } else {
                    Color.clear.frame(width: Self.key, height: Self.key)
                }
                digit("0")
                Button {
                    if !entry.isEmpty { entry.removeLast() }
                } label: {
                    Image(systemName: "delete.left")
                        .font(.system(size: 24, weight: .medium))
                        .foregroundStyle(Nexis.ink)
                        .frame(width: Self.key, height: Self.key)
                        .contentShape(Circle())
                }
                .accessibilityLabel(app.t("lockDelete"))
                .opacity(entry.isEmpty ? 0.3 : 1)
                .disabled(entry.isEmpty)
            }
        }
        .sensoryFeedback(.selection, trigger: entry.count)
    }

    private func digit(_ value: String) -> some View {
        Button {
            guard entry.count < CodeRules.length else { return }
            entry += value
            if entry.count == CodeRules.length {
                let code = entry
                // Laisse voir le dernier point avant de vérifier.
                Task {
                    try? await Task.sleep(for: .milliseconds(140))
                    onComplete(code)
                }
            }
        } label: {
            Text(value)
                .font(.title(28, .medium))
                .foregroundStyle(Nexis.ink)
                .frame(width: Self.key, height: Self.key)
        }
        .buttonStyle(PadKeyStyle())
    }
}

private struct PadKeyStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .background(Circle().fill(configuration.isPressed ? Nexis.soft : Nexis.surface))
            .overlay(Circle().strokeBorder(Nexis.line, lineWidth: 1))
            .scaleEffect(configuration.isPressed ? 0.94 : 1)
            .animation(.easeOut(duration: 0.12), value: configuration.isPressed)
            .contentShape(Circle())
    }
}

/// Petit tremblement après un code refusé.
struct Shake: GeometryEffect {
    var animatableData: CGFloat

    func effectValue(size: CGSize) -> ProjectionTransform {
        ProjectionTransform(CGAffineTransform(translationX: 8 * sin(animatableData * .pi * 4), y: 0))
    }
}
