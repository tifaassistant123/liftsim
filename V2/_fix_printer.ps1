$printerName = "Brother MFC-T910DW"

# Check printer status
$printer = Get-Printer -Name $printerName -ErrorAction SilentlyContinue
if ($printer) {
    Write-Output ("Printer: " + $printer.Name)
    Write-Output ("Status: " + $printer.PrinterStatus)
    Write-Output ("Job count: " + $printer.JobCount)
    Write-Output ("Port: " + $printer.PortName)
    Write-Output ("Location: " + $printer.Location)
    Write-Output ("Comment: " + $printer.Comment)
    Write-Output ("Shared: " + $printer.IsShared)
    Write-Output ("")
}

# Get the stuck job
$job = Get-PrintJob -PrinterName $printerName -ErrorAction SilentlyContinue
if ($job) {
    Write-Output ("Stuck job details:")
    $job | Format-Table Id, DocumentName, JobStatus, Size, SubmissionTime -AutoSize
    Write-Output ("")
    
    # Try to restart the job
    Write-Output ("Attempting to restart the print job...")
    try {
        Restart-PrintJob -PrinterName $printerName -Id $job.Id -ErrorAction SilentlyContinue
        Write-Output ("Job restarted. New status:")
        Start-Sleep -Seconds 2
        Get-PrintJob -PrinterName $printerName -ErrorAction SilentlyContinue | Format-Table Id, DocumentName, JobStatus -AutoSize
    } catch {
        Write-Output ("Restart failed: " + $_.Exception.Message)
    }
} else {
    Write-Output ("No active print jobs.")
}
