import Foundation
import AVFoundation
import AppKit
let asset = AVURLAsset(url: URL(fileURLWithPath: CommandLine.arguments[1]))
print("Duration: \(CMTimeGetSeconds(asset.duration))")
let generator = AVAssetImageGenerator(asset: asset)
generator.appliesPreferredTrackTransform = true
generator.maximumSize = CGSize(width: 360, height: 640)
for second in [0, 1, 2, 3, 4, 6, 8] {
 do {
  let cg = try generator.copyCGImage(at: CMTime(seconds: Double(second), preferredTimescale: 600), actualTime: nil)
  let image = NSBitmapImageRep(cgImage: cg)
  try image.representation(using: .jpeg, properties: [.compressionFactor:0.8])!.write(to: URL(fileURLWithPath:"data/media-preview/frame-\(second).jpg"))
 } catch { print(error) }
}
