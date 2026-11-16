import Foundation
import AppKit
import PDFKit
import Vision
import Darwin

// Local one-page OCR only. No URLs, subprocesses, logging, write paths or UI.
let maxInputBytes = 25 * 1024 * 1024
let absolutePixelLimit = 8_000_000
let parentPID = getppid()
if parentPID <= 1 { _exit(125) }
let started = DispatchTime.now().uptimeNanoseconds
let nullFD = open("/dev/null", O_WRONLY)
if nullFD >= 0 { dup2(nullFD, STDERR_FILENO); close(nullFD) }
func finish(_ value: [String:Any], _ code: Int32 = 0) -> Never {
    if var data = try? JSONSerialization.data(withJSONObject: value, options: [.sortedKeys]) {
        if data.count > 4 * 1024 * 1024 {
            data = (try? JSONSerialization.data(withJSONObject:result("unreadable","output_limit",value["page"] as? Int ?? 0),options:[.sortedKeys])) ?? Data()
        }
        FileHandle.standardOutput.write(data)
        FileHandle.standardOutput.write(Data([10]))
    }
    _exit(code)
}
func result(_ status: String, _ reason: String, _ page: Int = 0) -> [String:Any] {
    return ["schema":1,"status":status,"reason_category":reason,"page":page,
            "text":"","regions":[],"confidence":0.0,"language":"en-US",
            "engine":"Apple Vision","review_status":"unreviewed_ocr"]
}
var flags: [String:String] = [:]
let arguments = CommandLine.arguments
if arguments.count != 7 { finish(result("unsupported","invalid_arguments")) }
for index in stride(from: 1, to: arguments.count, by: 2) {
    let key = arguments[index]
    if !["--pdf","--page","--max-pixels"].contains(key) || flags[key] != nil {
        finish(result("unsupported","invalid_arguments"))
    }
    flags[key] = arguments[index+1]
}
guard let input = flags["--pdf"], (input as NSString).isAbsolutePath,
      let pageNumber = Int(flags["--page"] ?? ""), pageNumber > 0,
      let requestedPixels = Int(flags["--max-pixels"] ?? ""), requestedPixels > 0,
      requestedPixels <= absolutePixelLimit else { finish(result("unsupported","invalid_arguments")) }
let watchdog = DispatchSource.makeTimerSource(queue: DispatchQueue.global(qos:.utility))
watchdog.schedule(deadline:.now(), repeating:.milliseconds(100))
watchdog.setEventHandler {
    if getppid() != parentPID { _exit(125) }
    if DispatchTime.now().uptimeNanoseconds - started > 15_000_000_000 {
        let value = result("unreadable","timeout",pageNumber)
        if let data = try? JSONSerialization.data(withJSONObject:value) {
            _ = fcntl(STDOUT_FILENO,F_SETFL,O_NONBLOCK)
            data.withUnsafeBytes { pointer in _ = Darwin.write(STDOUT_FILENO,pointer.baseAddress,data.count) }
        }
        _exit(124)
    }
}
watchdog.resume()
DispatchQueue.global(qos:.userInitiated).async {
    autoreleasepool {
        let fd = open(input, O_RDONLY | O_NOFOLLOW | O_NONBLOCK)
        guard fd >= 0 else { finish(result("unsupported","input_unavailable",pageNumber)) }
        var information = stat()
        guard fstat(fd,&information) == 0,
              (information.st_mode & S_IFMT) == S_IFREG,
              information.st_size > 0, information.st_size <= maxInputBytes else {
            close(fd); finish(result("unsupported","input_limit_or_type",pageNumber))
        }
        let handle = FileHandle(fileDescriptor:fd, closeOnDealloc:true)
        guard let bytes = try? handle.read(upToCount:maxInputBytes+1),
              bytes.count <= maxInputBytes,
              bytes.starts(with:Data("%PDF-".utf8)) else {
            try? handle.close();finish(result("unsupported","invalid_pdf",pageNumber))
        }
        try? handle.close()
        guard let document = PDFDocument(data:bytes) else { finish(result("unsupported","invalid_pdf",pageNumber)) }
        guard !document.isEncrypted && !document.isLocked else { finish(result("unsupported","encrypted",pageNumber)) }
        guard document.pageCount <= 2000, pageNumber <= document.pageCount,
              let page = document.page(at:pageNumber-1) else { finish(result("unsupported","page_out_of_range",pageNumber)) }
        let bounds = page.bounds(for:.cropBox)
        guard bounds.width.isFinite, bounds.height.isFinite,
              bounds.width > 0, bounds.height > 0,
              bounds.width <= 144_000, bounds.height <= 144_000 else {
            finish(result("unsupported","invalid_page_geometry",pageNumber))
        }
        var width = bounds.width * 150.0 / 72.0
        var height = bounds.height * 150.0 / 72.0
        if page.rotation % 180 != 0 { swap(&width,&height) }
        let factor = min(1.0,sqrt(Double(requestedPixels)/(width*height)))
        let target = NSSize(width:max(1,floor(width*factor)),height:max(1,floor(height*factor)))
        let thumbnail = page.thumbnail(of:target,for:.cropBox)
        guard let image = thumbnail.cgImage(forProposedRect:nil,context:nil,hints:nil),
              image.width > 0, image.height > 0,
              image.width * image.height <= requestedPixels else {
            finish(result("unreadable","rasterization_failed",pageNumber))
        }
        let request = VNRecognizeTextRequest()
        request.recognitionLevel = .accurate
        request.recognitionLanguages = ["en-US"]
        request.usesLanguageCorrection = false
        request.minimumTextHeight = 0.005
        do { try VNImageRequestHandler(cgImage:image,options:[:]).perform([request]) }
        catch {
            request.usesCPUOnly = true
            do { try VNImageRequestHandler(cgImage:image,options:[:]).perform([request]) }
            catch {
            let problem = error as NSError
            var failure = result("unreadable","recognition_failed",pageNumber)
            if problem.domain == NSOSStatusErrorDomain && problem.code == -6662 { failure["reason_category"] = "vision_buffer_allocation_failed" }
            failure["diagnostic_domain"] = problem.domain
            failure["diagnostic_code"] = problem.code
            failure["recovery"] = "Try the same page in the Finder-launched app. Keep this page unresolved if recognition fails."
            finish(failure)
            }
        }
        let observations = (request.results ?? []).sorted {
            let rowA = Int(($0.boundingBox.midY * 80).rounded())
            let rowB = Int(($1.boundingBox.midY * 80).rounded())
            return rowA != rowB ? rowA > rowB : $0.boundingBox.minX < $1.boundingBox.minX
        }
        var regions: [[String:Any]] = []
        var text: [String] = []
        var confidence: Double = 0
        var outputBytes = 0
        for observation in observations {
            guard let candidate = observation.topCandidates(1).first else { continue }
            let line = candidate.string.trimmingCharacters(in:.whitespacesAndNewlines)
            if line.isEmpty { continue }
            outputBytes += line.utf8.count
            if regions.count >= 5000 || outputBytes > 1_000_000 { finish(result("unreadable","output_limit",pageNumber)) }
            let box = observation.boundingBox
            regions.append(["text":line,"confidence":Double(candidate.confidence),
                            "bounds":["x":box.minX,"y":box.minY,"width":box.width,"height":box.height]])
            text.append(line);confidence += Double(candidate.confidence)
        }
        if text.isEmpty { finish(result("unreadable","empty",pageNumber)) }
        finish(["schema":1,"status":"ok","reason_category":"recognized","page":pageNumber,
                "text":text.joined(separator:"\n"),"regions":regions,
                "confidence":confidence/Double(regions.count),"language":"en-US",
                "engine":"Apple Vision","algorithm_revision":request.revision,"review_status":"unreviewed_ocr",
                "raster":["width":image.width,"height":image.height,"requested_dpi":150,"pixel_limit":requestedPixels],
                "elapsed_ms":Double(DispatchTime.now().uptimeNanoseconds-started)/1_000_000])
    }
}
dispatchMain()
