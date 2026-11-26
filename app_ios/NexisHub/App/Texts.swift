import Foundation

/// Les textes de Nexis en français, lingala et anglais.
///
/// Source unique : app_mobile/lib/l10n/*.arb, copiés dans textes.json par
/// outils/textes_apps_natives.py. Rien n'est traduit ici.
struct Texts {
    enum Entry {
        case text(String)
        case plural([String: String])
    }

    private let table: [String: [String: Entry]]

    static let shared: Texts = {
        guard let url = Bundle.main.url(forResource: "textes", withExtension: "json"),
              let data = try? Data(contentsOf: url) else {
            assertionFailure("textes.json absent du paquet de l'app")
            return Texts(table: [:])
        }
        return Texts(json: data)
    }()

    init(json: Data) {
        let raw = (try? JSONSerialization.jsonObject(with: json)) as? [String: [String: Any]] ?? [:]
        var table: [String: [String: Entry]] = [:]
        for (key, languages) in raw {
            var entries: [String: Entry] = [:]
            for (language, value) in languages {
                if let text = value as? String {
                    entries[language] = .text(text)
                } else if let forms = value as? [String: String] {
                    entries[language] = .plural(forms)
                }
            }
            table[key] = entries
        }
        self.table = table
    }

    private init(table: [String: [String: Entry]]) { self.table = table }

    /// Texte simple. Les variables {nom} sont remplacées par `args`.
    func text(_ key: String, _ language: String, _ args: [String: String] = [:]) -> String {
        guard let entry = table[key]?[language] ?? table[key]?["fr"] else {
            assertionFailure("texte inconnu : \(key)")
            return key
        }
        switch entry {
        case .text(let text):
            return Self.fill(text, args)
        case .plural(let forms):
            return Self.fill(forms["other"] ?? key, args)
        }
    }

    /// Texte au pluriel ICU : « =0 », « =1 », sinon « other ».
    func plural(_ key: String, _ language: String, count: Int, _ args: [String: String] = [:]) -> String {
        guard let entry = table[key]?[language] ?? table[key]?["fr"] else {
            assertionFailure("texte inconnu : \(key)")
            return key
        }
        var values = args
        values["count"] = String(count)
        switch entry {
        case .text(let text):
            return Self.fill(text, values)
        case .plural(let forms):
            return Self.fill(forms["=\(count)"] ?? forms["other"] ?? key, values)
        }
    }

    static func fill(_ text: String, _ args: [String: String]) -> String {
        var out = text
        for (name, value) in args {
            out = out.replacingOccurrences(of: "{\(name)}", with: value)
        }
        return out
    }
}
