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

// MARK: - Services (série B validée)

/// Pastille de service : pictogramme blanc sur carré arrondi de la couleur
/// du service, avec l'ombre colorée des maquettes validées.
struct ServiceTile: View {
    let color: Color
    var service: Service? = nil
    /// Pictogramme système pour un service publié par le serveur que l'app
    /// ne connaît pas encore.
    var fallbackSymbol: String = "sparkles"
    var size: CGFloat = 46

    var body: some View {
        RoundedRectangle(cornerRadius: size * 0.32, style: .continuous)
            .fill(color)
            .frame(width: size, height: size)
            .shadow(color: color.opacity(0.45), radius: size * 0.15, y: size * 0.12)
            .overlay {
                if let service {
                    Text(service.glyph)
                        .font(.services(size * 0.565))
                        .foregroundStyle(.white)
                } else {
                    Image(systemName: fallbackSymbol)
                        .font(.system(size: size * 0.42, weight: .semibold))
                        .foregroundStyle(.white)
                }
            }
            .accessibilityHidden(true)
    }
}

extension ServiceTile {
    init(_ item: CatalogService, size: CGFloat = 46) {
        self.init(color: Color(hex: item.color), service: item.service,
                  fallbackSymbol: ServiceTile.symbol(for: item.id), size: size)
    }

    init(_ mission: Mission, size: CGFloat = 46) {
        if let item = mission.catalogService {
            self.init(item, size: size)
        } else {
            self.init(color: mission.service.color, service: mission.service, size: size)
        }
    }

    static func symbol(for id: String) -> String {
        switch id {
        case "peinture": return "paintbrush.fill"
        case "demenagement": return "shippingbox.fill"
        default: return "sparkles"
        }
    }
}

extension Service {
    /// Caractère de la police NexisServices (U+E000 à U+E008).
    var glyph: String {
        let index = Service.allCases.firstIndex(of: self)!
        return String(UnicodeScalar(0xE000 + UInt32(index))!)
    }

    /// Couleur de chaque service (mêmes valeurs que l'app Flutter).
    var color: Color {
        switch self {
        case .plomberie: return Color(hex: 0x0350E6)
        case .electricite: return Color(hex: 0xC98200)
        case .climatisation: return Color(hex: 0x0A84D6)
        case .informatique: return Color(hex: 0x021937)
        case .graphisme: return Color(hex: 0x494C95)
        case .coiffure: return Color(hex: 0xC2416B)
        case .nettoyage: return Color(hex: 0x1E8A4C)
        case .jardinage: return Color(hex: 0x4F8A10)
        case .autre: return Color(hex: 0x5B667A)
        }
    }
}

/// « Nouveau » : petite pastille rouge de la maquette.
struct NewBadge: View {
    @Environment(AppModel.self) private var app

    var body: some View {
        Text(app.t("newBadge"))
            .font(.body(10, .bold, relativeTo: .caption2))
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
