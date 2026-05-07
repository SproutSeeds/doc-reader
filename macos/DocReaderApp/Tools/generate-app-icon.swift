import AppKit
import Foundation

private struct IconSize {
    let points: Int
    let scale: Int

    var pixels: Int {
        points * scale
    }

    var filename: String {
        scale == 1 ? "icon_\(points)x\(points).png" : "icon_\(points)x\(points)@\(scale)x.png"
    }
}

private let sizes = [
    IconSize(points: 16, scale: 1),
    IconSize(points: 16, scale: 2),
    IconSize(points: 32, scale: 1),
    IconSize(points: 32, scale: 2),
    IconSize(points: 128, scale: 1),
    IconSize(points: 128, scale: 2),
    IconSize(points: 256, scale: 1),
    IconSize(points: 256, scale: 2),
    IconSize(points: 512, scale: 1),
    IconSize(points: 512, scale: 2),
]

guard CommandLine.arguments.count == 2 else {
    fputs("usage: generate-app-icon.swift <output.iconset>\n", stderr)
    exit(64)
}

let outputURL = URL(fileURLWithPath: CommandLine.arguments[1], isDirectory: true)
try FileManager.default.createDirectory(at: outputURL, withIntermediateDirectories: true)

for size in sizes {
    let image = renderIcon(pixelSize: size.pixels)
    let output = outputURL.appendingPathComponent(size.filename)
    guard let tiff = image.tiffRepresentation,
          let rep = NSBitmapImageRep(data: tiff),
          let png = rep.representation(using: .png, properties: [:]) else {
        fputs("could not render \(size.filename)\n", stderr)
        exit(1)
    }
    try png.write(to: output)
}

private func renderIcon(pixelSize: Int) -> NSImage {
    let canvas = CGFloat(pixelSize)
    let image = NSImage(size: NSSize(width: canvas, height: canvas))
    image.lockFocus()
    defer { image.unlockFocus() }

    NSGraphicsContext.current?.shouldAntialias = true
    NSGraphicsContext.current?.imageInterpolation = .high

    let bounds = NSRect(x: 0, y: 0, width: canvas, height: canvas)
    let radius = canvas * 0.22
    let background = NSBezierPath(roundedRect: bounds.insetBy(dx: canvas * 0.035, dy: canvas * 0.035), xRadius: radius, yRadius: radius)
    background.addClip()

    let gradient = NSGradient(colors: [
        NSColor(calibratedRed: 0.05, green: 0.20, blue: 0.35, alpha: 1.0),
        NSColor(calibratedRed: 0.02, green: 0.48, blue: 0.55, alpha: 1.0),
        NSColor(calibratedRed: 0.20, green: 0.70, blue: 0.62, alpha: 1.0),
    ])
    gradient?.draw(in: bounds, angle: 315)

    NSColor(calibratedWhite: 1.0, alpha: 0.14).setFill()
    NSBezierPath(ovalIn: NSRect(x: canvas * 0.57, y: canvas * 0.60, width: canvas * 0.42, height: canvas * 0.42)).fill()

    NSColor(calibratedWhite: 0.0, alpha: 0.20).setFill()
    let shadow = NSBezierPath(
        roundedRect: NSRect(x: canvas * 0.24, y: canvas * 0.17, width: canvas * 0.56, height: canvas * 0.68),
        xRadius: canvas * 0.055,
        yRadius: canvas * 0.055
    )
    shadow.transform(using: AffineTransform(translationByX: canvas * 0.025, byY: -canvas * 0.025))
    shadow.fill()

    let documentRect = NSRect(x: canvas * 0.22, y: canvas * 0.20, width: canvas * 0.56, height: canvas * 0.68)
    let document = NSBezierPath(roundedRect: documentRect, xRadius: canvas * 0.055, yRadius: canvas * 0.055)
    NSColor(calibratedRed: 0.96, green: 0.99, blue: 1.0, alpha: 1.0).setFill()
    document.fill()

    NSColor(calibratedRed: 0.06, green: 0.24, blue: 0.34, alpha: 0.18).setStroke()
    document.lineWidth = max(1.0, canvas * 0.012)
    document.stroke()

    let fold = NSBezierPath()
    fold.move(to: NSPoint(x: documentRect.maxX - canvas * 0.17, y: documentRect.maxY))
    fold.line(to: NSPoint(x: documentRect.maxX, y: documentRect.maxY - canvas * 0.17))
    fold.line(to: NSPoint(x: documentRect.maxX - canvas * 0.17, y: documentRect.maxY - canvas * 0.17))
    fold.close()
    NSColor(calibratedRed: 0.82, green: 0.93, blue: 0.96, alpha: 1.0).setFill()
    fold.fill()

    let lineColor = NSColor(calibratedRed: 0.08, green: 0.32, blue: 0.42, alpha: 0.78)
    for index in 0..<3 {
        let width = [0.34, 0.42, 0.28][index] * canvas
        let y = documentRect.maxY - canvas * (0.27 + CGFloat(index) * 0.105)
        let line = NSBezierPath(roundedRect: NSRect(x: documentRect.minX + canvas * 0.095, y: y, width: width, height: canvas * 0.024), xRadius: canvas * 0.012, yRadius: canvas * 0.012)
        lineColor.setFill()
        line.fill()
    }

    let accent = NSColor(calibratedRed: 0.96, green: 0.67, blue: 0.21, alpha: 1.0)
    let play = NSBezierPath()
    play.move(to: NSPoint(x: documentRect.minX + canvas * 0.15, y: documentRect.minY + canvas * 0.13))
    play.line(to: NSPoint(x: documentRect.minX + canvas * 0.15, y: documentRect.minY + canvas * 0.29))
    play.line(to: NSPoint(x: documentRect.minX + canvas * 0.29, y: documentRect.minY + canvas * 0.21))
    play.close()
    accent.setFill()
    play.fill()

    accent.setStroke()
    for index in 0..<3 {
        let wave = NSBezierPath()
        let x = documentRect.minX + canvas * (0.36 + CGFloat(index) * 0.09)
        let y = documentRect.minY + canvas * 0.13
        wave.move(to: NSPoint(x: x, y: y))
        wave.curve(
            to: NSPoint(x: x, y: y + canvas * 0.16),
            controlPoint1: NSPoint(x: x + canvas * 0.035, y: y + canvas * 0.035),
            controlPoint2: NSPoint(x: x + canvas * 0.035, y: y + canvas * 0.125)
        )
        wave.lineWidth = max(1.4, canvas * 0.016)
        wave.lineCapStyle = .round
        wave.stroke()
    }

    return image
}
