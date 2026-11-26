import SwiftUI

// Espace prestataire, repris des écrans Flutter
// (app_mobile/lib/screens/provider) : accueil « En service », demandes,
// envoi d'un devis et déroulé d'une mission payée.

// MARK: - Prix tapé

enum PriceInput {
    /// Lit le prix tapé : des francs entiers, ou des dollars avec au plus
    /// deux décimales. Rien de lisible ou zéro : pas de prix. Même règle que
    /// l'app Flutter (`parsePrice`) ; le serveur revérifie.
    static func parse(_ text: String, _ currency: Currency) -> Money? {
        let clean = text.filter { !$0.isWhitespace }.replacingOccurrences(of: ",", with: ".")
        guard !clean.isEmpty else { return nil }
        switch currency {
        case .cdf:
            guard clean.count <= 9, clean.allSatisfy(\.isASCIIDigit), let value = Int(clean), value > 0 else { return nil }
            return Money(value, .cdf)
        case .usd:
            let parts = clean.split(separator: ".", omittingEmptySubsequences: false)
            guard (1...2).contains(parts.count),
                  (1...7).contains(parts[0].count), parts[0].allSatisfy(\.isASCIIDigit) else { return nil }
            var cents = Int(parts[0])! * 100
            if parts.count == 2 {
                let decimals = parts[1]
                guard (1...2).contains(decimals.count), decimals.allSatisfy(\.isASCIIDigit) else { return nil }
                cents += Int(decimals.padding(toLength: 2, withPad: "0", startingAt: 0))!
            }
            return cents > 0 ? Money(cents, .usd) : nil
        }
    }

    /// Ce que le champ garde pendant la frappe : les francs groupés par
    /// milliers (« 25 000 »), les dollars avec leur virgule.
    static func typed(_ text: String, _ currency: Currency) -> String {
        switch currency {
        case .cdf:
            let digits = String(text.filter(\.isASCIIDigit).prefix(9))
            var grouped = ""
            for (index, digit) in digits.enumerated() {
                if index > 0, (digits.count - index) % 3 == 0 { grouped.append(" ") }
                grouped.append(digit)
            }
            return grouped
        case .usd:
            return String(text.filter { $0.isASCIIDigit || $0 == "." || $0 == "," }.prefix(10))
        }
    }
}

private extension Character {
    var isASCIIDigit: Bool { isASCII && isNumber }
}

// MARK: - Client / Prestataire

/// Passe de l'espace client à l'espace prestataire (même compte).
struct SpaceSwitch: View {
    @Environment(AppModel.self) private var app

    var body: some View {
        Picker(app.t("spaceProvider"), selection: Binding(get: { app.providerSpace },
                                                          set: { app.providerSpace = $0 })) {
            Text(app.t("spaceClient")).tag(false)
            Text(app.t("spaceProvider")).tag(true)
        }
        .pickerStyle(.segmented)
    }
}

extension AppModel {
    /// « Limete et Gombe », « Limete, Gombe et Ngaliema ».
    func communesList(_ communes: [String]) -> String {
        guard let last = communes.last else { return "" }
        guard communes.count > 1 else { return last }
        return t("andList", ["head": communes.dropLast().joined(separator: ", "), "last": last])
    }

    func requestAge(_ date: Date) -> String {
        let minutes = max(0, Int(Date.now.timeIntervalSince(date) / 60))
        if minutes < 60 { return t("minutesAgo", ["count": String(minutes)]) }
        return t("hoursAgo", ["count": String(minutes / 60)])
    }

    func jobStatus(_ job: ProviderJob) -> String {
        let name = job.clientFirstName
        if job.steps[.finished] != nil { return t("jobWaitingClient", ["name": name]) }
        if job.steps[.arrived] != nil { return t("jobOnSite") }
        if job.arrivalSignaled { return t("jobArrivalPending", ["name": name]) }
        if job.steps[.leftHome] != nil { return t("jobOnTheWay") }
        return t("jobToStart")
    }
}

// MARK: - 11. Accueil prestataire

struct ProviderHomeView: View {
    @Environment(AppModel.self) private var app
    let onTab: (AppTab) -> Void
    @State private var flow = MissionFlow()
    @State private var home: ProviderHome?
    @State private var profile: Profile?
    @State private var saving = false

    var body: some View {
        NavigationStack(path: $flow.path) {
            Group {
                if let home { content(home) } else { FlowLoading(label: app.t("spaceProvider")) }
            }
            .background(Nexis.bg)
            .greetingHeader(greeting)
            .missionDestinations()
        }
        .missionFlow(flow, tab: .home)
        .task(id: app.revision) {
            home = try? await app.repository.providerHome()
            profile = try? await app.repository.profile()
        }
        .onAppear {
            if let routes = MissionRoute.forCapture(app.capture), flow.path.isEmpty,
               MissionRoute.providerCaptures.contains(app.capture ?? "") {
                flow.path = routes
            }
        }
    }

    private var greeting: String {
        guard let profile else { return "NexisHub" }
        let hour = Calendar.current.component(.hour, from: .now)
        return app.t(hour < 12 ? "helloHome" : "eveningHome", ["name": profile.firstName])
    }

    private func content(_ home: ProviderHome) -> some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                SpaceSwitch()
                HStack(spacing: 12) {
                    Circle().fill(home.inService ? Nexis.ok : Color(hex: 0xC9D0DB)).frame(width: 9, height: 9)
                    VStack(alignment: .leading, spacing: 2) {
                        Text(app.t(home.inService ? "inService" : "offService"))
                            .font(.body(15, .bold)).foregroundStyle(Nexis.ink)
                        Text(home.inService ? app.t("inServiceSub", ["communes": app.communesList(home.communes)])
                                            : app.t("offServiceSub"))
                            .font(.body(13, relativeTo: .footnote)).foregroundStyle(Nexis.muted)
                    }
                    Spacer(minLength: 8)
                    Toggle(app.t("inService"), isOn: Binding(get: { home.inService },
                                                             set: { value in Task { await setInService(value) } }))
                        .labelsHidden()
                        .tint(Nexis.ok)
                        .disabled(saving)
                }
                .nxCard(padding: 14)
                moneyCard(home)
                HStack(alignment: .firstTextBaseline) {
                    Text(app.t("newRequests")).font(.title(17)).foregroundStyle(Nexis.ink)
                    Spacer()
                    Button(app.t("seeAll")) { onTab(.missions) }
                        .font(.body(14, .semibold))
                        .tint(Nexis.accent)
                }
                .padding(.top, 6)
                if !home.inService {
                    InfoNote(text: app.t("offServiceHint"))
                } else if home.requests.isEmpty {
                    EmptyLine(text: app.t("noRequests"))
                } else {
                    ForEach(home.requests) { request in RequestCard(request: request) }
                }
                if !home.jobs.isEmpty {
                    Text(app.t("jobsInProgress")).font(.title(17)).foregroundStyle(Nexis.ink).padding(.top, 6)
                    ForEach(home.jobs) { job in JobCard(job: job) }
                }
            }
            .padding(.horizontal, 18)
            .padding(.bottom, 24)
        }
    }

    private func moneyCard(_ home: ProviderHome) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("\(app.t("available")) · \(home.available.currency == .cdf ? "FC" : "USD")")
                .font(.body(13, relativeTo: .footnote)).foregroundStyle(.white.opacity(0.85))
            Text(app.amountsHidden ? "•••" : app.money(home.available))
                .font(.title(28, .semibold, relativeTo: .largeTitle))
                .foregroundStyle(.white)
                .monospacedDigit()
                .minimumScaleFactor(0.6)
                .lineLimit(1)
            Label(app.t("securedUntilConfirm", ["amount": app.amountsHidden ? "•••" : app.money(home.secured)]),
                  systemImage: "checkmark.shield.fill")
                .font(.body(13, relativeTo: .footnote))
                .foregroundStyle(.white)
                .padding(.top, 4)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(18)
        .background(LinearGradient(stops: [.init(color: Nexis.halo, location: 0),
                                           .init(color: Nexis.gradientStart, location: 0.45),
                                           .init(color: Nexis.gradientEnd, location: 1)],
                                   startPoint: .topLeading, endPoint: .bottomTrailing),
                    in: RoundedRectangle(cornerRadius: 24, style: .continuous))
        .accessibilityElement(children: .combine)
    }

    private func setInService(_ value: Bool) async {
        saving = true
        defer { saving = false }
        do {
            try await app.repository.setInService(value)
            app.dataChanged()
        } catch {
            flow.say(app.t("actionFailed"))
        }
    }
}

private struct EmptyLine: View {
    let text: String

    var body: some View {
        Text(text)
            .font(.body(14.5)).foregroundStyle(Nexis.muted)
            .multilineTextAlignment(.center)
            .frame(maxWidth: .infinity)
            .padding(16)
    }
}

// MARK: - Missions côté prestataire

struct ProviderMissionsView: View {
    @Environment(AppModel.self) private var app
    @State private var flow = MissionFlow()
    @State private var home: ProviderHome?

    var body: some View {
        NavigationStack(path: $flow.path) {
            ScrollView {
                VStack(alignment: .leading, spacing: 14) {
                    if let home {
                        Text(app.t("jobsInProgress")).font(.title(17)).foregroundStyle(Nexis.ink)
                        if home.jobs.isEmpty { EmptyLine(text: app.t("noMissions")) }
                        ForEach(home.jobs) { job in JobCard(job: job) }
                        Text(app.t("newRequests")).font(.title(17)).foregroundStyle(Nexis.ink).padding(.top, 6)
                        if home.requests.isEmpty { EmptyLine(text: app.t("noRequests")) }
                        ForEach(home.requests) { request in RequestCard(request: request) }
                    }
                }
                .padding(.horizontal, 18)
                .padding(.bottom, 24)
            }
            .background(Nexis.bg)
            .navigationTitle(app.t("myMissions"))
            .missionDestinations()
        }
        .missionFlow(flow, tab: .missions)
        .task(id: app.revision) { home = try? await app.repository.providerHome() }
    }
}

// MARK: - Cartes

/// Une demande de client : « Nouveau » et le bouton « Envoyer un devis » les
/// dix premières minutes, l'âge ensuite.
struct RequestCard: View {
    @Environment(AppModel.self) private var app
    @Environment(MissionFlow.self) private var flow
    let request: ProviderRequest

    var body: some View {
        let fresh = Date.now.timeIntervalSince(request.receivedAt) < 600 && !request.quoted
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 12) {
                ServiceTile(request.service, size: 44)
                VStack(alignment: .leading, spacing: 3) {
                    Text("\(request.service.name(app.language)) · \(request.commune)")
                        .font(.body(15.5, .bold)).foregroundStyle(Nexis.ink).lineLimit(1)
                    Text(request.summary)
                        .font(.body(13, relativeTo: .footnote)).foregroundStyle(Nexis.muted).lineLimit(1)
                }
                Spacer(minLength: 8)
                if request.quoted {
                    Pill(tone: .ok, systemImage: "checkmark", text: app.t("quoteSentPill"))
                } else if fresh {
                    Text(app.t("newPill"))
                        .font(.body(11, .bold, relativeTo: .caption2))
                        .foregroundStyle(Nexis.ok)
                        .padding(.horizontal, 8).padding(.vertical, 3)
                        .background(Color(light: 0xE3F5EA, dark: 0x16351F), in: Capsule())
                } else {
                    Pill(tone: .wait, systemImage: "clock", text: app.requestAge(request.receivedAt))
                }
            }
            if fresh {
                Button { flow.push(.sendQuote(request.missionId)) } label: { WideLabel(text: app.t("sendAQuote")) }
                    .nxProminentButton()
            }
        }
        .nxCard(padding: 14)
        .contentShape(Rectangle())
        .onTapGesture { if !request.quoted { flow.push(.sendQuote(request.missionId)) } }
        .accessibilityElement(children: .combine)
        .accessibilityAddTraits(request.quoted ? [] : .isButton)
    }
}

/// Une mission payée, côté prestataire : où elle en est.
struct JobCard: View {
    @Environment(AppModel.self) private var app
    @Environment(MissionFlow.self) private var flow
    let job: ProviderJob

    var body: some View {
        Button { flow.push(.job(job.missionId)) } label: {
            HStack(spacing: 12) {
                ServiceTile(job.service, size: 44)
                VStack(alignment: .leading, spacing: 3) {
                    Text("\(job.service.name(app.language)) · \(job.commune)")
                        .font(.body(15.5, .bold)).foregroundStyle(Nexis.ink).lineLimit(1)
                    Text(app.jobStatus(job))
                        .font(.body(13, relativeTo: .footnote)).foregroundStyle(Nexis.muted).lineLimit(1)
                }
                Spacer(minLength: 8)
                PaymentPill(state: .secured, text: app.money(job.amount))
            }
            .nxCard(padding: 14)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
    }
}

// MARK: - 12. Envoyer un devis

struct SendQuoteView: View {
    @Environment(AppModel.self) private var app
    @Environment(MissionFlow.self) private var flow
    let missionId: Int
    @State private var request: ProviderRequest?
    @State private var price = ""
    @State private var currency: Currency = .cdf
    @State private var slot: Date?
    @State private var custom: Date?
    @State private var pickingOther = false
    @State private var otherChoice = Date.now.addingTimeInterval(3600)
    @State private var busy = false
    @FocusState private var typing: Bool

    var body: some View {
        Group {
            if let request { content(request) } else { FlowLoading(label: app.t("sendAQuote")) }
        }
        .flowTitle(app.t("sendAQuote"),
                   subtitle: request.map { "\($0.service.name(app.language)) · \($0.commune)" })
        .task(id: app.revision) { if !busy { request = try? await app.repository.providerRequest(missionId: missionId) } }
        .sheet(isPresented: $pickingOther) { otherSlotSheet }
    }

    private func content(_ request: ProviderRequest) -> some View {
        let parsed = PriceInput.parse(price, currency)
        let ready = parsed != nil && slot != nil && !request.quoted
        let slots = request.slotChoices + [custom].compactMap { $0 }
        return ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                VStack(alignment: .leading, spacing: 12) {
                    Text(request.description)
                        .font(.body(14.5)).foregroundStyle(Nexis.ink).lineSpacing(3)
                    if request.photos > 0 {
                        HStack(spacing: 8) {
                            ForEach(0..<min(request.photos, 3), id: \.self) { _ in
                                PhotoSlot(systemImage: "photo", label: app.plural("photosCount", count: request.photos)) {
                                    flow.comingSoon = SheetTitle(app.plural("photosCount", count: request.photos))
                                }
                            }
                        }
                    }
                    WrapLayout {
                        Pill(tone: .wait, systemImage: "calendar", text: request.wanted)
                        Pill(tone: .wait, systemImage: "mappin", text: request.commune)
                    }
                }
                .nxCard()
                Text(app.t("yourPrice")).font(.body(16, .semibold, relativeTo: .headline)).foregroundStyle(Nexis.ink)
                    .padding(.top, 4)
                VStack(alignment: .leading, spacing: 4) {
                    Text(app.t("priceAsked")).font(.body(12.5, .semibold, relativeTo: .caption1)).foregroundStyle(Nexis.muted)
                    HStack {
                        TextField("0", text: $price)
                            .font(.title(24, .semibold, relativeTo: .title2))
                            .foregroundStyle(Nexis.ink)
                            .keyboardType(currency == .cdf ? .numberPad : .decimalPad)
                            .focused($typing)
                            .disabled(busy)
                            .onChange(of: price) { _, value in
                                let kept = PriceInput.typed(value, currency)
                                if kept != value { price = kept }
                            }
                            .accessibilityLabel(app.t("priceAsked"))
                        Menu {
                            Picker(app.t("changeCurrency"), selection: $currency) {
                                Text("FC").tag(Currency.cdf)
                                Text("USD").tag(Currency.usd)
                            }
                        } label: {
                            HStack(spacing: 3) {
                                Text(currency == .cdf ? "FC" : "USD").font(.body(15, .semibold))
                                Image(systemName: "chevron.down").font(.system(size: 11, weight: .semibold))
                            }
                            .foregroundStyle(Nexis.muted)
                            .padding(6)
                        }
                        .accessibilityLabel(app.t("changeCurrency"))
                        .disabled(busy)
                        .onChange(of: currency) { price = "" }
                    }
                }
                .padding(.horizontal, 14).padding(.vertical, 12)
                .background(Nexis.surface, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
                .overlay(RoundedRectangle(cornerRadius: 16, style: .continuous)
                    .strokeBorder(typing ? Nexis.brand : Nexis.line, lineWidth: typing ? 2 : 1))
                .onTapGesture { typing = true }
                Text(app.t("yourSlot")).font(.body(16, .semibold, relativeTo: .headline)).foregroundStyle(Nexis.ink)
                    .padding(.top, 4)
                WrapLayout {
                    ForEach(slots, id: \.self) { choice in
                        SlotChip(label: app.slot(choice, capital: true), selected: slot == choice) { slot = choice }
                            .disabled(busy)
                    }
                    SlotChip(label: app.t("otherSlot"), selected: false) { pickingOther = true }
                        .disabled(busy)
                }
            }
            .flowScreen()
        }
        .scrollDismissesKeyboard(.interactively)
        .bottomActions {
            Button { if let parsed { Task { await send(parsed) } } } label: {
                BusyLabel(text: app.t("sendTheQuote"), busy: busy)
            }
            .nxProminentButton()
            .disabled(!ready || busy)
        }
    }

    private var otherSlotSheet: some View {
        NavigationStack {
            DatePicker(app.t("otherSlot"), selection: $otherChoice,
                       in: Date.now...Date.now.addingTimeInterval(60 * 86_400),
                       displayedComponents: [.date, .hourAndMinute])
                .datePickerStyle(.graphical)
                .environment(\.locale, app.locale)
                .tint(Nexis.brand)
                .padding()
                .navigationTitle(app.t("yourSlot"))
                .navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItem(placement: .cancellationAction) {
                        Button(app.t("close")) { pickingOther = false }
                    }
                    ToolbarItem(placement: .confirmationAction) {
                        Button(app.t("confirmCode")) {
                            if otherChoice > .now {
                                custom = otherChoice
                                slot = otherChoice
                            }
                            pickingOther = false
                        }
                    }
                }
        }
        .presentationDetents([.large])
    }

    private func send(_ parsed: Money) async {
        guard let slot else { return }
        busy = true
        typing = false
        do {
            try await app.repository.sendQuote(missionId: missionId, price: parsed, slot: slot)
            app.dataChanged()
            if !flow.path.isEmpty { flow.path.removeLast() }
            flow.say(app.t("quoteSentToast"))
        } catch {
            busy = false
            flow.say(app.t("quoteFailed"))
        }
    }
}

private struct SlotChip: View {
    let label: String
    let selected: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Text(label)
                .font(.body(14, .semibold, relativeTo: .subheadline))
                .foregroundStyle(selected ? Nexis.accent : Nexis.ink)
                .padding(.horizontal, 13).padding(.vertical, 9)
                .background(selected ? Nexis.soft : Nexis.surface,
                            in: RoundedRectangle(cornerRadius: 12, style: .continuous))
                .overlay(RoundedRectangle(cornerRadius: 12, style: .continuous)
                    .strokeBorder(selected ? Nexis.brand : Nexis.line, lineWidth: selected ? 1.5 : 1))
        }
        .buttonStyle(.plain)
        .accessibilityAddTraits(selected ? .isSelected : [])
    }
}

// MARK: - 13. Mission côté prestataire

/// L'arrivée suit la règle du serveur : « Je suis arrivé » ne confirme rien
/// seul. Le client confirme sur son téléphone, ou le prestataire tape son
/// code de présence (cinq essais au plus).
struct ProviderJobView: View {
    @Environment(AppModel.self) private var app
    @Environment(MissionFlow.self) private var flow
    let missionId: Int
    @State private var job: ProviderJob?
    @State private var busy = false
    @State private var code = ""
    @State private var codeError: String?

    var body: some View {
        Group {
            if let job { content(job) } else { FlowLoading(label: app.t("jobTitle")) }
        }
        .flowTitle(app.t("jobTitle"), subtitle: job.map { "\($0.service.name(app.language)) · \($0.commune)" })
        .task(id: app.revision) { job = try? await app.repository.providerJob(missionId: missionId) }
    }

    private func content(_ job: ProviderJob) -> some View {
        let name = job.clientFirstName
        let steps = job.steps
        let arrived = steps[.arrived] != nil
        let finished = steps[.finished] != nil
        let waitingArrival = job.arrivalSignaled && !arrived
        let current = ProviderStep.allCases.first { steps[$0] == nil } ?? .finished
        func item(_ title: String, sub: String? = nil, _ step: ProviderStep) -> StepItem {
            StepItem(title: title, sub: sub, time: steps[step].map(app.clock),
                     state: steps[step] != nil ? .done : (step == current ? .now : .todo))
        }
        return ScrollView {
            VStack(spacing: 14) {
                VStack(alignment: .leading, spacing: 12) {
                    PersonHeader(initials: job.clientInitials, color: job.clientColor, name: job.clientName,
                                 subtitle: job.place) {
                        RoundIconButton(systemImage: "ellipsis.message.fill", label: app.t("messageLabel")) {
                            flow.comingSoon = SheetTitle(app.t("messageLabel"))
                        }
                    }
                    PaymentPill(state: .secured, text: app.t("securedAmount", ["amount": app.money(job.amount)]))
                }
                .nxCard(padding: 14)
                if !finished {
                    HStack(spacing: 12) {
                        Image(systemName: "location.north.fill")
                            .font(.system(size: 15, weight: .semibold))
                            .foregroundStyle(Nexis.softInk)
                            .frame(width: 38, height: 38)
                            .background(Nexis.soft, in: Circle())
                            .accessibilityHidden(true)
                        VStack(alignment: .leading, spacing: 2) {
                            Text(app.t("shareLocation")).font(.body(15, .bold)).foregroundStyle(Nexis.ink)
                            Text(app.t("shareLocationSub", ["name": name]))
                                .font(.body(13, relativeTo: .footnote)).foregroundStyle(Nexis.muted)
                        }
                        Spacer(minLength: 8)
                        Toggle(app.t("shareLocation"), isOn: Binding(get: { job.sharing }, set: { value in
                            run { _ = try await app.repository.setSharing(missionId: job.missionId, value) }
                        }))
                        .labelsHidden()
                        .tint(Nexis.ok)
                        .disabled(busy)
                    }
                    .nxCard(padding: 14)
                }
                StepList(items: [
                    item(app.t("pStepPaid"), .clientPaid),
                    item(app.t("pStepLeft"), .leftHome),
                    item(app.t(arrived ? "pStepOnSite" : "pStepArrive"),
                         sub: arrived ? app.t("arrivalConfirmed")
                             : (waitingArrival ? app.t("arrivalWaitingSub", ["name": name]) : nil),
                         .arrived),
                    item(app.t("pStepDone"), .finished),
                ])
                .nxCard()
                if waitingArrival {
                    InfoNote(text: app.t("arrivalWaiting", ["name": name]))
                    if job.codeAttemptsLeft > 0 {
                        codeEntry(job)
                    } else {
                        InfoNote(text: app.t("codeLocked", ["name": name]), kind: .danger, systemImage: "lock.fill")
                    }
                }
                if finished {
                    InfoNote(text: app.t("finishedNote", ["name": name]), kind: .violet)
                }
            }
            .flowScreen()
        }
        .scrollDismissesKeyboard(.interactively)
        .bottomActions {
            if let primary = primaryAction(job, arrived: arrived, finished: finished, waitingArrival: waitingArrival) {
                Button { run(primary.action) } label: {
                    BusyLabel(text: primary.title, systemImage: primary.symbol, busy: busy)
                }
                .nxProminentButton()
                .disabled(busy)
            }
            Button { flow.comingSoon = SheetTitle(app.t("callClient", ["name": name])) } label: {
                Label(app.t("callClient", ["name": name]), systemImage: "phone")
                    .font(.body(16, .semibold))
            }
            .buttonStyle(OutlineButtonStyle())
        }
    }

    private struct Primary {
        let title: String
        let symbol: String
        let action: () async throws -> Void
    }

    private func primaryAction(_ job: ProviderJob, arrived: Bool, finished: Bool,
                               waitingArrival: Bool) -> Primary? {
        let repo = app.repository
        let id = job.missionId
        if finished || waitingArrival { return nil }
        if arrived {
            return Primary(title: app.t("btnFinished"), symbol: "checkmark") { _ = try await repo.finishJob(missionId: id) }
        }
        if job.steps[.leftHome] != nil {
            return Primary(title: app.t("btnArrived"), symbol: "mappin.and.ellipse") {
                _ = try await repo.signalArrival(missionId: id)
            }
        }
        return Primary(title: app.t("btnLeave"), symbol: "location.north.fill") {
            _ = try await repo.leaveForJob(missionId: id)
        }
    }

    private func codeEntry(_ job: ProviderJob) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(app.t("presenceCode")).font(.body(14.5, .semibold)).foregroundStyle(Nexis.ink)
            HStack(spacing: 10) {
                TextField("••••", text: $code)
                    .font(.title(22, .semibold))
                    .kerning(8)
                    .keyboardType(.numberPad)
                    .textContentType(.oneTimeCode)
                    .disabled(busy)
                    .padding(.horizontal, 14).padding(.vertical, 10)
                    .background(Nexis.bg, in: RoundedRectangle(cornerRadius: 12, style: .continuous))
                    .overlay(RoundedRectangle(cornerRadius: 12, style: .continuous).strokeBorder(Nexis.line))
                    .onChange(of: code) { _, value in
                        let digits = String(value.filter(\.isNumber).prefix(4))
                        if digits != value { code = digits }
                    }
                    .accessibilityLabel(app.t("presenceCode"))
                Button { sendCode(job) } label: {
                    Text(app.t("confirmCode")).font(.body(15, .semibold)).padding(.horizontal, 6)
                }
                .nxProminentButton()
                .disabled(code.count != 4 || busy)
            }
            if let codeError {
                Text(codeError).font(.body(13, .semibold, relativeTo: .footnote)).foregroundStyle(Nexis.danger)
            }
        }
        .nxCard()
    }

    private func sendCode(_ job: ProviderJob) {
        let entered = code
        run {
            let result = try await app.repository.enterPresenceCode(missionId: job.missionId, code: entered)
            let after = try await app.repository.providerJob(missionId: job.missionId)
            code = ""
            switch result {
            case .confirmed: codeError = nil
            case .wrongCode: codeError = app.plural("wrongCode", count: after.codeAttemptsLeft)
            case .locked: codeError = app.t("codeLocked", ["name": job.clientFirstName])
            }
        }
    }

    private func run(_ action: @escaping () async throws -> Void) {
        busy = true
        Task {
            do {
                try await action()
                app.dataChanged()
            } catch {
                flow.say(app.t("actionFailed"))
            }
            busy = false
        }
    }
}
