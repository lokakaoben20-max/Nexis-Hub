import Foundation

/// Montants : la seule façon d'afficher de l'argent dans l'app.
///
/// L'app ne calcule jamais d'argent : elle affiche les montants que le
/// serveur Nexis envoie, en unités mineures et sans virgule flottante,
/// avec les règles de la charte : « 25 000 FC » sans décimales et
/// « 12,50 USD » toujours avec deux décimales.
enum Currency: String, CaseIterable, Hashable {
    case cdf, usd
}

struct Money: Hashable {
    /// Francs congolais : en francs. Dollars : en cents.
    let minorUnits: Int
    let currency: Currency

    init(_ minorUnits: Int, _ currency: Currency) {
        self.minorUnits = minorUnits
        self.currency = currency
    }

    var isZero: Bool { minorUnits == 0 }

    /// Même règle que l'app Flutter (`formatMoney`) : espace fine
    /// insécable en français et en lingala, virgule en anglais.
    func formatted(_ language: String) -> String {
        let english = language == "en"
        let group = english ? "," : "\u{202F}"
        let sign = minorUnits < 0 ? "−" : ""
        let absolute = minorUnits.magnitude

        func grouped(_ value: UInt) -> String {
            let digits = Array(String(value))
            var out = ""
            for (i, digit) in digits.enumerated() {
                if i > 0 && (digits.count - i) % 3 == 0 { out += group }
                out.append(digit)
            }
            return out
        }

        switch currency {
        case .cdf:
            return "\(sign)\(grouped(absolute)) FC"
        case .usd:
            let cents = String(absolute % 100)
            let padded = cents.count == 1 ? "0" + cents : cents
            return "\(sign)\(grouped(absolute / 100))\(english ? "." : ",")\(padded) USD"
        }
    }
}
