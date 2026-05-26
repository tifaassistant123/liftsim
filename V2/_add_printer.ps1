Add-Printer -ConnectionName "\\192.168.50.93\lp" -ErrorAction SilentlyContinue
if (!$?) {
    Write-Output "Direct LPD connection failed, trying standard port..."
    Add-PrinterPort -Name "LPD_Printer" -PrinterHostAddress "192.168.50.93" -PortNumber 515 -SNMPCommunity "" -SNMPEnabled $false -SNMPDevIndex 1
    Write-Output "Trying to find available LPD printers on the network..."
}
Write-Output "---"
Get-Printer | Format-Table Name, PortName, DriverName -AutoSize
