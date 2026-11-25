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
                    Spacer(minLength: 24)
                    Image("LogoBlanc")
                        .resizable()
                        .scaledToFit()
                        .frame(height: 44)
                        .accessibilityLabel("Nexis Hub")
                    Text(app.t("slogan"))
                        .font(.title(30, .semibold, relativeTo: .largeTitle))
                        .foregroundStyle(.white)
                        .padding(.top, 28)
                        .fixedSize(horizontal: false, vertical: true)
                    Text(app.t("welcomeIntro"))
                        .font(.body(17, relativeTo: .body))
                        .foregroundStyle(.white.opacity(0.88))
                        .padding(.top, 12)
                    VerifiedStrip().padding(.top, 28)
                    Spacer(minLength: 24)
                    VStack(spacing: 12) {
                        Button { path.append(.phone(login: false)) } label: {
                            WideLabel(text: app.t("start"))
                                .foregroundStyle(Nexis.brand)
                        }
                        .whiteProminentButton()

                        Button { path.append(.phone(login: true)) } label: {
                            WideLabel(text: app.t("haveAccount"))
                                .foregroundStyle(.white)
                        }
                        .nxSecondaryButton()
                    }
                }
                .padding(.horizontal, 24)
                .padding(.bottom, 12)
            }
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) { LanguageMenu(onBrand: true) }
            }
            .toolbarBackground(.hidden, for: .navigationBar)
            .onAppear {
                switch app.capture {
                case "phone": path = [.phone(login: false)]
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

private extension View {
    @ViewBuilder
    func whiteProminentButton() -> some View {
        if #available(iOS 26.0, *) {
            self.buttonStyle(.glassProminent).tint(.white).controlSize(.large)
        } else {
            self.buttonStyle(.borderedProminent).tint(.white).controlSize(.large)
        }
    }
}

/// Les trois promesses de la maquette de bienvenue, en verre sur le bleu.
private struct VerifiedStrip: View {
    @Environment(AppModel.self) private var app

    var body: some View {
        HStack(spacing: 10) {
            ForEach([Service.plomberie, .electricite, .nettoyage], id: \.self) { service in
                VStack(spacing: 8) {
                    ServiceTile(service, size: 40)
                    Text(service.name(app.language))
                        .font(.body(12, .semibold, relativeTo: .caption1))
                        .foregroundStyle(.white)
                        .lineLimit(1)
                        .minimumScaleFactor(0.8)
                    Label(app.t("verifiedProvider"), systemImage: "checkmark.seal.fill")
                        .labelStyle(.iconOnly)
                        .font(.system(size: 13, weight: .semibold))
                        .foregroundStyle(.white.opacity(0.9))
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 14)
                .nxGlass(in: RoundedRectangle(cornerRadius: 20, style: .continuous))
            }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(app.t("verifiedProvider"))
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
        }
        .accessibilityLabel(app.t("language"))
    }
}

// MARK: - Numéro

struct PhoneView: View {
    @Environment(AppModel.self) private var app
    let login: Bool
    @Binding var path: [EntryStep]
    @State private var phone = DrcPhone(digits: "")
    @State private var channel: CodeChannel?
    @FocusState private var focused: Bool

    private var channels: [CodeChannel] { app.repository.codeChannels }

    var body: some View {
        Form {
            Section {
                Text(app.t("yourNumberIntro"))
                    .font(.body(15))
                    .foregroundStyle(Nexis.muted)
                    .listRowBackground(Color.clear)
                    .listRowInsets(EdgeInsets(top: 0, leading: 4, bottom: 8, trailing: 4))
            }
            Section {
                HStack(spacing: 10) {
                    Text("🇨🇩 +243")
                        .font(.body(17, .semibold))
                        .foregroundStyle(Nexis.ink)
                    Divider()
                    TextField("81 234 5678", text: Binding(
                        get: { phone.formatted },
                        set: { phone = DrcPhone.parse($0) }))
                        .font(.body(17, .medium))
                        .keyboardType(.phonePad)
                        .textContentType(.telephoneNumber)
                        .focused($focused)
                        .accessibilityLabel(app.t("phone"))
                }
            } footer: {
                if !phone.prefixKnown {
                    Text(app.t("numberNotCongolese"))
                        .font(.body(13)).foregroundStyle(Nexis.danger)
                }
            }
            Section {
                ForEach(channels, id: \.self) { item in
                    Button { channel = item } label: {
                        HStack(spacing: 14) {
                            ChannelIcon(channel: item)
                            VStack(alignment: .leading, spacing: 2) {
                                Text(channelName(item))
                                    .font(.body(16, .semibold)).foregroundStyle(Nexis.ink)
                                Text(channelSub(item))
                                    .font(.body(13)).foregroundStyle(Nexis.muted)
                            }
                            Spacer()
                            if selectedChannel == item {
                                Image(systemName: "checkmark.circle.fill")
                                    .font(.title3).foregroundStyle(Nexis.accent)
                            }
                        }
                    }
                    .accessibilityAddTraits(selectedChannel == item ? .isSelected : [])
                }
            } header: {
                Text(app.t("receiveCodeBy")).font(.body(13, .semibold))
            }
            if channels.isEmpty {
                Text(app.t("noCodeChannel")).font(.body(14)).foregroundStyle(Nexis.muted)
            }
        }
        .scrollContentBackground(.hidden)
        .background(Nexis.bg)
        .navigationTitle(login ? app.t("signInTitle") : app.t("yourNumber"))
        .safeAreaInset(edge: .bottom) {
            Button {
                guard let selectedChannel else { return }
                path.append(.code(phone: phone.e164, channel: selectedChannel, login: login))
            } label: {
                WideLabel(text: app.t("receiveCode"))
            }
            .nxProminentButton()
            .disabled(!phone.isValid || selectedChannel == nil)
            .padding(.horizontal, 20)
            .padding(.bottom, 8)
        }
        .onAppear { focused = true }
    }

    private var selectedChannel: CodeChannel? { channel ?? channels.first }

    private func channelName(_ channel: CodeChannel) -> String {
        switch channel {
        case .whatsapp: return "WhatsApp"
        case .telegram: return "Telegram"
        case .sms: return "SMS"
        }
    }

    private func channelSub(_ channel: CodeChannel) -> String {
        switch channel {
        case .whatsapp: return app.t("whatsappSub")
        case .telegram: return app.t("telegramSub")
        case .sms: return app.t("smsSub")
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

// MARK: - Code

struct CodeView: View {
    @Environment(AppModel.self) private var app
    let phone: String
    let channel: CodeChannel
    let login: Bool
    @Binding var path: [EntryStep]
    @State private var code = ""
    @State private var noAccount = false
    @FocusState private var focused: Bool

    private static let length = 6

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            Text(sentText)
                .font(.body(15)).foregroundStyle(Nexis.muted)
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
            Label(app.t("codeHint"), systemImage: "clock")
                .font(.body(13)).foregroundStyle(Nexis.muted)
            Label(app.t("neverAskCode"), systemImage: "lock.shield")
                .font(.body(13)).foregroundStyle(Nexis.muted)
            Spacer()
        }
        .padding(20)
        .background(Nexis.bg)
        .navigationTitle(app.t("enterCode"))
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

    private var sentText: String {
        let shown = DrcPhone.parse(phone)
        let number = "+243 \(shown.formatted)"
        if channel == .sms { return app.t("codeSentBySms", ["phone": number]) }
        return app.t("codeSentTo", ["channel": channel == .whatsapp ? "WhatsApp" : "Telegram",
                                    "phone": number])
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

// MARK: - Inscription

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
        Form {
            Section {
                Text(app.t("signupDemoNotice"))
                    .font(.body(14)).foregroundStyle(Nexis.muted)
                    .listRowBackground(Color.clear)
                    .listRowInsets(EdgeInsets(top: 0, leading: 4, bottom: 8, trailing: 4))
            }
            Section {
                TextField(app.t("signupFirstName"), text: $firstName)
                    .textContentType(.givenName)
                    .textInputAutocapitalization(.words)
                TextField(app.t("signupLastName"), text: $lastName)
                    .textContentType(.familyName)
                    .textInputAutocapitalization(.words)
                Picker(app.t("commune"), selection: $commune) {
                    Text("—").tag(String?.none)
                    ForEach(app.repository.communes, id: \.self) { item in
                        Text(item).tag(String?.some(item))
                    }
                }
                .pickerStyle(.navigationLink)
            }
            .font(.body(16))
            Section {
                VStack(alignment: .leading, spacing: 4) {
                    Text(app.t("legalTerms")).font(.title(15)).foregroundStyle(Nexis.ink)
                    Text(app.t("termsVersion", ["date": termsDate]))
                        .font(.body(13)).foregroundStyle(Nexis.muted)
                }
                Button(app.t("signupReadTerms")) { readingTerms = true }
                    .font(.body(16, .semibold))
                Toggle(app.t("signupAcceptTerms"), isOn: $accepted)
                    .font(.body(16))
                    .tint(Nexis.brand)
            }
            if failed {
                Text(app.t("signupFailed")).font(.body(14)).foregroundStyle(Nexis.danger)
            }
        }
        .scrollContentBackground(.hidden)
        .background(Nexis.bg)
        .navigationTitle(app.t("signupTitle"))
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
