import SwiftUI

/// Étapes du parcours d'entrée.
enum EntryStep: Hashable {
    case phone(login: Bool)
    case code(phone: String, channel: CodeChannel, login: Bool)
    case signup(phone: String)
}

// MARK: - Bienvenue

struct WelcomeView: View {
    @Environment(AppModel.self) private var app
    @State private var path: [EntryStep] = []

    var body: some View {
        NavigationStack(path: $path) {
            ZStack {
                Nexis.heroGradient.ignoresSafeArea()
                VStack(alignment: .leading, spacing: 0) {
                    HStack {
                        Image("LogoBlanc")
                            .resizable()
                            .scaledToFit()
                            .frame(height: 17)
                            .accessibilityLabel("Nexis Hub")
                            .accessibilityAddTraits(.isHeader)
                        Spacer()
                        LanguageMenu(onBrand: true)
                    }
                    .padding(.horizontal, 20)
                    .padding(.top, 8)
                    Constellation()
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                        .padding(.vertical, 12)
                    Text(app.t("slogan"))
                        .font(.title(28, .semibold, relativeTo: .largeTitle))
                        .foregroundStyle(.white)
                        .fixedSize(horizontal: false, vertical: true)
                        .padding(.horizontal, 24)
                    Text(app.t("welcomeIntro"))
                        .font(.body(16, relativeTo: .body))
                        .foregroundStyle(.white.opacity(0.9))
                        .fixedSize(horizontal: false, vertical: true)
                        .padding(.top, 12)
                        .padding(.horizontal, 24)
                    VStack(spacing: 12) {
                        Button(app.t("start")) { path.append(.phone(login: false)) }
                            .buttonStyle(OnBlueButtonStyle(kind: .filled))

                        Button(app.t("haveAccount")) { path.append(.phone(login: true)) }
                            .buttonStyle(OnBlueButtonStyle(kind: .outlined))
                    }
                    .padding(.horizontal, 24)
                    .padding(.top, 32)
                    .padding(.bottom, 12)
                }
            }
            .toolbar(.hidden, for: .navigationBar)
            .onAppear {
                switch app.capture {
                case "phone": path = [.phone(login: false)]
                case "code": path = [.phone(login: false), .code(phone: "+243991112222", channel: .whatsapp, login: false)]
                case "signup": path = [.phone(login: false), .signup(phone: "+243991112222")]
                default: break
                }
            }
            .navigationDestination(for: EntryStep.self) { step in
                switch step {
                case .phone(let login):
                    PhoneView(login: login, path: $path)
                case .code(let phone, let channel, let login):
                    CodeView(phone: phone, channel: channel, login: login, path: $path)
                case .signup(let phone):
                    SignupView(phone: phone)
                }
            }
        }
    }
}

/// Boutons posés sur le bleu de la bienvenue. Des couleurs pleines plutôt que
/// du verre : sur ce bleu vif, le verre prenait une teinte cyan et rendait le
/// texte blanc de « J'ai déjà un compte » difficile à lire.
private struct OnBlueButtonStyle: ButtonStyle {
    enum Kind { case filled, outlined }
    let kind: Kind

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.body(17, .semibold, relativeTo: .headline))
            .foregroundStyle(kind == .filled ? Nexis.brand : Color.white)
            .multilineTextAlignment(.center)
            .padding(.horizontal, 20)
            .frame(maxWidth: .infinity, minHeight: 54)
            .background(Capsule().fill(kind == .filled ? Color.white : Color.white.opacity(0.12)))
            .overlay(Capsule().strokeBorder(Color.white.opacity(kind == .filled ? 0 : 0.6), lineWidth: 1))
            .shadow(color: Nexis.navy.opacity(kind == .filled ? 0.18 : 0), radius: 12, y: 6)
            .contentShape(Capsule())
            .opacity(configuration.isPressed ? 0.8 : 1)
            .scaleEffect(configuration.isPressed ? 0.98 : 1)
            .animation(.easeOut(duration: 0.15), value: configuration.isPressed)
    }
}

/// Bienvenue « Constellation » (maquette A1 choisie par Ben le 2026-11-25) :
/// des carrés de services blancs, penchés, qui flottent lentement. À chaque
/// ouverture de l'app, chacun fait une fois le tour de ses objets (même rythme que
/// « Quel service ? »), puis revient à son icône. Avec « Réduire les
/// animations », rien ne bouge.
private struct Constellation: View {
    private struct Spot {
        let service: String
        let x, y, size, angle: CGFloat
        /// Durée d'un aller-retour du flottement, en secondes.
        let period: Double
    }

    /// Positions de la maquette, pour un écran de 390 points de large.
    private static let spots: [Spot] = [
        Spot(service: "plomberie", x: 30, y: 30, size: 74, angle: -6, period: 7.0),
        Spot(service: "climatisation", x: 150, y: 6, size: 58, angle: 4, period: 6.2),
        Spot(service: "coiffure", x: 262, y: 42, size: 82, angle: 7, period: 7.8),
        Spot(service: "electricite", x: 84, y: 146, size: 60, angle: 5, period: 6.6),
        Spot(service: "nettoyage", x: 186, y: 120, size: 86, angle: -4, period: 7.4),
        Spot(service: "demenagement", x: 296, y: 172, size: 58, angle: -7, period: 6.0),
        Spot(service: "informatique", x: 24, y: 240, size: 56, angle: 3, period: 7.2),
        Spot(service: "peinture", x: 122, y: 248, size: 66, angle: -3, period: 6.8),
    ]
    private static let design = CGSize(width: 390, height: 320)

    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var tour = 0
    @State private var floating = false

    var body: some View {
        GeometryReader { geo in
            let k = min(geo.size.width / Self.design.width, geo.size.height / Self.design.height)
            let left = (geo.size.width - Self.design.width * k) / 2
            let top = (geo.size.height - Self.design.height * k) / 2
            ForEach(Self.spots.indices, id: \.self) { i in
                let spot = Self.spots[i]
                ServiceTile(icons: Pictogrammes.byService[spot.service] ?? Pictogrammes.fallback,
                            size: spot.size * k, tour: tour, delay: 1 + Double(i) * 0.4)
                    .shadow(color: Nexis.navy.opacity(0.22), radius: 14 * k, y: 10 * k)
                    .rotationEffect(.degrees(spot.angle))
                    .offset(y: floating ? -9 * k : 0)
                    .animation(reduceMotion ? nil : .easeInOut(duration: spot.period / 2)
                        .repeatForever(autoreverses: true).delay(Double(i) * 0.6), value: floating)
                    .position(x: left + (spot.x + spot.size / 2) * k, y: top + (spot.y + spot.size / 2) * k)
            }
        }
        // Carrés blancs et icônes bleues, même en mode sombre : ils sont posés sur le bleu.
        .environment(\.colorScheme, .light)
        .accessibilityHidden(true)
        .onAppear {
            // Un seul tour par ouverture de l'app, pas à chaque retour en arrière.
            if tour == 0 { tour = 1 }
            if !reduceMotion { floating = true }
        }
    }
}

/// Pastille de langue : FR, LN ou EN, et un menu des trois langues.
struct LanguageMenu: View {
    @Environment(AppModel.self) private var app
    var onBrand = false

    var body: some View {
        Menu {
            Picker(app.t("language"), selection: Binding(
                get: { app.language }, set: { app.language = $0 })) {
                Text("Français").tag("fr")
                Text("Lingála").tag("ln")
                Text("English").tag("en")
            }
        } label: {
            Label(app.language.uppercased(), systemImage: "globe")
                .font(.body(14, .semibold, relativeTo: .subheadline))
                .foregroundStyle(onBrand ? Color.white : Nexis.ink)
                .padding(.horizontal, onBrand ? 12 : 0)
                .frame(minHeight: 36)
                .nxOnBrandPill()
        }
        .accessibilityLabel(app.t("language"))
    }
}

// MARK: - Parties communes (maquettes A2 à A4)

/// Titre et phrase d'introduction des écrans d'entrée, dans le contenu
/// (la barre ne garde que le retour et la langue).
private struct EntryHeading: View {
    let title: String
    var text: String? = nil

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title)
                .font(.title(28, .semibold, relativeTo: .largeTitle))
                .foregroundStyle(Nexis.ink)
                .accessibilityAddTraits(.isHeader)
            if let text {
                Text(text).font(.body(15)).foregroundStyle(Nexis.muted).lineSpacing(3)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

private extension View {
    /// Barre des écrans d'entrée : retour à gauche, langue à droite.
    func entryChrome(_ title: String) -> some View {
        self.background(Nexis.bg)
            .navigationTitle(title)
            .toolbar {
                ToolbarItem(placement: .principal) { Color.clear.frame(width: 1, height: 1) }
                ToolbarItem(placement: .topBarTrailing) { LanguageMenu() }
            }
            .navigationBarTitleDisplayMode(.inline)
    }
}

/// Carte blanche aux coins de 20, comme dans les maquettes.
private struct EntryCard<Content: View>: View {
    @ViewBuilder var content: Content

    var body: some View {
        VStack(spacing: 0) { content }
            .background(Nexis.surface, in: RoundedRectangle(cornerRadius: 20, style: .continuous))
    }
}

private struct EntryLabel: View {
    let text: String

    var body: some View {
        Text(text).font(.body(13, .semibold, relativeTo: .footnote)).foregroundStyle(Nexis.muted)
    }
}

// MARK: - Numéro (A2)

struct PhoneView: View {
    @Environment(AppModel.self) private var app
    let login: Bool
    @Binding var path: [EntryStep]
    @State private var phone = DrcPhone(digits: "")
    @State private var channel: CodeChannel?
    @State private var sending = false
    @State private var failed = false
    @FocusState private var focused: Bool

    private var channels: [CodeChannel] { app.repository.codeChannels }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 0) {
                EntryHeading(title: login ? app.t("signInTitle") : app.t("yourNumber"), text: app.t("yourNumberIntro"))
                EntryLabel(text: app.t("phone")).padding(.top, 24)
                HStack(spacing: 12) {
                    Text("🇨🇩").font(.system(size: 22)).accessibilityHidden(true)
                    Text("+243").font(.body(17, .semibold)).foregroundStyle(Nexis.ink)
                    Rectangle().fill(Nexis.line).frame(width: 1, height: 26)
                    TextField("81 234 5678", text: Binding(
                        get: { phone.formatted },
                        set: { phone = DrcPhone.parse($0) }))
                        .font(.body(19, .medium))
                        .keyboardType(.phonePad)
                        .textContentType(.telephoneNumber)
                        .focused($focused)
                        .accessibilityLabel(app.t("phone"))
                }
                .padding(.horizontal, 16)
                .frame(height: 60)
                .background(Nexis.surface, in: RoundedRectangle(cornerRadius: 18, style: .continuous))
                .overlay(RoundedRectangle(cornerRadius: 18, style: .continuous)
                    .strokeBorder(focused ? Nexis.brand : Nexis.line, lineWidth: focused ? 2 : 1))
                .background(RoundedRectangle(cornerRadius: 22, style: .continuous)
                    .fill(Nexis.brand.opacity(focused ? 0.12 : 0)).padding(-4))
                .contentShape(Rectangle())
                .onTapGesture { focused = true }
                .padding(.top, 8)
                .animation(.snappy(duration: 0.2), value: focused)
                if !phone.prefixKnown {
                    Text(app.t("numberNotCongolese"))
                        .font(.body(13)).foregroundStyle(Nexis.danger).padding(.top, 8)
                }
                EntryLabel(text: app.t("receiveCodeBy")).padding(.top, 26)
                EntryCard {
                    ForEach(Array(channels.enumerated()), id: \.element) { index, item in
                        Button { channel = item } label: {
                            HStack(spacing: 14) {
                                ChannelIcon(channel: item)
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(channelName(item))
                                        .font(.body(16, .semibold)).foregroundStyle(Nexis.ink)
                                    Text(channelSub(item))
                                        .font(.body(13, relativeTo: .footnote)).foregroundStyle(Nexis.muted)
                                }
                                Spacer(minLength: 8)
                                if selectedChannel == item {
                                    Image(systemName: "checkmark.circle.fill")
                                        .font(.system(size: 24)).foregroundStyle(Nexis.brand)
                                } else {
                                    Circle().strokeBorder(Color(light: 0xC9D0DB, dark: 0x3A4A66), lineWidth: 2)
                                        .frame(width: 22, height: 22).padding(1)
                                }
                            }
                            .padding(.horizontal, 16)
                            .padding(.vertical, 12)
                            .contentShape(Rectangle())
                        }
                        .buttonStyle(.plain)
                        .accessibilityAddTraits(selectedChannel == item ? .isSelected : [])
                        if index < channels.count - 1 { Divider().padding(.leading, 66) }
                    }
                }
                .padding(.top, 8)
                if channels.isEmpty {
                    Text(app.t("noCodeChannel")).font(.body(14)).foregroundStyle(Nexis.muted).padding(.top, 8)
                }
                if failed {
                    Text(app.t("actionFailed")).font(.body(14)).foregroundStyle(Nexis.danger).padding(.top, 12)
                }
            }
            .padding(.horizontal, 20)
            .padding(.top, 8)
            .padding(.bottom, 24)
        }
        .scrollDismissesKeyboard(.interactively)
        .disabled(sending)
        .entryChrome(login ? app.t("signInTitle") : app.t("yourNumber"))
        .safeAreaInset(edge: .bottom) {
            Button(action: sendCode) {
                BusyLabel(text: app.t("receiveCode"), busy: sending)
            }
            .nxProminentButton()
            .disabled(!phone.isValid || selectedChannel == nil || sending)
            .padding(.horizontal, 20)
            .padding(.bottom, 8)
        }
        .onAppear { focused = true }
    }

    private var selectedChannel: CodeChannel? { channel ?? channels.first }

    /// Le serveur envoie le code ; on n'avance qu'une fois l'envoi confirmé.
    private func sendCode() {
        guard let selectedChannel, phone.isValid, !sending else { return }
        let number = phone.e164
        sending = true
        failed = false
        focused = false
        Task {
            do {
                try await app.repository.sendCode(phone: number, channel: selectedChannel)
                path.append(.code(phone: number, channel: selectedChannel, login: login))
            } catch {
                failed = true
            }
            sending = false
        }
    }

    private func channelName(_ channel: CodeChannel) -> String { channel.displayName }

    private func channelSub(_ channel: CodeChannel) -> String {
        switch channel {
        case .whatsapp: return app.t("whatsappSub")
        case .telegram: return app.t("telegramSub")
        case .sms: return app.t("smsSub")
        }
    }
}

extension CodeChannel {
    var displayName: String {
        switch self {
        case .whatsapp: return "WhatsApp"
        case .telegram: return "Telegram"
        case .sms: return "SMS"
        }
    }
}

private struct ChannelIcon: View {
    let channel: CodeChannel

    var body: some View {
        let (symbol, color): (String, Color) = {
            switch channel {
            case .whatsapp: return ("message.fill", Color(hex: 0x25D366))
            case .telegram: return ("paperplane.fill", Color(hex: 0x229ED9))
            case .sms: return ("text.bubble.fill", Nexis.muted)
            }
        }()
        return Image(systemName: symbol)
            .font(.system(size: 17, weight: .semibold))
            .foregroundStyle(.white)
            .frame(width: 36, height: 36)
            .background(color, in: RoundedRectangle(cornerRadius: 10, style: .continuous))
            .accessibilityHidden(true)
    }
}

// MARK: - Code (A3)

struct CodeView: View {
    @Environment(AppModel.self) private var app
    let phone: String
    let login: Bool
    @Binding var path: [EntryStep]
    @State private var channel: CodeChannel
    @State private var code = ""
    @State private var noAccount = false
    @State private var secondsLeft = CodeView.resendDelay
    @State private var resending = false
    @State private var notice: String?
    @FocusState private var focused: Bool

    private static let length = 6
    /// Délai avant de pouvoir redemander un code : 60 s (choix de Ben).
    static let resendDelay = 60

    init(phone: String, channel: CodeChannel, login: Bool, path: Binding<[EntryStep]>) {
        self.phone = phone
        self.login = login
        _path = path
        _channel = State(initialValue: channel)
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                EntryHeading(title: app.t("enterCode"), text: sentText)
                CodeBoxes(code: code, length: Self.length)
                    .overlay {
                        TextField("", text: $code)
                            .keyboardType(.numberPad)
                            .textContentType(.oneTimeCode)
                            .focused($focused)
                            .foregroundStyle(.clear)
                            .tint(.clear)
                            .accessibilityLabel(app.t("enterCode"))
                            .onChange(of: code) { _, value in
                                let digits = String(value.filter(\.isNumber).prefix(Self.length))
                                if digits != value { code = digits }
                                if digits.count == Self.length { verified() }
                            }
                    }
                    .onTapGesture { focused = true }
                VStack(alignment: .leading, spacing: 10) {
                    hint("clock", app.t("codeHint"))
                    hint("checkmark.shield", app.t("neverAskCode"))
                }
                HStack {
                    Button(action: resend) {
                        Text(secondsLeft == 0 ? app.t("resendNow")
                             : app.t("resendIn", ["time": String(format: "%d:%02d", secondsLeft / 60, secondsLeft % 60)]))
                            .font(.body(14, secondsLeft == 0 ? .semibold : .regular))
                            .foregroundStyle(secondsLeft == 0 ? Nexis.accent : Nexis.muted)
                            .monospacedDigit()
                    }
                    .disabled(secondsLeft > 0 || resending)
                    Spacer()
                    Button(app.t("changeLoginNumber")) { path.removeLast() }
                        .font(.body(14, .semibold))
                        .tint(Nexis.accent)
                }
                ForEach(app.repository.codeChannels.filter { $0 != channel }, id: \.self) { other in
                    Button(app.t("receiveInstead", ["channel": other.displayName])) { switchTo(other) }
                        .font(.body(14, .semibold))
                        .tint(Nexis.accent)
                        .disabled(resending)
                }
            }
            .padding(.horizontal, 20)
            .padding(.top, 8)
            .padding(.bottom, 24)
        }
        .entryChrome(app.t("enterCode"))
        .overlay(alignment: .bottom) {
            if let notice {
                Toast(text: notice).padding(.bottom, 20).transition(.move(edge: .bottom).combined(with: .opacity))
            }
        }
        .animation(.snappy, value: notice)
        .task(id: notice) {
            guard let shown = notice else { return }
            AccessibilityNotification.Announcement(shown).post()
            try? await Task.sleep(for: .seconds(2.5))
            if notice == shown { notice = nil }
        }
        .task(id: channel) {
            // Le compte à rebours repart à chaque nouvel envoi.
            while secondsLeft > 0 {
                try? await Task.sleep(for: .seconds(1))
                if Task.isCancelled { return }
                secondsLeft -= 1
            }
        }
        .onAppear { focused = true }
        .alert(app.t("noAccountTitle"), isPresented: $noAccount) {
            Button(app.t("signupCreateProfile")) { path.append(.signup(phone: phone)) }
            Button(app.t("changeLoginNumber"), role: .cancel) {
                path.removeLast(path.count - 1)
            }
        } message: {
            Text(app.t("noAccountHint"))
        }
    }

    private func hint(_ symbol: String, _ text: String) -> some View {
        HStack(alignment: .top, spacing: 8) {
            Image(systemName: symbol).font(.system(size: 14)).foregroundStyle(Nexis.muted).padding(.top, 1)
            Text(text).font(.body(13, relativeTo: .footnote)).foregroundStyle(Nexis.muted)
        }
        .accessibilityElement(children: .combine)
    }

    private var sentText: String {
        let shown = DrcPhone.parse(phone)
        let number = "+243 \(shown.formatted)"
        if channel == .sms { return app.t("codeSentBySms", ["phone": number]) }
        return app.t("codeSentTo", ["channel": channel.displayName, "phone": number])
    }

    /// Redemande un code par le même canal, une fois le délai passé.
    private func resend() {
        guard secondsLeft == 0 else { return }
        send(by: channel, notice: app.t("codeResentToast", ["channel": channel.displayName]))
    }

    private func switchTo(_ other: CodeChannel) {
        send(by: other, notice: app.t("codeSentToast", ["channel": other.displayName]))
    }

    private func send(by target: CodeChannel, notice text: String) {
        resending = true
        Task {
            do {
                try await app.repository.sendCode(phone: phone, channel: target)
                code = ""
                secondsLeft = Self.resendDelay
                if target == channel {
                    // Même canal : relancer le compte à rebours à la main.
                    channel = target
                    restartCountdown()
                } else {
                    channel = target
                }
                notice = text
            } catch {
                notice = app.t("actionFailed")
            }
            resending = false
        }
    }

    private func restartCountdown() {
        Task {
            while secondsLeft > 0 {
                try? await Task.sleep(for: .seconds(1))
                secondsLeft -= 1
            }
        }
    }

    /// Démonstration : tout code à 6 chiffres est accepté.
    private func verified() {
        focused = false
        if app.repository.openAccount(phone: phone) {
            app.signIn()
        } else if login {
            noAccount = true
        } else {
            path.append(.signup(phone: phone))
        }
    }
}

private struct CodeBoxes: View {
    let code: String
    let length: Int

    var body: some View {
        HStack(spacing: 10) {
            ForEach(0..<length, id: \.self) { index in
                let digit = index < code.count ? String(Array(code)[index]) : ""
                Text(digit)
                    .font(.title(24, .semibold))
                    .foregroundStyle(Nexis.ink)
                    .frame(maxWidth: .infinity)
                    .frame(height: 58)
                    .background(Nexis.surface, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
                    .overlay(RoundedRectangle(cornerRadius: 14, style: .continuous)
                        .strokeBorder(index == code.count ? Nexis.accent : Nexis.line,
                                      lineWidth: index == code.count ? 2 : 1))
            }
        }
        .accessibilityHidden(true)
    }
}

// MARK: - Inscription (A4)

struct SignupView: View {
    @Environment(AppModel.self) private var app
    let phone: String
    @State private var firstName = ""
    @State private var lastName = ""
    @State private var commune: String?
    @State private var accepted = false
    @State private var failed = false
    @State private var readingTerms = false

    private var complete: Bool {
        !firstName.trimmingCharacters(in: .whitespaces).isEmpty &&
        !lastName.trimmingCharacters(in: .whitespaces).isEmpty &&
        commune != nil && accepted
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 0) {
                EntryHeading(title: app.t("signupTitle"))
                Label(app.t("numberVerified", ["phone": "+243 \(DrcPhone.parse(phone).formatted)"]),
                      systemImage: "checkmark.circle.fill")
                    .font(.body(13, .semibold, relativeTo: .footnote))
                    .foregroundStyle(Nexis.ok)
                    .padding(.horizontal, 11).padding(.vertical, 6)
                    .background(Color(light: 0xE6F4EC, dark: 0x12301F), in: Capsule())
                    .padding(.top, 12)
                EntryCard {
                    fieldRow(app.t("signupFirstName")) {
                        TextField(app.t("signupFirstName"), text: $firstName)
                            .textContentType(.givenName)
                            .textInputAutocapitalization(.words)
                    }
                    Divider().padding(.leading, 16)
                    fieldRow(app.t("signupLastName")) {
                        TextField(app.t("signupLastName"), text: $lastName)
                            .textContentType(.familyName)
                            .textInputAutocapitalization(.words)
                    }
                    Divider().padding(.leading, 16)
                    NavigationLink {
                        CommunePicker(selection: $commune)
                    } label: {
                        fieldRow(app.t("commune")) {
                            Text(commune ?? "—")
                                .foregroundStyle(commune == nil ? Nexis.muted : Nexis.ink)
                                .frame(maxWidth: .infinity, alignment: .leading)
                            Image(systemName: "chevron.right")
                                .font(.system(size: 14, weight: .semibold))
                                .foregroundStyle(Nexis.muted)
                        }
                    }
                    .buttonStyle(.plain)
                }
                .padding(.top, 22)
                EntryCard {
                    HStack(spacing: 12) {
                        Image(systemName: "doc.text")
                            .font(.system(size: 18, weight: .medium))
                            .foregroundStyle(Nexis.brand)
                            .frame(width: 38, height: 38)
                            .background(Nexis.soft, in: RoundedRectangle(cornerRadius: 11, style: .continuous))
                            .accessibilityHidden(true)
                        VStack(alignment: .leading, spacing: 2) {
                            Text(app.t("legalTerms")).font(.body(15, .semibold)).foregroundStyle(Nexis.ink)
                            Text(app.t("termsVersion", ["date": termsDate]))
                                .font(.body(13, relativeTo: .footnote)).foregroundStyle(Nexis.muted)
                        }
                        Spacer(minLength: 8)
                        Button(app.t("signupReadTerms")) { readingTerms = true }
                            .font(.body(14, .semibold))
                            .tint(Nexis.accent)
                    }
                    .padding(.horizontal, 16)
                    .padding(.vertical, 14)
                    Divider().padding(.leading, 16)
                    Toggle(app.t("signupAcceptTerms"), isOn: $accepted)
                        .font(.body(15))
                        .tint(Nexis.brand)
                        .padding(.horizontal, 16)
                        .frame(minHeight: 54)
                }
                .padding(.top, 16)
                if failed {
                    Text(app.t("signupFailed")).font(.body(14)).foregroundStyle(Nexis.danger).padding(.top, 12)
                }
                Text(app.t("signupDemoNotice"))
                    .font(.body(13, relativeTo: .footnote)).foregroundStyle(Nexis.muted)
                    .padding(.top, 16)
            }
            .padding(.horizontal, 20)
            .padding(.top, 8)
            .padding(.bottom, 24)
        }
        .scrollDismissesKeyboard(.interactively)
        .entryChrome(app.t("signupTitle"))
        .onChange(of: [firstName, lastName]) { failed = false }
        .safeAreaInset(edge: .bottom) {
            Button(action: submit) { WideLabel(text: app.t("signupCreateProfile")) }
                .nxProminentButton()
                .disabled(!complete)
                .padding(.horizontal, 20)
                .padding(.bottom, 8)
        }
        .sheet(isPresented: $readingTerms) {
            NavigationStack {
                ScrollView {
                    VStack(alignment: .leading, spacing: 12) {
                        Text(app.t("termsVersion", ["date": termsDate]))
                            .font(.body(13)).foregroundStyle(Nexis.muted)
                        Text(app.t("signupDemoTerms")).font(.body(16)).foregroundStyle(Nexis.ink)
                    }
                    .padding(20)
                }
                .navigationTitle(app.t("legalTerms"))
                .navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItem(placement: .confirmationAction) {
                        Button(app.t("close")) { readingTerms = false }
                    }
                }
            }
        }
    }

    /// Ligne « Prénom · Grâce » : le libellé à gauche, la valeur à côté.
    private func fieldRow(_ label: String, @ViewBuilder value: () -> some View) -> some View {
        HStack(spacing: 12) {
            Text(label)
                .font(.body(14)).foregroundStyle(Nexis.muted)
                .frame(width: 84, alignment: .leading)
                .accessibilityHidden(true)
            HStack { value() }
                .font(.body(16, .medium))
                .foregroundStyle(Nexis.ink)
        }
        .padding(.horizontal, 16)
        .frame(minHeight: 54)
        .contentShape(Rectangle())
    }

    private var termsDate: String {
        app.repository.signupTermsVersion.formatted(
            .dateTime.day().month(.twoDigits).year().locale(app.locale))
    }

    private func submit() {
        guard complete, let commune else { return }
        let repo = app.repository
        let created = repo.registerClient(
            phone: phone, firstName: firstName, lastName: lastName, commune: commune,
            acceptedTermsVersion: accepted ? repo.signupTermsVersion : nil)
        if created { app.signIn() } else { failed = true }
    }
}

/// La liste des communes, avec une coche sur celle choisie.
struct CommunePicker: View {
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    @Binding var selection: String?

    var body: some View {
        List(app.repository.communes, id: \.self) { item in
            Button {
                selection = item
                dismiss()
            } label: {
                HStack {
                    Text(item).font(.body(16)).foregroundStyle(Nexis.ink)
                    Spacer()
                    if selection == item {
                        Image(systemName: "checkmark").font(.system(size: 15, weight: .semibold)).foregroundStyle(Nexis.accent)
                    }
                }
            }
            .accessibilityAddTraits(selection == item ? .isSelected : [])
        }
        .scrollContentBackground(.hidden)
        .background(Nexis.bg)
        .navigationTitle(app.t("commune"))
        .navigationBarTitleDisplayMode(.inline)
    }
}
