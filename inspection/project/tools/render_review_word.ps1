param([Parameter(Mandatory=$true)][string]$InputPath, [Parameter(Mandatory=$true)][string]$OutputPath)
$documentPath = (Resolve-Path -LiteralPath $InputPath).Path
$pdfPath = [IO.Path]::GetFullPath($OutputPath)
[IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($pdfPath)) | Out-Null
$word = New-Object -ComObject Word.Application
$previousVisible = $word.Visible
$previousAlerts = $word.DisplayAlerts
$initialDocuments = $word.Documents.Count
$document = $null
try {
    if ($initialDocuments -eq 0) { $word.Visible = $false }
    $word.DisplayAlerts = 0
    $document = $word.Documents.Open($documentPath, $false, $true)
    $document.ExportAsFixedFormat($pdfPath, 17)
    Write-Output "Native Word PDF created"
} finally {
    if ($null -ne $document) { $document.Close(0) }
    $word.DisplayAlerts = $previousAlerts
    if ($initialDocuments -eq 0 -and $word.Documents.Count -eq 0) { $word.Quit() }
    else { $word.Visible = $previousVisible }
}
