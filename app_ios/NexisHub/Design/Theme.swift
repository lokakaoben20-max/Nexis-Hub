import CoreText
import SwiftUI
import UIKit

/// Identité Nexis validée par Ben : bleu vif #0A63F0 (adopté le
/// 2026-11-23, icône en aplat avec le monogramme blanc), marine #021937,
/// Unbounded pour les titres et les montants, Inter pour le texte.
enum Nexis {
    static let brand = Color(hex: 0x0A63F0)
    static let navy = Color(hex: 0x021937)
    static let halo = Color(hex: 0x0A8CFF)
    /// Dégradé E : version sûre pour poser du texte blanc dessus.
    static let gradientStart = Color(hex: 0x0870EE)
    static let gradientEnd = Color(hex: 0x0350E6)
    static let ok = Color(hex: 0x1E8A4C)
    static let danger = Color(hex: 0xC62828)
    static let wait = Color(hex: 0xB26A00)
    /// Pastille « Nouveau » de la maquette.
    static let newBadge = Color(hex: 0xE5484D)

    static let brandGradient = LinearGradient(
        colors: [gradientStart, gradientEnd], startPoint: .topLeading, endPoint: .bottomTrailing)
    static let heroGradient = LinearGradient(
        colors: [halo, gradientEnd], startPoint: .top, endPoint: .bottom)

    /// Couleurs qui suivent le thème clair ou sombre (mêmes valeurs que
    /// l'app Flutter, NexisPalette).
    static let bg = Color(light: 0xF6F8FB, dark: 0x0B1424)
    static let surface = Color(light: 0xFFFFFF, dark: 0x121E33)
    static let ink = Color(light: 0x021937, dark: 0xEAF0FA)
    static let muted = Color(light: 0x5B667A, dark: 0x9AA7BD)
    static let line = Color(light: 0xE3E8F0, dark: 0x22314B)
    static let soft = Color(light: 0xE8F0FE, dark: 0x1A2B4D)
    static let softInk = Color(light: 0x0A63F0, dark: 0x8DB4FF)
    /// Bleu lisible sur le fond du thème (le bleu Nexis est trop sombre
    /// sur le fond nuit).
    static let accent = Color(light: 0x0A63F0, dark: 0x5B8CFF)
}

extension Color {
    init(hex: UInt32, opacity: Double = 1) {
        self.init(.sRGB,
                  red: Double((hex >> 16) & 0xFF) / 255,
                  green: Double((hex >> 8) & 0xFF) / 255,
                  blue: Double(hex & 0xFF) / 255,
                  opacity: opacity)
    }

    init(light: UInt32, dark: UInt32) {
        self.init(uiColor: UIColor { traits in
            let hex = traits.userInterfaceStyle == .dark ? dark : light
            return UIColor(red: CGFloat((hex >> 16) & 0xFF) / 255,
                           green: CGFloat((hex >> 8) & 0xFF) / 255,
                           blue: CGFloat(hex & 0xFF) / 255,
                           alpha: 1)
        })
    }
}

/// Polices de la charte. Unbounded et Inter sont des polices variables :
/// la graisse est posée directement sur leur axe « wght », ce qui donne
/// exactement la même graisse que l'app Flutter (fontVariations). Les
/// tailles suivent la taille de texte choisie dans Réglages.
enum NexisFont {
    static func ui(_ family: String, _ size: CGFloat, _ weight: Font.Weight,
                   relativeTo style: UIFont.TextStyle?) -> UIFont {
        let wghtAxis = 0x7767_6874 // 'wght'
        let descriptor = UIFontDescriptor(fontAttributes: [
            .family: family,
            UIFontDescriptor.AttributeName(rawValue: kCTFontVariationAttribute as String):
                [wghtAxis: value(weight)],
        ])
        let base = UIFont(descriptor: descriptor, size: size)
        guard let style else { return base }
        return UIFontMetrics(forTextStyle: style).scaledFont(for: base)
    }

    static func value(_ weight: Font.Weight) -> CGFloat {
        switch weight {
        case .ultraLight: return 200
        case .thin: return 250
        case .light: return 300
        case .medium: return 500
        case .semibold: return 600
        case .bold: return 700
        case .heavy: return 800
        case .black: return 900
        default: return 400
        }
    }
}

extension Font {
    /// Unbounded : titres, montants importants, boutons de marque.
    static func title(_ size: CGFloat, _ weight: Font.Weight = .semibold,
                      relativeTo style: UIFont.TextStyle = .title2) -> Font {
        Font(NexisFont.ui("Unbounded", size, weight, relativeTo: style))
    }

    /// Inter : texte courant, descriptions, formulaires.
    static func body(_ size: CGFloat, _ weight: Font.Weight = .regular,
                     relativeTo style: UIFont.TextStyle = .body) -> Font {
        Font(NexisFont.ui("Inter", size, weight, relativeTo: style))
    }

    /// Pictogrammes des services (police NexisServices de l'app Flutter).
    static func services(_ size: CGFloat) -> Font {
        .custom("NexisServices-Regular", fixedSize: size)
    }
}
