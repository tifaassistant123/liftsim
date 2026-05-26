$printerName = "Brother MFC-T910DW"
$jobId = 3

# 1. Try to remove the stuck job
Write-Output "Step 1: Removing stuck print job ID $jobId..."
try {
    Remove-PrintJob -PrinterName $printerName -Id $jobId -ErrorAction SilentlyContinue
    Write-Output "Job removed."
} catch {
    Write-Output "Remove failed: " + $_.Exception.Message
    
    # Alternative: Clear via WMI
    Write-Output "Trying WMI method..."
    $job = Get-WmiObject -Class Win32_PrintJob | Where-Object { $_.Document -like "*Working Visa*" }
    if ($job) {
        $job.Delete()
        Write-Output "Job deleted via WMI."
    }
}

Start-Sleep -Seconds 1

# 2. Restart print spooler
Write-Output ""
Write-Output "Step 2: Restarting Print Spooler..."
Restart-Service -Name Spooler -Force
Write-Output "Print Spooler restarted."
Start-Sleep -Seconds 2

# 3. Verify clear queue
Write-Output ""
Write-Output "Step 3: Verifying queue is clear..."
$jobs = Get-PrintJob -PrinterName $printerName -ErrorAction SilentlyContinue
if ($jobs) {
    $jobs | Format-Table Id, DocumentName, JobStatus -AutoSize
    Write-Output "Jobs still present - may need manual check on the printer itself."
} else {
    Write-Output "Queue is clear! Ready to print again. ✅"
}
