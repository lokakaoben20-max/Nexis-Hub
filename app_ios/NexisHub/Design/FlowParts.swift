import SwiftUI

// Pièces communes aux écrans de mission (suivi, devis, paiement, litige,
// espace prestataire). Mêmes couleurs que l'app Flutter (ui/common.dart,
// ui/parts.dart), posées dans le style iOS validé.

// MARK: - Dates et heures

extension AppModel {
    /// Noms des jours, lundi d'abord (les noms lingala sont à relire par
    /// une personne de Kinshasa, comme dans l'app Flutter).
    private static let weekdays: [String: [String]] = [
        "fr": ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"],
        "ln": ["mokɔlɔ ya yambo", "mokɔlɔ ya mibale", "mokɔlɔ ya misato", "mokɔlɔ ya minei",
               "mokɔlɔ ya mitano", "mposɔ", "lomingo"],
        "en": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
    ]
    private static let shortWeekdays: [String: [String]] = [
        "fr": ["lun.", "mar.", "mer.", "jeu.", "ven.", "sam.", "dim."],
        "en": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
    ]

    /// Lundi = 0 … dimanche = 6.
    private static func mondayIndex(_ date: Date) -> Int {
        (Calendar.current.component(.weekday, from: date) + 5) % 7
    }

    /// « 9 h », « 8 h 41 » ; en anglais « 9 am », « 8:41 am ».
    func clock(_ date: Date) -> String {
        let parts = Calendar.current.dateComponents([.hour, .minute], from: date)
        let hour = parts.hour ?? 0, minute = parts.minute ?? 0
        let mm = String(format: "%02d", minute)
        if language == "en" {
            let h = hour % 12 == 0 ? 12 : hour % 12
            let suffix = hour < 12 ? "am" : "pm"
            return minute == 0 ? "\(h) \(suffix)" : "\(h):\(mm) \(suffix)"
        }
        return minute == 0 ? "\(hour) h" : "\(hour) h \(mm)"
    }

    /// « samedi 9 h » (ou « Samedi 9 h »).
    func slot(_ date: Date, capital: Bool = false) -> String {
        let days = Self.weekdays[language] ?? Self.weekdays["fr"]!
        let text = "\(days[Self.mondayIndex(date)]) \(clock(date))"
        return capital ? text.prefix(1).uppercased() + text.dropFirst() : text
    }

    /// « 13 h » aujourd'hui, sinon « sam. 13 h » (le lingala garde le jour entier).
    func stamp(_ date: Date) -> String {
        if Calendar.current.isDateInToday(date) { return clock(date) }
        let days = Self.shortWeekdays[language] ?? Self.weekdays[language] ?? Self.weekdays["fr"]!
        return "\(days[Self.mondayIndex(date)]) \(clock(date))"
    }

    /// « 4,9 » (« 4.9 » en anglais).
    func rating(_ value: Double) -> String {
        let text = String(format: "%.1f", value)
        return language == "en" ? text : text.replacingOccurrences(of: ".", with: ",")
    }

    /// « Plomberie · Gombe ».
    func place(_ mission: Mission) -> String {
        "\(mission.serviceName(language)) · \(mission.commune)"
    }
}

/// Jours entiers qui restent avant `until` (au moins 1 tant que ce n'est pas
/// passé, 0 ensuite).
func daysLeft(until: Date, now: Date = .now) -> Int {
    let left = until.timeIntervalSince(now)
    guard left > 0 else { return 0 }
    return Int((left / 86_400).rounded(.up))
}

// MARK: - Pastilles

enum PillTone {
    case secured, ok, info, warn, wait, bad

    var colors: (background: Color, text: Color) {
        switch self {
        case .secured: return (Color(light: 0xE8F0FE, dark: 0x1A2B4D), Color(light: 0x0A3D9E, dark: 0x8DB4FF))
        case .ok: return (Color(light: 0xE3F5EA, dark: 0x12301F), Color(light: 0x17663A, dark: 0x5BD08A))
        case .info: return (Color(light: 0xECECF8, dark: 0x22234A), Color(light: 0x3B3E80, dark: 0xB3B5F2))
        case .warn: return (Color(light: 0xFFF1D6, dark: 0x33270D), Color(light: 0x7A4E00, dark: 0xF2C661))
        case .wait: return (Color(light: 0xEEF1F5, dark: 0x1A2740), Color(light: 0x4E5B70, dark: 0xA9B4C6))
        case .bad: return (Color(light: 0xFDECEA, dark: 0x3A1715), Color(light: 0xB42318, dark: 0xFF8A80))
        }
    }
}

struct Pill: View {
    let tone: PillTone
    var systemImage: String? = nil
    let text: String

    var body: some View {
        let colors = tone.colors
        HStack(spacing: 5) {
            if let systemImage {
                Image(systemName: systemImage).font(.system(size: 11, weight: .semibold))
            }
            Text(text).font(.body(12, .semibold, relativeTo: .caption1)).lineLimit(1)
        }
        .foregroundStyle(colors.text)
        .padding(.horizontal, 10)
        .padding(.vertical, 5)
        .background(colors.background, in: Capsule())
    }
}

/// L'état de l'argent, avec sa couleur de la charte.
struct PaymentPill: View {
    @Environment(AppModel.self) private var app
    let state: PaymentState
    var text: String? = nil

    var body: some View {
        let look = Self.look(state)
        Pill(tone: look.tone, systemImage: look.symbol, text: text ?? app.paymentLabel(state) ?? "")
    }

    private static func look(_ state: PaymentState) -> (symbol: String, tone: PillTone) {
        switch state {
        case .secured: return ("lock.shield.fill", .secured)
        case .released: return ("checkmark.circle.fill", .ok)
        case .refunded: return ("arrow.uturn.backward", .info)
        case .blocked: return ("lock.fill", .bad)
        case .available: return ("wallet.bifold.fill", .ok)
        case .none: return ("clock", .wait)
        }
    }
}

// MARK: - Notes

/// Encadré d'information (bleu), de décision (violet) ou d'argent bloqué (rouge).
struct InfoNote: View {
    enum Kind { case info, violet, danger }

    let text: String
    var kind: Kind = .info
    var systemImage: String = "info.circle.fill"

    private var colors: (background: Color, foreground: Color) {
        switch kind {
        case .info: return (Color(light: 0xE8F0FE, dark: 0x1A2B4D), Color(light: 0x0A3D9E, dark: 0x8DB4FF))
        case .violet: return (Color(light: 0xECECF8, dark: 0x22234A), Color(light: 0x3B3E80, dark: 0xB3B5F2))
        case .danger: return (Color(light: 0xFFF6F5, dark: 0x3A1715), Color(light: 0x7A3A33, dark: 0xFFB4AB))
        }
    }

    var body: some View {
        let background = colors.background, foreground = colors.foreground
        HStack(alignment: .top, spacing: 10) {
            Image(systemName: systemImage)
                .font(.system(size: 15, weight: .semibold))
                .padding(.top, 1)
            Text(text)
                .font(.body(13.5, relativeTo: .footnote))
                .lineSpacing(3)
                .frame(maxWidth: .infinity, alignment: .leading)
        }
        .foregroundStyle(foreground)
        .padding(14)
        .background(background, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
        .accessibilityElement(children: .combine)
    }
}

// MARK: - Personnes

/// Rond coloré à initiales (couleur donnée par le serveur).
struct PersonAvatar: View {
    let initials: String
    let color: UInt32
    var size: CGFloat = 44

    var body: some View {
        Text(initials)
            .font(.body(size / 3, .bold))
            .foregroundStyle(.white)
            .frame(width: size, height: size)
            .background(Color(hex: color), in: Circle())
            .accessibilityHidden(true)
    }
}

/// « ★ 4,9 (128) ».
struct Stars: View {
    @Environment(AppModel.self) private var app
    let rating: Double
    let reviews: Int

    var body: some View {
        HStack(spacing: 3) {
            Image(systemName: "star.fill")
                .font(.system(size: 11))
                .foregroundStyle(Color(hex: 0xE3A008))
            Text("\(app.rating(rating)) (\(reviews))")
                .font(.body(12.5, .semibold, relativeTo: .caption1))
                .foregroundStyle(Nexis.ink)
        }
    }
}

/// Une personne et sa note, avec des boutons ronds à droite.
struct PersonHeader<Trailing: View>: View {
    let initials: String
    let color: UInt32
    let name: String
    var rating: Double? = nil
    var reviews: Int? = nil
    var subtitle: String? = nil
    @ViewBuilder var trailing: Trailing

    var body: some View {
        HStack(spacing: 12) {
            PersonAvatar(initials: initials, color: color)
            VStack(alignment: .leading, spacing: 3) {
                Text(name).font(.body(15.5, .bold)).foregroundStyle(Nexis.ink)
                if let rating, let reviews { Stars(rating: rating, reviews: reviews) }
                if let subtitle {
                    Text(subtitle).font(.body(13, relativeTo: .footnote))
                        .foregroundStyle(Nexis.muted).lineLimit(1)
                }
            }
            Spacer(minLength: 8)
            trailing
        }
    }
}

/// Bouton rond bleu clair (appeler, écrire).
struct RoundIconButton: View {
    let systemImage: String
    let label: String
    var size: CGFloat = 42
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Image(systemName: systemImage)
                .font(.system(size: size * 0.42, weight: .semibold))
                .foregroundStyle(Nexis.softInk)
                .frame(width: size, height: size)
                .background(Nexis.soft, in: Circle())
        }
        .buttonStyle(.plain)
        .accessibilityLabel(label)
    }
}

// MARK: - Étapes

enum StepState { case done, now, todo }

struct StepItem: Identifiable {
    let title: String
    var sub: String? = nil
    var time: String? = nil
    let state: StepState
    var id: String { title }
}

/// Frise des étapes : points bleus pleins pour les étapes faites, point
/// entouré pour l'étape en cours, trait bleu entre les faites.
struct StepList: View {
    let items: [StepItem]

    var body: some View {
        VStack(spacing: 0) {
            ForEach(Array(items.enumerated()), id: \.offset) { index, item in
                HStack(alignment: .top, spacing: 12) {
                    VStack(spacing: 0) {
                        dot(item.state)
                        if index < items.count - 1 {
                            Rectangle()
                                .fill(item.state == .done ? Nexis.brand : Color(light: 0xE3E7EE, dark: 0x22314B))
                                .frame(width: 2)
                                .frame(maxHeight: .infinity)
                        }
                    }
                    .frame(width: 22)
                    VStack(alignment: .leading, spacing: 2) {
                        Text(item.title)
                            .font(.body(14.5, item.state == .todo ? .medium : .bold))
                            .foregroundStyle(item.state == .todo ? Color(light: 0x8A94A6, dark: 0x7D8AA3) : Nexis.ink)
                        if let sub = item.sub {
                            Text(sub).font(.body(13, relativeTo: .footnote)).foregroundStyle(Nexis.muted)
                        }
                    }
                    .padding(.top, 1)
                    .padding(.bottom, index < items.count - 1 ? 16 : 0)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    if let time = item.time {
                        Text(time)
                            .font(.body(12.5, .medium, relativeTo: .caption1))
                            .foregroundStyle(Nexis.muted)
                            .monospacedDigit()
                            .padding(.top, 2)
                    }
                }
                .fixedSize(horizontal: false, vertical: true)
                .accessibilityElement(children: .combine)
            }
        }
    }

    @ViewBuilder
    private func dot(_ state: StepState) -> some View {
        switch state {
        case .done:
            Circle().fill(Nexis.brand).frame(width: 22, height: 22)
                .overlay(Image(systemName: "checkmark").font(.system(size: 10, weight: .heavy)).foregroundStyle(.white))
        case .now:
            Circle().fill(Nexis.surface).frame(width: 22, height: 22)
                .overlay(Circle().strokeBorder(Nexis.brand, lineWidth: 2))
                .overlay(Circle().fill(Nexis.brand).frame(width: 8, height: 8))
                .background(Circle().fill(Color(light: 0xDCEBFF, dark: 0x1A2B4D)).padding(-4))
        case .todo:
            Circle().fill(Nexis.surface).frame(width: 22, height: 22)
                .overlay(Circle().strokeBorder(Color(light: 0xC9D0DB, dark: 0x3A4A66), lineWidth: 2))
        }
    }
}

// MARK: - Choix

/// Rond de choix unique (opérateur, raison du litige).
struct RadioDot: View {
    let selected: Bool

    var body: some View {
        Circle()
            .strokeBorder(selected ? Nexis.brand : Color(light: 0xC9D0DB, dark: 0x3A4A66),
                          lineWidth: selected ? 6 : 2)
            .frame(width: 22, height: 22)
            .animation(.snappy(duration: 0.2), value: selected)
    }
}

/// Ligne de choix dans une carte, bordée de bleu quand elle est choisie.
struct ChoiceRow<Leading: View>: View {
    let title: String
    var subtitle: String? = nil
    let selected: Bool
    @ViewBuilder var leading: Leading
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 12) {
                leading
                VStack(alignment: .leading, spacing: 2) {
                    Text(title).font(.body(15, selected ? .semibold : .medium)).foregroundStyle(Nexis.ink)
                    if let subtitle {
                        Text(subtitle).font(.body(13, relativeTo: .footnote)).foregroundStyle(Nexis.muted)
                    }
                }
                Spacer(minLength: 8)
                RadioDot(selected: selected)
            }
            .padding(.horizontal, 14)
            .padding(.vertical, 13)
            .background(Nexis.surface, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 16, style: .continuous)
                .strokeBorder(selected ? Nexis.brand : Nexis.line, lineWidth: selected ? 2 : 0.5))
            .contentShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
        }
        .buttonStyle(.plain)
        .accessibilityAddTraits(selected ? .isSelected : [])
    }
}

/// Le logo de l'opérateur sur un fond blanc (logos repris tels quels, sans
/// les redessiner). Africell : une lettre en attendant son logo.
struct OperatorBadge: View {
    let mobileOperator: MobileOperator

    private var logo: String? {
        switch mobileOperator {
        case .mpesa: return "OpMpesa"
        case .orange: return "OpOrange"
        case .airtel: return "OpAirtel"
        case .africell: return nil
        }
    }

    var body: some View {
        Group {
            if let logo {
                Image(logo)
                    .resizable().scaledToFit()
                    .padding(6)
                    .frame(width: 58, height: 40)
                    .background(.white, in: RoundedRectangle(cornerRadius: 12, style: .continuous))
                    .overlay(RoundedRectangle(cornerRadius: 12, style: .continuous)
                        .strokeBorder(Nexis.line, lineWidth: 0.5))
            } else {
                Text("Af")
                    .font(.body(14, .heavy))
                    .foregroundStyle(.white)
                    .frame(width: 58, height: 40)
                    .background(Color(hex: 0x7B2D8E), in: RoundedRectangle(cornerRadius: 12, style: .continuous))
            }
        }
        .accessibilityHidden(true)
    }
}

/// Case photo. L'envoi et l'affichage des photos arrivent avec le serveur :
/// en attendant, la case le dit au lieu de faire semblant.
struct PhotoSlot: View {
    let systemImage: String
    let label: String
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            RoundedRectangle(cornerRadius: 14, style: .continuous)
                .fill(LinearGradient(colors: [Color(light: 0xDDE6F0, dark: 0x223047),
                                              Color(light: 0xC8D4E2, dark: 0x1A263A)],
                                     startPoint: .topLeading, endPoint: .bottomTrailing))
                .frame(width: 64, height: 64)
                .overlay(Image(systemName: systemImage).font(.system(size: 20)).foregroundStyle(Color(hex: 0x7B8AA0)))
        }
        .buttonStyle(.plain)
        .accessibilityLabel(label)
    }
}

/// Puces qui passent à la ligne (créneaux, souhaits).
struct WrapLayout: Layout {
    var spacing: CGFloat = 8

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let rows = arrange(width: proposal.width ?? .infinity, subviews: subviews)
        let height = rows.last.map { $0.y + $0.height } ?? 0
        let width = rows.map(\.width).max() ?? 0
        return CGSize(width: proposal.width ?? width, height: height)
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        for row in arrange(width: bounds.width, subviews: subviews) {
            var x = bounds.minX
            for index in row.items {
                let size = subviews[index].sizeThatFits(.unspecified)
                subviews[index].place(at: CGPoint(x: x, y: bounds.minY + row.y), proposal: ProposedViewSize(size))
                x += size.width + spacing
            }
        }
    }

    private struct Row { var items: [Int] = []; var y: CGFloat = 0; var width: CGFloat = 0; var height: CGFloat = 0 }

    private func arrange(width: CGFloat, subviews: Subviews) -> [Row] {
        var rows: [Row] = [Row()]
        for index in subviews.indices {
            let size = subviews[index].sizeThatFits(.unspecified)
            if !rows[rows.count - 1].items.isEmpty, rows[rows.count - 1].width + spacing + size.width > width {
                let last = rows[rows.count - 1]
                rows.append(Row(y: last.y + last.height + spacing))
            }
            var row = rows[rows.count - 1]
            row.width += (row.items.isEmpty ? 0 : spacing) + size.width
            row.height = max(row.height, size.height)
            row.items.append(index)
            rows[rows.count - 1] = row
        }
        return rows
    }
}

// MARK: - Boutons

/// Libellé d'un bouton qui attend le serveur : les pictogrammes se relaient
/// à la place du texte.
struct BusyLabel: View {
    let text: String
    var systemImage: String? = nil
    var busy = false
    var loaderColor: Color = .white

    var body: some View {
        ZStack {
            WideLabel(text: text, systemImage: systemImage).opacity(busy ? 0 : 1)
            if busy { PictoLoader(size: 22, color: loaderColor, label: text) }
        }
    }
}

extension View {
    /// Boutons d'action posés en bas de l'écran, au-dessus du contenu.
    func bottomActions(@ViewBuilder _ actions: () -> some View) -> some View {
        safeAreaInset(edge: .bottom) {
            VStack(spacing: 10) { actions() }
                .padding(.horizontal, 18)
                .padding(.top, 10)
                .padding(.bottom, 8)
                .background(Nexis.bg.opacity(0.96).ignoresSafeArea(edges: .bottom))
        }
    }

    /// Le fond et les marges des écrans de mission.
    func flowScreen() -> some View {
        self.padding(.horizontal, 18)
            .padding(.top, 6)
            .padding(.bottom, 24)
    }
}

/// Bouton bordé (« Signaler un problème », « Appeler Esther »).
struct OutlineButtonStyle: ButtonStyle {
    var tint: Color = Nexis.ink

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .foregroundStyle(tint)
            .padding(.vertical, 12)
            .frame(maxWidth: .infinity)
            .background(Nexis.surface, in: Capsule())
            .overlay(Capsule().strokeBorder(Color(light: 0xD5DBE5, dark: 0x2D3D5A), lineWidth: 1))
            .opacity(configuration.isPressed ? 0.7 : 1)
    }
}

// MARK: - Message bref

/// Message bref en bas de l'écran (« Merci ! Nadia reçoit l'argent. »).
struct Toast: View {
    let text: String

    var body: some View {
        Text(text)
            .font(.body(14.5, .medium))
            .foregroundStyle(.white)
            .multilineTextAlignment(.center)
            .padding(.horizontal, 18)
            .padding(.vertical, 12)
            .background(Nexis.navy.opacity(0.94), in: Capsule())
            .padding(.horizontal, 24)
            .accessibilityAddTraits(.isStaticText)
    }
}
