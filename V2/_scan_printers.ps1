$ips = @('192.168.50.1','192.168.50.3','192.168.50.56','192.168.50.68','192.168.50.89','192.168.50.93')
$ports = @(80, 443, 515, 631, 9100)

foreach ($ip in $ips) {
    foreach ($port in $ports) {
        try {
            $sock = New-Object System.Net.Sockets.TcpClient
            $ar = $sock.BeginConnect($ip, $port, $null, $null)
            $ar.AsyncWaitHandle.WaitOne(300) | Out-Null
            if ($sock.Connected) {
                $svc = switch ($port) { 80 {"HTTP"}; 443 {"HTTPS"}; 515 {"LPD"}; 631 {"IPP"}; 9100 {"JetDirect"}; default {"?"} }
                Write-Output ("$ip : port $port ($svc) OPEN")
            }
            $sock.Close()
        } catch {}
    }
}
Write-Output "--- Scan complete ---"
