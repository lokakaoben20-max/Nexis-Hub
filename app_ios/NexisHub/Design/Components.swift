import SwiftUI

// MARK: - Liquid Glass

extension View {
    /// Matériau Liquid Glass d'iOS 26 et 27. Les réglages de l'utilisateur
    /// (curseur Liquid Glass d'iOS 27, Réduire la transparence, Augmenter
    /// le contraste) s'appliquent d'eux-mêmes. Avant iOS 26 : matériau
    /// translucide classique.
    @ViewBuilder
    func nxGlass(tint: Color? = nil, interactive: Bool = false,
                 in shape: some Shape = Capsule()) -> some View {
        if #available(iOS 26.0, *) {
            self.glassEffect(Glass.regular.tint(tint).interactive(interactive), in: shape)
        } else {
            self.background(.ultraThinMaterial, in: shape)
        }
    }

    /// Bouton principal de l'écran : verre teinté du bleu Nexis.
    @ViewBuilder
    func nxProminentButton() -> some View {
        if #available(iOS 26.0, *) {
            self.buttonStyle(.glassProminent).tint(Nexis.brand).controlSize(.large)
        } else {
            self.buttonStyle(.borderedProminent).tint(Nexis.brand).controlSize(.large)
        }
    }

    /// Bouton secondaire : verre clair.
    @ViewBuilder
    func nxSecondaryButton() -> some View {
        if #available(iOS 26.0, *) {
            self.buttonStyle(.glass).controlSize(.large)
        } else {
            self.buttonStyle(.bordered).tint(Nexis.accent).controlSize(.large)
        }
    }

    /// Carte de contenu : surface pleine aux coins continus d'iOS.
    func nxCard(padding: CGFloat = 16) -> some View {
        self.padding(padding)
            .background(Nexis.surface, in: RoundedRectangle(cornerRadius: 22, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 22, style: .continuous)
                .strokeBorder(Nexis.line, lineWidth: 0.5))
    }
}

/// Libellé pleine largeur pour les boutons d'action.
struct WideLabel: View {
    let text: String
    var systemImage: String? = nil

    var body: some View {
        HStack(spacing: 8) {
            if let systemImage { Image(systemName: systemImage) }
            Text(text).font(.body(17, .semibold, relativeTo: .headline))
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 4)
    }
}

// MARK: - Services (Phosphor Duotone, bleu Nexis)

/// Pastille de service : pictogramme Phosphor bleu sur carré blanc bordé
/// (direction B choisie par Ben). Quand `tour` change, le carré montre un à
/// un les autres objets de son service, puis revient à l'icône principale.
struct ServiceTile: View {
    /// Icône principale d'abord, puis les objets du tour.
    let icons: [String]
    var size: CGFloat = 46
    /// Change pour lancer un tour ; 0 = jamais.
    var tour: Int = 0
    /// Attente avant le premier changement (décalage d'un carré à l'autre).
    var delay: Double = 0

    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var index = 0

    /// Durée d'affichage de chaque objet pendant le tour.
    static let step: Duration = .milliseconds(3500)

    var body: some View {
        RoundedRectangle(cornerRadius: size * 0.32, style: .continuous)
            .fill(Nexis.surface)
            .overlay(RoundedRectangle(cornerRadius: size * 0.32, style: .continuous)
                .strokeBorder(Nexis.tileLine, lineWidth: 1))
            .frame(width: size, height: size)
            .overlay {
                Image(icons[index])
                    .resizable()
                    .renderingMode(.template)
                    .scaledToFit()
                    .frame(width: size * 0.5, height: size * 0.5)
                    .foregroundStyle(Nexis.accent)
                    .id(index)
                    .transition(.blurReplace)
            }
            .animation(.smooth(duration: 0.84), value: index)
            .accessibilityHidden(true)
            .task(id: tour) {
                guard tour > 0, icons.count > 1, !reduceMotion else { return }
                do {
                    try await Task.sleep(for: .seconds(delay))
                    for next in icons.indices.dropFirst() {
                        index = next
                        try await Task.sleep(for: Self.step)
                    }
                } catch {
                    // Feuille fermée pendant le tour : on revient à l'icône principale.
                }
                index = 0
            }
    }
}

extension ServiceTile {
    init(_ item: CatalogService, size: CGFloat = 46, tour: Int = 0, delay: Double = 0) {
        self.init(icons: Pictogrammes.icons(forCatalogId: item.id, service: item.service),
                  size: size, tour: tour, delay: delay)
    }

    init(_ mission: Mission, size: CGFloat = 46) {
        if let item = mission.catalogService {
            self.init(item, size: size)
        } else {
            self.init(icons: Pictogrammes.icons(for: mission.service), size: size)
        }
    }

    init(_ service: Service, size: CGFloat = 46) {
        self.init(icons: Pictogrammes.icons(for: service), size: size)
    }
}

/// « Nouveau » : petite pastille rouge de la maquette.
struct NewBadge: View {
    @Environment(AppModel.self) private var app

    var body: some View {
        Text(app.t("newBadge"))
            .font(.body(10, .bold, relativeTo: .caption2))
            .lineLimit(1)
            .fixedSize()
            .foregroundStyle(.white)
            .padding(.horizontal, 6)
            .padding(.vertical, 2)
            .background(Nexis.newBadge, in: Capsule())
    }
}

// MARK: - Missions

extension MissionStatus {
    var tint: Color {
        switch self {
        case .pending, .quoted: return Nexis.wait
        case .confirmed, .inProgress: return Nexis.accent
        case .awaitingConfirmation: return Nexis.wait
        case .completed: return Nexis.ok
        case .cancelled: return Nexis.muted
        case .disputed: return Nexis.danger
        }
    }
}

extension AppModel {
    func statusLabel(_ mission: Mission) -> String {
        switch mission.status {
        case .pending: return t("statusPending")
        case .quoted: return t("statusQuoted", ["count": String(mission.quotesCount)])
        case .confirmed: return t("statusConfirmed")
        case .inProgress: return t("statusInProgress", ["name": mission.providerName ?? ""])
        case .awaitingConfirmation: return t("statusAwaiting")
        case .completed: return t("statusCompleted")
        case .cancelled: return t("statusCancelled")
        case .disputed: return t("statusDisputed")
        }
    }

    func paymentLabel(_ state: PaymentState) -> String? {
        switch state {
        case .none: return nil
        case .secured: return t("paySecured")
        case .released: return t("payReleased")
        case .refunded: return t("payRefunded")
        case .blocked: return t("payBlocked")
        case .available: return t("payAvailable")
        }
    }

    /// « Aujourd'hui », « Hier », sinon la date en chiffres (les noms de
    /// mois en lingala ne sont pas encore relus).
    func day(_ date: Date) -> String {
        let calendar = Calendar.current
        if calendar.isDateInToday(date) { return t("today") }
        if calendar.isDateInYesterday(date) { return t("yesterday") }
        return date.formatted(.dateTime.day(.twoDigits).month(.twoDigits).year().locale(locale))
    }
}

struct MissionRow: View {
    @Environment(AppModel.self) private var app
    let mission: Mission

    var body: some View {
        HStack(alignment: .top, spacing: 14) {
            ServiceTile(mission, size: 44)
            VStack(alignment: .leading, spacing: 4) {
                HStack(alignment: .firstTextBaseline) {
                    Text(mission.serviceName(app.language))
                        .font(.body(16, .semibold, relativeTo: .headline))
                        .foregroundStyle(Nexis.ink)
                    Spacer(minLength: 8)
                    if let amount = mission.amount {
                        Text(app.amountsHidden ? "•••" : app.money(amount))
                            .font(.title(14, .semibold, relativeTo: .subheadline))
                            .foregroundStyle(Nexis.ink)
                            .monospacedDigit()
                    }
                }
                Text("\(mission.commune) · \(mission.reference)")
                    .font(.body(13, relativeTo: .footnote))
                    .foregroundStyle(Nexis.muted)
                HStack(spacing: 6) {
                    Circle().fill(mission.status.tint).frame(width: 7, height: 7)
                    Text(app.statusLabel(mission))
                        .font(.body(13, .medium, relativeTo: .footnote))
                        .foregroundStyle(mission.status.tint)
                    if let payment = app.paymentLabel(mission.payment) {
                        Text("· \(payment)")
                            .font(.body(13, relativeTo: .footnote))
                            .foregroundStyle(Nexis.muted)
                            .lineLimit(1)
                    }
                }
            }
        }
        .padding(.vertical, 4)
        .accessibilityElement(children: .combine)
    }
}

/// Écran pas encore construit dans l'app native : on le dit, sans faire
/// semblant (« Bientôt dans l'app »).
struct ComingSoonView: View {
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    let title: String

    var body: some View {
        VStack(spacing: 14) {
            Image(systemName: "hammer.fill")
                .font(.system(size: 30, weight: .semibold))
                .foregroundStyle(Nexis.accent)
                .frame(width: 64, height: 64)
                .nxGlass(tint: Nexis.brand.opacity(0.12), in: Circle())
            Text(title).font(.title(20)).foregroundStyle(Nexis.ink)
            Text(app.t("comingSoonText"))
                .font(.body(15)).foregroundStyle(Nexis.muted)
                .multilineTextAlignment(.center)
            Button { dismiss() } label: { WideLabel(text: app.t("ok")) }
                .nxProminentButton()
                .padding(.top, 8)
        }
        .padding(24)
        .presentationDetents([.medium])
    }
}

/// Avatar à initiales.
struct InitialsAvatar: View {
    let initials: String
    var size: CGFloat = 64

    var body: some View {
        Text(initials)
            .font(.title(size * 0.34, .semibold))
            .foregroundStyle(.white)
            .frame(width: size, height: size)
            .background(Nexis.brandGradient, in: Circle())
            .accessibilityHidden(true)
    }
}

/// Titre d'une feuille ouverte par `.sheet(item:)`.
struct SheetTitle: Identifiable {
    let id: String
    init(_ id: String) { self.id = id }
}
