import Foundation
import AVFoundation
import Vision
import CoreImage
import AppKit
let asset=AVURLAsset(url:URL(fileURLWithPath:"static/eagle-flight.mp4"))
let generator=AVAssetImageGenerator(asset:asset)
generator.appliesPreferredTrackTransform=true
generator.maximumSize=CGSize(width:540,height:960)
generator.requestedTimeToleranceBefore = .zero
generator.requestedTimeToleranceAfter = .zero
let context=CIContext()
let count=CommandLine.arguments.count>1 ? Int(CommandLine.arguments[1])! : 1
try FileManager.default.createDirectory(atPath:"static/eagle-frames",withIntermediateDirectories:true)
for i in 0..<count {
 autoreleasepool {
 do {
  let cg=try generator.copyCGImage(at:CMTime(seconds:Double(i)/15,preferredTimescale:600),actualTime:nil)
  let request=VNGenerateForegroundInstanceMaskRequest()
  let handler=VNImageRequestHandler(cgImage:cg,options:[:])
  try handler.perform([request])
  guard let result=request.results?.first, !result.allInstances.isEmpty else {fatalError("No foreground at frame \(i)")}
  let mask=try result.generateScaledMaskForImage(forInstances:result.allInstances,from:handler)
  let input=CIImage(cgImage:cg)
  let clear=CIImage(color:.clear).cropped(to:input.extent)
  let output=input.applyingFilter("CIBlendWithMask",parameters:[kCIInputBackgroundImageKey:clear,kCIInputMaskImageKey:CIImage(cvPixelBuffer:mask)])
  let rendered=context.createCGImage(output,from:input.extent)!
  let bitmap=NSBitmapImageRep(cgImage:rendered)
  try bitmap.representation(using:.png,properties:[:])!.write(to:URL(fileURLWithPath:String(format:"static/eagle-frames/%03d.png",i)))
  print("Frame \(i)")
 } catch {fatalError("Frame \(i): \(error)")}
 }
}
