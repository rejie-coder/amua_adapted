$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
Add-Type -AssemblyName System.Runtime.WindowsRuntime
function Wait-Operation($Operation, [Type]$ResultType) {
    $Method = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.IsGenericMethodDefinition -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' } | Select-Object -First 1
    $Task = $Method.MakeGenericMethod($ResultType).Invoke($null, @($Operation))
    $Task.GetAwaiter().GetResult()
}
function Wait-Action($Operation) {
    $Method = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and -not $_.IsGenericMethod -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncAction' } | Select-Object -First 1
    $Task = $Method.Invoke($null, @($Operation)); $Task.GetAwaiter().GetResult() | Out-Null
}
try {
    $StorageFile = [Windows.Storage.StorageFile, Windows.Storage, ContentType=WindowsRuntime]
    $PdfDocument = [Windows.Data.Pdf.PdfDocument, Windows.Data.Pdf, ContentType=WindowsRuntime]
    $MemoryStream = [Windows.Storage.Streams.InMemoryRandomAccessStream, Windows.Storage.Streams, ContentType=WindowsRuntime]
    $Decoder = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics.Imaging, ContentType=WindowsRuntime]
    $Bitmap = [Windows.Graphics.Imaging.SoftwareBitmap, Windows.Graphics.Imaging, ContentType=WindowsRuntime]
    $OcrEngine = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType=WindowsRuntime]
    $OcrResult = [Windows.Media.Ocr.OcrResult, Windows.Foundation, ContentType=WindowsRuntime]
    $Language = [Windows.Globalization.Language, Windows.Globalization, ContentType=WindowsRuntime]
    $PageNumber = [int]$env:AMUA_OCR_PAGE
    $PdfBytes = [Convert]::FromBase64String([Console]::In.ReadToEnd())
    $SourceMemory = [System.IO.MemoryStream]::new([byte[]]$PdfBytes, $false)
    $PdfStream = [System.IO.WindowsRuntimeStreamExtensions]::AsRandomAccessStream($SourceMemory)
    $Pdf = Wait-Operation ($PdfDocument::LoadFromStreamAsync($PdfStream)) $PdfDocument
    if ($PageNumber -lt 1 -or $PageNumber -gt $Pdf.PageCount) { throw 'invalid page' }
    $Page = $Pdf.GetPage($PageNumber - 1)
    $MaxPixels = [Math]::Min(8000000, [int]$env:AMUA_OCR_PIXELS)
    $Scale = [Math]::Min(2.0, [Math]::Sqrt($MaxPixels / ($Page.Size.Width * $Page.Size.Height)))
    $Scale = [Math]::Min($Scale, $OcrEngine::MaxImageDimension / [Math]::Max($Page.Size.Width, $Page.Size.Height))
    $Options = New-Object Windows.Data.Pdf.PdfPageRenderOptions
    $Options.DestinationWidth = [uint32][Math]::Max(1, [Math]::Floor($Page.Size.Width * $Scale))
    $Options.DestinationHeight = [uint32][Math]::Max(1, [Math]::Floor($Page.Size.Height * $Scale))
    $Stream = New-Object Windows.Storage.Streams.InMemoryRandomAccessStream
    Wait-Action ($Page.RenderToStreamAsync($Stream, $Options))
    $Decode = Wait-Operation ($Decoder::CreateAsync($Stream)) $Decoder
    $Image = Wait-Operation ($Decode.GetSoftwareBitmapAsync([Windows.Graphics.Imaging.BitmapPixelFormat]::Bgra8, [Windows.Graphics.Imaging.BitmapAlphaMode]::Premultiplied)) $Bitmap
    $Engine = $OcrEngine::TryCreateFromLanguage((New-Object Windows.Globalization.Language 'en-US'))
    if ($null -eq $Engine) { @{status='unsupported'; reason_category='windows-english-ocr-language-unavailable'; language='en-US'; page=$PageNumber} | ConvertTo-Json -Compress; exit 0 }
    $Result = Wait-Operation ($Engine.RecognizeAsync($Image)) $OcrResult
    $Regions = @(); foreach ($Line in $Result.Lines) {
        foreach ($Word in $Line.Words) {
            $Rect = $Word.BoundingRect
            $Regions += @{text=$Word.Text; confidence=0; bounds=@(($Rect.X/$Image.PixelWidth), (1-($Rect.Y+$Rect.Height)/$Image.PixelHeight), ($Rect.Width/$Image.PixelWidth), ($Rect.Height/$Image.PixelHeight))}
            if ($Regions.Count -gt 5000) { throw 'region limit' }
        }
    }
    @{status='ok'; text=$Result.Text; confidence=0; confidence_note='Windows OCR does not expose confidence; no estimate invented'; regions=$Regions; language='en-US'; page=$PageNumber} | ConvertTo-Json -Depth 6 -Compress
    $Page.Dispose(); $Stream.Dispose(); $Image.Dispose(); $PdfStream.Dispose(); $SourceMemory.Dispose()
} catch {
    $Issue = $_.Exception; for ($i=0; $i -lt 4 -and $null -ne $Issue.InnerException; $i++) { $Issue = $Issue.InnerException }; $Code = '0x' + $Issue.HResult.ToString('X8')
    @{status='unsupported'; reason_category='windows-ocr-unavailable-or-unreadable'; diagnostic_code=$Code; language='en-US'; page=[int]$env:AMUA_OCR_PAGE} | ConvertTo-Json -Compress
}
