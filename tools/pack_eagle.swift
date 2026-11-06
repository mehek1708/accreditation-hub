import Foundation
import AppKit
let frames=(0..<60).map { NSImage(contentsOfFile:String(format:"static/eagle-frames/%03d.png",$0))!.cgImage(forProposedRect:nil,context:nil,hints:nil)! }
let width=540, height=420, columns=10, rows=6
let context=CGContext(data:nil,width:width*columns,height:height*rows,bitsPerComponent:8,bytesPerRow:0,space:CGColorSpaceCreateDeviceRGB(),bitmapInfo:CGImageAlphaInfo.premultipliedLast.rawValue)!
for (i,frame) in frames.enumerated(){
 let crop=frame.cropping(to:CGRect(x:0,y:270,width:width,height:height))!
 context.draw(crop,in:CGRect(x:(i%columns)*width,y:(rows-1-i/columns)*height,width:width,height:height))
 if i==59 {try NSBitmapImageRep(cgImage:crop).representation(using:.png,properties:[:])!.write(to:URL(fileURLWithPath:"static/eagle-cutout.png"))}
}
try NSBitmapImageRep(cgImage:context.makeImage()!).representation(using:.png,properties:[:])!.write(to:URL(fileURLWithPath:"static/eagle-sprite.png"))
print("Packed transparent 60-frame sequence")
