$ips = @('192.168.50.89','192.168.50.93')
$ports = @(21, 22, 23, 80, 443, 515, 631, 9100, 9101, 9102, 161)

foreach ($ip in $ips) {
    foreach ($port in $ports) {
        try {
            $sock = New-Object System.Net.Sockets.TcpClient
            $ar = $sock.BeginConnect($ip, $port, $null, $null)
            $ar.AsyncWaitHandle.WaitOne(500) | Out-Null
            if ($sock.Connected) {
                $svc = switch ($port) { 21 {"FTP"}; 22 {"SSH"}; 23 {"Telnet"}; 80 {"HTTP"}; 443 {"HTTPS"}; 515 {"LPD"}; 631 {"IPP"}; 9100 {"JetDirect"}; 9101 {"JetDirect2"}; 9102 {"JetDirect3"}; 161 {"SNMP"}; default {"?"} }
                Write-Output ("$ip : port $port ($svc) OPEN")
            }
            $sock.Close()
        } catch {}
    }
}
Write-Output "--- Deep scan complete ---"
