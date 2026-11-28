import SwiftUI

// Espace entreprise : création en quatre étapes puis suivi de la demande
// (envoyée, correction demandée, validée), et invitation reçue. Mêmes
// composants que « Devenir prestataire » : barre « Étape x sur 5 », cartes
// libellé / valeur, pastilles. L'identité ne se vérifie qu'une fois par
// personne : une personne déjà vérifiée n'a rien de plus à envoyer.

// MARK: - Pièces communes

/// Carte blanche à coins continus, comme les écrans d'inscription.
struct OrgFieldCard<Content: View>: View {
    @ViewBuilder var content: Content

    var body: some View {
        VStack(spacing: 0) { content }
            .background(Nexis.surface, in: RoundedRectangle(cornerRadius: 20, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 20, style: .continuous)
                .strokeBorder(Nexis.line, lineWidth: 0.5))
    }
}

/// Une rangée « libellé / valeur ».
struct OrgFieldRow<Value: View>: View {
    let label: String
    @ViewBuilder var value: Value

    var body: some View {
        HStack(spacing: 12) {
            Text(label)
                .font(.body(14)).foregroundStyle(Nexis.muted)
                .frame(width: 84, alignment: .leading)
                .accessibilityHidden(true)
            HStack { value }
                .font(.body(16, .medium))
                .foregroundStyle(Nexis.ink)
        }
        .padding(.horizontal, 16)
        .frame(minHeight: 54)
        .contentShape(Rectangle())
    }
}

/// Liste déroulante : un choix parmi plusieurs, sans occuper l'écran.
struct OrgMenuRow<T: Hashable>: View {
    let placeholder: String
    let options: [T]
    let selection: T?
    let title: (T) -> String
    let pick: (T) -> Void

    var body: some View {
        Menu {
            ForEach(options, id: \.self) { option in
                Button { pick(option) } label: {
                    if option == selection {
                        Label(title(option), systemImage: "checkmark")
                    } else {
                        Text(title(option))
                    }
                }
            }
        } label: {
            HStack(spacing: 12) {
                Text(selection.map(title) ?? placeholder)
                    .font(.body(16, .medium))
                    .foregroundStyle(selection == nil ? Nexis.muted : Nexis.ink)
                    .frame(maxWidth: .infinity, alignment: .leading)
                Image(systemName: "chevron.up.chevron.down")
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundStyle(Nexis.muted)
            }
            .padding(.horizontal, 16)
            .frame(minHeight: 54)
            .contentShape(Rectangle())
        }
    }
}

/// Petit titre au-dessus d'un groupe de puces.
struct OrgGroupLabel: View {
    let text: String

    var body: some View {
        Text(text)
            .font(.body(13, .semibold, relativeTo: .footnote))
            .foregroundStyle(Nexis.muted)
            .padding(.top, 6)
    }
}

/// Bandeau vert (identité déjà vérifiée) ou bleu (à vérifier).
struct OrgIdentityBanner: View {
    let done: Bool
    let title: String
    let text: String

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: done ? "checkmark.seal.fill" : "person.badge.shield.checkmark.fill")
                .font(.system(size: 20, weight: .semibold))
                .foregroundStyle(done ? Nexis.ok : Nexis.accent)
                .frame(width: 40, height: 40)
                .background(done ? Color(light: 0xE3F5EA, dark: 0x12301F) : Nexis.soft, in: Circle())
                .accessibilityHidden(true)
            VStack(alignment: .leading, spacing: 3) {
                Text(title).font(.body(15.5, .bold)).foregroundStyle(Nexis.ink)
                Text(text).font(.body(13.5, relativeTo: .footnote)).foregroundStyle(Nexis.muted)
                    .lineSpacing(2)
            }
            Spacer(minLength: 0)
        }
        .nxCard(padding: 14)
        .accessibilityElement(children: .combine)
    }
}

extension AppModel {
    func roleName(_ role: OrgRole) -> String {
        switch role {
        case .representative: return t("orgRoleRepresentative")
        case .manager: return t("orgRoleManager")
        case .accountant: return t("orgRoleAccountant")
        case .worker: return t("orgRoleWorker")
        }
    }

    func functionName(_ function: OrgFunction) -> String {
        switch function {
        case .manager: return t("orgFnManager")
        case .director: return t("orgFnDirector")
        case .owner: return t("orgFnOwner")
        case .accountant: return t("orgFnAccountant")
        case .other: return t("orgFormOther")
        }
    }

    func formName(_ form: OrgLegalForm) -> String {
        switch form {
        case .sarl: return "SARL"
        case .sarlu: return "SARLU"
        case .sa: return "SA"
        case .establishment: return t("orgFormEstablishment")
        case .other: return t("orgFormOther")
        }
    }

    func activityName(_ activity: OrgActivity) -> String {
        switch activity {
        case .orders: return t("orgActOrders")
        case .provides: return t("orgActProvides")
        case .both: return t("orgActBoth")
        }
    }

    func docTitle(_ kind: OrgDocKind) -> String {
        switch kind {
        case .rccm: return "RCCM"
        case .idnat: return "IDNAT"
        case .nif: return "NIF"
        }
    }

    func docSubtitle(_ kind: OrgDocKind) -> String {
        switch kind {
        case .rccm: return t("orgDocRccm")
        case .idnat: return t("orgDocIdnat")
        case .nif: return t("orgDocNif")
        }
    }

    /// « Aujourd'hui, 14 h 20 ».
    func sentStamp(_ date: Date) -> String { "\(day(date)), \(clock(date))" }
}

/// Charge une entreprise, puis dessine `content`. Tant qu'elle n'est pas
/// lue, les pictogrammes se relaient.
struct OrgLoader<Content: View>: View {
    @Environment(AppModel.self) private var app
    let orgId: Int
    @ViewBuilder var content: (Organization) -> Content
    @State private var org: Organization?

    var body: some View {
        Group {
            if let org { content(org) } else { FlowLoading(label: app.t("orgTitle")) }
        }
        .task(id: app.revision) { org = try? await app.repository.organization(id: orgId) }
    }
}

// MARK: - Création

struct OrgCreateView: View {
    @Environment(AppModel.self) private var app
    @Environment(MissionFlow.self) private var flow
    /// 0 = présentation, 1 à 4 = les étapes, puis « Demande envoyée ».
    @State private var step = 0
    @State private var draft = OrgDraft()
    @State private var identity = IdentityDraft()
    @State private var profile: Profile?
    @State private var accepted = false
    @State private var readingTerms = false
    @State private var busy = false
    @State private var failed = false
    @State private var sent: Organization?

    /// Quatre écrans de saisie, puis « Demande envoyée » : 5 étapes.
    private let total = 5

    private var identityVerified: Bool { profile?.isIdentityVerified ?? false }

    var body: some View {
        Group {
            if let sent {
                OrgStatusBody(org: sent)
            } else if step == 0 {
                introView
            } else {
                stepsView
            }
        }
        .flowTitle(app.t("orgTitle"))
        .navigationBarBackButtonHidden(step > 0 && sent == nil)
        .toolbar {
            if step > 0 && sent == nil {
                ToolbarItem(placement: .topBarLeading) {
                    Button { goBack() } label: {
                        Image(systemName: "chevron.backward").font(.system(size: 17, weight: .semibold))
                    }
                    .accessibilityLabel(app.t("back"))
                    .disabled(busy)
                }
            }
        }
        .sheet(isPresented: $readingTerms) { LegalReader(key: .orgTerms) }
        .task { profile = try? await app.repository.profile() }
        .onAppear(perform: openDemo)
    }

    /// Captures de la CI : l'écran voulu, avec des données dessinées.
    private func openDemo() {
        guard let capture = app.capture, OrgDemo.profileCaptures.contains(capture) else { return }
        switch capture {
        case "org-step1": step = 1
        case "org-rep-verified", "org-rep-unverified":
            draft = OrgDemo.draft(documents: false)
            step = 2
        case "org-docs":
            draft = OrgDemo.draft(documents: false)
            draft.documents = [.rccm, .idnat]
            step = 3
        case "org-terms":
            draft = OrgDemo.draft(documents: true)
            step = 4
        default: break
        }
    }

    private func goBack() {
        withAnimation(.snappy) { step -= 1 }
    }

    // MARK: Présentation (2)

    private var introView: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                Text(app.t("orgIntroTitle")).font(.title(22)).foregroundStyle(Nexis.ink)
                    .accessibilityAddTraits(.isHeader)
                Text(app.t("orgIntroPersonal")).font(.body(15)).foregroundStyle(Nexis.muted)
                VStack(spacing: 0) {
                    benefit("wallet.bifold.fill", app.t("orgIntroWalletT"), app.t("orgIntroWalletS"))
                    Divider().padding(.leading, 66)
                    benefit("person.2.fill", app.t("orgIntroTeamT"), app.t("orgIntroTeamS"))
                    Divider().padding(.leading, 66)
                    benefit("doc.text.fill", app.t("orgIntroReceiptsT"), app.t("orgIntroReceiptsS"))
                }
                .background(Nexis.surface, in: RoundedRectangle(cornerRadius: 20, style: .continuous))
                InfoNote(text: "\(app.t("orgIntroPrepareT")) : \(app.t("orgIntroPrepareS"))",
                         systemImage: "checklist")
            }
            .flowScreen()
        }
        .bottomActions {
            Button { withAnimation(.snappy) { step = 1 } } label: { WideLabel(text: app.t("orgStart")) }
                .nxProminentButton()
            Button { if !flow.path.isEmpty { flow.path.removeLast() } } label: {
                WideLabel(text: app.t("orgLater"))
            }
            .nxSecondaryButton()
        }
    }

    private func benefit(_ symbol: String, _ title: String, _ text: String) -> some View {
        HStack(spacing: 14) {
            Image(systemName: symbol)
                .font(.system(size: 18, weight: .semibold))
                .foregroundStyle(Nexis.softInk)
                .frame(width: 40, height: 40)
                .background(Nexis.soft, in: RoundedRectangle(cornerRadius: 12, style: .continuous))
                .accessibilityHidden(true)
            VStack(alignment: .leading, spacing: 2) {
                Text(title).font(.body(15.5, .bold)).foregroundStyle(Nexis.ink)
                Text(text).font(.body(13.5, relativeTo: .footnote)).foregroundStyle(Nexis.muted)
            }
            Spacer(minLength: 0)
        }
        .padding(14)
        .accessibilityElement(children: .combine)
    }

    // MARK: Étapes (3 à 8)

    private var stepReady: Bool {
        switch step {
        case 1: return draft.step1Ready
        case 2: return draft.step2Ready(identityVerified: identityVerified, identityTaken: identity.capture != nil)
        case 3: return draft.step3Ready
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
                case 1: companyStep
                case 2: representativeStep
                case 3: documentsStep
                default: termsStep
                }
                if failed {
                    Text(app.t("orgFailed")).font(.body(14)).foregroundStyle(Nexis.danger)
                }
            }
            .flowScreen()
        }
        .bottomActions {
            Button {
                if step < 4 { withAnimation(.snappy) { step += 1 } } else { Task { await send() } }
            } label: {
                BusyLabel(text: app.t(step == 4 ? "becomeSend" : "nextStep"), busy: busy)
            }
            .nxProminentButton()
            .disabled(!stepReady || busy)
            if step >= 2 {
                Button { goBack() } label: { WideLabel(text: app.t("back")) }
                    .nxSecondaryButton()
                    .disabled(busy)
            }
        }
    }

    // Étape 1 : l'entreprise (3)

    private var companyStep: some View {
        VStack(alignment: .leading, spacing: 12) {
            StepHeading(title: app.t("orgStep1Title"), hint: nil)
            OrgFieldCard {
                OrgFieldRow(label: app.t("orgName")) {
                    TextField(app.t("orgName"), text: $draft.name)
                        .textInputAutocapitalization(.words)
                }
                Divider().padding(.leading, 16)
                OrgFieldRow(label: "RCCM") {
                    TextField("CD/KIN/RCCM/…", text: $draft.rccm)
                        .textInputAutocapitalization(.characters).autocorrectionDisabled()
                }
                Divider().padding(.leading, 16)
                OrgFieldRow(label: "IDNAT") {
                    TextField("01-F4300-…", text: $draft.idnat)
                        .textInputAutocapitalization(.characters).autocorrectionDisabled()
                }
                Divider().padding(.leading, 16)
                OrgFieldRow(label: "NIF") {
                    TextField("A2512345B", text: $draft.nif)
                        .textInputAutocapitalization(.characters).autocorrectionDisabled()
                }
                Divider().padding(.leading, 16)
                OrgFieldRow(label: app.t("orgEmail")) {
                    TextField("contact@entreprise.cd", text: $draft.email)
                        .keyboardType(.emailAddress)
                        .textInputAutocapitalization(.never).autocorrectionDisabled()
                }
                Divider().padding(.leading, 16)
                NavigationLink {
                    CommunePicker(selection: $draft.commune)
                } label: {
                    OrgFieldRow(label: app.t("commune")) {
                        Text(draft.commune ?? "—")
                            .foregroundStyle(draft.commune == nil ? Nexis.muted : Nexis.ink)
                            .frame(maxWidth: .infinity, alignment: .leading)
                        Image(systemName: "chevron.right")
                            .font(.system(size: 14, weight: .semibold))
                            .foregroundStyle(Nexis.muted)
                    }
                }
                .buttonStyle(.plain)
            }
            if !draft.email.isEmpty && !OrgDraft.isEmail(draft.email) {
                Text(app.t("orgEmailInvalid")).font(.body(13.5)).foregroundStyle(Nexis.danger)
            }
            OrgGroupLabel(text: app.t("orgLegalForm"))
            OrgFieldCard {
                OrgMenuRow(placeholder: "—", options: OrgLegalForm.allCases, selection: draft.form,
                           title: { app.formName($0) }) { draft.form = $0 }
            }
            OrgGroupLabel(text: app.t("orgActivityLabel"))
            OrgFieldCard {
                OrgMenuRow(placeholder: "—", options: OrgActivity.allCases, selection: draft.activity,
                           title: { app.activityName($0) }) { draft.activity = $0 }
            }
        }
    }

    // Étape 2 : le représentant (4, 5)

    private var representativeStep: some View {
        VStack(alignment: .leading, spacing: 12) {
            StepHeading(title: app.t("orgRepTitle"), hint: nil)
            ChoiceRow(title: app.t("orgRepSelf"), subtitle: profile.map { "\($0.firstName) \($0.lastName)" },
                      selected: draft.representativeIsMe) {
                InitialsAvatar(initials: profile?.initials ?? "", size: 40, photoKey: "me")
            } action: {
                draft.representativeIsMe = true
            }
            ChoiceRow(title: app.t("orgRepOther"), subtitle: app.t("orgRepOtherSub"),
                      selected: !draft.representativeIsMe) {
                Image(systemName: "person.crop.circle.badge.plus")
                    .font(.system(size: 20, weight: .medium)).foregroundStyle(Nexis.softInk)
                    .frame(width: 40, height: 40).background(Nexis.soft, in: Circle())
            } action: {
                draft.representativeIsMe = false
            }
            if !draft.representativeIsMe {
                OrgFieldCard {
                    OrgFieldRow(label: app.t("phone")) {
                        Text("+243").foregroundStyle(Nexis.muted)
                        TextField("81 234 5678", text: $draft.representativePhone)
                            .keyboardType(.numberPad)
                    }
                }
            }
            OrgGroupLabel(text: app.t("orgFunction"))
            OrgFieldCard {
                OrgMenuRow(placeholder: "—", options: OrgFunction.allCases, selection: draft.function,
                           title: { app.functionName($0) }) { draft.function = $0 }
            }
            if draft.function == .other {
                OrgFieldCard {
                    OrgFieldRow(label: app.t("orgFunction")) {
                        TextField(app.t("orgFnOtherHint"), text: $draft.functionOther)
                            .textInputAutocapitalization(.sentences)
                    }
                }
            }
            if draft.representativeIsMe, profile != nil {
                if identityVerified {
                    OrgIdentityBanner(done: true, title: app.t("orgIdVerifiedT"), text: app.t("orgIdVerifiedS"))
                } else {
                    OrgIdentityBanner(done: false, title: app.t("orgIdTodoT"), text: app.t("orgIdTodoS"))
                    InfoNote(text: app.t("orgIdOnce"), systemImage: "lock.shield.fill")
                    IdentityStep(draft: $identity)
                }
            }
        }
    }

    // Étape 3 : les documents (7)

    private var documentsStep: some View {
        VStack(alignment: .leading, spacing: 12) {
            StepHeading(title: app.t("orgDocsTitle"), hint: nil)
            ForEach(OrgDocKind.allCases, id: \.self) { kind in
                let received = draft.documents.contains(kind)
                Button {
                    if received { draft.documents.remove(kind) } else { draft.documents.insert(kind) }
                } label: {
                    OrgDocRow(kind: kind, state: received ? .received : .toAdd)
                }
                .buttonStyle(.plain)
            }
            InfoNote(text: app.t("orgDocsFormat"), systemImage: "doc.viewfinder")
            InfoNote(text: app.t("orgDocsNote"), systemImage: "lock.shield.fill")
            InfoNote(text: app.t("orgDocsDemo"), kind: .violet)
        }
    }

    // Étape 4 : conditions et envoi (8)

    private var termsStep: some View {
        VStack(alignment: .leading, spacing: 12) {
            VStack(alignment: .leading, spacing: 8) {
                HStack(alignment: .firstTextBaseline) {
                    Text(draft.name.isEmpty ? "—" : draft.name).font(.title(18)).foregroundStyle(Nexis.ink)
                    Spacer(minLength: 8)
                    Button(app.t("orgEdit")) { withAnimation(.snappy) { step = 1 } }
                        .font(.body(15, .semibold)).tint(Nexis.accent)
                }
                summaryLine("RCCM \(draft.rccm)")
                if let functionLabel {
                    summaryLine(app.t("orgSummaryRep", ["name": representativeName,
                                                        "role": functionLabel.lowercased()]))
                } else {
                    summaryLine("\(app.t("orgProfileRep")) : \(representativeName)")
                }
                if let activity = draft.activity { summaryLine(summary(activity)) }
                summaryLine(app.plural("orgDocsCount", count: draft.documents.count))
            }
            .nxCard(padding: 16)
            VStack(alignment: .leading, spacing: 12) {
                Text(app.t("orgTermsTitle")).font(.body(15.5, .bold)).foregroundStyle(Nexis.ink)
                Text(app.t("termsVersion", ["date": app.longDate(app.repository.orgTermsVersion)]))
                    .font(.body(13, relativeTo: .footnote)).foregroundStyle(Nexis.muted)
                Button(app.t("becomeReadTerms")) { readingTerms = true }
                    .font(.body(15, .semibold)).tint(Nexis.accent)
                Divider()
                Toggle(app.t("orgAccept"), isOn: $accepted)
                    .font(.body(15))
                    .tint(Nexis.brand)
                    .disabled(busy)
            }
            .nxCard(padding: 14)
            InfoNote(text: app.t("orgReviewNote"), systemImage: "hourglass")
        }
    }

    private var functionLabel: String? {
        guard let function = draft.function else { return nil }
        let other = draft.functionOther.trimmingCharacters(in: .whitespaces)
        return function == .other && !other.isEmpty ? other : app.functionName(function)
    }

    private var representativeName: String {
        if draft.representativeIsMe {
            guard let profile else { return "" }
            return "\(profile.firstName) \(profile.lastName)"
        }
        return "+243 \(DrcPhone.parse(draft.representativePhone).formatted)"
    }

    private func summary(_ activity: OrgActivity) -> String {
        switch activity {
        case .orders: return app.t("orgSummaryOrders")
        case .provides: return app.t("orgSummaryProvides")
        case .both: return app.t("orgSummaryBoth")
        }
    }

    private func summaryLine(_ text: String) -> some View {
        Text(text).font(.body(14)).foregroundStyle(Nexis.muted)
    }

    private func send() async {
        busy = true
        failed = false
        do {
            let org = try await app.repository.createOrganization(
                draft, acceptedTermsVersion: accepted ? app.repository.orgTermsVersion : nil,
                // Une personne déjà vérifiée n'envoie rien de plus.
                identity: draft.representativeIsMe && !identityVerified ? identity.capture : nil)
            app.dataChanged()
            withAnimation(.snappy) { sent = org }
        } catch {
            failed = true
        }
        busy = false
    }
}

/// Un document de l'entreprise : sigle, nom, état.
struct OrgDocRow: View {
    @Environment(AppModel.self) private var app
    let kind: OrgDocKind
    let state: OrgDocState

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: "doc.text")
                .font(.system(size: 20, weight: .medium)).foregroundStyle(Nexis.softInk)
                .frame(width: 46, height: 46)
                .background(Nexis.soft, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
                .accessibilityHidden(true)
            VStack(alignment: .leading, spacing: 2) {
                Text(app.docTitle(kind)).font(.body(15.5, .bold)).foregroundStyle(Nexis.ink)
                Text(app.docSubtitle(kind)).font(.body(13, relativeTo: .footnote)).foregroundStyle(Nexis.muted)
            }
            Spacer(minLength: 8)
            switch state {
            case .received: Pill(tone: .ok, systemImage: "checkmark", text: app.t("orgDocReceived"))
            case .toAdd: Pill(tone: .secured, systemImage: "plus", text: app.t("orgDocToAdd"))
            case .toRedo: Pill(tone: .warn, systemImage: "arrow.counterclockwise", text: app.t("orgDocToRedo"))
            }
        }
        .padding(14)
        .background(Nexis.surface, in: RoundedRectangle(cornerRadius: 18, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 18, style: .continuous).strokeBorder(Nexis.line, lineWidth: 0.5))
        .contentShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
        .accessibilityElement(children: .combine)
    }
}

// MARK: - Suivi de la demande (9, 10, 11)

/// L'écran du suivi, ouvert depuis le profil.
struct OrgStatusView: View {
    @Environment(AppModel.self) private var app
    let orgId: Int

    var body: some View {
        OrgLoader(orgId: orgId) { org in OrgStatusBody(org: org) }
            .flowTitle(app.t("orgTitle"))
    }
}

/// Selon l'état : demande envoyée, correction demandée, espace validé.
struct OrgStatusBody: View {
    @Environment(AppModel.self) private var app
    @Environment(MissionFlow.self) private var flow
    let org: Organization
    @State private var busy = false
    @State private var failed = false

    var body: some View {
        switch org.status {
        case .reviewing: reviewing
        case .correction: correction
        case .open: approved
        }
    }

    private func badge(_ symbol: String, _ color: Color, _ background: Color) -> some View {
        Image(systemName: symbol)
            .font(.system(size: 38, weight: .medium))
            .foregroundStyle(color)
            .frame(width: 96, height: 96)
            .background(Circle().fill(background))
            .padding(.vertical, 16)
            .accessibilityHidden(true)
    }

    // 9. En attente de vérification

    private var reviewing: some View {
        ScrollView {
            VStack(spacing: 10) {
                badge("hourglass", Nexis.accent, Nexis.soft)
                Text(app.t("orgSentTitle")).font(.title(21)).foregroundStyle(Nexis.ink)
                Text(app.t("orgSentText", ["name": org.shortName])).font(.body(15)).foregroundStyle(Nexis.muted)
                    .multilineTextAlignment(.center).lineSpacing(3)
                StepList(items: [
                    StepItem(title: app.t("orgSentTitle"), time: app.sentStamp(org.sentAt), state: .done),
                    StepItem(title: app.t("orgTimeReview"), sub: app.t("orgTimeReviewSub"), state: .now),
                    StepItem(title: app.t("orgTimeOpen"), sub: app.t("orgTimeOpenSub"), state: .todo),
                ])
                .nxCard(padding: 16)
                .padding(.top, 10)
                InfoNote(text: app.t("orgSentPersonal"), systemImage: "person.crop.circle")
                    .padding(.top, 4)
            }
            .frame(maxWidth: .infinity)
            .flowScreen()
        }
        .bottomActions {
            Button { flow.restart(at: nil) } label: { WideLabel(text: app.t("orgBackProfile")) }
                .nxProminentButton()
        }
    }

    // 10. Corrections demandées

    private var correction: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 12) {
                badge("exclamationmark.bubble.fill", Nexis.wait, Color(light: 0xFFF1D6, dark: 0x33270D))
                    .frame(maxWidth: .infinity)
                Text(app.t("orgFixTitle")).font(.title(20)).foregroundStyle(Nexis.ink)
                Text(app.t("orgFixKept")).font(.body(15)).foregroundStyle(Nexis.muted)
                ForEach(org.documents) { document in
                    OrgDocRow(kind: document.kind, state: document.state)
                }
                if let note = org.correctionNote {
                    VStack(alignment: .leading, spacing: 6) {
                        Label(app.t("orgFixMessage"), systemImage: "bubble.left.fill")
                            .font(.body(13.5, .semibold)).foregroundStyle(Nexis.softInk)
                        Text("« \(note) »").font(.body(15)).foregroundStyle(Nexis.ink).lineSpacing(3)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(14)
                    .background(Nexis.soft, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
                }
                if failed {
                    Text(app.t("orgFailed")).font(.body(14)).foregroundStyle(Nexis.danger)
                }
            }
            .flowScreen()
        }
        .bottomActions {
            Button { Task { await replace() } } label: {
                BusyLabel(text: app.t("orgFixReplace"), busy: busy)
            }
            .nxProminentButton()
            .disabled(busy || !org.documents.contains(where: { $0.state == .toRedo }))
            Button { flow.comingSoon = SheetTitle(app.t("orgFixWrite")) } label: {
                WideLabel(text: app.t("orgFixWrite"))
            }
            .nxSecondaryButton()
        }
    }

    private func replace() async {
        guard let redo = org.documents.first(where: { $0.state == .toRedo }) else { return }
        busy = true
        failed = false
        do {
            try await app.repository.replaceDocument(orgId: org.id, kind: redo.kind)
            app.dataChanged()
        } catch {
            failed = true
        }
        busy = false
    }

    // 11. Entreprise validée

    private var approved: some View {
        ScrollView {
            VStack(spacing: 10) {
                badge("checkmark.seal.fill", Nexis.ok, Color(light: 0xE3F5EA, dark: 0x12301F))
                Text(app.t("orgApprovedTitle", ["name": org.shortName])).font(.title(21)).foregroundStyle(Nexis.ink)
                    .multilineTextAlignment(.center)
                Text(app.t("orgApprovedText")).font(.body(15)).foregroundStyle(Nexis.muted)
                    .multilineTextAlignment(.center).lineSpacing(3)
                VStack(spacing: 0) {
                    firstStep("phone.badge.plus", app.t("orgApprovedNumber")) { flow.push(.orgNumberAdd(org.id)) }
                    Divider().padding(.leading, 62)
                    firstStep("person.badge.plus", app.t("orgApprovedInvite")) { flow.push(.orgInvite(org.id)) }
                }
                .background(Nexis.surface, in: RoundedRectangle(cornerRadius: 20, style: .continuous))
                .padding(.top, 12)
            }
            .frame(maxWidth: .infinity)
            .flowScreen()
        }
        .bottomActions {
            Button {
                app.openOrgSpace(org.id)
                flow.restart(at: nil)
            } label: { WideLabel(text: app.t("orgApprovedOpen")) }
                .nxProminentButton()
        }
    }

    private func firstStep(_ symbol: String, _ title: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            HStack(spacing: 14) {
                Image(systemName: symbol)
                    .font(.system(size: 18, weight: .semibold)).foregroundStyle(Nexis.softInk)
                    .frame(width: 40, height: 40)
                    .background(Nexis.soft, in: RoundedRectangle(cornerRadius: 12, style: .continuous))
                Text(title).font(.body(15, .semibold)).foregroundStyle(Nexis.ink)
                    .multilineTextAlignment(.leading)
                Spacer(minLength: 8)
                Image(systemName: "chevron.right").font(.system(size: 13, weight: .semibold))
                    .foregroundStyle(Color(light: 0xC4CAD4, dark: 0x4A5A75))
            }
            .padding(14)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
    }
}

// MARK: - Invitation reçue (16, 17)

struct OrgInvitationView: View {
    @Environment(AppModel.self) private var app
    @Environment(MissionFlow.self) private var flow
    let invitationId: Int
    @State private var invitation: OrgInvitation?
    @State private var profile: Profile?
    @State private var loaded = false
    @State private var busy = false
    @State private var failed = false

    private var verified: Bool { profile?.isIdentityVerified ?? false }

    var body: some View {
        Group {
            if let invitation, profile != nil {
                content(invitation)
            } else if loaded {
                ContentUnavailableView(app.t("orgInvTitle"), systemImage: "envelope.open")
            } else {
                FlowLoading(label: app.t("orgInvTitle"))
            }
        }
        .flowTitle(app.t("orgInvTitle"))
        .task(id: app.revision) {
            profile = try? await app.repository.profile()
            invitation = (try? await app.repository.invitations())?.first { $0.id == invitationId }
            loaded = true
        }
    }

    private func content(_ invitation: OrgInvitation) -> some View {
        ScrollView {
            VStack(spacing: 10) {
                OrgMark(name: invitation.orgName, size: 84)
                    .padding(.vertical, 12)
                Text(app.t("orgInvHeading", ["org": Organization.shortName(of: invitation.orgName)]))
                    .font(.title(21)).foregroundStyle(Nexis.ink).multilineTextAlignment(.center)
                Text(app.t("orgInvBody", ["name": invitation.inviterName,
                                          "role": app.roleName(invitation.role).lowercased()]))
                    .font(.body(15)).foregroundStyle(Nexis.muted)
                    .multilineTextAlignment(.center).lineSpacing(3)
                if verified {
                    OrgIdentityBanner(done: true, title: app.t("orgInvVerifiedT"), text: app.t("orgIdVerifiedS"))
                        .padding(.top, 10)
                } else {
                    OrgIdentityBanner(done: false, title: app.t("orgInvUnverT"), text: app.t("orgInvUnverS"))
                        .padding(.top, 10)
                }
                InfoNote(text: verified ? app.t("orgInvOwn") : app.t("orgInvUnverNote"),
                         systemImage: verified ? "person.crop.circle" : "info.circle.fill")
                if failed {
                    Text(app.t("orgFailed")).font(.body(14)).foregroundStyle(Nexis.danger)
                }
            }
            .frame(maxWidth: .infinity)
            .flowScreen()
        }
        .bottomActions {
            Button { Task { await answer(invitation, accept: true) } } label: {
                BusyLabel(text: app.t(verified ? "orgInvAccept" : "orgInvAcceptVerify"), busy: busy)
            }
            .nxProminentButton()
            .disabled(busy)
            Button { Task { await answer(invitation, accept: false) } } label: {
                WideLabel(text: app.t("orgInvRefuse"))
            }
            .nxSecondaryButton()
            .disabled(busy)
        }
    }

    private func answer(_ invitation: OrgInvitation, accept: Bool) async {
        busy = true
        failed = false
        do {
            try await app.repository.answerInvitation(id: invitation.id, accept: accept)
            app.dataChanged()
            if accept && !verified {
                // Seule cette personne passe par la vérification, avec les écrans existants.
                flow.restart(at: .orgIdentity)
            } else {
                flow.restart(at: nil)
                flow.say(app.t(accept ? "orgInvAccepted" : "orgInvRefused"))
            }
        } catch {
            failed = true
        }
        busy = false
    }
}

/// Vérification d'identité d'un invité jamais vérifié : les écrans de
/// « Devenir prestataire » (pièce, puis vidéo), rien de plus.
struct OrgIdentityView: View {
    @Environment(AppModel.self) private var app
    @Environment(MissionFlow.self) private var flow
    @State private var identity = IdentityDraft()
    @State private var busy = false
    @State private var failed = false

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 12) {
                StepHeading(title: app.t("becomeIdentity"), hint: nil)
                IdentityStep(draft: $identity)
                if failed {
                    Text(app.t("orgFailed")).font(.body(14)).foregroundStyle(Nexis.danger)
                }
            }
            .flowScreen()
        }
        .flowTitle(app.t("orgInvTitle"))
        .bottomActions {
            Button { Task { await send() } } label: {
                BusyLabel(text: app.t("orgIdTodoT"), busy: busy)
            }
            .nxProminentButton()
            .disabled(identity.capture == nil || busy)
        }
    }

    private func send() async {
        guard let capture = identity.capture else { return }
        busy = true
        failed = false
        do {
            try await app.repository.submitIdentity(capture)
            app.dataChanged()
            flow.restart(at: nil)
            flow.say(app.t("orgIdSent"))
        } catch {
            failed = true
        }
        busy = false
    }
}
