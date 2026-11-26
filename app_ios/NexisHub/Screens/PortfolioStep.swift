import PhotosUI
import SwiftUI
import UIKit

// Preuves de réalisations : étape facultative de « Devenir prestataire » et
// écran « Mes réalisations » du profil. L'équipe NexisHub les revoit, puis
// les photos d'un service approuvé sont montrées aux clients (« Voir ses
// réalisations » sur les devis). Les diplômes restent vus par l'équipe
// seulement. La galerie est permise ici, et seulement ici : ce sont des
// travaux déjà faits (la pièce d'identité et la vidéo restent sans galerie).

/// Une photo choisie, réduite, prête à être envoyée.
struct ProofPhoto: Identifiable {
    let id = UUID()
    let jpeg: Data
    let image: UIImage
}

enum ProofImages {
    /// Redessine l'image à l'endroit, réduite à 1 600 px, puis la réencode
    /// en JPEG : les métadonnées (lieu, appareil, date) disparaissent.
    static func prepare(_ data: Data) -> ProofPhoto? {
        guard let source = UIImage(data: data), source.size.width > 0, source.size.height > 0 else { return nil }
        let scale = min(1, 1600 / max(source.size.width, source.size.height))
        let size = CGSize(width: (source.size.width * scale).rounded(), height: (source.size.height * scale).rounded())
        let format = UIGraphicsImageRendererFormat()
        format.scale = 1
        format.opaque = true
        let image = UIGraphicsImageRenderer(size: size, format: format).image { _ in
            source.draw(in: CGRect(origin: .zero, size: size))
        }
        guard let jpeg = image.jpegData(compressionQuality: 0.8) else { return nil }
        return ProofPhoto(jpeg: jpeg, image: image)
    }
}

/// Ce qui est en cours de saisie.
struct PortfolioDraft {
    var photos: [String: [ProofPhoto]] = [:]
    var notes: [String: String] = [:]
    var certificates: [ProofPhoto] = []
    /// Ce qui a été envoyé, avec la décision de l'équipe.
    var sent = Portfolio()

    var isEmpty: Bool { photos.values.allSatisfy(\.isEmpty) && certificates.isEmpty }

    init() {}

    /// La décision de l'équipe sur un service, tant que ses photos et sa
    /// phrase n'ont pas été changées ici (sinon elles seront revues).
    func review(for serviceId: String) -> ProofReview? {
        guard let work = sent.works.first(where: { $0.serviceId == serviceId }) else { return nil }
        let unchanged = (photos[serviceId] ?? []).map(\.jpeg) == work.photos
            && (notes[serviceId] ?? "").trimmingCharacters(in: .whitespacesAndNewlines) == work.note
        return unchanged ? work.review : nil
    }

    var certificatesVerified: Bool {
        sent.certificatesVerified && certificates.map(\.jpeg) == sent.certificates
    }

    /// Reprend ce qui a déjà été envoyé.
    init(_ portfolio: Portfolio) {
        sent = portfolio
        for work in portfolio.works {
            photos[work.serviceId] = work.photos.compactMap { data in UIImage(data: data).map { ProofPhoto(jpeg: data, image: $0) } }
            notes[work.serviceId] = work.note
        }
        certificates = portfolio.certificates.compactMap { data in UIImage(data: data).map { ProofPhoto(jpeg: data, image: $0) } }
    }

    /// Les preuves à envoyer, dans l'ordre des services.
    func portfolio(services: [String]) -> Portfolio {
        Portfolio(works: services.map { id in
            WorkProof(serviceId: id, photos: (photos[id] ?? []).map(\.jpeg), note: notes[id] ?? "")
        }, certificates: certificates.map(\.jpeg)).cleaned
    }
}

struct PortfolioEditor: View {
    @Environment(AppModel.self) private var app
    let services: [CatalogService]
    @Binding var draft: PortfolioDraft
    /// Figé pendant la vérification du prestataire : on montre ce qui a été
    /// envoyé, sans rien pouvoir changer.
    var locked = false
    @State private var failed = false

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            if !locked {
                InfoNote(text: app.t("worksPrivacy"), systemImage: "lock.shield.fill")
            }
            ForEach(services.filter { !locked || !(draft.photos[$0.id] ?? []).isEmpty }) { service in
                ProofCard(locked: locked, title: service.name(app.language), status: status(draft.review(for: service.id)),
                          maxPhotos: Portfolio.maxPhotos,
                          photos: Binding(get: { draft.photos[service.id] ?? [] }, set: { draft.photos[service.id] = $0 }),
                          note: Binding(get: { draft.notes[service.id] ?? "" }, set: { draft.notes[service.id] = $0 }),
                          failed: $failed) {
                    ServiceTile(service, size: 38)
                }
            }
            if !locked || !draft.certificates.isEmpty {
            ProofCard(locked: locked, title: app.t("worksCertificates"), subtitle: app.t("worksCertificatesSub"),
                      status: draft.certificatesVerified ? ProofStatus(tone: .ok, icon: "checkmark.seal.fill", text: app.t("worksCertificatesVerified")) : nil,
                      maxPhotos: Portfolio.maxCertificates, photos: $draft.certificates, note: nil, failed: $failed) {
                Image(systemName: "graduationcap").font(.system(size: 18)).foregroundStyle(Nexis.softInk)
                    .frame(width: 38, height: 38)
                    .background(Nexis.soft, in: RoundedRectangle(cornerRadius: 10, style: .continuous))
                    .accessibilityHidden(true)
            }
            }
            if failed {
                Text(app.t("worksPhotoFailed")).font(.body(14)).foregroundStyle(Nexis.danger)
            }
        }
    }

    private func status(_ review: ProofReview?) -> ProofStatus? {
        switch review {
        case .pending: ProofStatus(tone: .wait, icon: "clock", text: app.t("worksReviewPending"))
        case .approved: ProofStatus(tone: .ok, icon: "eye", text: app.t("worksReviewApproved"))
        case .rejected: ProofStatus(tone: .bad, icon: "xmark.circle", text: app.t("worksReviewRejected"))
        case nil: nil
        }
    }
}

struct ProofStatus {
    let tone: PillTone
    let icon: String
    let text: String
}

/// Les photos d'un service (ou les attestations), choisies dans la galerie.
private struct ProofCard<Leading: View>: View {
    @Environment(AppModel.self) private var app
    var locked = false
    let title: String
    var subtitle: String?
    var status: ProofStatus?
    let maxPhotos: Int
    @Binding var photos: [ProofPhoto]
    var note: Binding<String>?
    @Binding var failed: Bool
    @ViewBuilder var leading: Leading
    @State private var picked: [PhotosPickerItem] = []
    @State private var loading = false

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 12) {
                leading
                VStack(alignment: .leading, spacing: 2) {
                    Text(title).font(.body(15.5, .bold)).foregroundStyle(Nexis.ink)
                    if let subtitle {
                        Text(subtitle).font(.body(13, relativeTo: .footnote)).foregroundStyle(Nexis.muted)
                    }
                }
                Spacer(minLength: 8)
                Text(app.t("worksCount", ["count": String(photos.count), "max": String(maxPhotos)]))
                    .font(.body(12.5, .semibold, relativeTo: .caption1)).foregroundStyle(Nexis.muted)
            }
            if let status {
                Pill(tone: status.tone, systemImage: status.icon, text: status.text)
            }
            if !photos.isEmpty {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 8) {
                        ForEach(photos) { photo in
                            Image(uiImage: photo.image).resizable().scaledToFill()
                                .frame(width: 76, height: 76)
                                .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
                                .overlay(alignment: .topTrailing) {
                                    if !locked {
                                    Button {
                                        photos.removeAll { $0.id == photo.id }
                                    } label: {
                                        Image(systemName: "xmark.circle.fill")
                                            .font(.system(size: 20))
                                            .symbolRenderingMode(.palette)
                                            .foregroundStyle(.white, .black.opacity(0.55))
                                            .padding(4)
                                    }
                                    .accessibilityLabel(app.t("worksRemove"))
                                    }
                                }
                        }
                    }
                }
            }
            if locked {
                if let note, !note.wrappedValue.isEmpty {
                    Text(note.wrappedValue).font(.body(14.5)).foregroundStyle(Nexis.ink)
                }
            } else {
            PhotosPicker(selection: $picked, maxSelectionCount: max(maxPhotos - photos.count, 1),
                         selectionBehavior: .ordered, matching: .images) {
                Label(app.t("worksAddPhotos"), systemImage: "photo.on.rectangle.angled").font(.body(14.5, .semibold))
            }
            .buttonStyle(OutlineButtonStyle(tint: Nexis.accent))
            .disabled(photos.count >= maxPhotos || loading)
            if let note {
                VStack(alignment: .leading, spacing: 6) {
                    Text(app.t("worksNote")).font(.body(13, .semibold, relativeTo: .footnote)).foregroundStyle(Nexis.ink)
                    TextField(app.t("worksNoteExample"), text: note, axis: .vertical)
                        .lineLimit(1...3)
                        .font(.body(15))
                        .padding(12)
                        .background(Nexis.soft, in: RoundedRectangle(cornerRadius: 12, style: .continuous))
                        .onChange(of: note.wrappedValue) { _, text in
                            if text.count > Portfolio.maxNote { note.wrappedValue = String(text.prefix(Portfolio.maxNote)) }
                        }
                }
            }
            }
        }
        .nxCard(padding: 14)
        .onChange(of: picked) { _, items in
            guard !items.isEmpty else { return }
            Task { await load(items) }
        }
    }

    private func load(_ items: [PhotosPickerItem]) async {
        loading = true
        var unreadable = false
        for item in items where photos.count < maxPhotos {
            if let data = try? await item.loadTransferable(type: Data.self), let photo = ProofImages.prepare(data) {
                photos.append(photo)
            } else {
                unreadable = true
            }
        }
        failed = unreadable
        picked = []
        loading = false
    }
}

// MARK: - Mes réalisations (profil)

struct PortfolioView: View {
    @Environment(AppModel.self) private var app
    @State private var services: [CatalogService] = []
    @State private var draft = PortfolioDraft()
    @State private var request: PortfolioRequest?
    @State private var locked = false
    @State private var busy = false
    @State private var failed = false
    @State private var saved = false

    var body: some View {
        Group {
            if locked {
                form
            } else {
                form.bottomActions {
                    Button { Task { await send() } } label: { BusyLabel(text: app.t("worksSave"), busy: busy) }
                        .nxProminentButton()
                        .disabled(busy || app.capture == PortfolioDemo.profile)
                }
            }
        }
        .flowTitle(app.t("myWorks"))
        .task { await load() }
    }

    private var form: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 12) {
                if let request {
                    let names = request.services.compactMap { id in services.first { $0.id == id }?.name(app.language) }
                    InfoNote(text: app.t("worksRequested", ["services": names.joined(separator: ", ")]),
                             systemImage: "envelope.badge.fill")
                }
                if locked {
                    InfoNote(text: app.t("worksLocked"), systemImage: "hourglass")
                }
                PortfolioEditor(services: services, draft: $draft, locked: locked)
                if saved {
                    InfoNote(text: app.t("worksSaved"), systemImage: "checkmark.circle.fill")
                }
                if failed {
                    Text(app.t("actionFailed")).font(.body(14)).foregroundStyle(Nexis.danger)
                }
                InfoNote(text: app.t("worksDemoNote"), kind: .violet)
            }
            .flowScreen()
        }
    }

    private func load() async {
        let catalog = (try? await app.repository.serviceCatalog()) ?? []
        if app.capture == PortfolioDemo.profile {
            services = catalog.filter { $0.id == "plomberie" || $0.id == "electricite" }
            request = PortfolioRequest(services: ["electricite"], askedAt: .now)
            draft = PortfolioDemo.draft(services: ["plomberie"])
            // La plomberie a déjà été approuvée : les clients la voient.
            var sent = draft.portfolio(services: ["plomberie"])
            sent.works = sent.works.map { var work = $0; work.review = .approved; return work }
            draft.sent = sent
            return
        }
        if app.capture == PortfolioDemo.locked {
            services = catalog.filter { $0.id == "plomberie" || $0.id == "electricite" }
            draft = PortfolioDemo.draft(services: ["plomberie"])
            draft.sent = draft.portfolio(services: ["plomberie"])
            locked = true
            return
        }
        let chosen = (try? await app.repository.providerServices()) ?? []
        services = catalog.filter { chosen.contains($0.id) }
        draft = PortfolioDraft((try? await app.repository.portfolio()) ?? Portfolio())
        request = try? await app.repository.portfolioRequest()
        let status = try? await app.repository.profile().providerStatus
        locked = !Portfolio.isEditable(status: status, requested: request != nil)
    }

    private func send() async {
        busy = true
        failed = false
        saved = false
        do {
            try await app.repository.sendPortfolio(draft.portfolio(services: services.map(\.id)))
            request = nil
            saved = true
            let status = try? await app.repository.profile().providerStatus
            locked = !Portfolio.isEditable(status: status, requested: false)
            app.dataChanged()
        } catch {
            failed = true
        }
        busy = false
    }
}

// MARK: - Démonstration (captures de la CI)

/// `become-portfolio` (étape de la demande), `portfolio` (profil, avec une
/// demande de l'équipe) et `portfolio-locked` (figé pendant la vérification).
enum PortfolioDemo {
    static let step = "become-portfolio"
    static let profile = "portfolio"
    static let locked = "portfolio-locked"

    /// Photos dessinées par l'app (pas de vraies photos).
    @MainActor
    static func draft(services: [String]) -> PortfolioDraft {
        var draft = PortfolioDraft()
        let symbols = ["wrench.and.screwdriver.fill", "drop.fill", "shower.fill"]
        for id in services {
            draft.photos[id] = symbols.compactMap { symbol in
                let renderer = ImageRenderer(content:
                    ZStack {
                        LinearGradient(colors: [Color(hex: 0xD6E4F5), Color(hex: 0x9FB6D6)], startPoint: .top, endPoint: .bottom)
                        Image(systemName: symbol).font(.system(size: 54)).foregroundStyle(Color(hex: 0x24344D).opacity(0.7))
                    }
                    .frame(width: 240, height: 240))
                renderer.scale = 1
                guard let image = renderer.uiImage, let jpeg = image.jpegData(compressionQuality: 0.8) else { return nil }
                return ProofPhoto(jpeg: jpeg, image: image)
            }
            draft.notes[id] = "Limete, 2025"
        }
        return draft
    }
}
