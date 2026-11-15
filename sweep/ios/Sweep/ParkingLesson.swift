import SwiftUI
import WebKit

/// The six-step parallel parking lesson (Web/parking.html, ported from the "Parallel parking two Kias"
/// artifact). Defaults to the 2027 Kia Seltos; anyone can pick another size or enter their own numbers.
/// Runs offline from the bundle.
struct ParkingLessonView: View {
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        VStack(spacing: 0) {
            HStack(alignment: .firstTextBaseline) {
                Text("How to parallel park").font(Theme.display(24, 750, style: .title2))
                Spacer()
                Button("Done") { dismiss() }.font(Theme.body(17, 700)).foregroundStyle(Theme.sun)
            }
            .padding(.horizontal, 16).padding(.top, 14).padding(.bottom, 4)
            LessonWeb()
        }
        .background(Theme.bg.ignoresSafeArea())
        .foregroundStyle(Theme.fg)
    }
}

private struct LessonWeb: UIViewRepresentable {
    func makeUIView(context: Context) -> WKWebView {
        let w = WKWebView(frame: .zero, configuration: WKWebViewConfiguration())
        w.isOpaque = false
        w.backgroundColor = UIColor(Theme.bg)
        w.scrollView.backgroundColor = UIColor(Theme.bg)
        w.scrollView.contentInsetAdjustmentBehavior = .never
        w.allowsLinkPreview = false
        if let url = Bundle.main.url(forResource: "parking", withExtension: "html")
            ?? Bundle.main.url(forResource: "parking", withExtension: "html", subdirectory: "Web") {
            w.loadFileURL(url, allowingReadAccessTo: url.deletingLastPathComponent())
        }
        return w
    }

    func updateUIView(_ w: WKWebView, context: Context) {}
}
