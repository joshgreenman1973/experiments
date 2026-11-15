import SwiftUI
import UIKit
import CoreText

/// House style v5, "black": black ground, paper text, saturated inks that mean something.
/// Archivo for display, Karla for reading. Square corners, no shadows, no gradients.
enum Theme {
    static let bg = Color(hex: 0x111311)
    static let bg2 = Color(hex: 0x1b1e1b)
    static let fg = Color(hex: 0xf2f3ef)
    static let fg2 = Color(hex: 0xa2a8a1)
    static let line = Color(hex: 0x3a3f3a)
    static let sun = Color(hex: 0xffd23f)        // your car, the thing to act on
    static let vermilion = Color(hex: 0xff6a45)  // under a day: move it
    static let orange = Color(hex: 0xff9f2e)     // one to three days
    static let mint = Color(hex: 0x3fd68f)       // three days or more, or suspended
    static let cobalt = Color(hex: 0x5b86ff)     // the other side of the street

    static func registerFonts() {
        for name in ["Archivo", "Karla"] {
            if let u = Bundle.main.url(forResource: name, withExtension: "woff2") ?? Bundle.main.url(forResource: name, withExtension: "woff2", subdirectory: "Fonts") {
                CTFontManagerRegisterFontsForURL(u as CFURL, .process, nil)
            }
        }
    }

    private static func make(_ ps: String, _ size: CGFloat, _ wght: CGFloat, wdth: CGFloat?, _ style: UIFont.TextStyle) -> Font {
        var variation: [NSNumber: CGFloat] = [NSNumber(value: 0x77676874): wght]
        if let w = wdth { variation[NSNumber(value: 0x77647468)] = w }
        let d = UIFontDescriptor(fontAttributes: [
            .name: ps,
            UIFontDescriptor.AttributeName(rawValue: kCTFontVariationAttribute as String): variation,
        ])
        let base = UIFont(descriptor: d, size: size)
        let f = base.familyName.lowercased().contains(ps.prefix(5).lowercased()) ? base : UIFont.systemFont(ofSize: size, weight: wght >= 650 ? .bold : .regular)
        return Font(UIFontMetrics(forTextStyle: style).scaledFont(for: f) as CTFont)
    }

    /// Archivo, slightly condensed.
    static func display(_ size: CGFloat, _ weight: CGFloat = 700, style: UIFont.TextStyle = .title1) -> Font {
        make("ArchivoRoman-Regular", size, weight, wdth: 88, style)
    }
    /// Karla for reading text.
    static func body(_ size: CGFloat = 17, _ weight: CGFloat = 400, style: UIFont.TextStyle = .body) -> Font {
        make("Karla-Regular", size, weight, wdth: nil, style)
    }
}

extension Color {
    init(hex: Int) {
        self.init(.sRGB, red: Double(hex >> 16 & 255) / 255, green: Double(hex >> 8 & 255) / 255, blue: Double(hex & 255) / 255, opacity: 1)
    }
}

/// A square button: solid ink with black text, or an outline.
struct SquareButton: ButtonStyle {
    var fill: Color? = Theme.sun
    var ink: Color = Theme.bg
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(Theme.display(19, 700, style: .headline))
            .foregroundStyle(fill == nil ? Theme.fg : ink)
            .frame(maxWidth: .infinity, minHeight: 54)
            .padding(.horizontal, 14)
            .background(fill ?? Color.clear)
            .overlay(Rectangle().stroke(fill == nil ? Theme.line : Color.clear, lineWidth: 1.5))
            .opacity(configuration.isPressed ? 0.75 : 1)
            .contentShape(Rectangle())
    }
}
