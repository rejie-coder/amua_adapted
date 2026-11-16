import AppKit
import PDFKit

let destination=CommandLine.arguments[1]
let width=1200, height=1500
let rep=NSBitmapImageRep(bitmapDataPlanes:nil,pixelsWide:width,pixelsHigh:height,bitsPerSample:8,samplesPerPixel:4,hasAlpha:true,isPlanar:false,colorSpaceName:.deviceRGB,bytesPerRow:width*4,bitsPerPixel:32)!
let context=NSGraphicsContext(bitmapImageRep:rep)!
NSGraphicsContext.saveGraphicsState()
NSGraphicsContext.current=context
NSColor.white.setFill(); NSRect(x:0,y:0,width:width,height:height).fill()
let attributes:[NSAttributedString.Key:Any]=[.font:NSFont.systemFont(ofSize:40),.foregroundColor:NSColor.black]
let lines=["SYNTHETIC RESEARCH PAPER", "Equipment price: 125 LKR", "Study year: 2026", "Sample size: 100 patients", "Verify all recognized values."]
for (index,line) in lines.enumerated(){(line as NSString).draw(at:NSPoint(x:90,y:height-160-index*110),withAttributes:attributes)}
context.flushGraphics();NSGraphicsContext.restoreGraphicsState()
let image=NSImage(cgImage:rep.cgImage!,size:NSSize(width:width,height:height))
let document=PDFDocument();document.insert(PDFPage(image:image)!,at:0)
if !document.write(to:URL(fileURLWithPath:destination)){exit(1)}
print("Created synthetic image-only PDF fixture")
