// Platform export of the approved raster. The monogram and glass remain intact.
// A clean rounded silhouette trims the generation fringe outside the tile.
import AppKit
import Foundation

guard CommandLine.arguments.count == 3 else {
    fputs("usage: export_icons.swift <approved.png> <output-directory>\n", stderr)
    exit(64)
}
let source = NSImage(contentsOfFile: CommandLine.arguments[1])!
source.size = NSSize(width: 1280, height: 1280)
let output = URL(fileURLWithPath: CommandLine.arguments[2], isDirectory: true)
try FileManager.default.createDirectory(at: output, withIntermediateDirectories: true)
for pixels in [16, 32, 48, 64, 128, 180, 192, 256, 512, 1024] {
    let bitmap = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: pixels,
        pixelsHigh: pixels, bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true,
        isPlanar: false, colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0)!
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: bitmap)
    NSGraphicsContext.current?.imageInterpolation = .high
    NSGraphicsContext.current?.shouldAntialias = true
    let size = CGFloat(pixels)
    let tile = NSRect(x: size / 16, y: size / 16, width: size * 7 / 8, height: size * 7 / 8)
    let radius = tile.width * 0.235
    NSBezierPath(roundedRect: tile, xRadius: radius, yRadius: radius).addClip()
    // AppKit's source coordinates start at the bottom-left.
    source.draw(in: tile, from: NSRect(x: 118, y: 138, width: 1008, height: 1008),
                operation: .copy, fraction: 1)
    NSGraphicsContext.restoreGraphicsState()
    try bitmap.representation(using: .png, properties: [:])!.write(
        to: output.appendingPathComponent("read-docs-\(pixels).png"))
}
