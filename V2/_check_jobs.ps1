$printers = Get-Printer
foreach ($p in $printers) {
    Write-Output ("--- " + $p.Name + " ---")
    $jobs = Get-PrintJob -PrinterName $p.Name -ErrorAction SilentlyContinue
    if ($jobs) {
        $jobs | Format-Table Id, DocumentName, JobStatus, Size, SubmissionTime -AutoSize
    } else {
        Write-Output "No active print jobs."
    }
}
