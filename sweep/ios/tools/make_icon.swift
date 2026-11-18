// Draws the 1024px app icon: a parking P (sun, the app's color for your car) struck through by a
// street-cleaning broom (vermilion), like the broom on the city's alternate side signs.
// Run from ios/: swift tools/make_icon.swift
import CoreGraphics
import CoreText
import Foundation
import ImageIO
import UniformTypeIdentifiers
let S: CGFloat = 1024
func c(_ hex: Int) -> CGColor { CGColor(red: CGFloat(hex >> 16 & 255) / 255, green: CGFloat(hex >> 8 & 255) / 255, blue: CGFloat(hex & 255) / 255, alpha: 1) }
let BG = 0x111311, FG = 0xf2f3ef, SUN = 0xffd23f, VER = 0xff6a45
func draw(_ name: String, pColor: Int, broom: Int) {
    let x = CGContext(data: nil, width: 1024, height: 1024, bitsPerComponent: 8, bytesPerRow: 0, space: CGColorSpace(name: CGColorSpace.sRGB)!, bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue)!
    x.setFillColor(c(BG)); x.fill(CGRect(x: 0, y: 0, width: S, height: S))
    let font = CTFontCreateWithName("HelveticaNeue-CondensedBlack" as CFString, 700, nil)
    let str = NSAttributedString(string: "P", attributes: [NSAttributedString.Key(kCTFontAttributeName as String): font,
                                                           NSAttributedString.Key(kCTForegroundColorAttributeName as String): c(pColor)])
    let line = CTLineCreateWithAttributedString(str)
    let b = CTLineGetImageBounds(line, x)
    x.textPosition = CGPoint(x: (S - b.width) / 2 - b.minX - 10, y: (S - b.height) / 2 - b.minY + 40)
    CTLineDraw(line, x)
    x.saveGState()
    x.translateBy(x: 560, y: 410); x.rotate(by: .pi / 4)
    // dark gap so the broom reads as lying on top of the P
    let gap = CGMutablePath()
    gap.addRect(CGRect(x: -170, y: -58, width: 560, height: 116))
    gap.move(to: CGPoint(x: -150, y: -78)); gap.addLine(to: CGPoint(x: -150, y: 78))
    gap.addLine(to: CGPoint(x: -400, y: 190)); gap.addLine(to: CGPoint(x: -400, y: -190)); gap.closeSubpath()
    x.setFillColor(c(BG)); x.addPath(gap); x.fillPath()
    x.setFillColor(c(broom))
    x.addPath(CGPath(roundedRect: CGRect(x: -120, y: -32, width: 430, height: 58), cornerWidth: 29, cornerHeight: 29, transform: nil)); x.fillPath()   // handle
    x.addPath(CGPath(roundedRect: CGRect(x: -168, y: -54, width: 70, height: 108), cornerWidth: 14, cornerHeight: 14, transform: nil)); x.fillPath()  // collar
    let p = CGMutablePath()
    p.move(to: CGPoint(x: -160, y: -54)); p.addLine(to: CGPoint(x: -160, y: 54))
    p.addLine(to: CGPoint(x: -372, y: 162)); p.addLine(to: CGPoint(x: -372, y: -162)); p.closeSubpath()
    x.addPath(p); x.fillPath()
    x.setStrokeColor(c(BG)); x.setLineWidth(16)
    for k in [-2, -1, 0, 1, 2] {
        let t = CGFloat(k) / 2.6
        x.move(to: CGPoint(x: -230, y: t * 90)); x.addLine(to: CGPoint(x: -380, y: t * 165)); x.strokePath()
    }
    x.restoreGState()
    let d = CGImageDestinationCreateWithURL(URL(fileURLWithPath: name) as CFURL, UTType.png.identifier as CFString, 1, nil)!
    CGImageDestinationAddImage(d, x.makeImage()!, nil); CGImageDestinationFinalize(d)
}
draw("Sweep/Assets.xcassets/AppIcon.appiconset/icon-1024.png", pColor: SUN, broom: VER)
print("icon written")
