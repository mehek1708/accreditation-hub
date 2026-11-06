import Foundation
import AVFoundation
import AppKit
let asset = AVURLAsset(url:URL(fileURLWithPath:CommandLine.arguments[1]))
let composition = AVMutableComposition()
let source = asset.tracks(withMediaType:.video)[0]
let track = composition.addMutableTrack(withMediaType:.video, preferredTrackID:kCMPersistentTrackID_Invalid)!
try track.insertTimeRange(CMTimeRange(start:CMTime(seconds:4,preferredTimescale:600),duration:CMTime(seconds:4,preferredTimescale:600)),of:source,at:.zero)
track.preferredTransform = source.preferredTransform
let exporter = AVAssetExportSession(asset:composition,presetName:AVAssetExportPreset1280x720)!
exporter.outputURL=URL(fileURLWithPath:"static/eagle-flight.mp4")
exporter.outputFileType = .mp4
exporter.shouldOptimizeForNetworkUse=true
let semaphore=DispatchSemaphore(value:0)
exporter.exportAsynchronously { semaphore.signal() }
semaphore.wait()
if exporter.status != .completed { fatalError("Export failed: \(String(describing:exporter.error))") }
let generator=AVAssetImageGenerator(asset:asset)
generator.appliesPreferredTrackTransform=true
generator.maximumSize=CGSize(width:720,height:1280)
let cg=try generator.copyCGImage(at:CMTime(seconds:8,preferredTimescale:600),actualTime:nil)
let rep=NSBitmapImageRep(cgImage:cg)
try rep.representation(using:.jpeg,properties:[.compressionFactor:0.85])!.write(to:URL(fileURLWithPath:"static/eagle-poster.jpg"))
print("Exported four-second silent clip and poster.")
