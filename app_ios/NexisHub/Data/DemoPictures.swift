import UIKit

/// Photos dessinées par l'app pour l'aperçu (pas de vraies photos de
/// travaux) : un dégradé et un symbole, en JPEG.
enum DemoPictures {
    static func jpeg(symbol: String, top: UInt32 = 0xD6E4F5, bottom: UInt32 = 0x9FB6D6) -> Data {
        let size = CGSize(width: 240, height: 240)
        let format = UIGraphicsImageRendererFormat()
        format.scale = 1
        format.opaque = true
        let image = UIGraphicsImageRenderer(size: size, format: format).image { context in
            let colors = [UIColor(rgb: top).cgColor, UIColor(rgb: bottom).cgColor] as CFArray
            if let gradient = CGGradient(colorsSpace: CGColorSpaceCreateDeviceRGB(), colors: colors, locations: [0, 1]) {
                context.cgContext.drawLinearGradient(gradient, start: .zero, end: CGPoint(x: 0, y: size.height), options: [])
            }
            let configuration = UIImage.SymbolConfiguration(pointSize: 64, weight: .regular)
            if let glyph = UIImage(systemName: symbol, withConfiguration: configuration)?
                .withTintColor(UIColor(rgb: 0x24344D).withAlphaComponent(0.7), renderingMode: .alwaysOriginal) {
                glyph.draw(at: CGPoint(x: (size.width - glyph.size.width) / 2, y: (size.height - glyph.size.height) / 2))
            }
        }
        return image.jpegData(compressionQuality: 0.8) ?? Data()
    }
}

private extension UIColor {
    convenience init(rgb: UInt32) {
        self.init(red: CGFloat((rgb >> 16) & 0xFF) / 255, green: CGFloat((rgb >> 8) & 0xFF) / 255,
                  blue: CGFloat(rgb & 0xFF) / 255, alpha: 1)
    }
}
