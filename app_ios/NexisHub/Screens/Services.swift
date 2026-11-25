import SwiftUI

private enum PickerStep: Hashable {
    case request(String)
    case describe
}

/// « Quel service ? » : le catalogue publié par le serveur, en grille,
/// avec recherche. Ouvert en feuille (verre sur iOS 26 et 27).
struct ServicePickerView: View {
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    let onRequested: () -> Void

    @State private var catalog: [CatalogService] = []
    @State private var query = ""
    @State private var path: [PickerStep] = []

    private let columns = [GridItem(.adaptive(minimum: 96), spacing: 12)]

    var body: some View {
        NavigationStack(path: $path) {
            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    Text(app.t("pickServiceHint"))
                        .font(.body(15)).foregroundStyle(Nexis.muted)
                    if filtered.isEmpty {
                        Text(app.t("noServiceMatches"))
                            .font(.body(15)).foregroundStyle(Nexis.muted)
                    }
                    LazyVGrid(columns: columns, spacing: 12) {
                        ForEach(filtered) { item in
                            NavigationLink(value: PickerStep.request(item.id)) {
                                ServiceCell(item: item)
                            }
                            .buttonStyle(.plain)
                        }
                    }
                    notInList
                }
                .padding(.horizontal, 18)
                .padding(.bottom, 24)
            }
            .background(Nexis.bg)
            .navigationTitle(app.t("whichService"))
            .navigationBarTitleDisplayMode(.inline)
            .searchable(text: $query, prompt: app.t("searchService"))
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button(role: .cancel) { dismiss() } label: {
                        Image(systemName: "xmark")
                    }
                    .accessibilityLabel(app.t("close"))
                }
            }
            .navigationDestination(for: PickerStep.self) { step in
                switch step {
                case .request(let id):
                    if let item = catalog.first(where: { $0.id == id }) {
                        RequestServiceView(item: item, onDone: onRequested)
                    }
                case .describe:
                    DescribeNeedView(onDone: { dismiss() })
                }
            }
            .task { catalog = (try? await app.repository.serviceCatalog()) ?? [] }
        }
        .presentationDetents([.large])
    }

    /// La recherche accepte le nom affiché et le nom d'origine du catalogue.
    private var filtered: [CatalogService] {
        let needle = query.trimmingCharacters(in: .whitespaces)
        guard !needle.isEmpty else { return catalog }
        return catalog.filter {
            $0.name(app.language).localizedStandardContains(needle)
                || $0.baseName.localizedStandardContains(needle)
        }
    }

    private var notInList: some View {
        NavigationLink(value: PickerStep.describe) {
            HStack(spacing: 14) {
                Image(systemName: "square.and.pencil")
                    .font(.system(size: 18, weight: .semibold))
                    .foregroundStyle(Nexis.accent)
                    .frame(width: 44, height: 44)
                    .background(Nexis.soft, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
                VStack(alignment: .leading, spacing: 2) {
                    Text(app.t("cantFindService"))
                        .font(.body(15, .semibold)).foregroundStyle(Nexis.ink)
                    Text(app.t("cantFindHint"))
                        .font(.body(13, relativeTo: .footnote)).foregroundStyle(Nexis.muted)
                        .multilineTextAlignment(.leading)
                }
                Spacer(minLength: 0)
                Image(systemName: "chevron.right").foregroundStyle(Nexis.muted)
            }
            .nxCard(padding: 14)
        }
        .buttonStyle(.plain)
    }
}

private struct ServiceCell: View {
    @Environment(AppModel.self) private var app
    let item: CatalogService

    var body: some View {
        VStack(spacing: 10) {
            ServiceTile(item, size: 52)
                .overlay(alignment: .topTrailing) {
                    if item.isNew { NewBadge().offset(x: 14, y: -8) }
                }
            Text(item.name(app.language))
                .font(.body(13, .semibold, relativeTo: .footnote))
                .foregroundStyle(Nexis.ink)
                .multilineTextAlignment(.center)
                .lineLimit(2)
                .minimumScaleFactor(0.85)
        }
        .frame(maxWidth: .infinity, minHeight: 112)
        .padding(.vertical, 12)
        .background(Nexis.surface, in: RoundedRectangle(cornerRadius: 20, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 20, style: .continuous)
            .strokeBorder(Nexis.line, lineWidth: 0.5))
        .contentShape(RoundedRectangle(cornerRadius: 20, style: .continuous))
        .accessibilityElement(children: .combine)
        .accessibilityAddTraits(.isButton)
    }
}

/// Demande pour un service du catalogue : commune et besoin. Rien n'est
/// payé à cette étape ; dans l'aperçu, la demande est une simulation.
struct RequestServiceView: View {
    @Environment(AppModel.self) private var app
    let item: CatalogService
    let onDone: () -> Void

    @State private var commune: String?
    @State private var text = ""
    @State private var sending = false
    @State private var saved = false
    @State private var failed = false

    private var trimmed: String { text.trimmingCharacters(in: .whitespacesAndNewlines) }
    private var valid: Bool { commune != nil && (10...500).contains(trimmed.count) }

    var body: some View {
        Form {
            Section {
                HStack(spacing: 14) {
                    ServiceTile(item, size: 48)
                    Text(item.name(app.language)).font(.title(18)).foregroundStyle(Nexis.ink)
                }
                .listRowBackground(Color.clear)
            }
            Section {
                Picker(app.t("commune"), selection: $commune) {
                    Text("—").tag(String?.none)
                    ForEach(app.repository.communes, id: \.self) { Text($0).tag(String?.some($0)) }
                }
                .pickerStyle(.navigationLink)
                .font(.body(16))
            }
            Section {
                TextField(app.t("describeTextHint"), text: $text, axis: .vertical)
                    .lineLimit(4...8)
                    .font(.body(16))
            } header: {
                Text(app.t("describeTextLabel")).font(.body(13, .semibold))
            } footer: {
                Text("\(trimmed.count)/500").font(.body(12)).foregroundStyle(Nexis.muted)
            }
            Section {
                Label(app.t("serviceRequestDemo"), systemImage: "info.circle")
                Label(app.t("serviceRequestNoPay"), systemImage: "lock.shield")
            }
            .font(.body(14))
            .foregroundStyle(Nexis.muted)
            if failed {
                Text(app.t("requestNotSent")).font(.body(14)).foregroundStyle(Nexis.danger)
            }
        }
        .scrollContentBackground(.hidden)
        .background(Nexis.bg)
        .navigationTitle(app.t("requestService"))
        .navigationBarTitleDisplayMode(.inline)
        .safeAreaInset(edge: .bottom) {
            Button(action: send) {
                if sending { ProgressView().frame(maxWidth: .infinity) }
                else { WideLabel(text: app.t("sendRequest")) }
            }
            .nxProminentButton()
            .disabled(!valid || sending)
            .padding(.horizontal, 20)
            .padding(.bottom, 8)
        }
        .alert(app.t("serviceRequestSaved"), isPresented: $saved) {
            Button(app.t("ok")) { onDone() }
        } message: {
            Text(app.t("serviceRequestSavedText"))
        }
        .sensoryFeedback(.success, trigger: saved)
    }

    private func send() {
        guard valid, let commune else { return }
        sending = true
        failed = false
        Task {
            do {
                try await app.repository.requestService(
                    serviceId: item.id, commune: commune, description: trimmed)
                app.dataChanged()
                saved = true
            } catch {
                failed = true
            }
            sending = false
        }
    }
}

/// « Décrire mon besoin » : une demande libre transmise à l'équipe.
struct DescribeNeedView: View {
    @Environment(AppModel.self) private var app
    let onDone: () -> Void

    @State private var title = ""
    @State private var text = ""
    @State private var sending = false
    @State private var sent = false
    @State private var failed = false

    private var valid: Bool {
        !title.trimmingCharacters(in: .whitespaces).isEmpty
            && text.trimmingCharacters(in: .whitespacesAndNewlines).count >= 10
    }

    var body: some View {
        Form {
            Section {
                Text(app.t("describeLead")).font(.body(15)).foregroundStyle(Nexis.muted)
                    .listRowBackground(Color.clear)
                    .listRowInsets(EdgeInsets(top: 0, leading: 4, bottom: 8, trailing: 4))
            }
            Section {
                TextField(app.t("describeTypeHint"), text: $title).font(.body(16))
            } header: {
                Text(app.t("describeTypeLabel")).font(.body(13, .semibold))
            }
            Section {
                TextField(app.t("describeTextHint"), text: $text, axis: .vertical)
                    .lineLimit(4...8).font(.body(16))
            } header: {
                Text(app.t("describeTextLabel")).font(.body(13, .semibold))
            }
            Section {
                Label(app.t("describeNoPay"), systemImage: "lock.shield")
                    .font(.body(14)).foregroundStyle(Nexis.muted)
            }
            if failed {
                Text(app.t("requestNotSent")).font(.body(14)).foregroundStyle(Nexis.danger)
            }
        }
        .scrollContentBackground(.hidden)
        .background(Nexis.bg)
        .navigationTitle(app.t("describeNeed"))
        .navigationBarTitleDisplayMode(.inline)
        .safeAreaInset(edge: .bottom) {
            Button(action: send) { WideLabel(text: app.t("sendRequest")) }
                .nxProminentButton()
                .disabled(!valid || sending)
                .padding(.horizontal, 20)
                .padding(.bottom, 8)
        }
        .alert(app.t("requestSent"), isPresented: $sent) {
            Button(app.t("backHome")) { onDone() }
        } message: {
            Text(app.t("requestSentText"))
        }
    }

    private func send() {
        guard valid else { return }
        sending = true
        Task {
            do {
                try await app.repository.sendFreeRequest(title: title, text: text)
                sent = true
            } catch {
                failed = true
            }
            sending = false
        }
    }
}
