// Draws the 1024px app icon: a street seen from above, two curbs, the car (sun square)
// against the near curb and the sweeper's broom marks (vermilion) coming down the far side.
// Run from ios/: swift tools/make_icon.swift
import CoreGraphics
import ImageIO
import UniformTypeIdentifiers
let size = 1024
let ctx = CGContext(data: nil, width: size, height: size, bitsPerComponent: 8, bytesPerRow: 0,
                    space: CGColorSpace(name: CGColorSpace.sRGB)!, bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue)!
func c(_ hex: Int) -> CGColor { CGColor(red: CGFloat(hex >> 16 & 255) / 255, green: CGFloat(hex >> 8 & 255) / 255, blue: CGFloat(hex & 255) / 255, alpha: 1) }
ctx.setFillColor(c(0x111311)); ctx.fill(CGRect(x: 0, y: 0, width: size, height: size))
// curbs (CoreGraphics origin is bottom-left)
ctx.setFillColor(c(0xf2f3ef))
ctx.fill(CGRect(x: 0, y: 236, width: 1024, height: 44))
ctx.fill(CGRect(x: 0, y: 744, width: 1024, height: 44))
// the car, parked against the near curb
ctx.setFillColor(c(0xffd23f))
ctx.fill(CGRect(x: 548, y: 292, width: 300, height: 176))
// broom marks along the far curb
ctx.setStrokeColor(c(0xff6a45)); ctx.setLineWidth(34); ctx.setLineCap(.butt)
for i in 0..<5 {
    let x = CGFloat(120 + i * 92)
    ctx.move(to: CGPoint(x: x, y: 724)); ctx.addLine(to: CGPoint(x: x + 70, y: 560)); ctx.strokePath()
}
let url = URL(fileURLWithPath: "Sweep/Assets.xcassets/AppIcon.appiconset/icon-1024.png") as CFURL
let dest = CGImageDestinationCreateWithURL(url, UTType.png.identifier as CFString, 1, nil)!
CGImageDestinationAddImage(dest, ctx.makeImage()!, nil)
CGImageDestinationFinalize(dest)
print("icon written")
