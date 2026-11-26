import Foundation

/// Opérateurs mobiles de la RDC, d'après les deux chiffres qui suivent
/// +243. Contrôle de confort à la saisie seulement : le serveur reste seul
/// juge du numéro (backend/app/app_auth.py). Même règle que
/// app_mobile/lib/ui/phone.dart.
enum DrcOperator: CaseIterable {
    case vodacom, airtel, orange, africell

    var prefixes: Set<String> {
        switch self {
        case .vodacom: return ["81", "82", "83"]
        case .airtel: return ["97", "98", "99"]
        case .orange: return ["80", "84", "85", "89"]
        case .africell: return ["90", "91"]
        }
    }
}

/// Le numéro national saisi : 9 chiffres, sans le 0 d'appel ni le +243.
struct DrcPhone: Equatable {
    static let length = 9
    let digits: String

    /// Garde les chiffres, retire un +243 / 00243 / 243 ou un 0 d'appel
    /// collé en tête, et coupe à 9 chiffres.
    static func parse(_ raw: String) -> DrcPhone {
        var d = raw.filter(\.isASCIIDigit)
        if d.hasPrefix("00243") {
            d = String(d.dropFirst(5))
        } else if d.hasPrefix("243") && d.count > length {
            d = String(d.dropFirst(3))
        } else if d.hasPrefix("0") {
            d = String(d.dropFirst())
        }
        return DrcPhone(digits: String(d.prefix(length)))
    }

    var isComplete: Bool { digits.count == Self.length }

    var drcOperator: DrcOperator? {
        guard digits.count >= 2 else { return nil }
        let prefix = String(digits.prefix(2))
        return DrcOperator.allCases.first { $0.prefixes.contains(prefix) }
    }

    /// Faux dès que les deux premiers chiffres ne sont ceux d'aucun opérateur.
    var prefixKnown: Bool { digits.count < 2 || drcOperator != nil }

    var isValid: Bool { isComplete && drcOperator != nil }

    /// `81 234 5678` (maquette de connexion).
    var formatted: String {
        var parts: [String] = []
        var rest = Substring(digits)
        for size in [2, 3, 4] where !rest.isEmpty {
            parts.append(String(rest.prefix(size)))
            rest = rest.dropFirst(size)
        }
        return parts.joined(separator: " ")
    }

    /// Format international attendu par le serveur : `+243812345454`.
    var e164: String { "+243" + digits }
}

private extension Character {
    var isASCIIDigit: Bool { ("0"..."9").contains(self) }
}
