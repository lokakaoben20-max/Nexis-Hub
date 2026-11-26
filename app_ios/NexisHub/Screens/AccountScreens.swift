import SwiftUI
import UIKit
import UserNotifications

// Écrans ouverts depuis le profil : mes informations, mes téléphones,
// notifications, aide et litiges, conditions, devenir prestataire.

// MARK: - Mes informations

struct ProfileInfoView: View {
    @Environment(AppModel.self) private var app
    @Environment(MissionFlow.self) private var flow
    @State private var profile: Profile?
    @State private var firstName = ""
    @State private var lastName = ""
    @State private var commune: String?
    @State private var busy = false
    @State private var failed = false

    var body: some View {
        Group {
            if let profile { form(profile) } else { FlowLoading(label: app.t("myInfo")) }
        }
        .flowTitle(app.t("myInfo"))
        .task {
            guard profile == nil, let loaded = try? await app.repository.profile() else { return }
            profile = loaded
            firstName = loaded.firstName
            lastName = loaded.lastName
            commune = loaded.commune
        }
    }

    private func form(_ profile: Profile) -> some View {
        let first = firstName.trimmingCharacters(in: .whitespacesAndNewlines)
        let last = lastName.trimmingCharacters(in: .whitespacesAndNewlines)
        let changed = first != profile.firstName || last != profile.lastName || commune != profile.commune
        let ready = changed && !first.isEmpty && !last.isEmpty && commune != nil
        return Form {
            Section {
                HStack {
                    Spacer()
                    InitialsAvatar(initials: (String(first.prefix(1)) + String(last.prefix(1))).uppercased())
                        .scaleEffect(1.3)
                        .padding(.vertical, 14)
                    Spacer()
                }
                .listRowBackground(Color.clear)
            }
            Section {
                LabeledContent(app.t("signupFirstName")) {
                    TextField(app.t("signupFirstName"), text: $firstName)
                        .textContentType(.givenName)
                        .textInputAutocapitalization(.words)
                        .multilineTextAlignment(.trailing)
                }
                LabeledContent(app.t("signupLastName")) {
                    TextField(app.t("signupLastName"), text: $lastName)
                        .textContentType(.familyName)
                        .textInputAutocapitalization(.words)
                        .multilineTextAlignment(.trailing)
                }
                Picker(app.t("commune"), selection: $commune) {
                    ForEach(app.repository.communes, id: \.self) { item in
                        Text(item).tag(String?.some(item))
                    }
                }
                .pickerStyle(.navigationLink)
            }
            .font(.body(16))
            .disabled(busy)
            Section {
                LabeledContent(app.t("phone")) {
                    VStack(alignment: .trailing, spacing: 4) {
                        Text("+243 \(DrcPhone.parse(profile.phone).formatted)")
                            .font(.body(16)).foregroundStyle(Nexis.ink).monospacedDigit()
                        Pill(tone: .ok, systemImage: "checkmark.seal.fill", text: app.t("infoPhoneVerified"))
                    }
                }
                .font(.body(16))
            } footer: {
                Text(app.t("infoPhoneLocked")).font(.body(13, relativeTo: .footnote))
            }
            if failed {
                Text(app.t("infoFailed")).font(.body(14)).foregroundStyle(Nexis.danger)
                    .listRowBackground(Color.clear)
            }
        }
        .scrollContentBackground(.hidden)
        .onChange(of: [firstName, lastName]) { failed = false }
        .bottomActions {
            Button { Task { await save() } } label: { BusyLabel(text: app.t("infoSave"), busy: busy) }
                .nxProminentButton()
                .disabled(!ready || busy)
        }
    }

    private func save() async {
        guard let commune else { return }
        busy = true
        do {
            _ = try await app.repository.updateProfile(firstName: firstName, lastName: lastName, commune: commune)
            app.dataChanged()
            if !flow.path.isEmpty { flow.path.removeLast() }
            flow.say(app.t("infoSaved"))
        } catch {
            busy = false
            failed = true
        }
    }
}

// MARK: - Mes appareils

struct DevicesView: View {
    @Environment(AppModel.self) private var app
    @Environment(MissionFlow.self) private var flow
    @State private var devices: [AppDevice]?
    @State private var confirming: AppDevice?
    @State private var busy: Int?

    var body: some View {
        Group {
            if let devices { content(devices) } else { FlowLoading(label: app.t("myDevices")) }
        }
        .flowTitle(app.t("myDevices"))
        .task(id: app.revision) { devices = try? await app.repository.devices() }
        .confirmationDialog(confirming.map { app.t("devicesSignOutTitle", ["name": $0.label]) } ?? "",
                            isPresented: Binding(get: { confirming != nil }, set: { if !$0 { confirming = nil } }),
                            titleVisibility: .visible, presenting: confirming) { device in
            Button(app.t("devicesSignOut"), role: .destructive) { Task { await signOut(device) } }
            Button(app.t("close"), role: .cancel) {}
        } message: { _ in
            Text(app.t("devicesSignOutText"))
        }
    }

    private func content(_ devices: [AppDevice]) -> some View {
        let others = devices.filter { !$0.isCurrent }
        return ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                SectionHeader(text: app.t("devicesThis"))
                ForEach(devices.filter(\.isCurrent)) { device in DeviceCard(device: device) }
                if !others.isEmpty {
                    SectionHeader(text: app.t("devicesOthers")).padding(.top, 6)
                    ForEach(others) { device in
                        DeviceCard(device: device) {
                            Button(role: .destructive) { confirming = device } label: {
                                BusyLabel(text: app.t("devicesSignOut"), busy: busy == device.id, loaderColor: Nexis.danger)
                            }
                            .buttonStyle(OutlineButtonStyle(tint: Nexis.danger))
                            .disabled(busy != nil)
                        }
                    }
                    InfoNote(text: app.t("devicesNotMe"), kind: .danger, systemImage: "exclamationmark.shield.fill")
                }
                InfoNote(text: app.t("devicesMoneyHint"), systemImage: "lock.shield.fill")
            }
            .flowScreen()
        }
    }

    private func signOut(_ device: AppDevice) async {
        busy = device.id
        defer { busy = nil }
        do {
            try await app.repository.signOutDevice(id: device.id)
            app.dataChanged()
            flow.say(app.t("devicesSignedOut", ["name": device.label]))
        } catch {
            flow.say(app.t("actionFailed"))
        }
    }
}

private struct SectionHeader: View {
    let text: String

    var body: some View {
        Text(text).font(.body(16, .semibold, relativeTo: .headline)).foregroundStyle(Nexis.ink)
            .accessibilityAddTraits(.isHeader)
    }
}

private struct DeviceCard<Actions: View>: View {
    @Environment(AppModel.self) private var app
    let device: AppDevice
    @ViewBuilder var actions: Actions

    var body: some View {
        let hours = device.moneyHoursLeft()
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 12) {
                Image(systemName: device.platform == .ios ? "iphone" : "smartphone")
                    .font(.system(size: 19, weight: .medium))
                    .foregroundStyle(Nexis.softInk)
                    .frame(width: 44, height: 44)
                    .background(Nexis.soft, in: RoundedRectangle(cornerRadius: 13, style: .continuous))
                    .accessibilityHidden(true)
                VStack(alignment: .leading, spacing: 3) {
                    Text(device.label).font(.body(15.5, .bold)).foregroundStyle(Nexis.ink)
                    Text(app.t("devicesAdded", ["date": app.longDate(device.addedAt)]))
                        .font(.body(13, relativeTo: .footnote)).foregroundStyle(Nexis.muted)
                    if let seen = device.lastSeenAt, !device.isCurrent {
                        Text(app.t("devicesLastSeen", ["when": app.lastSeen(seen)]))
                            .font(.body(13, relativeTo: .footnote)).foregroundStyle(Nexis.muted)
                    }
                }
                Spacer(minLength: 8)
            }
            if hours > 0 {
                Pill(tone: .warn, systemImage: "clock", text: app.plural("devicesMoneyIn", count: hours))
            }
            actions
        }
        .nxCard(padding: 14)
    }
}

extension DeviceCard where Actions == EmptyView {
    init(device: AppDevice) {
        self.init(device: device) { EmptyView() }
    }
}

extension AppModel {
    /// « aujourd'hui 1 h 30 » : l'heure seule se lirait comme une durée.
    func lastSeen(_ date: Date) -> String {
        Calendar.current.isDateInToday(date) ? "\(t("today").lowercased()) \(clock(date))" : stamp(date)
    }

    /// « 20/11/2026 » (dans l'ordre de la langue).
    func longDate(_ date: Date) -> String {
        date.formatted(.dateTime.day().month(.twoDigits).year().locale(locale))
    }
}

// MARK: - Notifications

/// L'autorisation réelle du téléphone, et ce que NexisHub envoie. Les
/// messages sur l'argent et la sécurité ne se règlent pas un par un.
struct NotificationSettingsView: View {
    @Environment(AppModel.self) private var app
    @Environment(\.scenePhase) private var scenePhase
    @Environment(\.openURL) private var openURL
    @State private var status: UNAuthorizationStatus?

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                if let status {
                    let allowed = status == .authorized || status == .provisional || status == .ephemeral
                    VStack(alignment: .leading, spacing: 14) {
                        HStack(spacing: 12) {
                            Image(systemName: allowed ? "bell.badge.fill" : "bell.slash.fill")
                                .font(.system(size: 19, weight: .medium))
                                .foregroundStyle(allowed ? Nexis.ok : Nexis.danger)
                                .frame(width: 44, height: 44)
                                .background(allowed ? Color(light: 0xE3F5EA, dark: 0x12301F) : Color(light: 0xFDECEA, dark: 0x3A1715),
                                            in: RoundedRectangle(cornerRadius: 13, style: .continuous))
                                .accessibilityHidden(true)
                            VStack(alignment: .leading, spacing: 3) {
                                Text(app.t(allowed ? "notifAllowed" : "notifOff"))
                                    .font(.body(15.5, .bold)).foregroundStyle(Nexis.ink)
                                Text(app.t(allowed ? "notifAllowedSub" : "notifOffSub"))
                                    .font(.body(13, relativeTo: .footnote)).foregroundStyle(Nexis.muted)
                            }
                        }
                        .accessibilityElement(children: .combine)
                        if status == .notDetermined {
                            Button { Task { await ask() } } label: { WideLabel(text: app.t("notifAllow")) }
                                .nxProminentButton()
                        } else if !allowed {
                            Button {
                                if let url = URL(string: UIApplication.openNotificationSettingsURLString) { openURL(url) }
                            } label: { WideLabel(text: app.t("notifOpenSettings")) }
                                .nxProminentButton()
                        }
                    }
                    .nxCard(padding: 14)
                }
                SectionHeader(text: app.t("notifWhatTitle")).padding(.top, 6)
                VStack(alignment: .leading, spacing: 0) {
                    ForEach(Array(kinds.enumerated()), id: \.offset) { index, kind in
                        Label { Text(app.t(kind.key)).font(.body(15)).foregroundStyle(Nexis.ink) } icon: {
                            Image(systemName: kind.symbol).foregroundStyle(Nexis.accent)
                        }
                        .padding(.vertical, 12)
                        if index < kinds.count - 1 { Divider() }
                    }
                }
                .padding(.horizontal, 16)
                .background(Nexis.surface, in: RoundedRectangle(cornerRadius: 20, style: .continuous))
                .overlay(RoundedRectangle(cornerRadius: 20, style: .continuous).strokeBorder(Nexis.line, lineWidth: 0.5))
                InfoNote(text: app.t("notifAlwaysHint"), systemImage: "lock.shield.fill")
            }
            .flowScreen()
        }
        .flowTitle(app.t("notifications"))
        .task { await refresh() }
        .onChange(of: scenePhase) { _, phase in
            if phase == .active { Task { await refresh() } }
        }
    }

    private var kinds: [(key: String, symbol: String)] {
        [("notifQuotes", "doc.text"), ("notifMission", "figure.walk"), ("notifMoney", "banknote"),
         ("notifDisputes", "exclamationmark.bubble"), ("notifSecurity", "iphone.badge.exclamationmark")]
    }

    private func refresh() async {
        status = await UNUserNotificationCenter.current().notificationSettings().authorizationStatus
    }

    private func ask() async {
        _ = try? await UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .badge, .sound])
        await refresh()
    }
}

// MARK: - Aide et litiges

struct HelpView: View {
    @Environment(AppModel.self) private var app
    @Environment(MissionFlow.self) private var flow
    @State private var disputes: [Mission]?

    private let questions: [(question: String, answer: String)] = [
        ("faqPaidQ", "faqPaidA"), ("faqReportQ", "faqReportA"), ("faqContestQ", "faqContestA"),
        ("faqSettleQ", "faqSettleA"), ("faqDeviceQ", "faqDeviceA"),
    ]

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                SectionHeader(text: app.t("helpMyDisputes"))
                if let disputes {
                    if disputes.isEmpty {
                        Text(app.t("helpNoDispute")).font(.body(14.5)).foregroundStyle(Nexis.muted)
                            .frame(maxWidth: .infinity).padding(14)
                    }
                    ForEach(disputes) { mission in
                        Button { flow.push(.dispute(mission.id)) } label: {
                            HStack(spacing: 12) {
                                ServiceTile(mission, size: 44)
                                VStack(alignment: .leading, spacing: 4) {
                                    Text(app.place(mission)).font(.body(15.5, .bold)).foregroundStyle(Nexis.ink)
                                    if let name = mission.providerName {
                                        Text(name).font(.body(13, relativeTo: .footnote)).foregroundStyle(Nexis.muted)
                                    }
                                    PaymentPill(state: mission.payment)
                                }
                                Spacer(minLength: 8)
                                Image(systemName: "chevron.right").font(.system(size: 13, weight: .semibold))
                                    .foregroundStyle(Nexis.muted)
                            }
                            .nxCard(padding: 14)
                            .contentShape(Rectangle())
                        }
                        .buttonStyle(.plain)
                    }
                }
                SectionHeader(text: app.t("helpQuestions")).padding(.top, 6)
                VStack(alignment: .leading, spacing: 0) {
                    ForEach(Array(questions.enumerated()), id: \.offset) { index, item in
                        DisclosureGroup {
                            Text(app.t(item.answer))
                                .font(.body(14.5)).foregroundStyle(Nexis.muted).lineSpacing(3)
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .padding(.bottom, 12)
                        } label: {
                            Text(app.t(item.question)).font(.body(15, .semibold)).foregroundStyle(Nexis.ink)
                                .multilineTextAlignment(.leading)
                                .padding(.vertical, 12)
                        }
                        .tint(Nexis.accent)
                        if index < questions.count - 1 { Divider() }
                    }
                }
                .padding(.horizontal, 16)
                .background(Nexis.surface, in: RoundedRectangle(cornerRadius: 20, style: .continuous))
                .overlay(RoundedRectangle(cornerRadius: 20, style: .continuous).strokeBorder(Nexis.line, lineWidth: 0.5))
            }
            .flowScreen()
        }
        .bottomActions {
            Button { flow.comingSoon = SheetTitle(app.t("writeNexis")) } label: {
                WideLabel(text: app.t("writeNexis"), systemImage: "bubble.left.and.bubble.right")
            }
            .nxProminentButton()
        }
        .flowTitle(app.t("helpDisputes"))
        .task(id: app.revision) {
            disputes = (try? await app.repository.missions())?.filter { $0.status == .disputed }
        }
    }
}

// MARK: - Conditions d'utilisation

extension AppModel {
    func legalTitle(_ key: LegalDocumentKey) -> String {
        switch key {
        case .cgu: return t("legalCgu")
        case .providerTerms: return t("legalProviderTerms")
        }
    }
}

struct LegalView: View {
    @Environment(AppModel.self) private var app
    @State private var documents: [LegalDocument]?
    @State private var reading: LegalDocumentKey?

    var body: some View {
        Group {
            if let documents {
                ScrollView {
                    VStack(alignment: .leading, spacing: 14) {
                        ForEach(documents) { document in
                            VStack(alignment: .leading, spacing: 10) {
                                Text(app.legalTitle(document.key)).font(.body(15.5, .bold)).foregroundStyle(Nexis.ink)
                                Text(app.t("termsVersion", ["date": app.longDate(document.version)]))
                                    .font(.body(13, relativeTo: .footnote)).foregroundStyle(Nexis.muted)
                                HStack {
                                    if let accepted = document.acceptedAt {
                                        Pill(tone: .ok, systemImage: "checkmark",
                                             text: app.t("legalAcceptedOn", ["date": app.longDate(accepted)]))
                                    } else {
                                        Pill(tone: .warn, systemImage: "exclamationmark", text: app.t("legalToAccept"))
                                    }
                                    Spacer()
                                    Button(app.t("legalRead")) { reading = document.key }
                                        .font(.body(15, .semibold)).tint(Nexis.accent)
                                }
                            }
                            .nxCard(padding: 14)
                        }
                    }
                    .flowScreen()
                }
            } else {
                FlowLoading(label: app.t("legalTerms"))
            }
        }
        .flowTitle(app.t("legalTerms"))
        .task(id: app.revision) { documents = try? await app.repository.legalDocuments() }
        .sheet(item: Binding(get: { reading.map(LegalReading.init) }, set: { reading = $0?.key })) { item in
            LegalReader(key: item.key)
        }
    }
}

private struct LegalReading: Identifiable {
    let key: LegalDocumentKey
    var id: String { key.rawValue }
}

/// Le texte exact de la version en vigueur. Tant qu'aucune version n'est
/// publiée (aperçu), l'écran le dit.
struct LegalReader: View {
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    let key: LegalDocumentKey
    @State private var text: LegalText?

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 12) {
                    if let text {
                        Text(app.t("termsVersion", ["date": app.longDate(text.version)]))
                            .font(.body(13)).foregroundStyle(Nexis.muted)
                        Text(text.text ?? app.t("signupDemoTerms")).font(.body(16)).foregroundStyle(Nexis.ink)
                            .textSelection(.enabled)
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(20)
            }
            .navigationTitle(app.legalTitle(key))
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) { Button(app.t("close")) { dismiss() } }
            }
            .task { text = try? await app.repository.legalText(key) }
        }
    }
}

// MARK: - Devenir prestataire

struct BecomeProviderView: View {
    @Environment(AppModel.self) private var app
    @Environment(MissionFlow.self) private var flow
    @State private var step = 1
    @State private var catalog: [CatalogService] = []
    @State private var services: Set<String> = []
    @State private var communes: Set<String> = []
    @State private var identity = IdentityDraft()
    @State private var accepted = false
    @State private var readingTerms = false
    @State private var busy = false
    @State private var failed = false
    @State private var sent = false

    private let total = 4

    var body: some View {
        Group {
            if sent { sentView } else { stepsView }
        }
        .flowTitle(app.t("becomeProvider"))
        .navigationBarBackButtonHidden(step > 1 && !sent)
        .toolbar {
            if step > 1 && !sent {
                ToolbarItem(placement: .topBarLeading) {
                    Button { withAnimation(.snappy) { step -= 1 } } label: {
                        Image(systemName: "chevron.backward").font(.system(size: 17, weight: .semibold))
                    }
                    .accessibilityLabel(app.t("back"))
                    .disabled(busy)
                }
            }
        }
        .task { catalog = (try? await app.repository.serviceCatalog()) ?? [] }
        .sheet(isPresented: $readingTerms) { LegalReader(key: .providerTerms) }
        .onAppear { if let capture = app.capture, IdentityDemo.captures.contains(capture) { step = 3 } }
    }

    private var stepReady: Bool {
        switch step {
        case 1: return !services.isEmpty
        case 2: return !communes.isEmpty
        case 3: return identity.capture != nil
        default: return accepted
        }
    }

    private var stepsView: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                VStack(alignment: .leading, spacing: 8) {
                    Text(app.t("becomeStep", ["step": String(step), "total": String(total)]))
                        .font(.body(13, .semibold, relativeTo: .footnote)).foregroundStyle(Nexis.accent)
                    ProgressView(value: Double(step), total: Double(total)).tint(Nexis.brand)
                        .accessibilityHidden(true)
                }
                switch step {
                case 1: servicesStep
                case 2: communesStep
                case 3: identityStep
                default: termsStep
                }
                if failed {
                    Text(app.t("becomeFailed")).font(.body(14)).foregroundStyle(Nexis.danger)
                }
            }
            .flowScreen()
        }
        .bottomActions {
            Button {
                if step < total { withAnimation(.snappy) { step += 1 } } else { Task { await send() } }
            } label: {
                BusyLabel(text: app.t(step < total ? "nextStep" : "becomeSend"), busy: busy)
            }
            .nxProminentButton()
            .disabled(!stepReady || busy)
        }
    }

    private var servicesStep: some View {
        VStack(alignment: .leading, spacing: 12) {
            if step == 1 {
                Text(app.t("becomeIntro")).font(.body(14.5)).foregroundStyle(Nexis.muted).lineSpacing(3)
            }
            StepHeading(title: app.t("becomeServices"), hint: app.t("becomeServicesHint"))
            ForEach(catalog) { item in
                CheckRow(title: item.name(app.language), selected: services.contains(item.id)) {
                    ServiceTile(item, size: 38)
                } action: {
                    if services.contains(item.id) { services.remove(item.id) } else { services.insert(item.id) }
                }
            }
        }
    }

    private var communesStep: some View {
        VStack(alignment: .leading, spacing: 12) {
            StepHeading(title: app.t("becomeCommunes"), hint: app.t("becomeCommunesHint"))
            WrapLayout {
                ForEach(app.repository.communes, id: \.self) { commune in
                    ToggleChip(label: commune, selected: communes.contains(commune)) {
                        if communes.contains(commune) { communes.remove(commune) } else { communes.insert(commune) }
                    }
                }
            }
        }
    }

    private var identityStep: some View {
        VStack(alignment: .leading, spacing: 12) {
            StepHeading(title: app.t("becomeIdentity"), hint: nil)
            IdentityStep(draft: $identity)
        }
    }

    private var termsStep: some View {
        VStack(alignment: .leading, spacing: 12) {
            StepHeading(title: app.t("legalProviderTerms"), hint: nil)
            VStack(alignment: .leading, spacing: 12) {
                Text(app.t("termsVersion", ["date": app.longDate(app.repository.providerTermsVersion)]))
                    .font(.body(13, relativeTo: .footnote)).foregroundStyle(Nexis.muted)
                Button(app.t("becomeReadTerms")) { readingTerms = true }
                    .font(.body(15, .semibold)).tint(Nexis.accent)
                Divider()
                Toggle(app.t("becomeAcceptTerms"), isOn: $accepted)
                    .font(.body(15))
                    .tint(Nexis.brand)
                    .disabled(busy)
            }
            .nxCard(padding: 14)
        }
    }

    private var sentView: some View {
        ScrollView {
            VStack(spacing: 10) {
                Image(systemName: "checkmark.seal.fill")
                    .font(.system(size: 38, weight: .medium))
                    .foregroundStyle(Nexis.ok)
                    .frame(width: 96, height: 96)
                    .background(Circle().fill(Color(light: 0xE3F5EA, dark: 0x12301F)))
                    .padding(.vertical, 16)
                    .accessibilityHidden(true)
                Text(app.t("becomeSentTitle")).font(.title(21)).foregroundStyle(Nexis.ink)
                Text(app.t("becomeSentText")).font(.body(15)).foregroundStyle(Nexis.muted)
                    .multilineTextAlignment(.center).lineSpacing(3)
            }
            .frame(maxWidth: .infinity)
            .flowScreen()
            .padding(.top, 30)
        }
        .bottomActions {
            Button { flow.restart(at: nil) } label: { WideLabel(text: app.t("back")) }
                .nxProminentButton()
        }
    }

    private func send() async {
        guard let capture = identity.capture else { return }
        busy = true
        failed = false
        do {
            try await app.repository.applyAsProvider(
                services: catalog.map(\.id).filter(services.contains), communes: communes.sorted(),
                identity: capture,
                acceptedTermsVersion: accepted ? app.repository.providerTermsVersion : nil)
            app.dataChanged()
            withAnimation(.snappy) { sent = true }
        } catch {
            failed = true
        }
        busy = false
    }
}

private struct StepHeading: View {
    let title: String
    let hint: String?

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(title).font(.title(19)).foregroundStyle(Nexis.ink).accessibilityAddTraits(.isHeader)
            if let hint { Text(hint).font(.body(14)).foregroundStyle(Nexis.muted) }
        }
        .padding(.top, 4)
    }
}

/// Ligne à cocher (plusieurs choix possibles).
private struct CheckRow<Leading: View>: View {
    let title: String
    let selected: Bool
    @ViewBuilder var leading: Leading
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 12) {
                leading
                Text(title).font(.body(15, selected ? .semibold : .medium)).foregroundStyle(Nexis.ink)
                Spacer(minLength: 8)
                Image(systemName: selected ? "checkmark.circle.fill" : "circle")
                    .font(.system(size: 22))
                    .foregroundStyle(selected ? Nexis.brand : Color(light: 0xC9D0DB, dark: 0x3A4A66))
            }
            .padding(.horizontal, 14)
            .padding(.vertical, 10)
            .background(Nexis.surface, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 16, style: .continuous)
                .strokeBorder(selected ? Nexis.brand : Nexis.line, lineWidth: selected ? 2 : 0.5))
            .contentShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
        }
        .buttonStyle(.plain)
        .accessibilityAddTraits(selected ? .isSelected : [])
    }
}

/// Puce à cocher (communes).
private struct ToggleChip: View {
    let label: String
    let selected: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 5) {
                if selected { Image(systemName: "checkmark").font(.system(size: 11, weight: .bold)) }
                Text(label).font(.body(14, .semibold, relativeTo: .subheadline))
            }
            .foregroundStyle(selected ? Nexis.accent : Nexis.ink)
            .padding(.horizontal, 13).padding(.vertical, 9)
            .background(selected ? Nexis.soft : Nexis.surface, in: Capsule())
            .overlay(Capsule().strokeBorder(selected ? Nexis.brand : Nexis.line, lineWidth: selected ? 1.5 : 1))
        }
        .buttonStyle(.plain)
        .accessibilityAddTraits(selected ? .isSelected : [])
    }
}
